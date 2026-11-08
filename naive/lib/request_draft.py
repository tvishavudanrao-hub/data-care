#!/usr/bin/env python3
"""request_draft.py - Data Care requests to fill gaps (Python 3.8+, standard library only).

After a rebuild, turns every gap that is still open into one exact request and writes into --out-dir:
  requests.json  one entry per open gap or client question: kind, who it is for, the exact item, what it unlocks
  requests.md    one short email for the client (at most --max-asks items), sent by the Recovery Manager only
                 after a person approves it

    python3 request_draft.py --case C-0001 --rebuilt-dir rebuilt/ --evidence evidence.json
        [--context-gaps gaps.json] [--client "Acme Tools"] [--client-email cfo@acme.example] [--contact-name "Dana"]
        [--previous requests.json] [--round 2] [--out-dir rebuilt/]

Kinds: ask_client (a figure, file or answer the client keeps), client_forward (a request the client can send to
the bank, vendor or payroll provider that holds a document; Data Care never sends it), search_more (a search task
for the Mail Scout or Context), leave_unresolved (the client said it does not exist, or two rounds found nothing).
Rounds: round 1 takes the first place on each gap's ranked where_to_look list; round 2 asks again (or drafts a
request to the third party that holds it); after round 2 whatever is still open becomes leave_unresolved with
every place searched. With --previous the round is counted per gap and request ids stay the same.
It reads only JSON files, never opens the client's workbook, and never sends anything.
"""
import argparse
import json
import os
import re
from datetime import date

SECRET = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)(\s*[=:]\s*)\S+")
LONG_NUMBER = re.compile(r"(?<![\d.,])\d{9,19}(?![\d.,])")             # account or card numbers
CARD = re.compile(r"\b\d{4}(?:[ -]\d{4}){2,3}(?:[ -]\d{1,4})?\b")
CELL = r"(?:'[^']+'|[^\s!(),:;'\"]+)!\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?"
CELL_RE = re.compile(CELL)
REF1 = r"R(?:\[-?\d+\]|\d+)?C(?:\[-?\d+\]|\d+)?"
R1C1 = re.compile(r"(?<![A-Za-z0-9_.$!'])(?:(?P<sh>'[^']+'|[A-Za-z_][\w.]*)!)?(?P<a>%s)(?::(?P<b>%s))?(?![A-Za-z0-9_(\[])"
                  % (REF1, REF1))

# what a gap is, from its text (first match wins)
STATES = [
    ("internal", r"does not reproduce its surviving value"),
    ("choice", r"^client choice for"),
    ("known_missing", r"client says this figure is not available|raw input the client cannot supply"),
    ("conflict", r"^conflicting figures for|evidence value conflicts with surviving"),
    ("mismatch", r"the rebuilt model gives .+ but .+ reports"),
    ("override", r"differs from the row's rule|does not follow the rebuilt rule"),
    ("assumption", r"assumption cell is damaged"),
    ("no_reports", r"^no reported figures"),
    ("missing_file", r"is mentioned in .+ but is not in the case files|links to an external workbook|references sheet '"),
    ("unreadable", r"could not be (?:parsed|read)|does not parse|unreadable rows"),
    ("missing_code", r"^(?:function|module) `"),
    ("garbled", r"\bis garbled\b"),
    ("error", r"\bshows #|cell shows #"),
    ("blank", r"\bis blank\b|cell blank|input value was lost"),
]
SEVERITY = {"question": 0, "blank": 1, "error": 1, "garbled": 1, "assumption": 1, "receipt": 1, "conflict": 2,
            "mismatch": 2, "override": 2, "untested": 3, "missing_file": 4, "unreadable": 4, "missing_code": 4,
            "choice": 5, "no_reports": 6, "other": 6, "built_on_missing": 7}
STATE_WORDS = {"blank": "was blank", "error": "showed an error", "garbled": "was unreadable"}
# where an item may be: a place our agents can search, a document a third party holds, or something the client keeps
INTERNAL = re.compile(r"rules\.json|the inputs feeding|with a pdf tool|as fragments", re.I)
MAIL = re.compile(r"e-?mail|mailbox|inbox|\bthreads?\b|attachments?", re.I)
DRIVE = re.compile(r"shared drive|\bdrive\b|version history|folder .{0,40}came from|git (?:history|log)|repository|"
                   r"older (?:saved )?cop(?:y|ies)|older build|installed .{0,30}build|\.pyc|ci artifacts|coding-chat|"
                   r"case files", re.I)
THIRD = [(re.compile(r"\bbank\b", re.I), "bank"),
         (re.compile(r"credit card|card (?:statement|export)s?", re.I), "card issuer"),
         (re.compile(r"payroll (?:export|report|provider|register|records?)", re.I), "payroll provider"),
         (re.compile(r"\bvendors?\b|\bsuppliers?\b|duplicate (?:receipt|invoice)", re.I), "vendor"),
         (re.compile(r"\baccountant\b|\bbookkeeper\b", re.I), "accountant")]
DOCS = {"bank": ("a copy of my bank statement", "Copy of my bank statement"),
        "card issuer": ("a copy of my card statement", "Copy of my card statement"),
        "payroll provider": ("a copy of the payroll report", "Copy of the payroll report"),
        "vendor": ("a duplicate of the invoice or receipt", "Duplicate invoice or receipt"),
        "accountant": ("a copy of the ledger or trial balance", "Copy of the ledger or trial balance")}


def load(path, default):
    if not path:
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def clean(text):
    """Plain text: no secrets, no account numbers, no long dashes, one line."""
    text = SECRET.sub(r"\1\2[removed]", str(text if text is not None else ""))
    text = CARD.sub("[number removed]", LONG_NUMBER.sub("[number removed]", text))
    text = text.replace("\u2014", ", ").replace("\u2013", "-")
    return re.sub(r"\s+", " ", text).strip()


def norm(s):
    return " ".join(sorted(re.findall(r"[a-z0-9]+", str(s or "").lower())))


def as_list(x):
    return [] if x is None else [x] if isinstance(x, str) else list(x)


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def uses(n):
    return "%s that %s it" % (plural(n, "rebuilt cell"), "uses" if n == 1 else "use")


# ---------------------------------------------------------------- cells and dependencies
def col_n(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def cells_of(ref, cap=5000):
    """'Model!B5:I5' -> [('model', 5, 2), ...] (sheet lowercased)."""
    sh, _, rng = ref.rpartition("!")
    a, _, b = rng.replace("$", "").partition(":")
    m1, m2 = re.match(r"([A-Z]+)(\d+)$", a), re.match(r"([A-Z]+)(\d+)$", b or a)
    if not (m1 and m2):
        return []
    r1, r2 = sorted((int(m1.group(2)), int(m2.group(2))))
    c1, c2 = sorted((col_n(m1.group(1)), col_n(m2.group(1))))
    out = [(sh.strip("'").lower(), r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
    return out[:cap]


def rc(part, row, col):
    m = re.match(r"R(\[-?\d+\]|\d+)?C(\[-?\d+\]|\d+)?$", part)
    one = lambda tok, base: base if not tok else base + int(tok[1:-1]) if tok[0] == "[" else int(tok)
    return one(m.group(1), row), one(m.group(2), col)


class Model(object):
    """What the rebuild says about each cell: its label (report_items) and which rebuilt cells use it (rules)."""

    def __init__(self, rules, items):
        self.rev, self.rule_cells, self.state, self.name = {}, {}, {}, {}
        for r in rules or []:
            cells = [c for ref in as_list(r.get("cells")) for c in cells_of(ref)]
            self.rule_cells[r.get("rule_id")] = cells
            f = r.get("formula_r1c1") or ""
            refs = list(R1C1.finditer(f))
            for sh, row, col in cells:
                for m in refs:
                    psh = (m.group("sh") or sh).strip("'").lower()
                    r1, c1 = rc(m.group("a"), row, col)
                    r2, c2 = rc(m.group("b"), row, col) if m.group("b") else (r1, c1)
                    for rr in range(min(r1, r2), max(r1, r2) + 1):
                        for cc in range(min(c1, c2), max(c1, c2) + 1):
                            self.rev.setdefault((psh, rr, cc), set()).add((sh, row, col))
        parsed = []
        for it in items or []:
            text = str(it.get("item") or "")
            refs = [c for ref in CELL_RE.findall(text.split(" (")[0]) for c in cells_of(ref)]
            parsed.append((refs, it.get("label"), text))
        for refs, label, text in sorted(parsed, key=lambda p: -len(p[0])):   # a single-cell item overrides its range
            for c in refs:
                self.state[c] = label
            m = re.match(r"^.*?\((.*)\)\s*$", text)
            if len(refs) == 1 and m and ", " in m.group(1):
                self.name[refs[0]] = m.group(1).rsplit(", ", 1)

    def dependents(self, start):
        seen, todo = set(start), list(start)
        while todo:
            for d in self.rev.get(todo.pop(), ()):
                if d not in seen:
                    seen.add(d)
                    todo.append(d)
        return seen


# ---------------------------------------------------------------- reading gaps
def paren_after(text):
    """Content of the first balanced (...) in text."""
    i = text.find("(")
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(text)):
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j]
    return None


def parse_gap(g, origin):
    what, why = str(g.get("what") or ""), str(g.get("why") or "")
    it = {"gap_ids": [g["gap_id"]] if g.get("gap_id") else [], "what": what, "why_text": why, "origin": origin,
          "where": [str(w) for w in as_list(g.get("where_to_look") or g.get("search_hints"))],
          "label": None, "period": None, "cell": None, "file": None, "values": [], "state": "other"}
    for st, rx in STATES:
        if re.search(rx, what, re.I) or (st == "known_missing" and re.search(rx, why, re.I)):
            it["state"] = st
            break
    if g.get("amount") is not None and g.get("date"):                      # a money movement with no record
        it.update(state="receipt", amount=str(g["amount"]), date=str(g["date"]), payee=clean(g.get("description")))
        return it
    m = CELL_RE.search(what)
    if m and it["state"] != "choice":
        it["cell"] = m.group(0)
        before = what[:m.start()].rstrip(" (")
        if not before:                                                      # "Model!E9 (Label, Period) is blank"
            inner = paren_after(what[m.end():]) or ""
            lab, _, per = inner.rpartition(", ")
            it["label"] = lab if lab and lab != "no label" else None
            it["period"] = per if per and per != "no period" else None
        else:                                                               # "Label for Period (Model!E9): ..."
            lab, sep, per = before.rpartition(" for ")
            it["label"], it["period"] = (lab, per) if sep else (before, None)
        got = re.search(r"gives (\S+) but (\S+) reports (\S+)", what)
        if got:
            it["values"] = [(got.group(1), "the rebuilt model"), (got.group(3), got.group(2))]
        return it
    pats = [r"^(?P<label>.+), (?P<period>[^,:]+): the client says",
            r"^Conflicting figures for (?P<label>.+), (?P<period>[^,:]+): (?P<vals>.+)$",
            r"^No reported figures(?: \(.*?\))? for (?P<period>.+)$",
            r"^(?P<file>.+?) is mentioned in (?P<rel>.+?) \(line (?P<ln>\d+)\)",
            r"links to an external workbook '(?P<file>[^']+)'",
            r"references sheet '(?P<sheet>[^']+)', which is not in (?P<file>.+)$",
            r"^(?P<file>\S+) (?:could not be|does not parse|has \d+ unreadable)",
            r"`(?P<code>[^`]+)`",
            r"^client choice for (?P<label>.+) \((?P<rule>R-[\w-]+)\)"]
    for p in pats:
        mm = re.search(p, what, re.I)
        if mm:
            d = mm.groupdict()
            it["label"] = d.get("label") or d.get("code") or it["label"]
            per = d.get("period")
            it["period"] = None if not per or "any model period" in per else per
            it["file"], it["rel"], it["sheet"], it["rule_id"] = d.get("file"), d.get("rel"), d.get("sheet"), d.get("rule")
            if d.get("vals"):
                it["values"] = [(v.split(" (")[0].strip(), (paren_after(v) or "").split("#")[0])
                                for v in d["vals"].split("; ")]
            break
    return it


def keys_of(it):
    ks = []
    if it.get("cell"):
        ks.append("cell:" + it["cell"].replace("$", "").lower())
    if it.get("label") and it.get("period"):
        ks.append("lp:%s|%s" % (norm(it["label"]), norm(it["period"])))
    if it.get("rule_id") and it["state"] in ("question", "choice"):
        ks.append("rule:" + it["rule_id"])
    if it.get("file"):
        ks.append("file:" + it["file"].lower())
    if it["state"] == "receipt":
        ks.append("money:%s|%s|%s" % (it["date"], it["amount"], norm(it.get("payee"))))
    if not ks:
        ks.append("what:" + norm(it["what"]))
    return ks


def merge(items):
    """One item per thing missing: Context's gap and the engine's gap for the same cell or figure become one."""
    out, index = [], {}
    for it in items:
        hit = next((index[k] for k in keys_of(it) if k in index), None)
        if hit is None:
            out.append(it)
            hit = it
        else:
            hit["gap_ids"] += [g for g in it["gap_ids"] if g not in hit["gap_ids"]]
            hit["where"] += [w for w in it["where"] if w not in hit["where"]]
            for f in ("cell", "label", "period", "file", "km"):
                hit[f] = hit.get(f) or it.get(f)
            if it["state"] == "known_missing" or SEVERITY.get(it["state"], 6) < SEVERITY.get(hit["state"], 6) \
                    and hit["state"] != "known_missing":
                hit["state"] = it["state"]
        for k in keys_of(hit):
            index.setdefault(k, hit)
    return out


# ---------------------------------------------------------------- choosing the request
def classify(place):
    s = place.lower()
    if INTERNAL.search(s):
        return "internal", None
    if MAIL.search(s):
        return "search", "mail-scout"
    if DRIVE.search(s):
        return "search", "context"
    hits = [(m.start(), role) for rx, role in THIRD for m in [rx.search(s)] if m]
    return ("third", min(hits)[1]) if hits else ("client", "client")


def choose(places, rnd, prev=None):
    """(kind, place, to) for a gap in round rnd (1 or 2). places: [(text, class, role)] in where_to_look order."""
    as_kind = lambda p: ({"search": "search_more", "client": "ask_client", "third": "client_forward"}[p[1]], p[0], p[2])
    first = as_kind(places[0]) if places else ("ask_client", None, "client")
    if rnd <= 1:
        return first
    asked = [p for p in places if p[1] != "search"]      # round 1 (or the Mail Scout pass) already searched
    prev = prev or first
    if prev[0] == "ask_client":                          # the client did not have it: draft a request to the source
        third = [p for p in asked if p[1] == "third"]
        return as_kind(third[0]) if third else prev
    if prev[0] == "client_forward":
        return prev
    return as_kind(asked[0]) if asked else ("ask_client", None, "client")


def terms_of(it):
    t = []
    for w in it["where"]:
        t += re.findall(r"search '([^']+)'", w) + re.findall(r'search for "([^"]+)"', w)
    if it.get("file"):
        t.append(it["file"])
    if it["state"] == "no_reports" and it.get("period"):
        t += ["%s %s" % (w, it["period"]) for w in ("board report", "management accounts", "investor update")]
    if it.get("label") and it["state"] not in ("missing_file",):
        t.append(" ".join(x for x in (it["label"], it.get("period")) if x))
    seen, out = set(), []
    for x in t:
        x = clean(x)
        if x and x.lower() != "none" and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out[:4]


def for_client(place):
    """Agent wording -> client wording: 'the client's sales export (it has ...)' -> 'your sales export'."""
    p = re.sub(r"\s*\((?:it has|search|check|they said)[^)]*\)", "", place or "")
    p = re.sub(r"\bthe client's\b", "your", p, flags=re.I)
    p = re.sub(r"^the\s+", "your ", p.strip(), flags=re.I)
    return clean(p)


def nice_date(s):
    try:
        d = date.fromisoformat(str(s)[:10])
        return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
    except ValueError:
        return clean(s)


def money(s):
    s = clean(s)
    try:
        return "$" + "{:,.2f}".format(abs(float(s.replace(",", "").lstrip("$"))))
    except ValueError:
        return s


def what_item(it):
    """The exact item, in the client's words."""
    if it["state"] == "question":
        return "Question about %s" % clean(it.get("label") or "a rule in your model")
    if it["state"] == "receipt":
        return "The receipt or invoice for %s paid to %s on %s" % (money(it["amount"]), it.get("payee") or "this payee",
                                                                  nice_date(it["date"]))
    if it["state"] == "missing_file" and it.get("file"):
        return "The file %s" % clean(it["file"])
    if it["state"] == "unreadable" and it.get("file"):
        return "A fresh copy of %s" % clean(it["file"])
    if it["state"] == "no_reports":
        return "A board report or management accounts for %s" % clean(it.get("period") or "each period of the model")
    s = clean(it.get("label") or it["what"].split(":")[0])
    if it.get("period"):
        s += " for %s" % clean(it["period"])
    if it.get("cell"):
        s += " (cell %s)" % clean(it["cell"])
    return s


def ask_body(it, place, repeat):
    head = what_item(it)
    eg = (", for example from %s" % for_client(place)) if place and not re.match(r"^ask\b", place, re.I) \
        and for_client(place).lower() not in ("you", "your") else ""
    st = it["state"]
    if st == "question":
        opts = " ".join("Option %d: %s." % (k + 1, clean(o).rstrip(".")) for k, o in enumerate(it.get("options") or []))
        body = "%s %s Please reply with the option number." % (clean(it.get("question")), opts)
    elif st == "untested":
        body = "%s. The cell %s; we rebuilt it from your other figures, but nothing you sent lets us check it. " \
               "Please send the figure%s, so we can confirm it." % (head, STATE_WORDS.get(it.get("was"), "was lost"), eg)
    elif st in STATE_WORDS:
        body = "%s. The cell %s and nothing you sent has this figure. Please send it%s." % (head, STATE_WORDS[st], eg)
    elif st == "assumption":
        body = "%s. This assumption was damaged and nothing you sent gives its value. Please send it%s." % (head, eg)
    elif st == "conflict" and it["values"]:
        vals = " and ".join("%s in %s" % (clean(v), clean(s) or "one file") for v, s in it["values"][:3])
        body = "%s. We found different figures: %s. Which one is right?" % (head, vals)
    elif st == "conflict":
        body = "%s. The figure in your exports does not fit the rest of the model. Which figure is right?" % head
    elif st == "mismatch" and it["values"]:
        (got, _), (rep, src) = it["values"][:2]
        body = "%s. %s reports %s, but the rebuilt model gives %s. Was that report changed later, or did an input " \
               "change?" % (head, clean(src.split("#")[0]), clean(rep), clean(got))
    elif st == "override":
        body = "%s does not follow the rule the rest of its row uses. Did you type this figure in on purpose, as a " \
               "one-off adjustment?" % head
    elif st == "missing_file":
        body = "%s%s. Please send it if you have it." % (
            head, (", which %s mentions" % clean(it["rel"])) if it.get("rel") else
            (", which still has the sheet '%s'" % clean(it["sheet"])) if it.get("sheet") else "")
    elif st == "unreadable":
        body = "%s: the copy we have could not be read." % head
    elif st == "no_reports":
        body = "%s, if you have them. They let us check the rebuilt %s figures against your own totals." % (
            head, clean(it.get("period") or ""))
    elif st == "receipt":
        body = "%s. Your bank shows this payment, but we found no receipt or record for it." % head
    elif st == "missing_code":
        body = "%s: any copy you have (an older build, a backup or the project repository)." % head
    else:
        body = "%s. If you have it, please send it%s." % (head, eg)
    return ("Second request. " if repeat else "") + re.sub(r"\.\.", ".", body)


def forward_draft(it, place, role, client, contact):
    """The client's own message to the bank, vendor or payroll provider. Data Care never sends it."""
    doc, title = DOCS.get(role, ("a copy of the document", "Copy of a document"))
    when = ""
    if it["state"] == "receipt":
        when = " for the payment of %s on %s" % (money(it["amount"]), nice_date(it["date"]))
    elif it.get("period"):
        when = " for %s" % clean(it["period"])
    acct = " (account: [your account number])" if role in ("bank", "card issuer") else ""
    sign = "\n".join(x for x in (clean(contact) if contact else "[your name]", clean(client) if client else "") if x)
    subject = "%s%s" % (title, when)
    body = "Hello,\n\nCould you please send me %s%s%s? I need it to complete my company's records.\n\nThank you,\n%s" % (
        doc, when, acct, sign)
    return subject, body


# ---------------------------------------------------------------- main logic
def collect(rebuilt_dir, evidence_path, context_gaps_path, extra_gaps):
    d = lambda name, default: load(os.path.join(rebuilt_dir, name), default) if rebuilt_dir else default
    evidence = load(evidence_path, {}) or {}
    ctx = load(context_gaps_path, []) or []
    eng = d("gaps.json", [])
    model = Model(d("rules.json", []), d("report_items.json", []))
    items = [parse_gap(g, "context") for g in ctx if isinstance(g, dict) and g.get("status", "open") == "open"]
    items += [parse_gap(g, "reconstruction") for g in eng if isinstance(g, dict) and g.get("status", "open") == "open"]
    for path in extra_gaps or []:
        x = load(path, [])
        x = x.get("gaps", []) if isinstance(x, dict) else x
        items += [parse_gap(g, os.path.basename(path)) for g in x if isinstance(g, dict) and g.get("status", "open") == "open"]
    for km in evidence.get("known_missing") or []:
        items.append({"gap_ids": [], "what": "%s, %s" % (km.get("label"), km.get("period")), "why_text": "",
                      "origin": "evidence", "where": [], "label": km.get("label"), "period": km.get("period"),
                      "cell": None, "file": None, "values": [], "state": "known_missing", "km": km})
    q = d("question.json", None)
    if isinstance(q, dict) and q.get("question"):
        rule = q.get("rule_id")
        lab = next((r.get("description", "").split(" = ")[0] for r in d("rules.json", []) if r.get("rule_id") == rule), None)
        items.insert(0, {"gap_ids": [], "what": q["question"], "why_text": "", "origin": "question", "where": [],
                         "label": lab, "period": None, "cell": None, "file": None, "values": [], "state": "question",
                         "rule_id": rule, "question": q["question"], "options": q.get("options") or []})
    items = merge(items)
    kms = {"%s|%s" % (norm(k.get("label")), norm(k.get("period"))): k for k in evidence.get("known_missing") or []}
    resolved, open_items = [], []
    rule_rows = {(c[0], c[1]) for cs in model.rule_cells.values() for c in cs}
    for it in items:                           # known missing first: what is built on them is not worth asking for
        k = kms.get("%s|%s" % (norm(it.get("label")), norm(it.get("period"))))
        if k and it["state"] in ("known_missing", "blank", "error", "garbled", "other", "untested"):
            it["state"], it["km"] = "known_missing", it.get("km") or k
    built_on = {}
    for it in items:
        if it["state"] == "known_missing" and it.get("cell"):
            start = cells_of(it["cell"])
            for c in model.dependents(start) - set(start):
                built_on.setdefault(c, it)
    for it in items:
        cells = cells_of(it["cell"]) if it.get("cell") else []
        if len(cells) == 1 and cells[0] in built_on and it["state"] in ("blank", "error", "garbled", "other"):
            it["state"], it["base"] = "built_on_missing", built_on[cells[0]]
        if len(cells) == 1 and cells[0] in model.name and not it.get("period"):
            it["label"], it["period"] = it.get("label") or model.name[cells[0]][0], model.name[cells[0]][1]
        label = model.state.get(cells[0]) if len(cells) == 1 else None
        if (it["state"] == "blank" and len(cells) == 1 and label is None
                and (cells[0][0], cells[0][1]) in rule_rows):
            # A blank cell on a rebuilt line that the rebuild gave no label: the line's rule does not apply
            # to it (for example the first quarter of a "vs prior quarter" line), so it stays empty. Not an ask.
            it["state"] = "left_empty"
            resolved.append(it)
            continue
        if it["state"] in ("blank", "error", "garbled", "other", "assumption") and label in (
                "recovered", "reconstructed and tested"):
            resolved.append(it)
            continue
        if it["state"] in ("blank", "error", "garbled") and label == "reconstructed but untested":
            it["was"], it["state"] = it["state"], "untested"
        if it["state"] == "question":
            start = model.rule_cells.get(it.get("rule_id")) or []
        else:
            start = cells
        it["blocks"] = len(model.dependents(start)) if start else 0
        if it["state"] == "no_reports" and it.get("period"):
            it["blocks"] = sum(1 for c, (lab, per) in model.name.items() if norm(per) == norm(it["period"])
                               and model.state.get(c) == "reconstructed but untested" and c not in built_on)
        open_items.append(it)
    return open_items, resolved


def build(items, rnd, previous, client, contact, case, max_asks):
    prev_by_key = {}
    for e in previous or []:
        for k in e.get("keys") or []:
            prev_by_key.setdefault(k, e)
    out = []
    for it in items:
        if it["state"] == "internal":
            continue
        keys = keys_of(it)
        prev = next((prev_by_key[k] for k in keys if k in prev_by_key), None)
        r = (prev.get("round", 1) + 1 if prev and prev.get("status") != "found" else 1) if previous is not None else rnd
        pc = (prev["kind"], prev.get("place"), prev.get("to")) if prev and prev.get("kind") in (
            "ask_client", "client_forward", "search_more") else None
        places = [(w,) + classify(w) for w in it["where"]]
        places = [p for p in places if p[1] != "internal"]
        e = {"request_id": None, "gap_id": it["gap_ids"][0] if it["gap_ids"] else None, "gap_ids": it["gap_ids"],
             "kind": None, "to": None, "subject": None, "body": None, "why": None,
             "item": {k: it.get(k) for k in ("label", "period", "cell", "file", "amount", "date") if it.get(k)},
             "blocks": it.get("blocks", 0), "round": r, "repeat": False, "status": "draft", "keys": keys,
             "_sev": SEVERITY.get(it["state"], 6), "_state": it["state"]}
        if it.get("rule_id"):
            e["rule_id"] = it["rule_id"]
        head = what_item(it)
        unlock = ("it fills %s and lets us check %s" % (clean(it["cell"]), uses(e["blocks"] - 1))
                  if it.get("cell") and e["blocks"] > 1 else "it fills %s" % clean(it["cell"]) if it.get("cell") else "")
        if it["state"] == "known_missing":
            km = it.get("km") or {}
            said = clean(km.get("text") or (it["where"][0] if it["where"] else "the client says it does not exist"))
            e.update(kind="leave_unresolved", to="report", subject="Left blank on purpose: %s" % head,
                     body="%s: you told us you do not have this figure (\"%s\"), so we left it blank and marked it "
                          "'unresolved' in your report instead of guessing." % (head, said.rstrip(".")),
                     why="the client said they do not have it (%s%s); the cell stays blank and 'unresolved'" % (
                         clean(km.get("source") or "client email"),
                         (", " + km["fragment_id"]) if km.get("fragment_id") else ""))
            out.append(e)
            continue
        if it["state"] == "built_on_missing":
            base = what_item(it["base"])
            e.update(kind="leave_unresolved", to="report", subject="Waits on a missing figure: %s" % head,
                     body="%s is worked out from %s, which you told us you do not have, so we cannot check it until "
                          "that figure exists." % (head, base[0].lower() + base[1:]),
                     why="built on %s, which the client does not have (%s)" % (
                         base, clean((it["base"].get("km") or {}).get("source") or "client email")))
            out.append(e)
            continue
        if r >= 3:
            searched = ["the case files"] + [clean(p[0]) for p in places if p[1] == "search"]
            asked = [choose(places, 1), choose(places, 2, pc)]
            searched += ["asked %s: %s" % ("the client" if k == "ask_client" else "the client to forward a request to the "
                                           + (t or "holder"), for_client(p) if p else "directly")
                         for k, p, t in asked if k != "search_more"]
            searched = list(dict.fromkeys(searched))
            e.update(kind="leave_unresolved", to="report", subject="Not found after two rounds: %s" % head,
                     body=("%s: no answer after two rounds, so the rule keeps the first reading and stays 'reconstructed "
                           "but untested' in your report." % head) if it["state"] in ("question", "choice") else
                          ("%s: we searched everywhere we could and asked twice, but found nothing reliable, so we left "
                           "it as it is and say so in your report." % head),
                     why="searched: " + "; ".join(searched), searched=searched)
            out.append(e)
            continue
        kind, place, to = choose(places, r, pc)
        if kind == "ask_client" and it["state"] == "no_reports" and not e["blocks"]:
            srch = [p for p in places if p[1] == "search"]   # it would test nothing: do not spend the client's time
            if srch:
                kind, place, to = "search_more", srch[0][0], srch[0][2]
        if it["state"] in ("question", "choice"):
            kind, place, to = "ask_client", None, "client"
        e["repeat"] = bool(r >= 2 and (prev or {"kind": choose(places, 1)[0]})["kind"] in ("ask_client", "client_forward")
                           and kind != "search_more")
        e["kind"], e["to"], e["place"] = kind, to, place
        if kind == "search_more":
            terms = terms_of(it)
            where = "the client's mail" if to == "mail-scout" else "the connected drive and case folders"
            e.update(subject="Search %s: %s" % ("mail" if to == "mail-scout" else "files", "; ".join(terms) or head),
                     body="Search %s for: %s. Look in: %s. Save any message or file that holds %s to the case's "
                          "incoming folder." % (where, ", ".join("'%s'" % t for t in terms) or head, clean(place),
                                                head[0].lower() + head[1:]),
                     why="%s may be there: %s" % (head, clean(place)), terms=terms,
                     scout_note="%s %s (search '%s')" % (e["gap_id"] or "", clean(it.get("label") or it.get("file") or head),
                                                          terms[0] if terms else head))
        elif kind == "client_forward":
            subj, body = forward_draft(it, place, to, client, contact)
            e.update(subject=("Second request: " if e["repeat"] else "") + subj, body=body,
                     why="the %s keeps it (%s); %s" % (to, clean(place), unlock or "it holds " + head))
            e["for_client"] = "%s: if you do not have it, your %s can send a copy." % (head, to)
        else:
            e.update(subject=("Second request: " if e["repeat"] else "") + (
                "Question: %s" % clean(it.get("label") or "a rule in your model") if it["state"] == "question" else head),
                body=ask_body(it, place, e["repeat"]))
            if it["state"] == "question":
                e["why"] = "it locks rule %s; until then %s stay 'reconstructed but untested'" % (
                    it.get("rule_id"), plural(e["blocks"], "cell"))
            elif it["state"] == "untested":
                e["why"] = "%s is 'reconstructed but untested'; the real figure would test it%s" % (
                    clean(it.get("cell")), " and " + uses(e["blocks"] - 1) if e["blocks"] > 1 else "")
            elif it["state"] == "no_reports":
                e["why"] = "lets us test the rebuilt %s figures against a reported total%s" % (
                    clean(it.get("period") or ""), " (%s now untested)" % plural(e["blocks"], "cell") if e["blocks"] else "")
            elif it["state"] == "choice":
                e["why"] = "asked after the first question is answered"
            else:
                e["why"] = unlock or clean(it.get("why_text")) or "it is missing from what you sent"
        out.append(e)
    # order: the email items that unlock the most first, then searches, then what stays unresolved
    rank = {"ask_client": 0, "client_forward": 0, "search_more": 1, "leave_unresolved": 2}
    out.sort(key=lambda e: (rank[e["kind"]], -e["blocks"], e["_sev"]))
    n = 0
    for e in out:
        if rank[e["kind"]] == 0:
            e["batch"] = n // max_asks + 1 if e["_state"] != "choice" else max(2, n // max_asks + 1)
            n += 1
        else:
            e["batch"] = None
    # request ids: kept from the last round for the same item, new ones after the highest used
    cnum = re.sub(r"^C-", "", case or "0000")
    used = {e["request_id"] for e in previous or [] if e.get("request_id")}
    nxt = max([int(re.sub(r".*-", "", u)) for u in used if re.match(r".*-\d+$", u)] + [0]) + 1
    for e in out:
        prev = next((prev_by_key[k] for k in e["keys"] if k in prev_by_key), None)
        if prev and prev.get("request_id"):
            e["request_id"] = prev["request_id"]
        else:
            e["request_id"] = "Q-%s-%02d" % (cnum, nxt)
            nxt += 1
    open_keys = {k for e in out for k in e["keys"]}
    for p in previous or []:                     # asked before and no longer open: it was found
        if p.get("status") != "found" and not any(k in open_keys for k in p.get("keys") or []):
            out.append(dict(p, status="found", batch=None))
        elif p.get("status") == "found" and not any(k in open_keys for k in p.get("keys") or []):
            out.append(p)
    for e in out:
        e.pop("_sev", None)
        e.pop("_state", None)
    return out


def email(reqs, case, client=None, client_email=None, contact=None):
    asks = [e for e in reqs if e["kind"] == "ask_client" and e.get("batch") == 1 and e["status"] == "draft"]
    fwd = [e for e in reqs if e["kind"] == "client_forward" and e.get("batch") == 1 and e["status"] == "draft"]
    if not asks and not fwd:
        return "No email this round: nothing to ask the client.\n"
    n = len(asks) + len(fwd)
    repeat = any(e.get("repeat") for e in asks + fwd)
    L = []
    if client_email:
        L.append("To: %s" % clean(client_email))
    L += ["Subject: Case %s: %s we need to finish your recovery" % (case, plural(n, "item")), ""]
    L += ["Hi %s," % clean(contact) if contact else "Hello,", ""]
    if repeat:
        L.append("Thank you for your help so far. We are still missing %s (we asked about some of these before). If you "
                 "do not have one, just say so: we will mark it as missing in your report rather than guess." % plural(n, "item"))
    else:
        L.append("We rebuilt %s from what survived. To finish, we need %s from you. You can reply to this email with "
                 "the figure or attach the file. If you do not have something, just say so: we will mark it as missing "
                 "in your report rather than guess." % ("the files %s lost" % clean(client) if client else "your files",
                                                       plural(n, "exact item")))
    if asks:
        L.append("")
        L += ["%d. %s" % (i, e["body"]) for i, e in enumerate(asks, 1)]
    if fwd:
        L += ["", "Documents you could forward to us", "",
              "If you do not have one of these yourself, the company that keeps it can send you a copy. We wrote a short "
              "request you can send them; we never contact them for you. Once you have the document, forward it to us."]
        for i, e in enumerate(fwd):
            L += ["", "%s. %s Request you can send:" % ("ABCDEFGHIJ"[i % 10], e.get("for_client") or e["subject"]),
                  "Subject: %s" % e["subject"]]
            L += [("    " + x) if x else "" for x in e["body"].split("\n")]
    L += ["", "Thank you,", "The Data Care recovery team (case %s)" % case, ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draft the requests that fill a case's open gaps (never sends anything).")
    ap.add_argument("--case", required=True)
    ap.add_argument("--rebuilt-dir", help="formula_infer.py output folder (gaps.json, question.json, report_items.json, rules.json)")
    ap.add_argument("--evidence", help="Context's evidence.json (for known_missing)")
    ap.add_argument("--context-gaps", help="Context's gaps.json (default: gaps.json next to --evidence)")
    ap.add_argument("--gaps", action="append", default=[], help="more gap files (Forensics, reconcile.py)")
    ap.add_argument("--client")
    ap.add_argument("--client-email")
    ap.add_argument("--contact-name")
    ap.add_argument("--previous", help="requests.json from the last round")
    ap.add_argument("--round", type=int, help="1, 2, or 3+ to close out (default: last round + 1, or 1)")
    ap.add_argument("--max-asks", type=int, default=5)
    ap.add_argument("--out-dir")
    a = ap.parse_args(argv)
    ctx = a.context_gaps
    if not ctx and a.evidence:
        cand = os.path.join(os.path.dirname(os.path.abspath(a.evidence)), "gaps.json")
        if os.path.exists(cand) and (not a.rebuilt_dir or os.path.abspath(cand) != os.path.abspath(
                os.path.join(a.rebuilt_dir, "gaps.json"))):
            ctx = cand
    previous = load(a.previous, None) if a.previous else None
    if a.previous and not isinstance(previous, list):
        previous = []
    rnd = a.round or (max([p.get("round", 1) for p in previous or []] + [0]) + 1 if previous else 1)
    if a.round and previous is not None:
        for p in previous:                        # an explicit --round wins over the per-gap count
            p["round"] = a.round - 1
    items, resolved = collect(a.rebuilt_dir, a.evidence, ctx, a.gaps)
    reqs = build(items, rnd, previous, a.client, a.contact_name, a.case, max(1, a.max_asks))
    out = a.out_dir or a.rebuilt_dir or "."
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "requests.json"), "w", encoding="utf-8") as fh:
        json.dump(reqs, fh, indent=2, ensure_ascii=False)
    text = email(reqs, a.case, a.client, a.client_email, a.contact_name)
    with open(os.path.join(out, "requests.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    count = lambda k: sum(1 for e in reqs if e["kind"] == k and e["status"] == "draft")
    in_mail = sum(1 for e in reqs if e.get("batch") == 1 and e["status"] == "draft")
    print("requests round %d: %d ask_client, %d client_forward, %d search_more, %d leave_unresolved; email: %s%s%s" % (
        rnd, count("ask_client"), count("client_forward"), count("search_more"), count("leave_unresolved"),
        plural(in_mail, "item") if in_mail else "none", ("; no request needed (rebuilt, or empty on purpose): " + ", ".join(
            g for it in resolved for g in it["gap_ids"])) if resolved else "",
        ("; found since last round: " + ", ".join(e["request_id"] for e in reqs if e["status"] == "found"))
        if any(e["status"] == "found" for e in reqs) else ""))
    print("wrote %s and %s" % (os.path.join(out, "requests.json"), os.path.join(out, "requests.md")))


if __name__ == "__main__":
    main()
