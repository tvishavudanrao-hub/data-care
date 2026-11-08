// Local preview of tickets + connectors: node web/connectors/server.js  (then http://127.0.0.1:8791/tickets)
// DEMO mode (default here): a pretend Google Drive with a few sample files, nothing leaves your machine,
// no Naive calls. Submit a ticket, then open the connect link printed in this terminal.
import { createServer } from "node:http";
import { handleTickets, memoryTicketStore } from "../tickets/tickets.js";
import { handleConnectors, memoryConnectorStore } from "./connectors.js";

const port = Number(process.env.PORT || 8791);
const base = `http://127.0.0.1:${port}`;
const env = { CC_API_TOKEN: "dev", CONNECTOR_KEY: Buffer.alloc(32, 1).toString("base64"), GOOGLE_CLIENT_ID: "demo",
  GOOGLE_CLIENT_SECRET: "demo", PUBLIC_BASE_URL: base };
const tickets = memoryTicketStore();
const store = memoryConnectorStore(tickets);
const sample = [
  { id: "s1", name: "Q3 forecast model (backup).xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size: "48000" },
  { id: "s2", name: "ERP export 2025Q1-2026Q3.csv", mimeType: "text/csv", size: "2100" },
  { id: "s3", name: "Board report Q3 2026.pdf", mimeType: "application/pdf", size: "260000" },
  { id: "s4", name: "Holiday photos.zip", mimeType: "application/zip", size: "900000000" },
];
const demoProvider = {
  name: "google_drive",
  authUrl: (state) => `${base}/connect/google/callback?code=demo&state=${encodeURIComponent(state)}`,
  exchange: async () => ({ refresh: "demo-refresh", access: "demo-access", account: "you@example.com" }),
  search: async () => sample.filter((f) => f.mimeType !== "application/zip"),
  download: async (_a, f) => ({ bytes: new Uint8Array(Number(f.size)), name: f.name, contentType: f.mimeType }),
  revoke: async () => {},
};
const deps = { store, provider: demoProvider, startSession: async (m) => { console.log("\n[would start Recovery Manager]\n" + m); return "ses_demo"; },
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
}).listen(port, "127.0.0.1", () => console.log(`demo on ${base}/tickets (pretend Google Drive)`));
