// Local preview: node web/tickets/server.js, then open http://127.0.0.1:8790/tickets
// In-memory only (tickets vanish on restart). Token for the team routes: TICKETS_TOKEN or "dev".
import { createServer } from "node:http";
import { handleTickets, memoryTicketStore } from "./tickets.js";

const store = memoryTicketStore();
const env = { CC_API_TOKEN: process.env.TICKETS_TOKEN || "dev" };
const port = Number(process.env.PORT || 8790);

createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks);
  const request = new Request(`http://${req.headers.host}${req.url}`, { method: req.method, headers: req.headers, body });
  const out = (await handleTickets(request, env, store)) || new Response("not found", { status: 404 });
  res.writeHead(out.status, Object.fromEntries(out.headers));
  res.end(Buffer.from(await out.arrayBuffer()));
}).listen(port, "127.0.0.1", () => console.log(`ticket form on http://127.0.0.1:${port}/tickets`));
