// Data Care ticket intake: the public "tell us what you lost" form and its API.
//
// Bare bones on purpose, and self-contained so it can be wired into the Data Care app later
// (app/src/handler.js) without changing anything else there:
//
//   import { handleTickets, sqlTicketStore } from "../../web/tickets/tickets.js";
//   const tickets = sqlTicketStore(query);           // the same query(text, params) the app uses
//   ...first thing inside handle():
//   const t = await handleTickets(request, env, tickets); if (t) return t;
//
// Routes
//   GET   /tickets               the form (public)
//   POST  /api/tickets           submit a ticket (public; JSON or form-encoded)
//   GET   /api/tickets[?status=] list tickets (x-cc-token, the app's shared token)
//   PATCH /api/tickets/<id>      update status / quote_usd / case_id (x-cc-token)
//
// The form never accepts file uploads: a client's damaged files may be infected, so files come in
// later through the case flow (Forensics scans and quarantines first). Nothing here sends email;
// the Recovery Manager replies with the quote and the install steps after a person approves.

import { FORM_HTML } from "./form.js";

export const KINDS = ["excel", "code", "other"];
export const ENVIRONMENTS = ["excel_desktop_windows", "excel_desktop_mac", "excel_web", "google_sheets",
  "codebase", "other", ""];
export const STATUSES = ["new", "quoted", "in_progress", "closed"];
const MAX_BODY_BYTES = 20_000;
const EMAIL = /^[^\s@<>"']{1,64}@[^\s@<>"']{1,190}\.[a-z]{2,24}$/i;

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });

function sameToken(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length || !b) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function newTicketId(now = new Date()) {
  const d = now.toISOString().slice(0, 10).replace(/-/g, "");
  const alphabet = "23456789ABCDEFGHJKMNPQRSTVWXYZ"; // no 0/O/1/I/L: easy to read out on a call
  const bytes = crypto.getRandomValues(new Uint8Array(5));
  return `T-${d}-${Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("")}`;
}

const clean = (v, max) => (typeof v === "string" ? v.replace(/\u0000/g, "").trim().slice(0, max) : "");

/** Validate a submission. Returns { ticket } or { error }. Never throws on bad input. */
export function validateTicket(input) {
  if (!input || typeof input !== "object") return { error: "send the form fields" };
  if (clean(input.website, 200)) return { spam: true }; // honeypot: humans never see this field
  const t = {
    name: clean(input.name, 120),
    email: clean(input.email, 254).toLowerCase(),
    company: clean(input.company, 160),
    kind: clean(input.kind, 20),
    environment: clean(input.environment, 40),
    description: clean(input.description, 5000),
    consent: input.consent === true || input.consent === "true" || input.consent === "on",
  };
  if (!t.name) return { error: "please tell us your name" };
  if (!EMAIL.test(t.email)) return { error: "please give an email address we can reply to" };
  if (!KINDS.includes(t.kind)) return { error: "pick what was lost: a spreadsheet, code, or something else" };
  if (!ENVIRONMENTS.includes(t.environment)) return { error: "pick where you use it, or leave it blank" };
  if (t.description.length < 20) return { error: "describe what was lost in at least a sentence (20 characters)" };
  if (!t.consent) return { error: "please agree that we may email you about this request" };
  return { ticket: t };
}

async function readBody(request) {
  const len = Number(request.headers.get("content-length") || 0);
  if (len > MAX_BODY_BYTES) return { tooBig: true };
  const text = await request.text();
  if (text.length > MAX_BODY_BYTES) return { tooBig: true };
  const type = request.headers.get("content-type") || "";
  if (type.includes("application/json")) {
    try { return { data: JSON.parse(text) }; } catch { return { data: null }; }
  }
  return { data: Object.fromEntries(new URLSearchParams(text)) };
}

/**
 * Handle ticket routes. Returns a Response, or null when the path is not a ticket route,
 * so the app's own handler can carry on.
 */
export async function handleTickets(request, env, store) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method;

  if (path === "/tickets" && method === "GET") {
    return new Response(FORM_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
  }
  if (path !== "/api/tickets" && !path.startsWith("/api/tickets/")) return null;

  try {
    if (path === "/api/tickets" && method === "POST") {
      const body = await readBody(request);
      if (body.tooBig) return json(413, { error: "that is too long; please shorten the description" });
      const v = validateTicket(body.data);
      if (v.spam) return json(201, { ok: true }); // look accepted, store nothing
      if (v.error) return json(400, { error: v.error });
      const row = await store.insert({ ticket_id: newTicketId(), status: "new", ...v.ticket });
      return json(201, {
        ok: true, ticket_id: row.ticket_id,
        message: `Thanks. Your reference is ${row.ticket_id}. We'll email ${row.email} with a quote ` +
          "and the install steps. Please don't send any files until we reply.",
      });
    }

    // Everything else reads or changes client data: the app's shared token only.
    if (!sameToken(request.headers.get("x-cc-token"), env.CC_API_TOKEN || "")) {
      return json(401, { error: "missing or wrong x-cc-token" });
    }
    if (path === "/api/tickets" && method === "GET") {
      const status = url.searchParams.get("status");
      if (status && !STATUSES.includes(status)) return json(400, { error: `status must be one of ${STATUSES.join(", ")}` });
      return json(200, { tickets: await store.list(status || null) });
    }
    const id = decodeURIComponent(path.slice("/api/tickets/".length));
    if (method === "PATCH" && id) {
      const body = await readBody(request);
      const p = body.data || {};
      const patch = {};
      if (p.status !== undefined) {
        if (!STATUSES.includes(p.status)) return json(400, { error: `status must be one of ${STATUSES.join(", ")}` });
        patch.status = p.status;
      }
      if (p.quote_usd !== undefined) {
        const q = Number(p.quote_usd);
        if (!Number.isFinite(q) || q < 0 || q > 1_000_000) return json(400, { error: "quote_usd must be a number of dollars" });
        patch.quote_usd = Math.round(q * 100) / 100;
      }
      if (p.case_id !== undefined) {
        if (!/^C-\d{4,}$/.test(String(p.case_id))) return json(400, { error: "case_id looks like C-0001" });
        patch.case_id = String(p.case_id);
      }
      if (!Object.keys(patch).length) return json(400, { error: "send status, quote_usd or case_id" });
      const row = await store.update(id, patch);
      return row ? json(200, row) : json(404, { error: `ticket ${id} not found` });
    }
    return json(405, { error: "method not allowed" });
  } catch (err) {
    return json(500, { error: "could not save the ticket, please try again" });
  }
}

// ---------------------------------------------------------------- stores

/** Postgres/Neon store over the app's query(text, params) -> rows. Table: web/tickets/tickets.sql */
export function sqlTicketStore(query) {
  const COLS = "ticket_id, status, name, email, company, kind, environment, description, consent, " +
    "quote_usd, case_id, created_at, updated_at";
  return {
    async insert(t) {
      const rows = await query(
        `insert into tickets (ticket_id, status, name, email, company, kind, environment, description, consent)
         values ($1,$2,$3,$4,$5,$6,$7,$8,$9) returning ${COLS}`,
        [t.ticket_id, t.status, t.name, t.email, t.company, t.kind, t.environment, t.description, t.consent]);
      return rows[0];
    },
    async list(status) {
      return status
        ? query(`select ${COLS} from tickets where status = $1 order by created_at desc limit 200`, [status])
        : query(`select ${COLS} from tickets order by created_at desc limit 200`, []);
    },
    async update(id, patch) {
      const keys = Object.keys(patch);
      const sets = keys.map((k, i) => `${k} = $${i + 2}`).join(", ");
      const rows = await query(`update tickets set ${sets}, updated_at = now() where ticket_id = $1 returning ${COLS}`,
        [id, ...keys.map((k) => patch[k])]);
      return rows[0] || null;
    },
  };
}

/** In-memory store for local preview and tests. */
export function memoryTicketStore() {
  const rows = new Map();
  return {
    async insert(t) {
      const now = new Date().toISOString();
      const row = { quote_usd: null, case_id: null, ...t, created_at: now, updated_at: now };
      rows.set(t.ticket_id, row);
      return row;
    },
    async list(status) {
      return [...rows.values()].filter((r) => !status || r.status === status).reverse();
    },
    async update(id, patch) {
      const r = rows.get(id);
      if (!r) return null;
      Object.assign(r, patch, { updated_at: new Date().toISOString() });
      return r;
    },
  };
}
