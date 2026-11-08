// Worker entry: one database client per isolate, built from the app's NEON_DATABASE_URL secret.
import { handle } from "./src/handler.js";
import { makeDb } from "./src/db.js";
import { neonQuery } from "./src/neon.js";

let cached;

export default {
  async fetch(request, env) {
    if (!env.NEON_DATABASE_URL) {
      return new Response(JSON.stringify({ error: "NEON_DATABASE_URL is not configured on the app" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      });
    }
    if (!cached || cached.url !== env.NEON_DATABASE_URL) {
      cached = { url: env.NEON_DATABASE_URL, db: makeDb(neonQuery(env.NEON_DATABASE_URL)) };
    }
    return handle(request, env, cached.db);
  },
};
