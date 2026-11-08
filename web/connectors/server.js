// Local preview of tickets + connectors: node web/connectors/server.js  (then http://127.0.0.1:8791/tickets)
// DEMO mode (default here): pretend Google Drive, Microsoft 365, Dropbox and GitHub with sample files; nothing leaves your machine,
// no Naive calls. Submit a ticket, then open the connect link printed in this terminal.
import { createServer } from "node:http";
import { handleTickets, memoryTicketStore } from "../tickets/tickets.js";
import { handleConnectors, memoryConnectorStore } from "./connectors.js";

const port = Number(process.env.PORT || 8791);
const base = `http://127.0.0.1:${port}`;
const env = { CC_API_TOKEN: "dev", CONNECTOR_KEY: Buffer.alloc(32, 1).toString("base64"), PUBLIC_BASE_URL: base,
  GOOGLE_CLIENT_ID: "demo", GOOGLE_CLIENT_SECRET: "demo", MICROSOFT_CLIENT_ID: "demo", MICROSOFT_CLIENT_SECRET: "demo",
  DROPBOX_APP_KEY: "demo", DROPBOX_APP_SECRET: "demo", GITHUB_CLIENT_ID: "demo", GITHUB_CLIENT_SECRET: "demo" };
const tickets = memoryTicketStore();
const store = memoryConnectorStore(tickets);
const xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
// Pretend storage per provider. The last file in each list doesn't match and is never copied.
const SAMPLES = {
  google: ["Google Drive", "you@gmail.example", [["Q3 forecast model (backup).xlsx", xlsx, 48000], ["Board report Q3 2026.pdf", "application/pdf", 260000], ["Holiday photos.zip", "application/zip", 9e8]]],
  microsoft: ["Microsoft 365 / OneDrive", "you@company.example", [["Forecast model v12.xlsx", xlsx, 51000], ["ERP export 2025Q1-2026Q3.csv", "text/csv", 2100], ["Team lunch.jpg", "image/jpeg", 30000]]],
  dropbox: ["Dropbox", "you@dropbox.example", [["CFO email - model rules.eml", "message/rfc822", 4000], ["Old laptop backup.dmg", "application/x-apple-diskimage", 9e9]]],
  github: ["GitHub", "github:your-team", [["billing/src/invoicing.py", "text/x-python", 3000], ["billing/config/discounts.yml", "application/x-yaml", 400], ["billing/assets/logo.png", "image/png", 9000]]],
};
const relevant = (name) => /forecast|export|report|model|invoic|discount|cfo/i.test(name);
const providers = Object.fromEntries(Object.entries(SAMPLES).map(([slug, [label, account, files]]) => [slug, {
  name: { google: "google_drive", microsoft: "microsoft_365", dropbox: "dropbox", github: "github" }[slug], slug, label,
  authUrl: (state) => `${base}/connect/${slug}/callback?code=demo&state=${encodeURIComponent(state)}`,
  exchange: async () => ({ refresh: `demo-${slug}`, access: `demo-${slug}`, account }),
  search: async () => files.filter(([n]) => relevant(n)).map(([n, m, size], i) => ({ id: `${slug}-${i}`, name: n, mimeType: m, size: String(size) })),
  download: async (_a, f) => ({ bytes: new Uint8Array(Number(f.size)), name: f.name.replace(/\//g, "__"), contentType: f.mimeType }),
  revoke: async () => (slug === "microsoft" ? { manual: "https://myapps.microsoft.com" } : {}),
}]));
const deps = { store, providers, startSession: async (m) => { console.log("\n[would start Recovery Manager]\n" + m); return "ses_demo"; },
  files: { upload: async (f) => { console.log(`[would copy to Naive Files] ${f.folder}/${f.name}`); return "fil_demo"; } } };

createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks);
  const request = new Request(base + req.url, { method: req.method, headers: req.headers, body });
  let out = await handleConnectors(request, env, deps);
  if (!out) {
    out = await handleTickets(request, env, tickets);
    if (out && req.method === "POST" && req.url === "/api/tickets" && out.status === 201) {
      const t = (await tickets.list(null))[0];
      console.log(`ticket ${t.ticket_id}: connect link ${base}/connect/${t.connect_token}`);
    }
  }
  out = out || new Response("not found", { status: 404 });
  res.writeHead(out.status, Object.fromEntries(out.headers));
  res.end(Buffer.from(await out.arrayBuffer()));
}).listen(port, "127.0.0.1", () => console.log(`demo on ${base}/tickets (pretend Google Drive, Microsoft 365, Dropbox and GitHub)`));
