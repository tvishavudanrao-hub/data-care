// The public ticket form, in the Data Care brand (web/tickets/brand.js). No external scripts, fonts or
// trackers, so it works anywhere the app runs (Worker, Vercel, Node). Posts JSON to /api/tickets.

import { page } from "./brand.js";

export const FORM_HTML = page("Data Care: request a recovery", `
  <p class="kicker">Request a recovery</p>
  <h1>Tell us what you <em>lost</em></h1>
  <p class="lead">We'll reply by email with a quote and how to get started. We rebuild only from data that still
  survives somewhere, and anything we can't support with evidence, we say so.</p>

  <form id="ticket" class="card" novalidate>
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

    <label for="environment">Where do you use it? <span class="hint">(so we send the right steps)</span></label>
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

    <div style="position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden" aria-hidden="true">
      <label for="website">Leave this empty</label>
      <input id="website" name="website" tabindex="-1" autocomplete="off">
    </div>

    <label style="display:flex;gap:10px;align-items:flex-start;font-weight:400;color:var(--body);margin-top:20px">
      <input type="checkbox" id="consent" name="consent" required style="width:auto;min-height:0;margin-top:4px">
      <span>You may email me about this request.</span></label>

    <button type="submit" id="send" class="btn" style="margin-top:20px">Send request</button>
    <div id="status" role="status" aria-live="polite" style="margin-top:14px;min-height:1.5em"></div>
  </form>

  <p class="muted" style="margin-top:20px">Please don't attach files here. Once we reply, you can connect your
  storage read-only or send files another way, and every file is scanned before anyone opens it.</p>

<script>
  const form = document.getElementById("ticket");
  const status = document.getElementById("status");
  const send = document.getElementById("send");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.className = ""; status.textContent = "";
    const body = Object.fromEntries(new FormData(form).entries());
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
</script>`);
