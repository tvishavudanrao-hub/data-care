// Vercel entry (Naive fullstack apps build on Vercel): same Worker handler, secrets from process.env.
let loaded;
async function run(request) {
  try {
    loaded ||= (await import("../worker.js")).default;
  } catch (e) {
    return new Response(JSON.stringify({ error: "app failed to load", detail: String(e && e.message || e) }), {
      status: 500, headers: { "content-type": "application/json" },
    });
  }
  return loaded.fetch(request, process.env);
}
export const GET = run;
export const POST = run;
export const PATCH = run;
