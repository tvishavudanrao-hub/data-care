import { test } from "node:test";
import assert from "node:assert/strict";
import { handleSite } from "../src/site/site.js";
import { BOARD_HTML } from "../src/board.js";

const get = (path, method = "GET") => handleSite(new Request("https://datacare.test" + path, { method }));

test("website pages", async () => {
  const home = get("/");
  assert.equal(home.status, 200);
  assert.match(home.headers.get("content-type"), /text\/html/);
  assert.match(await home.text(), /Data Care/);

  assert.equal(await get("/board").text(), BOARD_HTML);
  assert.equal(await get("/live/").text(), BOARD_HTML);

  for (const p of ["/case", "/case/C-0006", "/download"]) {
    const r = get(p);
    assert.equal(r.status, 200, p);
    assert.match(await r.text(), /Data Care/, p);
  }
  assert.match(get("/favicon.svg").headers.get("content-type"), /svg/);
});

test("collector download", async () => {
  const z = get("/download/datacare-collect.zip?case=C-0006");
  assert.equal(z.headers.get("content-type"), "application/zip");
  assert.match(z.headers.get("content-disposition"), /filename="datacare-collect-C-0006\.zip"/);
  const bytes = new Uint8Array(await z.arrayBuffer());
  assert.deepEqual([...bytes.slice(0, 4)], [0x50, 0x4b, 0x03, 0x04]);

  const odd = get("/download/datacare-collect.zip?case=../../etc");
  assert.match(odd.headers.get("content-disposition"), /filename="datacare-collect\.zip"/);
});

test("everything else falls through to the app", () => {
  for (const p of ["/tickets", "/connect", "/api/board", "/api/board/case/C-0006", "/api/health", "/case/a/b", "/nope"]) {
    assert.equal(get(p), null, p);
  }
  assert.equal(get("/", "POST"), null);
});
