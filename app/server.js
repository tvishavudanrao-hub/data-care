// Node entry for local runs and tests.
//   NEON_DATABASE_URL set -> talks to Neon.
//   not set               -> an in-memory Postgres (PGlite) loaded with db/schema.sql.
import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { handle } from "./src/handler.js";
import { makeDb } from "./src/db.js";

export async function memoryQuery() {
  const { PGlite } = await import("@electric-sql/pglite");
  const pg = new PGlite();
  const schema = await readFile(new URL("../db/schema.sql", import.meta.url), "utf8");
  await pg.exec(schema);
  return async (text, params = []) => (await pg.query(text, params)).rows;
}

export async function startServer({ port = 8787, env = process.env } = {}) {
  let query;
  if (env.NEON_DATABASE_URL) {
    const { neonQuery } = await import("./src/neon.js");
    query = neonQuery(env.NEON_DATABASE_URL);
  } else {
    query = await memoryQuery();
  }
  const db = makeDb(query);
  const server = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const body = chunks.length ? Buffer.concat(chunks) : undefined;
    const request = new Request(`http://${req.headers.host}${req.url}`, {
      method: req.method,
      headers: req.headers,
      body: ["GET", "HEAD"].includes(req.method) ? undefined : body,
    });
    const response = await handle(request, env, db);
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  });
  await new Promise((resolve) => server.listen(port, "127.0.0.1", resolve));
  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 8787);
  const server = await startServer({ port });
  const where = process.env.NEON_DATABASE_URL ? "Neon" : "an in-memory database";
  console.log(`Data Care app on http://127.0.0.1:${server.address().port} using ${where}`);
}
