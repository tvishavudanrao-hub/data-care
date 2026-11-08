// Client pages of the Data Care site: case tracking at /case and /case/<id>, the collector download page at
// /download, the collector zip at /download/datacare-collect.zip and the favicon. Plain strings plus one small zip
// writer, no build step and no dependencies; site.js routes to them. Case data comes from GET /api/board/case/<id>,
// which is public and masks the client's email.
import { COLLECTOR_COMMAND } from "./collector.js";

const EMAIL = "datacare-recover@agentmail.to";

// The brand puzzle piece (docs/brand/datacare-mark.svg, viewBox -72 -72 144 144), simplified to 98 points for the
// logo and 55 for the favicon. Same outline at these sizes, a tenth of the bytes.
const MARK_D = "M-25.8-47.6L-26.3-46.4L-26.1-45L-22.8-42L-20.6-39.1L-18.8-35.4L-18-31.8L-17.9-28.2L-18.4-24.6L-19.7-21.3L-21.9-17.8L-24.5-15.2L-27.9-12.9L-31.3-11.6L-34.9-11L-38.5-11.1L-41.4-11.7L-45.3-13.3L-49.1-16L-51.2-15.9L-68.8 5.5L-69.3 6.5L-69.2 7.7L-68.5 8.9L-43.5 29.1L-42.9 30L-42.8 31.1L-43.4 32.2L-48.2 34.6L-51.7 37.8L-53.8 41.1L-55.1 45L-55.4 49.4L-54.5 53.6L-52.3 57.8L-49.3 61L-45.6 63.2L-41.1 64.5L-36.7 64.4L-32.2 63.1L-28.9 61.1L-26.2 58.5L-23.8 54.3L-22.5 49.2L-21.6 48.3L-20.4 48.2L-19.5 48.6L5.6 68.9L7.7 69.2L8.9 68.5L26.2 46.8L25.9 44.7L22.5 41.5L20.1 38.1L18.8 35.3L18 31.9L17.9 28.2L18.4 24.6L19.9 20.8L21.9 17.8L24.5 15.2L27.9 12.9L31.3 11.6L34.9 11L38.5 11.1L41.4 11.7L45.3 13.3L49.1 16L51.2 15.9L68.8-5.5L69.3-6.5L69.2-7.7L68.5-8.9L42.9-29.9L42.8-31.1L43.3-32.1L48.6-34.9L52.4-38.7L54.4-42.5L55.4-47.2L55-52.1L52.9-56.9L49.7-60.6L45.2-63.4L41.5-64.4L37.8-64.5L33.7-63.7L30.3-62.1L27.8-60.1L25.6-57.6L23.6-53.9L22.5-49.2L21.7-48.4L20.5-48.1L19.5-48.6L-5.6-68.9L-7.6-69.3L-8.9-68.5Z";
const FAVICON_D = "M-26-48L-26-45L-21-39L-18-32L-18-25L-22-18L-28-13L-35-11L-41-12L-49-16L-51-16L-69 6L-69 8L-43 30L-43 32L-52 38L-55 45L-54 54L-49 61L-41 64L-32 63L-26 58L-22 49L-20 48L6 69L8 69L26 47L26 45L20 38L18 32L18 25L22 18L28 13L35 11L41 12L49 16L51 16L69-6L69-8L43-30L43-32L49-35L52-39L55-47L55-52L53-57L50-61L45-63L38-65L30-62L26-58L22-49L21-48L-6-69L-8-69Z";
const GRADIENT_STOPS = '<stop offset="0" stop-color="#FF8A1F"/><stop offset=".52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/>';

// The app icon (docs/brand/datacare-app-icon.svg): white piece on the gradient tile, same proportions.
export const FAVICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144">' +
  `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">${GRADIENT_STOPS}</linearGradient></defs>` +
  '<rect x="-72" y="-72" width="144" height="144" rx="33" fill="url(#g)"/>' +
  `<path fill="#fff" transform="scale(.647)" d="${FAVICON_D}"/></svg>`;

const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Instrument+Serif:ital@0;1&amp;display=swap";

const icon = (d, size = 18, width = 2, stroke = "currentColor") =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="${width}" ` +
  `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="${d}"/></svg>`;
const ARROW = "M5 12h14M13 6l6 6-6 6";
const BACK = "M19 12H5M11 6l-6 6 6 6";
const DOWN = "M12 4v11M7 10l5 5 5-5M5 20h14";
const MAIL = `<span class="nw">${EMAIL}</span>`;
const CHECK = "M5 12.5l4.5 4.5L19 7.5";
const CROSS = "M6 6l12 12M18 6L6 18";

const logo = (size) =>
  `<svg width="${size}" height="${size}" viewBox="-72 -72 144 144" aria-hidden="true" focusable="false"><use href="#dc-mark" fill="url(#dc-grad)"/></svg>`;

// One hidden copy of the gradient and the piece; every logo on the page points at it.
const DEFS = '<svg width="0" height="0" aria-hidden="true" focusable="false" style="position:absolute">' +
  `<defs><linearGradient id="dc-grad" x1="0" y1="0" x2="1" y2="1">${GRADIENT_STOPS}</linearGradient>` +
  `<path id="dc-mark" d="${MARK_D}"/></defs></svg>`;

const navLink = (current) => (href, text) =>
  `<a href="${href}"${href === current ? ' aria-current="page"' : ""}>${text}</a>`;

function header(current) {
  const a = navLink(current);
  return `<header class="site-head">
  <a class="brand" href="/">${logo(30)}Data Care</a>
  <nav class="site-nav" aria-label="Main">${a("/#how", "How it works")}${a("/board", "Live board")}${a("/case", "Track a case")}</nav>
  <a class="pill" href="/tickets">Get an estimate</a>
</header>`;
}

function footer(current) {
  const a = navLink(current);
  return `<footer class="site-foot"><div class="foot-in">
  <a class="foot-brand" href="/">${logo(22)}Data Care</a>
  <nav class="foot-nav" aria-label="Footer">${a("/#how", "How it works")}${a("/board", "Live board")}${a("/case", "Track a case")}${a("/download", "Download")}${a("/tickets", "Get an estimate")}</nav>
</div>
<p class="foot-note">Questions about a case? Reply to our email from ${MAIL}.</p>
</footer>`;
}

const BASE_CSS = `
:root{--ink:#141414;--text:#4A4A4A;--muted:#6B6B6B;--page:#FBF8F6;--card:#FFFFFF;--line:#ECE6E1;--line-2:#E2D8CF;
--field:#DCD3CB;--accent:#B4470F;--ok:#13795B;--ok-ink:#0F5F47;--ok-bg:#E6F4EE;--warm-bg:#FFF1E4;--warm-ink:#8A3409;
--violet:#7B3FE4;--violet-bg:#EEE5FD;--violet-ink:#4A1C99;--grad:linear-gradient(135deg,#FF8A1F 0%,#F2557A 52%,#7B3FE4 100%);
--sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;--serif:"Instrument Serif",Georgia,serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color-scheme:light}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--page);color:var(--ink);
font:16px/1.5 var(--sans);-webkit-font-smoothing:antialiased;overflow-wrap:break-word}
h1,h2,h3,p{margin:0}
a{color:var(--ink)}
a:hover{color:var(--accent)}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
main:focus{outline:none}
[hidden]{display:none !important}
main{flex:1 0 auto;width:100%;max-width:1200px;margin:0 auto;padding:clamp(32px,5vw,64px) clamp(16px,3vw,32px) 80px;
display:flex;flex-direction:column;gap:32px}
.nw{white-space:nowrap}
.vh{position:absolute !important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
.skip{position:absolute;left:16px;top:-80px;z-index:60;padding:12px 16px;border-radius:10px;background:var(--ink);color:#fff;font-weight:600;text-decoration:none}
.skip:focus{top:12px;color:#fff}
.serif{font-family:var(--serif);font-weight:400;letter-spacing:-.015em;line-height:1}
.serif em{font-style:italic;color:var(--accent)}
.site-head{position:sticky;top:0;z-index:30;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;
gap:8px 12px;padding:12px clamp(16px,3vw,40px);background:rgba(251,248,246,.92);-webkit-backdrop-filter:blur(10px);
backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,20,20,.06)}
.brand{display:inline-flex;align-items:center;gap:10px;min-height:44px;color:var(--ink);text-decoration:none;font-weight:600;font-size:18px;letter-spacing:-.01em}
.brand:hover{color:var(--ink)}
.site-nav{display:flex;gap:2px}
.site-nav a{display:flex;align-items:center;min-height:44px;padding:0 14px;color:var(--ink);text-decoration:none;font-size:15px;font-weight:500;
background:linear-gradient(currentColor,currentColor) no-repeat 14px calc(100% - 10px)/0 1.5px}
.site-nav a:hover{color:var(--ink);background-size:calc(100% - 28px) 1.5px}
.site-nav a[aria-current="page"]{font-weight:600;background-size:calc(100% - 28px) 1.5px}
.pill{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 20px;border-radius:999px;background:var(--ink);
color:#fff;text-decoration:none;font-size:15px;font-weight:600;white-space:nowrap}
.pill:hover{background:#000;color:#fff}
@media (max-width:760px){
.site-head{position:static}
.site-nav{order:3;flex-basis:100%;justify-content:space-between;margin:0 -8px}
.site-nav a{padding:0 8px;font-size:14px;background-position:8px calc(100% - 10px)}
.site-nav a:hover,.site-nav a[aria-current="page"]{background-size:calc(100% - 16px) 1.5px}
}
.site-foot{width:100%;max-width:1200px;margin:0 auto;padding:0 clamp(16px,3vw,32px) 40px}
.foot-in{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:4px 16px;border-top:1px solid var(--line-2);padding-top:16px}
.foot-brand{display:inline-flex;align-items:center;gap:8px;min-height:44px;color:var(--ink);font-weight:600;text-decoration:none}
.foot-brand:hover{color:var(--ink)}
.foot-nav{display:flex;flex-wrap:wrap;gap:0 20px;font-size:14px}
.foot-nav a{display:flex;align-items:center;min-height:44px;text-decoration:none}
.foot-nav a[aria-current="page"]{font-weight:600}
.foot-note{margin-top:4px;font-size:13px;color:var(--text)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:48px;padding:0 22px;border:0;border-radius:10px;
background:var(--ink);color:#fff;font:600 16px/1.2 var(--sans);text-decoration:none;cursor:pointer;text-align:center}
.btn:hover{background:#000;color:#fff}
.btn-ghost{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 18px;border-radius:10px;
border:1px solid var(--field);background:rgba(255,255,255,.7);color:var(--ink);font:600 14px/1.2 var(--sans);text-decoration:none;cursor:pointer;text-align:center}
.btn-ghost:hover{border-color:var(--ink);color:var(--ink)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:clamp(18px,2.6vw,26px)}
.chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:10px;font-size:13px;font-weight:600;line-height:1.3}
.chip-new{background:#F1ECE7;color:#3A3A3A}
.chip-work{background:var(--warm-bg);color:var(--warm-ink)}
.chip-you{background:var(--violet-bg);color:var(--violet-ink)}
.chip-done{background:var(--ok-bg);color:var(--ok-ink)}
.chip-stop{background:#fff;color:var(--text);border:1px dashed #A69C93}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex:none}
.eyebrow{font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--accent)}
.lead{font-size:clamp(17px,1.6vw,19px);line-height:1.55;color:var(--text);max-width:640px}
.note{font-size:13px;color:var(--text)}
.sec-head{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 16px}
.sec-head h2{font-size:18px;font-weight:600;letter-spacing:-.01em}
.stack{display:flex;flex-direction:column;gap:24px}
code{font:500 .9em/1.4 var(--mono);background:#F1ECE7;border-radius:6px;padding:1px 6px;color:var(--ink);white-space:nowrap}
@media (max-width:359px){code,.nw{white-space:normal;overflow-wrap:anywhere}}
@keyframes dc-up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes dc-pulse{0%{box-shadow:0 0 0 0 currentColor}70%,100%{box-shadow:0 0 0 7px rgba(255,255,255,0)}}
@keyframes dc-fade{0%,100%{opacity:1}50%{opacity:.45}}
@media (prefers-reduced-motion:no-preference){
.site-head{animation:dc-up .5s cubic-bezier(.2,.8,.2,1) both}
.site-nav a{transition:background-size .25s ease}
.btn,.pill,.btn-ghost{transition:background .2s ease,border-color .2s ease,transform .15s ease}
.btn:active,.pill:active,.btn-ghost:active{transform:scale(.97)}
.rise{animation:dc-up .6s cubic-bezier(.2,.8,.2,1) both}
.rise-2{animation-delay:.08s}.rise-3{animation-delay:.16s}.rise-4{animation-delay:.24s}
.pulse{animation:dc-pulse 1.8s ease-out infinite}
}
`;

function shell({ title, description, current, css, body, script }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<meta name="description" content="${description}">
<meta name="theme-color" content="#FBF8F6">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="${FONTS}">
<style>${BASE_CSS}${css}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
${DEFS}
${header(current)}
<main id="main" tabindex="-1">
${body}
</main>
${footer(current)}
<script>(${script})();</script>
</body>
</html>
`;
}

// ---------------------------------------------------------------------------------------------------------------
// /case and /case/<id>
// ---------------------------------------------------------------------------------------------------------------

const CASE_CSS = `
.find{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:clamp(28px,5vw,64px);align-items:start}
@media (max-width:880px){.find{grid-template-columns:1fr}}
.find-main{display:flex;flex-direction:column;gap:18px}
.find-main h1{font-size:clamp(48px,6.4vw,84px)}
.find-form{display:flex;flex-direction:column;gap:8px;margin-top:8px;max-width:540px}
.find-form label{font-size:14px;font-weight:600}
.field-row{display:flex;flex-wrap:wrap;gap:10px}
.field{flex:1 1 200px;min-width:0;min-height:52px;padding:0 16px;border:1px solid var(--field);border-radius:10px;background:#fff;
color:var(--ink);font:500 18px/1.2 var(--sans);letter-spacing:.02em}
.field::placeholder{color:#756B64}
.field:focus{outline:none;border-color:var(--ink);box-shadow:0 0 0 3px rgba(20,20,20,.12)}
.field[aria-invalid="true"]{border-color:var(--accent)}
.find-form .btn{min-height:52px;flex:0 0 auto}
.hint{font-size:14px;color:var(--text)}
.err{font-size:14px;font-weight:600;color:var(--accent)}
.err:empty{display:none}
.explain h2{font-size:18px;font-weight:600;margin-bottom:14px}
.explain ol{list-style:none;margin:0;padding:0}
.explain li{display:grid;grid-template-columns:32px minmax(0,1fr);gap:2px 14px;padding:14px 0;border-top:1px solid var(--line)}
.explain li:first-child{border-top:0;padding-top:0}
.explain li:last-child{padding-bottom:0}
.num{grid-row:span 2;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;background:var(--page);
border:1px solid var(--line-2);font-size:13px;font-weight:600}
.explain b{font-size:15px;font-weight:600}
.explain p{font-size:14px;line-height:1.5;color:var(--text)}
.case-head{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 24px}
.crumb{font-size:14px;font-weight:500;margin-bottom:10px}
.crumb a{display:inline-flex;align-items:center;gap:6px;min-height:44px;text-decoration:none}
.case-head h1{font-size:clamp(48px,6.4vw,76px)}
.kind{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin-top:14px;font-size:14px;color:var(--text)}
.kind-tag{padding:4px 12px;border-radius:999px;border:1px solid var(--line-2);background:#fff;font-size:13px;font-weight:600;color:var(--ink)}
.updated{font-size:13px;color:var(--text);max-width:360px}
.state{display:flex;flex-direction:column;align-items:flex-start;gap:14px}
.state .skel{display:block;width:100%;height:14px;border-radius:7px;background:#EFE9E3}
.state .skel:nth-child(3){width:72%}.state .skel:nth-child(4){width:48%}
.status{display:flex;flex-direction:column;gap:28px}
.status-top{display:flex;flex-direction:column;align-items:flex-start;gap:10px;max-width:780px}
.status-title{font-size:clamp(22px,2.4vw,28px);font-weight:600;letter-spacing:-.02em;line-height:1.2}
.status-sub{font-size:16px;line-height:1.55;color:var(--text)}
.stepper{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr))}
.stepper li{position:relative;display:flex;flex-direction:column;align-items:center;gap:8px;padding:0 6px;text-align:center}
.stepper li::after{content:"";position:absolute;top:15px;left:calc(50% + 22px);right:calc(-50% + 22px);height:2px;border-radius:2px;background:var(--line-2)}
.stepper li:last-child::after{display:none}
.stepper li.done::after{background:var(--ok)}
.sd{position:relative;z-index:1;flex:none;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:600;
background:#fff;border:1.5px solid var(--field);color:var(--muted)}
.done .sd{background:var(--ok);border-color:var(--ok);color:#fff}
.now .sd{background:var(--ink);border-color:var(--ink);color:#fff}
.wait .sd{background:var(--violet-bg);border:2px solid var(--violet);color:var(--violet-ink)}
.stop .sd{background:#fff;border:2px dashed var(--text);color:var(--text)}
.st{display:flex;flex-direction:column;gap:2px;min-width:0}
.sl{font-size:14px;font-weight:600}
.todo .sl{font-weight:500;color:var(--muted)}
.ss{font-size:12.5px;line-height:1.35;color:var(--text)}
.wait .ss{color:var(--violet-ink);font-weight:600}
@media (max-width:719px){
.stepper{grid-template-columns:1fr}
.stepper li{flex-direction:row;align-items:flex-start;gap:14px;padding:0 0 16px;text-align:left}
.stepper li:last-child{padding-bottom:0}
.stepper li::after{top:36px;bottom:4px;left:15px;right:auto;width:2px;height:auto}
.st{padding-top:5px}
}
.callout{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;border-radius:12px}
.callout-text{display:flex;flex-direction:column;gap:4px;flex:1 1 360px;min-width:0}
.callout h3{font-size:16px;font-weight:600}
.callout p{font-size:15px;line-height:1.55}
.callout-you{background:#F4EEFF;border:1px solid #D9C7FA;color:#2E1066}
.callout-done{background:var(--ok-bg);border:1px solid #BFE3D2;color:#0F3D2E}
.callout-stop{background:#fff;border:1px dashed #A69C93;color:var(--ink)}
.lab-sum{font-size:15px;color:var(--text);margin:6px 0 14px}
.labels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:10px}
.lab{display:flex;flex-direction:column;gap:6px;padding:14px 16px;border-radius:12px}
.lab-top{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.lab-name{font-size:14px;font-weight:600}
.lab-n{font-size:28px;font-weight:600;letter-spacing:-.02em;line-height:1.05;font-variant-numeric:tabular-nums}
.lab-note{font-size:13px;line-height:1.45}
.l-rec{background:#E6F4EE;border:1px solid #BFE3D2;color:#0F5F47}
.l-rt{background:#FFF1E4;border:1px solid #F6CDA8;color:#8A3409}
.l-ru{background:#F4EEFF;border:1px solid #D9C7FA;color:#5B2BB0}
.l-un{background:#fff;border:1px dashed #A69C93;color:#4A4A4A}
.cols{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:24px;align-items:start}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
.feed-card{display:flex;flex-direction:column;gap:14px;align-items:stretch}
.feed{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.feed li{display:grid;grid-template-columns:88px minmax(0,1fr);gap:2px 12px;padding:12px 14px;border-radius:12px;background:var(--page)}
.feed li:first-child{background:#FFF6EE}
.feed li:focus{outline:2px solid var(--ink);outline-offset:2px}
.feed time{font-size:13px;line-height:1.5;color:var(--text);font-variant-numeric:tabular-nums}
.who{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;font-size:14px;font-weight:600}
.msg{font-size:14px;line-height:1.5;color:#2A2A2A}
.feed .empty{display:block;color:var(--text);font-size:14px}
@media (max-width:480px){.feed li{grid-template-columns:minmax(0,1fr)}}
.tag{padding:1px 8px;border-radius:10px;font-size:11.5px;font-weight:600;line-height:1.5}
.tag-person{background:var(--violet-bg);color:var(--violet-ink)}
#more{align-self:flex-start}
.side{display:flex;flex-direction:column;gap:16px}
.side .card{display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:20px}
.side h2{font-size:15px;font-weight:600}
.big{font-size:34px;font-weight:600;letter-spacing:-.03em;line-height:1.1;font-variant-numeric:tabular-nums}
.big.small{font-size:22px;letter-spacing:-.01em}
.hlist{list-style:none;margin:4px 0 0;padding:0;display:flex;flex-direction:column;gap:6px;font-size:14px;line-height:1.45;width:100%}
.hlist li{display:flex;flex-direction:column;padding-top:6px;border-top:1px solid var(--line)}
.hlist time{font-size:12.5px;color:var(--text)}
.facts{margin:4px 0 0;display:flex;flex-direction:column;width:100%}
.facts div{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:9px 0;border-top:1px solid var(--line);font-size:14px}
.facts div:first-child{border-top:0;padding-top:0}
.facts dt{color:var(--text)}
.facts dd{margin:0;font-weight:600;text-align:right}
.side .btn-ghost{margin-top:4px}
@keyframes dc-ring{0%{box-shadow:0 0 0 0 rgba(20,20,20,.3)}70%,100%{box-shadow:0 0 0 8px rgba(20,20,20,0)}}
@media (prefers-reduced-motion:no-preference){
.state .skel{animation:dc-fade 1.4s ease-in-out infinite}
.now .sd{animation:dc-ring 1.8s ease-out infinite}
}
`;

const STEP_HELP = [
  ["Request", "You tell us what was lost and approve the quote by replying APPROVE."],
  ["Investigate", "Forensics checks every file with static checks. Nothing you send is run."],
  ["Recover", "Context finds the data that survived in your files."],
  ["Reconstruct", "Reconstruction restores what that data supports. If a piece is missing, we ask you."],
  ["Validate", "Validation checks the result against values held back from the agent that restored it."],
  ["Delivered", "We email your report. Every item in it carries one of four labels."],
];

const CASE_BODY = `
<section id="v-find" class="find" aria-labelledby="find-h" hidden>
  <div class="find-main rise">
    <p class="eyebrow">Case tracking</p>
    <h1 id="find-h" class="serif">Track your <em>case.</em></h1>
    <p class="lead">Enter the case number from our emails to see where your recovery stands. The page updates on its own.</p>
    <form id="find-form" class="find-form" action="/case" method="get" novalidate>
      <label for="case-input">Case number</label>
      <div class="field-row">
        <input id="case-input" class="field" name="id" type="text" autocomplete="off" autocapitalize="characters" spellcheck="false"
          placeholder="C-0006" maxlength="40" aria-describedby="case-hint case-err" required>
        <button class="btn" type="submit">Track case ${icon(ARROW)}</button>
      </div>
      <p id="case-hint" class="hint">It looks like C-0006.</p>
      <p id="case-err" class="err" role="alert"></p>
    </form>
  </div>
  <section class="card explain rise rise-2" aria-labelledby="explain-h">
    <h2 id="explain-h">What each step means</h2>
    <ol>
${STEP_HELP.map(([name, text], i) => `      <li><span class="num" aria-hidden="true">${i + 1}</span><b>${name}</b><p>${text}</p></li>`).join("\n")}
    </ol>
  </section>
</section>

<div id="v-case" class="stack" hidden>
  <div class="case-head rise">
    <div>
      <p class="crumb"><a href="/case">${icon(BACK, 16)}Track another case</a></p>
      <h1 class="serif">Case <span data-id></span></h1>
      <p class="kind" id="kind-line" hidden><span class="kind-tag" id="kind"></span><span id="changed"></span></p>
    </div>
    <p class="updated" id="updated"></p>
  </div>

  <section id="c-load" class="card state" role="status">
    <p class="status-title">Loading case <span data-id></span>&hellip;</p>
    <span class="skel" aria-hidden="true"></span><span class="skel" aria-hidden="true"></span><span class="skel" aria-hidden="true"></span>
  </section>

  <section id="c-error" class="card state" role="alert" aria-labelledby="err-h" hidden>
    <h2 id="err-h" class="status-title">We can't load this case right now.</h2>
    <p class="status-sub">Check your connection. This page tries again every 20 seconds.</p>
    <button type="button" class="btn" id="retry">Try again</button>
  </section>

  <div id="c-body" class="stack" hidden>
    <section class="card status rise rise-2" aria-labelledby="st-h">
      <div class="status-top">
        <span class="chip" id="chip"><span class="dot" id="chip-dot"></span><span id="chip-text"></span></span>
        <h2 id="st-h" class="status-title"></h2>
        <p id="st-sub" class="status-sub"></p>
      </div>
      <ol class="stepper" id="stepper" aria-label="Progress"></ol>
      <div id="callout" hidden></div>
    </section>

    <section class="card rise rise-3" aria-labelledby="lab-h">
      <div class="sec-head"><h2 id="lab-h">Every item, labeled</h2><p class="note">Missing facts are flagged, never invented.</p></div>
      <p id="lab-sum" class="lab-sum"></p>
      <div class="labels" id="labels"></div>
    </section>

    <div class="cols rise rise-4">
      <section class="card feed-card" aria-labelledby="feed-h">
        <div class="sec-head"><h2 id="feed-h">Latest steps</h2><p class="note" id="feed-n"></p></div>
        <ol class="feed" id="feed"></ol>
        <button type="button" class="btn-ghost" id="more" aria-controls="feed" hidden>Show all steps</button>
      </section>
      <aside class="side" aria-label="Case details">
        <section class="card" aria-labelledby="q-h">
          <h2 id="q-h">Quote</h2>
          <p class="big" id="quote"></p>
          <p class="note" id="quote-note"></p>
        </section>
        <section class="card" aria-labelledby="h-h">
          <h2 id="h-h">Humans stepped in</h2>
          <p class="big" id="humans"></p>
          <p class="note" id="humans-note"></p>
          <ul class="hlist" id="humans-list" hidden></ul>
        </section>
        <section class="card" aria-labelledby="w-h">
          <h2 id="w-h">Work so far</h2>
          <dl class="facts" id="facts"></dl>
        </section>
        <section class="card" id="files-card" aria-labelledby="f-h">
          <h2 id="f-h">Sending more files?</h2>
          <p class="note">Use the Data Care Collector on a Mac, or reply to our email and attach them.</p>
          <a class="btn-ghost" id="dl-link" href="/download">Get the collector</a>
        </section>
      </aside>
    </div>
  </div>
  <p id="live" class="vh" aria-live="polite"></p>
</div>
`;

// Runs in the browser (injected with Function.prototype.toString): it may only use what it defines itself.
function caseApp() {
  "use strict";
  const POLL_MS = 20000;
  const EMAIL = "datacare-recover@agentmail.to";
  const STEPS = ["Request", "Investigate", "Recover", "Reconstruct", "Validate", "Delivered"];
  const STAGE_STEP = { intake: 0, forensics: 1, context: 2, reconstruction: 3, waiting_client: 3, validation: 4, approval: 4, delivered: 5 };
  const STAGE_TEXT = { intake: "Request received", forensics: "Checking your files", context: "Finding surviving data",
    reconstruction: "Restoring", waiting_client: "Asked you for a missing piece", validation: "Checking the result",
    approval: "Final approval", delivered: "Report delivered", unresolved: "Marked unresolved", mail: "Searching shared mail" };
  const LABELS = [
    ["recovered", "Recovered", "l-rec", "Taken directly from your files or replies."],
    ["reconstructed and tested", "Reconstructed and tested", "l-rt", "Restored from your data, then checked against known results."],
    ["reconstructed but untested", "Reconstructed but untested", "l-ru", "Restored from your data, with nothing to check it against."],
    ["unresolved", "Unresolved", "l-un", "Not found in your data. The report lists where we looked."],
  ];
  const KINDS = { excel: "Excel model", code: "Code", checkup: "Code checkup", other: "Other files" };
  const AGENTS = { "recovery-manager": "Recovery Manager", forensics: "Forensics", context: "Context",
    reconstruction: "Reconstruction", validation: "Validation", "mail-scout": "Mail Scout" };
  const CHECK_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  const FEED_FIRST = 8;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const plural = (n, one, many) => n + " " + (n === 1 ? one : many);
  const clock = (d, sec) => d.toLocaleTimeString([], sec ? { hour: "numeric", minute: "2-digit", second: "2-digit" } : { hour: "numeric", minute: "2-digit" });
  const when = (iso) => {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    if (d.toDateString() === new Date().toDateString()) return clock(d);
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + ", " + clock(d);
  };
  const money = (n) => n === 0 ? "Free"
    : "$" + n.toLocaleString("en-US", Number.isInteger(n) ? {} : { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const agentName = (a) => AGENTS[a] || String(a || "Agent").split(/[-_\s]+/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  const listText = (parts) => parts.length < 2 ? parts.join("") : parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1];
  const withMail = (text) => esc(text).replace(EMAIL, '<span class="nw">' + EMAIL + "</span>");

  // "6", "0006", "c6", "c-0006" all mean C-0006; other ids pass through as typed (the API decides).
  function normalize(s) {
    s = String(s == null ? "" : s).trim().toUpperCase().replace(/\s+/g, "");
    if (!s) return "";
    const m = s.match(/^(?:C-?)?(\d{1,4})$/);
    if (m) return "C-" + m[1].padStart(4, "0");
    return /^[A-Z0-9-]{1,40}$/.test(s) ? s : null;
  }

  const input = $("case-input"), err = $("case-err");
  const setErr = (msg) => { err.textContent = msg; input.setAttribute("aria-invalid", msg ? "true" : "false"); };
  const errFor = (v) => v === "" ? "Enter your case number, for example C-0006." : "Use letters, numbers and dashes only, for example C-0006.";
  $("find-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const v = normalize(input.value);
    if (!v) { setErr(errFor(v)); input.focus(); return; }
    location.assign("/case/" + encodeURIComponent(v));
  });
  input.addEventListener("input", () => { if (err.textContent) setErr(""); });
  function showFind(msg, value) {
    $("v-case").hidden = true;
    $("v-find").hidden = false;
    if (value) input.value = value;
    if (msg) setErr(msg);
  }

  // /case/<id>, or /case?id=<id> when the form was sent without JavaScript.
  const segs = location.pathname.split("/").filter(Boolean);
  let raw = segs[0] === "case" && segs.length > 1 ? segs.slice(1).join("/") : "";
  try { raw = decodeURIComponent(raw); } catch (e) { /* keep it as typed */ }
  if (!raw) {
    const q = new URLSearchParams(location.search).get("id");
    const v = q == null ? "" : normalize(q);
    if (v) { location.replace("/case/" + encodeURIComponent(v)); return; }
    showFind(q != null && q.trim() ? errFor(v) : "", q);
    return;
  }
  const id = /^c-\d{4}$/i.test(raw) ? raw.toUpperCase() : raw;
  const dlHref = /^C-\d{4}$/.test(id) ? "/download?case=" + encodeURIComponent(id) : "/download";
  document.title = "Case " + id + " · Data Care";
  document.querySelectorAll("[data-id]").forEach((el) => { el.textContent = id; });
  $("dl-link").href = dlHref;
  $("v-case").hidden = false;

  let data = null, busy = false, lastTry = 0, timer = 0, showAll = false, prevStage = null;

  function statusFor(c) {
    const quoted = c.quote_usd != null;
    const work = (title, sub) => ({ chip: "chip-work", label: "In progress", live: true, title, sub });
    switch (c.stage) {
      case "intake": return quoted
        ? { chip: "chip-you", label: "Waiting for your approval", title: "Your quote is in your inbox.", sub: "Reply APPROVE to our quote email to start the work." }
        : { chip: "chip-new", label: "Received", title: "We received your request.", sub: "We're preparing your quote. It will arrive by email from " + EMAIL + "." };
      case "forensics": return work("Checking your files.", "Forensics is checking every file with static checks. Nothing you sent is run.");
      case "context": return work("Finding what survived.", "Context is looking for the data that survived in your files.");
      case "reconstruction": return work("Restoring what your data supports.", "Reconstruction restores only what your surviving data supports. Anything else is marked unresolved.");
      case "waiting_client": return { chip: "chip-you", label: "Waiting for you", title: "We asked for a missing piece.", sub: "Check your email from " + EMAIL + "." };
      case "validation": return work("Checking the result.", "Validation is checking the result against values held back from the agent that restored it.");
      case "approval": return { chip: "chip-work", label: "Final approval", live: true, title: "Checked. Approving delivery.", sub: "Your report is being approved before we send it." };
      case "delivered": return { chip: "chip-done", label: "Delivered", title: "Your report is ready.", sub: "We emailed it to you from " + EMAIL + "." };
      case "unresolved": return { chip: "chip-stop", label: "Unresolved", title: "We couldn't finish this case on our own.", sub: "A person on our team has been asked to review it." };
      default: return { chip: "chip-new", label: "Open", title: "Your case is open.", sub: "" };
    }
  }

  function counts(items) {
    const n = {};
    for (const it of items || []) n[it.label] = (n[it.label] || 0) + 1;
    return n;
  }

  // For an unresolved case: the furthest step its events reached.
  function reached(c) {
    let best = 0;
    for (const e of c.events || []) {
      const s = STAGE_STEP[e.stage];
      if (s != null && s > best) best = s;
    }
    return Math.min(best, 4);
  }

  function renderStepper(c) {
    let cur = STAGE_STEP[c.stage] != null ? STAGE_STEP[c.stage] : 0, mode = "now";
    if (c.stage === "delivered") cur = STEPS.length;
    else if (c.stage === "unresolved") { cur = reached(c); mode = "stop"; }
    else if (c.stage === "waiting_client" || (c.stage === "intake" && c.quote_usd != null)) mode = "wait";
    $("stepper").innerHTML = STEPS.map((name, i) => {
      let cls = "todo", sub = "", sr = "not started";
      if (i < cur) { cls = "done"; sub = "Done"; sr = "done"; }
      else if (i === cur) {
        cls = mode; sr = "current step";
        sub = c.stage === "waiting_client" ? "We asked for a missing piece"
          : mode === "stop" ? "Stopped here"
          : c.stage === "approval" ? "Final approval"
          : mode === "wait" ? "Waiting for your approval" : "In progress";
      }
      return '<li class="' + cls + '"' + (i === cur ? ' aria-current="step"' : "") + '><span class="sd" aria-hidden="true">' +
        (cls === "done" ? CHECK_SVG : i + 1) + '</span><span class="st"><span class="sl">' + name + '</span>' +
        (sub ? '<span class="ss">' + sub + "</span>" : "") + '<span class="vh">, ' + sr + "</span></span></li>";
    }).join("");
  }

  function renderCallout(c) {
    let html = "";
    if (c.stage === "waiting_client") {
      html = '<div class="callout callout-you"><div class="callout-text"><h3>What we need from you</h3><p>Our email says exactly what is missing. ' +
        "Reply with the file or the figure. If you don't have it, say so and we will mark it unresolved in your report.</p></div>" +
        '<a class="btn" href="' + esc(dlHref) + '">Send files with the collector</a></div>';
    } else if (c.stage === "delivered") {
      const n = counts(c.report_items);
      const parts = LABELS.map((l) => (n[l[0]] || 0) + " " + l[1].toLowerCase());
      const total = LABELS.reduce((s, l) => s + (n[l[0]] || 0), 0);
      const v = (c.verdicts || [])[0];
      const passed = v && (v.outcome || (v.pass ? "pass" : "fail")) === "pass";
      html = '<div class="callout callout-done"><div class="callout-text"><h3>Report summary</h3><p>' +
        (total ? "Your report covers " + plural(total, "item", "items") + ": " + esc(listText(parts)) + "." : "Your report is in your email.") +
        (passed ? " Validation passed." : "") + "</p></div></div>";
    } else if (c.stage === "unresolved") {
      html = '<div class="callout callout-stop"><div class="callout-text"><h3>Questions in the meantime?</h3><p>' +
        withMail("Reply to our email from " + EMAIL + ".") + "</p></div></div>";
    }
    $("callout").innerHTML = html;
    $("callout").hidden = !html;
  }

  function renderLabels(c) {
    const n = counts(c.report_items);
    const total = LABELS.reduce((s, l) => s + (n[l[0]] || 0), 0);
    const done = c.stage === "delivered";
    $("lab-h").textContent = done ? "Your report" : "Every item, labeled";
    $("lab-sum").textContent = total ? plural(total, "item", "items") + (done ? " in your report." : " labeled so far.")
      : "No items labeled yet. They appear here as the work goes on.";
    $("labels").innerHTML = LABELS.map((l) => '<div class="lab ' + l[2] + '"><p class="lab-top"><span class="lab-name">' + l[1] +
      '</span><span class="lab-n">' + (n[l[0]] || 0) + '</span></p><p class="lab-note">' + l[3] + "</p></div>").join("");
  }

  function renderFeed(events) {
    const list = showAll ? events : events.slice(0, FEED_FIRST);
    $("feed").innerHTML = list.length ? list.map((e) => '<li><time datetime="' + esc(e.created_at) + '">' + esc(when(e.created_at)) +
      '</time><div><p class="who">' + esc(agentName(e.agent)) + (e.human_stepped_in ? '<span class="tag tag-person">Person</span>' : "") +
      '</p><p class="msg">' + esc(e.message || STAGE_TEXT[e.stage] || e.stage) + "</p></div></li>").join("")
      : '<li class="empty">No steps yet. They appear here as agents work.</li>';
    $("more").hidden = showAll || events.length <= FEED_FIRST;
    $("feed-n").textContent = !events.length ? "" : events.length >= 30 ? "Latest 30 steps" : plural(events.length, "step", "steps");
  }

  function verdictText(v) {
    if (!v) return "Not run yet";
    const o = v.outcome || (v.pass ? "pass" : "fail");
    return { pass: "Passed", fail: "Mismatches found", untested: "Nothing to test against", error: "Could not run" }[o] || o;
  }

  function renderSide(c) {
    const q = c.quote_usd;
    $("quote").textContent = q == null ? "Not quoted yet" : money(q);
    $("quote").classList.toggle("small", q == null);
    $("quote-note").innerHTML = withMail(q == null ? "Your quote will arrive by email from " + EMAIL + "."
      : c.stage === "intake" ? "Reply APPROVE to our quote email to start." : "Approved by email.");
    const events = c.events || [];
    const humans = events.filter((e) => e.human_stepped_in);
    $("humans").textContent = String(humans.length);
    $("humans-note").textContent = humans.length === 1 ? "A person on our team stepped in once."
      : humans.length ? "A person on our team stepped in " + humans.length + " times."
      : events.length ? "None. Agents did every step so far." : "None so far.";
    $("humans-list").innerHTML = humans.slice(0, 5).map((e) => '<li><time datetime="' + esc(e.created_at) + '">' + esc(when(e.created_at)) +
      "</time><span>" + esc(e.message || agentName(e.agent)) + "</span></li>").join("");
    $("humans-list").hidden = !humans.length;
    const k = c.counts || {};
    const rows = [["Evidence found", plural(k.fragments || 0, "piece", "pieces")], ["Rules found", String(k.rules || 0)],
      ["Missing pieces flagged", String(k.gaps || 0)], ["Latest check", verdictText((c.verdicts || [])[0])]];
    if (c.retry_count) rows.push(["Retries", String(c.retry_count)]);
    $("facts").innerHTML = rows.map((r) => "<div><dt>" + r[0] + "</dt><dd>" + esc(r[1]) + "</dd></div>").join("");
    $("files-card").hidden = c.stage === "delivered";
  }

  function render(c) {
    const s = statusFor(c);
    $("c-load").hidden = true;
    $("c-error").hidden = true;
    $("c-body").hidden = false;
    $("kind").textContent = KINDS[c.kind] || c.kind || "Case";
    $("changed").textContent = c.updated_at ? "Last change " + when(c.updated_at) : "";
    $("kind-line").hidden = false;
    $("chip").className = "chip " + s.chip;
    $("chip-dot").className = "dot" + (s.live ? " pulse" : "");
    $("chip-text").textContent = s.label;
    $("st-h").textContent = s.title;
    $("st-sub").innerHTML = withMail(s.sub);
    renderStepper(c);
    renderCallout(c);
    renderLabels(c);
    renderFeed(c.events || []);
    renderSide(c);
    if (prevStage && prevStage !== c.stage) $("live").textContent = "Case " + id + " update: " + s.title;
    prevStage = c.stage;
  }

  function notFound() {
    clearInterval(timer);
    timer = 0;
    document.title = "Case not found · Data Care";
    showFind("We couldn't find case " + id + ". Check the number in our emails and try again.", id);
  }

  function failed() {
    if (!data) {
      $("c-load").hidden = true;
      $("c-error").hidden = false;
    }
    $("updated").textContent = "Couldn't refresh at " + clock(new Date()) + ". Trying again in 20 seconds.";
  }

  async function load() {
    if (busy) return;
    busy = true;
    lastTry = Date.now();
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 15000);
    try {
      const r = await fetch("/api/board/case/" + encodeURIComponent(id), { cache: "no-store", signal: ctrl.signal, headers: { accept: "application/json" } });
      if (r.status === 404) { notFound(); return; }
      if (!r.ok) throw new Error("HTTP " + r.status);
      const c = await r.json();
      if (!c || typeof c !== "object" || !c.case_id) throw new Error("unexpected answer");
      data = c;
      render(c);
      $("updated").textContent = "Updated " + clock(new Date(), true) + ". Refreshes every 20 seconds.";
    } catch (e) {
      failed();
    } finally {
      clearTimeout(t);
      busy = false;
    }
  }

  $("retry").addEventListener("click", () => {
    $("c-error").hidden = true;
    $("c-load").hidden = false;
    load();
  });
  $("more").addEventListener("click", () => {
    showAll = true;
    renderFeed((data && data.events) || []);
    const next = $("feed").children[FEED_FIRST];
    if (next) { next.tabIndex = -1; next.focus(); }
  });

  load();
  timer = setInterval(() => { if (document.visibilityState === "visible") load(); }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (timer && document.visibilityState === "visible" && Date.now() - lastTry >= POLL_MS) load();
  });
}

export const CASE_HTML = shell({
  title: "Track your case · Data Care",
  description: "Track a Data Care recovery case: where it stands, the latest steps our agents took, and how every item in your report is labeled.",
  current: "/case",
  css: CASE_CSS,
  body: CASE_BODY,
  script: caseApp,
});

// ---------------------------------------------------------------------------------------------------------------
// /download
// ---------------------------------------------------------------------------------------------------------------

const DOWNLOAD_CSS = `
main{gap:clamp(48px,6vw,72px)}
.dl-hero{display:flex;flex-direction:column;align-items:center;gap:18px;max-width:760px;margin:0 auto;text-align:center}
.appicon{width:120px;height:120px;border-radius:28px;background:var(--grad);display:grid;place-items:center}
.dl-hero h1{font-size:clamp(48px,6.4vw,84px)}
.dl-hero .lead{max-width:600px}
.btn-lg{min-height:56px;padding:0 28px;font-size:17px;margin-top:6px}
.dl-meta{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;justify-content:center;gap:2px 16px;font-size:13px;color:var(--text)}
.dl-meta li{display:flex;align-items:center;gap:8px}
.dl-meta li::before{content:"";width:4px;height:4px;border-radius:50%;background:#A69C93}
.dl-case{font-size:14px;color:var(--text)}
.sec-title{font-size:clamp(34px,4vw,52px);margin-bottom:20px}
.dl-steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr));gap:16px}
.dl-steps li{display:flex;flex-direction:column;gap:10px}
.dl-steps .n{font-size:13px;font-weight:600;color:var(--accent)}
.dl-steps h3{font-size:18px;font-weight:600;letter-spacing:-.01em}
.dl-steps p{font-size:15px;line-height:1.55;color:var(--text)}
.open{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.6fr);gap:clamp(20px,4vw,56px);align-items:start}
@media (max-width:860px){.open{grid-template-columns:1fr}}
.open .sec-title{margin-bottom:12px}
.open .lead{font-size:16px}
.howto{margin:0;padding:0 0 0 22px;display:flex;flex-direction:column;gap:12px;font-size:15px;line-height:1.55;color:var(--text)}
.howto li{padding-left:4px}
.howto li::marker{color:var(--accent);font-weight:600}
.howto b{color:var(--ink);font-weight:600}
.path{display:inline-flex;flex-wrap:wrap;align-items:center;gap:2px 6px;color:var(--ink);font-weight:600}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(360px,100%),1fr));gap:16px}
.two .card{display:flex;flex-direction:column;gap:14px}
.two h2{font-size:20px;font-weight:600;letter-spacing:-.01em}
.xlist{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:12px;font-size:15px;line-height:1.5;color:var(--text)}
.xlist li{display:flex;gap:10px}
.xlist svg{flex:none;margin-top:3px}
.xlist b{color:var(--ink);font-weight:600}
.safe{background:var(--ok-bg);border-color:#BFE3D2;color:#0F3D2E}
.safe .xlist{color:#0F3D2E}
.safe .xlist b{color:#0F3D2E}
.safe p{font-size:15px;line-height:1.55}
.alt{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px}
.alt h2{font-size:20px;font-weight:600;margin-bottom:4px}
.alt p{font-size:15px;color:var(--text);overflow-wrap:anywhere}
@keyframes dc-icon{0%{opacity:0;transform:scale(.6) rotate(-10deg)}70%{opacity:1;transform:scale(1.04) rotate(2deg)}100%{transform:none}}
@media (prefers-reduced-motion:no-preference){
.appicon{animation:dc-icon .9s cubic-bezier(.2,.8,.2,1) .1s both}
.btn-lg svg{transition:transform .2s ease}
.btn-lg:hover svg{transform:translateY(2px)}
}
`;

const DOWNLOAD_BODY = `
<section class="dl-hero" aria-labelledby="dl-h">
  <div class="appicon" aria-hidden="true"><svg width="76" height="76" viewBox="-72 -72 144 144" focusable="false"><use href="#dc-mark" fill="#fff"/></svg></div>
  <p class="chip chip-new" id="case-chip" hidden><span>Case <span data-case></span></span></p>
  <h1 id="dl-h" class="serif rise">Download the <em>collector.</em></h1>
  <p class="lead rise rise-2">A small Mac tool that puts the files your recovery case needs into one zip. You email the zip to us.</p>
  <a class="btn btn-lg rise rise-3" id="dl" href="/download/datacare-collect.zip" download>${icon(DOWN, 20)}Download for Mac</a>
  <ul class="dl-meta rise rise-3" aria-label="About the collector"><li>For macOS</li><li>No install</li><li>Nothing keeps running</li><li>Works offline</li></ul>
  <p class="dl-case" id="case-note" hidden>This download holds case <b data-case></b>, so the collector won't ask for it.</p>
</section>

<section aria-labelledby="does-h">
  <h2 id="does-h" class="serif sec-title">What it does</h2>
  <ol class="dl-steps">
    <li class="card"><span class="n">1</span><h3>Asks for your case</h3><p id="does-1">It asks for your case number, unless its file name already holds it, and what was lost (optional).</p></li>
    <li class="card"><span class="n">2</span><h3>You pick the folders</h3><p>You choose the folders to share. Nothing outside them is read.</p></li>
    <li class="card"><span class="n">3</span><h3>You see the list</h3><p>It shows what it will share. Show list opens the full list. Cancel stops.</p></li>
    <li class="card"><span class="n">4</span><h3>It saves one zip</h3><p>Create bundle saves <code>DataCare-&lt;case&gt;.zip</code> on your Desktop.</p></li>
  </ol>
</section>

<section class="open" aria-labelledby="open-h">
  <div>
    <h2 id="open-h" class="serif sec-title">How to open it on macOS</h2>
    <p class="lead">The collector is a script that runs in Terminal. macOS asks before it opens a file from the internet.</p>
  </div>
  <div class="card">
    <ol class="howto">
      <li>If your browser didn't unzip the download, double-click <code data-zip>datacare-collect.zip</code> in Downloads.</li>
      <li>Double-click <code data-cmd>datacare-collect.command</code>.</li>
      <li>If macOS says it can't verify the developer, right-click the file and choose <b>Open</b>.</li>
      <li>On macOS 15 or later, go to <span class="path">System Settings <span aria-hidden="true">&gt;</span><span class="vh">then</span> Privacy &amp; Security</span> and click <b>Open Anyway</b>.</li>
      <li>If asked whether Terminal may open a folder, click <b>OK</b>.</li>
    </ol>
  </div>
</section>

<div class="two">
  <section class="card" aria-labelledby="never-h">
    <h2 id="never-h">What it never touches</h2>
    <ul class="xlist">
      <li>${icon(CROSS, 18, 2.4, "#B4470F")}<span><b>Keys and passwords.</b> SSH and cloud keys, password managers, keychains, browser logins and cookies are never opened or named.</span></li>
      <li>${icon(CROSS, 18, 2.4, "#B4470F")}<span><b>Hidden files, app data and caches.</b> They are skipped.</span></li>
      <li>${icon(CROSS, 18, 2.4, "#B4470F")}<span><b>Files over 50 MB.</b> They are skipped.</span></li>
      <li>${icon(CROSS, 18, 2.4, "#B4470F")}<span><b>Settings in your code projects.</b> They never run. Projects are shared as a copy of their git history.</span></li>
    </ul>
  </section>
  <section class="card safe" aria-labelledby="up-h">
    <h2 id="up-h">Nothing is uploaded</h2>
    <ul class="xlist">
      <li>${icon(CHECK, 18, 2.6, "#13795B")}<span><b>It never goes online.</b> No upload, no account.</span></li>
      <li>${icon(CHECK, 18, 2.6, "#13795B")}<span><b>It installs nothing.</b> Nothing keeps running after it closes.</span></li>
      <li>${icon(CHECK, 18, 2.6, "#13795B")}<span><b>It works on copies.</b> Your originals stay as they are.</span></li>
      <li>${icon(CHECK, 18, 2.6, "#13795B")}<span><b>You send the zip.</b> Reply to our email and attach it.</span></li>
    </ul>
  </section>
</div>

<section class="card alt" aria-labelledby="alt-h">
  <div>
    <h2 id="alt-h">Rather not run it?</h2>
    <p>Reply to our email from <b class="nw">${EMAIL}</b> and attach the files yourself.</p>
  </div>
  <a class="btn-ghost" id="track" href="/case">Track your case</a>
</section>
`;

// Runs in the browser. With ?case=C-0006 the download carries the case number in its file name.
function downloadApp() {
  "use strict";
  const raw = new URLSearchParams(location.search).get("case");
  const id = raw ? raw.trim().toUpperCase() : "";
  if (!/^C-\d{4}$/.test(id)) return;
  const each = (sel, fn) => document.querySelectorAll(sel).forEach(fn);
  each("[data-case]", (el) => { el.textContent = id; });
  each("[data-zip]", (el) => { el.textContent = "datacare-collect-" + id + ".zip"; });
  each("[data-cmd]", (el) => { el.textContent = "datacare-collect-" + id + ".command"; });
  document.getElementById("dl").href = "/download/datacare-collect.zip?case=" + encodeURIComponent(id);
  document.getElementById("does-1").textContent = "Your download already holds case " + id + ", so it only asks what was lost (optional).";
  const track = document.getElementById("track");
  track.href = "/case/" + encodeURIComponent(id);
  track.textContent = "Track case " + id;
  document.getElementById("case-chip").hidden = false;
  document.getElementById("case-note").hidden = false;
  document.title = "Download the collector for case " + id + " · Data Care";
}

export const DOWNLOAD_HTML = shell({
  title: "Download the collector · Data Care",
  description: "The Data Care Collector for Mac puts the files your recovery case needs into one zip on your Desktop. It never goes online; you email the zip to us.",
  current: "/download",
  css: DOWNLOAD_CSS,
  body: DOWNLOAD_BODY,
  script: downloadApp,
});

// ---------------------------------------------------------------------------------------------------------------
// /download/datacare-collect.zip: the collector in a zip, stored (no compression), marked executable for macOS.
// ---------------------------------------------------------------------------------------------------------------

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const ZIP_TIME = 9 << 11;                               // 09:00:00, MS-DOS format; fixed so the zip is reproducible
const ZIP_DATE = ((2026 - 1980) << 9) | (11 << 5) | 8;  // 2026-11-08
const MADE_BY_UNIX = (3 << 8) | 20;                     // host 3 (Unix), spec 2.0: unzippers then read the mode below
const NEEDED = 10;                                      // 1.0 is enough for a stored file
const MODE_EXEC = ((0o100755 << 16) >>> 0);             // regular file, rwxr-xr-x, in the high 16 bits
let payload;

// One entry: datacare-collect.command, or datacare-collect-C-0006.command when caseId is a case number (the
// collector reads its case from its own file name).
export function collectorZip(caseId) {
  if (!payload) {
    const data = new TextEncoder().encode(COLLECTOR_COMMAND);
    payload = { data, crc: crc32(data) };
  }
  const { data, crc } = payload;
  const fileName = typeof caseId === "string" && /^C-\d{4}$/.test(caseId) ? `datacare-collect-${caseId}.command` : "datacare-collect.command";
  const name = new TextEncoder().encode(fileName);
  const local = 30 + name.length, central = 46 + name.length;
  const out = new Uint8Array(local + data.length + central + 22);
  const v = new DataView(out.buffer);

  v.setUint32(0, 0x04034b50, true);    // local file header
  v.setUint16(4, NEEDED, true);
  v.setUint16(6, 0, true);             // flags
  v.setUint16(8, 0, true);             // method: stored
  v.setUint16(10, ZIP_TIME, true);
  v.setUint16(12, ZIP_DATE, true);
  v.setUint32(14, crc, true);
  v.setUint32(18, data.length, true);  // compressed size
  v.setUint32(22, data.length, true);  // uncompressed size
  v.setUint16(26, name.length, true);
  v.setUint16(28, 0, true);            // extra field length
  out.set(name, 30);
  out.set(data, local);

  const cd = local + data.length;      // central directory
  v.setUint32(cd, 0x02014b50, true);
  v.setUint16(cd + 4, MADE_BY_UNIX, true);
  v.setUint16(cd + 6, NEEDED, true);
  v.setUint16(cd + 8, 0, true);
  v.setUint16(cd + 10, 0, true);
  v.setUint16(cd + 12, ZIP_TIME, true);
  v.setUint16(cd + 14, ZIP_DATE, true);
  v.setUint32(cd + 16, crc, true);
  v.setUint32(cd + 20, data.length, true);
  v.setUint32(cd + 24, data.length, true);
  v.setUint16(cd + 28, name.length, true);
  v.setUint16(cd + 30, 0, true);       // extra field length
  v.setUint16(cd + 32, 0, true);       // comment length
  v.setUint16(cd + 34, 0, true);       // disk number
  v.setUint16(cd + 36, 0, true);       // internal attributes
  v.setUint32(cd + 38, MODE_EXEC, true);
  v.setUint32(cd + 42, 0, true);       // offset of the local header
  out.set(name, cd + 46);

  const end = cd + central;            // end of central directory
  v.setUint32(end, 0x06054b50, true);
  v.setUint16(end + 4, 0, true);
  v.setUint16(end + 6, 0, true);
  v.setUint16(end + 8, 1, true);
  v.setUint16(end + 10, 1, true);
  v.setUint32(end + 12, central, true);
  v.setUint32(end + 16, cd, true);
  v.setUint16(end + 20, 0, true);
  return out;
}
