// The live Data Care board, built for a projector. Polls /api/board every 5 seconds.
export const BOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Care Live</title>
<style>
:root{--bg:#0b1419;--panel:#122029;--line:#22394a;--ink:#e8f0f4;--muted:#8fa7b5;--accent:#4cc3d9;
  --good:#5fd38d;--warn:#f0a04b;--bad:#ff7b6e;--mono:ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--ink);font:16px/1.4 var(--sans);padding:20px 24px;display:flex;flex-direction:column;gap:18px;min-height:100vh}
header{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{margin:0;font-size:30px;letter-spacing:-.01em}
h1 span{color:var(--accent)}
#status{font:13px var(--mono);color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kpi b{display:block;font:600 32px/1.1 var(--mono);font-variant-numeric:tabular-nums}
.kpi span{font-size:13px;color:var(--muted)}
.kpi.pass b{color:var(--good)} .kpi.fail b{color:var(--bad)} .kpi.human b{color:var(--warn)}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.lane{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px;display:flex;flex-direction:column;gap:8px;min-height:140px}
.lane h2{margin:0;font:600 12px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);display:flex;justify-content:space-between}
.lane.hot{border-color:var(--accent)}
.card{background:var(--bg);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:6px;padding:8px 10px}
.card.unresolved{border-left-color:var(--bad)} .card.delivered{border-left-color:var(--good)} .card.waiting_client{border-left-color:var(--warn)}
.card b{font:600 15px var(--mono)}
.card div{font-size:12.5px;color:var(--muted)}
.bottom{display:grid;grid-template-columns:2fr 1fr;gap:12px}
@media (max-width:800px){.bottom{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.panel h2{margin:0 0 8px;font:600 12px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
ol{margin:0;padding:0;list-style:none;display:grid;gap:4px;font-size:14px}
ol li{display:grid;grid-template-columns:70px 72px 1fr auto;gap:8px;align-items:baseline}
ol li .t,ol li .c{font:12.5px var(--mono);color:var(--muted)}
ol li.human{color:var(--warn)}
.labels{display:grid;gap:6px;font-size:14px}
.labels div{display:flex;justify-content:space-between;gap:8px}
.labels b{font-family:var(--mono)}
.empty{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<header>
  <h1>Data Care <span>live</span></h1>
  <div id="status">connecting…</div>
</header>
<section class="kpis">
  <div class="kpi"><b id="k-cases">0</b><span>cases</span></div>
  <div class="kpi"><b id="k-cost">$0.00</b><span>total agent cost</span></div>
  <div class="kpi"><b id="k-avg">$0.00</b><span>cost per case</span></div>
  <div class="kpi human"><b id="k-human">0</b><span>humans stepped in</span></div>
  <div class="kpi"><b id="k-checkups">0</b><span>checkups run</span></div>
  <div class="kpi" id="k-verdict-box"><b id="k-verdict">none</b><span id="k-verdict-sub">latest verdict</span></div>
</section>
<section class="lanes" id="lanes"></section>
<section class="bottom">
  <div class="panel"><h2>Latest steps</h2><ol id="events"></ol></div>
  <div class="panel"><h2>Report labels</h2><div class="labels" id="labels"></div></div>
</section>
<script>
const LABELS = ["recovered", "reconstructed and tested", "reconstructed but untested", "unresolved"];
const money = (n) => "$" + Number(n || 0).toFixed(2);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const time = (iso) => new Date(iso).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});

function render(d) {
  document.getElementById("k-cases").textContent = d.cases.length;
  document.getElementById("k-cost").textContent = money(d.total_cost);
  const caseCost = d.cases.reduce((s, c) => s + c.cost, 0);
  document.getElementById("k-avg").textContent = money(d.cases.length ? caseCost / d.cases.length : 0);
  document.getElementById("k-human").textContent = d.humans_stepped_in;
  document.getElementById("k-checkups").textContent = d.checkups_run;
  const v = d.latest_verdict, box = document.getElementById("k-verdict-box");
  const outcome = v ? (v.outcome || (v.pass ? "pass" : "fail")) : null;
  box.className = "kpi" + (outcome ? ({pass: " pass", fail: " fail"}[outcome] || " human") : "");
  document.getElementById("k-verdict").textContent = outcome ? outcome.toUpperCase() : "none";
  document.getElementById("k-verdict-sub").textContent = v ? "latest verdict · " + v.case_id + " · retry " + v.retry_count : "latest verdict";

  document.getElementById("lanes").innerHTML = d.stages.map((stage) => {
    const cs = d.cases.filter((c) => c.stage === stage);
    const cards = cs.map((c) =>
      '<div class="card ' + esc(c.stage) + '"><b>' + esc(c.case_id) + '</b>' +
      '<div>' + esc(c.kind) + ' · ' + money(c.cost) + (c.retry_count ? ' · retry ' + c.retry_count : '') + '</div>' +
      (c.quote_usd != null ? '<div>quote ' + money(c.quote_usd) + '</div>' : '') + '</div>').join("");
    return '<div class="lane' + (cs.length ? ' hot' : '') + '"><h2><span>' + esc(stage.replace("_", " ")) +
      '</span><span>' + cs.length + '</span></h2>' + (cards || '<div class="empty">none</div>') + '</div>';
  }).join("");

  document.getElementById("events").innerHTML = d.recent_events.length ? d.recent_events.map((e) =>
    '<li class="' + (e.human_stepped_in ? 'human' : '') + '"><span class="t">' + time(e.created_at) + '</span>' +
    '<span class="c">' + esc(e.case_id || "") + '</span><span>' + esc(e.agent) + ': ' + esc(e.message || e.stage) +
    (e.human_stepped_in ? ' (human)' : '') + '</span><span class="c">' + money(e.cost_usd) + '</span></li>').join("")
    : '<li class="empty">No steps yet.</li>';

  document.getElementById("labels").innerHTML = LABELS.map((l) =>
    '<div><span>' + l + '</span><b>' + (d.labels[l] || 0) + '</b></div>').join("");
}

async function tick() {
  const status = document.getElementById("status");
  try {
    const r = await fetch("/api/board", {cache: "no-store"});
    if (!r.ok) throw new Error("HTTP " + r.status);
    render(await r.json());
    status.textContent = "updated " + new Date().toLocaleTimeString();
  } catch (e) {
    status.textContent = "can't reach the records store (" + e.message + "), retrying";
  }
}
tick();
setInterval(tick, 5000);
</script>
</body>
</html>`;
