// HTML for the connect and status pages, in the Data Care brand. No external resources. Everything the
// client typed is escaped before it is shown.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Brand (docs/brand): shared with the ticket form. In app/ the same relative path holds the copy.
import { page, labelChip } from "../tickets/brand.js";

const shell = (title, body) => page(esc(title), body);

const PROVIDERS = [["google", "Google Drive"], ["microsoft", "Microsoft 365 / OneDrive"], ["dropbox", "Dropbox"], ["github", "GitHub"]];

export function CONNECT_PAGE(ticket, token, cancelled, enabled = ["google"]) {
  const buttons = PROVIDERS.map(([slug, label]) => enabled.includes(slug)
    ? `<a class="btn" href="/connect/${esc(token)}/${slug}">Connect ${label} (read-only)</a>`
    : `<a class="btn secondary soon" aria-disabled="true">${label}: coming soon</a>`).join("\n  ");
  return shell("Data Care: connect your files", `
  <p class="kicker">Request ${esc(ticket.ticket_id)} · ${esc(ticket.name)}</p>
  <h1>Approve, and let us <em>find</em> your files</h1>
  ${cancelled ? `<p><strong>No access was given.</strong> You can try again below or simply reply to our email.</p>` : ""}
  <p>Instead of sending us files, connect your storage. Our agents search it for the evidence your
  ${ticket.kind === "code" ? "code" : "spreadsheet"} was built from (older copies, exports, reports, related files${ticket.kind === "code" ? ", repositories" : ""}),
  so you don't have to guess what we need.</p>
  <ul class="promises">
    <li><strong>Read-only.</strong> We can't change or delete anything.</li>
    <li><strong>Only what matches your case</strong> is copied. You'll see every file we looked at.</li>
    <li><strong>Nothing is ever run.</strong> Every file is scanned before anyone opens it.</li>
    <li><strong>Access ends automatically</strong> when your case is delivered, or the moment you press Disconnect.</li>
    <li><strong>We never guess.</strong> Every item in your report gets exactly one label:<br>
      ${["recovered", "reconstructed and tested", "reconstructed but untested", "unresolved"].map(labelChip).join(" ")}</li>
  </ul>
  <p>By connecting, you approve the quote we emailed you.</p>
  ${buttons}
  <p class="muted" style="margin-top:12px">You can connect more than one. Each is searched separately and listed on your status page.</p>
  <p class="muted" style="margin-top:20px">Prefer not to connect? Reply to our email with APPROVE and attach your files instead.</p>`);
}

export function STATUS_PAGE(ticket, token, connections, log) {
  const active = connections.filter((c) => !c.revoked_at);
  const rows = log.filter((e) => e.provider !== "naive").map((e) => `<tr><td style="color:var(--ink);font-weight:500">${esc(e.name)}</td>
    <td>${e.action === "fetched" ? '<span class="chip recovered">copied for your case</span>' : '<span class="muted">not copied' + (e.reason ? ": " + esc(e.reason) : "") + "</span>"}</td>
    <td data-k="Matched on">${esc(e.matched_terms || "content match")}</td></tr>`).join("");
  return shell("Data Care: what we read", `
  <p class="kicker">Request ${esc(ticket.ticket_id)}</p>
  <h1>What we <em>read</em></h1>
  ${active.length ? `<p>Connected: ${active.map((c) => esc(c.account || c.provider)).join(", ")} (read-only).</p>
    <form method="post" action="/connect/${esc(token)}/disconnect"><button class="btn secondary" type="submit">Disconnect now</button></form>`
    : `<p class="ok">No accounts are connected. Our access has ended.</p>`}
  ${connections.some((c) => c.provider === "microsoft_365") ? `<p class="muted">Microsoft doesn't let apps cancel their own access,
    so on Disconnect we delete our copy of it. To remove Data Care from your Microsoft account as well, go to
    <a href="https://myapps.microsoft.com" rel="noopener">myapps.microsoft.com</a>.</p>` : ""}
  <p class="muted">Every file our search looked at is listed here. Copied files are scanned before anyone opens them.</p>
  <div class="wrap card" style="padding:8px 12px"><table class="stack"><thead><tr><th>File</th><th>What we did</th><th>Matched on</th></tr></thead>
  <tbody>${rows || '<tr><td colspan="3" class="muted">Nothing yet.</td></tr>'}</tbody></table></div>`);
}
