// The Data Care home page, served at "/". One self-contained HTML document: inline CSS and
// vanilla JS, and the only external resource is Google Fonts. The request form posts JSON to
// /api/tickets with the same fields as /tickets (see ../tickets/tickets.js validateTicket).
// Animations run only under prefers-reduced-motion: no-preference.
export const HOME_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Care: lost data isn't gone, it's in pieces</title>
<meta name="description" content="Data Care recovers lost business data from what still survives in your files, email and exports. Every result is labeled, and you approve the quote before any work starts.">
<meta property="og:type" content="website">
<meta property="og:title" content="Data Care: lost data isn't gone, it's in pieces">
<meta property="og:description" content="Data Care recovers lost business data from what still survives in your files, email and exports. Every result is labeled, and you approve the quote before any work starts.">
<meta name="theme-color" content="#FBF8F6">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Instrument+Serif:ital@0;1&amp;display=swap" rel="stylesheet">
<script>(function(d){try{if('IntersectionObserver' in window&&window.matchMedia('(prefers-reduced-motion: no-preference)').matches)d.classList.add('dc-anim')}catch(e){}})(document.documentElement)</script>
<style>
:root{color-scheme:light;--ink:#141414;--body:#4A4A4A;--page:#FBF8F6;--line:#ECE6E1;--edge:#E8E0D8;--rule:#E2D8CF;--ctl:#DCD3CB;--accent:#B4470F;--err:#B42318;--serif:'Instrument Serif',Georgia,serif}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif}
a{color:var(--ink)}
button:focus-visible,a:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.dc-page{background:var(--page);overflow-x:clip}
.dc-defs{position:absolute;width:0;height:0;overflow:hidden}
.dc-vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.dc-skip{position:absolute;left:16px;top:-90px;z-index:60;display:flex;align-items:center;min-height:44px;padding:0 18px;border-radius:10px;background:var(--ink);color:#fff;font-weight:600;text-decoration:none}
.dc-skip:focus{top:14px}
.dc-head{position:sticky;top:0;z-index:30;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:14px clamp(16px,3vw,40px);background:rgba(251,248,246,0.92);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid rgba(20,20,20,0.06)}
.dc-brand{display:flex;align-items:center;gap:10px;min-height:44px;color:var(--ink);text-decoration:none;font-weight:600;font-size:18px;letter-spacing:-0.01em}
.dc-navs{display:flex;gap:2px}
.dc-nav{display:flex;align-items:center;min-height:44px;padding:0 14px;color:var(--ink);text-decoration:none;font-size:15px;font-weight:500;background:linear-gradient(currentColor,currentColor) no-repeat 14px calc(100% - 10px)/0 1.5px;transition:background-size 0.25s ease}
.dc-nav:hover{background-size:calc(100% - 28px) 1.5px}
.dc-btn{display:flex;align-items:center;gap:10px;min-height:52px;padding:0 24px;border:0;border-radius:999px;background:var(--ink);color:#fff;text-decoration:none;font:inherit;font-size:16px;font-weight:600;cursor:pointer;transition:background 0.2s ease,transform 0.15s ease}
.dc-btn:hover{background:#000;color:#fff}
.dc-btn svg{flex:none;transition:transform 0.2s ease}
.dc-btn:hover svg{transform:translateX(3px)}
.dc-btn-sm{min-height:44px;padding:0 20px;font-size:15px}
.dc-btn[disabled]{opacity:0.6;cursor:wait}
.dc-btn2{display:flex;align-items:center;min-height:52px;padding:0 22px;border-radius:999px;background:#fff;border:1px solid rgba(20,20,20,0.16);color:var(--ink);text-decoration:none;font-size:16px;font-weight:600;transition:border-color 0.2s ease,transform 0.15s ease}
.dc-btn2:hover{border-color:var(--ink)}
.dc-btn:active,.dc-btn2:active,.dc-pill:active,.dc-chipw:active .dc-chip{transform:scale(0.97)}
.dc-arrow{display:inline-block;transition:transform 0.2s ease}
a:hover .dc-arrow{transform:translateX(4px)}
.dc-more{display:flex;align-items:center;gap:10px;min-height:44px;font-size:16px;font-weight:600;color:var(--ink)}
.dc-stack{position:relative}
.dc-hero{z-index:1;height:clamp(660px,60vw,860px);overflow:hidden;background:var(--page)}
.dc-hero-art{position:absolute;inset:0;transform-origin:50% 40%}
.dc-hero-art svg{position:absolute;inset:0;width:100%;height:100%;display:block}
.dc-hero-copy{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;padding:0 24px;text-align:center}
.dc-hero h1{margin:0;max-width:900px;font-family:var(--serif);font-weight:400;font-size:clamp(44px,5.6vw,84px);line-height:0.98;letter-spacing:-0.015em}
.dc-hero h1 em,.dc-h2 em{color:var(--accent)}
.dc-sub{margin:0;max-width:560px;font-size:19px;line-height:1.5;color:#2A2A2A;text-wrap:balance}
.dc-ctas{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;padding-top:6px}
.dc-sec{border-radius:40px 40px 0 0;border-top:1px solid var(--edge);padding:clamp(56px,8vw,104px) clamp(16px,4vw,64px);display:flex;flex-direction:column;justify-content:center}
.dc-white{background:#fff}
.dc-cream{background:var(--page)}
.dc-wrap{max-width:1200px;width:100%;margin:0 auto}
.dc-col{display:flex;flex-direction:column}
.dc-row{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between}
.dc-h2{margin:0;font-family:var(--serif);font-weight:400;font-size:clamp(40px,5.2vw,76px);line-height:1}
.dc-bal{text-wrap:balance}
.dc-how .dc-wrap{max-width:1100px;gap:clamp(36px,5vw,64px)}
.dc-steps{width:100%;max-width:980px;display:flex;flex-direction:column;gap:30px}
.dc-steps svg{width:100%;height:auto;overflow:visible}
.dc-steps ol{list-style:none;margin:0;padding:0 1.6%;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(190px,100%),1fr));gap:24px}
.dc-steps li{display:flex;flex-direction:column;transition:opacity 0.25s ease}
.dc-steps:has(li:hover) li:not(:hover){opacity:0.55}
.dc-step-t{display:flex;align-items:center;min-height:44px;font-size:20px;font-weight:600;letter-spacing:-0.01em;text-decoration:none;color:var(--ink)}
.dc-step-d{font-size:16px;color:var(--body)}
.dc-sp{transform-box:fill-box;transform-origin:50% 50%}
.dc-recover{padding-left:0;padding-right:0;gap:clamp(32px,5vw,56px)}
.dc-recover-h{padding:0 clamp(16px,4vw,64px);gap:12px 24px}
.dc-mq{overflow:hidden;-webkit-mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent);mask-image:linear-gradient(90deg,transparent,#000 6%,#000 94%,transparent)}
.dc-mq-track{display:flex;gap:20px;width:max-content;padding:8px 0 12px}
.dc-card{flex:none;width:340px;display:flex;flex-direction:column;gap:18px;padding:16px 16px 22px;border-radius:22px;background:#fff;border:1px solid var(--line);color:var(--ink);text-decoration:none;transition:border-color 0.3s ease}
.dc-card:hover{border-color:#D9CFC6;color:var(--ink)}
.dc-art{display:block;width:100%;height:auto;overflow:visible}
.dc-card-t{display:flex;flex-direction:column;gap:6px;padding:0 6px}
.dc-card-h{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.dc-card-n{font-size:22px;font-weight:600;letter-spacing:-0.01em}
.dc-card-p{font-size:15px;font-weight:600;white-space:nowrap}
.dc-card-l{font-size:16px;color:var(--body)}
.dc-demo-sec{padding-top:clamp(56px,7vw,96px);padding-bottom:clamp(56px,7vw,96px)}
.dc-demo-sec .dc-wrap{gap:28px}
.dc-demo-h{gap:16px 24px}
.dc-pills{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.dc-pill{min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--ctl);background:#fff;color:var(--ink);font:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:border-color 0.2s ease,background 0.2s ease,color 0.2s ease,transform 0.15s ease}
.dc-pill:hover{border-color:var(--ink)}
.dc-pill[aria-pressed=true]{border-color:var(--ink);background:var(--ink);color:#fff}
.dc-replay{display:flex;align-items:center;justify-content:center;width:44px;height:44px;padding:0;border-radius:22px}
.dc-demo{border-radius:20px;border:1px solid var(--line);background:var(--page);overflow:hidden}
.dc-demo-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;padding:12px 18px;background:#fff;border-bottom:1px solid var(--line)}
.dc-demo-name{display:flex;align-items:center;gap:10px;min-width:0;font-size:14px;font-weight:600}
.dc-demo-name svg{flex:none}
.dc-demo-name span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dc-status{display:flex;align-items:center;gap:6px;padding:5px 11px;border-radius:8px;font-size:12px;font-weight:600}
.dc-status::before{content:"";width:6px;height:6px;border-radius:3px;background:currentColor}
.dc-prog{height:3px;background:#EFE8E2}
.dc-prog div{height:100%;background:var(--ink)}
.dc-demo-body{display:flex;flex-wrap:wrap}
.dc-sheetbox{flex:3 1 520px;min-width:0;box-sizing:content-box;padding:clamp(12px,2vw,22px);overflow-x:auto}
.dc-sheetbox table{width:100%;border-collapse:separate;border-spacing:6px;font-size:14px;font-variant-numeric:tabular-nums}
.dc-sheetbox thead th{padding:0 12px 4px;text-align:right;font-size:12px;font-weight:600;color:#6B6B6B}
.dc-sheetbox thead th:first-child{width:34%}
.dc-sheetbox tbody th{padding-right:8px;text-align:left;font-size:13px;font-weight:500;color:var(--body);white-space:nowrap}
.dc-sheetbox td{height:40px;padding:0 12px;border-radius:8px;text-align:right;white-space:nowrap;background:#fff;border:1px solid #EFE8E2;color:var(--ink);font-weight:400}
.dc-sheetbox td.c-bad{background:#FFF4EC;border:1.5px dashed #E58A4A;color:var(--accent);font-weight:600}
.dc-sheetbox td.c-fix{border:1.5px solid #F2A46A;font-weight:600}
.dc-sheetbox td.c-hole{background:#FFF4EC;border:1.5px dashed #E58A4A}
.dc-sheetbox td.c-ask{background:#F4EEFF;border:1.5px dashed #8B5CF6;color:#6D35CF;font-weight:600}
.dc-sheetbox td.c-asked{border:1.5px solid #B394F3;font-weight:600}
.dc-feedbox{flex:2 1 340px;min-width:0;min-height:460px;padding:18px;background:#fff;border-left:1px solid var(--line);display:flex;flex-direction:column;gap:12px}
.dc-eyebrow{font-size:12px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#5A5A5A}
.dc-feedbox ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.dc-feedbox li{display:flex;gap:10px;padding:10px 12px;border-radius:10px;background:var(--page);font-size:13.5px;line-height:1.45;color:#2A2A2A}
.dc-feedbox li.is-last{background:#FFF6EE}
.dc-feedbox li.is-future{visibility:hidden}
.dc-feedbox li i{flex:none;width:8px;height:8px;margin-top:6px;border-radius:4px}
.dc-feedbox strong{font-weight:600;color:var(--ink)}
.dc-agents .dc-wrap{gap:clamp(32px,4vw,48px)}
.dc-agents-h{gap:16px 32px}
.dc-lead{margin:0;max-width:440px;font-size:18px;line-height:1.5;color:var(--body)}
.dc-grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:16px}
.dc-agent{display:flex;flex-direction:column;gap:10px;padding:22px;border-radius:20px;background:#fff;border:1px solid var(--line)}
.dc-agent h3{display:flex;align-items:center;gap:10px;margin:0;font-size:18px;font-weight:600;letter-spacing:-0.01em}
.dc-agent h3 i{flex:none;width:10px;height:10px;border-radius:5px}
.dc-agent p{margin:0;font-size:15px;line-height:1.5;color:var(--body)}
.dc-labels{display:flex;flex-wrap:wrap;align-items:center;gap:10px 12px;padding-top:8px;border-top:1px solid var(--rule)}
.dc-labels-t{padding-top:16px;font-size:15px;font-weight:600;margin-right:6px}
.dc-labels ul{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:16px 0 0;list-style:none}
.dc-label{display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border-radius:999px;font-size:14px;font-weight:600}
.dc-l1{background:#E6F4EE;border:1px solid #BFE3D2;color:#0F5F47}
.dc-l2{background:#FFF1E4;border:1px solid #F6CDA8;color:#8A3409}
.dc-l3{background:#F4EEFF;border:1px solid #D9C7FA;color:#5B2BB0}
.dc-l4{background:#fff;border:1px dashed #B9AEA4;color:var(--body)}
.dc-labels-n{width:100%;margin:0;font-size:15px;color:var(--body)}
.dc-miss .dc-wrap{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:48px}
.dc-miss-t{flex:1 1 440px;gap:22px}
.dc-miss-t p{margin:0;font-size:19px;line-height:1.5;color:var(--body)}
.dc-miss-t .dc-more{align-self:flex-start}
.dc-miss-a{flex:1 1 360px;display:flex;justify-content:center}
.dc-miss-a svg{width:min(440px,100%);height:auto;overflow:visible}
.dc-price-sec{justify-content:flex-start;padding-bottom:64px}
.dc-price-sec .dc-wrap{gap:clamp(48px,7vw,88px)}
.dc-nums{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:32px;padding-top:32px;border-top:1px solid var(--rule)}
.dc-nums p{display:flex;flex-direction:column;gap:8px;margin:0}
.dc-num{font-family:var(--serif);font-size:clamp(64px,7vw,104px);line-height:0.9;font-variant-numeric:tabular-nums}
.dc-num-l{font-size:16px;color:var(--body)}
.dc-plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));gap:16px}
.dc-plan{display:flex;flex-direction:column;gap:8px;padding:22px;border-radius:20px;background:var(--page);color:var(--ink);border:1px solid var(--line)}
.dc-plan h3{margin:0;font-size:15px;font-weight:600}
.dc-plan-p{font-family:var(--serif);font-size:44px;line-height:1}
.dc-plan p{margin:0;font-size:15px;line-height:1.5;color:var(--body)}
.dc-plan-dark{background:var(--ink);color:#fff;border-color:var(--ink)}
.dc-plan-dark p{color:#D9D2CB}
.dc-ask{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:32px;scroll-margin-top:96px}
.dc-ask-t{flex:1 1 380px;gap:16px}
.dc-ask-t .dc-h2{font-size:clamp(44px,6vw,92px);line-height:0.95}
.dc-ask-t p{margin:0;max-width:420px;font-size:17px;line-height:1.5;color:var(--body)}
.dc-form{flex:1 1 440px;max-width:560px;padding:clamp(18px,2.4vw,26px);border-radius:20px;background:var(--page);border:1px solid var(--line);display:flex;flex-direction:column;gap:16px}
.dc-fs{margin:0;padding:0;border:0;min-width:0}
.dc-fs legend{float:left;width:100%;margin:0 0 16px;padding:0;font-size:14px;font-weight:600}
.dc-chips{clear:both;display:flex;flex-wrap:wrap;gap:8px}
.dc-chipw{position:relative;display:flex}
.dc-chip{display:flex;align-items:center;min-height:44px;padding:0 16px;border-radius:10px;border:1px solid var(--ctl);background:#fff;color:var(--ink);font-size:14px;font-weight:600;cursor:pointer;transition:border-color 0.2s ease,background 0.2s ease,color 0.2s ease,transform 0.15s ease}
.dc-chipw:hover .dc-chip{border-color:var(--ink)}
.dc-chipw input:checked+.dc-chip{border-color:var(--ink);background:var(--ink);color:#fff}
.dc-chipw input:focus-visible+.dc-chip{outline:2px solid var(--ink);outline-offset:2px}
.dc-two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:16px}
.dc-fg{display:flex;flex-direction:column;gap:6px;min-width:0}
.dc-fg label{font-size:14px;font-weight:600}
.dc-hint{font-weight:400;color:var(--body)}
.dc-field{min-height:48px;width:100%;padding:0 14px;border-radius:10px;border:1px solid var(--ctl);background:#fff;font:inherit;font-size:15px;color:var(--ink);transition:border-color 0.2s ease,box-shadow 0.2s ease}
.dc-field::placeholder{color:#8A8A8A}
.dc-field:focus{outline:none;border-color:var(--ink);box-shadow:0 0 0 3px rgba(20,20,20,0.12)}
.dc-field[aria-invalid=true]{border:1.5px solid var(--err)}
textarea.dc-field{min-height:120px;padding:12px 14px;line-height:1.5;resize:vertical}
select.dc-field{-webkit-appearance:none;appearance:none;padding-right:40px;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23141414' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") no-repeat right 14px center;cursor:pointer}
.dc-ferr{font-size:13px;font-weight:500;color:var(--err)}
.dc-ferr:empty,.dc-msg:empty,.dc-quote-l:empty{display:none}
.dc-hp{position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden}
.dc-check{display:flex;align-items:center;gap:12px;min-height:44px;font-size:15px;cursor:pointer}
.dc-check input{flex:none;width:20px;height:20px;margin:0;accent-color:var(--ink);cursor:pointer}
.dc-check input:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.dc-check input[aria-invalid=true]{outline:2px solid var(--err);outline-offset:2px}
.dc-go{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding-top:2px}
.dc-quote{display:flex;align-items:baseline;gap:8px}
.dc-quote-l{font-size:14px;color:var(--body)}
.dc-quote-p{font-size:30px;font-weight:600;letter-spacing:-0.02em;font-variant-numeric:tabular-nums}
.dc-quote.is-ask .dc-quote-p{font-size:17px;letter-spacing:-0.01em}
.dc-go .dc-btn{padding:0 22px}
.dc-msg{display:flex;align-items:flex-start;gap:10px;padding:14px 16px;border-radius:12px;font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.dc-msg p{margin:0}
.dc-ok{background:#E6F4EE;color:#0F3D2E}
.dc-ok svg{flex:none;margin-top:2px}
.dc-bad{background:#FDEDEB;color:var(--err);font-weight:500}
.dc-foot{position:relative;z-index:8;background:#fff;padding:0 clamp(16px,4vw,64px) 32px}
.dc-foot-in{max-width:1200px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid var(--rule);padding-top:16px;font-size:14px;color:var(--body)}
.dc-foot-b{display:flex;align-items:center;gap:8px;color:var(--ink);font-weight:600}
.dc-foot nav{display:flex;flex-wrap:wrap;gap:4px 20px}
.dc-foot nav a{display:flex;align-items:center;min-height:44px;text-decoration:none}
.dc-foot nav a:hover{color:var(--accent)}
@media (max-width:760px){.dc-hide-sm{display:none!important}}
@media (min-width:900px){
.dc-stack{position:sticky;top:min(0px,calc(100vh - var(--h,860px)))}
.dc-sheet{min-height:860px}
}
@media (max-width:600px){
.dc-sheetbox{padding:12px 8px}
.dc-sheetbox table{border-spacing:3px;font-size:12px}
.dc-sheetbox thead th{padding:0 6px 4px}
.dc-sheetbox thead th:first-child{width:24%}
.dc-sheetbox td{padding:0 5px;height:34px}
.dc-sheetbox tbody th{white-space:normal;font-size:11.5px;line-height:1.25;padding-right:2px}
.dc-field{font-size:16px}
}
@keyframes dc-up{from{opacity:0;transform:translateY(0.6em)}to{opacity:1;transform:none}}
@keyframes dc-tilt{from{opacity:0;transform:translateY(0.5em) rotate(-9deg)}to{opacity:1;transform:none}}
@keyframes dc-fadein{from{opacity:0}to{opacity:1}}
@keyframes dc-settle{from{opacity:0;transform:scale(1.05)}to{opacity:1;transform:none}}
@keyframes dc-ring{from{opacity:0;transform:translate(var(--dx),var(--dy)) rotate(var(--rot))}to{opacity:1;transform:none}}
@keyframes dc-recede{to{transform:scale(0.96);opacity:0.6}}
@keyframes dc-mq{from{transform:translateX(0)}to{transform:translateX(calc(-50% - 10px))}}
@keyframes dc-dropl{0%,6%{opacity:0;transform:translateY(-70px) rotate(-20deg)}20%{opacity:1;transform:none}82%{opacity:1;transform:none}94%,100%{opacity:0;transform:translateY(-10px)}}
@keyframes dc-ants{to{stroke-dashoffset:-32}}
@keyframes dc-fix{0%{background:#FFD3AE;transform:scale(1.08)}100%{transform:none}}
@keyframes dc-askfix{0%{background:#E4D6FF;transform:scale(1.08)}100%{transform:none}}
@keyframes dc-ok{0%{box-shadow:0 0 0 0 rgba(19,121,91,0)}40%{box-shadow:0 0 0 4px rgba(19,121,91,0.3)}100%{box-shadow:0 0 0 0 rgba(19,121,91,0)}}
@keyframes dc-wait{0%,100%{opacity:1}50%{opacity:0.5}}
@keyframes dc-feed{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes dc-live{0%{box-shadow:0 0 0 0 var(--c)}70%{box-shadow:0 0 0 7px rgba(255,255,255,0)}100%{box-shadow:0 0 0 0 rgba(255,255,255,0)}}
@keyframes dc-down{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:no-preference){
html{scroll-behavior:smooth}
.dc-head{animation:dc-fadein 0.7s ease both}
.dc-hero-in{transform-box:view-box;transform-origin:50% 50%;animation:dc-settle 1.4s cubic-bezier(0.2,0.7,0.2,1) both}
.dc-rp{transform-box:fill-box;transform-origin:50% 50%;animation:dc-ring 1s cubic-bezier(0.25,1.1,0.35,1) both;animation-delay:calc(0.2s + var(--d))}
.dc-w{display:inline-block;animation:dc-up 0.9s cubic-bezier(0.2,0.8,0.2,1) both;animation-delay:calc(0.35s + var(--i) * 0.08s)}
.dc-w2{display:inline-block;transform-origin:0 100%;animation:dc-tilt 1s cubic-bezier(0.3,1.3,0.5,1) both;animation-delay:calc(0.35s + var(--i) * 0.08s)}
.dc-sub{animation:dc-up 0.8s cubic-bezier(0.2,0.8,0.2,1) 1s both}
.dc-ctas{animation:dc-up 0.8s cubic-bezier(0.2,0.8,0.2,1) 1.15s both}
.dc-sp{transition:transform 0.35s cubic-bezier(0.3,1.4,0.5,1)}
.dc-steps:has(li:nth-child(1):hover) .dc-sp1,.dc-steps:has(li:nth-child(2):hover) .dc-sp2,.dc-steps:has(li:nth-child(3):hover) .dc-sp3,.dc-steps:has(li:nth-child(4):hover) .dc-sp4{transform:translateY(-10px)}
.dc-card{transition:translate 0.3s cubic-bezier(0.2,0.8,0.2,1),border-color 0.3s ease}
.dc-card:hover{translate:0 -6px}
.dc-mq-track{animation:dc-mq 100s linear infinite}
.dc-mq:hover .dc-mq-track,.dc-mq:focus-within .dc-mq-track{animation-play-state:paused}
.dc-dl{transform-box:fill-box;transform-origin:50% 50%;animation:dc-dropl 7s cubic-bezier(0.3,1.3,0.5,1) infinite;animation-delay:var(--d,0s)}
.dc-ants{animation:dc-ants 1.4s linear infinite}
.dc-prog div{transition:width 0.8s cubic-bezier(0.2,0.8,0.2,1)}
.dc-sheetbox td.dc-fixed{animation:dc-fix 0.7s cubic-bezier(0.2,0.8,0.2,1) both}
.dc-sheetbox td.dc-asking{animation:dc-wait 1.2s ease-in-out infinite}
.dc-sheetbox td.dc-asked{animation:dc-askfix 0.7s cubic-bezier(0.2,0.8,0.2,1) both}
.dc-sheetbox td.dc-okc{animation:dc-ok 1s ease both;animation-delay:var(--cd,0s)}
.dc-feedbox li.dc-new{animation:dc-feed 0.45s cubic-bezier(0.2,0.8,0.2,1) both}
.dc-msg,.dc-ferr{animation:dc-down 0.3s ease both}
.dc-agent h3 i{animation:dc-live 2.4s ease-out infinite;animation-delay:var(--dd,0s)}
.dc-anim .dc-rv{opacity:0;transform:translateY(40px);transition:opacity 0.8s cubic-bezier(0.2,0.8,0.2,1) var(--d,0s),transform 0.9s cubic-bezier(0.2,0.8,0.2,1) var(--d,0s),translate 0.3s ease,border-color 0.3s ease}
.dc-anim .dc-rv.is-in{opacity:1;transform:none}
.dc-anim .dc-fly{transform-box:fill-box;transform-origin:50% 50%;opacity:0;transform:translate(var(--dx),var(--dy)) rotate(var(--rot));transition:transform 1.1s cubic-bezier(0.25,1.15,0.35,1) var(--d,0s),opacity 0.35s ease var(--d,0s)}
.dc-anim .is-in .dc-fly{opacity:1;transform:none}
.dc-anim .dc-cell{opacity:0;transition:opacity 0.3s ease var(--d,0s)}
.dc-anim .is-in .dc-cell{opacity:1}
.dc-anim .dc-bar{transform-box:fill-box;transform-origin:0 50%;transform:scaleX(0);transition:transform 0.6s cubic-bezier(0.2,0.8,0.2,1) var(--d,0s)}
.dc-anim .is-in .dc-bar{transform:none}
.dc-anim .dc-line{stroke-dasharray:220;stroke-dashoffset:220;transition:stroke-dashoffset 0.9s cubic-bezier(0.4,0,0.2,1) var(--d,0s)}
.dc-anim .is-in .dc-line{stroke-dashoffset:0}
.dc-anim .dc-pop{transform-box:fill-box;transform-origin:50% 50%;opacity:0;transform:scale(0.2);transition:transform 0.55s cubic-bezier(0.3,1.6,0.5,1) var(--d,0s),opacity 0.2s ease var(--d,0s)}
.dc-anim .is-in .dc-pop{opacity:1;transform:none}
}
@supports (animation-timeline:scroll()){
@media (prefers-reduced-motion:no-preference) and (min-width:900px){
.dc-hero-art{animation:dc-recede linear both;animation-timeline:scroll();animation-range:0px 860px}
}
}
@media (prefers-reduced-motion:reduce){
.dc-mq{overflow-x:auto}
.dc-mq-track{padding-left:clamp(16px,4vw,64px);padding-right:clamp(16px,4vw,64px)}
.dc-dup{display:none}
}
</style>
</head>
<body>
<div class="dc-page">
<svg class="dc-defs" width="0" height="0" aria-hidden="true" focusable="false">
<defs>
<linearGradient id="dc-g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1920" y2="720"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient>
<linearGradient id="dc-gk" gradientUnits="userSpaceOnUse" x1="90" y1="90" x2="510" y2="510"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient>
<linearGradient id="dc-gs" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="480" y2="120"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.5" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient>
<linearGradient id="dc-logo-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF8A1F"/><stop offset="0.52" stop-color="#F2557A"/><stop offset="1" stop-color="#7B3FE4"/></linearGradient>
<path id="dc-logo" d="M-25.8 -47.6L-26.3 -46.4L-26.1 -45.1L-22.7 -41.8L-20.5 -38.9L-18.9 -35.6L-18.0 -32.1L-17.8 -28.5L-18.6 -24.2L-19.9 -20.8L-21.9 -17.8L-24.4 -15.2L-27.5 -13.1L-31.6 -11.5L-35.2 -11.0L-38.7 -11.1L-41.5 -11.7L-45.5 -13.5L-49.1 -16.0L-50.1 -16.2L-51.2 -15.9L-51.9 -15.3L-68.8 5.5L-69.3 6.5L-69.3 7.7L-68.4 8.9L-43.5 29.1L-42.9 29.9L-42.8 31.0L-43.4 32.2L-48.3 34.6L-51.8 37.9L-53.9 41.2L-55.1 45.0L-55.4 49.2L-54.4 53.8L-52.2 58.0L-49.3 61.0L-45.3 63.3L-41.3 64.4L-36.6 64.4L-32.6 63.3L-29.1 61.3L-26.2 58.5L-23.8 54.3L-22.5 49.2L-21.7 48.4L-20.5 48.1L-19.5 48.6L5.5 68.8L6.5 69.3L7.7 69.3L8.9 68.4L25.8 47.6L26.2 46.8L26.3 45.7L25.9 44.7L22.6 41.7L20.1 38.2L18.9 35.6L18.0 32.1L17.8 28.5L18.6 24.2L19.9 20.8L21.9 17.8L24.5 15.2L27.5 13.1L31.6 11.5L35.2 11.0L38.7 11.1L41.5 11.7L45.5 13.5L49.1 16.0L50.2 16.2L51.2 15.9L51.9 15.3L68.8 -5.5L69.3 -6.5L69.3 -7.7L68.4 -8.9L43.5 -29.1L42.9 -29.9L42.8 -31.0L43.4 -32.2L48.3 -34.6L50.6 -36.6L52.2 -38.5L54.5 -42.7L55.4 -46.8L55.4 -49.2L54.9 -52.2L54.1 -54.5L53.0 -56.7L51.6 -58.7L49.4 -60.9L45.2 -63.4L41.4 -64.4L38.0 -64.6L34.1 -63.8L30.5 -62.2L27.9 -60.2L25.7 -57.8L23.6 -53.7L22.5 -49.2L21.7 -48.4L20.5 -48.1L19.5 -48.6L-5.5 -68.8L-6.5 -69.3L-7.6 -69.3L-8.9 -68.4Z"/>
<path id="dc-pc" d="M240 240L286 240C286 246 280 250 280 258C280 270 320 270 320 258C320 250 314 246 314 240L360 240L360 286C366 286 370 280 378 280C390 280 390 320 378 320C370 320 366 314 360 314L360 360L314 360C314 354 320 350 320 342C320 330 280 330 280 342C280 350 286 354 286 360L240 360L240 314C234 314 230 320 222 320C210 320 210 280 222 280C230 280 234 286 240 286L240 240Z" transform="translate(-300 -300)"/>
<pattern id="dc-seam" width="240" height="240" patternUnits="userSpaceOnUse"><path d="M0 0L46 0C46 6 40 10 40 18C40 30 80 30 80 18C80 10 74 6 74 0L120 0M120 0L166 0C166 -6 160 -10 160 -18C160 -30 200 -30 200 -18C200 -10 194 -6 194 0L240 0M0 120L46 120C46 114 40 110 40 102C40 90 80 90 80 102C80 110 74 114 74 120L120 120M120 120L166 120C166 126 160 130 160 138C160 150 200 150 200 138C200 130 194 126 194 120L240 120M0 240L46 240C46 246 40 250 40 258C40 270 80 270 80 258C80 250 74 246 74 240L120 240M120 240L166 240C166 234 160 230 160 222C160 210 200 210 200 222C200 230 194 234 194 240L240 240M0 0L0 46C-6 46 -10 40 -18 40C-30 40 -30 80 -18 80C-10 80 -6 74 0 74L0 120M0 120L0 166C6 166 10 160 18 160C30 160 30 200 18 200C10 200 6 194 0 194L0 240M120 0L120 46C126 46 130 40 138 40C150 40 150 80 138 80C130 80 126 74 120 74L120 120M120 120L120 166C114 166 110 160 102 160C90 160 90 200 102 200C110 200 114 194 120 194L120 240M240 0L240 46C234 46 230 40 222 40C210 40 210 80 222 80C230 80 234 74 240 74L240 120M240 120L240 166C246 166 250 160 258 160C270 160 270 200 258 200C250 200 246 194 240 194L240 240" fill="none" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></pattern>
<mask id="dc-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="720"><rect width="1920" height="720" fill="#fff"/><path d="M480 0L526 0C526 6 520 10 520 18C520 30 560 30 560 18C560 10 554 6 554 0L600 0L646 0C646 -6 640 -10 640 -18C640 -30 680 -30 680 -18C680 -10 674 -6 674 0L720 0L766 0C766 6 760 10 760 18C760 30 800 30 800 18C800 10 794 6 794 0L840 0L886 0C886 -6 880 -10 880 -18C880 -30 920 -30 920 -18C920 -10 914 -6 914 0L960 0L1006 0C1006 6 1000 10 1000 18C1000 30 1040 30 1040 18C1040 10 1034 6 1034 0L1080 0L1126 0C1126 -6 1120 -10 1120 -18C1120 -30 1160 -30 1160 -18C1160 -10 1154 -6 1154 0L1200 0L1246 0C1246 6 1240 10 1240 18C1240 30 1280 30 1280 18C1280 10 1274 6 1274 0L1320 0L1366 0C1366 -6 1360 -10 1360 -18C1360 -30 1400 -30 1400 -18C1400 -10 1394 -6 1394 0L1440 0L1440 46C1434 46 1430 40 1422 40C1410 40 1410 80 1422 80C1430 80 1434 74 1440 74L1440 120L1440 166C1446 166 1450 160 1458 160C1470 160 1470 200 1458 200C1450 200 1446 194 1440 194L1440 240L1440 286C1434 286 1430 280 1422 280C1410 280 1410 320 1422 320C1430 320 1434 314 1440 314L1440 360L1440 406C1446 406 1450 400 1458 400C1470 400 1470 440 1458 440C1450 440 1446 434 1440 434L1440 480L1440 526C1434 526 1430 520 1422 520C1410 520 1410 560 1422 560C1430 560 1434 554 1440 554L1440 600L1440 646C1446 646 1450 640 1458 640C1470 640 1470 680 1458 680C1450 680 1446 674 1440 674L1440 720L1394 720C1394 714 1400 710 1400 702C1400 690 1360 690 1360 702C1360 710 1366 714 1366 720L1320 720L1274 720C1274 726 1280 730 1280 738C1280 750 1240 750 1240 738C1240 730 1246 726 1246 720L1200 720L1154 720C1154 714 1160 710 1160 702C1160 690 1120 690 1120 702C1120 710 1126 714 1126 720L1080 720L1034 720C1034 726 1040 730 1040 738C1040 750 1000 750 1000 738C1000 730 1006 726 1006 720L960 720L914 720C914 714 920 710 920 702C920 690 880 690 880 702C880 710 886 714 886 720L840 720L794 720C794 726 800 730 800 738C800 750 760 750 760 738C760 730 766 726 766 720L720 720L674 720C674 714 680 710 680 702C680 690 640 690 640 702C640 710 646 714 646 720L600 720L554 720C554 726 560 730 560 738C560 750 520 750 520 738C520 730 526 726 526 720L480 720L480 674C486 674 490 680 498 680C510 680 510 640 498 640C490 640 486 646 480 646L480 600L480 554C474 554 470 560 462 560C450 560 450 520 462 520C470 520 474 526 480 526L480 480L480 434C486 434 490 440 498 440C510 440 510 400 498 400C490 400 486 406 480 406L480 360L480 314C474 314 470 320 462 320C450 320 450 280 462 280C470 280 474 286 480 286L480 240L480 194C486 194 490 200 498 200C510 200 510 160 498 160C490 160 486 166 480 166L480 120L480 74C474 74 470 80 462 80C450 80 450 40 462 40C470 40 474 46 480 46L480 0Z" fill="#000"/></mask>
</defs>
</svg>
<a class="dc-skip" href="#main">Skip to content</a>

<header class="dc-head">
  <a href="#top" class="dc-brand"><svg width="30" height="30" viewBox="-72 -72 144 144" aria-hidden="true" focusable="false"><use href="#dc-logo" fill="url(#dc-logo-g)"/></svg>Data Care</a>
  <nav aria-label="Main" class="dc-navs dc-hide-sm">
    <a href="#how" class="dc-nav">How it works</a>
    <a href="#recover" class="dc-nav">What we recover</a>
    <a href="#demo" class="dc-nav">Demo</a>
    <a href="#agents" class="dc-nav">Agents</a>
    <a href="#pricing" class="dc-nav">Pricing</a>
  </nav>
  <a href="#start" class="dc-btn dc-btn-sm">Get an estimate</a>
</header>

<main id="main">
  <section id="top" class="dc-stack dc-hero" aria-labelledby="dc-h1">
    <div class="dc-hero-art">
      <svg viewBox="0 0 1920 720" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
        <g class="dc-hero-in">
          <rect width="1920" height="720" fill="url(#dc-g)" mask="url(#dc-mask)"/>
          <rect width="1920" height="720" fill="url(#dc-seam)" mask="url(#dc-mask)"/>
        </g>
        <g><g class="dc-rp" style="--dx:-257px;--dy:-31px;--rot:14deg;--d:0.00s"><path d="M480 240L526 240C526 246 520 250 520 258C520 270 560 270 560 258C560 250 554 246 554 240L600 240L600 286C606 286 610 280 618 280C630 280 630 320 618 320C610 320 606 314 600 314L600 360L554 360C554 354 560 350 560 342C560 330 520 330 520 342C520 350 526 354 526 360L480 360L480 314C474 314 470 320 462 320C450 320 450 280 462 280C470 280 474 286 480 286L480 240Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-239px;--dy:-87px;--rot:-21deg;--d:0.04s"><path d="M480 120L526 120C526 114 520 110 520 102C520 90 560 90 560 102C560 110 554 114 554 120L600 120L600 166C594 166 590 160 582 160C570 160 570 200 582 200C590 200 594 194 600 194L600 240L554 240C554 246 560 250 560 258C560 270 520 270 520 258C520 250 526 246 526 240L480 240L480 194C486 194 490 200 498 200C510 200 510 160 498 160C490 160 486 166 480 166L480 120Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-223px;--dy:-113px;--rot:28deg;--d:0.08s"><path d="M600 120L646 120C646 126 640 130 640 138C640 150 680 150 680 138C680 130 674 126 674 120L720 120L720 166C726 166 730 160 738 160C750 160 750 200 738 200C730 200 726 194 720 194L720 240L674 240C674 234 680 230 680 222C680 210 640 210 640 222C640 230 646 234 646 240L600 240L600 194C594 194 590 200 582 200C570 200 570 160 582 160C590 160 594 166 600 166L600 120Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-212px;--dy:-128px;--rot:-19deg;--d:0.12s"><path d="M480 0L526 0C526 6 520 10 520 18C520 30 560 30 560 18C560 10 554 6 554 0L600 0L600 46C606 46 610 40 618 40C630 40 630 80 618 80C610 80 606 74 600 74L600 120L554 120C554 114 560 110 560 102C560 90 520 90 520 102C520 110 526 114 526 120L480 120L480 74C474 74 470 80 462 80C450 80 450 40 462 40C470 40 474 46 480 46L480 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-184px;--dy:-156px;--rot:26deg;--d:0.16s"><path d="M600 0L646 0C646 -6 640 -10 640 -18C640 -30 680 -30 680 -18C680 -10 674 -6 674 0L720 0L720 46C714 46 710 40 702 40C690 40 690 80 702 80C710 80 714 74 720 74L720 120L674 120C674 126 680 130 680 138C680 150 640 150 640 138C640 130 646 126 646 120L600 120L600 74C606 74 610 80 618 80C630 80 630 40 618 40C610 40 606 46 600 46L600 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-134px;--dy:-189px;--rot:-17deg;--d:0.20s"><path d="M720 0L766 0C766 6 760 10 760 18C760 30 800 30 800 18C800 10 794 6 794 0L840 0L840 46C846 46 850 40 858 40C870 40 870 80 858 80C850 80 846 74 840 74L840 120L794 120C794 114 800 110 800 102C800 90 760 90 760 102C760 110 766 114 766 120L720 120L720 74C714 74 710 80 702 80C690 80 690 40 702 40C710 40 714 46 720 46L720 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-51px;--dy:-216px;--rot:24deg;--d:0.24s"><path d="M840 0L886 0C886 -6 880 -10 880 -18C880 -30 920 -30 920 -18C920 -10 914 -6 914 0L960 0L960 46C954 46 950 40 942 40C930 40 930 80 942 80C950 80 954 74 960 74L960 120L914 120C914 126 920 130 920 138C920 150 880 150 880 138C880 130 886 126 886 120L840 120L840 74C846 74 850 80 858 80C870 80 870 40 858 40C850 40 846 46 840 46L840 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:51px;--dy:-216px;--rot:-15deg;--d:0.28s"><path d="M960 0L1006 0C1006 6 1000 10 1000 18C1000 30 1040 30 1040 18C1040 10 1034 6 1034 0L1080 0L1080 46C1086 46 1090 40 1098 40C1110 40 1110 80 1098 80C1090 80 1086 74 1080 74L1080 120L1034 120C1034 114 1040 110 1040 102C1040 90 1000 90 1000 102C1000 110 1006 114 1006 120L960 120L960 74C954 74 950 80 942 80C930 80 930 40 942 40C950 40 954 46 960 46L960 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:134px;--dy:-189px;--rot:22deg;--d:0.32s"><path d="M1080 0L1126 0C1126 -6 1120 -10 1120 -18C1120 -30 1160 -30 1160 -18C1160 -10 1154 -6 1154 0L1200 0L1200 46C1194 46 1190 40 1182 40C1170 40 1170 80 1182 80C1190 80 1194 74 1200 74L1200 120L1154 120C1154 126 1160 130 1160 138C1160 150 1120 150 1120 138C1120 130 1126 126 1126 120L1080 120L1080 74C1086 74 1090 80 1098 80C1110 80 1110 40 1098 40C1090 40 1086 46 1080 46L1080 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:184px;--dy:-156px;--rot:-29deg;--d:0.36s"><path d="M1200 0L1246 0C1246 6 1240 10 1240 18C1240 30 1280 30 1280 18C1280 10 1274 6 1274 0L1320 0L1320 46C1326 46 1330 40 1338 40C1350 40 1350 80 1338 80C1330 80 1326 74 1320 74L1320 120L1274 120C1274 114 1280 110 1280 102C1280 90 1240 90 1240 102C1240 110 1246 114 1246 120L1200 120L1200 74C1194 74 1190 80 1182 80C1170 80 1170 40 1182 40C1190 40 1194 46 1200 46L1200 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:212px;--dy:-128px;--rot:20deg;--d:0.40s"><path d="M1320 0L1366 0C1366 -6 1360 -10 1360 -18C1360 -30 1400 -30 1400 -18C1400 -10 1394 -6 1394 0L1440 0L1440 46C1434 46 1430 40 1422 40C1410 40 1410 80 1422 80C1430 80 1434 74 1440 74L1440 120L1394 120C1394 126 1400 130 1400 138C1400 150 1360 150 1360 138C1360 130 1366 126 1366 120L1320 120L1320 74C1326 74 1330 80 1338 80C1350 80 1350 40 1338 40C1330 40 1326 46 1320 46L1320 0Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:223px;--dy:-113px;--rot:-27deg;--d:0.44s"><path d="M1200 120L1246 120C1246 114 1240 110 1240 102C1240 90 1280 90 1280 102C1280 110 1274 114 1274 120L1320 120L1320 166C1314 166 1310 160 1302 160C1290 160 1290 200 1302 200C1310 200 1314 194 1320 194L1320 240L1274 240C1274 246 1280 250 1280 258C1280 270 1240 270 1240 258C1240 250 1246 246 1246 240L1200 240L1200 194C1206 194 1210 200 1218 200C1230 200 1230 160 1218 160C1210 160 1206 166 1200 166L1200 120Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:239px;--dy:-87px;--rot:18deg;--d:0.48s"><path d="M1320 120L1366 120C1366 126 1360 130 1360 138C1360 150 1400 150 1400 138C1400 130 1394 126 1394 120L1440 120L1440 166C1446 166 1450 160 1458 160C1470 160 1470 200 1458 200C1450 200 1446 194 1440 194L1440 240L1394 240C1394 234 1400 230 1400 222C1400 210 1360 210 1360 222C1360 230 1366 234 1366 240L1320 240L1320 194C1314 194 1310 200 1302 200C1290 200 1290 160 1302 160C1310 160 1314 166 1320 166L1320 120Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:257px;--dy:-31px;--rot:-25deg;--d:0.52s"><path d="M1320 240L1366 240C1366 234 1360 230 1360 222C1360 210 1400 210 1400 222C1400 230 1394 234 1394 240L1440 240L1440 286C1434 286 1430 280 1422 280C1410 280 1410 320 1422 320C1430 320 1434 314 1440 314L1440 360L1394 360C1394 366 1400 370 1400 378C1400 390 1360 390 1360 378C1360 370 1366 366 1366 360L1320 360L1320 314C1326 314 1330 320 1338 320C1350 320 1350 280 1338 280C1330 280 1326 286 1320 286L1320 240Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:257px;--dy:31px;--rot:16deg;--d:0.56s"><path d="M1320 360L1366 360C1366 366 1360 370 1360 378C1360 390 1400 390 1400 378C1400 370 1394 366 1394 360L1440 360L1440 406C1446 406 1450 400 1458 400C1470 400 1470 440 1458 440C1450 440 1446 434 1440 434L1440 480L1394 480C1394 474 1400 470 1400 462C1400 450 1360 450 1360 462C1360 470 1366 474 1366 480L1320 480L1320 434C1314 434 1310 440 1302 440C1290 440 1290 400 1302 400C1310 400 1314 406 1320 406L1320 360Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:239px;--dy:87px;--rot:-23deg;--d:0.60s"><path d="M1320 480L1366 480C1366 474 1360 470 1360 462C1360 450 1400 450 1400 462C1400 470 1394 474 1394 480L1440 480L1440 526C1434 526 1430 520 1422 520C1410 520 1410 560 1422 560C1430 560 1434 554 1440 554L1440 600L1394 600C1394 606 1400 610 1400 618C1400 630 1360 630 1360 618C1360 610 1366 606 1366 600L1320 600L1320 554C1326 554 1330 560 1338 560C1350 560 1350 520 1338 520C1330 520 1326 526 1320 526L1320 480Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:223px;--dy:113px;--rot:14deg;--d:0.64s"><path d="M1200 480L1246 480C1246 486 1240 490 1240 498C1240 510 1280 510 1280 498C1280 490 1274 486 1274 480L1320 480L1320 526C1326 526 1330 520 1338 520C1350 520 1350 560 1338 560C1330 560 1326 554 1320 554L1320 600L1274 600C1274 594 1280 590 1280 582C1280 570 1240 570 1240 582C1240 590 1246 594 1246 600L1200 600L1200 554C1194 554 1190 560 1182 560C1170 560 1170 520 1182 520C1190 520 1194 526 1200 526L1200 480Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:212px;--dy:128px;--rot:-21deg;--d:0.68s"><path d="M1320 600L1366 600C1366 606 1360 610 1360 618C1360 630 1400 630 1400 618C1400 610 1394 606 1394 600L1440 600L1440 646C1446 646 1450 640 1458 640C1470 640 1470 680 1458 680C1450 680 1446 674 1440 674L1440 720L1394 720C1394 714 1400 710 1400 702C1400 690 1360 690 1360 702C1360 710 1366 714 1366 720L1320 720L1320 674C1314 674 1310 680 1302 680C1290 680 1290 640 1302 640C1310 640 1314 646 1320 646L1320 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:184px;--dy:156px;--rot:28deg;--d:0.72s"><path d="M1200 600L1246 600C1246 594 1240 590 1240 582C1240 570 1280 570 1280 582C1280 590 1274 594 1274 600L1320 600L1320 646C1314 646 1310 640 1302 640C1290 640 1290 680 1302 680C1310 680 1314 674 1320 674L1320 720L1274 720C1274 726 1280 730 1280 738C1280 750 1240 750 1240 738C1240 730 1246 726 1246 720L1200 720L1200 674C1206 674 1210 680 1218 680C1230 680 1230 640 1218 640C1210 640 1206 646 1200 646L1200 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:134px;--dy:189px;--rot:-19deg;--d:0.76s"><path d="M1080 600L1126 600C1126 606 1120 610 1120 618C1120 630 1160 630 1160 618C1160 610 1154 606 1154 600L1200 600L1200 646C1206 646 1210 640 1218 640C1230 640 1230 680 1218 680C1210 680 1206 674 1200 674L1200 720L1154 720C1154 714 1160 710 1160 702C1160 690 1120 690 1120 702C1120 710 1126 714 1126 720L1080 720L1080 674C1074 674 1070 680 1062 680C1050 680 1050 640 1062 640C1070 640 1074 646 1080 646L1080 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:51px;--dy:216px;--rot:26deg;--d:0.80s"><path d="M960 600L1006 600C1006 594 1000 590 1000 582C1000 570 1040 570 1040 582C1040 590 1034 594 1034 600L1080 600L1080 646C1074 646 1070 640 1062 640C1050 640 1050 680 1062 680C1070 680 1074 674 1080 674L1080 720L1034 720C1034 726 1040 730 1040 738C1040 750 1000 750 1000 738C1000 730 1006 726 1006 720L960 720L960 674C966 674 970 680 978 680C990 680 990 640 978 640C970 640 966 646 960 646L960 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-51px;--dy:216px;--rot:-17deg;--d:0.84s"><path d="M840 600L886 600C886 606 880 610 880 618C880 630 920 630 920 618C920 610 914 606 914 600L960 600L960 646C966 646 970 640 978 640C990 640 990 680 978 680C970 680 966 674 960 674L960 720L914 720C914 714 920 710 920 702C920 690 880 690 880 702C880 710 886 714 886 720L840 720L840 674C834 674 830 680 822 680C810 680 810 640 822 640C830 640 834 646 840 646L840 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-134px;--dy:189px;--rot:24deg;--d:0.88s"><path d="M720 600L766 600C766 594 760 590 760 582C760 570 800 570 800 582C800 590 794 594 794 600L840 600L840 646C834 646 830 640 822 640C810 640 810 680 822 680C830 680 834 674 840 674L840 720L794 720C794 726 800 730 800 738C800 750 760 750 760 738C760 730 766 726 766 720L720 720L720 674C726 674 730 680 738 680C750 680 750 640 738 640C730 640 726 646 720 646L720 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-184px;--dy:156px;--rot:-15deg;--d:0.92s"><path d="M600 600L646 600C646 606 640 610 640 618C640 630 680 630 680 618C680 610 674 606 674 600L720 600L720 646C726 646 730 640 738 640C750 640 750 680 738 680C730 680 726 674 720 674L720 720L674 720C674 714 680 710 680 702C680 690 640 690 640 702C640 710 646 714 646 720L600 720L600 674C594 674 590 680 582 680C570 680 570 640 582 640C590 640 594 646 600 646L600 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-212px;--dy:128px;--rot:22deg;--d:0.96s"><path d="M480 600L526 600C526 594 520 590 520 582C520 570 560 570 560 582C560 590 554 594 554 600L600 600L600 646C594 646 590 640 582 640C570 640 570 680 582 680C590 680 594 674 600 674L600 720L554 720C554 726 560 730 560 738C560 750 520 750 520 738C520 730 526 726 526 720L480 720L480 674C486 674 490 680 498 680C510 680 510 640 498 640C490 640 486 646 480 646L480 600Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-223px;--dy:113px;--rot:-29deg;--d:1.00s"><path d="M600 480L646 480C646 474 640 470 640 462C640 450 680 450 680 462C680 470 674 474 674 480L720 480L720 526C714 526 710 520 702 520C690 520 690 560 702 560C710 560 714 554 720 554L720 600L674 600C674 606 680 610 680 618C680 630 640 630 640 618C640 610 646 606 646 600L600 600L600 554C606 554 610 560 618 560C630 560 630 520 618 520C610 520 606 526 600 526L600 480Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-239px;--dy:87px;--rot:20deg;--d:1.04s"><path d="M480 480L526 480C526 486 520 490 520 498C520 510 560 510 560 498C560 490 554 486 554 480L600 480L600 526C606 526 610 520 618 520C630 520 630 560 618 560C610 560 606 554 600 554L600 600L554 600C554 594 560 590 560 582C560 570 520 570 520 582C520 590 526 594 526 600L480 600L480 554C474 554 470 560 462 560C450 560 450 520 462 520C470 520 474 526 480 526L480 480Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g><g class="dc-rp" style="--dx:-257px;--dy:31px;--rot:-27deg;--d:1.08s"><path d="M480 360L526 360C526 354 520 350 520 342C520 330 560 330 560 342C560 350 554 354 554 360L600 360L600 406C594 406 590 400 582 400C570 400 570 440 582 440C590 440 594 434 600 434L600 480L554 480C554 486 560 490 560 498C560 510 520 510 520 498C520 490 526 486 526 480L480 480L480 434C486 434 490 440 498 440C510 440 510 400 498 400C490 400 486 406 480 406L480 360Z" fill="url(#dc-g)" stroke="rgba(70,12,90,0.26)" stroke-width="2"/></g></g>
      </svg>
    </div>
    <div class="dc-hero-copy">
      <h1 id="dc-h1"><span class="dc-w" style="--i:0">Lost</span> <span class="dc-w" style="--i:1">data</span> <span class="dc-w" style="--i:2">isn't</span> <span class="dc-w" style="--i:3">gone.</span><br><span class="dc-w" style="--i:4">It's</span> <em><span class="dc-w2" style="--i:5">in</span> <span class="dc-w2" style="--i:6">pieces.</span></em></h1>
      <p class="dc-sub">We find each piece in what you still have, and show you where it came from.</p>
      <div class="dc-ctas">
        <a href="#start" class="dc-btn">Get a free estimate<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>
        <a href="#demo" class="dc-btn2">Watch it work</a>
      </div>
    </div>
  </section>

  <section id="how" class="dc-stack dc-sheet dc-sec dc-white dc-how" style="z-index:2" aria-labelledby="dc-how-h">
    <div class="dc-wrap dc-col">
      <h2 id="dc-how-h" class="dc-h2 dc-bal dc-rv">Four steps. You approve once.</h2>
      <div class="dc-io dc-steps">
        <svg viewBox="-8 -24 496 160" role="img" aria-label="Four puzzle pieces, one per step, fitting together">
          <g class="dc-fly" style="--dx:-60px;--dy:150px;--rot:-20deg;--d:0.00s"><g class="dc-sp dc-sp1"><path d="M0 0L120 0L120 46C126 46 130 40 138 40C150 40 150 80 138 80C130 80 126 74 120 74L120 120L0 120L0 0Z" fill="url(#dc-gs)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/><text x="60" y="79" text-anchor="middle" font-family="Instrument Serif, Georgia, serif" font-size="54" fill="#fff">1</text></g></g>
          <g class="dc-fly" style="--dx:30px;--dy:200px;--rot:16deg;--d:0.13s"><g class="dc-sp dc-sp2"><path d="M120 0L240 0L240 46C234 46 230 40 222 40C210 40 210 80 222 80C230 80 234 74 240 74L240 120L120 120L120 74C126 74 130 80 138 80C150 80 150 40 138 40C130 40 126 46 120 46L120 0Z" fill="url(#dc-gs)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/><text x="180" y="79" text-anchor="middle" font-family="Instrument Serif, Georgia, serif" font-size="54" fill="#fff">2</text></g></g>
          <g class="dc-fly" style="--dx:-30px;--dy:170px;--rot:-12deg;--d:0.26s"><g class="dc-sp dc-sp3"><path d="M240 0L360 0L360 46C366 46 370 40 378 40C390 40 390 80 378 80C370 80 366 74 360 74L360 120L240 120L240 74C234 74 230 80 222 80C210 80 210 40 222 40C230 40 234 46 240 46L240 0Z" fill="url(#dc-gs)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/><text x="300" y="79" text-anchor="middle" font-family="Instrument Serif, Georgia, serif" font-size="54" fill="#fff">3</text></g></g>
          <g class="dc-fly" style="--dx:60px;--dy:210px;--rot:22deg;--d:0.39s"><g class="dc-sp dc-sp4"><path d="M360 0L480 0L480 120L360 120L360 74C366 74 370 80 378 80C390 80 390 40 378 40C370 40 366 46 360 46L360 0Z" fill="url(#dc-gs)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/><text x="420" y="79" text-anchor="middle" font-family="Instrument Serif, Georgia, serif" font-size="54" fill="#fff">4</text></g></g>
        </svg>
        <ol>
          <li class="dc-rv" style="--d:0.55s"><a href="#start" class="dc-step-t">Tell us what's missing</a><span class="dc-step-d">Get an estimate first.</span></li>
          <li class="dc-rv" style="--d:0.67s"><a href="/download" class="dc-step-t">Share your files</a><span class="dc-step-d">Read-only copies you pick.</span></li>
          <li class="dc-rv" style="--d:0.79s"><a href="/board" class="dc-step-t">We find the pieces</a><span class="dc-step-d">Each one shows its source.</span></li>
          <li class="dc-rv" style="--d:0.91s"><a href="/case" class="dc-step-t">Get it back, checked</a><span class="dc-step-d">Tested against your numbers.</span></li>
        </ol>
      </div>
    </div>
  </section>

  <section id="recover" class="dc-stack dc-sheet dc-sec dc-cream dc-recover" style="z-index:3" aria-labelledby="dc-rec-h">
    <div class="dc-wrap dc-row dc-recover-h">
      <h2 id="dc-rec-h" class="dc-h2 dc-rv">What we recover.</h2>
      <a href="#pricing" class="dc-more dc-rv">See prices <span class="dc-arrow" aria-hidden="true">→</span></a>
    </div>
    <div class="dc-mq dc-io">
      <div class="dc-mq-track">
        <a href="#start" class="dc-card" data-choose="sheet"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF1E4"/><rect class="dc-cell" style="--d:0.35s" x="32" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.38s" x="92" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.41s" x="152" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.44s" x="212" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.47s" x="272" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.50s" x="32" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.53s" x="92" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.56s" x="152" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.59s" x="212" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.62s" x="272" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.65s" x="32" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.68s" x="92" y="102" width="56" height="30" rx="5" fill="#fff"/><rect x="152" y="102" width="56" height="30" rx="5" fill="none" stroke="#E7A877" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-cell" style="--d:0.74s" x="212" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.77s" x="272" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.80s" x="32" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.83s" x="92" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.86s" x="152" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.89s" x="212" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.92s" x="272" y="136" width="56" height="30" rx="5" fill="#fff"/><g class="dc-dl" style="--d:0.60s"><use href="#dc-pc" transform="translate(180 117) scale(0.36)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.2" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Spreadsheets</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Formulas, totals, models.</span></span></a>
        <a href="#start" class="dc-card" data-choose="code"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFEFF3"/><rect class="dc-bar" style="--d:0.35s" x="40" y="30" width="150" height="14" rx="7" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.47s" x="40" y="58" width="220" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.59s" x="64" y="86" width="96" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.71s" x="40" y="114" width="180" height="14" rx="7" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.83s" x="64" y="142" width="140" height="14" rx="7" fill="#fff"/><rect x="176" y="79" width="60" height="28" rx="8" fill="none" stroke="#E98AA6" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.75s" x="246" y="86" width="70" height="14" rx="7" fill="#fff"/><g class="dc-dl" style="--d:1.75s"><use href="#dc-pc" transform="translate(206 93) scale(0.34)" fill="#EF5C7E" stroke="rgba(70,12,90,0.25)" stroke-width="4.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Code</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Pricing and invoicing logic.</span></span></a>
        <a href="#start" class="dc-card" data-choose="trace"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><path class="dc-line" style="--d:0.75s" d="M118 100 C170 100 190 48 246 48" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><path class="dc-line" style="--d:0.87s" d="M118 100 C170 100 190 100 246 100" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><path class="dc-line" style="--d:0.99s" d="M118 100 C170 100 190 152 246 152" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><g class="dc-pop" style="--d:1.45s"><use href="#dc-pc" transform="translate(276 48) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><rect x="260" y="84" width="32" height="32" rx="6" fill="none" stroke="#B892F0" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-dl" style="--d:2.90s"><use href="#dc-pc" transform="translate(276 100) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><g class="dc-pop" style="--d:1.69s"><use href="#dc-pc" transform="translate(276 152) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><g class="dc-pop" style="--d:0.40s"><use href="#dc-pc" transform="translate(82 100) scale(0.4)" fill="#8B44D6" stroke="rgba(70,12,90,0.25)" stroke-width="3.8" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Food trace-back</span><span class="dc-card-p">from $2,000</span></span><span class="dc-card-l">From a recall back to the farm.</span></span></a>
        <a href="#start" class="dc-card"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FDF0F7"/><rect class="dc-bar" style="--d:0.35s" x="32" y="30" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.40s" x="92" y="30" width="150" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="270" y="30" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.43s" x="32" y="60" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.48s" x="92" y="60" width="120" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.53s" x="270" y="60" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.51s" x="32" y="90" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.56s" x="92" y="90" width="150" height="14" rx="7" fill="#fff"/><rect x="262" y="82" width="66" height="30" rx="8" fill="none" stroke="#E49AC4" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.59s" x="32" y="120" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.64s" x="92" y="120" width="120" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.69s" x="270" y="120" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.67s" x="32" y="150" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.72s" x="92" y="150" width="150" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.77s" x="270" y="150" width="58" height="14" rx="7" fill="#F7C6E0"/><g class="dc-dl" style="--d:4.05s"><use href="#dc-pc" transform="translate(295 97) scale(0.32)" fill="#D45094" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Ledgers</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Books matched to receipts and bank lines.</span></span></a>
        <a href="#start" class="dc-card"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F6EEFB"/><circle class="dc-pop" style="--d:0.35s" cx="48" cy="56" r="19" fill="#F5B78E"/><rect class="dc-bar" style="--d:0.40s" x="74" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="74" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.43s" cx="154" cy="56" r="19" fill="#F29AB6"/><rect class="dc-bar" style="--d:0.48s" x="180" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.53s" x="180" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.51s" cx="260" cy="56" r="19" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.56s" x="286" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.61s" x="286" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.59s" cx="48" cy="128" r="19" fill="#F5B78E"/><rect class="dc-bar" style="--d:0.64s" x="74" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.69s" x="74" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><circle cx="154" cy="128" r="19" fill="none" stroke="#C59BEA" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.72s" x="180" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.77s" x="180" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.75s" cx="260" cy="128" r="19" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.80s" x="286" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.85s" x="286" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><g class="dc-dl" style="--d:5.20s"><use href="#dc-pc" transform="translate(154 128) scale(0.3)" fill="#9944CA" stroke="rgba(70,12,90,0.25)" stroke-width="5.0" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Customer lists</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Contacts pieced back from email and invoices.</span></span></a>
        <a href="#start" class="dc-card"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF4EA"/><rect class="dc-bar" style="--d:0.3s" x="28" y="98" width="304" height="6" rx="3" fill="#F3CDA8"/><rect class="dc-bar" style="--d:0.3s" x="28" y="170" width="304" height="6" rx="3" fill="#F3CDA8"/><rect class="dc-pop" style="--d:0.35s" x="40" y="54" width="44" height="44" rx="6" fill="#fff"/><rect class="dc-pop" style="--d:0.41s" x="92" y="64" width="60" height="34" rx="6" fill="#FBD9BC"/><rect class="dc-pop" style="--d:0.47s" x="160" y="48" width="40" height="50" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.53s" x="232" y="60" width="50" height="38" rx="6" fill="#fff"/><rect class="dc-pop" style="--d:0.59s" x="288" y="70" width="36" height="28" rx="6" fill="#FBD9BC"/><rect class="dc-pop" style="--d:0.65s" x="40" y="128" width="56" height="42" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.71s" x="104" y="140" width="40" height="30" rx="6" fill="#fff"/><rect x="150" y="122" width="52" height="48" rx="6" fill="none" stroke="#F0A56B" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-pop" style="--d:0.83s" x="210" y="134" width="44" height="36" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.89s" x="262" y="126" width="58" height="44" rx="6" fill="#fff"/><g class="dc-dl" style="--d:6.35s"><use href="#dc-pc" transform="translate(176 146) scale(0.32)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Inventory</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Stock counts traced through orders.</span></span></a>
        <a href="#start" class="dc-card" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFEFF3"/><rect class="dc-pop" style="--d:0.35s" x="32" y="40" width="110" height="120" rx="12" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="48" y="62" width="70" height="10" rx="5" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.5s" x="48" y="82" width="54" height="10" rx="5" fill="#FBE0E8"/><rect class="dc-bar" style="--d:0.55s" x="48" y="102" width="62" height="10" rx="5" fill="#FBE0E8"/><rect class="dc-pop" style="--d:0.60s" x="170" y="40" width="150" height="30" rx="15" fill="#fff"/><rect x="200" y="82" width="120" height="30" rx="15" fill="none" stroke="#E98AA6" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-pop" style="--d:0.84s" x="170" y="124" width="140" height="30" rx="15" fill="#F7C6D4"/><g class="dc-dl" style="--d:0.60s"><use href="#dc-pc" transform="translate(260 97) scale(0.3)" fill="#EF5C7E" stroke="rgba(70,12,90,0.25)" stroke-width="5.0" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Handover packs</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Know-how kept when someone leaves.</span></span></a>
        <a href="#start" class="dc-card" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><g class="dc-pop" style="--d:0.35s"><rect x="106" y="42" width="148" height="28" rx="14" fill="#fff"/><ellipse cx="180" cy="48" rx="74" ry="10" fill="#fff" opacity="0.7"/></g><ellipse cx="180" cy="100" rx="74" ry="16" fill="none" stroke="#C59BEA" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.59s"><rect x="106" y="130" width="148" height="28" rx="14" fill="#E9DDF7"/><ellipse cx="180" cy="136" rx="74" ry="10" fill="#fff" opacity="0.7"/></g><g class="dc-dl" style="--d:1.75s"><use href="#dc-pc" transform="translate(180 100) scale(0.32)" fill="#8B44D6" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Databases</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Rows matched to exports, logs and invoices.</span></span></a>
        <a href="#start" class="dc-card" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF1E4"/><g class="dc-pop" style="--d:0.35s"><path d="M40 34H120V166L44 170L52 164L60 170L68 164L76 170L84 164L92 170L100 164L108 170L116 164L40 166Z" fill="#fff"/><rect x="52" y="52" width="44" height="8" rx="4" fill="#FBD9BC"/><rect x="52" y="72" width="56" height="8" rx="4" fill="#FFE7D3"/><rect x="52" y="92" width="36" height="8" rx="4" fill="#FFE7D3"/><rect x="80" y="128" width="28" height="10" rx="5" fill="#FC7D36"/></g><rect x="124" y="34" width="80" height="132" rx="6" fill="none" stroke="#F0A56B" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.55s"><path d="M208 34H288V166L212 170L220 164L228 170L236 164L244 170L252 164L260 170L268 164L276 170L284 164L208 166Z" fill="#fff"/><rect x="220" y="52" width="44" height="8" rx="4" fill="#FBD9BC"/><rect x="220" y="72" width="56" height="8" rx="4" fill="#FFE7D3"/><rect x="220" y="92" width="36" height="8" rx="4" fill="#FFE7D3"/><rect x="248" y="128" width="28" height="10" rx="5" fill="#FC7D36"/></g><g class="dc-dl" style="--d:2.90s"><use href="#dc-pc" transform="translate(164 100) scale(0.34)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Receipts for an audit</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Every expense tied to a document.</span></span></a>
        <a href="#start" class="dc-card" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FDF0F7"/><g class="dc-pop" style="--d:0.35s"><rect x="36" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="48" y="54" width="30" height="30" rx="8" fill="#F7C6E0"/><rect x="86" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="86" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.42s"><rect x="132" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="144" y="54" width="30" height="30" rx="8" fill="#FBD9BC"/><rect x="182" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="182" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.49s"><rect x="228" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="240" y="54" width="30" height="30" rx="8" fill="#E9DDF7"/><rect x="278" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="278" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.56s"><rect x="36" y="112" width="88" height="58" rx="10" fill="#fff"/><rect x="48" y="126" width="30" height="30" rx="8" fill="#F7C6E0"/><rect x="86" y="130" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="86" y="144" width="18" height="8" rx="4" fill="#F3D9E8"/></g><rect x="132" y="112" width="88" height="58" rx="10" fill="none" stroke="#E49AC4" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.70s"><rect x="228" y="112" width="88" height="58" rx="10" fill="#fff"/><rect x="240" y="126" width="30" height="30" rx="8" fill="#E9DDF7"/><rect x="278" y="130" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="278" y="144" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-dl" style="--d:4.05s"><use href="#dc-pc" transform="translate(176 141) scale(0.32)" fill="#D45094" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Insurance claims</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Each item tied to a purchase and price.</span></span></a>
        <a href="#start" class="dc-card" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><rect class="dc-pop" style="--d:0.3s" x="40" y="30" width="280" height="140" rx="14" fill="#fff"/><circle cx="62" cy="50" r="5" fill="#F5B78E"/><circle cx="78" cy="50" r="5" fill="#F29AB6"/><circle cx="94" cy="50" r="5" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.45s" x="64" y="78" width="180" height="14" rx="7" fill="#E9DDF7"/><rect x="64" y="100" width="120" height="22" rx="11" fill="none" stroke="#B892F0" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.69s" x="64" y="130" width="150" height="14" rx="7" fill="#E9DDF7"/><g class="dc-dl" style="--d:5.20s"><use href="#dc-pc" transform="translate(124 111) scale(0.28)" fill="#9944CA" stroke="rgba(70,12,90,0.25)" stroke-width="5.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Retired tools</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Same outputs on your recorded inputs.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="sheet"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF1E4"/><rect class="dc-cell" style="--d:0.35s" x="32" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.38s" x="92" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.41s" x="152" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.44s" x="212" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.47s" x="272" y="34" width="56" height="30" rx="5" fill="#FBD9BC"/><rect class="dc-cell" style="--d:0.50s" x="32" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.53s" x="92" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.56s" x="152" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.59s" x="212" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.62s" x="272" y="68" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.65s" x="32" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.68s" x="92" y="102" width="56" height="30" rx="5" fill="#fff"/><rect x="152" y="102" width="56" height="30" rx="5" fill="none" stroke="#E7A877" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-cell" style="--d:0.74s" x="212" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.77s" x="272" y="102" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.80s" x="32" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.83s" x="92" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.86s" x="152" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.89s" x="212" y="136" width="56" height="30" rx="5" fill="#fff"/><rect class="dc-cell" style="--d:0.92s" x="272" y="136" width="56" height="30" rx="5" fill="#fff"/><g class="dc-dl" style="--d:0.60s"><use href="#dc-pc" transform="translate(180 117) scale(0.36)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.2" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Spreadsheets</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Formulas, totals, models.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="code"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFEFF3"/><rect class="dc-bar" style="--d:0.35s" x="40" y="30" width="150" height="14" rx="7" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.47s" x="40" y="58" width="220" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.59s" x="64" y="86" width="96" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.71s" x="40" y="114" width="180" height="14" rx="7" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.83s" x="64" y="142" width="140" height="14" rx="7" fill="#fff"/><rect x="176" y="79" width="60" height="28" rx="8" fill="none" stroke="#E98AA6" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.75s" x="246" y="86" width="70" height="14" rx="7" fill="#fff"/><g class="dc-dl" style="--d:1.75s"><use href="#dc-pc" transform="translate(206 93) scale(0.34)" fill="#EF5C7E" stroke="rgba(70,12,90,0.25)" stroke-width="4.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Code</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Pricing and invoicing logic.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="trace"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><path class="dc-line" style="--d:0.75s" d="M118 100 C170 100 190 48 246 48" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><path class="dc-line" style="--d:0.87s" d="M118 100 C170 100 190 100 246 100" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><path class="dc-line" style="--d:0.99s" d="M118 100 C170 100 190 152 246 152" fill="none" stroke="#C9B5F3" stroke-width="3" stroke-linecap="round"/><g class="dc-pop" style="--d:1.45s"><use href="#dc-pc" transform="translate(276 48) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><rect x="260" y="84" width="32" height="32" rx="6" fill="none" stroke="#B892F0" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-dl" style="--d:2.90s"><use href="#dc-pc" transform="translate(276 100) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><g class="dc-pop" style="--d:1.69s"><use href="#dc-pc" transform="translate(276 152) scale(0.26)" fill="#B892F0" stroke="rgba(70,12,90,0.25)" stroke-width="5.8" stroke-linejoin="round"/></g><g class="dc-pop" style="--d:0.40s"><use href="#dc-pc" transform="translate(82 100) scale(0.4)" fill="#8B44D6" stroke="rgba(70,12,90,0.25)" stroke-width="3.8" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Food trace-back</span><span class="dc-card-p">from $2,000</span></span><span class="dc-card-l">From a recall back to the farm.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FDF0F7"/><rect class="dc-bar" style="--d:0.35s" x="32" y="30" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.40s" x="92" y="30" width="150" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="270" y="30" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.43s" x="32" y="60" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.48s" x="92" y="60" width="120" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.53s" x="270" y="60" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.51s" x="32" y="90" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.56s" x="92" y="90" width="150" height="14" rx="7" fill="#fff"/><rect x="262" y="82" width="66" height="30" rx="8" fill="none" stroke="#E49AC4" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.59s" x="32" y="120" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.64s" x="92" y="120" width="120" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.69s" x="270" y="120" width="58" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.67s" x="32" y="150" width="48" height="14" rx="7" fill="#F7C6E0"/><rect class="dc-bar" style="--d:0.72s" x="92" y="150" width="150" height="14" rx="7" fill="#fff"/><rect class="dc-bar" style="--d:0.77s" x="270" y="150" width="58" height="14" rx="7" fill="#F7C6E0"/><g class="dc-dl" style="--d:4.05s"><use href="#dc-pc" transform="translate(295 97) scale(0.32)" fill="#D45094" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Ledgers</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Books matched to receipts and bank lines.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F6EEFB"/><circle class="dc-pop" style="--d:0.35s" cx="48" cy="56" r="19" fill="#F5B78E"/><rect class="dc-bar" style="--d:0.40s" x="74" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="74" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.43s" cx="154" cy="56" r="19" fill="#F29AB6"/><rect class="dc-bar" style="--d:0.48s" x="180" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.53s" x="180" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.51s" cx="260" cy="56" r="19" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.56s" x="286" y="44" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.61s" x="286" y="60" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.59s" cx="48" cy="128" r="19" fill="#F5B78E"/><rect class="dc-bar" style="--d:0.64s" x="74" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.69s" x="74" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><circle cx="154" cy="128" r="19" fill="none" stroke="#C59BEA" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.72s" x="180" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.77s" x="180" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><circle class="dc-pop" style="--d:0.75s" cx="260" cy="128" r="19" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.80s" x="286" y="116" width="44" height="10" rx="5" fill="#fff"/><rect class="dc-bar" style="--d:0.85s" x="286" y="132" width="30" height="10" rx="5" fill="#E9DDF7"/><g class="dc-dl" style="--d:5.20s"><use href="#dc-pc" transform="translate(154 128) scale(0.3)" fill="#9944CA" stroke="rgba(70,12,90,0.25)" stroke-width="5.0" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Customer lists</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Contacts pieced back from email and invoices.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF4EA"/><rect class="dc-bar" style="--d:0.3s" x="28" y="98" width="304" height="6" rx="3" fill="#F3CDA8"/><rect class="dc-bar" style="--d:0.3s" x="28" y="170" width="304" height="6" rx="3" fill="#F3CDA8"/><rect class="dc-pop" style="--d:0.35s" x="40" y="54" width="44" height="44" rx="6" fill="#fff"/><rect class="dc-pop" style="--d:0.41s" x="92" y="64" width="60" height="34" rx="6" fill="#FBD9BC"/><rect class="dc-pop" style="--d:0.47s" x="160" y="48" width="40" height="50" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.53s" x="232" y="60" width="50" height="38" rx="6" fill="#fff"/><rect class="dc-pop" style="--d:0.59s" x="288" y="70" width="36" height="28" rx="6" fill="#FBD9BC"/><rect class="dc-pop" style="--d:0.65s" x="40" y="128" width="56" height="42" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.71s" x="104" y="140" width="40" height="30" rx="6" fill="#fff"/><rect x="150" y="122" width="52" height="48" rx="6" fill="none" stroke="#F0A56B" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-pop" style="--d:0.83s" x="210" y="134" width="44" height="36" rx="6" fill="#FFE7D3"/><rect class="dc-pop" style="--d:0.89s" x="262" y="126" width="58" height="44" rx="6" fill="#fff"/><g class="dc-dl" style="--d:6.35s"><use href="#dc-pc" transform="translate(176 146) scale(0.32)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Inventory</span><span class="dc-card-p">from $450</span></span><span class="dc-card-l">Stock counts traced through orders.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFEFF3"/><rect class="dc-pop" style="--d:0.35s" x="32" y="40" width="110" height="120" rx="12" fill="#fff"/><rect class="dc-bar" style="--d:0.45s" x="48" y="62" width="70" height="10" rx="5" fill="#F7C6D4"/><rect class="dc-bar" style="--d:0.5s" x="48" y="82" width="54" height="10" rx="5" fill="#FBE0E8"/><rect class="dc-bar" style="--d:0.55s" x="48" y="102" width="62" height="10" rx="5" fill="#FBE0E8"/><rect class="dc-pop" style="--d:0.60s" x="170" y="40" width="150" height="30" rx="15" fill="#fff"/><rect x="200" y="82" width="120" height="30" rx="15" fill="none" stroke="#E98AA6" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-pop" style="--d:0.84s" x="170" y="124" width="140" height="30" rx="15" fill="#F7C6D4"/><g class="dc-dl" style="--d:0.60s"><use href="#dc-pc" transform="translate(260 97) scale(0.3)" fill="#EF5C7E" stroke="rgba(70,12,90,0.25)" stroke-width="5.0" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Handover packs</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Know-how kept when someone leaves.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><g class="dc-pop" style="--d:0.35s"><rect x="106" y="42" width="148" height="28" rx="14" fill="#fff"/><ellipse cx="180" cy="48" rx="74" ry="10" fill="#fff" opacity="0.7"/></g><ellipse cx="180" cy="100" rx="74" ry="16" fill="none" stroke="#C59BEA" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.59s"><rect x="106" y="130" width="148" height="28" rx="14" fill="#E9DDF7"/><ellipse cx="180" cy="136" rx="74" ry="10" fill="#fff" opacity="0.7"/></g><g class="dc-dl" style="--d:1.75s"><use href="#dc-pc" transform="translate(180 100) scale(0.32)" fill="#8B44D6" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Databases</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Rows matched to exports, logs and invoices.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FFF1E4"/><g class="dc-pop" style="--d:0.35s"><path d="M40 34H120V166L44 170L52 164L60 170L68 164L76 170L84 164L92 170L100 164L108 170L116 164L40 166Z" fill="#fff"/><rect x="52" y="52" width="44" height="8" rx="4" fill="#FBD9BC"/><rect x="52" y="72" width="56" height="8" rx="4" fill="#FFE7D3"/><rect x="52" y="92" width="36" height="8" rx="4" fill="#FFE7D3"/><rect x="80" y="128" width="28" height="10" rx="5" fill="#FC7D36"/></g><rect x="124" y="34" width="80" height="132" rx="6" fill="none" stroke="#F0A56B" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.55s"><path d="M208 34H288V166L212 170L220 164L228 170L236 164L244 170L252 164L260 170L268 164L276 170L284 164L208 166Z" fill="#fff"/><rect x="220" y="52" width="44" height="8" rx="4" fill="#FBD9BC"/><rect x="220" y="72" width="56" height="8" rx="4" fill="#FFE7D3"/><rect x="220" y="92" width="36" height="8" rx="4" fill="#FFE7D3"/><rect x="248" y="128" width="28" height="10" rx="5" fill="#FC7D36"/></g><g class="dc-dl" style="--d:2.90s"><use href="#dc-pc" transform="translate(164 100) scale(0.34)" fill="#FC7D36" stroke="rgba(70,12,90,0.25)" stroke-width="4.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Receipts for an audit</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Every expense tied to a document.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#FDF0F7"/><g class="dc-pop" style="--d:0.35s"><rect x="36" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="48" y="54" width="30" height="30" rx="8" fill="#F7C6E0"/><rect x="86" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="86" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.42s"><rect x="132" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="144" y="54" width="30" height="30" rx="8" fill="#FBD9BC"/><rect x="182" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="182" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.49s"><rect x="228" y="40" width="88" height="58" rx="10" fill="#fff"/><rect x="240" y="54" width="30" height="30" rx="8" fill="#E9DDF7"/><rect x="278" y="58" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="278" y="72" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-pop" style="--d:0.56s"><rect x="36" y="112" width="88" height="58" rx="10" fill="#fff"/><rect x="48" y="126" width="30" height="30" rx="8" fill="#F7C6E0"/><rect x="86" y="130" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="86" y="144" width="18" height="8" rx="4" fill="#F3D9E8"/></g><rect x="132" y="112" width="88" height="58" rx="10" fill="none" stroke="#E49AC4" stroke-width="1.5" stroke-dasharray="5 4"/><g class="dc-pop" style="--d:0.70s"><rect x="228" y="112" width="88" height="58" rx="10" fill="#fff"/><rect x="240" y="126" width="30" height="30" rx="8" fill="#E9DDF7"/><rect x="278" y="130" width="26" height="8" rx="4" fill="#F3D9E8"/><rect x="278" y="144" width="18" height="8" rx="4" fill="#F3D9E8"/></g><g class="dc-dl" style="--d:4.05s"><use href="#dc-pc" transform="translate(176 141) scale(0.32)" fill="#D45094" stroke="rgba(70,12,90,0.25)" stroke-width="4.7" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Insurance claims</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Each item tied to a purchase and price.</span></span></a>
        <a href="#start" class="dc-card dc-dup" aria-hidden="true" tabindex="-1" data-choose="other"><svg class="dc-art" viewBox="0 0 360 200" aria-hidden="true" focusable="false"><rect width="360" height="200" rx="16" fill="#F3EEFF"/><rect class="dc-pop" style="--d:0.3s" x="40" y="30" width="280" height="140" rx="14" fill="#fff"/><circle cx="62" cy="50" r="5" fill="#F5B78E"/><circle cx="78" cy="50" r="5" fill="#F29AB6"/><circle cx="94" cy="50" r="5" fill="#C9A6F2"/><rect class="dc-bar" style="--d:0.45s" x="64" y="78" width="180" height="14" rx="7" fill="#E9DDF7"/><rect x="64" y="100" width="120" height="22" rx="11" fill="none" stroke="#B892F0" stroke-width="1.5" stroke-dasharray="5 4"/><rect class="dc-bar" style="--d:0.69s" x="64" y="130" width="150" height="14" rx="7" fill="#E9DDF7"/><g class="dc-dl" style="--d:5.20s"><use href="#dc-pc" transform="translate(124 111) scale(0.28)" fill="#9944CA" stroke="rgba(70,12,90,0.25)" stroke-width="5.4" stroke-linejoin="round"/></g></svg><span class="dc-card-t"><span class="dc-card-h"><span class="dc-card-n">Retired tools</span><span class="dc-card-p">Quote on request</span></span><span class="dc-card-l">Same outputs on your recorded inputs.</span></span></a>
      </div>
    </div>
  </section>

  <section id="demo" class="dc-stack dc-sheet dc-sec dc-white dc-demo-sec" style="z-index:4" aria-labelledby="dc-demo-h">
    <div class="dc-wrap dc-col">
      <div class="dc-row dc-demo-h dc-rv">
        <h2 id="dc-demo-h" class="dc-h2">Watch it work.</h2>
        <div class="dc-pills" role="group" aria-label="Demo steps">
          <button type="button" class="dc-pill" data-t="0" aria-pressed="false">Scan</button>
          <button type="button" class="dc-pill" data-t="1" aria-pressed="false">Find</button>
          <button type="button" class="dc-pill" data-t="5" aria-pressed="false">Ask</button>
          <button type="button" class="dc-pill" data-t="8" aria-pressed="true">Check</button>
          <button type="button" class="dc-pill dc-replay" id="dc-replay" aria-label="Replay the demo"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 12a8 8 0 1 0 2.3-5.6M4 4v4.5h4.5"/></svg></button>
        </div>
      </div>
      <div id="dc-demo" class="dc-demo dc-rv" style="--d:0.1s">
        <div class="dc-demo-bar">
          <span class="dc-demo-name"><svg width="20" height="20" viewBox="-72 -72 144 144" aria-hidden="true" focusable="false"><use href="#dc-logo" fill="url(#dc-logo-g)"/></svg><span>Case C-0104 · alderbank_q3_model.xlsx</span></span>
          <span class="dc-status" id="dc-dstatus" style="background:#E6F4EE;color:#0F5F47">Recovered</span>
        </div>
        <div class="dc-prog" aria-hidden="true"><div id="dc-dprog" style="width:100%"></div></div>
        <div class="dc-demo-body">
          <div class="dc-sheetbox">
            <table>
              <caption class="dc-vh">Demo spreadsheet, by quarter</caption>
              <thead><tr><th scope="col"><span class="dc-vh">Line</span></th><th scope="col">Q1</th><th scope="col">Q2</th><th scope="col">Q3</th><th scope="col">Q4</th></tr></thead>
              <tbody>
                <tr><th scope="row">Revenue</th><td style="--cd:0.00s">1,240</td><td style="--cd:0.05s">1,310</td><td style="--cd:0.10s">1,405</td><td style="--cd:0.15s">1,520</td></tr>
                <tr><th scope="row">Cost of goods</th><td style="--cd:0.05s">702</td><td style="--cd:0.10s">735</td><td style="--cd:0.15s">781</td><td style="--cd:0.20s">842</td></tr>
                <tr><th scope="row">Gross profit</th><td style="--cd:0.10s">538</td><td style="--cd:0.15s">575</td><td class="c-fix" style="--cd:0.20s">624</td><td style="--cd:0.25s">678</td></tr>
                <tr><th scope="row">Operating expenses</th><td class="c-asked" style="--cd:0.15s">412</td><td style="--cd:0.20s">421</td><td style="--cd:0.25s">436</td><td style="--cd:0.30s">451</td></tr>
                <tr><th scope="row">Operating income</th><td style="--cd:0.20s">126</td><td style="--cd:0.25s">154</td><td class="c-fix" style="--cd:0.30s">188</td><td class="c-fix" style="--cd:0.35s">227</td></tr>
                <tr><th scope="row">Margin</th><td style="--cd:0.25s">10.2%</td><td class="c-fix" style="--cd:0.30s">11.8%</td><td style="--cd:0.35s">13.4%</td><td class="c-fix" style="--cd:0.40s">14.9%</td></tr>
              </tbody>
            </table>
          </div>
          <div class="dc-feedbox">
            <span class="dc-eyebrow" id="dc-feed-h">Live updates</span>
            <ol id="dc-feed" aria-labelledby="dc-feed-h" aria-live="off">
              <li><i aria-hidden="true" style="background:#9944CA"></i><span><strong>Forensics</strong> Opened a sealed copy of alderbank_q3_model.xlsx. 6 cells damaged, nothing unsafe.</span></li>
              <li><i aria-hidden="true" style="background:#FC7D36"></i><span><strong>Context</strong> Q3 gross profit: the formula is in the CFO’s notes.</span></li>
              <li><i aria-hidden="true" style="background:#FC7D36"></i><span><strong>Context</strong> Q3 operating income: found in your ERP export.</span></li>
              <li><i aria-hidden="true" style="background:#FC7D36"></i><span><strong>Context</strong> Q4 operating income: found in the board report.</span></li>
              <li><i aria-hidden="true" style="background:#F56263"></i><span><strong>Reconstruction</strong> Q2 and Q4 margin: restored as income ÷ revenue, then tested.</span></li>
              <li><i aria-hidden="true" style="background:#141414"></i><span><strong>Recovery Manager</strong> Q1 operating expenses are in none of your files. Emailed Priya Shah, your accountant.</span></li>
              <li><i aria-hidden="true" style="background:#6D35CF"></i><span><strong>Priya Shah</strong> “Q1 opex was $412k.” Filled in and linked to her email.</span></li>
              <li class="is-last"><i aria-hidden="true" style="background:#13795B"></i><span><strong>Validation</strong> Checked every value against your numbers: 0 mismatches.</span></li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="agents" class="dc-stack dc-sheet dc-sec dc-cream dc-agents" style="z-index:5" aria-labelledby="dc-ag-h">
    <div class="dc-wrap dc-col">
      <div class="dc-row dc-agents-h dc-rv">
        <h2 id="dc-ag-h" class="dc-h2">Run by agents.</h2>
        <p class="dc-lead">Six agents work every case. You approve the quote, they do the rest.</p>
      </div>
      <div class="dc-grid3">
        <div class="dc-agent dc-rv" style="--d:0.00s"><h3><i aria-hidden="true" style="--c:rgba(20,20,20,0.35);--dd:0.0s;background:#141414"></i>Recovery Manager</h3><p>Opens your case, sends the quote and keeps you posted.</p></div>
        <div class="dc-agent dc-rv" style="--d:0.08s"><h3><i aria-hidden="true" style="--c:rgba(153,68,202,0.4);--dd:0.4s;background:#9944CA"></i>Forensics</h3><p>Scans every file first. Never runs them.</p></div>
        <div class="dc-agent dc-rv" style="--d:0.16s"><h3><i aria-hidden="true" style="--c:rgba(252,125,54,0.45);--dd:0.8s;background:#FC7D36"></i>Context</h3><p>Finds every piece that survived, and where.</p></div>
        <div class="dc-agent dc-rv" style="--d:0.24s"><h3><i aria-hidden="true" style="--c:rgba(245,98,99,0.45);--dd:1.2s;background:#F56263"></i>Reconstruction</h3><p>Restores only what is missing, and cites the evidence.</p></div>
        <div class="dc-agent dc-rv" style="--d:0.32s"><h3><i aria-hidden="true" style="--c:rgba(19,121,91,0.4);--dd:1.6s;background:#13795B"></i>Validation</h3><p>Tests the result on examples the builder never saw.</p></div>
        <div class="dc-agent dc-rv" style="--d:0.40s"><h3><i aria-hidden="true" style="--c:rgba(212,80,148,0.4);--dd:2.0s;background:#D45094"></i>Mail Scout</h3><p>Searches the email you connect, read-only.</p></div>
      </div>
      <div class="dc-labels dc-rv">
        <span class="dc-labels-t" id="dc-labels-t">Every result gets one label:</span>
        <ul aria-labelledby="dc-labels-t">
          <li class="dc-label dc-l1">Recovered</li>
          <li class="dc-label dc-l2">Reconstructed and tested</li>
          <li class="dc-label dc-l3">Reconstructed but untested</li>
          <li class="dc-label dc-l4">Unresolved</li>
        </ul>
        <p class="dc-labels-n">Missing facts are flagged, never invented.</p>
      </div>
    </div>
  </section>

  <section id="missing" class="dc-stack dc-sheet dc-sec dc-cream dc-miss" style="z-index:6" aria-labelledby="dc-miss-h">
    <div class="dc-wrap">
      <div class="dc-col dc-miss-t dc-rv">
        <h2 id="dc-miss-h" class="dc-h2 dc-bal">When a piece is missing, we ask for it.</h2>
        <p>We never guess. We email your accountant, bank or supplier for you, and keep you in copy.</p>
        <a href="#demo" class="dc-more">See how it works <span class="dc-arrow" aria-hidden="true">→</span></a>
      </div>
      <div class="dc-miss-a dc-io">
        <svg viewBox="80 80 440 440" role="img" aria-label="Eight puzzle pieces come together around one missing piece">
          <path class="dc-ants" d="M240 240L286 240C286 246 280 250 280 258C280 270 320 270 320 258C320 250 314 246 314 240L360 240L360 286C366 286 370 280 378 280C390 280 390 320 378 320C370 320 366 314 360 314L360 360L314 360C314 354 320 350 320 342C320 330 280 330 280 342C280 350 286 354 286 360L240 360L240 314C234 314 230 320 222 320C210 320 210 280 222 280C230 280 234 286 240 286L240 240Z" fill="#fff" stroke="#E58A4A" stroke-width="2.5" stroke-dasharray="9 7"/>
          <g class="dc-fly" style="--dx:-170px;--dy:-170px;--rot:24deg;--d:0.00s"><path d="M120 120L166 120C166 126 160 130 160 138C160 150 200 150 200 138C200 130 194 126 194 120L240 120L240 166C246 166 250 160 258 160C270 160 270 200 258 200C250 200 246 194 240 194L240 240L194 240C194 234 200 230 200 222C200 210 160 210 160 222C160 230 166 234 166 240L120 240L120 194C114 194 110 200 102 200C90 200 90 160 102 160C110 160 114 166 120 166L120 120Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:0px;--dy:-170px;--rot:-24deg;--d:0.10s"><path d="M240 120L286 120C286 114 280 110 280 102C280 90 320 90 320 102C320 110 314 114 314 120L360 120L360 166C354 166 350 160 342 160C330 160 330 200 342 200C350 200 354 194 360 194L360 240L314 240C314 246 320 250 320 258C320 270 280 270 280 258C280 250 286 246 286 240L240 240L240 194C246 194 250 200 258 200C270 200 270 160 258 160C250 160 246 166 240 166L240 120Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:170px;--dy:-170px;--rot:24deg;--d:0.20s"><path d="M360 120L406 120C406 126 400 130 400 138C400 150 440 150 440 138C440 130 434 126 434 120L480 120L480 166C486 166 490 160 498 160C510 160 510 200 498 200C490 200 486 194 480 194L480 240L434 240C434 234 440 230 440 222C440 210 400 210 400 222C400 230 406 234 406 240L360 240L360 194C354 194 350 200 342 200C330 200 330 160 342 160C350 160 354 166 360 166L360 120Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:-170px;--dy:0px;--rot:-24deg;--d:0.30s"><path d="M120 240L166 240C166 234 160 230 160 222C160 210 200 210 200 222C200 230 194 234 194 240L240 240L240 286C234 286 230 280 222 280C210 280 210 320 222 320C230 320 234 314 240 314L240 360L194 360C194 366 200 370 200 378C200 390 160 390 160 378C160 370 166 366 166 360L120 360L120 314C126 314 130 320 138 320C150 320 150 280 138 280C130 280 126 286 120 286L120 240Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:170px;--dy:0px;--rot:24deg;--d:0.40s"><path d="M360 240L406 240C406 234 400 230 400 222C400 210 440 210 440 222C440 230 434 234 434 240L480 240L480 286C474 286 470 280 462 280C450 280 450 320 462 320C470 320 474 314 480 314L480 360L434 360C434 366 440 370 440 378C440 390 400 390 400 378C400 370 406 366 406 360L360 360L360 314C366 314 370 320 378 320C390 320 390 280 378 280C370 280 366 286 360 286L360 240Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:-170px;--dy:170px;--rot:-24deg;--d:0.50s"><path d="M120 360L166 360C166 366 160 370 160 378C160 390 200 390 200 378C200 370 194 366 194 360L240 360L240 406C246 406 250 400 258 400C270 400 270 440 258 440C250 440 246 434 240 434L240 480L194 480C194 474 200 470 200 462C200 450 160 450 160 462C160 470 166 474 166 480L120 480L120 434C114 434 110 440 102 440C90 440 90 400 102 400C110 400 114 406 120 406L120 360Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:0px;--dy:170px;--rot:24deg;--d:0.60s"><path d="M240 360L286 360C286 354 280 350 280 342C280 330 320 330 320 342C320 350 314 354 314 360L360 360L360 406C354 406 350 400 342 400C330 400 330 440 342 440C350 440 354 434 360 434L360 480L314 480C314 486 320 490 320 498C320 510 280 510 280 498C280 490 286 486 286 480L240 480L240 434C246 434 250 440 258 440C270 440 270 400 258 400C250 400 246 406 240 406L240 360Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
          <g class="dc-fly" style="--dx:170px;--dy:170px;--rot:-24deg;--d:0.70s"><path d="M360 360L406 360C406 366 400 370 400 378C400 390 440 390 440 378C440 370 434 366 434 360L480 360L480 406C486 406 490 400 498 400C510 400 510 440 498 440C490 440 486 434 480 434L480 480L434 480C434 474 440 470 440 462C440 450 400 450 400 462C400 470 406 474 406 480L360 480L360 434C354 434 350 440 342 440C330 440 330 400 342 400C350 400 354 406 360 406L360 360Z" fill="url(#dc-gk)" stroke="rgba(70,12,90,0.25)" stroke-width="1.5" stroke-linejoin="round"/></g>
        </svg>
      </div>
    </div>
  </section>

  <section id="pricing" class="dc-sheet dc-sec dc-white dc-price-sec" style="position:relative;z-index:7" aria-label="Results and pricing">
    <div class="dc-wrap dc-col">
      <div class="dc-nums">
        <p class="dc-rv"><span class="dc-num" data-count="81">81</span><span class="dc-num-l">formulas restored from the client's own files</span></p>
        <p class="dc-rv" style="--d:0.12s"><span class="dc-num">0</span><span class="dc-num-l">mismatches on an independent check</span></p>
        <p class="dc-rv" style="--d:0.24s"><span class="dc-num" data-count="29" data-suffix="/29">29/29</span><span class="dc-num-l">invoices matched to the cent</span></p>
      </div>
      <div class="dc-plans">
        <div class="dc-plan dc-rv"><h3>Checkup</h3><span class="dc-plan-p">Free</span><p>Leaked keys, risky packages, and whether your files could be recovered if lost.</p></div>
        <div class="dc-plan dc-plan-dark dc-rv" style="--d:0.1s"><h3>Recovery</h3><span class="dc-plan-p">from $450</span><p>A fixed quote before any work starts. It never goes up without your OK.</p></div>
        <div class="dc-plan dc-rv" style="--d:0.2s"><h3>Trace-back</h3><span class="dc-plan-p">from $2,000</span><p>From a recall back to the farm, with records requests sent for you.</p></div>
      </div>
      <div id="start" class="dc-ask dc-rv">
        <div class="dc-col dc-ask-t">
          <h2 class="dc-h2" id="dc-ask-h">Tell us what you <em>lost.</em></h2>
          <p>Free estimate now. You approve the final quote before any work starts.</p>
        </div>
        <form id="dc-form" class="dc-form" action="/api/tickets" method="post" novalidate aria-labelledby="dc-ask-h">
          <fieldset class="dc-fs">
            <legend>What did you lose?</legend>
            <div class="dc-chips">
              <label class="dc-chipw"><input class="dc-vh" type="radio" name="kind" value="excel" data-pick="sheet" data-price="$450" checked><span class="dc-chip">Spreadsheet</span></label>
              <label class="dc-chipw"><input class="dc-vh" type="radio" name="kind" value="code" data-pick="code" data-price="$450"><span class="dc-chip">Code</span></label>
              <label class="dc-chipw"><input class="dc-vh" type="radio" name="kind" value="other" data-pick="trace" data-price="$2,000"><span class="dc-chip">Food trace-back</span></label>
              <label class="dc-chipw"><input class="dc-vh" type="radio" name="kind" value="other" data-pick="other" data-price=""><span class="dc-chip">Something else</span></label>
            </div>
          </fieldset>
          <div class="dc-two">
            <div class="dc-fg"><label for="dc-name">Your name</label><input class="dc-field" id="dc-name" name="name" autocomplete="name" maxlength="120" required aria-describedby="dc-name-e"><span class="dc-ferr" id="dc-name-e"></span></div>
            <div class="dc-fg"><label for="dc-email">Work email</label><input class="dc-field" id="dc-email" name="email" type="email" autocomplete="email" maxlength="254" required placeholder="you@company.com" aria-describedby="dc-email-e"><span class="dc-ferr" id="dc-email-e"></span></div>
            <div class="dc-fg"><label for="dc-company">Company <span class="dc-hint">(optional)</span></label><input class="dc-field" id="dc-company" name="company" autocomplete="organization" maxlength="160"></div>
            <div class="dc-fg"><label for="dc-env">Where do you use it?</label><select class="dc-field" id="dc-env" name="environment">
              <option value="">Not sure</option>
              <option value="excel_desktop_windows">Excel on Windows</option>
              <option value="excel_desktop_mac">Excel on Mac</option>
              <option value="excel_web">Excel on the web</option>
              <option value="google_sheets">Google Sheets</option>
              <option value="codebase">A code repository</option>
              <option value="other">Other</option>
            </select></div>
          </div>
          <div class="dc-fg"><label for="dc-desc">What happened? <span class="dc-hint">What's missing, roughly when, and what still survives.</span></label><textarea class="dc-field" id="dc-desc" name="description" maxlength="4900" required aria-describedby="dc-desc-e"></textarea><span class="dc-ferr" id="dc-desc-e"></span></div>
          <div class="dc-hp" aria-hidden="true"><label for="dc-website">Leave this empty</label><input id="dc-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
          <div class="dc-fg">
            <label class="dc-check"><input type="checkbox" id="dc-consent" name="consent" required aria-describedby="dc-consent-e"><span>You may email me about this request.</span></label>
            <span class="dc-ferr" id="dc-consent-e"></span>
          </div>
          <div class="dc-go">
            <span class="dc-quote" id="dc-quote"><span class="dc-quote-l" id="dc-quote-l">Quote, from</span><span class="dc-quote-p" id="dc-quote-p">$450</span></span>
            <button type="submit" class="dc-btn" id="dc-send"><span id="dc-send-t">Get my free estimate</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
          </div>
          <div class="dc-msg dc-bad" id="dc-err" role="alert"></div>
          <div class="dc-msg dc-ok" id="dc-ok" role="status"></div>
        </form>
      </div>
    </div>
  </section>
</main>

<footer class="dc-foot">
  <div class="dc-foot-in">
    <span class="dc-foot-b"><svg width="22" height="22" viewBox="-72 -72 144 144" aria-hidden="true" focusable="false"><use href="#dc-logo" fill="url(#dc-logo-g)"/></svg>Data Care</span>
    <nav aria-label="Footer">
      <a href="/board">Live board</a>
      <a href="/case">Track a case</a>
      <a href="/download">Download for Mac</a>
    </nav>
  </div>
</footer>
</div>
<script>
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  var each = function (list, fn) { Array.prototype.forEach.call(list, fn); };
  var $ = function (id) { return doc.getElementById(id); };
  var reduce = true;
  try { reduce = !window.matchMedia('(prefers-reduced-motion: no-preference)').matches; } catch (e) {}

  // Stacked sheets: each one sticks once its whole height has been on screen.
  var stacks = doc.querySelectorAll('.dc-stack');
  var measure = function () { each(stacks, function (s) { s.style.setProperty('--h', s.offsetHeight + 'px'); }); };
  measure();
  if ('ResizeObserver' in window) {
    var ro = new ResizeObserver(measure);
    each(stacks, function (s) { ro.observe(s); });
  } else {
    window.addEventListener('resize', measure);
  }

  // Scroll reveals and count-ups. The head script adds dc-anim only when motion is welcome.
  if (root.classList.contains('dc-anim')) {
    var count = function (el) {
      var to = Number(el.getAttribute('data-count')), suf = el.getAttribute('data-suffix') || '', t0 = 0;
      var tick = function (now) {
        if (!t0) t0 = now;
        var p = Math.min(1, (now - t0) / 1400);
        el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))) + suf;
        if (p < 1) requestAnimationFrame(tick);
      };
      el.textContent = '0' + suf;
      requestAnimationFrame(tick);
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add('is-in');
        io.unobserve(en.target);
        each(en.target.querySelectorAll('[data-count]'), count);
      });
    }, { threshold: 0.2 });
    each(doc.querySelectorAll('.dc-rv, .dc-io'), function (el) { io.observe(el); });
  }

  // Marquee: a card focused by keyboard is scrolled into view; put the strip back afterwards.
  var mq = doc.querySelector('.dc-mq');
  if (mq) mq.addEventListener('focusout', function () { mq.scrollLeft = 0; });

  // Mini demo: one step every 1.4 s while it is on screen; with reduced motion it waits for Replay.
  var D = {"vals":[["1,240","1,310","1,405","1,520"],["702","735","781","842"],["538","575","624","678"],["412","421","436","451"],["126","154","188","227"],["10.2%","11.8%","13.4%","14.9%"]],"bad":{"2-2":["#VALUE!",1],"4-2":["",2],"4-3":["#REF!",3],"5-1":["",4],"5-3":["#VALUE!",4]},"ev":[[0,"Forensics","Opened a sealed copy of alderbank_q3_model.xlsx. 6 cells damaged, nothing unsafe."],[1,"Context","Q3 gross profit: the formula is in the CFO’s notes."],[2,"Context","Q3 operating income: found in your ERP export."],[3,"Context","Q4 operating income: found in the board report."],[4,"Reconstruction","Q2 and Q4 margin: restored as income ÷ revenue, then tested."],[5,"Recovery Manager","Q1 operating expenses are in none of your files. Emailed Priya Shah, your accountant."],[7,"Priya Shah","“Q1 opex was $412k.” Filled in and linked to her email."],[8,"Validation","Checked every value against your numbers: 0 mismatches."]],"who":{"Forensics":"#9944CA","Context":"#FC7D36","Reconstruction":"#F56263","Recovery Manager":"#141414","Priya Shah":"#6D35CF","Validation":"#13795B"}};
  var demo = $('dc-demo');
  if (demo) {
    var cells = demo.querySelectorAll('tbody td');
    var feed = $('dc-feed'), stat = $('dc-dstatus'), prog = $('dc-dprog');
    var pills = doc.querySelectorAll('.dc-pill[data-t]');
    var STEPS = [[0, 0], [1, 4], [5, 7], [8, 99]];
    var sec = demo.closest('section');
    var t = reduce ? 8 : 0, playing = !reduce, loop = !reduce;
    var state = function (r, c) {
      var key = r + '-' + c, v = D.vals[r][c], st = '', fx = '', bad = D.bad[key];
      if (bad) {
        if (t < bad[1]) { v = bad[0]; st = 'c-bad'; } else { st = 'c-fix'; fx = 'dc-fixed'; }
      }
      if (key === '3-0') {
        if (t < 5) { v = ''; st = 'c-hole'; }
        else if (t < 7) { v = 'Asked'; st = 'c-ask'; fx = 'dc-asking'; }
        else { st = 'c-asked'; fx = 'dc-asked'; }
      }
      if (t >= 8) fx = 'dc-okc';
      return [v, (st + ' ' + fx).trim()];
    };
    var status = function () {
      return t < 1 ? ['Scanning', '#F3EEE9', '#4A4A4A'] : t < 5 ? ['Finding pieces', '#FFF1E4', '#8A3409']
        : t < 7 ? ['Waiting on Priya', '#F4EEFF', '#5B2BB0'] : t < 8 ? ['Checking', '#FFF1E4', '#8A3409']
        : ['Recovered', '#E6F4EE', '#0F5F47'];
    };
    var render = function () {
      each(cells, function (td, i) {
        var s = state(Math.floor(i / 4), i % 4);
        if (td.textContent !== s[0]) td.textContent = s[0];
        if (td.className !== s[1]) td.className = s[1];
      });
      var st = status();
      stat.textContent = st[0];
      stat.style.background = st[1];
      stat.style.color = st[2];
      prog.style.width = Math.min(100, Math.round((t / 8) * 100)) + '%';
      // Every update keeps its row (later ones hidden), so the panel never changes height.
      each(feed.children, function (li, k) {
        var on = D.ev[k][0] <= t, future = li.classList.contains('is-future');
        if (on && future) { li.classList.remove('is-future'); li.classList.add('dc-new'); }
        if (!on && !future) { li.classList.add('is-future'); li.classList.remove('dc-new'); }
        li.classList.toggle('is-last', on && (k === D.ev.length - 1 || D.ev[k + 1][0] > t));
      });
      each(pills, function (p, k) { p.setAttribute('aria-pressed', t >= STEPS[k][0] && t <= STEPS[k][1] ? 'true' : 'false'); });
    };
    // On screen means: inside the viewport and not covered by the next stacked sheet.
    var onScreen = function () {
      var r = demo.getBoundingClientRect(), vh = window.innerHeight || root.clientHeight;
      var next = sec && sec.nextElementSibling, cover = next ? next.getBoundingClientRect().top : vh;
      var seen = Math.min(r.bottom, vh, cover) - Math.max(r.top, 0);
      return seen >= Math.min(r.height, vh) * 0.25;
    };
    setInterval(function () {
      if (!playing || doc.hidden || !onScreen()) return;
      t = t >= 13 ? 0 : t + 1;
      if (!loop && t >= 8) playing = false;
      render();
    }, 1400);
    var drive = function () { feed.setAttribute('aria-live', 'polite'); };
    each(pills, function (p) {
      p.addEventListener('click', function () { t = Number(p.getAttribute('data-t')); drive(); render(); });
    });
    $('dc-replay').addEventListener('click', function () { t = 0; playing = true; drive(); render(); });
    render();
  }

  // Request form: same fields and API as /tickets.
  var form = $('dc-form');
  if (form && window.fetch && window.JSON) {
    var EMAIL = /^[^\\s@<>"']{1,64}@[^\\s@<>"']{1,190}\\.[a-z]{2,24}$/i;
    var nameEl = $('dc-name'), emailEl = $('dc-email'), coEl = $('dc-company'), envEl = $('dc-env');
    var descEl = $('dc-desc'), hpEl = $('dc-website'), consentEl = $('dc-consent');
    var send = $('dc-send'), sendT = $('dc-send-t'), okBox = $('dc-ok'), errBox = $('dc-err');
    var quote = $('dc-quote'), quoteL = $('dc-quote-l'), quoteP = $('dc-quote-p');
    var picked = function () { return form.querySelector('input[name="kind"]:checked'); };
    var showPrice = function () {
      var c = picked(), p = c ? c.getAttribute('data-price') : '';
      quote.classList.toggle('is-ask', !p);
      quoteL.textContent = p ? 'Quote, from' : '';
      quoteP.textContent = p || 'Quote after a few questions';
    };
    each(form.querySelectorAll('input[name="kind"]'), function (r) { r.addEventListener('change', showPrice); });
    each(doc.querySelectorAll('a[data-choose]'), function (a) {
      a.addEventListener('click', function () {
        var r = form.querySelector('input[data-pick="' + a.getAttribute('data-choose') + '"]');
        if (r) { r.checked = true; showPrice(); }
      });
    });
    var fields = [nameEl, emailEl, descEl, consentEl];
    var mark = function (el, msg) {
      if (msg) el.setAttribute('aria-invalid', 'true'); else el.removeAttribute('aria-invalid');
      $(el.id + '-e').textContent = msg || '';
    };
    fields.forEach(function (el) {
      el.addEventListener(el === consentEl ? 'change' : 'input', function () {
        if (el.getAttribute('aria-invalid') === 'true') mark(el, '');
      });
    });
    var tidy = function (s) {
      s = String(s || '').trim();
      if (!s) return '';
      s = s.charAt(0).toUpperCase() + s.slice(1);
      return /[.!?]$/.test(s) ? s : s + '.';
    };
    var OK_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#13795B" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
    var busy = false;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (busy) return;
      errBox.textContent = '';
      okBox.textContent = '';
      var c = picked(), desc = descEl.value.trim(), firstBad = null;
      [
        [nameEl, !nameEl.value.trim(), 'Please tell us your name.'],
        [emailEl, !EMAIL.test(emailEl.value.trim()), 'Use an email like name@company.com.'],
        [descEl, desc.length < 20, 'Describe what was lost in at least a sentence (20 characters).'],
        [consentEl, !consentEl.checked, 'Please agree that we may email you about this request.']
      ].forEach(function (k) {
        mark(k[0], k[1] ? k[2] : '');
        if (k[1] && !firstBad) firstBad = k[0];
      });
      if (!c) {
        errBox.textContent = 'Pick what you lost: a spreadsheet, code, or something else.';
        firstBad = firstBad || form.querySelector('input[name="kind"]');
      }
      if (firstBad) { firstBad.focus(); return; }
      var body = {
        name: nameEl.value.trim(),
        email: emailEl.value.trim(),
        company: coEl.value.trim(),
        kind: c.value,
        environment: envEl.value,
        description: ((c.getAttribute('data-pick') === 'trace' ? 'Food trace-back: ' : '') + desc).slice(0, 5000),
        website: hpEl.value,
        consent: consentEl.checked
      };
      busy = true;
      send.disabled = true;
      send.setAttribute('aria-busy', 'true');
      sendT.textContent = 'Sending...';
      fetch(form.getAttribute('action'), {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body)
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (out) {
          if (res.ok) {
            okBox.innerHTML = OK_ICON + '<div><p></p><p>Your quote comes from <strong>datacare-recover@agentmail.to</strong>.</p></div>';
            okBox.querySelector('p').textContent = out.message || 'Thanks. We will email you a quote soon.';
            form.reset();
            showPrice();
          } else {
            errBox.textContent = tidy(out.error) || (res.status === 413
              ? 'That is too long. Please shorten the description.'
              : 'Something went wrong. Please try again.');
          }
        });
      }).catch(function () {
        errBox.textContent = "We couldn't reach the server. Please try again in a minute.";
      }).then(function () {
        busy = false;
        send.disabled = false;
        send.removeAttribute('aria-busy');
        sendT.textContent = 'Get my free estimate';
      });
    });
    showPrice();
  }
})();
</script>
</body>
</html>
`;
