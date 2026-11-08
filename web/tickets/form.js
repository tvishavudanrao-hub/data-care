// The public ticket form. Plain HTML, no external scripts, fonts or trackers, so it works
// anywhere the app runs (Worker, Vercel, Node). Posts JSON to /api/tickets on the same site.

export const FORM_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Care: request a recovery</title>
<style>
  :root { --bg: #ffffff; --fg: #1a1a1a; --muted: #5c5c5c; --line: #d9d9d9; --accent: #c2185b; --ok: #1b7f3b; --err: #b3261e; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #121212; --fg: #f2f2f2; --muted: #a8a8a8; --line: #3a3a3a; --accent: #f06292; --ok: #6fd08c; --err: #ff8a80; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
  main { max-width: 560px; margin: 0 auto; padding: 32px 16px 48px; }
  h1 { font-size: 1.6rem; margin: 0 0 4px; }
  p.lead { color: var(--muted); margin: 0 0 24px; }
  label { display: block; font-weight: 600; margin: 16px 0 6px; }
  .hint { font-weight: 400; color: var(--muted); font-size: .9rem; }
  input, select, textarea { width: 100%; padding: 10px 12px; font: inherit; color: inherit; background: transparent;
    border: 1px solid var(--line); border-radius: 8px; }
  textarea { min-height: 140px; resize: vertical; }
  .check { display: flex; gap: 10px; align-items: flex-start; margin-top: 20px; font-weight: 400; }
  .check input { width: auto; margin-top: 4px; }
  .hp { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
  button { margin-top: 24px; width: 100%; padding: 12px; font: inherit; font-weight: 600; color: #fff;
    background: var(--accent); border: 0; border-radius: 8px; cursor: pointer; }
  button[disabled] { opacity: .6; cursor: wait; }
  #status { margin-top: 16px; min-height: 1.5em; }
  #status.ok { color: var(--ok); } #status.err { color: var(--err); }
  .note { margin-top: 24px; font-size: .9rem; color: var(--muted); }
</style>
</head>
<body>
<main>
  <h1>Request a recovery</h1>
  <p class="lead">Tell us what you lost. We'll reply by email with a quote and the steps to install our tool.
  We rebuild only from data that still survives. Anything we can't support with evidence, we say so.</p>

  <form id="ticket" novalidate>
    <label for="name">Your name</label>
    <input id="name" name="name" autocomplete="name" maxlength="120" required>

    <label for="email">Email <span class="hint">(we reply here)</span></label>
    <input id="email" name="email" type="email" autocomplete="email" maxlength="254" required>

    <label for="company">Company <span class="hint">(optional)</span></label>
    <input id="company" name="company" autocomplete="organization" maxlength="160">

    <label for="kind">What was lost or damaged?</label>
    <select id="kind" name="kind" required>
      <option value="">Choose one</option>
      <option value="excel">A spreadsheet or financial model</option>
      <option value="code">Code or a script</option>
      <option value="other">Something else</option>
    </select>

    <label for="environment">Where do you use it? <span class="hint">(so we send the right install steps)</span></label>
    <select id="environment" name="environment">
      <option value="">Not sure</option>
      <option value="excel_desktop_windows">Excel on Windows</option>
      <option value="excel_desktop_mac">Excel on Mac</option>
      <option value="excel_web">Excel on the web</option>
      <option value="google_sheets">Google Sheets</option>
      <option value="codebase">A code repository</option>
      <option value="other">Other</option>
    </select>

    <label for="description">What happened? <span class="hint">(what's missing, roughly when, what still survives)</span></label>
    <textarea id="description" name="description" maxlength="5000" required></textarea>

    <div class="hp" aria-hidden="true">
      <label for="website">Leave this empty</label>
      <input id="website" name="website" tabindex="-1" autocomplete="off">
    </div>

    <label class="check"><input type="checkbox" id="consent" name="consent" required>
      <span>You may email me about this request.</span></label>

    <button type="submit" id="send">Send request</button>
    <div id="status" role="status" aria-live="polite"></div>
  </form>

  <p class="note">Please don't attach files here. Once we reply, we'll send a secure way to share them,
  and every file is scanned before anyone opens it.</p>
</main>
<script>
  const form = document.getElementById("ticket");
  const status = document.getElementById("status");
  const send = document.getElementById("send");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.className = ""; status.textContent = "";
    const f = new FormData(form);
    const body = Object.fromEntries(f.entries());
    body.consent = document.getElementById("consent").checked;
    send.disabled = true; send.textContent = "Sending...";
    try {
      const res = await fetch("/api/tickets", { method: "POST",
        headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      const out = await res.json().catch(() => ({}));
      if (res.ok) {
        status.className = "ok";
        status.textContent = out.message || "Thanks, we'll be in touch.";
        form.reset();
      } else {
        status.className = "err";
        status.textContent = out.error || "Something went wrong. Please try again.";
      }
    } catch {
      status.className = "err";
      status.textContent = "We couldn't reach the server. Please try again in a minute.";
    } finally {
      send.disabled = false; send.textContent = "Send request";
    }
  });
</script>
</body>
</html>`;
