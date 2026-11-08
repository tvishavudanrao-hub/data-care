import { test } from "node:test";
import assert from "node:assert/strict";
import { HOME_HTML } from "../src/site/home.js";
import { KINDS, ENVIRONMENTS, validateTicket } from "../src/tickets/tickets.js";

test("home page is one complete HTML document", () => {
  assert.match(HOME_HTML, /^<!doctype html>/i);
  assert.match(HOME_HTML, /<\/html>\s*$/);
  assert.match(HOME_HTML, /Data Care/);
  assert.match(HOME_HTML, /<title>Data Care: lost data isn't gone, it's in pieces<\/title>/);
  assert.match(HOME_HTML, /<link rel="icon" href="\/favicon.svg"/);
  assert.ok(Buffer.byteLength(HOME_HTML) < 200 * 1024, "stays under 200 KB");
});

test("request form posts to /api/tickets", () => {
  const form = HOME_HTML.match(/<form\b[^>]*>/i);
  assert.ok(form, "has a form");
  assert.match(form[0], /action="\/api\/tickets"/);
  assert.match(form[0], /method="post"/i);
  assert.match(HOME_HTML, /method: 'POST', headers: \{ 'content-type': 'application\/json' \}/);
  for (const name of ["name", "email", "company", "kind", "environment", "description", "consent"]) {
    assert.match(HOME_HTML, new RegExp(`name="${name}"`), `field ${name}`);
  }
});

test("form has the hidden honeypot field website", () => {
  assert.match(HOME_HTML, /<div class="dc-hp" aria-hidden="true">[^]*?<input[^>]*name="website"[^>]*tabindex="-1"/);
});

test("form only offers values the ticket API accepts", () => {
  const kinds = [...HOME_HTML.matchAll(/name="kind" value="([^"]*)"/g)].map((m) => m[1]);
  assert.ok(kinds.length === 4 && kinds.every((k) => KINDS.includes(k)), `kinds ${kinds}`);
  const envs = [...HOME_HTML.matchAll(/<option value="([^"]*)"/g)].map((m) => m[1]);
  assert.deepEqual([...envs].sort(), [...ENVIRONMENTS].sort());
  const sample = { name: "Dana", email: "dana@example.com", company: "", kind: "other", environment: "",
    description: "Food trace-back: a recall on lot 4471, trace the lettuce to the farm.", website: "", consent: true };
  assert.ok(validateTicket(sample).ticket, "the page's payload shape validates");
});

test("no external scripts, only Google Fonts", () => {
  assert.doesNotMatch(HOME_HTML, /<script src=/i);
  assert.doesNotMatch(HOME_HTML, /<script[^>]*\ssrc=/i);
  const external = [...HOME_HTML.matchAll(/(?:href|src)="(https?:[^"]*)"/g)].map((m) => new URL(m[1]).host);
  assert.ok(external.every((h) => h === "fonts.googleapis.com" || h === "fonts.gstatic.com"), external.join(","));
});

test("links go to the app's pages and motion is opt-in", () => {
  for (const href of ["#start", "/board", "/case", "/download"]) assert.ok(HOME_HTML.includes(`href="${href}"`), href);
  assert.match(HOME_HTML, /@media \(prefers-reduced-motion:no-preference\)\{/);
  assert.ok(!HOME_HTML.includes("—"), "no em dashes");
});
