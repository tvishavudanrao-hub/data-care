// HTML for the connect and status pages. Plain HTML, no external resources. Everything the client
// typed is escaped before it is shown.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const STYLE = `
  :root { --bg:#fff; --fg:#1a1a1a; --muted:#5c5c5c; --line:#d9d9d9; --accent:#c2185b; --ok:#1b7f3b; }
  @media (prefers-color-scheme: dark) { :root { --bg:#121212; --fg:#f2f2f2; --muted:#a8a8a8; --line:#3a3a3a; --accent:#f06292; --ok:#6fd08c; } }
  * { box-sizing: border-box; } body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }
  main { max-width:640px; margin:0 auto; padding:32px 16px 48px; } h1 { font-size:1.5rem; margin:0 0 8px; }
  .muted { color:var(--muted); } ul.promises { padding-left:20px; } ul.promises li { margin:6px 0; }
  .btn { display:block; width:100%; text-align:center; padding:12px; margin-top:12px; border-radius:8px; font-weight:600;
    text-decoration:none; color:#fff; background:var(--accent); border:0; font-size:1rem; cursor:pointer; }
  .btn.secondary { background:transparent; color:var(--fg); border:1px solid var(--line); }
  .soon { opacity:.55; pointer-events:none; }
  table { width:100%; border-collapse:collapse; font-size:.92rem; margin-top:12px; }
  th, td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top; overflow-wrap:anywhere; }
  .wrap { overflow-x:auto; } .ok { color:var(--ok); }`;

const shell = (title, body) => `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title><style>${STYLE}</style></head>
<body><main>${body}</main></body></html>`;

const PROVIDERS = [["google", "Google Drive"], ["microsoft", "Microsoft 365 / OneDrive"], ["dropbox", "Dropbox"], ["github", "GitHub"]];

export function CONNECT_PAGE(ticket, token, cancelled, enabled = ["google"]) {
  const buttons = PROVIDERS.map(([slug, label]) => enabled.includes(slug)
    ? `<a class="btn" href="/connect/${esc(token)}/${slug}">Connect ${label} (read-only)</a>`
    : `<a class="btn secondary soon" aria-disabled="true">${label}: coming soon</a>`).join("\n  ");
  return shell("Data Care: connect your files", `
  <h1>Approve and let us find your files</h1>
  <p class="muted">Request ${esc(ticket.ticket_id)} for ${esc(ticket.name)}</p>
  ${cancelled ? `<p><strong>No access was given.</strong> You can try again below or simply reply to our email.</p>` : ""}
  <p>Instead of sending us files, connect your storage. Our agents search it for the evidence your
  ${ticket.kind === "code" ? "code" : "spreadsheet"} was built from (older copies, exports, reports, related files${ticket.kind === "code" ? ", repositories" : ""}),
  so you don't have to guess what we need.</p>
  <ul class="promises">
    <li><strong>Read-only.</strong> We can't change or delete anything.</li>
    <li><strong>Only what matches your case</strong> is copied. You'll see every file we looked at.</li>
    <li><strong>Nothing is ever run.</strong> Every file is scanned before anyone opens it.</li>
    <li><strong>Access ends automatically</strong> when your case is delivered, or the moment you press Disconnect.</li>
    <li><strong>We never guess.</strong> Every item in your report is labelled recovered, reconstructed and tested,
      reconstructed but untested, or unresolved.</li>
  </ul>
  <p>By connecting, you approve the quote we emailed you.</p>
  ${buttons}
  <p class="muted" style="margin-top:12px">You can connect more than one. Each is searched separately and listed on your status page.</p>
  <p class="muted" style="margin-top:20px">Prefer not to connect? Reply to our email with APPROVE and attach your files instead.</p>`);
}

export function STATUS_PAGE(ticket, token, connections, log) {
  const active = connections.filter((c) => !c.revoked_at);
  const rows = log.filter((e) => e.provider !== "naive").map((e) => `<tr><td>${esc(e.name)}</td>
    <td>${e.action === "fetched" ? '<span class="ok">copied for your case</span>' : "not copied" + (e.reason ? ": " + esc(e.reason) : "")}</td>
    <td>${esc(e.matched_terms || "content match")}</td></tr>`).join("");
  return shell("Data Care: what we read", `
  <h1>What we read for request ${esc(ticket.ticket_id)}</h1>
  ${active.length ? `<p>Connected: ${active.map((c) => esc(c.account || c.provider)).join(", ")} (read-only).</p>
    <form method="post" action="/connect/${esc(token)}/disconnect"><button class="btn secondary" type="submit">Disconnect now</button></form>`
    : `<p class="ok">No accounts are connected. Our access has ended.</p>`}
  ${connections.some((c) => c.provider === "microsoft_365") ? `<p class="muted">Microsoft doesn't let apps cancel their own access,
    so on Disconnect we delete our copy of it. To remove Data Care from your Microsoft account as well, go to
    <a href="https://myapps.microsoft.com" rel="noopener">myapps.microsoft.com</a>.</p>` : ""}
  <p class="muted">Every file our search looked at is listed here. Copied files are scanned before anyone opens them.</p>
  <div class="wrap"><table><thead><tr><th>File</th><th>What we did</th><th>Why it matched</th></tr></thead>
  <tbody>${rows || '<tr><td colspan="3" class="muted">Nothing yet.</td></tr>'}</tbody></table></div>`);
}
