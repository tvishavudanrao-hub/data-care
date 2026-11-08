#!/usr/bin/env python3
"""trace_infer.py - Data Care Reconstruction tool for a food-outbreak trace-back case (kind "trace").
Python 3.8+, standard library only. It reads only the trace graph from trace_scan.py; it never opens client files
and never sends anything.

    python3 trace_infer.py --graph trace_graph.json --case C-0001 --out-dir OUT [--top 5] [--answer R-0001-01=0]

A source (a farm, and also a packer lot) explains an illness case when a chain farm -> lot -> packer -> distributor ->
store exists, the store is the case's store, and the purchase falls on or after the store received the lot and within
SHELF_LIFE_DAYS (14) after the lot's pack date. A case with no purchase date is taken as bought 1 to 10 days before onset.
Score: each case a source explains counts the confidence of the weakest link on its best chain (the case record
included); when k other sources explain the same case as well (within EQUAL_TOL) or better, that case keeps
1 - 0.5 * k / (k + 1) of its weight (SHARED_PENALTY: 75% with one rival, never below 50%), so the number of cases
explained stays the main signal. Confidence = score / number of cases.
Labels: "reconstructed and tested" (every case it explains has a chain backed by records: log rows with full lot codes),
"reconstructed but untested" (some case relies on an email, a partial code, an estimated date or a missing hop),
"unresolved" (the top two are within TOO_CLOSE_MARGIN of each other: too close to call).
Writes to OUT:
  hypotheses.json   [{"rank","source","source_type","lots","explains":{"cases","of","case_ids"},"confidence","label",
                      "evidence","missing_links","why"}], top N. A lot from one farm is listed inside that farm's
                      hypothesis; a commingled lot, or a lot with no known farm, is a hypothesis of its own.
  rules.json        each hypothesis as a Rule record R-<n>-01.. (status = its label), for the relay and the app
  question.json     only when the top two are too close to call: the one record that would separate them, as a plain
                    question with options. The agent replies needs_client with it.
  requests.json/.md 24-hour records requests, one per supplier (farm, packer or distributor) holding a missing link that
                    matters for the top hypotheses. Drafts only: a person approves every send.
  gaps.json         engine gaps G-<n>-51..89
  report_draft.md   plain-English draft; Validation adds its verdict before anything is sent
  summary.json      {"status": "done" | "needs_client" | "failed", ...}
After the client answers, rerun with --answer <rule_id>=<option index> (0-based, as in formula_infer.py).
"""
import argparse
import datetime
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

SHELF_LIFE_DAYS = 14          # a lot can be sold up to 14 days after its pack date
DATE_TOLERANCE_DAYS = 1       # loose dates may be a day off
INCUBATION_MIN_DAYS = 1       # no purchase date: bought 1 to 10 days before onset
INCUBATION_MAX_DAYS = 10
EQUAL_TOL = 0.05              # two chains within 0.05 of each other explain a case "equally"
SHARED_PENALTY = 0.5          # a case k other sources explain as well keeps 1 - 0.5*k/(k+1) of its weight (75% for one
                              # other, never below 50%), so the number of cases explained stays the main signal
TOO_CLOSE_MARGIN = 0.15       # top two within 15% of the top score: too close to call
IMPLIED_HOP_CONF = 0.6        # packer -> distributor hop missing for this lot, the distributor gets other lots from that packer
IMPLIED_HOP_NEW_CONF = 0.3    # the distributor has no record of ever getting anything from that packer
IMPLIED_HOP_NO_PACKER = 0.4   # the lot's packer is unknown
LOT_NO_RECORD_CONF = 0.8      # the lot has no pack record (no pack date to check the shelf life against)
ESTIMATED_EXPOSURE_CONF = 0.6
NO_DATE_EXPOSURE_CONF = 0.4
CLIENT_ANSWER_CONF = 0.9
MAX_QUESTION_CANDIDATES = 40  # candidate records re-ranked to find the one that separates the top two
REQUEST_HOURS = 24
TOP_DEFAULT = 5
MAX_EVIDENCE = 60

TESTED, UNTESTED, UNRESOLVED = "reconstructed and tested", "reconstructed but untested", "unresolved"
LABELS = ("recovered", TESTED, UNTESTED, UNRESOLVED)
LABEL_WORDS = OrderedDict([
    ("recovered", "survived intact, or copied exactly from your records (not used for a source: a source is always a "
                  "reconstruction)"),
    (TESTED, "every case it explains has a chain backed by records: log rows with full lot codes from farm to store"),
    (UNTESTED, "it relies on at least one inferred or partial link: a supplier email, a smudged or missing lot code, a day "
               "missing from a log, or a purchase date estimated from the onset date"),
    (UNRESOLVED, "too close to call: another source fits the cases about as well, so we ask one question instead of "
                 "guessing"),
])
ROLES = ("farm", "packer", "distributor")
SECRET = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)(\s*[=:]\s*)\S+")


# -- helpers ---------------------------------------------------------------------------------------------------------
def days(n):
    return datetime.timedelta(days=n)


def pdate(s):
    m = re.match(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})", str(s or ""))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def iso(d):
    return d.isoformat() if d else None


def num(x, default):
    try:
        v = float(x)
        return v if 0 <= v <= 1 else default
    except (TypeError, ValueError):
        return default


def clean(text):
    """Plain text for people: no secrets, no long dashes, one line."""
    text = SECRET.sub(r"\1\2[removed]", str(text or ""))
    text = text.replace("—", ", ").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def join_and(items):
    items = [str(x) for x in items if x]
    if len(items) <= 1:
        return "".join(items)
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def norm_text(s):
    return " ".join(re.findall(r"[a-z0-9]+", str(s or "").lower()))


PROD_STOP = {"lettuce", "salad", "salads", "bag", "bags", "bagged", "fresh", "organic", "chopped", "heart", "hearts",
             "whole", "head", "heads", "mix", "kit", "kits", "case", "cases", "cs", "lb", "lbs", "ct", "count", "the",
             "of", "and", "a", "box", "boxes", "baby", "leaf", "leaves"}


def prod_key(p):
    toks = [t[:-1] if len(t) > 4 and t.endswith("s") else t for t in norm_text(p).split()]
    k = frozenset(t for t in toks if t not in PROD_STOP)
    return k or frozenset(toks)


def prod_match(a, b):
    if not a or not b:
        return True
    ka, kb = prod_key(a), prod_key(b)
    return bool(ka and kb) and (ka <= kb or kb <= ka)


def timing_ok(pack, recv, w0, w1, shelf):
    """The lot was packed before the store got it, and the purchase window meets [received or packed, pack + shelf]."""
    tol = days(DATE_TOLERANCE_DAYS)
    if pack and recv and recv < pack - tol:
        return False
    if w0 is None or w1 is None:
        return True
    starts = [d for d in (pack, recv) if d]
    if starts and w1 < max(starts) - tol:
        return False
    anchor = pack or recv
    if anchor and w0 > anchor + days(shelf) + tol:
        return False
    return True


def pattern_range(raw):
    """'RL-041?' -> ('RL-0410', 'RL-0419'). None unless the unreadable characters are all at the end: 'RL-06?6' is ten
    codes, not the range RL-0606 to RL-0696, so its lots are listed instead."""
    raw = str(raw or "").strip().upper()
    if not re.match(r"^[A-Z0-9][A-Z0-9-]*?[0-9-][?*#]+$", raw):
        return None
    lo, hi = re.sub(r"[?*#]", "0", raw), re.sub(r"[?*#]", "9", raw)
    return (lo, hi) if lo != hi else None


def lot_text(lots, raws=()):
    """'lots RL-0410 to RL-0419', 'lot RL-0412', 'lots RL-0412 and RL-0415'."""
    lots = sorted(set(l for l in lots if l))
    ranges = [r for r in (pattern_range(x) for x in raws) if r]
    if ranges:
        return "lots " + join_and("%s to %s" % r for r in ranges)
    if not lots:
        return ""
    if len(lots) == 1:
        return "lot " + lots[0]
    m = [re.match(r"^(.*?)(\d+)$", l) for l in lots]
    if len(lots) >= 4 and all(m) and len({x.group(1) for x in m}) == 1:
        return "lots %s to %s" % (lots[0], lots[-1])
    return "lots " + join_and(lots)


# -- the engine ------------------------------------------------------------------------------------------------------
class Engine(object):
    def __init__(self, g, shelf=SHELF_LIFE_DAYS, margin=TOO_CLOSE_MARGIN):
        self.g, self.applied = g, []
        self.case_id = str(g.get("case_id") or "")
        self.shelf, self.margin = int(shelf), float(margin)
        self.graph_shelf = g.get("shelf_life_days")
        self.nodes = OrderedDict((str(n["id"]), n) for n in g.get("nodes") or [] if isinstance(n, dict) and n.get("id"))
        self.links = OrderedDict()
        for raw in g.get("links") or []:
            if not isinstance(raw, dict) or not raw.get("link_id") or not raw.get("from") or not raw.get("to"):
                continue
            L = dict(raw)
            L["_date"] = pdate(L.get("date"))
            L["_lots"] = [str(L["lot_code"])] if L.get("lot_code") else [str(x) for x in (L.get("lot_candidates") or [])]
            L["_hop"] = L.get("hop") or "%s-%s" % (self.type_of(L["from"]), self.type_of(L["to"]))
            L["_conf"] = num(L.get("confidence"), 0.5)
            basis = L.get("basis")
            if basis not in ("record", "stated", "partial", "inferred"):
                basis = "partial" if not L.get("lot_code") else ("record" if L["_conf"] >= 0.9 else "stated")
            L["_basis"] = basis
            self.links[str(L["link_id"])] = L
        self.lots = OrderedDict()
        for x in g.get("lots") or []:
            if isinstance(x, dict) and x.get("lot_code"):
                self.lots[str(x["lot_code"])] = {
                    "packer_id": x.get("packer_id"), "pack_date": pdate(x.get("pack_date")), "product": x.get("product"),
                    "in_packer_records": x.get("in_packer_records", True) is not False,
                    "fragment_id": x.get("fragment_id"), "source": x.get("source")}
        for L in self.links.values():
            if L["_hop"] == "farm-packer":
                for lot in L["_lots"]:
                    info = self.lots.setdefault(lot, {"packer_id": L["to"], "pack_date": L["_date"], "product": L.get("product"),
                                                      "in_packer_records": True, "fragment_id": L.get("fragment_id"),
                                                      "source": L.get("source")})
                    if not info.get("packer_id"):
                        info["packer_id"] = L["to"]
        self.exposures = []
        for x in g.get("exposures") or []:
            if not isinstance(x, dict) or not x.get("case_id"):
                continue
            conf, basis = num(x.get("confidence"), 0.95), x.get("basis") or "record"
            p, onset = pdate(x.get("purchase_date")), pdate(x.get("onset_date"))
            w = x.get("purchase_window") if isinstance(x.get("purchase_window"), list) else None
            if p:
                w0 = w1 = p
            elif w and len(w) == 2 and pdate(w[0]) and pdate(w[1]):
                w0, w1, basis, conf = pdate(w[0]), pdate(w[1]), "estimated", min(conf, ESTIMATED_EXPOSURE_CONF)
            elif onset:
                w0, w1 = onset - days(INCUBATION_MAX_DAYS), onset - days(INCUBATION_MIN_DAYS)
                basis, conf = "estimated", min(conf, ESTIMATED_EXPOSURE_CONF)
            else:
                w0 = w1 = None
                basis, conf = "estimated", min(conf, NO_DATE_EXPOSURE_CONF)
            stores = [x["store_id"]] if x.get("store_id") else [s for s in (x.get("store_candidates") or []) if s]
            self.exposures.append({"case_id": str(x["case_id"]), "store_id": x.get("store_id") or None, "stores": stores,
                                   "product": x.get("product"), "w0": w0, "w1": w1, "conf": conf, "basis": basis,
                                   "source": x.get("source"), "fragment_id": x.get("fragment_id"), "lots_only": None,
                                   "excluded": False, "answered": False})
        self.gap_info = OrderedDict()
        for gi in g.get("gap_info") or []:
            if isinstance(gi, dict) and gi.get("gap_id"):
                self.gap_info[str(gi["gap_id"])] = gi
        for gid in g.get("gaps") or []:
            self.gap_info.setdefault(str(gid), {"gap_id": gid, "kind": "other"})
        self.answer_note = None
        self.index()

    # names and types
    def type_of(self, eid):
        n = self.nodes.get(eid)
        if n and n.get("type"):
            return n["type"]
        m = re.match(r"^([A-Za-z])", str(eid or ""))
        return {"F": "farm", "P": "packer", "D": "distributor", "S": "store"}.get(m.group(1).upper() if m else "", "unknown")

    def name(self, eid):
        n = self.nodes.get(eid)
        return clean(n.get("name")) if n and n.get("name") and n.get("name") != eid else str(eid)

    def who(self, eid):
        nm = self.name(eid)
        return "%s (%s)" % (nm, eid) if nm != eid else str(eid)

    def src_words(self, h):
        if h["source_type"] == "farm":
            return self.who(h["source"])
        if h["farms"]:
            return "lot %s (commingled: %s)" % (h["source"], join_and(self.who(f) for f in h["farms"]))
        return "lot %s (farm unknown)" % h["source"]

    # indexes
    def index(self):
        self.farm_links = defaultdict(OrderedDict)  # lot -> farm -> best link
        self.pd_by_lot = {}                         # (packer, distributor, lot) -> best link
        self.dist_packers = defaultdict(set)
        self.ds_by_store = defaultdict(list)
        better = lambda a, b: (a["_conf"], a["_basis"] == "record") > (b["_conf"], b["_basis"] == "record")
        for L in self.links.values():
            h = L["_hop"]
            if h == "farm-packer":
                for lot in L["_lots"]:
                    cur = self.farm_links[lot].get(L["from"])
                    if cur is None or better(L, cur):
                        self.farm_links[lot][L["from"]] = L
            elif h == "packer-distributor":
                self.dist_packers[L["to"]].add(L["from"])
                for lot in L["_lots"]:
                    k = (L["from"], L["to"], lot)
                    if k not in self.pd_by_lot or better(L, self.pd_by_lot[k]):
                        self.pd_by_lot[k] = L
            elif h == "distributor-store":
                self.ds_by_store[L["to"]].append(L)

    def implied_conf(self, packer, dist):
        if not packer:
            return IMPLIED_HOP_NO_PACKER
        return IMPLIED_HOP_CONF if packer in self.dist_packers.get(dist, ()) else IMPLIED_HOP_NEW_CONF

    # chains
    def chains(self, e):
        """Every chain farm -> lot -> packer -> distributor -> store that can explain case e."""
        out = []
        if e["excluded"]:
            return out
        for S, dl in [(S, dl) for S in e["stores"] for dl in self.ds_by_store.get(S, [])]:
            if not prod_match(dl.get("product"), e["product"]):
                continue
            t = dl["_date"]
            for lot in dl["_lots"]:
                if e["lots_only"] is not None and lot not in e["lots_only"]:
                    continue
                info = self.lots.get(lot) or {}
                if info.get("product") and not prod_match(info["product"], e["product"]):
                    continue
                pk = info.get("pack_date")
                if not timing_ok(pk, t, e["w0"], e["w1"], self.shelf):
                    continue
                D, P = dl["from"], info.get("packer_id")
                pdl = self.pd_by_lot.get((P, D, lot)) if P else None
                if pdl is not None:
                    hop_conf, hop_basis, implied = pdl["_conf"], pdl["_basis"], None
                else:
                    hop_conf, hop_basis, implied = self.implied_conf(P, D), "inferred", (P, D, lot)
                lot_conf = 0.95 if info.get("in_packer_records", True) and pk else LOT_NO_RECORD_CONF
                parts = ((e["conf"], e["basis"]), (dl["_conf"], dl["_basis"]), (hop_conf, hop_basis),
                         (lot_conf, "record" if lot_conf >= 0.9 else "inferred"))
                lot_strength = min(p[0] for p in parts)
                lot_record = all(p[1] == "record" for p in parts)
                ids = [dl["link_id"]] + ([pdl["link_id"]] if pdl is not None else [])
                frags = [x for x in (e["fragment_id"], dl.get("fragment_id"), pdl.get("fragment_id") if pdl else None,
                                     info.get("fragment_id")) if x]
                base = {"case": e["case_id"], "lot": lot, "store": S, "distributor": D, "packer": P, "date": t,
                        "ds": dl, "pd": pdl, "implied": implied, "links": ids, "frags": frags,
                        "lot_strength": lot_strength, "lot_record": lot_record, "partial": dl["_basis"] == "partial"}
                farms = self.farm_links.get(lot) or {}
                if not farms:
                    out.append(dict(base, farm=None, fl=None, strength=lot_strength, record=lot_record))
                for f, fl in farms.items():
                    out.append(dict(base, farm=f, fl=fl, strength=min(lot_strength, fl["_conf"]),
                                    record=lot_record and fl["_basis"] == "record", links=ids + [fl["link_id"]],
                                    frags=frags + ([fl["fragment_id"]] if fl.get("fragment_id") else [])))
        return out

    # client answers
    def apply(self, spec):
        if not spec:
            return "no change"
        self.applied.append(spec)
        if spec.get("link"):
            L = self.links.get(spec["link"])
            if L is not None:
                L["_lots"], L["_conf"], L["_basis"] = list(spec.get("lots") or []), CLIENT_ANSWER_CONF, "record"
                L["answered"] = True
        if spec.get("lot") and spec.get("farm"):
            for L in self.links.values():
                if L["_hop"] == "farm-packer" and spec["lot"] in L["_lots"]:
                    if L["from"] == spec["farm"]:
                        L["_conf"], L["_basis"] = max(L["_conf"], CLIENT_ANSWER_CONF), "record"
                    else:
                        L["_lots"] = [x for x in L["_lots"] if x != spec["lot"]]
        if spec.get("cases") and spec.get("lots"):
            for e in self.exposures:
                if e["case_id"] in spec["cases"]:
                    e["lots_only"] = set(spec["lots"])
        for c in spec.get("exclude_cases") or []:
            for e in self.exposures:
                if e["case_id"] == c:
                    e["excluded"] = True
        self.index()
        return "applied"

    # scoring
    @staticmethod
    def credit(weights):
        """{case: {source: weight}} -> ({source: score}, {source: {case: credit}}). A case that k other sources explain
        as well or better keeps 1 - SHARED_PENALTY * k / (k + 1) of its weight."""
        total, cred = defaultdict(float), defaultdict(dict)
        for c, m in weights.items():
            for s, w in m.items():
                k = sum(1 for s2, w2 in m.items() if s2 != s and w2 >= w - EQUAL_TOL)
                cred[s][c] = w * (1 - SHARED_PENALTY * k / (1.0 + k))
                total[s] += cred[s][c]
        return total, cred

    def analyze(self):
        exps = [e for e in self.exposures if not e["excluded"]]
        self.N = len(exps)
        farm_ch, lot_ch = OrderedDict(), OrderedDict()
        for e in exps:
            fc, lc = OrderedDict(), OrderedDict()
            for ch in self.chains(e):
                fc.setdefault(ch["farm"] or "?" + ch["lot"], []).append(ch)
                lc.setdefault(ch["lot"], []).append(ch)
            farm_ch[e["case_id"]], lot_ch[e["case_id"]] = fc, lc
        self.farm_ch, self.lot_ch, self.exps = farm_ch, lot_ch, exps
        ftot, fcred = self.credit({c: {s: max(x["strength"] for x in chs) for s, chs in m.items()} for c, m in farm_ch.items()})
        ltot, lcred = self.credit({c: {s: max(x["lot_strength"] for x in chs) for s, chs in m.items()} for c, m in lot_ch.items()})
        hyps = []
        for s, sc in ftot.items():
            cases = [c for c in farm_ch if s in farm_ch[c]]
            chains = {c: farm_ch[c][s] for c in cases}
            if s.startswith("?"):
                h = {"key": s, "source": s[1:], "source_type": "lot", "farms": [], "level": "farm"}
            else:
                h = {"key": s, "source": s, "source_type": "farm", "farms": [s], "level": "farm"}
            h.update(score=sc, cases=cases, chains=chains, credit=fcred[s], skey="strength", rkey="record")
            hyps.append(h)
        for lot, sc in ltot.items():
            farms = list(self.farm_links.get(lot) or {})
            if len(farms) < 2:
                continue
            cases = [c for c in lot_ch if lot in lot_ch[c]]
            hyps.append({"key": "lot:" + lot, "source": lot, "source_type": "lot", "farms": farms, "level": "lot",
                         "score": sc, "cases": cases, "chains": {c: lot_ch[c][lot] for c in cases}, "credit": lcred[lot],
                         "skey": "lot_strength", "rkey": "lot_record"})
        # Sources first (farms, and lots whose farm is unknown), by score; then commingled lots, which refine their
        # farms' claims rather than compete with them, so they never push an alternative farm down the list.
        hyps.sort(key=lambda h: (1 if h["level"] == "lot" else 0, -round(h["score"], 6),
                                 0 if h["source_type"] == "farm" else 1, h["source"]))
        for h in hyps:
            sk, rk = h["skey"], h["rkey"]
            h["best"] = {c: max(chs, key=lambda x: (x[sk], x[rk])) for c, chs in h["chains"].items()}
            h["tested_cases"] = [c for c, chs in h["chains"].items() if any(x[rk] for x in chs)]
            lot_cases, lot_best = defaultdict(set), defaultdict(float)
            for c, chs in h["chains"].items():
                for x in chs:
                    lot_cases[x["lot"]].add(c)
                    lot_best[x["lot"]] = max(lot_best[x["lot"]], x[sk])
            order = sorted(lot_cases, key=lambda l: (-len(lot_cases[l]), -lot_best[l], l))
            h["lots"] = [h["source"]] if h["source_type"] == "lot" else order
            h["lot_cases"] = OrderedDict((l, sorted(lot_cases[l])) for l in h["lots"])
            h["confidence"] = round(h["score"] / self.N, 2) if self.N else 0.0
        self.hyps = hyps
        self.pair = self.too_close(hyps)
        unresolved = set()
        if self.pair:
            top = self.pair[0]
            unresolved = {self.pair[0]["key"], self.pair[1]["key"]}
            for h in hyps[hyps.index(top) + 1:]:
                if h["source_type"] == self.pair[1]["source_type"] and not self.nested(top, h) and self.close(top, h):
                    unresolved.add(h["key"])
        for h in hyps:
            if h["key"] in unresolved:
                h["label"] = UNRESOLVED
            elif len(h["tested_cases"]) == len(h["cases"]):
                h["label"] = TESTED
            else:
                h["label"] = UNTESTED
        return hyps

    @staticmethod
    def nested(a, b):
        if a["source_type"] == "farm" and b["source_type"] == "lot":
            return a["source"] in b["farms"]
        if a["source_type"] == "lot" and b["source_type"] == "farm":
            return b["source"] in a["farms"]
        if a["source_type"] == "lot" and b["source_type"] == "lot":
            return bool(a["farms"]) and set(a["farms"]) == set(b["farms"])
        return a["source"] == b["source"]

    def close(self, a, b):
        return a["score"] > 0 and (a["score"] - b["score"]) / a["score"] < self.margin

    def too_close(self, hyps):
        if not hyps:
            return None
        h1 = hyps[0]
        comp = [h for h in hyps[1:] if not self.nested(h1, h)]
        if comp and self.close(h1, comp[0]):
            return (h1, comp[0])
        farms = [h for h in hyps if h["source_type"] == "farm"]
        if len(farms) >= 2 and hyps.index(farms[0]) < 3 and self.close(farms[0], farms[1]):
            return (farms[0], farms[1])
        return None

    # the question that separates the top two
    def owns(self, h, lot):
        if h["source_type"] == "farm":
            return h["source"] in (self.farm_links.get(lot) or {})
        return lot == h["source"]

    def simulate(self, spec):
        """Scores by hypothesis key if the client answered with spec (on a fresh copy of the graph)."""
        sim = Engine(self.g, self.shelf, self.margin)
        for s in self.applied + [spec]:
            sim.apply(s)
        return {h["key"]: h["score"] for h in sim.analyze()}

    def gaps(self, h1, h2, specs):
        """(gap if the answer favours h1, gap if it favours h2), gap = (score h1 - score h2) / the larger score."""
        out = []
        for spec in specs[:2]:
            s = self.simulate(spec)
            a, b = s.get(h1["key"], 0.0), s.get(h2["key"], 0.0)
            out.append((a - b) / max(a, b, 1e-9))
        return out

    def question(self, h1, h2, rule_id):
        """The one record whose answer separates the top two most: candidate records are a partial or missing lot code,
        a commingled lot holding both farms, a store that got lots of both before a case bought there, or which cases
        belong to the cluster. Each is scored by re-ranking with either answer."""
        cands = []
        both = sorted(set(h1["cases"]) | set(h2["cases"]))
        # (a) a partial lot code whose possible lots split between the two
        uses = defaultdict(set)
        for h in (h1, h2):
            for c, chs in h["chains"].items():
                for ch in chs:
                    if ch["partial"]:
                        uses[ch["ds"]["link_id"]].add(c)
        for lid, cases in uses.items():
            L = self.links[lid]
            A = [l for l in L["_lots"] if self.owns(h1, l)]
            B = [l for l in L["_lots"] if self.owns(h2, l)]
            if A and B and set(A) != set(B):
                cands.append((0, -len(cases), lid, ("link", L, A, B, sorted(cases))))
        # (b) a commingled lot that holds both farms
        if h1["source_type"] == "farm" and h2["source_type"] == "farm":
            for lot, farms in self.farm_links.items():
                if h1["source"] in farms and h2["source"] in farms:
                    cases = sorted(c for c in both for h in (h1, h2) if c in h["chains"]
                                   and any(ch["lot"] == lot for ch in h["chains"][c]))
                    if cases:
                        cands.append((1, -len(set(cases)), lot, ("lot", lot, sorted(set(cases)))))
        # (c) the same store got lots of both before a case bought there
        groups = defaultdict(list)
        for c in both:
            if c in h1["chains"] and c in h2["chains"]:
                A = sorted({ch["lot"] for ch in h1["chains"][c]} - {ch["lot"] for ch in h2["chains"][c]})
                B = sorted({ch["lot"] for ch in h2["chains"][c]} - {ch["lot"] for ch in h1["chains"][c]})
                if A and B:
                    groups[(h1["chains"][c][0]["store"], tuple(A), tuple(B))].append(c)
        for (S, A, B), cases in groups.items():
            cands.append((2, -len(cases), S, ("store", S, list(A), list(B), cases)))
        # (d) each explains a case the other does not: which of those cases belong to the cluster
        only1 = sorted(set(h1["cases"]) - set(h2["cases"]))
        only2 = sorted(set(h2["cases"]) - set(h1["cases"]))
        if only1 and only2:
            cands.append((3, 0, "cases", ("cases", only1, only2)))
        if not cands:
            return None
        cands.sort(key=lambda x: (x[0], x[1], str(x[2])))
        specs = {"link": lambda k: [{"link": k[1]["link_id"], "lots": k[2]}, {"link": k[1]["link_id"], "lots": k[3]}],
                 "lot": lambda k: [{"lot": k[1], "farm": h1["source"]}, {"lot": k[1], "farm": h2["source"]}],
                 "store": lambda k: [{"cases": k[4], "lots": k[2]}, {"cases": k[4], "lots": k[3]}],
                 "cases": lambda k: [{"exclude_cases": k[2]}, {"exclude_cases": k[1]}]}
        # A record is decisive when either answer puts its source ahead by the full margin. Among decisive records the
        # most concrete kind wins (a lot code on a delivery record, then a packing record, then stock, then lab results);
        # when none is decisive, the record whose two answers move the gap furthest apart.
        scored = []
        for i, c in enumerate(cands[:MAX_QUESTION_CANDIDATES]):
            ga, gb = self.gaps(h1, h2, specs[c[3][0]](c[3]))
            decisive = ga >= self.margin and gb <= -self.margin
            scored.append(((0, c[0]) if decisive else (1, 0), -(ga - gb), i, ga - gb))
        scored.sort()
        best, sep = scored[0][2], scored[0][3]
        kind = cands[best][3]
        w1, w2 = self.src_words(h1), self.src_words(h2)
        tag = lambda h, lots: "%s, %s" % (join_and(lots), ("from " + self.src_words(h)) if h["source_type"] == "farm" else
                                          ("a commingled lot" if h["farms"] else "farm unknown"))
        if kind[0] == "link":
            _, L, A, B, cases = kind
            raw = L.get("lot_raw")
            q = "Which lot code is on the %s that %s received from %s on %s? %s" % (
                L.get("product") or "product", self.who(L["to"]), self.who(L["from"]), L.get("date") or "the day recorded",
                ("The record reads \"%s\" (%s)." % (clean(raw), clean(L.get("source")))) if raw else
                ("The record has no lot code (%s)." % clean(L.get("source"))))
            opts = [tag(h1, A), tag(h2, B), "Another code, or the record does not show it"]
            apply = [{"link": L["link_id"], "lots": A}, {"link": L["link_id"], "lots": B}, {}]
            key, record = "link:" + L["link_id"], {"kind": "lot code on a delivery record", "link_id": L["link_id"],
                                                    "source": L.get("source"), "store_id": L["to"],
                                                    "distributor_id": L["from"], "date": L.get("date"),
                                                    "lot_candidates": L["_lots"]}
        elif kind[0] == "lot":
            _, lot, cases = kind
            P = (self.lots.get(lot) or {}).get("packer_id")
            stores = sorted({ch["store"] for h in (h1, h2) for c in cases if c in h["chains"] for ch in h["chains"][c]
                             if ch["lot"] == lot})
            q = "Lot %s%s holds %s from both %s and %s. Whose %s went into the cases of %s shipped to %s?" % (
                lot, (" (packed by %s)" % self.who(P)) if P else "", (self.lots.get(lot) or {}).get("product") or "product",
                w1, w2, (self.lots.get(lot) or {}).get("product") or "product", lot, join_and(self.who(s) for s in stores))
            opts = [w1, w2, "Both, or the packing records cannot tell"]
            apply = [{"lot": lot, "farm": h1["source"]}, {"lot": lot, "farm": h2["source"]}, {}]
            key, record = "lot:" + lot, {"kind": "packing record of a commingled lot", "lot_code": lot, "packer_id": P,
                                          "store_ids": stores}
        elif kind[0] == "store":
            _, S, A, B, cases = kind
            dates = sorted(iso(e["w1"]) for e in self.exps if e["case_id"] in cases and e["w1"])
            lots_of = lambda ls: ("lots " if len(ls) > 1 else "lot ") + join_and(ls)
            q = "%s had %s from both sources in stock before case%s %s bought it there%s: %s from %s, and %s from %s. " \
                "Which lot was on sale then?" % (
                    self.who(S), self.exp_product(cases) or "the product", "s" if len(cases) > 1 else "", join_and(cases),
                    (" by %s" % dates[-1]) if dates else "", lots_of(A), w1, lots_of(B), w2)
            opts = [tag(h1, A), tag(h2, B), "Both, or the store cannot tell"]
            apply = [{"cases": cases, "lots": A}, {"cases": cases, "lots": B}, {}]
            key, record = "store:%s:%s|%s" % (S, ",".join(A), ",".join(B)), {
                "kind": "store stock rotation or sales record", "store_id": S, "lots": A + B, "case_ids": cases}
        else:
            _, only1, only2 = kind
            q = "Which of these illness cases are confirmed as part of this cluster (for example by a matching lab " \
                "result)? %s fit%s %s only; %s fit%s %s only." % (
                    join_and(only1), "s" if len(only1) == 1 else "", w1, join_and(only2), "s" if len(only2) == 1 else "", w2)
            opts = ["%s, not %s" % (join_and(only1), join_and(only2)), "%s, not %s" % (join_and(only2), join_and(only1)),
                    "All of them, or not known yet"]
            apply = [{"exclude_cases": only2}, {"exclude_cases": only1}, {}]
            key, record = "cases:%s|%s" % (",".join(only1), ",".join(only2)), {
                "kind": "lab confirmation of cases", "case_ids": only1 + only2}
        return OrderedDict([("rule_id", rule_id), ("key", key), ("question", clean(q)),
                            ("options", [clean(o) for o in opts]), ("apply", apply), ("record", record),
                            ("separates", [h1["source"], h2["source"]]),
                            ("scores", [round(h1["score"], 3), round(h2["score"], 3)]),
                            ("separation", round(sep, 3) if sep is not None else None),
                            ("margin", self.margin), ("status", "needs_client")])

    def exp_product(self, cases):
        ps = [e["product"] for e in self.exps if e["case_id"] in cases and e["product"]]
        return ps[0] if ps else None


# -- outputs ---------------------------------------------------------------------------------------------------------
class Writer(object):
    def __init__(self, eng, case, top):
        self.e, self.case, self.top = eng, case, top
        self.cnum = case[2:] if case.upper().startswith("C-") else case

    def run(self, question_answered=None):
        e = self.e
        hyps = e.analyze()
        shown = hyps[:self.top]
        for i, h in enumerate(hyps, 1):
            h["rank"] = i
            h["rule_id"] = "R-%s-%02d" % (self.cnum, i)
        question = None
        if e.pair:
            question = e.question(e.pair[0], e.pair[1], e.pair[0]["rule_id"])
            if question and question_answered and question["key"] == question_answered:
                question = None  # already asked and answered; keep the label and move on
        egaps = self.engine_gaps(hyps, question)
        for h in hyps:
            h["missing"] = self.missing_links(h, egaps)
        requests = self.requests(hyps, egaps)
        return hyps, shown, question, egaps, requests

    # engine gaps
    def engine_gaps(self, hyps, question):
        e, out, seen = self.e, [], set()

        def add(kind, what, why, where, **info):
            if (kind, what) in seen:
                return None
            seen.add((kind, what))
            g = OrderedDict([("gap_id", None), ("what", clean(what)), ("why", clean(why)),
                             ("where_to_look", [clean(x) for x in where]), ("status", "open")])
            info["kind"] = kind
            g["_info"] = info
            out.append(g)
            return g

        top = self.top_set(hyps)
        if e.pair:
            a, b = e.pair
            add("too_close", "%s and %s are too close to call (scores %.2f and %.2f, within %d%%)" % (
                e.src_words(a), e.src_words(b), a["score"], b["score"], round(e.margin * 100)),
                "the records fit both about equally; one more record decides it",
                ([question["question"]] if question else []) + ["the records requests drafted for this case"],
                sources=[a["key"], b["key"]], question=question)
        for h in top:
            for c in h["cases"]:
                if c in h["tested_cases"]:
                    continue
                ch = h["best"][c]
                if ch["implied"] and not ch["partial"]:  # behind a partial code, the unreadable-code gap covers it
                    P, D, lot = ch["implied"]
                    add("implied_hop", "No record shows %s receiving lot %s from %s; the hop is inferred from the lot code" % (
                        e.who(D), lot, e.who(P) if P else "its packer"),
                        "the chain from %s to case %s rests on it" % (e.src_words(h), c),
                        ["%s receiving and shipping records for lot %s" % (e.who(D), lot),
                         "%s shipping records for lot %s" % (e.who(P), lot) if P else "packer records for lot %s" % lot],
                        distributor_id=D, packer_id=P, lot_code=lot, case_ids=[c], hyps=[h["key"]])
                fl = ch.get("fl")
                if fl is not None and fl["_basis"] == "stated":
                    add("stated_farm", "Only an email says lot %s came from %s (%s)" % (
                        ch["lot"], e.who(fl["from"]), clean(fl.get("source"))),
                        "the packer lot list does not confirm it, and case %s depends on it" % c,
                        ["%s packing and harvest records for lot %s" % (e.who(fl["to"]), ch["lot"]),
                         "%s harvest records for that week" % e.who(fl["from"])],
                        packer_id=fl["to"], farm_id=fl["from"], lot_code=ch["lot"], case_ids=[c], hyps=[h["key"]])
        explained = set()
        for h in hyps:
            explained |= set(h["cases"])
        for x in e.exps:
            if x["case_id"] in explained:
                continue
            if x["stores"]:
                why = "no %s lot reached %s within %d days of packing before the purchase%s; the records that would show " \
                      "it may be missing, or the case may be unrelated" % (
                          x["product"] or "", join_and(e.who(s) for s in x["stores"]).replace(" and ", " or "), e.shelf,
                          (" (%s to %s)" % (iso(x["w0"]), iso(x["w1"]))) if x["w0"] and x["w0"] != x["w1"] else
                          (" on %s" % iso(x["w1"]) if x["w1"] else ""))
                where = ["%s receiving records for %s, %s to %s" % (e.who(s), x["product"] or "the product",
                                                                    iso(x["w0"] - days(e.shelf)) if x["w0"] else "?",
                                                                    iso(x["w1"]) if x["w1"] else "?") for s in x["stores"]]
                where.append("the case interview: what was eaten, and where and when it was bought")
            else:
                why = "the case has no store, so it cannot be tied to any delivery"
                where = ["the case interview or health department case file", "receipts or loyalty-card records"]
            add("unexplained_case", "Illness case %s%s is not explained by any candidate source" % (
                x["case_id"], (" (%s, %s)" % (" or ".join(e.who(s) for s in x["stores"]), x["product"] or "product"))
                if x["stores"] else ""),
                why, where, case_ids=[x["case_id"]], store_id=x["store_id"], store_ids=x["stores"])
        cap = 89 - 51 + 1
        if len(out) > cap:
            rest = out[cap - 1:]
            out = out[:cap - 1]
            g = OrderedDict([("gap_id", None), ("what", "%d more engine gaps of lower priority" % len(rest)),
                             ("why", "listed together so the gap ids stay within G-%s-51 to 89" % self.cnum),
                             ("where_to_look", ["the gaps above"]), ("status", "open")])
            g["_info"] = {"kind": "summary", "items": [x["what"] for x in rest]}
            out.append(g)
        for i, g in enumerate(out, 51):
            g["gap_id"] = "G-%s-%02d" % (self.cnum, i)
        return out

    def top_set(self, hyps):
        """The hypotheses whose missing links are worth a records request: rank 1, the next two when they are real
        contenders (at least half the top confidence), and both of a too-close pair."""
        if not hyps:
            return []
        top = [hyps[0]] + [h for h in hyps[1:3] if h["confidence"] >= 0.5 * hyps[0]["confidence"]]
        if self.e.pair:
            top += [h for h in self.e.pair if h not in top]
        return top

    def feasible(self, h, x):
        """Could a lot of h still have been on sale when case x bought? (pack date to pack date + shelf life)"""
        tol = days(DATE_TOLERANCE_DAYS)
        for lot in h["lots"]:
            pk = (self.e.lots.get(lot) or {}).get("pack_date")
            if pk is None or x["w0"] is None or (pk <= x["w1"] + tol and pk + days(self.e.shelf) >= x["w0"] - tol):
                return True
        return False

    # missing links per hypothesis: gaps on the chains it relies on that are not backed by records, and gaps that
    # could add a case it does not explain yet
    def missing_links(self, h, egaps):
        e = self.e
        weak_cases = [c for c in h["cases"] if c not in h["tested_cases"]]
        weak_links, weak_stores = set(), set()
        for c in weak_cases:
            ch = h["best"][c]
            weak_links |= set(ch["links"])
            weak_stores.add(ch["store"])
        dists, dates = set(), []
        for c, ch in h["best"].items():
            dists.add(ch["distributor"])
            if ch["date"]:
                dates.append(ch["date"])
        open_cases = [x for x in e.exps if x["case_id"] not in h["chains"] and self.feasible(h, x)]
        served = {S for S, ls in e.ds_by_store.items() if any(l["from"] in dists for l in ls)}
        open_stores = {s for x in open_cases for s in x["stores"]} & served
        nostore = {x["case_id"] for x in open_cases if not x["store_id"]}
        ends = [x["w1"] for x in e.exps if x["case_id"] in h["chains"] and x["w1"]] + [x["w1"] for x in open_cases if x["w1"]]
        lo = (min(dates) - days(e.shelf)) if dates else None
        hi = max(ends + dates) if (ends or dates) else None
        lots = set(h["lots"]) | {h["source"]}
        out = []
        for gid, gi in e.gap_info.items():
            k, rel = gi.get("kind"), False
            if gi.get("link_id") and gi.get("link_id") in weak_links:
                rel = True
            elif k == "lot_no_farm":
                rel = gi.get("lot_code") in lots
            elif k in ("case_no_store", "case_no_date"):
                cs = set(gi.get("case_ids") or [])
                rel = bool(cs & set(weak_cases)) or bool(cs & nostore)
            elif k in ("store_no_receiving", "store_missing_days", "unreadable_note"):
                rel = gi.get("store_id") in (weak_stores | open_stores)
            elif k == "distributor_missing_days":
                ds = [pdate(x) for x in (gi.get("dates") or [gi.get("date_from"), gi.get("date_to")]) if pdate(x)]
                rel = gi.get("distributor_id") in dists and (lo is None or hi is None or any(lo <= d <= hi for d in ds))
            elif k == "unreadable_code":
                rel = gi.get("store_id") in open_stores and gi.get("distributor_id") in dists
            elif k == "missing_file":
                rel = True
            if rel:
                out.append(gid)
        open_ids = {x["case_id"] for x in open_cases}
        for g in egaps:
            info = g["_info"]
            if h["key"] in (info.get("hyps") or []) or h["key"] in (info.get("sources") or []):
                out.append(g["gap_id"])
            elif info["kind"] == "unexplained_case" and set(info.get("case_ids") or []) & open_ids and \
                    (set(info.get("store_ids") or []) & served or not info.get("store_ids")):
                out.append(g["gap_id"])
        return out

    # records requests
    def requests(self, hyps, egaps):
        e = self.e
        top = self.top_set(hyps)
        product = e.exp_product([x["case_id"] for x in e.exps]) or ""
        top_lots = []
        for h in top:
            top_lots += [l for l in h["lots"] if l not in top_lots]
        gids = []
        for h in top:
            gids += [g for g in h["missing"] if g not in gids]
        egap_by_id = OrderedDict((g["gap_id"], g) for g in egaps)
        asks = OrderedDict()

        def add(holder, kind, gid, lots=(), raws=(), d0=None, d1=None, stores=(), packer=None, why=None):
            if not holder or e.type_of(holder) not in ROLES:
                return
            a = asks.setdefault(holder, {"items": OrderedDict(), "gap_ids": [], "why": []})
            it = a["items"].setdefault((kind, tuple(sorted(s for s in stores if s)), packer), {
                "kind": kind, "lots": [], "raws": [], "d0": None, "d1": None, "stores": [], "packer": packer})
            it["lots"] += [l for l in lots if l and l not in it["lots"]]
            it["raws"] += [r for r in raws if r and r not in it["raws"]]
            it["stores"] += [s for s in stores if s and s not in it["stores"]]
            for d in (d0, d1):
                if d:
                    it["d0"] = d if it["d0"] is None or d < it["d0"] else it["d0"]
                    it["d1"] = d if it["d1"] is None or d > it["d1"] else it["d1"]
            if gid not in a["gap_ids"]:
                a["gap_ids"].append(gid)
            if why and why not in a["why"]:
                a["why"].append(why)

        def handled(D, lots):
            """The lots of the top hypotheses a record shows passing through distributor D (may be none)."""
            return [l for l in lots if any(k[1] == D and k[2] == l for k in e.pd_by_lot) or
                    any(L["from"] == D and l in L["_lots"] for ls in e.ds_by_store.values() for L in ls)]

        def delivers(D, store):
            return any(L["from"] == D and prod_match(L.get("product"), product) for L in e.ds_by_store.get(store, []))

        for gid in gids:
            if gid in egap_by_id:
                info = egap_by_id[gid]["_info"]
                k = info["kind"]
                if k == "implied_hop":
                    lot = info["lot_code"]
                    pk = (e.lots.get(lot) or {}).get("pack_date")
                    last = max([L["_date"] for L in e.links.values() if L["_hop"] == "distributor-store" and
                                L["from"] == info["distributor_id"] and lot in L["_lots"] and L["_date"]] or [pk])
                    add(info["distributor_id"], "receiving", gid, [lot], d0=pk, d1=last,
                        why="confirms or rules out that lot %s passed through it (cases %s)" % (lot, join_and(info["case_ids"])))
                elif k == "stated_farm":
                    add(info["packer_id"], "packing", gid, [info["lot_code"]],
                        why="confirms or rules out which farm supplied lot %s" % info["lot_code"])
                elif k == "too_close":
                    q = info.get("question") or {}
                    rec = q.get("record") or {}
                    if rec.get("lot_code"):
                        lot = rec["lot_code"]
                        add(rec.get("packer_id"), "packing", gid, [lot], why="separates the two closest sources")
                        pk = (e.lots.get(lot) or {}).get("pack_date")
                        for f in q.get("separates") or []:
                            add(f, "harvest", gid, [lot], d0=pk - days(3) if pk else None, d1=pk,
                                packer=rec.get("packer_id"), why="separates the two closest sources")
                    elif rec.get("link_id"):
                        L = e.links.get(rec["link_id"])
                        if L is not None:
                            d = L["_date"]
                            add(L["from"], "shipping", gid, rec.get("lot_candidates") or [], [L.get("lot_raw")],
                                d - days(1) if d else None, d + days(1) if d else None, [L["to"]],
                                why="separates the two closest sources")
                    elif rec.get("store_id"):
                        for L in e.ds_by_store.get(rec["store_id"], []):
                            if set(L["_lots"]) & set(rec.get("lots") or []):
                                add(L["from"], "shipping", gid, [l for l in L["_lots"] if l in rec["lots"]],
                                    d0=L["_date"], d1=L["_date"], stores=[rec["store_id"]],
                                    why="separates the two closest sources")
                continue
            gi = e.gap_info.get(gid) or {}
            k = gi.get("kind")
            d0, d1 = pdate(gi.get("date_from")), pdate(gi.get("date_to"))
            if k == "unreadable_code":
                add(gi.get("distributor_id"), "shipping", gid, gi.get("lot_candidates") or [], [gi.get("lot_raw")],
                    d0 - days(1) if d0 else None, d1 + days(1) if d1 else None, [gi.get("store_id")],
                    why="gives the full lot code of a delivery to %s" % gi.get("store_id"))
            elif k == "distributor_missing_days":
                D = gi.get("distributor_id")
                add(D, "shipping", gid, handled(D, top_lots), d0=d0, d1=d1,
                    why="fills the days missing from its shipment log")
            elif k in ("store_no_receiving", "store_missing_days", "unreadable_note"):
                for D in gi.get("distributor_ids") or []:
                    if e.type_of(D) == "distributor" and delivers(D, gi.get("store_id")):
                        add(D, "shipping", gid, handled(D, top_lots), d0=d0, d1=d1, stores=[gi.get("store_id")],
                            why="shows what %s received when the store's own records are silent" % gi.get("store_id"))
            elif k == "lot_no_farm":
                add(gi.get("packer_id"), "packing", gid, [gi.get("lot_code")],
                    why="names the farm behind lot %s" % gi.get("lot_code"))
        out = []
        for i, (holder, a) in enumerate(asks.items(), 1):
            role = e.type_of(holder)
            items = list(a["items"].values())
            phrases = [self.phrase(it, product) for it in items]
            name = e.name(holder)
            lines = ["Hello %s team," % e.who(holder), ""]
            if len(phrases) == 1:
                lines.append("Please send %s within %d hours." % (phrases[0], REQUEST_HOURS))
            else:
                lines.append("Please send the following within %d hours:" % REQUEST_HOURS)
                lines += ["%d. %s%s." % (j, p[0].upper(), p[1:]) for j, p in enumerate(phrases, 1)]
            lines += ["", "We are completing a food-safety trace-back and need these records to confirm or rule out lots "
                          "that passed through %s. This is a routine records request, not a finding about your company. "
                          "If you do not hold some of these records, a short reply saying so helps just as much." % name,
                      "", "Thank you,", "[Name], Data Care trace-back team"]
            dates = [d for it in items for d in (it["d0"], it["d1"]) if d]
            subject = "Records request (%d hours): %s %s%s" % (
                REQUEST_HOURS, product or "product", join_and(sorted({it["kind"] for it in items})) + " records",
                (", %s to %s" % (iso(min(dates)), iso(max(dates)))) if dates else "")
            out.append(OrderedDict([
                ("request_id", "Q-%s-%02d" % (self.cnum, i)), ("to", holder), ("to_role", role), ("to_name", name),
                ("kind", "records_request"), ("subject", clean(subject)), ("body", "\n".join(clean(l) for l in lines)),
                ("why", clean("; ".join(a["why"]))), ("items", [OrderedDict([
                    ("records", it["kind"]), ("product", product or None), ("lots", sorted(it["lots"])),
                    ("lot_text", lot_text(it["lots"], it["raws"])), ("date_from", iso(it["d0"])),
                    ("date_to", iso(it["d1"])), ("stores", it["stores"])]) for it in items]),
                ("gap_id", a["gap_ids"][0] if a["gap_ids"] else None), ("gap_ids", a["gap_ids"]),
                ("hypotheses", [h["source"] for h in top]), ("due_hours", REQUEST_HOURS), ("round", 1),
                ("status", "draft")]))
        return out

    def phrase(self, it, product):
        e = self.e
        lt = lot_text(it["lots"], it["raws"])
        span = ""
        if it["d0"] and it["d1"]:
            span = (" on %s" % iso(it["d0"])) if it["d0"] == it["d1"] else (" %s to %s" % (iso(it["d0"]), iso(it["d1"])))
        to = (" to %s" % join_and(e.who(s) for s in it["stores"])) if it["stores"] else ""
        p = ("%s %s" % (product or "product", lt)).strip()
        if it["kind"] == "shipping":
            return "your shipping records for %s shipped%s%s" % (p, to, span) if span else \
                "your shipping records for %s%s" % (p, to)
        if it["kind"] == "receiving":
            return "your receiving and shipping records for %s%s" % (
                p, (" from%s" % span) if span and " to " in span else span)
        if it["kind"] == "packing":
            return "your packing and harvest records showing which farm or farms supplied %s" % p
        return "your harvest and shipping records for %s sent to %s%s (for %s)" % (
            product or "product", e.who(it["packer"]) if it["packer"] else "the packer", span, lt or "the lots above")


def why_sentence(e, h, pair):
    n, N = len(h["cases"]), e.N
    if h["label"] == UNRESOLVED and pair:
        other = pair[1] if h is pair[0] else pair[0]
        return "%s and %s fit the cases about equally (scores %.2f and %.2f), so the records cannot yet tell them apart." % (
            e.src_words(h), e.src_words(other), h["score"], other["score"])
    lots = h["lots"][:4]
    dists = sorted({h["best"][c]["distributor"] for c in h["cases"]})
    packers = sorted({h["best"][c]["packer"] for c in h["cases"] if h["best"][c]["packer"]})
    alone = [c for c, cr in h["credit"].items() if cr >= h["best"][c][h["skey"]] - 1e-9]
    if h["source_type"] == "farm":
        s = "%s from %s, %s%s, reached the stores of %s of %d cases through %s within %d days of packing" % (
            (e.exp_product(h["cases"]) or "product").capitalize(), e.who(h["source"]), lot_text(lots),
            (" packed by %s" % join_and(e.who(p) for p in packers)) if packers else "", n, N,
            join_and(e.who(d) for d in dists), e.shelf)
    else:
        s = "Lot %s%s%s reached the stores of %s of %d cases through %s within %d days of packing" % (
            h["source"], (", packed by %s" % join_and(e.who(p) for p in packers)) if packers else "",
            (" from %s," % join_and(e.who(f) for f in h["farms"])) if h["farms"] else " (farm unknown),", n, N,
            join_and(e.who(d) for d in dists), e.shelf)
    tail = []
    if alone:
        tail.append("%s fit%s no other source as well" % (plural(len(alone), "case"), "s" if len(alone) == 1 else ""))
    weak = len(h["cases"]) - len(h["tested_cases"])
    if weak:
        tail.append("%s rest%s on an inferred or partial link" % (plural(weak, "case"), "s" if weak == 1 else ""))
    return clean(s + ("; " + "; ".join(tail) if tail else "") + ".")


def describe(e, h):
    return "%s as the source%s: explains %d of %d cases (shelf-life window %d days after packing)." % (
        e.src_words(h), (" of %s" % lot_text(h["lots"][:6])) if h["source_type"] == "farm" and h["lots"] else "",
        len(h["cases"]), e.N, e.shelf)


def hyp_record(e, h, pair):
    ev = []
    for c in h["cases"]:
        chs = h["chains"][c]
        ch = max(chs, key=lambda x: (x[h["rkey"]], x[h["skey"]]))
        links = ch["links"] if h["level"] == "farm" else [l for l in ch["links"] if not ch.get("fl") or l != ch["fl"]["link_id"]]
        for x in links + ch["frags"]:
            if x not in ev:
                ev.append(x)
    return OrderedDict([
        ("rank", h["rank"]), ("source", h["source"]), ("source_type", h["source_type"]), ("name", e.src_words(h)),
        ("lots", h["lots"]), ("farms", h["farms"]),
        ("explains", OrderedDict([("cases", len(h["cases"])), ("of", e.N), ("case_ids", h["cases"])])),
        ("confidence", h["confidence"]), ("score", round(h["score"], 3)), ("label", h["label"]),
        ("evidence", ev[:MAX_EVIDENCE]), ("missing_links", h["missing"]), ("why", why_sentence(e, h, pair)),
        ("tested_case_ids", h["tested_cases"]), ("lot_cases", h["lot_cases"]), ("shelf_life_days", e.shelf),
        ("rule_id", h["rule_id"])])


def rule_record(e, h, hyps):
    alts = []
    for o in hyps:
        if o is h or Engine.nested(h, o) or len(alts) >= 3:
            continue
        alts.append(OrderedDict([("source", o["source"]), ("source_type", o["source_type"]),
                                 ("explains", "%d of %d" % (len(o["cases"]), e.N)), ("confidence", o["confidence"]),
                                 ("differs_when", "cases %s" % join_and(sorted(set(o["cases"]) ^ set(h["cases"]))) if
                                  set(o["cases"]) ^ set(h["cases"]) else "same cases, different lots or links")]))
    rec = hyp_record(e, h, e.pair)
    return OrderedDict([("rule_id", h["rule_id"]), ("description", describe(e, h)), ("evidence", rec["evidence"] or
                                                                                      [h["source"]]),
                        ("alternatives", alts), ("status", h["label"])])


def report(e, case, shown, question, requests, egaps, ctx_gap_text, client=None):
    L = ["# Data Care trace-back report: %s" % clean(client or case), ""]
    L.append("Case %s. Drafted by the Reconstruction Agent from the trace graph; the Validation Agent checks it before "
             "anything is sent. These are working hypotheses for investigators, not a finding against any company." % case)
    L += ["", "## In short", ""]
    if not shown:
        L.append("- No candidate source explains any of the %d cases with the records we have. See what is missing below." % e.N)
    else:
        h = shown[0]
        L.append("- Most likely source: %s. It explains %d of %d cases (confidence %.2f, %s)." % (
            e.src_words(h), len(h["cases"]), e.N, h["confidence"], h["label"]))
        L.append("- Why: %s" % why_sentence(e, h, e.pair))
        for o in shown[1:3]:
            L.append("- Next: %s explains %d of %d (confidence %.2f, %s)." % (
                e.src_words(o), len(o["cases"]), e.N, o["confidence"], o["label"]))
        explained = set()
        for h2 in e.hyps:
            explained |= set(h2["cases"])
        lone = [x["case_id"] for x in e.exps if x["case_id"] not in explained]
        if lone:
            L.append("- Not explained by any source: %s (the case may be unrelated, or its records are missing)." % join_and(lone))
    if question:
        L.append("- We have one question for you (below): the answer separates the two closest sources.")
    L.append("- We drafted %s (not sent; a person approves every send)." % plural(len(requests), "records request"))
    if shown:
        L += ["", "## Ranked sources", "", "| Rank | Source | Lots | Explains | Confidence | Label |", "|---|---|---|---|---|---|"]
        for h in shown:
            L.append("| %d | %s | %s | %d of %d | %.2f | %s |" % (h["rank"], e.src_words(h), ", ".join(h["lots"][:5]),
                                                               len(h["cases"]), e.N, h["confidence"], h["label"]))
    if question:
        L += ["", "## Question for you", "", "- **Question:** %s" % question["question"]]
        L += ["  - Option %d: %s" % (k + 1, o) for k, o in enumerate(question["options"])]
    L += ["", "## What is unconfirmed", ""]
    miss = []
    for h in shown[:3]:
        miss += [g for g in h["missing"] if g not in miss]
    texts = dict(ctx_gap_text)
    texts.update({g["gap_id"]: g["what"] for g in egaps})
    L += ["- %s: %s" % (g, clean(texts.get(g, "see gaps.json"))) for g in miss] or [
        "- Nothing: every chain behind the top sources is backed by records."]
    L += ["", "## What we asked for", ""]
    if requests:
        for r in requests:
            L.append("- To %s (%s, %s): %s" % (r["to"], r["to_name"], r["to_role"], "; ".join(
                "%s records for %s" % (it["records"], ("%s %s" % (it["product"] or "product", it["lot_text"])).strip()) +
                ((" on %s" % it["date_from"]) if it["date_from"] and it["date_from"] == it["date_to"] else
                 (" from %s to %s" % (it["date_from"], it["date_to"])) if it["date_from"] else "") for it in r["items"])))
        L.append("- Each asks for the records within %d hours, to confirm or rule out lots. Drafts only: a person approves "
                 "every send." % REQUEST_HOURS)
    else:
        L.append("- Nothing this round: the links that matter for the top sources are backed by records.")
    L += ["", "## How we ranked the sources", "",
          "- A source explains a case when a chain farm, lot, packer, distributor, store exists, the store is the case's "
          "store, and the purchase falls on or after the store received the lot and within %d days after its pack date "
          "(SHELF_LIFE_DAYS = %d). A case with no purchase date is taken as bought %d to %d days before onset." % (
              e.shelf, e.shelf, INCUBATION_MIN_DAYS, INCUBATION_MAX_DAYS),
          "- Each explained case counts the confidence of the weakest link in its chain; when other sources explain the "
          "same case as well or better, that case counts for less (a quarter less with one rival, never less than half). "
          "Two sources within %d%% of each other are too close to call." % round(e.margin * 100)]
    L += ["", "## What the labels mean", ""]
    L += ["- **%s**: %s." % (k, v) for k, v in LABEL_WORDS.items()]
    L += ["", "## Validation", "", "Pending: the Validation Agent adds its result here before the report is sent.", ""]
    text = "\n".join(L).replace("—", ", ").replace("–", "-")
    return SECRET.sub(r"\1\2[removed]", text)


def run(a):
    with open(a.graph, encoding="utf-8") as fh:
        g = json.load(fh)
    if not isinstance(g, dict):
        raise ValueError("the trace graph is not a JSON object")
    case = (a.case or g.get("case_id") or "C-0000").strip().upper()
    os.makedirs(a.out_dir, exist_ok=True)
    eng = Engine(g, a.shelf_life_days, a.margin)
    w = Writer(eng, case, a.top)
    answered_key, answer_note = None, None
    if a.answer:
        rid, _, idx = a.answer.rpartition("=")
        hyps, shown, question, egaps, reqs = w.run()
        if question and (not rid or rid.strip() == question["rule_id"]) and re.match(r"^\d+$", idx.strip()):
            k = int(idx)
            if 0 <= k < len(question["options"]):
                eng.apply(question["apply"][k])
                answered_key = question["key"]
                answer_note = "client answer to \"%s\": %s" % (question["question"], question["options"][k])
        if answered_key is None:
            answer_note = "--answer %s did not match the current question; nothing applied" % a.answer
    hyps, shown, question, egaps, reqs = w.run(answered_key)
    ctx_text = {gid: gi.get("what") for gid, gi in eng.gap_info.items() if gi.get("what")}
    gpath = os.path.join(os.path.dirname(os.path.abspath(a.graph)), "gaps.json")
    if os.path.abspath(gpath) != os.path.abspath(os.path.join(a.out_dir, "gaps.json")) and os.path.exists(gpath):
        try:
            with open(gpath, encoding="utf-8") as fh:
                for x in json.load(fh):
                    if isinstance(x, dict) and x.get("gap_id") and x.get("what"):
                        ctx_text.setdefault(x["gap_id"], x["what"])
        except (OSError, ValueError):
            pass
    out = lambda name: os.path.join(a.out_dir, name)
    hyp_json = [hyp_record(eng, h, eng.pair) for h in shown]
    if answer_note:
        for r in hyp_json:
            r["client_answer"] = answer_note
    rules = [rule_record(eng, h, hyps) for h in shown]
    if answer_note and answered_key:
        for r in rules:
            r["evidence"].append("client answer")
    gaps = [OrderedDict((k, v) for k, v in g.items() if not k.startswith("_")) for g in egaps]
    with open(out("hypotheses.json"), "w", encoding="utf-8") as fh:
        json.dump(hyp_json, fh, indent=2)
    with open(out("rules.json"), "w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=2)
    with open(out("gaps.json"), "w", encoding="utf-8") as fh:
        json.dump(gaps, fh, indent=2)
    if question:
        with open(out("question.json"), "w", encoding="utf-8") as fh:
            json.dump(question, fh, indent=2)
    elif os.path.exists(out("question.json")):
        os.remove(out("question.json"))  # an old question from an earlier run must not be sent again
    with open(out("requests.json"), "w", encoding="utf-8") as fh:
        json.dump(reqs, fh, indent=2)
    with open(out("requests.md"), "w", encoding="utf-8") as fh:
        fh.write(requests_md(case, reqs))
    with open(out("report_draft.md"), "w", encoding="utf-8") as fh:
        fh.write(report(eng, case, shown, question, reqs, egaps, ctx_text, a.client))
    counts = OrderedDict((l, sum(1 for h in shown if h["label"] == l)) for l in LABELS)
    summary = OrderedDict([("status", "needs_client" if question else "done"), ("case_id", case), ("kind", "trace"),
                           ("counts", counts), ("hypotheses", len(shown)), ("questions", 1 if question else 0),
                           ("question", question["question"] if question else None),
                           ("top", OrderedDict([("source", shown[0]["source"]), ("source_type", shown[0]["source_type"]),
                                                ("confidence", shown[0]["confidence"]), ("label", shown[0]["label"])])
                            if shown else None),
                           ("cases", eng.N), ("requests", len(reqs)), ("shelf_life_days", eng.shelf),
                           ("too_close_margin", eng.margin), ("client_answer", answer_note)])
    if eng.graph_shelf and int(eng.graph_shelf) != eng.shelf:
        summary["note"] = "the scan expanded partial codes with a %s-day window; ranking used %d" % (eng.graph_shelf, eng.shelf)
    with open(out("summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    top = "; ".join("%d. %s %s (%d of %d, confidence %.2f, %s)" % (
        h["rank"], h["source_type"], h["source"], len(h["cases"]), eng.N, h["confidence"], h["label"]) for h in shown[:3])
    return "%s: %s; %s; %d records request draft%s; shelf-life window %d days" % (
        case, top or "no source explains any case", "question for the client" if question else "no question",
        len(reqs), "" if len(reqs) == 1 else "s", eng.shelf)


def requests_md(case, reqs):
    L = ["# Records requests for %s (drafts, not sent)" % case, "",
         "A person approves every send. Each request asks for records within %d hours to confirm or rule out lots, and none "
         "says or implies that the company did anything wrong." % REQUEST_HOURS, ""]
    if not reqs:
        L += ["No records requests this round: the links that matter for the top sources are backed by records.", ""]
    for r in reqs:
        L += ["## %s to %s (%s), %s" % (r["request_id"], r["to"], r["to_name"], r["to_role"]), "",
              "To: %s (%s)" % (r["to"], r["to_role"]), "Subject: %s" % r["subject"], "", r["body"], "",
              "Why we ask: %s (gaps %s)" % (r["why"], ", ".join(r["gap_ids"])), ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rank the likely sources of a food-outbreak case from its trace graph.")
    ap.add_argument("--graph", required=True, help="trace_graph.json from trace_scan.py")
    ap.add_argument("--case", help="Data Care case id, e.g. C-0001 (default: the graph's)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--top", type=int, default=TOP_DEFAULT, help="hypotheses to keep (default %d)" % TOP_DEFAULT)
    ap.add_argument("--answer", help="the client's answer to question.json: RULE_ID=OPTION_INDEX (0-based)")
    ap.add_argument("--client", help="the client's name for the report")
    ap.add_argument("--shelf-life-days", type=int, default=SHELF_LIFE_DAYS,
                    help="days after packing a lot can be sold (default %d)" % SHELF_LIFE_DAYS)
    ap.add_argument("--margin", type=float, default=TOO_CLOSE_MARGIN,
                    help="top two within this share of the top score are too close to call (default %.2f)" % TOO_CLOSE_MARGIN)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    try:
        line = run(a)
    except Exception as exc:  # report the crash in summary.json so the agent can read it
        with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump({"status": "failed", "kind": "trace", "error": "%s: %s" % (type(exc).__name__, exc)}, fh, indent=2)
        print("failed: %s: %s" % (type(exc).__name__, exc))
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
