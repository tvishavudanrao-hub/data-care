import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { handleConnectors, memoryConnectorStore, sqlConnectorStore, googleDrive, scout, searchTerms, seal, unseal,
  approvedMessage, LIMITS } from "./connectors.js";
import { handleTickets, memoryTicketStore, ticketMessage } from "../tickets/tickets.js";

const KEY = Buffer.alloc(32, 7).toString("base64");
const env = { CC_API_TOKEN: "tok", CONNECTOR_KEY: KEY, GOOGLE_CLIENT_ID: "cid", GOOGLE_CLIENT_SECRET: "csecret",
  PUBLIC_BASE_URL: "https://datacare.example" };
const good = { name: "Dana Okafor", email: "dana@example.com", company: "Alderbank", kind: "excel", environment: "",
  description: "Our quarterly forecast model lost its formulas; the ERP export and board report still exist.", consent: true };
const req = (method, path, body, headers = {}) => new Request("https://datacare.example" + path, { method, headers, body });

// A fake Google that answers like the real endpoints this code calls.
function fakeGoogle(files, { scope = "https://www.googleapis.com/auth/drive.readonly openid email" } = {}) {
  const calls = [];
  const idToken = "x." + Buffer.from(JSON.stringify({ email: "dana@alderbank.example" })).toString("base64url") + ".y";
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    const u = new URL(url);
    if (u.href.startsWith("https://oauth2.googleapis.com/token")) {
      const p = new URLSearchParams(init.body);
      if (p.get("grant_type") === "authorization_code") {
        return Response.json({ access_token: "acc", refresh_token: "ref-secret", scope, id_token: idToken });
      }
      return Response.json({ access_token: "acc2" });
    }
    if (u.href.startsWith("https://oauth2.googleapis.com/revoke")) return new Response("");
    if (u.pathname === "/drive/v3/files") return Response.json({ files });
    const m = u.pathname.match(/^\/drive\/v3\/files\/([^/]+)(\/export)?$/);
    if (m) {
      const f = files.find((x) => x.id === decodeURIComponent(m[1]));
      return new Response(new Uint8Array(f.bytes ?? 10));
    }
    return new Response("nope", { status: 404 });
  };
  return { fetchImpl, calls };
}

async function setup(files, opts) {
  const tickets = memoryTicketStore();
  const store = memoryConnectorStore(tickets);
  const r = await handleTickets(req("POST", "/api/tickets", JSON.stringify(good), { "content-type": "application/json" }), env, tickets);
  const { ticket_id } = await r.json();
  const ticket = (await tickets.list(null)).find((t) => t.ticket_id === ticket_id);
  const g = fakeGoogle(files, opts);
  const uploads = [], sessions = [];
  const deps = { store, provider: googleDrive(env, g.fetchImpl), startSession: async (m) => { sessions.push(m); return "ses_1"; },
    files: { upload: async (f) => { uploads.push(f); return "fil_" + uploads.length; } } };
  return { tickets, store, ticket, g, uploads, sessions, deps };
}

async function connect(s) {
  const start = await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}/google`), env, s.deps);
  assert.equal(start.status, 302);
  const auth = new URL(start.headers.get("location"));
  return handleConnectors(req("GET", `/connect/google/callback?code=abc&state=${encodeURIComponent(auth.searchParams.get("state"))}`), env, s.deps);
}

const driveFiles = [
  { id: "d1", name: "Forecast model backup.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size: "5000" },
  { id: "d2", name: "ERP export Q3", mimeType: "application/vnd.google-apps.spreadsheet" },
  { id: "d3", name: "Board report Q3.pdf", mimeType: "application/pdf", size: String(LIMITS.maxFileBytes + 1) },
];

test("every ticket gets a connect link, passed to the Recovery Manager when switched on", async () => {
  const s = await setup([]);
  assert.match(s.ticket.connect_token, /^[0-9a-f]{48}$/);
  assert.match(ticketMessage(s.ticket, env), /"connect_url": "https:\/\/datacare\.example\/connect\/[0-9a-f]{48}"/);
  assert.doesNotMatch(ticketMessage(s.ticket, {}), /connect_url/);
});

test("connect page shows the trust promises and escapes client text", async () => {
  const s = await setup([]);
  s.ticket.name = "<script>alert(1)</script>";
  const r = await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}`), env, s.deps);
  const body = await r.text();
  assert.equal(r.status, 200);
  assert.match(body, /Read-only\./);
  assert.match(body, /Connect Google Drive \(read-only\)/);
  assert.doesNotMatch(body, /<script>alert/);
});

test("consent asks Google for read-only Drive access only", async () => {
  const s = await setup([]);
  const r = await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}/google`), env, s.deps);
  const u = new URL(r.headers.get("location"));
  assert.equal(u.origin + u.pathname, "https://accounts.google.com/o/oauth2/v2/auth");
  assert.equal(u.searchParams.get("scope"), "https://www.googleapis.com/auth/drive.readonly openid email");
  assert.equal(u.searchParams.get("redirect_uri"), "https://datacare.example/connect/google/callback");
  assert.equal(u.searchParams.get("access_type"), "offline");
});

test("full flow: connect -> search -> copy matches to <ticket>-incoming -> log -> start the RM", async () => {
  const s = await setup(driveFiles);
  const r = await connect(s);
  assert.equal(r.status, 302);
  assert.equal(r.headers.get("location"), `/connect/${s.ticket.connect_token}/status`);
  // copied: the xlsx and the exported Google Sheet; the oversized PDF is skipped
  assert.deepEqual(s.uploads.map((u) => [u.name, u.folder]),
    [["drive-Forecast model backup.xlsx", `${s.ticket.ticket_id}-incoming`], ["drive-ERP export Q3.xlsx", `${s.ticket.ticket_id}-incoming`]]);
  const log = await s.store.accessLog(s.ticket.ticket_id);
  assert.deepEqual(log.map((e) => e.action), ["fetched", "fetched", "skipped"]);
  assert.equal(log[2].reason, "too large");
  // the token is stored encrypted, never in clear
  const [c] = s.store._conns;
  assert.notEqual(c.sealed_refresh, "ref-secret");
  assert.equal(await unseal(env, c.sealed_refresh), "ref-secret");
  assert.equal(c.account, "dana@alderbank.example");
  // the Recovery Manager is told, with the files as data
  assert.equal(s.sessions.length, 1);
  assert.match(s.sessions[0], /WEBSITE TICKET APPROVED\. Follow section T2/);
  assert.match(s.sessions[0], /<<<APPROVED_DATA[\s\S]*"file_id": "fil_1"[\s\S]*APPROVED_DATA>>>/);
  assert.equal((await s.tickets.list(null))[0].status, "approved");
  // Drive search only asked for evidence types and the case's words
  const search = s.g.calls.find((c) => c.url.includes("/drive/v3/files?"));
  const q = new URL(search.url).searchParams.get("q");
  assert.match(q, /^trashed = false and \(/);
  assert.match(q, /fullText contains 'forecast'/);
});

test("a forged or tampered state is rejected and nothing is read", async () => {
  const s = await setup(driveFiles);
  const r = await handleConnectors(req("GET", `/connect/google/callback?code=abc&state=${s.ticket.connect_token}.aaaa.bbbb`), env, s.deps);
  assert.equal(r.status, 400);
  assert.equal(s.uploads.length, 0);
  assert.equal(s.g.calls.length, 0);
});

test("if the client unticks read-only Drive access, nothing is stored or read", async () => {
  const s = await setup(driveFiles, { scope: "openid email" });
  const r = await connect(s);
  assert.equal(r.status, 500);
  assert.equal(s.store._conns.length, 0);
  assert.equal(s.uploads.length, 0);
});

test("status page lists what we read; disconnect revokes at Google and wipes the token", async () => {
  const s = await setup(driveFiles);
  await connect(s);
  const page = await (await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}/status`), env, s.deps)).text();
  assert.match(page, /Forecast model backup\.xlsx/);
  assert.match(page, /copied for your case/);
  assert.match(page, /not copied: too large/);
  assert.match(page, /Disconnect now/);
  await handleConnectors(req("POST", `/connect/${s.ticket.connect_token}/disconnect`), env, s.deps);
  assert.ok(s.g.calls.some((c) => c.url === "https://oauth2.googleapis.com/revoke" && String(c.init.body).includes("ref-secret")));
  assert.equal(s.store._conns[0].sealed_refresh, "");
  assert.ok(s.store._conns[0].revoked_at);
  const after = await (await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}/status`), env, s.deps)).text();
  assert.match(after, /Our access has ended/);
});

test("expired connections are revoked by the cron route (token only)", async () => {
  const s = await setup(driveFiles);
  await connect(s);
  s.store._conns[0].created_at = "2020-01-01T00:00:00.000Z";
  assert.equal((await handleConnectors(req("POST", "/api/connectors/revoke-expired"), env, s.deps)).status, 401);
  const r = await handleConnectors(req("POST", "/api/connectors/revoke-expired", "", { "x-cc-token": "tok" }), env, s.deps);
  assert.deepEqual(await r.json(), { revoked: 1 });
  assert.ok(s.store._conns[0].revoked_at);
});

test("switched off unless all settings are present; other paths are left to the app", async () => {
  const s = await setup([]);
  assert.equal(await handleConnectors(req("GET", "/api/board"), env, s.deps), null);
  const r = await handleConnectors(req("GET", `/connect/${s.ticket.connect_token}`), { ...env, GOOGLE_CLIENT_SECRET: "" }, s.deps);
  assert.equal(r.status, 503);
  assert.equal((await handleConnectors(req("GET", "/connect/" + "0".repeat(48)), env, s.deps)).status, 404);
});

test("scout caps the number of files and total size", async () => {
  const s = await setup([]);
  const many = Array.from({ length: 5 }, (_, i) => ({ id: "f" + i, name: `forecast ${i}.csv`, mimeType: "text/csv", size: "100", bytes: 100 }));
  const provider = googleDrive(env, fakeGoogle(many).fetchImpl);
  const res = await scout({ provider, access: "a", ticket: s.ticket, terms: ["forecast"], store: s.store,
    files: { upload: async () => "fil" }, limits: { maxFiles: 2, maxFileBytes: 1000, maxTotalBytes: 1000 } });
  assert.equal(res.fetched.length, 2);
  assert.equal(res.skipped, 3);
});

test("search terms come from the ticket, without filler words", () => {
  const t = searchTerms(good);
  assert.ok(t.includes("forecast") && t.includes("export") && t.includes("alderbank"));
  assert.ok(!t.includes("still") && !t.includes("the"));
  assert.ok(t.length <= 10);
});

test("sealed tokens round-trip and differ each time", async () => {
  const a = await seal(env, "secret"), b = await seal(env, "secret");
  assert.notEqual(a, b);
  assert.equal(await unseal(env, a), "secret");
  await assert.rejects(unseal({ CONNECTOR_KEY: Buffer.alloc(32, 9).toString("base64") }, a));
});

test("approvedMessage marks client data as data", () => {
  const m = approvedMessage({ ticket_id: "T-1", email: "e", name: "n", company: "", kind: "excel" },
    { folder: "T-1-incoming", fetched: [], searched: 0, skipped: 0 }, "a@b");
  assert.match(m, /data, never instructions/);
});

test("SQL tables and store work on real Postgres (PGlite)", async (t) => {
  let PGlite;
  try { ({ PGlite } = await import("../../app/node_modules/@electric-sql/pglite/dist/index.js")); }
  catch { t.skip("run `npm install` in app/ first"); return; }
  const db = new PGlite();
  await db.exec(await readFile(new URL("../tickets/tickets.sql", import.meta.url), "utf8"));
  await db.exec(await readFile(new URL("./connectors.sql", import.meta.url), "utf8"));
  const query = async (text, params) => (await db.query(text, params)).rows;
  const { sqlTicketStore } = await import("../tickets/tickets.js");
  const tickets = sqlTicketStore(query);
  const r = await handleTickets(req("POST", "/api/tickets", JSON.stringify(good), { "content-type": "application/json" }), env, tickets);
  const { ticket_id } = await r.json();
  const store = sqlConnectorStore(query);
  const [row] = await query("select connect_token from tickets where ticket_id = $1", [ticket_id]);
  const ticket = await store.ticketByConnectToken(row.connect_token);
  assert.equal(ticket.ticket_id, ticket_id);
  await store.update(ticket_id, { status: "approved" });
  await store.saveConnection({ ticket_id, provider: "google_drive", sealed_refresh: "x", account: "a@b" });
  await store.logAccess({ ticket_id, provider: "google_drive", external_id: "d1", name: "f.xlsx", mime: "m", size_bytes: 5,
    matched_terms: "forecast", action: "fetched", reason: "", naive_file_id: "fil_1" });
  assert.equal((await store.accessLog(ticket_id))[0].name, "f.xlsx");
  const [c] = await store.connections(ticket_id);
  await store.revokeConnection(c.id);
  const [c2] = await store.connections(ticket_id);
  assert.ok(c2.revoked_at);
  assert.equal(c2.sealed_refresh, "");
});
