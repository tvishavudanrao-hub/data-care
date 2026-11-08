import { test } from "node:test";
import assert from "node:assert/strict";
import { handleSite } from "../src/site/site.js";
import { HOME_HTML } from "../src/site/home.js";

const get = (path) => handleSite(new Request("https://datacare.test" + path));

test("demo mode: /?demo keeps the home page and adds the walkthrough hook; plain / is untouched", async () => {
  assert.equal(await get("/").text(), HOME_HTML);
  const demo = await get("/?demo=1").text();
  assert.ok(demo.includes('id="dc-form"'), "the real form is still there");
  assert.ok(demo.includes("dc-demo-bar") && demo.includes("location.href = '/demo'"));
  assert.ok(demo.indexOf("dc-demo-bar") < demo.lastIndexOf("</body>"));
});

test("demo walkthrough page is self-contained: no API calls, no external scripts", async () => {
  const r = get("/demo");
  assert.equal(r.status, 200);
  const html = await r.text();
  assert.match(html, /Demo mode/);
  assert.doesNotMatch(html, /fetch\(|XMLHttpRequest|\/api\/|<script src=/);
  for (const step of ["Quote email", "What we read", "Agents at work", "Report"]) assert.ok(html.includes(step), step);
});
