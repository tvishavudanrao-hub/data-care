// Data Care brand for customer-facing pages (docs/brand/README.md, Balthazar's design).
// Self-contained: the logo is inlined and fonts fall back to system fonts, so the pages load nothing
// from other sites. Shared by web/tickets (form) and web/connectors (connect + status pages).

export const LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -72 144 144" width="32" height="32" aria-hidden="true" focusable="false"><defs><linearGradient id="dc-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient></defs><path d="M-25.77 -47.62 L-25.98 -47.33 L-26.12 -47.05 L-26.25 -46.67 L-26.30 -46.37 L-26.32 -45.99 L-26.28 -45.68 L-26.21 -45.38 L-26.06 -45.01 L-25.80 -44.62 L-25.55 -44.34 L-24.17 -43.24 L-23.32 -42.45 L-22.84 -41.97 L-21.69 -40.62 L-21.00 -39.68 L-20.63 -39.11 L-20.06 -38.14 L-19.75 -37.54 L-19.26 -36.48 L-18.84 -35.39 L-18.63 -34.75 L-18.32 -33.62 L-18.19 -33.00 L-17.99 -31.84 L-17.87 -30.69 L-17.83 -30.05 L-17.82 -28.88 L-17.85 -28.24 L-17.95 -27.08 L-18.04 -26.44 L-18.26 -25.30 L-18.42 -24.65 L-18.95 -22.95 L-19.39 -21.88 L-19.68 -21.26 L-20.20 -20.26 L-20.55 -19.68 L-21.19 -18.70 L-21.89 -17.78 L-22.33 -17.26 L-23.12 -16.40 L-23.97 -15.60 L-24.48 -15.16 L-25.37 -14.46 L-25.92 -14.07 L-26.91 -13.45 L-27.94 -12.89 L-28.54 -12.60 L-29.62 -12.15 L-30.22 -11.93 L-31.33 -11.59 L-32.47 -11.31 L-33.10 -11.19 L-34.26 -11.03 L-34.93 -10.97 L-36.70 -10.93 L-38.46 -11.06 L-39.72 -11.26 L-41.44 -11.69 L-42.55 -12.05 L-43.18 -12.30 L-44.25 -12.77 L-45.31 -13.33 L-45.86 -13.66 L-46.84 -14.30 L-47.79 -15.03 L-48.61 -15.72 L-49.09 -16.00 L-49.59 -16.16 L-50.15 -16.21 L-50.67 -16.13 L-51.19 -15.93 L-51.58 -15.67 L-51.94 -15.31 L-68.82 5.54 L-69.13 6.03 L-69.29 6.54 L-69.34 6.85 L-69.34 7.16 L-69.25 7.72 L-69.14 8.01 L-68.96 8.34 L-68.71 8.66 L-68.47 8.89 L-43.47 29.14 L-43.11 29.51 L-42.86 29.97 L-42.74 30.47 L-42.73 30.86 L-42.77 31.12 L-42.89 31.49 L-43.01 31.72 L-43.24 32.03 L-43.43 32.21 L-43.86 32.50 L-45.35 33.06 L-46.34 33.51 L-47.28 34.02 L-48.19 34.59 L-49.11 35.26 L-49.95 35.96 L-51.03 37.02 L-51.74 37.84 L-52.39 38.69 L-52.98 39.57 L-53.51 40.51 L-53.79 41.07 L-54.22 42.04 L-54.57 42.98 L-54.88 44.01 L-55.11 45.04 L-55.29 46.12 L-55.39 47.19 L-55.42 48.32 L-55.37 49.39 L-55.26 50.46 L-55.07 51.52 L-54.82 52.56 L-54.50 53.60 L-54.12 54.59 L-53.66 55.57 L-52.91 56.89 L-52.31 57.78 L-51.65 58.65 L-50.93 59.45 L-50.13 60.25 L-49.31 60.95 L-48.46 61.59 L-47.56 62.18 L-46.63 62.71 L-45.64 63.18 L-44.65 63.59 L-43.20 64.04 L-42.14 64.28 L-41.08 64.45 L-40.01 64.55 L-38.88 64.58 L-37.81 64.54 L-36.72 64.42 L-35.68 64.24 L-34.62 63.98 L-33.60 63.66 L-32.20 63.10 L-31.23 62.62 L-30.68 62.31 L-29.79 61.74 L-28.93 61.11 L-28.15 60.46 L-27.38 59.74 L-26.65 58.95 L-26.24 58.47 L-25.35 57.24 L-24.79 56.33 L-24.28 55.37 L-23.81 54.33 L-23.44 53.32 L-23.14 52.29 L-22.90 51.23 L-22.67 49.66 L-22.48 49.18 L-22.26 48.85 L-22.08 48.66 L-21.77 48.43 L-21.55 48.31 L-21.05 48.16 L-20.79 48.13 L-20.40 48.16 L-19.91 48.30 L-19.46 48.58 L5.63 68.89 L6.09 69.15 L6.63 69.31 L7.16 69.34 L7.72 69.25 L8.01 69.14 L8.34 68.96 L8.66 68.71 L8.91 68.45 L25.77 47.62 L26.05 47.19 L26.23 46.76 L26.32 46.21 L26.28 45.68 L26.12 45.15 L25.86 44.69 L25.48 44.28 L24.63 43.62 L23.73 42.84 L23.26 42.40 L22.46 41.55 L21.69 40.63 L21.00 39.68 L20.63 39.11 L20.05 38.11 L19.28 36.51 L18.82 35.32 L18.32 33.62 L17.99 31.88 L17.91 31.21 L17.83 30.05 L17.82 29.41 L17.85 28.25 L17.90 27.61 L18.04 26.44 L18.26 25.30 L18.42 24.65 L18.74 23.56 L18.97 22.92 L19.41 21.84 L19.91 20.79 L20.24 20.20 L20.85 19.21 L21.21 18.68 L21.91 17.75 L22.33 17.26 L23.12 16.40 L23.97 15.60 L24.48 15.16 L25.37 14.46 L25.92 14.07 L26.91 13.45 L27.94 12.89 L28.54 12.60 L29.62 12.15 L30.22 11.93 L31.33 11.59 L31.95 11.43 L33.10 11.19 L34.26 11.03 L34.93 10.97 L36.69 10.93 L38.46 11.06 L39.72 11.26 L41.44 11.69 L42.55 12.05 L43.18 12.30 L44.25 12.77 L45.31 13.33 L45.86 13.66 L46.84 14.30 L47.79 15.03 L48.61 15.72 L49.09 16.00 L49.59 16.16 L50.15 16.21 L50.67 16.13 L51.19 15.93 L51.58 15.67 L51.94 15.31 L68.82 -5.54 L69.13 -6.03 L69.29 -6.54 L69.34 -6.85 L69.34 -7.16 L69.25 -7.72 L69.14 -8.01 L68.96 -8.34 L68.71 -8.66 L68.47 -8.89 L43.47 -29.14 L43.11 -29.51 L42.91 -29.85 L42.82 -30.09 L42.74 -30.47 L42.73 -30.73 L42.77 -31.12 L42.95 -31.61 L43.16 -31.93 L43.33 -32.13 L43.53 -32.29 L43.86 -32.50 L45.42 -33.09 L46.80 -33.75 L47.74 -34.30 L48.63 -34.90 L49.54 -35.60 L50.67 -36.64 L51.45 -37.49 L52.38 -38.68 L52.98 -39.59 L53.55 -40.57 L54.01 -41.54 L54.42 -42.55 L54.75 -43.56 L55.02 -44.61 L55.22 -45.66 L55.39 -47.17 L55.42 -48.26 L55.37 -49.41 L55.19 -50.91 L54.95 -52.06 L54.53 -53.51 L54.12 -54.59 L53.66 -55.57 L52.90 -56.91 L52.26 -57.86 L51.31 -59.04 L50.56 -59.83 L49.71 -60.61 L48.52 -61.55 L47.56 -62.18 L46.61 -62.72 L45.24 -63.36 L44.65 -63.59 L43.63 -63.92 L42.61 -64.18 L41.55 -64.39 L40.55 -64.51 L39.49 -64.58 L38.86 -64.58 L37.79 -64.54 L36.74 -64.42 L35.74 -64.25 L34.70 -64.00 L33.69 -63.69 L32.69 -63.31 L32.11 -63.06 L31.17 -62.58 L30.31 -62.08 L28.97 -61.15 L27.75 -60.10 L26.60 -58.89 L25.61 -57.62 L25.02 -56.73 L24.52 -55.85 L24.05 -54.88 L23.64 -53.89 L23.31 -52.89 L23.14 -52.28 L22.90 -51.23 L22.67 -49.66 L22.48 -49.18 L22.18 -48.76 L21.88 -48.50 L21.66 -48.36 L21.18 -48.18 L20.79 -48.13 L20.53 -48.14 L20.28 -48.18 L19.91 -48.30 L19.46 -48.58 L-5.63 -68.89 L-6.09 -69.15 L-6.54 -69.29 L-7.01 -69.35 L-7.56 -69.29 L-7.93 -69.18 L-8.29 -68.99 L-8.60 -68.77 L-8.89 -68.47Z" fill="url(#dc-g)"/></svg>
`;

export const BRAND_CSS = `
  :root {
    --page:#FBF8F6; --ink:#141414; --body:#4A4A4A; --card:#FFFFFF; --border:#ECE6E1; --accent:#B4470F;
    --ok:#13795B; --ok-bg:#E6F4EE; --err:#B3261E;
    --grad:linear-gradient(135deg,#FF8A1F 0%,#F2557A 52%,#7B3FE4 100%);
    --sans:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;
    --serif:"Instrument Serif",Georgia,"Times New Roman",serif;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--page); color:var(--body); font:400 16px/1.55 var(--sans); }
  .bar { border-bottom:1px solid var(--border); background:var(--page); }
  .bar .in { max-width:640px; margin:0 auto; padding:16px; display:flex; align-items:center; gap:10px; }
  .wordmark { font:600 1.05rem/1 var(--sans); color:var(--ink); letter-spacing:-.01em; text-decoration:none;
    display:flex; align-items:center; gap:10px; }
  main { max-width:640px; margin:0 auto; padding:32px 16px 56px; }
  h1 { font:400 clamp(2rem,6vw,2.6rem)/1.1 var(--serif); color:var(--ink); margin:0 0 12px; letter-spacing:-.01em; }
  h1 em { font-style:italic; }
  .kicker { font:600 .78rem/1 var(--sans); letter-spacing:.08em; text-transform:uppercase; color:var(--accent); margin:0 0 12px; }
  .lead { margin:0 0 24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:24px; }
  label { display:block; font-weight:600; color:var(--ink); margin:16px 0 6px; }
  .hint { font-weight:400; color:var(--body); font-size:.9rem; }
  input, select, textarea { width:100%; padding:11px 12px; font:inherit; color:var(--ink); background:#fff;
    border:1px solid var(--border); border-radius:10px; min-height:44px; }
  input:focus, select:focus, textarea:focus { outline:2px solid var(--accent); outline-offset:1px; border-color:transparent; }
  textarea { min-height:140px; resize:vertical; }
  .btn { display:flex; align-items:center; justify-content:center; width:100%; min-height:48px; margin-top:12px;
    padding:12px 16px; border-radius:10px; border:0; background:var(--ink); color:#fff; font:600 1rem/1.25 var(--sans); text-align:center;
    text-decoration:none; cursor:pointer; }
  .btn.secondary { background:#fff; color:var(--ink); border:1px solid var(--border); }
  .btn[disabled] { opacity:.6; cursor:wait; }
  .soon { opacity:.5; pointer-events:none; }
  .muted { color:var(--body); font-size:.92rem; }
  .ok { color:var(--ok); } .err { color:var(--err); }
  a { color:var(--accent); }
  ul.promises { list-style:none; padding:0; margin:20px 0; display:grid; gap:10px; }
  ul.promises li { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:12px 14px; }
  ul.promises strong { color:var(--ink); }
  .chip { display:inline-block; padding:3px 10px; border-radius:999px; font:600 .8rem/1.4 var(--sans); white-space:nowrap; }
  .chip.recovered { color:#0F5F47; background:#E6F4EE; }
  .chip.tested { color:#8A3409; background:#FFF1E4; }
  .chip.untested { color:#5B2BB0; background:#F4EEFF; }
  .chip.unresolved { color:#4A4A4A; background:transparent; border:1px dashed #9A9A9A; }
  .wrap { overflow-x:auto; } table { width:100%; border-collapse:collapse; font-size:.92rem; }
  th, td { text-align:left; padding:10px 8px; border-bottom:1px solid var(--border); vertical-align:top; overflow-wrap:break-word; }
  th { color:var(--ink); font-weight:600; }
  @media (max-width:560px) {
    table.stack thead { display:none; }
    table.stack, table.stack tbody, table.stack tr, table.stack td { display:block; width:100%; }
    table.stack tr { padding:12px 0; border-bottom:1px solid var(--border); }
    table.stack td { border:0; padding:3px 0; }
    table.stack td[data-k]::before { content:attr(data-k) ": "; color:var(--body); font-size:.85rem; }
  }
  .foot { max-width:640px; margin:0 auto; padding:0 16px 40px; font-size:.85rem; color:var(--body); }
`;

export const HEADER = `<header class="bar"><div class="in"><span class="wordmark">${LOGO_SVG}<span>Data Care</span></span></div></header>`;
export const FOOTER = `<p class="foot">Lost data isn't gone. It's in pieces.</p>`;

/** One of the four result labels as a brand chip. */
export function labelChip(label) {
  const cls = { "recovered": "recovered", "reconstructed and tested": "tested",
    "reconstructed but untested": "untested", "unresolved": "unresolved" }[label] || "unresolved";
  const text = label.charAt(0).toUpperCase() + label.slice(1);
  return `<span class="chip ${cls}">${text}</span>`;
}

export function page(title, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title>
<style>${BRAND_CSS}</style></head><body>${HEADER}<main>${body}</main>${FOOTER}</body></html>`;
}
