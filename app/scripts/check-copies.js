// The deploy uploads only app/, so app/src/tickets and app/src/connectors are copies of web/tickets and
// web/connectors. This fails if a copy has drifted from its source (run: npm run check-copies).
import { readFile } from "node:fs/promises";
const pairs = {
  tickets: ["tickets.js", "form.js", "naive.js", "tickets.sql"],
  connectors: ["connectors.js", "pages.js", "providers.js", "naive_files.js", "connectors.sql"],
};
let bad = 0;
for (const [dir, files] of Object.entries(pairs)) {
  for (const f of files) {
    const src = await readFile(new URL(`../../web/${dir}/${f}`, import.meta.url), "utf8");
    const copy = await readFile(new URL(`../src/${dir}/${f}`, import.meta.url), "utf8");
    if (src !== copy) { bad++; console.error(`out of sync: web/${dir}/${f} vs app/src/${dir}/${f}`); }
  }
}
if (bad) { console.error(`${bad} file(s) differ: copy web/ over app/src/ (cp web/<dir>/<file> app/src/<dir>/)`); process.exit(1); }
console.log("app/src/tickets and app/src/connectors match web/");
