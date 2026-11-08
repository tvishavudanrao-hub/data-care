// Data Care app: records API for the agents plus the live board. Fetch-standard, so it runs as a
// Worker (worker.js) or under Node (server.js) with the same code.
import { TABLES, InputError } from "./db.js";
import { BOARD_HTML } from "./board.js";

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });

// Constant-time comparison so the token can't be guessed byte by byte.
function sameToken(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function dbErrorResponse(err) {
  // Postgres error codes: foreign key, check, not null, invalid text, numeric out of range.
  const code = err && err.code;
  if (code === "23503") return json(400, { error: "that case_id does not exist yet; open it with case-new first" });
  if (code === "23514") return json(400, { error: `a value is not allowed: ${err.constraint || err.message}` });
  if (code === "23502") return json(400, { error: `missing required field: ${err.column || err.message}` });
  if (code === "22P02" || code === "22003") return json(400, { error: `invalid value: ${err.message}` });
  return null;
}

export async function handle(request, env, db) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method;

  try {
    if (method === "GET" && path === "/") {
      return new Response(BOARD_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
    }
    if (method === "GET" && path === "/api/board") {
      return json(200, await db.board());
    }
    if (method === "GET" && path === "/api/health") {
      const token = request.headers.get("x-cc-token");
      return json(200, { ok: true, db: await db.health(), token_valid: sameToken(token, env.CC_API_TOKEN || "") && !!env.CC_API_TOKEN });
    }

    if (!path.startsWith("/api/")) return json(404, { error: "not found" });

    // Everything below needs the shared token.
    if (!env.CC_API_TOKEN) return json(503, { error: "CC_API_TOKEN is not configured on the app" });
    if (!sameToken(request.headers.get("x-cc-token"), env.CC_API_TOKEN)) {
      return json(401, { error: "missing or wrong x-cc-token" });
    }

    const parts = path.split("/").filter(Boolean); // ["api", table, id?]

    // Read one case back (stage, retry_count, cost): token-only because it shows the full client email.
    if (method === "GET" && parts.length === 3 && parts[1] === "cases") {
      const row = await db.getCase(decodeURIComponent(parts[2]));
      return row ? json(200, row) : json(404, { error: `case ${parts[2]} not found` });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { error: "body must be JSON" });
    }

    if (method === "POST" && parts.length === 2 && parts[1] in TABLES) {
      return json(201, await db.insert(parts[1], body));
    }
    if (method === "PATCH" && parts.length === 3 && parts[1] === "cases") {
      const row = await db.patchCase(decodeURIComponent(parts[2]), body);
      return row ? json(200, row) : json(404, { error: `case ${parts[2]} not found` });
    }
    return json(404, { error: `no route for ${method} ${path}` });
  } catch (err) {
    if (err instanceof InputError) return json(400, { error: err.message });
    const mapped = dbErrorResponse(err);
    if (mapped) return mapped;
    console.error(err);
    return json(500, { error: "server error" });
  }
}
