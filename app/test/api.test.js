import { test, before } from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/handler.js";
import { makeDb, maskEmail } from "../src/db.js";
import { memoryQuery } from "../server.js";

const env = { CC_API_TOKEN: "test-token" };
let db;

before(async () => {
  db = makeDb(await memoryQuery());
});

function call(method, path, body, token = "test-token") {
  const headers = { "content-type": "application/json" };
  if (token) headers["x-cc-token"] = token;
  return handle(new Request("http://app" + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  }), env, db);
}

test("writes need the token", async () => {
  assert.equal((await call("POST", "/api/cases", { case_id: "C-0000" }, null)).status, 401);
  assert.equal((await call("POST", "/api/cases", { case_id: "C-0000" }, "wrong")).status, 401);
  const noToken = await handle(new Request("http://app/api/cases", { method: "POST", body: "{}" }), {}, db);
  assert.equal(noToken.status, 503);
});

test("full case lifecycle lands in every table", async () => {
  let r = await call("POST", "/api/cases", { case_id: "C-0001", client_email: "cfo@acme.com", kind: "excel", quote_usd: 250 });
  assert.equal(r.status, 201);
  const created = await r.json();
  assert.equal(created.stage, "intake");
  assert.equal(created.quote_usd, 250);

  r = await call("POST", "/api/fragments", { fragment_id: "F-0001-001", case_id: "C-0001", source_file: "model.xlsx",
    location: "Model!C12", type: "record", confidence: 0.9, created_by: "forensics" });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/rules", { rule_id: "R-0001-01", case_id: "C-0001", description: "Revenue = units x price",
    evidence: ["F-0001-001"], alternatives: [{ formula_pattern: "x" }], status: "reconstructed and tested" });
  assert.equal(r.status, 201);
  assert.deepEqual((await r.json()).evidence, ["F-0001-001"]);
  r = await call("POST", "/api/gaps", { gap_id: "G-0001-01", case_id: "C-0001", what: "Q2 discount", where_to_look: ["CFO email"] });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/verdicts", { case_id: "C-0001", pass: false, results: [{ example_id: "S1", expected: 1, actual: 2 }], retry_count: 1 });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/report_items", { case_id: "C-0001", item: "Model!E12", label: "recovered", cites: ["F-0001-001"] });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/events", { case_id: "C-0001", agent: "forensics", stage: "forensics", message: "scan done", cost_usd: 0.12 });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/events", { case_id: "C-0001", agent: "recovery-manager", stage: "approval", cost_usd: 0.03, human_stepped_in: true });
  assert.equal(r.status, 201);
  r = await call("POST", "/api/checkups", { team: "Team X", repo_url: "https://example.com/x", high: 1, low: 3 });
  assert.equal(r.status, 201);

  r = await call("PATCH", "/api/cases/C-0001", { stage: "validation", retry_count: 1 });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).stage, "validation");

  const board = await (await call("GET", "/api/board", undefined, null)).json();
  const c = board.cases.find((x) => x.case_id === "C-0001");
  assert.equal(c.stage, "validation");
  assert.equal(c.client_email, "c***@acme.com");
  assert.ok(Math.abs(c.cost - 0.15) < 1e-9);
  assert.equal(board.humans_stepped_in, 1);
  assert.equal(board.checkups_run, 1);
  assert.equal(board.latest_verdict.pass, false);
  assert.equal(board.labels.recovered, 1);
});

test("retrying the same id updates instead of failing", async () => {
  await call("POST", "/api/cases", { case_id: "C-0002", client_email: "a@b.com", kind: "code" });
  const r = await call("POST", "/api/cases", { case_id: "C-0002", client_email: "a@b.com", kind: "code", quote_usd: 90 });
  assert.equal(r.status, 201);
  assert.equal((await r.json()).quote_usd, 90);
});

test("bad input gets a clear 400", async () => {
  const cases = [
    ["POST", "/api/cases", { case_id: "C-0003", kind: "excel" }, /missing field/],
    ["POST", "/api/cases", { case_id: "C-0003", client_email: "a@b.com", kind: "pdf" }, /not allowed/],
    ["POST", "/api/report_items", { case_id: "C-0001", item: "x", label: "guessed", cites: ["a"] }, /not allowed/],
    ["POST", "/api/fragments", { fragment_id: "F-9", case_id: "C-9999", source_file: "x", type: "clue", created_by: "x" }, /does not exist/],
    ["POST", "/api/events", { agent: "x", stage: "y", surprise: 1 }, /unknown field/],
    ["PATCH", "/api/cases/C-0001", { stage: "lunch" }, /stage must be/],
    ["PATCH", "/api/cases/C-0001", { client_email: "x" }, /can be patched/],
  ];
  for (const [m, p, b, re] of cases) {
    const r = await call(m, p, b);
    assert.equal(r.status, 400, `${m} ${p} ${JSON.stringify(b)}`);
    assert.match((await r.json()).error, re);
  }
  assert.equal((await call("PATCH", "/api/cases/C-4040", { stage: "intake" })).status, 404);
});

test("board page and health", async () => {
  const page = await call("GET", "/", undefined, null);
  assert.match(await page.text(), /Code Care/);
  const h = await (await call("GET", "/api/health")).json();
  assert.deepEqual(h, { ok: true, db: true, token_valid: true });
  assert.equal(maskEmail("anna@x.io"), "a***@x.io");
});
