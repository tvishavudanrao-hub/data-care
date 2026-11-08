// Records store on Postgres (Neon in production, PGlite in tests).
// `query(text, params)` must resolve to an array of row objects.

export const STAGES = ["intake", "forensics", "context", "reconstruction", "waiting_client",
  "validation", "approval", "delivered", "unresolved"];

// Per table: primary key (null for serial ids), columns agents may send, their SQL casts, required columns.
export const TABLES = {
  cases: {
    pk: "case_id",
    cols: { case_id: "", client_email: "", kind: "", stage: "", retry_count: "::int", quote_usd: "::numeric" },
    required: ["case_id", "client_email", "kind"],
  },
  fragments: {
    pk: "fragment_id",
    cols: { fragment_id: "", case_id: "", source_file: "", location: "", type: "", confidence: "::numeric",
      notes: "", created_by: "" },
    required: ["fragment_id", "case_id", "source_file", "type", "created_by"],
  },
  rules: {
    pk: "rule_id",
    cols: { rule_id: "", case_id: "", description: "", evidence: "::text[]", alternatives: "::jsonb", status: "" },
    required: ["rule_id", "case_id", "description", "evidence", "status"],
  },
  gaps: {
    pk: "gap_id",
    cols: { gap_id: "", case_id: "", what: "", why: "", where_to_look: "::text[]", status: "" },
    required: ["gap_id", "case_id", "what"],
  },
  verdicts: {
    pk: null,
    cols: { case_id: "", pass: "::boolean", results: "::jsonb", retry_count: "::int", outcome: "" },
    required: ["case_id", "pass", "results", "retry_count"],
  },
  report_items: {
    pk: null,
    cols: { case_id: "", item: "", label: "", cites: "::text[]" },
    required: ["case_id", "item", "label", "cites"],
  },
  events: {
    pk: null,
    cols: { case_id: "", agent: "", stage: "", message: "", cost_usd: "::numeric", human_stepped_in: "::boolean" },
    required: ["agent", "stage"],
  },
  checkups: {
    pk: null,
    cols: { case_id: "", team: "", repo_url: "", high: "::int", medium: "::int", low: "::int" },
    required: [],
  },
};

const CASE_PATCHABLE = { stage: "", retry_count: "::int", quote_usd: "::numeric" };
const NUMERIC_FIELDS = ["quote_usd", "confidence", "cost_usd", "cost", "total_cost"];

export class InputError extends Error {}

function encode(cast, value) {
  if (cast === "::jsonb") return JSON.stringify(value);
  if (cast === "::text[]") {
    if (!Array.isArray(value)) throw new InputError("expected a list of strings");
    return value.map(String);
  }
  return value;
}

function decode(row) {
  for (const f of NUMERIC_FIELDS) {
    if (row[f] !== null && row[f] !== undefined) row[f] = Number(row[f]);
  }
  return row;
}

export function makeDb(query) {
  async function insert(table, body) {
    const t = TABLES[table];
    if (!t) throw new InputError(`unknown table ${table}`);
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new InputError("body must be a JSON object");
    const unknown = Object.keys(body).filter((k) => !(k in t.cols));
    if (unknown.length) throw new InputError(`unknown field(s) for ${table}: ${unknown.join(", ")}`);
    const missing = t.required.filter((k) => body[k] === undefined || body[k] === null || body[k] === "");
    if (missing.length) throw new InputError(`missing field(s) for ${table}: ${missing.join(", ")}`);

    const cols = Object.keys(body).filter((k) => body[k] !== undefined && body[k] !== null);
    const params = [];
    const values = cols.map((c) => {
      try {
        params.push(encode(t.cols[c], body[c]));
      } catch (e) {
        throw new InputError(`${c}: ${e.message}`);
      }
      return `$${params.length}${t.cols[c]}`;
    });
    let sql = `insert into ${table} (${cols.join(", ")}) values (${values.join(", ")})`;
    if (t.pk) {
      // Agents retry: writing the same id twice updates the row instead of failing.
      const updates = cols.filter((c) => c !== t.pk).map((c) => `${c} = excluded.${c}`);
      if (table === "cases") updates.push("updated_at = now()");
      sql += updates.length
        ? ` on conflict (${t.pk}) do update set ${updates.join(", ")}`
        : ` on conflict (${t.pk}) do nothing`;
    }
    sql += " returning *";
    const rows = await query(sql, params);
    if (!rows.length && t.pk) {
      return decode((await query(`select * from ${table} where ${t.pk} = $1`, [body[t.pk]]))[0]);
    }
    return decode(rows[0]);
  }

  async function patchCase(caseId, body) {
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new InputError("body must be a JSON object");
    const unknown = Object.keys(body).filter((k) => !(k in CASE_PATCHABLE));
    if (unknown.length) throw new InputError(`only stage, retry_count and quote_usd can be patched (got ${unknown.join(", ")})`);
    const cols = Object.keys(body).filter((k) => body[k] !== undefined && body[k] !== null);
    if (!cols.length) throw new InputError("nothing to update");
    if (body.stage !== undefined && !STAGES.includes(body.stage)) {
      throw new InputError(`stage must be one of: ${STAGES.join(", ")}`);
    }
    const params = cols.map((c) => body[c]);
    const sets = cols.map((c, i) => `${c} = $${i + 1}${CASE_PATCHABLE[c]}`);
    params.push(caseId);
    const rows = await query(
      `update cases set ${sets.join(", ")}, updated_at = now() where case_id = $${params.length} returning *`,
      params,
    );
    return rows.length ? decode(rows[0]) : null;
  }

  async function board() {
    const [cases, humans, checkups, verdict, events, labels, total] = await Promise.all([
      query(`select c.case_id, c.client_email, c.kind, c.stage, c.retry_count, c.quote_usd, c.updated_at,
                    coalesce(sum(e.cost_usd), 0) as cost
               from cases c left join events e on e.case_id = c.case_id
              group by c.case_id order by c.created_at`),
      query(`select count(*)::int as n from events where human_stepped_in`),
      query(`select count(*)::int as n from checkups`),
      query(`select case_id, pass, outcome, retry_count, created_at from verdicts order by created_at desc, verdict_id desc limit 1`),
      query(`select case_id, agent, stage, message, cost_usd, human_stepped_in, created_at
               from events order by created_at desc, event_id desc limit 12`),
      query(`select label, count(*)::int as n from report_items group by label`),
      query(`select coalesce(sum(cost_usd), 0) as total_cost from events`),
    ]);
    return {
      cases: cases.map((r) => decode({ ...r, client_email: maskEmail(r.client_email) })),
      humans_stepped_in: humans[0].n,
      checkups_run: checkups[0].n,
      latest_verdict: verdict[0] || null,
      recent_events: events.map(decode),
      labels: Object.fromEntries(labels.map((r) => [r.label, r.n])),
      total_cost: Number(total[0].total_cost),
      stages: STAGES,
      generated_at: new Date().toISOString(),
    };
  }

  async function getCase(caseId) {
    const rows = await query(
      `select c.*, coalesce((select sum(cost_usd) from events e where e.case_id = c.case_id), 0) as cost
         from cases c where c.case_id = $1`,
      [caseId],
    );
    return rows.length ? decode(rows[0]) : null;
  }

  async function health() {
    await query("select 1 as ok");
    return true;
  }

  return { insert, patchCase, getCase, board, health };
}

// The board is shown on a projector: hide most of each client address.
export function maskEmail(email) {
  if (!email || !email.includes("@")) return email;
  const [user, domain] = email.split("@");
  return `${user.slice(0, 1)}***@${domain}`;
}
