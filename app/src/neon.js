// Neon over HTTP: works in a Worker and in Node, no connection pool to manage.
import { neon } from "@neondatabase/serverless";

export function neonQuery(databaseUrl) {
  const sql = neon(databaseUrl);
  return (text, params = []) => sql.query(text, params);
}
