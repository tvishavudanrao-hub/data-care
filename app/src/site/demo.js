// Demo mode: a walkthrough of the client's whole journey that runs entirely in the browser.
// Nothing is sent, no account is connected, no agent runs and no database is touched, so it works
// even when Naive is at capacity. Entry points: /?demo=1#start (the real home page, whose form opens
// this walkthrough instead of creating a ticket) and /demo directly.
// The data is our synthetic demo company (data/public/); the results are the ones our real runs
// produced on that data (docs/demo-script.md). Client-typed text is only ever set with textContent.

import { BRAND_CSS, HEADER, FOOTER } from "../tickets/brand.js";

// Injected into the home page when the URL has ?demo: a banner, an "example" filler, and a submit
// handler (capture phase, so it runs before the page's own) that opens /demo instead of posting.
export const DEMO_HOME_SNIPPET = `
<div id="dc-demo-bar" role="note" style="position:relative;z-index:50;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:center;padding:10px 16px;background:#141414;color:#fff;font:500 14px/1.4 Inter,system-ui,sans-serif;text-align:center">
  <span><strong>Demo mode.</strong> The form below opens a walkthrough. Nothing is sent and no one is emailed.</span>
  <button type="button" id="dc-demo-fill" style="min-height:36px;padding:0 14px;border-radius:999px;border:1px solid #fff;background:transparent;color:#fff;font:600 13px Inter,system-ui,sans-serif;cursor:pointer">Fill in an example</button>
</div>
<script>
(function () {
  var bar = document.getElementById('dc-demo-bar');
  document.body.insertBefore(bar, document.body.firstChild);
  var $ = function (id) { return document.getElementById(id); };
  var form = $('dc-form');
  if (!form) return;
  var send = $('dc-send-t'); if (send) send.textContent = 'Start the demo';
  $('dc-demo-fill').addEventListener('click', function () {
    var k = form.querySelector('input[name="kind"][data-pick="sheet"]'); if (k) { k.checked = true; k.dispatchEvent(new Event('change', { bubbles: true })); }
    $('dc-name').value = 'Dana Okafor';
    $('dc-email').value = 'dana.okafor@alderbank.example.com';
    $('dc-company').value = 'Alderbank Outfitters';
    $('dc-env').value = 'excel_desktop_windows';
    $('dc-desc').value = 'Someone pasted values over every formula in our quarterly forecast model. Some cells show #REF! now. The ERP export, the Q3 board report and an email from our CFO about the discount rules still exist.';
    $('dc-consent').checked = true;
    location.hash = 'start';
    $('dc-send').focus();
  });
  var EMAIL = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
  document.addEventListener('submit', function (e) {
    if (e.target !== form) return;
    var c = form.querySelector('input[name="kind"]:checked');
    var ok = c && $('dc-name').value.trim() && EMAIL.test($('dc-email').value.trim()) &&
      $('dc-desc').value.trim().length >= 20 && $('dc-consent').checked;
    if (!ok) return; // let the page's own handler show what is missing; it stops before sending
    e.preventDefault(); e.stopPropagation();
    var data = { name: $('dc-name').value.trim(), email: $('dc-email').value.trim(), company: $('dc-company').value.trim(),
      pick: c.getAttribute('data-pick') || '', environment: $('dc-env').value, description: $('dc-desc').value.trim().slice(0, 2000) };
    try { sessionStorage.setItem('dc-demo', JSON.stringify(data)); } catch (err) {}
    location.href = '/demo';
  }, true);
})();
</script>`;

const DEMO_CSS = `
  main, .bar .in, .foot { max-width:760px; }
  .counts .chip { white-space:normal; }
  .demo-bar { background:#141414; color:#fff; font:500 14px/1.45 var(--sans); padding:10px 16px; text-align:center; }
  .demo-bar a { color:#fff; }
  .steps { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 20px; padding:0; list-style:none; }
  .steps li { font:600 .78rem/1 var(--sans); padding:7px 10px; border-radius:999px; border:1px solid var(--border); background:#fff; color:var(--body); }
  .steps li.on { background:var(--ink); color:#fff; border-color:var(--ink); }
  .steps li.done { color:var(--ok); border-color:#BFE3D2; background:var(--ok-bg); }
  .nav { display:flex; gap:10px; margin-top:20px; }
  .nav .btn { margin-top:0; }
  .nav .btn.secondary { flex:0 0 auto; width:auto; padding:12px 20px; }
  .mail { background:#fff; border:1px solid var(--border); border-radius:14px; overflow:hidden; }
  .mail .meta { padding:12px 18px; border-bottom:1px solid var(--border); font-size:.88rem; display:grid; gap:2px; }
  .mail .meta b { color:var(--ink); }
  .mail .stripe { height:6px; background:var(--grad); }
  .mail .body { padding:20px 22px; }
  .mail h2 { font:400 1.8rem/1.2 var(--serif); color:var(--ink); margin:4px 0 16px; }
  .mail table td:first-child { color:var(--body); width:40%; } .mail table td:last-child { color:var(--ink); font-weight:600; }
  .callout { margin:16px 0 4px; padding:14px 16px; border:1px solid var(--border); border-radius:12px; background:var(--page); color:var(--ink); font-weight:600; }
  .consent { max-width:440px; margin:0 auto; text-align:left; }
  .consent .who { display:flex; align-items:center; gap:10px; font-weight:600; color:var(--ink); }
  .consent ul { padding-left:20px; }
  .tag { display:inline-block; font:600 .72rem/1 var(--sans); letter-spacing:.06em; text-transform:uppercase; color:var(--accent); border:1px solid #F6D9BF; background:#FFF8F1; border-radius:999px; padding:5px 9px; }
  .timeline { list-style:none; margin:0; padding:0; display:grid; gap:10px; }
  .timeline li { background:#fff; border:1px solid var(--border); border-radius:12px; padding:14px 16px; opacity:.35; transition:opacity .3s; }
  .timeline li.on { opacity:1; }
  .timeline li b { color:var(--ink); display:flex; justify-content:space-between; gap:10px; }
  .timeline li b span { font-weight:600; font-size:.82rem; color:var(--ok); }
  .timeline li p { margin:6px 0 0; font-size:.94rem; }
  .counts { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:16px 0; }
  .counts div { background:#fff; border:1px solid var(--border); border-radius:12px; padding:12px 14px; }
  .counts b { display:block; font:400 2rem/1.1 var(--serif); color:var(--ink); }
  .pass { display:inline-block; font-weight:700; color:var(--ok); background:var(--ok-bg); border-radius:999px; padding:4px 12px; }
  .searching { display:flex; align-items:center; gap:10px; }
  .spin { width:18px; height:18px; border-radius:50%; border:3px solid var(--border); border-top-color:var(--accent); animation:sp 0.8s linear infinite; }
  @keyframes sp { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spin { animation:none; } .timeline li { transition:none; } }
`;

export const DEMO_HTML = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Data Care demo</title>
<link rel="icon" href="/favicon.svg">
<style>${BRAND_CSS}${DEMO_CSS}</style></head><body>
<div class="demo-bar" role="note"><strong>Demo mode:</strong> a simulated walkthrough with our synthetic demo company. Nothing is sent, no account is connected and no agent runs. Results shown are the ones our real runs produced on the same demo data. <a href="/#start">Send a real request</a></div>
${HEADER}
<main>
  <ol class="steps" id="steps" aria-label="Demo steps"></ol>
  <div id="stage" aria-live="polite"></div>
  <div class="nav"><button class="btn secondary" id="back" type="button">Back</button><button class="btn" id="next" type="button">Next</button></div>
  <p class="muted" style="margin-top:16px"><a href="#" id="restart">Restart the demo</a> · <a href="/?demo=1#start">Back to the home page (demo mode)</a></p>
</main>
${FOOTER}
<script>
(function () {
  var EXAMPLE = { name: 'Dana Okafor', email: 'dana.okafor@alderbank.example.com', company: 'Alderbank Outfitters', pick: 'sheet',
    environment: 'excel_desktop_windows',
    description: 'Someone pasted values over every formula in our quarterly forecast model. Some cells show #REF! now. The ERP export, the Q3 board report and an email from our CFO about the discount rules still exist.' };
  var t = EXAMPLE;
  try { var s = JSON.parse(sessionStorage.getItem('dc-demo') || 'null'); if (s && s.name) t = s; } catch (e) {}
  var code = t.pick === 'code';
  var asked = t.pick === 'trace' || t.pick === 'other';
  var first = (t.name || 'there').split(/\\s+/)[0];
  var ticketId = 'T-DEMO-' + Math.random().toString(36).slice(2, 7).toUpperCase();
  var provider = 'Microsoft 365 / OneDrive';

  // ------------------------------------------------------------ the demo company's files
  var FILES = code ? [
    ['invoicing.py', 'copied', 'invoicing'], ['invoices.csv', 'copied', 'invoices'], ['discounts.yml', 'copied', 'discount'],
    ['CHANGELOG_excerpt.md', 'copied', 'discount'], ['office_party.jpg', 'skipped', 'not a document type we search'],
    ['hiring_plan_2027.docx', 'skipped', 'no match with your case']
  ] : [
    ['alderbank_model_damaged.xlsx', 'copied', 'model, forecast'], ['alderbank_erp_export_2025Q1-2026Q3.csv', 'copied', 'export'],
    ['alderbank_board_report_Q3_2026.pdf', 'copied', 'board report'], ['Re: rebuilding the quarterly model.eml', 'copied', 'model, CFO'],
    ['team_offsite_photos.jpg', 'skipped', 'not a document type we search'], ['holiday_rota_2026.xlsx', 'skipped', 'no match with your case']
  ];
  var copied = FILES.filter(function (f) { return f[1] === 'copied'; }).length;

  var AGENTS = code ? [
    ['Forensics', 'Scanned the ' + copied + ' files with static checks only. Nothing was opened, imported or run. The discount logic in invoicing.py is missing.'],
    ['Context', 'Mapped the evidence: volume tiers from discounts.yml (3%, 6% and 9% at 100, 500 and 1,000 units, inclusive), the silver and gold loyalty bonus, the 10% cap on the combined rate (CHANGELOG, FIN-112), rounding half-up once, and 30 past invoices, one of them damaged.'],
    ['Reconstruction', 'Rebuilt the discount function from that evidence, then ran it inside the sandbox against the past invoices.'],
    ['Validation', 'Checked the rebuilt function against the real past invoices: 29 of 29 readable invoices match to the cent. The damaged invoice is reported as unresolved, not guessed.'],
    ['Delivery', 'Packaged the rebuilt code, the report and the invoice, and emailed them to you.']
  ] : [
    ['Forensics', 'Scanned the ' + copied + ' files with static checks only. Nothing was opened or run. Found formulas pasted over as values, a #REF! error and blank cells.'],
    ['Context', 'Mapped the evidence: units, prices and discounts per quarter from the ERP export; net revenue, margin and growth from the board report; and the rules from the CFO\\'s email (5% from 1,000 units, 10% from 2,500, on the whole quarter; COGS 38% of net revenue; round to the cent). One gap: Q1 2026 operating expenses have no surviving source.'],
    ['Reconstruction', 'Rebuilt the model\\'s formulas from that evidence, pointing at the Assumptions tab instead of typing numbers in. Left Q1 2026 operating expenses blank and flagged them, as the CFO asked.'],
    ['Validation', 'A separate agent changed the inputs (prices, units, discount thresholds, costs) and checked every cell to the cent against answers the rebuilder never saw. Passed on the first try.'],
    ['Delivery', 'Packaged the rebuilt workbook, the report and the invoice, and emailed them to you.']
  ];

  // ------------------------------------------------------------ helpers (text only, never innerHTML for client text)
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    for (var k in (attrs || {})) { if (k === 'text') n.textContent = attrs[k]; else if (k === 'cls') n.className = attrs[k]; else n.setAttribute(k, attrs[k]); }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function chip(label) {
    var cls = { 'recovered': 'recovered', 'reconstructed and tested': 'tested', 'reconstructed but untested': 'untested', 'unresolved': 'unresolved' }[label];
    return el('span', { cls: 'chip ' + cls, text: label.charAt(0).toUpperCase() + label.slice(1) });
  }
  function row(cells) { return el('tr', {}, cells.map(function (c) { return el('td', {}, [c]); })); }

  // ------------------------------------------------------------ steps
  var STEPS = [
    { name: 'Request', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'Request ' + ticketId }),
        el('h1', {}, ['We got your ', el('em', { text: 'request' })]),
        el('p', { cls: 'lead', text: 'This is what you sent from the form. In the live service, our Recovery Manager agent now writes you a tailored quote by email.' }));
      var tb = el('tbody');
      [['Name', t.name], ['Email', t.email], ['Company', t.company || '-'], ['What was lost', code ? 'Code' : asked ? (t.pick === 'trace' ? 'Food trace-back' : 'Something else') : 'Spreadsheet'], ['What happened', t.description]]
        .forEach(function (r) { tb.append(row([r[0], r[1]])); });
      s.append(el('div', { cls: 'card wrap' }, [el('table', {}, [tb])]));
      if (asked) s.append(el('p', { cls: 'muted', text: 'For this kind of request we quote on request. The rest of this demo follows a spreadsheet case.' }));
    } },
    { name: 'Quote email', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'A few minutes later, in your inbox' }));
      var tb = el('tbody');
      tb.append(row(['Service', code ? 'Code recovery' : 'Spreadsheet recovery']), row(['Price', '$450 (not to exceed)']));
      var link = el('a', { href: '#', text: 'Your personal link: connect your storage' }); link.onclick = function (e) { e.preventDefault(); go(2); };
      tb.append(row(['Your link', link]));
      s.append(el('div', { cls: 'mail' }, [
        el('div', { cls: 'stripe' }),
        el('div', { cls: 'meta' }, [el('span', {}, [el('b', { text: 'From: ' }), 'Data Care <datacare-recover@agentmail.to>']),
          el('span', {}, [el('b', { text: 'To: ' }), t.email]),
          el('span', {}, [el('b', { text: 'Subject: ' }), 'Your Data Care recovery request ' + ticketId + ': quote $450'])]),
        el('div', { cls: 'body' }, [
          el('p', { cls: 'kicker', text: 'Quote' }), el('h2', { text: 'Your quote for request ' + ticketId }),
          el('p', { text: 'Dear ' + first + ',' }),
          el('p', { text: code
            ? 'We rebuild missing logic only from what survives (records it produced, configs, logs, tests, older copies), then test it against real past outputs.'
            : 'We rebuild lost formulas only from what survives (exports, past reports, related sheets, emails that used the numbers), then test the model on inputs it never saw.' }),
          el('p', { text: 'Every item in the final report is labeled recovered, reconstructed and tested, reconstructed but untested, or unresolved. We never guess a value.' }),
          el('div', { cls: 'wrap' }, [el('table', {}, [tb])]),
          el('div', { cls: 'callout', text: 'To go ahead, open your personal link and connect your storage read-only. That approves this quote. We search it for the evidence ourselves, so there is nothing to attach.' })
        ])
      ]));
    } },
    { name: 'Connect', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'Request ' + ticketId + ' · ' + t.name }),
        el('h1', {}, ['Approve, and let us ', el('em', { text: 'find' }), ' your files']),
        el('p', { text: 'Instead of sending us files, connect your storage. Our agents search it for the evidence your ' + (code ? 'code' : 'spreadsheet') + ' was built from.' }));
      var ul = el('ul', { cls: 'promises' });
      [['Read-only.', ' We can\\'t change or delete anything.'], ['Only what matches your case', ' is copied. You see every file we looked at.'],
       ['Nothing is ever run.', ' Every file is scanned before anyone opens it.'], ['Access ends automatically', ' when your case is delivered, or the moment you press Disconnect.']]
        .forEach(function (p) { ul.append(el('li', {}, [el('strong', { text: p[0] }), p[1]])); });
      s.append(ul);
      ['Microsoft 365 / OneDrive', 'Google Drive', 'Dropbox', 'GitHub'].forEach(function (p) {
        var b = el('button', { cls: 'btn', type: 'button', text: 'Connect ' + p + ' (read-only)' });
        b.onclick = function () { provider = p; go(3); };
        s.append(b);
      });
      s.append(el('p', { cls: 'muted', text: 'By connecting, you approve the quote we emailed you.' }));
    } },
    { name: 'Allow', render: function (s) {
      s.append(el('p', {}, [el('span', { cls: 'tag', text: 'Simulated sign-in' })]));
      var allow = el('button', { cls: 'btn', type: 'button', text: 'Allow' }); allow.onclick = function () { go(4); };
      var cancel = el('button', { cls: 'btn secondary', type: 'button', text: 'Cancel' }); cancel.onclick = function () { go(2); };
      s.append(el('div', { cls: 'card consent' }, [
        el('p', { cls: 'muted', text: 'In the live service this is ' + provider + '\\'s own sign-in screen. You sign in there; Data Care never sees your password.' }),
        el('p', { cls: 'who', text: 'Data Care wants to:' }),
        el('ul', {}, [el('li', { text: 'See and download your files (read-only)' }), el('li', { text: 'See your email address' })]),
        el('p', { cls: 'muted', text: 'It cannot edit, delete or share anything.' }), allow, cancel
      ]));
    } },
    { name: 'What we read', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'Request ' + ticketId }), el('h1', {}, ['What we ', el('em', { text: 'read' })]));
      var wait = el('p', { cls: 'searching' }, [el('span', { cls: 'spin', 'aria-hidden': 'true' }), 'Searching your ' + provider + ' for files that match your case...']);
      s.append(wait);
      later(1400, function () {
        wait.remove();
        s.append(el('p', { text: 'Connected: ' + t.email + ' on ' + provider + ' (read-only). ' + copied + ' files copied for your case.' }));
        var tb = el('tbody');
        FILES.forEach(function (f) {
          var what = f[1] === 'copied' ? el('span', { cls: 'chip recovered', text: 'copied for your case' }) : el('span', { cls: 'muted', text: 'not copied: ' + f[2] });
          var tr = el('tr', {}, [el('td', { text: f[0], style: 'color:var(--ink);font-weight:500' }), el('td', {}, [what]), f[1] === 'copied' ? el('td', { 'data-k': 'Matched on', text: f[2] }) : el('td', {})]);
          tb.append(tr);
        });
        s.append(el('div', { cls: 'wrap card', style: 'padding:8px 12px' }, [el('table', { cls: 'stack' }, [
          el('thead', {}, [el('tr', {}, [el('th', { text: 'File' }), el('th', { text: 'What we did' }), el('th', { text: 'Matched on' })])]), tb])]));
        var dis = el('button', { cls: 'btn secondary', type: 'button', text: 'Disconnect now' });
        dis.onclick = function () { dis.textContent = 'Disconnected. Our access has ended (demo).'; dis.disabled = true; };
        s.append(dis);
      });
    } },
    { name: 'Agents at work', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'Case opened from request ' + ticketId }), el('h1', {}, ['Our agents ', el('em', { text: 'rebuild' }), ' it']),
        el('p', { cls: 'lead', text: 'No one on our team touches the case. Each agent hands its result to the next, and a wrong rebuild goes back at most three times.' }));
      var ol = el('ol', { cls: 'timeline' });
      var items = AGENTS.map(function (a) { var li = el('li', {}, [el('b', {}, [a[0], el('span', { text: '' })]), el('p', { text: a[1] })]); ol.append(li); return li; });
      s.append(ol);
      items.forEach(function (li, i) { later(700 * (i + 1), function () { li.className = 'on'; li.querySelector('b span').textContent = 'done'; }); });
    } },
    { name: 'Report', render: function (s) {
      s.append(el('p', { cls: 'kicker', text: 'Your recovery is ready' }), el('h1', {}, ['Your ', el('em', { text: 'report' })]),
        el('p', {}, ['Independent validation: ', el('span', { cls: 'pass', text: 'Passed' })]));
      if (code) {
        var tb = el('tbody');
        [['Volume discount tiers', 'reconstructed and tested'], ['Loyalty bonus', 'reconstructed and tested'], ['10% cap on the combined rate', 'reconstructed and tested'],
         ['Rounding (half-up, once)', 'reconstructed and tested'], ['The damaged invoice', 'unresolved']]
          .forEach(function (r) { tb.append(row([r[0], chip(r[1])])); });
        s.append(el('p', { text: '29 of 29 readable invoices match to the cent. The one damaged invoice is reported as unresolved instead of being invented.' }),
          el('div', { cls: 'wrap card', style: 'padding:8px 12px' }, [el('table', {}, [tb])]));
      } else {
        var c = el('div', { cls: 'counts' });
        [['27', 'recovered'], ['81', 'reconstructed and tested'], ['0', 'reconstructed but untested'], ['1', 'unresolved']]
          .forEach(function (x) { c.append(el('div', {}, [el('b', { text: x[0] }), chip(x[1])])); });
        s.append(c);
        var tb2 = el('tbody');
        [['Volume discount, every quarter', 'reconstructed and tested', 'CFO email rule 2 + ERP export'],
         ['Discount thresholds and rates (Assumptions tab)', 'recovered', 'Copied from the surviving cells'],
         ['Operating expenses, Q1 2026', 'unresolved', 'No surviving source; left blank as the CFO asked']]
          .forEach(function (r) { tb2.append(el('tr', {}, [el('td', { text: r[0] }), el('td', {}, [chip(r[1])]), el('td', { 'data-k': 'Why', text: r[2] })])); });
        s.append(el('div', { cls: 'wrap card', style: 'padding:8px 12px' }, [el('table', { cls: 'stack' }, [
          el('thead', {}, [el('tr', {}, [el('th', { text: 'Item' }), el('th', { text: 'Label' }), el('th', { text: 'Evidence' })])]), tb2])]));
      }
      s.append(el('p', { text: 'Invoice: $450, the quoted price. Our access to your ' + provider + ' ended when the case was delivered.' }),
        el('p', { cls: 'muted', text: 'A pass means the tested behaviour matches. It never claims the original was recovered word for word.' }));
    } }
  ];

  // ------------------------------------------------------------ engine
  var stage = document.getElementById('stage'), stepsEl = document.getElementById('steps');
  var back = document.getElementById('back'), next = document.getElementById('next');
  var cur = 0, timers = [];
  function later(ms, fn) { var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; timers.push(setTimeout(fn, reduce ? 0 : ms)); }
  function go(i) {
    timers.forEach(clearTimeout); timers = [];
    cur = Math.max(0, Math.min(STEPS.length - 1, i));
    stepsEl.textContent = '';
    STEPS.forEach(function (st, j) { stepsEl.append(el('li', { cls: j === cur ? 'on' : j < cur ? 'done' : '', text: (j + 1) + '. ' + st.name, 'aria-current': j === cur ? 'step' : 'false' })); });
    stage.textContent = '';
    STEPS[cur].render(stage);
    back.disabled = cur === 0;
    next.textContent = cur === STEPS.length - 1 ? 'Start over' : cur === 2 ? 'Connect Microsoft 365 / OneDrive' : cur === 3 ? 'Allow' : 'Next';
    window.scrollTo(0, 0);
  }
  next.onclick = function () { go(cur === STEPS.length - 1 ? 0 : cur + 1); };
  back.onclick = function () { go(cur - 1); };
  document.getElementById('restart').onclick = function (e) { e.preventDefault(); go(0); };
  go(0);
})();
</script>
</body></html>`;
