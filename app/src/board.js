// The live Data Care board, built for a projector. Polls /api/board every 5 seconds.
export const BOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Care Live</title>
<link rel="icon" href="/favicon.svg">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Instrument+Serif&amp;display=swap">
<style>
:root{--page:#FBF8F6;--card:#FFFFFF;--line:#ECE6E1;--soft:#F3EEE9;--ink:#141414;--body:#4A4A4A;--muted:#6B6B6B;
  --accent:#B4470F;--good:#13795B;--bad:#B42318;--work:#7B3FE4;--wait:#E07A1F;
  --l0:#0F5F47;--l0-bg:#E6F4EE;--l1:#8A3409;--l1-bg:#FFF1E4;--l2:#5B2BB0;--l2-bg:#F4EEFF;--l3:#4A4A4A;--l3-line:#D6CCC3;
  --sans:Inter,system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;--serif:"Instrument Serif",Georgia,serif;
  --gut:clamp(16px,3vw,40px);--max:1680px;color-scheme:light}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--page);color:var(--ink);font:16px/1.45 var(--sans);padding:0 0 48px;display:flex;flex-direction:column;gap:20px;min-height:100vh}
body>section{width:min(100% - 2*var(--gut),var(--max));margin:0 auto}
b,strong,h2{font-weight:600}
.kpi b,.lane h2 span:last-child,.card div,#status,ol li .t,ol li .c:last-child,.labels b,#detail .grid b{font-variant-numeric:tabular-nums}
header{display:flex;align-items:center;flex-wrap:wrap;gap:12px 24px;padding:20px max(var(--gut),(100% - var(--max))/2) 16px;border-bottom:1px solid var(--line);
  background:linear-gradient(90deg,#FF8A1F,#F2557A 52%,#7B3FE4) top/100% 4px no-repeat,var(--card)}
h1{margin:0;display:flex;align-items:center;gap:12px;font:400 clamp(30px,2.6vw,44px)/1 var(--serif);letter-spacing:-.01em}
h1 .mark{flex:none;width:1.1em;height:1.1em}
#status{margin-left:auto;font-size:14px;color:var(--body)}
.home{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);font-size:15px;font-weight:500;text-decoration:none}
.home:focus-visible,#detail button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.summary{font:400 clamp(22px,2vw,32px)/1.25 var(--serif);color:var(--ink);padding:4px 2px} .summary b{font-weight:400;color:var(--accent)}
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}
.kpi{container-type:inline-size;display:flex;flex-direction:column;justify-content:space-between;gap:6px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.kpi span{order:-1;font-size:14px;font-weight:500;color:var(--body)}
.kpi span::first-letter,.lane h2 span:first-child::first-letter,.labels span::first-letter,#detail h2::first-letter{text-transform:uppercase}
.kpi b{font-size:40px;font-size:clamp(26px,20cqi,52px);line-height:1.1;letter-spacing:-.02em;white-space:nowrap}
.kpi #k-verdict{font-size:30px;font-size:clamp(22px,15cqi,40px)}
.kpi.pass{background:var(--l0-bg);border-color:#BFE3D2} .kpi.pass b{color:var(--l0)}
.kpi.fail{background:#FEF3F2;border-color:#F5C9C4} .kpi.fail b{color:var(--bad)}
.kpi.human{background:#FFF8F1;border-color:#F6D9BF} .kpi.human b{color:var(--accent)}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
@media (min-width:1200px){.lanes{grid-template-columns:none;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr)} .lane h2{min-height:calc(2.5em + 4px);align-items:flex-start}}
.lane{border:1px dashed var(--l3-line);border-radius:14px;padding:10px;display:flex;flex-direction:column;gap:8px;min-height:180px}
.lane.hot{background:var(--card);border:1px solid var(--line)}
.lane h2{margin:0;padding:2px 2px 2px 4px;display:flex;justify-content:space-between;align-items:center;gap:6px;font-size:13px;line-height:1.25;color:var(--body)}
.lane h2 span:last-child{flex:none;min-width:26px;padding:1px 8px;border-radius:999px;background:var(--soft);text-align:center}
.lane.hot h2{color:var(--ink)} .lane.hot h2 span:last-child{background:var(--ink);color:#FFFFFF}
.lane .empty{padding:0 4px}
.card{--dot:var(--work);background:var(--page);border:1px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer;transition:border-color .15s}
.card b{display:flex;align-items:center;gap:8px;font-size:17px;line-height:1.3}
.card b::before{content:"";flex:none;width:9px;height:9px;border-radius:50%;background:var(--dot)}
.card div{margin-top:4px;font-size:13.5px;line-height:1.35;color:var(--body)}
.card.delivered{--dot:var(--good);background:#F3FAF6;border-color:#CFE9DC}
.card.waiting_client{--dot:var(--wait);background:#FFF8F1;border-color:#F6D9BF}
.card.unresolved{--dot:#9A8F86;background:var(--card);border-style:dashed;border-color:var(--l3-line)}
.card:hover,.home:hover,#detail button:hover{border-color:var(--ink)}
.bottom{display:grid;grid-template-columns:2fr 1fr;gap:16px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.panel h2{margin:0 0 12px;font-size:16px;color:var(--ink)}
ol{margin:0;padding:0;list-style:none;display:grid;font-size:15px}
ol li{display:grid;grid-template-columns:5.5em 5.5em minmax(0,1fr) auto;gap:12px;align-items:baseline;padding:8px 10px;border-top:1px solid var(--soft);overflow-wrap:anywhere}
ol li:first-child{border-top-color:transparent}
ol li .t,ol li .c{font-size:14px;color:var(--body)}
ol li .c:last-child{color:var(--ink);font-weight:500}
ol li.human{background:var(--l1-bg);color:var(--l1);border-radius:10px;border-top-color:transparent}
ol li.human .t,ol li.human .c{color:var(--l1)}
ol li.empty{display:block}
.labels{display:grid;gap:8px;font-size:15px}
.labels div{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 14px;border:1px solid transparent;border-radius:12px;font-weight:500}
.labels b{font-size:26px;line-height:1.15}
.labels div:nth-child(1){background:var(--l0-bg);color:var(--l0)}
.labels div:nth-child(2){background:var(--l1-bg);color:var(--l1)}
.labels div:nth-child(3){background:var(--l2-bg);color:var(--l2)}
.labels div:nth-child(4){background:var(--card);color:var(--l3);border:1px dashed var(--l3-line)}
.empty{color:var(--muted);font-size:14px}
#detail{display:none} #detail.open{display:block}
#detail .head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}
#detail .head b{font-size:22px;line-height:1.25}
#detail button{flex:none;min-height:44px;padding:0 18px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);font:500 15px var(--sans);cursor:pointer}
#detail .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:6px}
#detail .grid div{display:flex;flex-direction:column;gap:2px;background:var(--page);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
#detail .grid b{font-size:26px;line-height:1.15;letter-spacing:-.01em}
#detail .grid span{font-size:13.5px;color:var(--body)}
#detail h2{margin:18px 0 8px;font-size:15px}
#detail ul{margin:0 0 8px;padding:0;list-style:none;display:grid;gap:6px;font-size:15px}
#detail li{overflow-wrap:anywhere}
#detail li small{font-size:13px;color:var(--muted)}
.tag{display:inline-block;font-size:12.5px;font-weight:600;line-height:1.5;border:1px solid transparent;border-radius:999px;padding:0 8px;margin-right:8px}
.tag.l0{background:var(--l0-bg);color:var(--l0)} .tag.l1{background:var(--l1-bg);color:var(--l1)}
.tag.l2{background:var(--l2-bg);color:var(--l2)} .tag.l3{background:var(--card);color:var(--l3);border:1px dashed var(--l3-line)}
@media (max-width:1100px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:800px){.bottom{grid-template-columns:1fr}}
@media (max-width:600px){
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px} .kpi{padding:14px}
  h1{flex:1 0 100%} #status{margin-left:0;flex:1 1 auto} .lane{min-height:0} .panel{padding:16px}
  ol li{grid-template-columns:auto minmax(0,1fr) auto;gap:2px 10px} ol li>span:nth-child(3){grid-column:1/-1;grid-row:2}
}
</style>
</head>
<body>
<header>
  <h1>
    <svg class="mark" viewBox="-72 -72 144 144" aria-hidden="true"><defs><linearGradient id="dc-mark-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient></defs><path d="M-25.77 -47.62 L-25.98 -47.33 L-26.12 -47.05 L-26.25 -46.67 L-26.30 -46.37 L-26.32 -45.99 L-26.28 -45.68 L-26.21 -45.38 L-26.06 -45.01 L-25.80 -44.62 L-25.55 -44.34 L-24.17 -43.24 L-23.32 -42.45 L-22.84 -41.97 L-21.69 -40.62 L-21.00 -39.68 L-20.63 -39.11 L-20.06 -38.14 L-19.75 -37.54 L-19.26 -36.48 L-18.84 -35.39 L-18.63 -34.75 L-18.32 -33.62 L-18.19 -33.00 L-17.99 -31.84 L-17.87 -30.69 L-17.83 -30.05 L-17.82 -28.88 L-17.85 -28.24 L-17.95 -27.08 L-18.04 -26.44 L-18.26 -25.30 L-18.42 -24.65 L-18.95 -22.95 L-19.39 -21.88 L-19.68 -21.26 L-20.20 -20.26 L-20.55 -19.68 L-21.19 -18.70 L-21.89 -17.78 L-22.33 -17.26 L-23.12 -16.40 L-23.97 -15.60 L-24.48 -15.16 L-25.37 -14.46 L-25.92 -14.07 L-26.91 -13.45 L-27.94 -12.89 L-28.54 -12.60 L-29.62 -12.15 L-30.22 -11.93 L-31.33 -11.59 L-32.47 -11.31 L-33.10 -11.19 L-34.26 -11.03 L-34.93 -10.97 L-36.70 -10.93 L-38.46 -11.06 L-39.72 -11.26 L-41.44 -11.69 L-42.55 -12.05 L-43.18 -12.30 L-44.25 -12.77 L-45.31 -13.33 L-45.86 -13.66 L-46.84 -14.30 L-47.79 -15.03 L-48.61 -15.72 L-49.09 -16.00 L-49.59 -16.16 L-50.15 -16.21 L-50.67 -16.13 L-51.19 -15.93 L-51.58 -15.67 L-51.94 -15.31 L-68.82 5.54 L-69.13 6.03 L-69.29 6.54 L-69.34 6.85 L-69.34 7.16 L-69.25 7.72 L-69.14 8.01 L-68.96 8.34 L-68.71 8.66 L-68.47 8.89 L-43.47 29.14 L-43.11 29.51 L-42.86 29.97 L-42.74 30.47 L-42.73 30.86 L-42.77 31.12 L-42.89 31.49 L-43.01 31.72 L-43.24 32.03 L-43.43 32.21 L-43.86 32.50 L-45.35 33.06 L-46.34 33.51 L-47.28 34.02 L-48.19 34.59 L-49.11 35.26 L-49.95 35.96 L-51.03 37.02 L-51.74 37.84 L-52.39 38.69 L-52.98 39.57 L-53.51 40.51 L-53.79 41.07 L-54.22 42.04 L-54.57 42.98 L-54.88 44.01 L-55.11 45.04 L-55.29 46.12 L-55.39 47.19 L-55.42 48.32 L-55.37 49.39 L-55.26 50.46 L-55.07 51.52 L-54.82 52.56 L-54.50 53.60 L-54.12 54.59 L-53.66 55.57 L-52.91 56.89 L-52.31 57.78 L-51.65 58.65 L-50.93 59.45 L-50.13 60.25 L-49.31 60.95 L-48.46 61.59 L-47.56 62.18 L-46.63 62.71 L-45.64 63.18 L-44.65 63.59 L-43.20 64.04 L-42.14 64.28 L-41.08 64.45 L-40.01 64.55 L-38.88 64.58 L-37.81 64.54 L-36.72 64.42 L-35.68 64.24 L-34.62 63.98 L-33.60 63.66 L-32.20 63.10 L-31.23 62.62 L-30.68 62.31 L-29.79 61.74 L-28.93 61.11 L-28.15 60.46 L-27.38 59.74 L-26.65 58.95 L-26.24 58.47 L-25.35 57.24 L-24.79 56.33 L-24.28 55.37 L-23.81 54.33 L-23.44 53.32 L-23.14 52.29 L-22.90 51.23 L-22.67 49.66 L-22.48 49.18 L-22.26 48.85 L-22.08 48.66 L-21.77 48.43 L-21.55 48.31 L-21.05 48.16 L-20.79 48.13 L-20.40 48.16 L-19.91 48.30 L-19.46 48.58 L5.63 68.89 L6.09 69.15 L6.63 69.31 L7.16 69.34 L7.72 69.25 L8.01 69.14 L8.34 68.96 L8.66 68.71 L8.91 68.45 L25.77 47.62 L26.05 47.19 L26.23 46.76 L26.32 46.21 L26.28 45.68 L26.12 45.15 L25.86 44.69 L25.48 44.28 L24.63 43.62 L23.73 42.84 L23.26 42.40 L22.46 41.55 L21.69 40.63 L21.00 39.68 L20.63 39.11 L20.05 38.11 L19.28 36.51 L18.82 35.32 L18.32 33.62 L17.99 31.88 L17.91 31.21 L17.83 30.05 L17.82 29.41 L17.85 28.25 L17.90 27.61 L18.04 26.44 L18.26 25.30 L18.42 24.65 L18.74 23.56 L18.97 22.92 L19.41 21.84 L19.91 20.79 L20.24 20.20 L20.85 19.21 L21.21 18.68 L21.91 17.75 L22.33 17.26 L23.12 16.40 L23.97 15.60 L24.48 15.16 L25.37 14.46 L25.92 14.07 L26.91 13.45 L27.94 12.89 L28.54 12.60 L29.62 12.15 L30.22 11.93 L31.33 11.59 L31.95 11.43 L33.10 11.19 L34.26 11.03 L34.93 10.97 L36.69 10.93 L38.46 11.06 L39.72 11.26 L41.44 11.69 L42.55 12.05 L43.18 12.30 L44.25 12.77 L45.31 13.33 L45.86 13.66 L46.84 14.30 L47.79 15.03 L48.61 15.72 L49.09 16.00 L49.59 16.16 L50.15 16.21 L50.67 16.13 L51.19 15.93 L51.58 15.67 L51.94 15.31 L68.82 -5.54 L69.13 -6.03 L69.29 -6.54 L69.34 -6.85 L69.34 -7.16 L69.25 -7.72 L69.14 -8.01 L68.96 -8.34 L68.71 -8.66 L68.47 -8.89 L43.47 -29.14 L43.11 -29.51 L42.91 -29.85 L42.82 -30.09 L42.74 -30.47 L42.73 -30.73 L42.77 -31.12 L42.95 -31.61 L43.16 -31.93 L43.33 -32.13 L43.53 -32.29 L43.86 -32.50 L45.42 -33.09 L46.80 -33.75 L47.74 -34.30 L48.63 -34.90 L49.54 -35.60 L50.67 -36.64 L51.45 -37.49 L52.38 -38.68 L52.98 -39.59 L53.55 -40.57 L54.01 -41.54 L54.42 -42.55 L54.75 -43.56 L55.02 -44.61 L55.22 -45.66 L55.39 -47.17 L55.42 -48.26 L55.37 -49.41 L55.19 -50.91 L54.95 -52.06 L54.53 -53.51 L54.12 -54.59 L53.66 -55.57 L52.90 -56.91 L52.26 -57.86 L51.31 -59.04 L50.56 -59.83 L49.71 -60.61 L48.52 -61.55 L47.56 -62.18 L46.61 -62.72 L45.24 -63.36 L44.65 -63.59 L43.63 -63.92 L42.61 -64.18 L41.55 -64.39 L40.55 -64.51 L39.49 -64.58 L38.86 -64.58 L37.79 -64.54 L36.74 -64.42 L35.74 -64.25 L34.70 -64.00 L33.69 -63.69 L32.69 -63.31 L32.11 -63.06 L31.17 -62.58 L30.31 -62.08 L28.97 -61.15 L27.75 -60.10 L26.60 -58.89 L25.61 -57.62 L25.02 -56.73 L24.52 -55.85 L24.05 -54.88 L23.64 -53.89 L23.31 -52.89 L23.14 -52.28 L22.90 -51.23 L22.67 -49.66 L22.48 -49.18 L22.18 -48.76 L21.88 -48.50 L21.66 -48.36 L21.18 -48.18 L20.79 -48.13 L20.53 -48.14 L20.28 -48.18 L19.91 -48.30 L19.46 -48.58 L-5.63 -68.89 L-6.09 -69.15 L-6.54 -69.29 L-7.01 -69.35 L-7.56 -69.29 L-7.93 -69.18 L-8.29 -68.99 L-8.60 -68.77 L-8.89 -68.47Z" fill="url(#dc-mark-g)"/></svg>
    Data Care Live
  </h1>
  <div id="status">connecting…</div>
  <a class="home" href="/">Data Care home</a>
</header>
<section class="summary" id="summary"></section>
<section class="kpis">
  <div class="kpi"><b id="k-cases">0</b><span>cases</span></div>
  <div class="kpi"><b id="k-cost">$0.00</b><span>total agent cost</span></div>
  <div class="kpi"><b id="k-avg">$0.00</b><span>cost per case (logged)</span></div>
  <div class="kpi human"><b id="k-human">0</b><span id="k-human-sub">humans stepped in</span></div>
  <div class="kpi"><b id="k-delivered">0</b><span>cases delivered</span></div>
  <div class="kpi" id="k-verdict-box"><b id="k-verdict">none</b><span id="k-verdict-sub">latest verdict</span></div>
</section>
<section class="lanes" id="lanes"></section>
<section class="panel" id="detail"></section>
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
  const costed = d.cases.filter((c) => c.cost > 0), caseCost = costed.reduce((s, c) => s + c.cost, 0);
  document.getElementById("k-avg").textContent = money(costed.length ? caseCost / costed.length : 0);
  document.getElementById("k-human").textContent = d.humans_stepped_in;
  document.getElementById("k-human-sub").textContent = "humans stepped in" + (d.events_total ? " · of " + d.events_total + " logged steps" : "");
  const dl = d.cases.filter((c) => c.stage === "delivered");
  document.getElementById("k-delivered").textContent = dl.length + " / " + d.cases.length;
  const lb = d.labels || {}, built = (lb["recovered"] || 0) + (lb["reconstructed and tested"] || 0);
  const dq = dl.reduce((s, c) => s + (c.quote_usd || 0), 0), dc = dl.reduce((s, c) => s + c.cost, 0);
  document.getElementById("summary").innerHTML = dl.length
    ? 'Damaged files in, rebuilt files out: <b>' + dl.length + ' cases delivered</b>, <b>' + built + ' items</b> recovered or rebuilt and tested, for <b>' + money(dc) + '</b> of agent cost against <b>' + money(dq) + '</b> quoted.'
    : 'Waiting for the first delivered case.';
  const v = d.latest_verdict, box = document.getElementById("k-verdict-box");
  const outcome = v ? (v.outcome || (v.pass ? "pass" : "fail")) : null;
  box.className = "kpi" + (outcome ? ({pass: " pass", fail: " fail"}[outcome] || " human") : "");
  document.getElementById("k-verdict").textContent = outcome ? outcome.toUpperCase() : "none";
  document.getElementById("k-verdict-sub").textContent = v ? "latest verdict · " + v.case_id + " · retry " + v.retry_count : "latest verdict";

  document.getElementById("lanes").innerHTML = d.stages.map((stage) => {
    const cs = d.cases.filter((c) => c.stage === stage);
    if (!cs.length) return "";
    const cards = cs.map((c) =>
      '<div class="card ' + esc(c.stage) + '" data-id="' + esc(c.case_id) + '" onclick="openCase(this.dataset.id)"><b>' + esc(c.case_id) + '</b>' +
      '<div>' + esc(c.kind) + (c.cost > 0 ? ' · ' + money(c.cost) : '') + (c.retry_count ? ' · retry ' + c.retry_count : '') + '</div>' +
      (c.quote_usd != null ? '<div>quote ' + money(c.quote_usd) + ' · ' + (c.cost > 0 ? 'cost ' + money(c.cost) + (c.quote_usd > 0 ? ' · ' + Math.round(100 * (1 - c.cost / c.quote_usd)) + '% margin' : '') : 'cost not logged') + '</div>' : '') + '</div>').join("");
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

let openId = null;
async function openCase(id) { openId = id; await showDetail(); document.getElementById("detail").scrollIntoView({behavior: "smooth"}); }
function closeCase() { openId = null; document.getElementById("detail").className = ""; }
async function showDetail() {
  if (!openId) return;
  const el = document.getElementById("detail");
  try {
    const r = await fetch("/api/board/case/" + encodeURIComponent(openId), {cache: "no-store"});
    if (!r.ok) throw new Error("HTTP " + r.status);
    const c = await r.json();
    const v = c.verdicts[0];
    const outcome = v ? (v.outcome || (v.pass ? "pass" : "fail")) : "none";
    const quote = c.quote_usd == null ? null : c.quote_usd;
    const byLabel = LABELS.map((l, i) => ({l: l, i: i, items: c.report_items.filter((x) => x.label === l)}));
    el.className = "panel open";
    el.innerHTML = '<div class="head"><b>' + esc(c.case_id) + ' · ' + esc(c.kind) + ' · ' + esc(c.stage.replace("_", " ")) +
      '</b><button onclick="closeCase()">close</button></div>' +
      '<div class="grid">' +
      '<div><b>' + esc(outcome.toUpperCase()) + '</b><span>verdict' + (v ? ' · retry ' + v.retry_count : '') + '</span></div>' +
      '<div><b>' + money(c.cost) + '</b><span>agent cost</span></div>' +
      '<div><b>' + (quote == null ? "n/a" : money(quote)) + '</b><span>quote' + (quote ? ' · margin ' + money(quote - c.cost) : '') + '</span></div>' +
      '<div><b>' + c.counts.fragments + ' / ' + c.counts.gaps + ' / ' + c.counts.rules + '</b><span>fragments / gaps / rules</span></div></div>' +
      byLabel.map((g) => '<h2>' + g.l + ' (' + g.items.length + ')</h2><ul>' + (g.items.length ? g.items.map((x) =>
        '<li><span class="tag l' + g.i + '">' + g.l.split(" ").pop() + '</span>' + esc(x.item) + ' <small>' + esc((x.cites || []).join(", ")) + '</small></li>').join("") : '<li class="empty">none</li>') + '</ul>').join("") +
      (c.rules.length ? '<h2>Rules and ranked hypotheses (' + c.rules.length + ')</h2><ul>' + c.rules.map((x) =>
        '<li><span class="tag l' + Math.max(0, LABELS.indexOf(x.status)) + '">' + esc(x.status.split(" ").pop()) + '</span><b>' + esc(x.rule_id) + '</b> ' + esc(x.description) +
        ' <small>' + esc((x.evidence || []).slice(0, 6).join(", ")) + '</small></li>').join("") + '</ul>' : '') +
      '<h2>Steps</h2><ul>' + c.events.slice(0, 8).map((e) => '<li><small>' + time(e.created_at) + '</small> ' + esc(e.agent) + ': ' + esc(e.message || e.stage) + ' <small>' + money(e.cost_usd) + '</small></li>').join("") + '</ul>';
  } catch (e) { el.className = "panel open"; el.textContent = "can't load " + openId + ": " + e.message; }
}

async function tick() {
  const status = document.getElementById("status");
  try {
    const r = await fetch("/api/board", {cache: "no-store"});
    if (!r.ok) throw new Error("HTTP " + r.status);
    render(await r.json());
    showDetail();
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
