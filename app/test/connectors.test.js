// The connector pages wired into the app (src/connectors, copied from web/connectors).
import { test, before } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { handle } from "../src/handler.js";
import { makeDb } from "../src/db.js";

let db;
before(async () => {
  const { PGlite } = await import("@electric-sql/pglite");
  const pg = new PGlite();
  for (const f of ["../../db/schema.sql", "../src/tickets/tickets.sql", "../src/connectors/connectors.sql"]) {
    await pg.exec(await readFile(new URL(f, import.meta.url), "utf8"));
  }
  db = makeDb(async (text, params = []) => (await pg.query(text, params)).rows);
});

const off = { CC_API_TOKEN: "t" };
const on = { CC_API_TOKEN: "t", CONNECTOR_KEY: Buffer.alloc(32, 3).toString("base64"), PUBLIC_BASE_URL: "https://app.example",
  GOOGLE_CLIENT_ID: "gid", GOOGLE_CLIENT_SECRET: "gsec" };
const get = (path, env) => handle(new Request("https://app.example" + path), env, db);
const ticket = { name: "Dana", email: "dana@example.com", kind: "excel", environment: "",
  description: "Our forecast model lost its formulas after a paste.", consent: true };

test("connect pages are off until configured; the board still works", async () => {
  assert.equal((await get("/connect/" + "a".repeat(48), off)).status, 503);
  assert.equal((await get("/", off)).status, 200);
});

test("with settings: a new ticket's connect link shows the page and starts Google's read-only consent", async () => {
  const r = await handle(new Request("https://app.example/api/tickets", { method: "POST",
    headers: { "content-type": "application/json" }, body: JSON.stringify(ticket) }), on, db);
  assert.equal(r.status, 201);
  const { ticket_id } = await r.json();
  const [{ connect_token }] = await db.query("select connect_token from tickets where ticket_id = $1", [ticket_id]);
  assert.match(connect_token, /^[0-9a-f]{48}$/);
  const page = await get(`/connect/${connect_token}`, on);
  assert.equal(page.status, 200);
  const html = await page.text();
  assert.match(html, /Connect Google Drive \(read-only\)/);
  assert.match(html, /Dropbox: coming soon/);
  const go = await get(`/connect/${connect_token}/google`, on);
  assert.equal(go.status, 302);
  const u = new URL(go.headers.get("location"));
  assert.equal(u.host, "accounts.google.com");
  assert.equal(u.searchParams.get("redirect_uri"), "https://app.example/connect/google/callback");
  const status = await get(`/connect/${connect_token}/status`, on);
  assert.match(await status.text(), /No accounts are connected/);
});

test("revoke-expired cron route needs the app token", async () => {
  const r = await handle(new Request("https://app.example/api/connectors/revoke-expired", { method: "POST" }), on, db);
  assert.equal(r.status, 401);
  const ok = await handle(new Request("https://app.example/api/connectors/revoke-expired", { method: "POST",
    headers: { "x-cc-token": "t" } }), on, db);
  assert.deepEqual(await ok.json(), { revoked: 0 });
});

test("app copies match web/ (npm run check-copies)", async () => {
  const { stdout } = await promisify(execFile)(process.execPath, [new URL("../scripts/check-copies.js", import.meta.url).pathname]);
  assert.match(stdout, /match web/);
});
