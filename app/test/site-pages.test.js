import { test } from "node:test";
import assert from "node:assert/strict";
import zlib from "node:zlib";
import { existsSync, readFileSync } from "node:fs";
import { CASE_HTML, DOWNLOAD_HTML, FAVICON_SVG, collectorZip } from "../src/site/pages.js";
import { COLLECTOR_COMMAND } from "../src/site/collector.js";

const PAGES = { case: CASE_HTML, download: DOWNLOAD_HTML };
const scriptOf = (html) => html.slice(html.lastIndexOf("<script>") + 8, html.lastIndexOf("</script>"));

// Reads a zip back from its central directory, checking each local header against it.
function readZip(u8) {
  const b = Buffer.from(u8.buffer, u8.byteOffset, u8.byteLength);
  const eocd = b.length - 22;
  assert.equal(b.readUInt32LE(eocd), 0x06054b50, "end of central directory at the end (no comment)");
  const count = b.readUInt16LE(eocd + 10), cdSize = b.readUInt32LE(eocd + 12), cdOff = b.readUInt32LE(eocd + 16);
  assert.equal(b.readUInt16LE(eocd + 8), count);
  assert.equal(cdOff + cdSize, eocd, "central directory ends where the end record starts");
  const entries = [];
  let p = cdOff;
  for (let i = 0; i < count; i++) {
    assert.equal(b.readUInt32LE(p), 0x02014b50, "central directory header");
    const e = {
      madeBy: b.readUInt16LE(p + 4), needed: b.readUInt16LE(p + 6), flags: b.readUInt16LE(p + 8), method: b.readUInt16LE(p + 10),
      crc: b.readUInt32LE(p + 16), csize: b.readUInt32LE(p + 20), usize: b.readUInt32LE(p + 24), external: b.readUInt32LE(p + 38),
    };
    const nlen = b.readUInt16LE(p + 28), xlen = b.readUInt16LE(p + 30), clen = b.readUInt16LE(p + 32), off = b.readUInt32LE(p + 42);
    e.name = b.toString("utf8", p + 46, p + 46 + nlen);
    assert.equal(b.readUInt32LE(off), 0x04034b50, "local file header");
    assert.equal(b.readUInt16LE(off + 8), e.method);
    assert.equal(b.readUInt32LE(off + 14), e.crc, "local and central CRC agree");
    assert.equal(b.readUInt32LE(off + 18), e.csize);
    assert.equal(b.readUInt32LE(off + 22), e.usize);
    const lnlen = b.readUInt16LE(off + 26), lxlen = b.readUInt16LE(off + 28);
    assert.equal(b.toString("utf8", off + 30, off + 30 + lnlen), e.name, "local and central names agree");
    const start = off + 30 + lnlen + lxlen;
    e.data = b.subarray(start, start + e.csize);
    assert.ok(start + e.csize <= cdOff, "file data ends before the central directory");
    entries.push(e);
    p += 46 + nlen + xlen + clen;
  }
  return entries;
}

test("both pages have the shared head, header and footer", () => {
  for (const [name, html] of Object.entries(PAGES)) {
    assert.match(html, /^<!DOCTYPE html>\n<html lang="en">/, name);
    assert.match(html, /<meta name="viewport" content="width=device-width, initial-scale=1">/, name);
    assert.match(html, /<title>[^<]+ · Data Care<\/title>/, name);
    assert.match(html, /<meta name="description" content="[^"]{40,}">/, name);
    assert.match(html, /<link rel="icon" href="\/favicon.svg"/, name);
    assert.match(html, /<a class="brand" href="\/">[\s\S]*?Data Care<\/a>/, name);
    for (const href of ["/#how", "/board", "/case", "/tickets", "/download"]) assert.ok(html.includes(`href="${href}"`), `${name} links ${href}`);
    assert.match(html, /<header class="site-head">/, name);
    assert.match(html, /<footer class="site-foot">/, name);
    assert.equal((html.match(/<main\b/g) || []).length, 1, name);
  }
});

test("pages load nothing but Google Fonts and stay in house style", () => {
  for (const [name, html] of Object.entries(PAGES)) {
    const urls = html.match(/\b(?:src|href)="(?:https?:)?\/\/[^"]+"/g) || [];
    for (const u of urls) assert.match(u, /"https:\/\/fonts\.(googleapis|gstatic)\.com[/"]/, `${name}: ${u}`);
    assert.ok(html.includes("family=Inter:wght@400;500;600&amp;family=Instrument+Serif:ital@0;1"), name);
    assert.ok(!/[—–]/.test(html), `${name} has no em or en dash`);
    assert.doesNotMatch(html, /\brebuil|\bguess/i, name);
    assert.doesNotMatch(html, /support\.js|<x-dc|DCLogic|sc-for|\{\{/, `${name} carries none of the design runtime`);
    assert.equal((html.match(/<\/script/gi) || []).length, 1, `${name}: one script, closed once`);
    assert.doesNotThrow(() => new Function(scriptOf(html)), `${name} script compiles`);
    // Motion only for people who have not asked to reduce it.
    const css = html.slice(html.indexOf("<style>"), html.indexOf("</style>"));
    const outside = css.replace(/@media \(prefers-reduced-motion:no-preference\)\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, "");
    assert.doesNotMatch(outside, /(?:^|[;{])\s*(?:animation|transition)\s*:/, `${name}: animation outside the motion query`);
  }
});

test("case page: tracking form, stepper, labels, steps, quote, humans, polling", () => {
  const h = CASE_HTML;
  assert.match(h, /Track your <em>case\.<\/em>/);
  assert.match(h, /<form id="find-form"[^>]*action="\/case"/);
  assert.match(h, /<label for="case-input">Case number<\/label>/);
  assert.ok(h.includes('"/api/board/case/" + encodeURIComponent(id)'));
  assert.ok(h.includes('location.assign("/case/" + encodeURIComponent(v))'));
  for (const step of ["Request", "Investigate", "Recover", "Reconstruct", "Validate", "Delivered"]) assert.ok(h.includes(`"${step}"`), step);
  for (const stage of ["intake", "forensics", "context", "reconstruction", "waiting_client", "validation", "approval", "delivered", "unresolved"]) {
    assert.ok(h.includes(stage), stage);
  }
  assert.ok(h.includes("We asked for a missing piece"));
  for (const label of ["recovered", "reconstructed and tested", "reconstructed but untested", "unresolved"]) assert.ok(h.includes(`"${label}"`), label);
  for (const color of ["#0F5F47", "#E6F4EE", "#8A3409", "#FFF1E4", "#5B2BB0", "#F4EEFF"]) assert.ok(h.includes(color), color);
  for (const text of ["Latest steps", "Quote", "Humans stepped in", "Report summary", "We couldn't find case", "We can't load this case right now", "Loading case"]) {
    assert.ok(h.includes(text), text);
  }
  assert.match(h, /const POLL_MS = 20000;/);
  assert.match(h, /document\.visibilityState === "visible"/);
  assert.match(h, /aria-current="step"/);
});

test("download page: what it does, what it never touches, how to open it, the download link", () => {
  const h = DOWNLOAD_HTML;
  assert.match(h, /id="dl" href="\/download\/datacare-collect\.zip"/);
  assert.ok(h.includes('"/download/datacare-collect.zip?case=" + encodeURIComponent(id)'));
  assert.ok(h.includes("/^C-\\d{4}$/.test(id)"), "only a real case number is passed through");
  assert.match(h, />Download for Mac</);
  for (const text of ["What it does", "What it never touches", "Nothing is uploaded", "never goes online", "Nothing outside them is read",
    "right-click the file and choose <b>Open</b>", "macOS 15 or later", "Privacy &amp; Security", "Open Anyway", "Files over 50 MB",
    "Keys and passwords", "Reply to our email and attach it", "datacare-recover@agentmail.to", "DataCare-&lt;case&gt;.zip"]) {
    assert.ok(h.includes(text), text);
  }
});

test("collector zip: one stored, executable file, readable back byte for byte", () => {
  const original = Buffer.from(COLLECTOR_COMMAND, "utf8");
  const cases = [
    [undefined, "datacare-collect.command"],
    ["", "datacare-collect.command"],
    ["C-0006", "datacare-collect-C-0006.command"],
    ["C-1234", "datacare-collect-C-1234.command"],
    ["c-0006", "datacare-collect.command"],
    ["C-006", "datacare-collect.command"],
    ["C-0006/../x", "datacare-collect.command"],
    [null, "datacare-collect.command"],
  ];
  for (const [caseId, name] of cases) {
    const zip = collectorZip(caseId);
    assert.ok(zip instanceof Uint8Array);
    const entries = readZip(zip);
    assert.equal(entries.length, 1);
    const [e] = entries;
    assert.equal(e.name, name, String(caseId));
    assert.equal(e.method, 0, "stored");
    assert.equal(e.flags, 0);
    assert.equal(e.madeBy >> 8, 3, "made by Unix");
    assert.equal(e.external >>> 16, 0o100755, "regular file, mode 0755");
    assert.equal(e.csize, original.length);
    assert.equal(e.usize, original.length);
    assert.equal(e.crc, zlib.crc32(e.data), "CRC matches the data");
    assert.equal(e.crc, zlib.crc32(original));
    assert.ok(e.data.equals(original), "content is byte-identical");
  }
  assert.deepEqual(collectorZip("C-0006"), collectorZip("C-0006"), "same input, same bytes");
});

test("collector.js is the collector script", (t) => {
  assert.ok(COLLECTOR_COMMAND.startsWith("#!/bin/zsh"));
  assert.ok(!COLLECTOR_COMMAND.includes("\r"));
  assert.match(COLLECTOR_COMMAND, /datacare-collect-C-0101\.command/, "reads its case from its file name");
  const repoCopy = new URL("../../collector/datacare-collect.command", import.meta.url);
  if (!existsSync(repoCopy)) return t.skip("collector/ is not next to app/ in this checkout");
  assert.equal(COLLECTOR_COMMAND, readFileSync(repoCopy, "utf8"), "collector.js is out of date: regenerate it");
});

test("favicon is the app icon, small and well formed", () => {
  const svg = FAVICON_SVG;
  assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="[^"]+">/);
  assert.match(svg, /<\/svg>$/);
  assert.ok(svg.length < 2048, `${svg.length} bytes`);
  for (const stop of ["#FF8A1F", "#F2557A", "#7B3FE4"]) assert.ok(svg.includes(stop), stop);
  assert.match(svg, /<rect [^>]*rx="\d+"[^>]*fill="url\(#g\)"\/>/);
  assert.match(svg, /<path fill="#fff"[^>]* d="M[-\d. LZ]+"\/>/);
  // Tags balance: every open tag closes, in order.
  const stack = [];
  for (const [, close, tag, selfClose] of svg.matchAll(/<(\/?)([a-zA-Z]+)[^>]*?(\/?)>/g)) {
    if (close) assert.equal(stack.pop(), tag);
    else if (!selfClose) stack.push(tag);
  }
  assert.deepEqual(stack, []);
});
