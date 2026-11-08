// Create the connector tables on the Neon branch in NEON_DATABASE_URL (run: npm run connectors-table).
// Run `npm run tickets-table` first. Safe to re-run.
import { readFile } from "node:fs/promises";
import { neon } from "@neondatabase/serverless";
const url = process.env.NEON_DATABASE_URL;
if (!url) { console.error("NEON_DATABASE_URL is not set (put it in app/.env)"); process.exit(1); }
const sql = neon(url);
const text = await readFile(new URL("../src/connectors/connectors.sql", import.meta.url), "utf8");
const stmts = text.replace(/--.*$/gm, "").split(";").map((s) => s.trim()).filter(Boolean);
for (const s of stmts) await sql.query(s);
console.log("connector tables ready on", new URL(url).host);
