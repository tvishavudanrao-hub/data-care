// Apply db/schema.sql to the Neon branch in NEON_DATABASE_URL (run: npm run schema).
// Safe to re-run: on a database that already has the tables it only adds columns added since.
import { readFile } from "node:fs/promises";
import { neon } from "@neondatabase/serverless";

const url = process.env.NEON_DATABASE_URL;
if (!url) {
  console.error("NEON_DATABASE_URL is not set (put it in app/.env)");
  process.exit(1);
}
const sql = neon(url);
const host = new URL(url).host;

// Columns added after the v2 schema, applied to databases created before them.
const ADDITIONS = [
  `alter table verdicts add column if not exists outcome text
     check (outcome in ('pass','fail','error','untested'))`,
];

const existing = await sql.query(
  "select table_name from information_schema.tables where table_schema = 'public' and table_name = 'cases'",
);
if (existing.length) {
  console.log(`tables already exist on ${host}; applying additions only`);
  for (const stmt of ADDITIONS) await sql.query(stmt);
} else {
  const schema = await readFile(new URL("../../db/schema.sql", import.meta.url), "utf8");
  const statements = schema
    .split("\n").filter((l) => !l.trim().startsWith("--")).join("\n")
    .split(";").map((s) => s.trim()).filter(Boolean);
  for (const stmt of statements) await sql.query(stmt);
  console.log(`created ${statements.length} tables on ${host}`);
}
const tables = await sql.query(
  "select table_name from information_schema.tables where table_schema = 'public' order by table_name",
);
console.log("tables:", tables.map((t) => t.table_name).join(", "));
