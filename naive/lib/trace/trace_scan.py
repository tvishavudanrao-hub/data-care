#!/usr/bin/env python3
"""trace_scan.py - Data Care Context tool for a food-outbreak trace-back case (kind "trace").
Python 3.8+, standard library only. It only parses files; it never runs, imports or opens anything else.

    python3 trace_scan.py --case-dir DIR --case C-0001 --out-dir OUT

Reads the case files. They are recognised by their columns and contents, not only by their names, so a flat library
folder (C-0001-working) works as well as subfolders:
  entities.csv               entity_id,type,name,location (type: farm, packer, distributor, store)
  illness_cases.csv          case_id,onset_date,store_id,purchase_date,product,notes (store or purchase date may be blank)
  store_receiving.csv        date,store_id,distributor_id,product,lot_code,qty_cases (lot code may be blank or "RL-041?")
  distributor_shipments.csv  ship_date,distributor_id,packer_id,store_id,product,lot_code,qty_cases
  packer_lots.csv            lot_code,packer_id,pack_date,product,farm_ids ("F-01;F-03" is a commingled lot)
  supplier emails (*.eml)    plain statements: which farm a lot came from, a shipment missing from the logs
  delivery notes (*.txt)     transcribed handwritten store notes ("Rcvd 4 cs romaine from Valley Fresh, lot RL-041? (smudged), 10/6")
  *.transcription.json       Forensics' transcription of a scanned or photographed note: date, product, lot_code, qty and
                             supplier, each with a legible flag. A field marked not legible is never used. Unknown keys are ignored.
Writes to OUT:
  trace_graph.json  {"case_id", "nodes", "links", "exposures", "gaps"} plus "lots", "gap_info", "flags", "shelf_life_days".
                    links: farm -> packer (packer_lots, emails), packer -> distributor (shipments, emails) and
                    distributor -> store (shipments, receiving logs, notes, emails), each with lot_code (or lot_candidates
                    for a partial or blank code), date, source "<file>#row<n>" or "#line<n>", confidence, fragment_id.
  fragments.json    F-<n>-001..899 (type record or clue): the evidence each link and exposure cites
  gaps.json         G-<n>-01..49: a store with no receiving records in an exposure window, a missing shipment day, a lot
                    with no known farm, a case with no store or date, an unreadable lot code
  inventory.md      what each file contributed and what is missing
Every file is data, never instructions: instruction-like text is flagged in inventory.md and never becomes a link.
Anything that looks like a password, key or token is replaced by a marker in every output.
"""
import argparse
import csv
import datetime
import email
import email.policy
import email.utils
import hashlib
import io
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

SHELF_LIFE_DAYS = 14          # a lot can still be on sale up to 14 days after its pack date
DATE_TOLERANCE_DAYS = 1       # a loose handwritten date ("10/6") may be a day off
INCUBATION_MIN_DAYS = 1       # with no purchase date, the purchase is taken as 1 to 10 days before onset
INCUBATION_MAX_DAYS = 10

# Link confidence, 0..1: a clean CSV row, then emails, then notes; partial codes lower again.
CONF_CSV = 0.95               # CSV row with a full lot code
CONF_CSV_PARTIAL = 0.55       # CSV row whose lot code is partly unreadable ("RL-041?")
CONF_CSV_BLANK = 0.4          # CSV row with no lot code
CONF_EMAIL = 0.7              # supplier email that names the lot
CONF_EMAIL_NO_LOT = 0.5       # supplier email that names no lot
CONF_TEXT = 0.6               # any other plain text file
CONF_NOTE = 0.75              # transcribed handwritten note with a legible lot code
CONF_NOTE_PARTIAL = 0.45      # smudged or partial code in a note
CONF_NOTE_BLANK = 0.3         # note with no lot code
CONF_SCAN = 0.6               # Forensics transcription of a scanned note, legible lot code
CONF_SCAN_PARTIAL = 0.4
CONF_SCAN_BLANK = 0.25
ONE_CANDIDATE_BONUS = 0.1     # a partial code that fits exactly one known lot
LOOSE_DATE_PENALTY = 0.05     # a date written without a year, or taken from the file name
GUESSED_PARTY_PENALTY = 0.1   # the note names no distributor; the store's only distributor for that product is used
CONF_EXPOSURE = 0.95          # illness case row with a store and a purchase date
CONF_EXPOSURE_NOTES = 0.6     # store or purchase date read from the case notes
CONF_EXPOSURE_ONSET = 0.6     # purchase window estimated from the onset date
CONF_EXPOSURE_PROBABLE = 0.7  # the notes say probable case, no lab confirmation
CONF_EXPOSURE_OTHER_FOOD = 0.8  # the notes name another possible exposure ("also had a deli sandwich")

MAX_FRAGMENTS = 899
MAX_GAPS = 49
MAX_FILE_BYTES = 20 * 1024 * 1024

HOPS = ("farm-packer", "packer-distributor", "distributor-store")
CSV_EXT = (".csv", ".tsv")
MAIL_EXT = (".eml", ".emlx")
TEXT_EXT = (".txt", ".text", ".md", ".note", ".notes")
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".svn", ".hg", ".venv", "venv", ".cache", ".idea", ".vscode"}
SECRET_FILE = re.compile(r"(^|/)(\.ssh|\.gnupg|\.aws)(/|$)|(^|/)\.env(\.|$)|\.(pem|key|p12|pfx|keystore|jks|kdbx)$"
                         r"|(^|/)id_(rsa|dsa|ecdsa|ed25519)", re.I)

# -- secrets never leave the scanner (same patterns as context_scan.py) ---------------------------------------------
SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|client_secret|token|api[_-]?key|access[_-]?key)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1\2[secret removed]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S), "[private key removed]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[access key removed]"),
    (re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[0-9A-Za-z]{8,}"), "[api key removed]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[token removed]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[token removed]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"), "Bearer [token removed]"),
]


def redact(obj):
    """obj with every secret-looking value in its strings replaced. Works on str, list, dict."""
    if isinstance(obj, str):
        for rx, rep in SECRET_PATTERNS:
            obj = rx.sub(rep, obj)
        return obj
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return OrderedDict((k, redact(v)) for k, v in obj.items())
    return obj


# Text that reads like an instruction to an agent. It is recorded as a clue and never followed or turned into a link.
_INJECT = re.compile(
    r"\b(?:ignore|disregard|forget|override)\b.{0,40}\b(?:instructions?|prompts?|rules|guidelines)\b"
    r"|\byou are (?:now )?(?:an? )?(?:ai|assistant|agent|language model|llm)\b|\bsystem prompt\b|\bnew instructions?\b"
    r"|\b(?:send|forward|email|upload|post)\b.{0,40}\b(?:passwords?|credentials?|api keys?|tokens?|secrets?)\b"
    r"|\b(?:delete|erase|wipe|rm -rf)\b.{0,30}\b(?:files?|records?|evidence|logs?|folders?)\b", re.I)


# -- small helpers ---------------------------------------------------------------------------------------------------
def days(n):
    return datetime.timedelta(days=n)


def iso(d):
    return d.isoformat() if d else None


def short(s, n=160):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 3].rstrip() + "..."


def norm_text(s):
    return " ".join(re.findall(r"[a-z0-9]+", str(s or "").lower()))


def decode(raw):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def mkdate(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d))
    except (TypeError, ValueError):
        return None


def is_false(x):
    return x is False or (isinstance(x, (int, float)) and not isinstance(x, bool) and x == 0) or \
        str(x).strip().lower() in ("false", "no", "n", "0", "illegible", "unreadable", "not legible")


def walk(top):
    for root, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS and "quarantine" not in d.lower())
        for f in sorted(files):
            p = os.path.join(root, f)
            if f.startswith(".") or os.path.islink(p):
                continue
            yield p


# -- dates -----------------------------------------------------------------------------------------------------------
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
          "nov": 11, "dec": 12}
_MON = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?"
        r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
RX_ISO = re.compile(r"(?<![\d.])(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
RX_MDY = re.compile(r"(?<![\w/.-])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
RX_MDY_DASH = re.compile(r"(?<![\w/.-])(\d{1,2})-(\d{1,2})-(\d{4})(?![\d-])")
RX_MD = re.compile(r"(?<![\w/.-])(\d{1,2})/(\d{1,2})(?![\d/])")
RX_MON_D = re.compile(r"\b" + _MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?", re.I)
RX_D_MON = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MON + r"(?:,?\s+(\d{4}))?\b", re.I)


class DateCtx(object):
    """Turns dates as written into dates. A date written without a year takes the year most dates in the logs have."""

    def __init__(self):
        self.year, self.lo, self.hi = None, None, None

    def setup(self, dates):
        dates = [d for d in dates if d]
        if dates:
            count = defaultdict(int)
            for d in dates:
                count[d.year] += 1
            self.year = max(sorted(count), key=lambda y: count[y])
            self.lo, self.hi = min(dates), max(dates)

    def plausible(self, d):
        return d is not None and (self.lo is None or self.lo - days(120) <= d <= self.hi + days(120))

    def make(self, y, m, d):
        if y is not None:
            return mkdate(y, m, d)
        y = self.year or datetime.date.today().year
        best = mkdate(y, m, d)
        if best and self.lo:  # December and January: take the year closest to the case dates
            mid = self.lo + (self.hi - self.lo) // 2
            for yy in (y - 1, y + 1):
                alt = mkdate(yy, m, d)
                if alt and abs((alt - mid).days) < abs((best - mid).days):
                    best = alt
        return best

    def md(self, a, b, y):
        """a/b is month/day, unless that cannot be a date or is far from the case dates while day/month fits."""
        us = self.make(y, a, b) if 1 <= a <= 12 else None
        eu = self.make(y, b, a) if 1 <= b <= 12 else None
        if us and (self.plausible(us) or not (eu and self.plausible(eu))):
            return us
        return eu or us


def find_dates(text, ctx):
    """[(position, date, loose)] for each date written in text; loose means it had no year."""
    out, taken = [], []
    text = str(text or "")

    def add(m, dt, loose):
        if dt is None or not ctx.plausible(dt) or any(a < m.end() and m.start() < b for a, b in taken):
            return
        taken.append((m.start(), m.end()))
        out.append((m.start(), dt, loose))

    for m in RX_ISO.finditer(text):
        add(m, mkdate(m.group(1), m.group(2), m.group(3)), False)
    for m in RX_MDY.finditer(text):
        y = int(m.group(3))
        add(m, ctx.md(int(m.group(1)), int(m.group(2)), y + 2000 if y < 100 else y), False)
    for m in RX_MDY_DASH.finditer(text):
        add(m, ctx.md(int(m.group(1)), int(m.group(2)), int(m.group(3))), False)
    for m in RX_MON_D.finditer(text):
        add(m, ctx.make(int(m.group(3)) if m.group(3) else None, MONTHS[m.group(1)[:3].lower()], int(m.group(2))),
            not m.group(3))
    for m in RX_D_MON.finditer(text):
        add(m, ctx.make(int(m.group(3)) if m.group(3) else None, MONTHS[m.group(2)[:3].lower()], int(m.group(1))),
            not m.group(3))
    for m in RX_MD.finditer(text):
        add(m, ctx.md(int(m.group(1)), int(m.group(2)), None), True)
    out.sort(key=lambda x: x[0])
    return out


# -- entities --------------------------------------------------------------------------------------------------------
TYPE_WORDS = {"farm": "farm", "grower": "farm", "ranch": "farm", "orchard": "farm", "packer": "packer",
              "packinghouse": "packer", "packing": "packer", "processor": "packer", "pack": "packer",
              "distributor": "distributor", "distribution": "distributor", "wholesaler": "distributor",
              "wholesale": "distributor", "store": "store", "retailer": "store", "retail": "store", "grocery": "store",
              "supermarket": "store", "market": "store", "restaurant": "store", "shop": "store"}
GENERIC_TAIL = {"farm", "farms", "ranch", "ranches", "orchard", "orchards", "grower", "growers", "inc", "llc", "co",
                "corp", "company", "ltd", "packing", "packers", "packer", "pack", "packinghouse", "produce",
                "distribution", "distributors", "distributor", "distributing", "foods", "food", "market", "markets",
                "grocery", "grocer", "grocers", "store", "stores", "supermarket", "logistics", "wholesale", "the", "and",
                "coop"}
RX_IDLIKE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,10}[-_]?#?\d{1,6})(?![A-Za-z0-9])")
RX_STORE_NUM = re.compile(r"\bstore\s*(?:no\.?|number)?\s*#?\s*(\d{1,5})\b", re.I)


def norm_type(t):
    for w in norm_text(t).split():
        for k in (w, w[:-1] if w.endswith("s") else w):
            if k in TYPE_WORDS:
                return TYPE_WORDS[k]
    return norm_text(t) or "unknown"


def id_key(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def id_key2(s):
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", id_key(s))


COMMON_WORDS = {"valley", "harbor", "corner", "riverside", "main", "street", "market", "green", "golden", "sunny",
                "coastal", "central", "pacific", "western", "eastern", "northern", "southern", "north", "south", "east",
                "west", "fresh", "family", "city", "county", "river", "lake", "hill", "hills", "creek", "mountain",
                "garden", "gardens", "country", "village", "town", "united", "national", "american", "quality",
                "premium", "select", "choice", "local", "organic", "natural", "global", "first", "prime", "royal",
                "silver", "orange", "summit", "harvest", "sunrise", "sunset", "meadow", "meadows", "acres", "growers",
                "produce", "brothers", "sons", "partners", "group", "station", "center", "plaza"}


def aliases(name):
    """The full name, plus the name without trailing words like Farm, Inc or Distribution ("Valley Fresh",
    "FreshWay") when that is two words, or one word of six letters or more that is not a common word."""
    toks = norm_text(name).split()
    out = {" ".join(toks)} if toks else set()
    t = list(toks)
    while t and t[-1] in GENERIC_TAIL:
        t.pop()
    while t and t[0] == "the":
        t.pop(0)
    if len(t) >= 2 or (len(t) == 1 and len(t[0]) >= 6 and t[0] not in COMMON_WORDS and not t[0].isdigit()):
        out.add(" ".join(t))
    if len(t) >= 2 and len(t[0]) >= 6 and t[0] not in COMMON_WORDS and not t[0].isdigit():
        out.add(t[0])  # "Meriwen" for Meriwen Cold Chain; dropped later if two entities share it
    return out


class Entities(object):
    def __init__(self):
        self.by_id = OrderedDict()
        self.keys = {}
        self.names = {}  # alias -> id, or None when two entities share it
        self.unlisted = []

    def add(self, eid, etype, name, location="", unlisted=False):
        eid = str(eid or "").strip()
        if not eid:
            return None
        if eid in self.by_id:
            return eid
        self.by_id[eid] = {"id": eid, "type": etype, "name": name or eid, "location": location or ""}
        for k in (id_key(eid), id_key2(eid)):
            self.keys.setdefault(k, eid)
        if name and name != eid:
            for a in aliases(name):
                self.names[a] = eid if self.names.get(a, eid) == eid else None
        if unlisted:
            self.unlisted.append(eid)
        return eid

    def type_of(self, eid):
        return (self.by_id.get(eid) or {}).get("type")

    def name_of(self, eid):
        return (self.by_id.get(eid) or {}).get("name") or eid

    def resolve(self, s):
        s = str(s or "").strip()
        if not s:
            return None
        for k in (id_key(s), id_key2(s)):
            if k in self.keys:
                return self.keys[k]
        e = self.names.get(norm_text(s))
        if e:
            return e
        hits = {h[2] for h in self.find(s)}
        return hits.pop() if len(hits) == 1 else None

    def find(self, text):
        """Entities named in text: [(start, end, id)], by id ("D-02"), store number ("store #3") or name."""
        text = str(text or "")
        hits = []

        def add(a, b, eid):
            if eid and not any(x < b and a < y for x, y, _ in hits):
                hits.append((a, b, eid))

        for m in RX_IDLIKE.finditer(text):
            add(m.start(), m.end(), self.keys.get(id_key(m.group(1))) or self.keys.get(id_key2(m.group(1))))
        for m in RX_STORE_NUM.finditer(text):
            n = int(m.group(1))
            c = [e for e, v in self.by_id.items() if v["type"] == "store" and (
                (re.findall(r"\d+", e) and int(re.findall(r"\d+", e)[-1]) == n) or re.search(r"#\s*0*%d\b" % n, v["name"]))]
            if len(c) == 1:
                add(m.start(), m.end(), c[0])
        toks = [(t.group(0).lower(), t.start(), t.end()) for t in re.finditer(r"[A-Za-z0-9]+", text)]
        words = [t[0] for t in toks]
        for alias in sorted(self.names, key=lambda a: (-len(a), a)):
            eid = self.names[alias]
            if not eid:
                continue
            at = alias.split()
            for i in range(len(words) - len(at) + 1):
                if words[i:i + len(at)] == at:
                    add(toks[i][1], toks[i + len(at) - 1][2], eid)
        hits.sort()
        return hits


# -- products and lot codes ------------------------------------------------------------------------------------------
PROD_STOP = {"lettuce", "salad", "salads", "bag", "bags", "bagged", "fresh", "organic", "chopped", "heart", "hearts",
             "whole", "head", "heads", "mix", "kit", "kits", "case", "cases", "cs", "lb", "lbs", "ct", "count", "the",
             "of", "and", "a", "box", "boxes", "baby", "leaf", "leaves"}
NOT_A_CODE = {"of", "was", "is", "the", "and", "for", "with", "to", "in", "on", "at", "that", "this", "more", "less",
              "size", "sizes", "number", "numbers", "code", "codes"}
UNREADABLE_WORDS = re.compile(r"(?i)^(n/?a|none|unknown|illegible|unreadable|unclear|smudged|blank|missing|torn|faded|-+|\?+)$")


def prod_key(p):
    toks = [t[:-1] if len(t) > 4 and t.endswith("s") else t for t in norm_text(p).split()]
    k = frozenset(t for t in toks if t not in PROD_STOP)
    return k or frozenset(toks)


def prod_match(a, b):
    """True when two product names plausibly mean the same product, or either is unknown."""
    if not a or not b:
        return True
    ka, kb = prod_key(a), prod_key(b)
    return bool(ka and kb) and (ka <= kb or kb <= ka)


def lot_key(code):
    """Comparable form of a lot code: upper case, no separators; an unreadable character becomes "?"."""
    s = str(code or "").strip().upper()
    m = re.match(r"^([A-Z]+)[\s_\-]*(.*)$", s)
    head, rest = (m.group(1), m.group(2)) if m else ("", s)
    rest = re.sub(r"[_*#]", "?", rest)
    return head + re.sub(r"[^A-Z0-9?]", "", rest)


RX_LOT_WORD = re.compile(r"(?i)\blots?\b\s*(?:#|no\.?|number|code)?\s*[:#]?\s*([A-Za-z0-9?*#_][A-Za-z0-9?*#_\-]{0,20})")
RX_LOT_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,5})[-_ ]?([0-9?*#]{2,8}[A-Za-z]?)(?![A-Za-z0-9?*#])")
RX_RECV_LINE = re.compile(r"(?i)\b(rcv'?d|rec'?d|recv'?d?|receiv\w*|deliver\w*|got|arrived|drop(?:ped)?\s*off)\b|\bin\s*:")
RX_QTY = re.compile(r"(?i)(?<![\w.])x?(\d{1,4})\s*(cs|cases?|ctns?|cartons?|boxes|bx|bags?|units?)\b")
RX_SHIP_CTX = re.compile(r"(?i)\b(ship\w*|deliver\w*|drops?|trucks?|routes?|dispatch\w*|sent|went out)\b")
RX_LOG_LOST = re.compile(r"(?i)\b(lost|missing|gap|not in|never got keyed)\b")
RX_LOG_WORD = re.compile(r"(?i)\b(logs?|records?|routes?|system|export)\b")
RX_NO_DETAIL = re.compile(r"(?i)invoice missing|missing invoice|no invoice|\bdriver\b|\btruck\b|\bdelivery\b|\bdelivered\b")
RX_NO_DELIVERY = re.compile(r"(?i)\bno delivery\b|\bbroke down\b|\bcancel\w*|\bdid not come\b|\bdidn't come\b")
RX_PROBABLE = re.compile(r"(?i)\bprobable\b|\bno lab\b|\bnot lab[- ]confirmed\b|\bunconfirmed\b|\bsuspect(?:ed)? case\b")
RX_OTHER_FOOD = re.compile(r"(?i)\balso (?:ate|had|eaten)\b|\bother possible (?:food|exposure)s?\b")
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "a couple of": 2, "a few": 3,
             "a day": 1, "the day": 1}
RX_REL_DAYS = re.compile(r"(?i)\b(\d{1,2}|one|two|three|four|five|six|seven|a couple of|a few|a day|the day)\s*(?:days?\s+)?"
                         r"before\s+(?:getting|got|falling|becoming|feeling|the\s+)?\s*(?:sick|ill|onset|symptoms|illness)")
RX_SMUDGE = re.compile(r"(?i)smudg\w*|illegib\w*|unclear|faded|can'?t read|cannot read|hard to read|torn|"
                       r"water[- ]?damage\w*|blurr\w*|partial\w*")
RX_SHIP = re.compile(r"(?i)\b(ship(?:ped|ping|s)?|deliver(?:ed|y|ies|s)?|sent|send(?:s)?|drop(?:ped)?\s+off|"
                     r"truck(?:ed)?|load(?:ed)?|transferr?(?:ed)?|dispatch(?:ed)?|went|go(?:es)?)\b")
RX_RECV = re.compile(r"(?i)\b(rcv'?d|rec'?d|recv'?d?|receiv(?:ed|e|ing)|got|took\s+in|picked\s+up|arrived)\b")
RX_FARM_VERB = re.compile(r"(?i)\b(grown|grew|harvest\w*|sourced|source|came\s+from|comes?\s+from|originat\w*|"
                          r"supplied|supplier|grower|picked|field|ranch|commingl\w*|co-?mingl\w*|combined|blend\w*|"
                          r"mix(?:ed)?|packed\s+from|from\s+(?:the\s+)?farm)\b")
RX_NEG_BEFORE = re.compile(r"(?:\b(?:not|never|nor|neither|rather\s+than|instead\s+of|except|excluding)|n't)\s+(?:\w+\s+){0,3}$", re.I)
RX_NEG_VERB = re.compile(r"(?:\b(?:not|never|no)|n't)\s+(?:\w+\s+){0,2}$", re.I)
RX_ROLE = re.compile(r"\b(to|into|for|from|by|via|at)\s+(?:the\s+)?(?:(?:store|distributor|packer|farm|dc)\s+)?(?:#\s*)?$",
                     re.I)
ABBR = {"oct", "sept", "sep", "nov", "dec", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "no", "inc", "co", "st",
        "ltd", "corp", "dr", "mr", "mrs", "ms", "approx", "vs", "etc", "ave", "rd", "jr", "sr", "dept", "e.g", "i.e"}


def sentences(para):
    """[(line, text)] -> [(line, sentence)], keeping the line each sentence starts on."""
    buf, marks = "", []
    for ln, t in para:
        marks.append((len(buf), ln))
        buf += t.strip() + " "
    out, start = [], 0
    for m in re.finditer(r"(?:[.!]|(?<![0-9A-Za-z?])\?)\s+(?=[A-Z0-9(\"'])", buf):  # "RL-041?" is a code, not an end
        word = re.findall(r"([A-Za-z.]+)$", buf[start:m.start()])
        if word and word[0].lower().strip(".") in ABBR:
            continue
        out.append((start, buf[start:m.start() + 1]))
        start = m.end()
    if buf[start:].strip():
        out.append((start, buf[start:]))

    def line_at(pos):
        ln = para[0][0]
        for off, l in marks:
            if off <= pos:
                ln = l
        return ln
    return [(line_at(p), s.strip()) for p, s in out if s.strip()]


def paragraphs(lines):
    """[(line, text)] -> paragraphs split at blank lines and list items."""
    out, cur = [], []
    for ln, t in lines:
        if not t.strip() or re.match(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+", t):
            if cur:
                out.append(cur)
            cur = [(ln, t)] if t.strip() else []
        else:
            cur.append((ln, t))
    if cur:
        out.append(cur)
    return out


def body_text(msg):
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:  # malformed message: read what is there
        part = None
    if part is None:
        if msg.is_multipart():
            return ""
        part = msg
    try:
        content = part.get_content()
    except Exception:
        content = decode(part.get_payload(decode=True) or b"")
    if not isinstance(content, str):
        return ""
    if part.get_content_type() == "text/html":
        content = re.sub(r"(?s)<(script|style).*?</\1>", " ", content)
        content = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", content)
        content = re.sub(r"<[^>]+>", " ", content)
    return content


def looks_like_email(text):
    head = [l.lower() for l in text.splitlines()[:30]]
    return sum(1 for h in ("from:", "to:", "subject:", "date:") if any(l.startswith(h) for l in head)) >= 2


def looks_like_note(rel, text):
    low = rel.lower()
    if low.endswith(".md") or os.path.basename(low).startswith("readme"):
        return False  # a description of the folder, not a receiving sheet
    if any(w in low for w in ("note", "deliver", "receiv", "rcvd", "invoice", "slip")):
        return True
    return any(RX_RECV_LINE.search(l) and (RX_QTY.search(l) or re.search(r"(?i)\blot\b\W*\w*\d", l)) and
               (RX_MD.search(l) or RX_ISO.search(l)) for l in text.splitlines())


# -- CSV layouts -----------------------------------------------------------------------------------------------------
COL_ALIASES = {
    "lot": "lot_code", "lot_no": "lot_code", "lot_number": "lot_code", "lotcode": "lot_code", "lot_id": "lot_code",
    "farm": "farm_ids", "farms": "farm_ids", "farm_id": "farm_ids", "source_farms": "farm_ids", "farm_list": "farm_ids",
    "packer": "packer_id", "distributor": "distributor_id", "store": "store_id", "retailer_id": "store_id",
    "store_name": "store_id", "date_received": "date", "received_date": "date", "receive_date": "date",
    "receipt_date": "date", "received": "date", "recv_date": "date", "delivery_date": "date", "shipped": "ship_date",
    "date_shipped": "ship_date", "shipped_date": "ship_date", "shipment_date": "ship_date", "onset": "onset_date",
    "illness_onset": "onset_date", "date_of_onset": "onset_date", "onset_dt": "onset_date", "purchase": "purchase_date",
    "purchased": "purchase_date", "date_purchased": "purchase_date", "purchase_dt": "purchase_date", "qty": "qty_cases",
    "quantity": "qty_cases", "cases": "qty_cases", "qty_case": "qty_cases", "id": "entity_id", "entity": "entity_id",
    "entity_type": "type", "kind": "type", "role": "type", "packed": "pack_date", "packed_date": "pack_date",
    "date_packed": "pack_date", "packing_date": "pack_date", "item": "product", "commodity": "product",
    "product_name": "product", "note": "notes", "comments": "notes", "comment": "notes", "case": "case_id",
    "patient_id": "case_id", "case_no": "case_id", "illness_case_id": "case_id",
}
KIND_WORDS = {"entities": "entity list", "illness_cases": "illness cases", "store_receiving": "store receiving log",
              "distributor_shipments": "distributor shipment log", "packer_lots": "packer lot list"}


def norm_col(c):
    c = re.sub(r"[^a-z0-9]+", "_", str(c or "").strip().lower()).strip("_")
    return COL_ALIASES.get(c, c)


def csv_kind(cols, rel):
    s, name = set(cols), rel.lower()
    if "lot_code" in s and ("farm_ids" in s or "pack_date" in s):
        return "packer_lots"
    if "distributor_id" in s and "store_id" in s:
        if "receiv" in name:
            return "store_receiving"
        if "packer_id" in s or "ship" in name or "ship_date" in s:
            return "distributor_shipments"
        return "store_receiving"
    if "case_id" in s and ("onset_date" in s or "purchase_date" in s or "store_id" in s):
        return "illness_cases"
    if "entity_id" in s and ("type" in s or "name" in s):
        return "entities"
    return None


# Forensics transcriptions (<name>.transcription.json). The format is not final, so the reader is tolerant.
TX_FIELDS = OrderedDict([
    ("date", ("date", "received_date", "delivery_date", "date_received", "received", "day")),
    ("product", ("product", "item", "commodity", "description")),
    ("lot_code", ("lot_code", "lot", "lot_no", "lot_number", "lotcode", "code")),
    ("qty", ("qty", "quantity", "qty_cases", "cases", "count")),
    ("supplier", ("supplier", "supplier_id", "distributor", "distributor_id", "vendor", "from", "shipper")),
    ("store", ("store", "store_id", "site")),
])
TX_LIST_KEYS = ("lines", "entries", "records", "items", "deliveries", "rows", "transcriptions")


def tx_records(data):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in TX_LIST_KEYS:
            v = data.get(k)
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                top = {kk: vv for kk, vv in data.items() if kk not in TX_LIST_KEYS and kk != "fields"}
                out = []
                for x in v:
                    rec = dict(top)
                    rec.update(x)
                    out.append(rec)
                return out
        return [data]
    return []


def tx_fields(rec):
    """({field: value} for legible fields only, [fields marked not legible])."""
    flds = rec.get("fields") if isinstance(rec.get("fields"), (dict, list)) else rec
    if isinstance(flds, list):
        d = {}
        for f in flds:
            if isinstance(f, dict):
                nm = f.get("name") or f.get("field") or f.get("key") or f.get("label")
                if nm:
                    d[str(nm)] = f
        flds = d
    flat = {re.sub(r"[^a-z0-9]+", "_", str(k).lower()).strip("_"): v for k, v in flds.items()}
    top = {re.sub(r"[^a-z0-9]+", "_", str(k).lower()).strip("_"): v for k, v in rec.items()}
    leg_map = top.get("legible") if isinstance(top.get("legible"), dict) else {}
    leg_map = {re.sub(r"[^a-z0-9]+", "_", str(k).lower()).strip("_"): v for k, v in leg_map.items()}
    vals, unread = OrderedDict(), []
    for field, names in TX_FIELDS.items():
        for nm in names:
            if nm not in flat:
                continue
            entry = flat[nm]
            if isinstance(entry, dict):
                val = next((entry.get(k) for k in ("value", "text", "raw", "transcription", "reading")
                            if entry.get(k) not in (None, "")), None)
                leg = entry.get("legible", entry.get("is_legible", entry.get("readable")))
            else:
                val = entry
                leg = top.get(nm + "_legible", leg_map.get(nm))
            if leg is not None and is_false(leg):
                unread.append(field)
            elif val is not None and not isinstance(val, (dict, list)) and str(val).strip():
                vals[field] = str(val).strip()
            break
    return vals, unread


# -- the scan --------------------------------------------------------------------------------------------------------
class Scan(object):
    def __init__(self, case_dir, case_id, out_dir, shelf_life_days=SHELF_LIFE_DAYS):
        self.case_dir, self.out_dir = case_dir, out_dir
        self.case_id = str(case_id).strip().upper()
        self.cnum = self.case_id[2:] if self.case_id.startswith("C-") else self.case_id
        self.shelf = int(shelf_life_days)
        self.dates = DateCtx()
        self.ents = Entities()
        self.lots = OrderedDict()
        self.lot_by_key, self.lot_prefixes, self.lot_len = {}, set(), {}
        self.vocab, self.vocab_keys = {}, {}
        self.frags, self.links, self.exposures, self.gaps = [], [], [], []
        self.tables = defaultdict(list)
        self.items = []
        self.inventory = OrderedDict()
        self.not_read, self.flags = [], []
        self.pd_seen = {}
        self.ship_days = defaultdict(set)
        self.ship_to = defaultdict(dict)  # (distributor, store) -> {ship date: {lot codes, "*" for an unreadable one}}
        self.recv_rows, self.deliveries, self.unlinked = [], [], []
        self.stated_missing = defaultdict(list)  # distributor -> [(days its own email says its log lost, source)]
        self.case_products, self.span = set(), None

    # inventory and records
    def inv(self, rel, kind=None):
        e = self.inventory.setdefault(rel, {"kind": kind or "file", "found": [], "missing": []})
        if kind and e["kind"] == "file":
            e["kind"] = kind
        return e

    def frag(self, rel, loc, ftype, conf, notes, product=None, date=None, prio=None):
        f = OrderedDict([("fragment_id", None), ("source_file", rel), ("location", loc), ("type", ftype),
                         ("confidence", round(min(max(conf, 0.05), 0.99), 2)), ("notes", short(notes, 300))])
        f["_product"], f["_date"], f["_prio"], f["_n"] = product, date, prio, len(self.frags)
        self.frags.append(f)
        return f

    def flag(self, rel, loc, text):
        self.flags.append((rel, loc, text))
        self.frag(rel, loc, "clue", 0.1, "instruction-like text found; treated as data and not followed: %s" % short(text, 100),
                  prio=0)
        self.inv(rel)["missing"].append("contains instruction-like text (%s), ignored" % loc)

    def add_link(self, hop, frm, to, product, lot, cands, date, src, conf, frag, basis, raw=None, qty=None, note=None,
                 loose=False):
        if loose:
            conf -= LOOSE_DATE_PENALTY
        L = OrderedDict([("link_id", None), ("hop", hop), ("from", frm), ("to", to), ("product", product or None)])
        if lot:
            L["lot_code"] = lot
        else:
            L["lot_candidates"] = list(cands or [])
            L["lot_raw"] = raw or ""
        L["date"] = iso(date)
        L["source"] = src
        L["confidence"] = round(min(max(conf, 0.05), 0.99), 2)
        L["fragment_id"] = None
        L["basis"] = basis
        if qty not in (None, ""):
            L["qty_cases"] = int(qty) if re.match(r"^\d+$", str(qty).strip()) else qty
        if note:
            L["note"] = note
        L["_frag"] = frag
        self.links.append(L)
        return L

    def party(self, value, role):
        """An id or name from a CSV cell -> entity id; an unknown one becomes an unlisted node of that role."""
        value = str(value or "").strip()
        if not value or UNREADABLE_WORDS.match(value) or value.lower() in ("unknown", "not known", "n.a.", "tbd"):
            return None
        eid = self.ents.resolve(value)
        if eid:
            return eid
        return self.ents.add(value, role, value, unlisted=True)

    def cell_date(self, s):
        hits = find_dates(s, self.dates)
        return (hits[0][1], hits[0][2]) if hits else (None, False)

    # 1. files
    def collect(self):
        seen = {}
        for path in walk(self.case_dir):
            rel = os.path.relpath(path, self.case_dir).replace(os.sep, "/")
            low = rel.lower()
            if SECRET_FILE.search(low):
                self.not_read.append((rel, "key or credential file, never opened"))
                continue
            ext = os.path.splitext(low)[1]
            is_tx = low.endswith(".transcription.json")
            if not (is_tx or ext in CSV_EXT + MAIL_EXT + TEXT_EXT):
                self.not_read.append((rel, "file type not read"))
                continue
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    self.not_read.append((rel, "larger than 20 MB, not read"))
                    continue
                with open(path, "rb") as fh:
                    raw = fh.read()
            except OSError as e:
                self.not_read.append((rel, "could not be read (%s)" % e.__class__.__name__))
                continue
            # identical copies are read once; a note's store can come from its file name, so for notes and other text
            # the same words under another name are another record
            h = hashlib.sha256(raw).hexdigest() + ("" if ext in CSV_EXT + MAIL_EXT else "|" + os.path.basename(low))
            if h in seen:
                self.not_read.append((rel, "identical copy of %s, read once" % seen[h]))
                continue
            seen[h] = rel
            if is_tx:
                self.items.append((rel, "transcription", raw))
            elif ext in CSV_EXT:
                self.read_csv(rel, raw)
            elif ext in MAIL_EXT:
                self.items.append((rel, "email", raw))
            else:
                text = decode(raw)
                kind = "email" if looks_like_email(text) else ("note" if looks_like_note(rel, text) else "text")
                self.items.append((rel, kind, raw if kind == "email" else text))

    def read_csv(self, rel, raw):
        text = decode(raw)
        delim = "\t" if rel.lower().endswith(".tsv") or text[:2000].count("\t") > text[:2000].count(",") else ","
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        except csv.Error as e:
            self.inv(rel, "CSV")["missing"].append("could not be parsed (%s)" % e)
            return
        hi = next((i for i, r in enumerate(rows) if any(c.strip() for c in r)), None)
        if hi is None:
            self.inv(rel, "CSV")["missing"].append("empty")
            return
        cols = [norm_col(c) for c in rows[hi]]
        kind = csv_kind(cols, rel)
        if not kind:
            self.inv(rel, "CSV")["missing"].append("columns not recognised (%s); not used" % ", ".join(c for c in cols[:8] if c))
            return
        if kind == "distributor_shipments" and "ship_date" not in cols and "date" in cols:
            cols[cols.index("date")] = "ship_date"
        recs = []
        for i in range(hi + 1, len(rows)):
            r = rows[i]
            if not any(c.strip() for c in r):
                continue
            d = {}
            for j, c in enumerate(cols):
                if c and c not in d:
                    d[c] = r[j].strip() if j < len(r) else ""
            recs.append((i + 1, d))
        self.tables[kind].append((rel, recs))
        self.inv(rel, KIND_WORDS[kind])

    # 2. entities, dates, lots
    def load_entities(self):
        for rel, rows in self.tables.get("entities", []):
            n = defaultdict(int)
            for rn, r in rows:
                eid = (r.get("entity_id") or "").strip()
                if eid:
                    t = norm_type(r.get("type"))
                    self.ents.add(eid, t, (r.get("name") or "").strip() or eid, (r.get("location") or "").strip())
                    n[t] += 1
            self.inv(rel)["found"].append("%d entities (%s)" % (sum(n.values()), ", ".join(
                "%d %s" % (v, k + ("s" if v != 1 else "")) for k, v in sorted(n.items()))))
        for kind, cols in (("packer_lots", (("packer_id", "packer"),)),
                           ("distributor_shipments", (("packer_id", "packer"), ("distributor_id", "distributor"),
                                                      ("store_id", "store"))),
                           ("store_receiving", (("distributor_id", "distributor"), ("store_id", "store"))),
                           ("illness_cases", (("store_id", "store"),))):
            for rel, rows in self.tables.get(kind, []):
                for rn, r in rows:
                    for col, role in cols:
                        self.party(r.get(col), role)
                    if kind == "packer_lots":
                        for f in split_farms(r.get("farm_ids")):
                            self.party(f, "farm")

    def init_dates(self):
        full = []
        for kind, rows_list in self.tables.items():
            for rel, rows in rows_list:
                for rn, r in rows:
                    for col in ("date", "ship_date", "pack_date", "onset_date", "purchase_date"):
                        for _, d, loose in find_dates(r.get(col, ""), self.dates):
                            if not loose:
                                full.append(d)
        self.dates.setup(full)

    def load_lots(self):
        for rel, rows in self.tables.get("packer_lots", []):
            e = self.inv(rel)
            nfarm, comm, nofarm = 0, [], []
            for rn, r in rows:
                code = re.sub(r"\s+", "", (r.get("lot_code") or "").strip().upper())
                if not code:
                    e["missing"].append("row %d has no lot code" % rn)
                    continue
                if code in self.lots:
                    e["missing"].append("row %d repeats lot %s; the first row is used" % (rn, code))
                    continue
                packer = self.party(r.get("packer_id"), "packer")
                pdate, loose = self.cell_date(r.get("pack_date"))
                product = (r.get("product") or "").strip()
                farms = [self.party(f, "farm") for f in split_farms(r.get("farm_ids"))]
                src = "%s#row%d" % (rel, rn)
                fr = self.frag(rel, "row%d" % rn, "record", CONF_CSV, "packer lot %s: %s packed by %s on %s, farms %s" % (
                    code, product or "product not given", packer or "packer not given", iso(pdate) or "date not given",
                    ", ".join(farms) or "not given"), product, pdate)
                self.lots[code] = {"lot_code": code, "packer_id": packer, "pack_date": iso(pdate), "_pack": pdate,
                                   "product": product, "farm_ids": list(farms), "farm_basis": {f: "record" for f in farms},
                                   "in_packer_records": True, "source": src, "_frag": fr, "confidence": CONF_CSV}
                for f in farms:
                    self.add_link("farm-packer", f, packer, product, code, None, pdate, src, CONF_CSV, fr, "record",
                                  note="commingled lot (%s)" % ";".join(farms) if len(farms) > 1 else None, loose=loose)
                nfarm += len(farms)
                if len(farms) > 1:
                    comm.append("%s: %s" % (code, ", ".join(farms)))
                if not farms:
                    nofarm.append(code)
            e["found"].append("%d lots -> %d farm-to-packer links" % (len(rows), nfarm))
            if comm:
                e["found"].append("commingled lots: %s" % "; ".join(comm))
            if nofarm:
                e["missing"].append("lots with no farm: %s" % ", ".join(nofarm))
        self.index_lots()

    def index_lots(self):
        self.lot_by_key, self.lot_prefixes, self.lot_len = {}, set(), defaultdict(int)
        for code, lot in self.lots.items():
            k = lot_key(code)
            self.lot_by_key.setdefault(k, code)
            m = re.match(r"^([A-Z]+)", k)
            if m:
                self.lot_prefixes.add(m.group(1))
                self.lot_len[m.group(1)] = max(self.lot_len[m.group(1)], len(k))
            p = lot.get("product")
            if p:
                self.vocab.setdefault(norm_text(p), p)

    def unknown_lot(self, code, packer, product, src):
        lot = self.lots.get(code)
        if lot is None:
            lot = {"lot_code": code, "packer_id": packer, "pack_date": None, "_pack": None, "product": product or "",
                   "farm_ids": [], "farm_basis": {}, "in_packer_records": False, "source": src, "_frag": None,
                   "confidence": None}
            self.lots[code] = lot
            self.index_lots()
        elif packer and not lot.get("packer_id"):
            lot["packer_id"] = packer
        return lot

    def window_lots(self, codes, product, date):
        pool = codes if codes is not None else list(self.lots)
        out = []
        for c in pool:
            lot = self.lots.get(c)
            if not lot or not lot.get("in_packer_records"):
                continue
            if product and lot.get("product") and not prod_match(product, lot["product"]):
                continue
            pd = lot.get("_pack")
            if date and pd and not (date - days(self.shelf) <= pd <= date + days(DATE_TOLERANCE_DAYS)):
                continue
            out.append(c)
        return sorted(out)

    def expand(self, raw, product, date, smudged=False):
        """A lot code as written -> (code, candidates, state); state is full, partial, blank or unknown.
        A partial or blank code expands to the lots in packer_lots for that product packed in the shelf-life window."""
        raw = str(raw or "").strip()
        key = lot_key(raw)
        if not raw or UNREADABLE_WORDS.match(raw) or not re.search(r"[A-Z0-9]", key) or \
                not (re.search(r"\d", key) or "?" in key):
            return None, self.window_lots(None, product, date), "blank"
        if "?" not in key:
            code = self.lot_by_key.get(key)
            if code:
                return code, [], "full"
            m = re.match(r"^([A-Z]+)", key)
            typical = self.lot_len.get(m.group(1), 0) if m else 0
            comp = [c for k, c in self.lot_by_key.items() if k.startswith(key) and 0 < len(k) - len(key) <= 2]
            if comp and (smudged or len(key) < typical):
                return None, self.window_lots(comp, product, date), "partial"
            return raw.upper(), [], "unknown"
        rx = re.compile("^" + "".join("[A-Z0-9]" if ch == "?" else re.escape(ch) for ch in key) + "$")
        return None, self.window_lots([c for k, c in self.lot_by_key.items() if rx.match(k)], product, date), "partial"

    def find_lots(self, t):
        """Lot codes written in t: [(position, code as written, looks smudged)]. Known codes match exactly first, so a
        code of any shape ("L-2026-1006-A") is found whole."""
        out, taken = [], []
        for code in sorted(self.lots, key=len, reverse=True):
            for m in re.finditer(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9?*#])" % re.escape(code), t, re.I):
                if not any(a < m.end() and m.start() < b for a, b in taken):
                    out.append((m.start(), m.group(0), False))
                    taken.append((m.start(), m.end()))
        for m in RX_LOT_WORD.finditer(t):
            if any(a <= m.start(1) < b for a, b in taken):
                continue
            tok = m.group(1).rstrip(".,;:)-")
            if tok.lower() in NOT_A_CODE or self.ents.keys.get(id_key(tok)):
                continue
            out.append((m.start(1), tok, "?" in tok or "*" in tok))
            taken.append((m.start(1), m.start(1) + len(tok)))
        for m in RX_LOT_TOKEN.finditer(t):
            if any(a <= m.start() < b for a, b in taken) or m.group(1).upper() not in self.lot_prefixes:
                continue
            tok = m.group(0)
            if self.ents.keys.get(id_key(tok)) or self.ents.keys.get(id_key2(tok)):
                continue
            out.append((m.start(), tok, "?" in tok or "*" in tok))
        out.sort()
        return out

    def find_product(self, t):
        nt = " %s " % norm_text(t)
        for p in sorted(self.vocab, key=lambda x: (-len(x), x)):
            if p and " %s " % p in nt:
                return self.vocab[p]
        for tok in nt.split():
            tok = tok[:-1] if len(tok) > 4 and tok.endswith("s") else tok
            if len(tok) >= 4 and self.vocab_keys.get(tok):
                return self.vocab_keys[tok]
        return None

    def build_vocab(self):
        for kind, cols in (("packer_lots", "product"), ("distributor_shipments", "product"),
                           ("store_receiving", "product"), ("illness_cases", "product")):
            for rel, rows in self.tables.get(kind, []):
                for rn, r in rows:
                    p = (r.get(cols) or "").strip()
                    if p:
                        self.vocab.setdefault(norm_text(p), p)
        owners = defaultdict(set)
        for p, orig in self.vocab.items():
            for t in prod_key(orig):
                owners[t].add(orig)
        self.vocab_keys = {t: next(iter(v)) for t, v in owners.items() if len(v) == 1 and t not in PROD_STOP}

    # 3. logs
    def lot_state_conf(self, state, ncand, full, partial, blank):
        conf = {"full": full, "unknown": full, "partial": partial, "blank": blank}[state]
        if state in ("partial", "blank") and ncand == 1:
            conf += ONE_CANDIDATE_BONUS
        return conf

    def load_shipments(self):
        for rel, rows in self.tables.get("distributor_shipments", []):
            e = self.inv(rel)
            npd = nds = 0
            odd = []
            for rn, r in rows:
                src = "%s#row%d" % (rel, rn)
                d = self.party(r.get("distributor_id"), "distributor")
                p = self.party(r.get("packer_id"), "packer")
                s = self.party(r.get("store_id"), "store")
                dt, loose = self.cell_date(r.get("ship_date") or r.get("date"))
                prod = (r.get("product") or "").strip()
                raw = (r.get("lot_code") or "").strip()
                code, cands, state = self.expand(raw, prod, dt)
                if state == "unknown":
                    self.unknown_lot(code, p, prod, src)
                conf = self.lot_state_conf(state, len(cands), CONF_CSV, CONF_CSV_PARTIAL, CONF_CSV_BLANK)
                basis = "record" if state in ("full", "unknown") else "partial"
                fr = self.frag(rel, "row%d" % rn, "record", conf, "shipment: %s shipped %s%s from packer %s to store %s on %s" % (
                    d or "?", prod or "product", (" lot " + raw) if raw else " (no lot code)", p or "?", s or "?",
                    iso(dt) or "no date"), prod, dt)
                if d and dt:
                    self.ship_days[d].add(dt)
                    if s:
                        self.ship_to[(d, s)].setdefault(dt, set()).add(code or "*")
                if state in ("partial", "blank"):
                    odd.append("row %d: lot code %s" % (rn, ("'%s' partly unreadable" % raw) if raw else "blank"))
                if not dt:
                    odd.append("row %d: no readable ship date" % rn)
                if p and d:
                    k = (p, d, code or tuple(cands) or raw)
                    if k not in self.pd_seen:
                        self.pd_seen[k] = self.add_link("packer-distributor", p, d, prod, code, cands, dt, src, conf, fr,
                                                        basis, raw=raw, qty=r.get("qty_cases"), loose=loose)
                        npd += 1
                if d and s:
                    self.add_link("distributor-store", d, s, prod, code, cands, dt, src, conf, fr, basis, raw=raw,
                                  qty=r.get("qty_cases"), loose=loose)
                    self.deliveries.append({"d": d, "s": s, "date": dt, "product": prod, "src": src, "kind": "shipment",
                                            "lot": code})
                    nds += 1
            e["found"].append("%d rows -> %d distributor-to-store and %d packer-to-distributor links" % (len(rows), nds, npd))
            e["missing"].extend(odd[:20] + (["%d more rows like these" % (len(odd) - 20)] if len(odd) > 20 else []))

    def load_receiving(self):
        for rel, rows in self.tables.get("store_receiving", []):
            e = self.inv(rel)
            n = 0
            odd = []
            for rn, r in rows:
                src = "%s#row%d" % (rel, rn)
                s = self.party(r.get("store_id"), "store")
                d = self.party(r.get("distributor_id"), "distributor")
                dt, loose = self.cell_date(r.get("date") or r.get("ship_date"))
                prod = (r.get("product") or "").strip()
                raw = (r.get("lot_code") or "").strip()
                code, cands, state = self.expand(raw, prod, dt)
                if state == "unknown":
                    self.unknown_lot(code, None, prod, src)
                conf = self.lot_state_conf(state, len(cands), CONF_CSV, CONF_CSV_PARTIAL, CONF_CSV_BLANK)
                basis = "record" if state in ("full", "unknown") else "partial"
                fr = self.frag(rel, "row%d" % rn, "record", conf, "receiving: store %s got %s%s from %s on %s%s" % (
                    s or "?", prod or "product", (" lot " + raw) if raw else " (no lot code)", d or "?", iso(dt) or "no date",
                    (" (lot code expands to %s)" % (", ".join(cands) or "no known lot")) if state in ("partial", "blank") else ""),
                    prod, dt)
                if s and dt:
                    self.recv_rows.append({"s": s, "d": d, "date": dt, "product": prod, "lot": code})
                if state in ("partial", "blank"):
                    odd.append("row %d: lot code %s" % (rn, ("'%s' partly unreadable" % raw) if raw else "blank"))
                if s and d:
                    self.add_link("distributor-store", d, s, prod, code, cands, dt, src, conf, fr, basis, raw=raw,
                                  qty=r.get("qty_cases"), loose=loose)
                    self.deliveries.append({"d": d, "s": s, "date": dt, "product": prod, "src": src, "kind": "receiving",
                                            "lot": code})
                    n += 1
                elif s or d:
                    odd.append("row %d: no %s" % (rn, "distributor" if s else "store"))
            e["found"].append("%d rows -> %d distributor-to-store links" % (len(rows), n))
            e["missing"].extend(odd[:20] + (["%d more rows like these" % (len(odd) - 20)] if len(odd) > 20 else []))

    # 4. emails and other text: statements in words
    def sender_of(self, hdr, body):
        name, addr = email.utils.parseaddr(hdr.get("from", ""))
        for t in (name,):
            hits = [h[2] for h in self.ents.find(t)]
            if len(set(hits)) == 1:
                return hits[0]
        label = addr.split("@")[-1].split(".")[0].lower() if "@" in addr else ""
        if len(label) >= 5:
            for eid, v in self.ents.by_id.items():
                for a in aliases(v["name"]):
                    flat = a.replace(" ", "")
                    if len(flat) >= 6 and (label == flat or label.startswith(flat) or flat.startswith(label)):
                        return eid
        # a signature line that is little more than a company name ("Valley Fresh Distributors")
        for l in reversed([l.strip() for l in body.splitlines() if l.strip()][-4:]):
            hits = self.ents.find(l)
            if len({h[2] for h in hits}) == 1 and sum(h[1] - h[0] for h in hits) >= 0.6 * len(l.strip(" ,.-")):
                return hits[0][2]
        return None

    def read_email(self, rel, raw):
        text = decode(raw)
        if rel.lower().endswith(".emlx") and re.match(r"^\s*\d+\s*\n", text):
            text = text.split("\n", 1)[1]
        e = self.inv(rel, "email")
        try:
            msg = email.message_from_string(text, policy=email.policy.default)
        except Exception:  # unreadable headers: read the text as it is
            msg = None
        hdr, body = {}, text
        if msg is not None:
            for h in ("from", "to", "subject", "date"):
                try:
                    hdr[h] = str(msg.get(h) or "")
                except Exception:
                    hdr[h] = ""
            body = body_text(msg) or ""
            try:
                for part in msg.iter_attachments():
                    e["missing"].append("attachment not read: %s" % (part.get_filename() or part.get_content_type()))
            except Exception:
                pass
        lines = text.splitlines()
        start = next((i for i, l in enumerate(lines) if not l.strip()), -1) + 1
        numbered, j = [], start
        for bl in body.splitlines():
            k = j
            while k < len(lines) and lines[k].strip() != bl.strip():
                k += 1
            if k < len(lines):
                numbered.append((k + 1, bl))
                j = k + 1
            else:
                numbered.append((min(j + 1, max(len(lines), 1)), bl))
        sender = self.sender_of(hdr, body)
        n = self.statements(rel, numbered, sender, CONF_EMAIL, "email")
        if n is None:
            e["found"].append("statements not used (instruction-like text)")
            return
        if sender:
            e["found"].append("from %s (%s)" % (sender, self.ents.name_of(sender)))
        e["found"].append("%d link(s) from statements in the text" % n if n else "no lot, farm or shipment statement found")

    def read_text(self, rel, text):
        e = self.inv(rel, "text")
        n = self.statements(rel, list(enumerate(text.splitlines(), 1)), None, CONF_TEXT, "text")
        e["found"].append("statements not used (instruction-like text)" if n is None else
                          "%d link(s) from statements in the text" % n if n else "no lot, farm or shipment statement found")

    def quarantine_lines(self, rel, numbered):
        """A file that holds instruction-like text gives no links: its other lines that name a lot or a party are kept
        as low-confidence clues for a person to review."""
        n = 0
        for ln, t in numbered:
            if t.strip() and not _INJECT.search(t) and (self.find_lots(t) or self.ents.find(t)):
                self.frag(rel, "line%d" % ln, "clue", 0.1, "not used: this file also holds instruction-like text: %s" %
                          short(t, 160), prio=0)
                n += 1
        self.inv(rel)["missing"].append("holds instruction-like text, so none of its statements were used as links "
                                        "(%d line(s) kept as clues for review)" % n)

    def statements(self, rel, numbered, sender, base, kind):
        hostile = False
        for ln, t in numbered:
            if _INJECT.search(t):
                hostile = True
                self.flag(rel, "line%d" % ln, t)
        if hostile:
            self.quarantine_lines(rel, numbered)
            return None
        made, intro = 0, ""
        for para in paragraphs([(ln, t) for ln, t in numbered if not t.lstrip().startswith(">")]):
            item = bool(re.match(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+", para[0][1]))
            if not item:
                intro = " ".join(t for _, t in para)
            # a list under "our drops ... (dates are the days the trucks went out):" lists shipments by the sender
            ship_ctx = item and bool(sender and self.ents.type_of(sender) in ("packer", "distributor") and
                                     RX_SHIP_CTX.search(intro))
            sents = sentences(para)
            pdates = []
            for _, s in sents:
                pdates += find_dates(s, self.dates)
            for ln, s in sents:
                if _INJECT.search(s):
                    continue
                self.stated_gap(rel, ln, s, sender)
                made += self.statement(rel, ln, s, sender, pdates, base, kind, ship_ctx)
        return made

    def stated_gap(self, rel, ln, s, sender):
        """A distributor saying its log lost days ("lost the route records for 10/6 through 10/11")."""
        if not sender or self.ents.type_of(sender) != "distributor" or not (RX_LOG_LOST.search(s) and RX_LOG_WORD.search(s)):
            return
        ds = find_dates(s, self.dates)
        if len(ds) >= 2 and re.search(r"(?i)\b(through|thru|to|until|till)\b|-", s[ds[0][0]:ds[1][0]]):
            lo, hi = ds[0][1], ds[1][1]
            span = [lo + days(i) for i in range((hi - lo).days + 1)] if 0 <= (hi - lo).days <= 31 else [lo, hi]
        else:
            span = [d for _, d, _ in ds]
        if span:
            self.stated_missing[sender].append((span, "%s#line%d" % (rel, ln)))

    def statement(self, rel, ln, s, sender, pdates, base, kind, ship_ctx=False):
        ents = self.ents.find(s)
        lots = self.find_lots(s)
        if not ents or not (lots or RX_SHIP.search(s) or RX_RECV.search(s) or ship_ctx):
            return 0
        prod = self.find_product(s)
        dts = find_dates(s, self.dates)
        date, loose = (dts[0][1], dts[0][2]) if dts else ((pdates[0][1], pdates[0][2]) if pdates else (None, False))
        src = "%s#line%d" % (rel, ln)
        holder = {}

        def fr(conf):
            if "f" not in holder:
                holder["f"] = self.frag(rel, "line%d" % ln, "clue", conf, "%s statement: %s" % (kind, short(s, 220)),
                                        prod, date)
            return holder["f"]

        def role(a):
            m = RX_ROLE.search(s[max(0, a - 40):a])
            return m.group(1).lower() if m else None

        def negated(a):
            return bool(RX_NEG_BEFORE.search(s[max(0, a - 40):a]))

        mentions = [(a, b, eid, role(a)) for a, b, eid in ents if not negated(a)]
        made = 0
        # (1) which farm a lot came from
        farms = [m for m in mentions if self.ents.type_of(m[2]) == "farm"]
        # "RL-0718 (whole romaine 24ct, packed 10/6): Quillfeather Farm" needs no verb; a shipment sentence does
        if farms and lots and (RX_FARM_VERB.search(s) or any(m[3] in ("from", "by", "at") for m in farms) or
                               not (RX_SHIP.search(s) or RX_RECV.search(s) or ship_ctx)):
            packers = [m[2] for m in mentions if self.ents.type_of(m[2]) == "packer"]
            for pos, raw, smudged in lots:
                code, cands, state = self.expand(raw, prod, None, smudged)
                if state not in ("full", "unknown"):
                    continue
                lot = self.lots.get(code) or self.unknown_lot(
                    code, packers[0] if packers else (sender if self.ents.type_of(sender) == "packer" else None), prod, src)
                packer = lot.get("packer_id") or (packers[0] if packers else None) or \
                    (sender if self.ents.type_of(sender) == "packer" else None)
                if not packer:
                    continue
                for f in dict.fromkeys(m[2] for m in farms):
                    if lot["farm_basis"].get(f):
                        continue  # packer_lots already says so
                    self.add_link("farm-packer", f, packer, lot.get("product") or prod, code, None,
                                  lot.get("_pack") or date, src, base, fr(base), "stated",
                                  note="%s says lot %s came from %s" % (kind, code, f))
                    lot["farm_ids"].append(f)
                    lot["farm_basis"][f] = "stated"
                    made += 1
        # (2) a shipment, as "we shipped ... to X", "X received ... from Y", or a list item under a shipping intro
        verb = RX_SHIP.search(s) or RX_RECV.search(s)
        if verb and RX_NEG_VERB.search(s[max(0, verb.start() - 30):verb.start()]):
            return made
        if not verb and not ship_ctx:
            return made
        vpos = verb.start() if verb else 0
        recv = bool(verb) and bool(RX_RECV.search(s)) and not RX_SHIP.search(s[:RX_RECV.search(s).start()])
        others = [m for m in mentions if self.ents.type_of(m[2]) in ("packer", "distributor", "store")]
        tos = [m[2] for m in others if m[3] in ("to", "into", "for")]
        frs = [m[2] for m in others if m[3] in ("from", "by", "via")]
        if sender and re.search(r"(?i)\bto\s+(?:us|our\s+(?:store|warehouse|dc|facility|location|shop))\b", s):
            tos.append(sender)
        plain = [m for m in others if m[3] not in ("to", "into", "for", "from", "by", "via") and m[2] not in tos + frs]
        if recv:
            if not tos:
                before = [m[2] for m in plain if m[0] < vpos]
                tos = before[:1] or ([sender] if sender else [])
            if not frs:
                frs = [m[2] for m in plain if m[2] not in tos][:1]
        else:
            if not frs:
                before = [m[2] for m in plain if m[0] < vpos]
                frs = before[:1] or ([sender] if sender else [])
            if not tos:
                tos = [m[2] for m in plain if (m[0] > vpos or not verb) and m[2] not in frs]
        full = [(raw, smudged) for _, raw, smudged in lots]
        for f in dict.fromkeys(frs):
            for t in dict.fromkeys(tos):
                hop = "%s-%s" % (self.ents.type_of(f), self.ents.type_of(t))
                if f == t or hop not in ("packer-distributor", "distributor-store"):
                    continue
                specs = []
                for raw, smudged in full:
                    code, cands, state = self.expand(raw, prod, date, smudged)
                    if state == "unknown":
                        self.unknown_lot(code, f if hop == "packer-distributor" else None, prod, src)
                    specs.append((code, cands, state, raw))
                if not specs:
                    cands = self.window_lots(None, prod, date)
                    if hop == "packer-distributor":
                        cands = [c for c in cands if self.lots[c].get("packer_id") == f]
                    specs.append((None, cands, "blank", ""))
                for code, cands, state, raw in specs:
                    conf = base if state in ("full", "unknown") else (CONF_EMAIL_NO_LOT if state == "blank" else base - 0.15)
                    conf = min(conf, base)
                    basis = "stated" if state in ("full", "unknown") else "partial"
                    product = prod or (self.lots[code].get("product") if code in self.lots else None)
                    self.add_link(hop, f, t, product, code, cands, date, src, conf, fr(conf), basis, raw=raw,
                                  note="stated in %s" % ("an email" if kind == "email" else "a text file"), loose=loose)
                    if hop == "distributor-store":
                        self.deliveries.append({"d": f, "s": t, "date": date, "product": product, "src": src, "kind": kind,
                                                "lot": code})
                    made += 1
        return made

    # 5. delivery notes and transcriptions
    def file_store(self, rel, lines):
        name = rel.replace("_", " ").replace(".", " ")
        for text in (rel, name):
            st = {h[2] for h in self.ents.find(text) if self.ents.type_of(h[2]) == "store"}
            if len(st) == 1:
                return st.pop()
        head = [l for l in lines if l.strip()][:3]
        for chunk in (head, lines):
            st = set()
            for l in chunk:
                st |= {h[2] for h in self.ents.find(l) if self.ents.type_of(h[2]) == "store"}
            if len(st) == 1:
                return st.pop()
        return None

    def only_distributor(self, store, product):
        ds = {L["from"] for L in self.links if L["hop"] == "distributor-store" and L["to"] == store and L["basis"] == "record"
              and prod_match(product, L.get("product"))}
        return ds.pop() if len(ds) == 1 else None

    def note_link(self, rel, loc, store, dist, prod, raw, smudged, dt, loose, qty, confs, ftype_word):
        """One receiving line from a note or a transcription -> a distributor-to-store link (or a reason it is not one)."""
        guessed = False
        if not dist and store:
            dist = self.only_distributor(store, prod)
            guessed = dist is not None
        if not store or not dist:
            return None, "%s not named" % ("store" if not store else "distributor")
        if not dt and not raw:
            return None, "no readable date or lot code"
        code, cands, state = self.expand(raw, prod, dt, smudged)
        if state == "full" and smudged:
            state_conf = (confs[0] + confs[1]) / 2.0
        else:
            state_conf = self.lot_state_conf(state, len(cands), confs[0], confs[1], confs[2])
        conf = state_conf - (GUESSED_PARTY_PENALTY if guessed else 0)
        basis = "record" if state in ("full", "unknown") and not smudged else "partial"
        src = "%s#%s" % (rel, loc)
        if state == "unknown":
            self.unknown_lot(code, None, prod, src)
        product = prod or (self.lots[code].get("product") if code in self.lots else None)
        fr = self.frag(rel, loc, "record" if basis == "record" else "clue", conf, "%s: %s received %s%s from %s on %s%s%s" % (
            ftype_word, store, product or "product", (" lot " + raw) if raw else " (no lot code)", dist,
            iso(dt) or "no date", " (smudged)" if smudged else "",
            (" (lot code expands to %s)" % (", ".join(cands) or "no known lot")) if state in ("partial", "blank") else ""),
            product, dt)
        L = self.add_link("distributor-store", dist, store, product, code, cands, dt, src, conf, fr, basis, raw=raw,
                          qty=qty, note=("distributor not named; %s is the store's only distributor for it" % dist)
                          if guessed else None, loose=loose)
        self.deliveries.append({"d": dist, "s": store, "date": dt, "product": product, "src": src, "kind": "note",
                                "lot": code})
        return L, None

    def read_note(self, rel, text):
        e = self.inv(rel, "delivery note")
        lines = text.splitlines()
        if any(_INJECT.search(l) for l in lines):
            for ln, t in enumerate(lines, 1):
                if _INJECT.search(t):
                    self.flag(rel, "line%d" % ln, t)
            self.quarantine_lines(rel, list(enumerate(lines, 1)))
            return
        store = self.file_store(rel, lines)
        fd = find_dates(os.path.basename(rel), self.dates) or find_dates("\n".join(lines[:3]), self.dates)
        fdate = fd[0][1] if fd else None
        made, part = 0, 0
        for ln, t in enumerate(lines, 1):
            if not t.strip():
                continue
            if _INJECT.search(t):
                self.flag(rel, "line%d" % ln, t)
                continue
            lots = self.find_lots(t)
            qty = RX_QTY.search(t)
            prod = self.find_product(t)
            ents = self.ents.find(t)
            dists = [h[2] for h in ents if self.ents.type_of(h[2]) == "distributor"]
            stores = [h[2] for h in ents if self.ents.type_of(h[2]) == "store"]
            dts = find_dates(t, self.dates)
            if not ((RX_RECV_LINE.search(t) and (lots or qty or (prod and (dts or dists)))) or (lots and (qty or prod))):
                if dts and RX_NO_DETAIL.search(t) and not RX_NO_DELIVERY.search(t) and (stores or store):
                    # "10/7 invoice missing, driver to bring it next trip": a delivery whose contents are unknown
                    self.unlinked.append({"src": "%s#line%d" % (rel, ln), "text": short(t, 120), "date": dts[0][1],
                                          "store": stores[0] if stores else store, "kind": "no_detail",
                                          "why": "a delivery with no product or lot code recorded"})
                    e["missing"].append("line %d: a delivery with no product or lot code" % ln)
                continue  # a heading or a remark, not a receiving line
            dt, loose = (dts[0][1], dts[0][2]) if dts else (fdate, True)
            raw = lots[0][1] if lots else ""
            smudged = bool(RX_SMUDGE.search(t)) or bool(lots and lots[0][2])
            L, why = self.note_link(rel, "line%d" % ln, stores[0] if stores else store, dists[0] if dists else None, prod,
                                    raw, smudged, dt, loose, int(qty.group(1)) if qty else None,
                                    (CONF_NOTE, CONF_NOTE_PARTIAL, CONF_NOTE_BLANK), "note")
            if L is None:
                e["missing"].append("line %d: %s; not linked" % (ln, why))
                self.unlinked.append({"src": "%s#line%d" % (rel, ln), "why": why, "text": short(t, 120), "store": store,
                                      "date": dt})
                continue
            made += 1
            part += 1 if "lot_candidates" in L else 0
        e["found"].append("%d receiving line(s) -> %d distributor-to-store link(s)%s" % (
            made, made, (", %d with a partial or missing lot code" % part) if part else ""))

    def read_transcription(self, rel, raw):
        e = self.inv(rel, "note transcription (Forensics)")
        try:
            data = json.loads(decode(raw))
        except ValueError:
            e["missing"].append("not valid JSON; not used")
            return
        recs = tx_records(data)
        base = re.sub(r"(?i)\.transcription\.json$", "", rel)
        store0 = self.file_store(base, [])
        fd = find_dates(os.path.basename(base), self.dates)
        made = 0
        parsed = [tx_fields(rec) for rec in recs]
        if any(_INJECT.search(" ".join(v.values())) for v, _ in parsed) or _INJECT.search(decode(raw)):
            self.flag(rel, "whole file", decode(raw))
            self.quarantine_lines(rel, [(i, " ".join(v.values())) for i, (v, _) in enumerate(parsed, 1)])
            return
        for i, (vals, unread) in enumerate(parsed, 1):
            loc = "entry%d" % i
            blob = " ".join(vals.values())
            if unread:
                e["missing"].append("entry %d: %s marked not legible; not used" % (i, ", ".join(unread)))
            store = self.ents.resolve(vals["store"]) if "store" in vals else store0
            if store and self.ents.type_of(store) != "store":
                store = store0
            dist = self.ents.resolve(vals.get("supplier")) if "supplier" in vals else None
            if dist and self.ents.type_of(dist) != "distributor":
                dist = None
            dt, loose = self.cell_date(vals["date"]) if "date" in vals else ((fd[0][1], True) if fd else (None, False))
            prod = vals.get("product")
            if prod:
                prod = self.find_product(prod) or prod
            rawc = vals.get("lot_code", "")
            qty = re.search(r"\d+", vals.get("qty", ""))
            L, why = self.note_link(rel, loc, store, dist, prod, rawc, bool(RX_SMUDGE.search(rawc)), dt, loose,
                                    int(qty.group(0)) if qty else None, (CONF_SCAN, CONF_SCAN_PARTIAL, CONF_SCAN_BLANK),
                                    "transcribed note")
            if L is None:
                e["missing"].append("entry %d: %s; not linked" % (i, why))
                self.unlinked.append({"src": "%s#%s" % (rel, loc), "why": why, "text": short(blob, 120), "store": store,
                                      "date": dt})
                continue
            made += 1
        e["found"].append("%d of %d entries -> distributor-to-store links (low confidence)" % (made, len(recs)))

    # 6. illness cases
    def load_cases(self):
        for rel, rows in self.tables.get("illness_cases", []):
            e = self.inv(rel)
            nostore, nodate = [], []
            for rn, r in rows:
                cid = (r.get("case_id") or "").strip()
                if not cid:
                    continue
                src = "%s#row%d" % (rel, rn)
                notes = r.get("notes") or ""
                flagged = bool(_INJECT.search(notes))
                if flagged:
                    self.flag(rel, "row%d" % rn, notes)
                basis, conf, how, cands = "record", CONF_EXPOSURE, [], []
                store = self.party(r.get("store_id"), "store") if (r.get("store_id") or "").strip() else None
                if not store and notes and not flagged:
                    st = list(OrderedDict.fromkeys(h[2] for h in self.ents.find(notes)
                                                   if self.ents.type_of(h[2]) == "store")) or self.stores_at_places(notes)
                    if len(st) == 1:
                        store, basis, conf = st[0], "notes", CONF_EXPOSURE_NOTES
                        how.append("store read from the case notes")
                    elif 2 <= len(st) <= 5:
                        cands, basis = st, "notes"
                        conf = CONF_EXPOSURE_NOTES - (0.1 if len(st) == 2 else 0.2)
                        how.append("the notes point to %d possible stores: %s" % (len(st), ", ".join(st)))
                pdate, _ = self.cell_date(r.get("purchase_date"))
                if not pdate and notes and not flagged:
                    m = re.search(r"(?i)\b(bought|purchas\w*|shopp\w*|picked up)\b", notes)
                    hits = find_dates(notes[m.start():] if m else notes, self.dates)
                    if hits:
                        pdate, basis, conf = hits[0][1], "notes", min(conf, CONF_EXPOSURE_NOTES)
                        how.append("purchase date read from the case notes")
                onset, _ = self.cell_date(r.get("onset_date"))
                window = None
                relm = RX_REL_DAYS.search(notes) if (not pdate and onset and notes and not flagged) else None
                if relm:  # "thinks it was about 2 days before getting sick"
                    g = relm.group(1).lower()
                    n = int(g) if g.isdigit() else NUM_WORDS.get(g, 2)
                    spread = 2 if g in ("a few", "a couple of") else 1
                    window = [iso(onset - days(n + spread)), iso(onset - days(max(n - spread, 0)))]
                    basis, conf = "notes", min(conf, CONF_EXPOSURE_NOTES)
                    how.append("purchase about %d days before onset, from the case notes" % n)
                elif not pdate and onset:
                    window = [iso(onset - days(INCUBATION_MAX_DAYS)), iso(onset - days(INCUBATION_MIN_DAYS))]
                    basis, conf = "estimated", min(conf, CONF_EXPOSURE_ONSET)
                    how.append("purchase taken as %d to %d days before onset" % (INCUBATION_MIN_DAYS, INCUBATION_MAX_DAYS))
                if notes and not flagged and RX_PROBABLE.search(notes):
                    conf = min(conf, CONF_EXPOSURE_PROBABLE)
                    how.append("probable case, no lab confirmation")
                if notes and not flagged and RX_OTHER_FOOD.search(notes):
                    conf = min(conf, CONF_EXPOSURE_OTHER_FOOD)
                    how.append("the notes name another possible exposure")
                product = (r.get("product") or "").strip() or (self.find_product(notes) if notes and not flagged else None)
                if product:
                    self.case_products.add(product)
                fr = self.frag(rel, "row%d" % rn, "record", conf, "illness case %s: onset %s, store %s, bought %s, %s%s" % (
                    cid, iso(onset) or "not given", store or "not given", iso(pdate) or "not given", product or "product not given",
                    ("; " + "; ".join(how)) if how else ""), product, pdate or onset, prio=0)
                x = OrderedDict([("case_id", cid), ("store_id", store), ("purchase_date", iso(pdate)), ("product", product),
                                 ("source", src), ("onset_date", iso(onset)), ("purchase_window", window),
                                 ("confidence", round(conf, 2)), ("basis", basis), ("fragment_id", None)])
                if cands:
                    x["store_candidates"] = cands
                x["_frag"], x["_pdate"], x["_onset"] = fr, pdate, onset
                x["_how"] = how
                x["_blank"] = [w for w, v in (("store", r.get("store_id")), ("purchase date", r.get("purchase_date")))
                               if not (v or "").strip() or UNREADABLE_WORDS.match((v or "").strip())]
                self.exposures.append(x)
                if not store:
                    nostore.append(cid)
                if not pdate:
                    nodate.append(cid)
            e["found"].append("%d illness cases" % len(rows))
            if nostore:
                e["missing"].append("no store: %s" % ", ".join(nostore))
            if nodate:
                e["missing"].append("no purchase date: %s" % ", ".join(nodate))
        wins = [w for w in (self.exp_window(x) for x in self.exposures) if w]
        if wins:
            self.span = (min(w[0] for w in wins) - days(self.shelf), max(w[1] for w in wins))

    def stores_at_places(self, text):
        """Stores whose location is named in text ("Lives in Upper Varrow and shops at the stores there")."""
        nt = " %s " % norm_text(text)
        out = []
        for eid, v in self.ents.by_id.items():
            places = {norm_text(v.get("location")), norm_text(str(v.get("location") or "").split(",")[0])} - {""}
            if v["type"] == "store" and any(" %s " % p in nt for p in places):
                out.append(eid)
        return out

    def exp_window(self, x):
        if x["_pdate"]:
            return x["_pdate"], x["_pdate"]
        if x["purchase_window"]:
            return (datetime.date(*map(int, x["purchase_window"][0].split("-"))),
                    datetime.date(*map(int, x["purchase_window"][1].split("-"))))
        return None

    def in_span(self, d, pad=3):
        return self.span is None or d is None or self.span[0] - days(pad) <= d <= self.span[1] + days(pad)

    def relevant_product(self, p):
        return not self.case_products or not p or any(prod_match(p, c) for c in self.case_products)

    # 7. gaps
    def gap(self, prio, date, kind, what, why, where, **info):
        g = OrderedDict([("gap_id", None), ("what", what), ("why", why), ("where_to_look", where), ("status", "open")])
        g["_prio"], g["_date"], g["_n"] = prio, date, len(self.gaps)
        info["kind"] = kind
        g["_info"] = info
        self.gaps.append(g)
        return g

    def find_gaps(self):
        nm = self.ents.name_of
        tables = self.tables
        for kind, prio in (("illness_cases", 0), ("packer_lots", 0), ("distributor_shipments", 1), ("store_receiving", 1),
                           ("entities", 6)):
            if not tables.get(kind):
                self.gap(prio, None, "missing_file", "No %s in the case files" % KIND_WORDS[kind],
                         "without it the trace-back cannot %s" % {
                             "illness_cases": "place any case", "packer_lots": "tie lots to farms",
                             "distributor_shipments": "follow lots from packers to stores",
                             "store_receiving": "check what each store received",
                             "entities": "name the farms, packers, distributors and stores"}[kind],
                         ["the client's records folder (%s)" % kind.replace("_", " "), "supplier emails with attachments"])
        # cases with no store or date
        for x in self.exposures:
            miss = [w for w in ("store", "purchase date") if w in x["_blank"] or
                    not x["store_id" if w == "store" else "purchase_date"]]
            if not miss:
                continue
            what = "Illness case %s has no %s on file" % (x["case_id"], " or ".join(miss))
            if "store" in miss and x["store_id"]:
                what += "; the store %s was read from the case notes" % x["store_id"]
            elif "store" in miss and x.get("store_candidates"):
                what += "; the notes point to %s" % " or ".join(x["store_candidates"])
            if x["purchase_window"]:
                from_notes = [h for h in x["_how"] if h.startswith("purchase about")]
                what += "; we use %s to %s (%s, onset %s)" % (
                    x["purchase_window"][0], x["purchase_window"][1], from_notes[0] if from_notes else
                    "%d to %d days before onset" % (INCUBATION_MIN_DAYS, INCUBATION_MAX_DAYS), x["onset_date"])
            elif "purchase date" in miss and x["purchase_date"]:
                what += "; the date %s was read from the case notes" % x["purchase_date"]
            self.gap(0, x["_pdate"] or x["_onset"], "case_no_store" if "store" in miss else "case_no_date", what,
                     "without a %s the case cannot be tied to one delivery" % miss[0],
                     ["the case interview or health department case file for %s" % x["case_id"],
                      "receipts, loyalty-card or payment records of the person in case %s" % x["case_id"],
                      "stores near the person's home that sold %s" % (x["product"] or "the product")],
                     case_ids=[x["case_id"]], store_id=x["store_id"], product=x["product"])
        # stores: no receiving records in an exposure window, or days missing from the store's log
        windows = defaultdict(list)
        for x in self.exposures:
            w = self.exp_window(x)
            if x["store_id"] and w:
                windows[x["store_id"]].append((w[0] - days(self.shelf), w[1], x["case_id"], x["product"]))
        for s, ws in windows.items():
            ws.sort()
            merged = []
            for lo, hi, cid, p in ws:
                if merged and lo <= merged[-1][1] + ONE:
                    m = merged[-1]
                    merged[-1] = (m[0], max(m[1], hi), m[2] + [cid], m[3] | ({p} if p else set()))
                else:
                    merged.append((lo, hi, [cid], {p} if p else set()))
            for lo, hi, cids, prods in merged:
                plist = sorted(prods) or [None]
                rows = [r for r in self.recv_rows if r["s"] == s and lo <= r["date"] <= hi and
                        any(prod_match(r["product"], p) for p in plist)]
                other = [o for o in self.deliveries if o["s"] == s and o["kind"] != "receiving" and o["date"] and
                         lo <= o["date"] <= hi and any(prod_match(o["product"], p) for p in plist)]
                ds = sorted({dl["d"] for dl in self.deliveries if dl["s"] == s and dl["d"]})
                look = ["store %s (%s) receiving log, invoices or delivery slips for %s, %s to %s" % (
                    s, nm(s), "/".join(p for p in plist if p) or "the product", iso(lo), iso(hi))]
                look += ["distributor %s (%s) shipping records to %s, %s to %s" % (d, nm(d), s, iso(lo), iso(hi)) for d in ds]
                look += ["delivery notes or driver receipts at %s" % s]
                if not rows:
                    self.gap(1, lo, "store_no_receiving",
                             "Store %s (%s) has no receiving records for %s from %s to %s, the window before case%s %s" % (
                                 s, nm(s), "/".join(p for p in plist if p) or "the product", iso(lo), iso(hi),
                                 "s" if len(cids) > 1 else "", ", ".join(cids)),
                             "the lots this store sold in that window are unknown%s" % (
                                 "; only %s cover%s it" % (", ".join(sorted({o["src"] for o in other}))[:200],
                                                         "s" if len(other) == 1 else "") if other else ""),
                             look, store_id=s, case_ids=cids, product=plist[0], date_from=iso(lo), date_to=iso(hi),
                             distributor_ids=ds)
                    continue
                logged = defaultdict(set)
                for r in self.recv_rows:
                    if r["s"] == s:
                        logged[r["date"]].add(r["lot"] or "*")
                missing = sorted({o["date"] for o in other if not any(
                    logged.get(x) and (not o.get("lot") or o["lot"] in logged[x] or "*" in logged[x])
                    for x in (o["date"], o["date"] + ONE))})
                if missing:
                    self.gap(2, missing[0], "store_missing_days",
                             "Store %s (%s) receiving log is missing deliveries on %s that other records show" % (
                                 s, nm(s), ", ".join(iso(d) for d in missing)),
                             "deliveries on those days are known only from %s" % ", ".join(
                                 sorted({o["src"] for o in other if o["date"] in missing}))[:200],
                             look, store_id=s, case_ids=cids, product=plist[0], date_from=iso(missing[0]),
                             date_to=iso(missing[-1]), dates=[iso(d) for d in missing], distributor_ids=ds)
        # distributors: shipment days missing from the log. Evidence first (a store received from the distributor, the
        # log has no shipment to that store that day or the two days before); then cadence (it ships on at least 75% of
        # the days any distributor ships, and never skips that weekday otherwise).
        span_ok = self.in_span
        all_days = set()
        for d, ds_ in self.ship_days.items():
            all_days |= ds_
        evid, part = defaultdict(set), defaultdict(set)
        for dl in self.deliveries:
            if dl["kind"] == "shipment" or not dl["d"] or not dl["date"] or not span_ok(dl["date"]):
                continue
            shipped = self.ship_days.get(dl["d"], set())
            t, rows = dl["date"], self.ship_to.get((dl["d"], dl["s"]), {})
            if shipped and not any(rows.get(t - days(k)) and (not dl.get("lot") or dl["lot"] in rows[t - days(k)] or
                                                               "*" in rows[t - days(k)]) for k in (0, 1, 2)):
                evid[dl["d"]].add(t if t not in shipped else (t - ONE if t - ONE not in shipped else t))
                part[dl["d"]].add(t in shipped)
        said = defaultdict(set)
        for d, items in self.stated_missing.items():
            for span, src in items:
                said[d] |= {x for x in span if span_ok(x)}
        for d in sorted(set(evid) | set(self.ship_days) | set(said)):
            mine = self.ship_days.get(d, set())
            cad = set()
            if len(mine) >= 4:  # a silent run much longer than its usual gap, on days other distributors shipped
                sd = sorted(mine)
                steps = [(sd[i + 1] - sd[i]).days for i in range(len(sd) - 1)]
                usual = sorted(steps)[len(steps) // 2]
                for i, g in enumerate(steps):
                    if g >= max(4, 3 * usual):
                        cad |= {x for x in (sd[i] + days(k) for k in range(1, g)) if x in all_days and span_ok(x)}
            missing = sorted(evid.get(d, set()) | cad | said.get(d, set()))
            if not missing:
                continue
            seen_by = "; store records or notes show a delivery from %s on %s that its log does not have" % (
                d, ", ".join(iso(x) for x in sorted(evid[d]))) if evid.get(d) else ""
            if said.get(d):
                seen_by += "; its own email says the log lost %s (%s)" % (
                    ", ".join(iso(x) for x in sorted(said[d])), ", ".join(src for _, src in self.stated_missing[d]))
            self.gap(2, missing[0], "distributor_missing_days",
                     "Distributor %s (%s) shipment log %s %s%s" % (
                         d, nm(d), "is missing deliveries on" if True in part.get(d, ()) else "has no rows for",
                         ", ".join(iso(x) for x in missing),
                         " (its own email says so)" if said.get(d) and not evid.get(d) else
                         "" if evid.get(d) or said.get(d) else " (a silent run much longer than its usual gap)"),
                     "lots shipped on those days cannot be followed from the distributor side%s" % seen_by,
                     ["distributor %s (%s) shipping records (bills of lading, invoices) for %s" % (
                         d, nm(d), ", ".join(iso(x) for x in missing)),
                      "receiving logs of the stores %s serves, same days" % d, "emails from %s" % d],
                     distributor_id=d, date_from=iso(missing[0]), date_to=iso(missing[-1]),
                     dates=[iso(x) for x in missing])
        for d in sorted({dl["d"] for dl in self.deliveries if dl["d"] and dl["kind"] != "shipment"} - set(self.ship_days)):
            if not tables.get("distributor_shipments"):
                break
            dd = sorted({dl["date"] for dl in self.deliveries if dl["d"] == d and dl["date"] and span_ok(dl["date"])})
            if dd:
                self.gap(2, dd[0], "distributor_missing_days",
                         "Distributor %s (%s) has no rows in the shipment log, but stores received from it on %s" % (
                             d, nm(d), ", ".join(iso(x) for x in dd)),
                         "lots it shipped cannot be followed from the distributor side",
                         ["distributor %s (%s) shipping records for %s to %s" % (d, nm(d), iso(dd[0]), iso(dd[-1])),
                          "emails from %s" % d], distributor_id=d, date_from=iso(dd[0]), date_to=iso(dd[-1]),
                         dates=[iso(x) for x in dd])
        # unreadable or partial lot codes
        for L in self.links:
            if L["hop"] == "farm-packer" or "lot_code" in L and L["lot_code"] in self.lots and \
                    self.lots[L["lot_code"]].get("in_packer_records"):
                continue
            dt = datetime.date(*map(int, L["date"].split("-"))) if L["date"] else None
            if not self.relevant_product(L["product"]) or not span_ok(dt):
                continue
            if "lot_code" in L:
                continue  # a full code missing from packer_lots: reported with the lots below
            raw = L.get("lot_raw") or ""
            cands = L["lot_candidates"]
            self.gap(3, dt, "unreadable_code",
                     "%s lot code at %s from %s on %s (%s): %s" % (
                         "Partly unreadable" if raw else "Missing", L["to"], L["from"], L["date"] or "unknown date",
                         L["source"], ("'%s' could be %s" % (raw, ", ".join(cands) if cands else "no lot in the packer records"))
                         if raw else ("could be %s" % (", ".join(cands) if cands else "no lot in the packer records"))),
                     "which lot this %s delivery carried decides which farm it can be traced to" % (L["product"] or "product"),
                     ["%s %s (%s) shipping records for deliveries to %s on %s (full lot code)" % (
                         self.ents.type_of(L["from"]) or "supplier", L["from"], nm(L["from"]), L["to"], L["date"] or "that day"),
                      "%s (%s) receiving invoice or delivery slip for that day" % (L["to"], nm(L["to"])),
                      "a photo of the original note or label"],
                     link_id=L, store_id=L["to"] if L["hop"] == "distributor-store" else None, distributor_id=L["from"],
                     lot_candidates=cands, lot_raw=raw, product=L["product"], date_from=L["date"], date_to=L["date"])
        # lots with no known farm, or no pack record
        for code, lot in self.lots.items():
            if not self.relevant_product(lot.get("product")):
                continue
            pd = lot.get("_pack")
            if pd and not span_ok(pd, pad=self.shelf + 3):
                continue
            p = lot.get("packer_id")
            if not lot.get("in_packer_records"):
                self.gap(4, pd, "lot_no_farm", "Lot %s appears in %s but is not in the packer lot list (no pack date, no farm)" % (
                    code, lot.get("source")), "it cannot be traced to a farm",
                    ["%s %s packing records for lot %s" % ("packer", p, code) if p else "packer records for lot %s" % code,
                     "the packer lot list (packer_lots) for a similar code", "supplier emails about lot %s" % code],
                    lot_code=code, packer_id=p, product=lot.get("product"))
            elif not lot.get("farm_ids"):
                self.gap(4, pd, "lot_no_farm", "Lot %s (packed by %s on %s) has no farm on record" % (
                    code, p or "an unknown packer", lot.get("pack_date") or "an unknown date"),
                    "cases traced to this lot cannot be traced further to a farm",
                    ["packer %s (%s) harvest and sourcing records for lot %s" % (p, nm(p), code) if p else
                     "packer records for lot %s" % code, "supplier emails about lot %s" % code,
                     "farm harvest logs for %s" % (lot.get("pack_date") or "the pack date")],
                    lot_code=code, packer_id=p, product=lot.get("product"))
        for u in self.unlinked:
            if not span_ok(u["date"]) or (u.get("kind") == "no_detail" and u["store"] not in windows):
                continue  # a delivery with no details matters only at a store with a case
            s, d = u["store"], u["date"]
            ds = sorted({dl["d"] for dl in self.deliveries if dl["s"] == s and dl["d"]}) if s else []
            if u.get("kind") == "no_detail":
                what = "Store %s (%s) had a delivery on %s with no product or lot code recorded (%s: \"%s\")" % (
                    s, nm(s), iso(d), u["src"], u["text"])
            else:
                what = "Delivery note %s could not be linked: %s (\"%s\")" % (u["src"], u["why"], u["text"])
            self.gap(5 if u.get("kind") != "no_detail" else 3, d, "unreadable_note", what,
                     "what that delivery carried is unknown, so it may hide a lot that reached the store",
                     ["the original note or a clearer photo"] +
                     ["distributor %s (%s) shipping records to %s on %s" % (x, nm(x), s, iso(d)) for x in ds] +
                     (["store %s (%s) receiving log or invoice for %s" % (s, nm(s), iso(d))] if s else []),
                     store_id=s, date_from=iso(d), date_to=iso(d), distributor_ids=ds)

    # 8. ids and output
    def assign_ids(self):
        def fprio(f):
            if f["_prio"] is not None:
                return f["_prio"]
            return 1 if self.relevant_product(f["_product"]) and self.in_span(f["_date"]) else 2
        order = sorted(self.frags, key=lambda f: (fprio(f), f["_n"]))
        keep, rest = (order, []) if len(order) <= MAX_FRAGMENTS else (order[:MAX_FRAGMENTS - 1], order[MAX_FRAGMENTS - 1:])
        for i, f in enumerate(keep, 1):
            f["fragment_id"] = "F-%s-%03d" % (self.cnum, i)
        frags = [OrderedDict((k, v) for k, v in f.items() if not k.startswith("_")) for f in keep]
        if rest:
            fid = "F-%s-%03d" % (self.cnum, MAX_FRAGMENTS)
            for f in rest:
                f["fragment_id"] = fid
            frags.append(OrderedDict([("fragment_id", fid), ("source_file", "(several files)"),
                                      ("location", "see each link's source"), ("type", "record"),
                                      ("confidence", min(f["confidence"] for f in rest)),
                                      ("notes", "%d more records of lower relevance; each link and exposure that cites this "
                                                "fragment names its own file and row in source" % len(rest))]))
        for i, L in enumerate(self.links, 1):
            L["link_id"] = "L-%s-%03d" % (self.cnum, i)
            L["fragment_id"] = L["_frag"]["fragment_id"] if L["_frag"] else None
        for x in self.exposures:
            x["fragment_id"] = x["_frag"]["fragment_id"]
        gs = sorted(self.gaps, key=lambda g: (g["_prio"], g["_date"] or datetime.date.max, g["_n"]))
        if len(gs) > MAX_GAPS:
            rest = gs[MAX_GAPS - 1:]
            gs = gs[:MAX_GAPS - 1]
            kinds = defaultdict(int)
            for g in rest:
                kinds[g["_info"]["kind"]] += 1
            summ = OrderedDict([("gap_id", None), ("what", "%d more gaps of lower priority (%s)" % (
                len(rest), ", ".join("%d %s" % (v, k.replace("_", " ")) for k, v in sorted(kinds.items())))),
                ("why", "listed together so the gap ids stay within G-%s-01 to 49" % self.cnum),
                ("where_to_look", ["inventory.md", "the same places as the gaps above"]), ("status", "open")])
            summ["_info"] = {"kind": "summary", "items": [g["what"] for g in rest]}
            gs.append(summ)
        for i, g in enumerate(gs, 1):
            g["gap_id"] = "G-%s-%02d" % (self.cnum, i)
        self.gaps = gs
        return frags

    def write(self):
        frags = self.assign_ids()
        nodes = []
        for eid, v in self.ents.by_id.items():
            n = OrderedDict([("id", eid), ("type", v["type"]), ("name", v["name"])])
            if eid in self.ents.unlisted:
                n["listed"] = False
            nodes.append(n)
        lots = []
        for code, lot in self.lots.items():
            lots.append(OrderedDict([("lot_code", code), ("packer_id", lot.get("packer_id")), ("pack_date", lot.get("pack_date")),
                                     ("product", lot.get("product") or None), ("farm_ids", lot.get("farm_ids") or []),
                                     ("farm_basis", lot.get("farm_basis") or {}),
                                     ("in_packer_records", bool(lot.get("in_packer_records"))),
                                     ("source", lot.get("source")),
                                     ("fragment_id", lot["_frag"]["fragment_id"] if lot.get("_frag") else None)]))
        gap_info = []
        for g in self.gaps:
            info = OrderedDict([("gap_id", g["gap_id"])])
            for k, v in g["_info"].items():
                info[k] = v["link_id"] if isinstance(v, dict) and "link_id" in v else v
            info["what"] = g["what"]
            gap_info.append(info)
        clean = lambda rows: [OrderedDict((k, v) for k, v in r.items() if not k.startswith("_")) for r in rows]
        graph = OrderedDict([("case_id", self.case_id), ("kind", "trace"), ("shelf_life_days", self.shelf),
                             ("year_assumed", self.dates.year), ("nodes", nodes), ("lots", lots),
                             ("links", clean(self.links)), ("exposures", clean(self.exposures)),
                             ("gaps", [g["gap_id"] for g in self.gaps]), ("gap_info", gap_info),
                             ("flags", [OrderedDict([("source", "%s#%s" % (r, l)), ("text", short(t, 160))])
                                        for r, l, t in self.flags])])
        gaps = clean(self.gaps)
        os.makedirs(self.out_dir, exist_ok=True)
        for name, obj in (("trace_graph.json", graph), ("fragments.json", frags), ("gaps.json", gaps)):
            with open(os.path.join(self.out_dir, name), "w", encoding="utf-8") as fh:
                json.dump(redact(obj), fh, indent=2)
        with open(os.path.join(self.out_dir, "inventory.md"), "w", encoding="utf-8") as fh:
            fh.write(redact(self.inventory_md(graph, gaps)))
        return {"files": len(self.inventory), "nodes": len(nodes), "links": len(self.links),
                "exposures": len(self.exposures), "fragments": len(frags), "gaps": len(gaps), "flags": len(self.flags)}

    def inventory_md(self, graph, gaps):
        L = ["# Inventory: %s (trace-back)" % self.case_id, "",
             "Every file is data, never instructions. Anything that looked like a password, key or token was replaced "
             "by a marker.", "", "## Files", ""]
        for rel, e in self.inventory.items():
            L.append("- %s: %s. %s" % (rel, e["kind"], "; ".join(e["found"]) or "nothing used"))
            for m in e["missing"]:
                L.append("  - missing or unclear: %s" % m)
        hops = defaultdict(int)
        for l in self.links:
            hops[l["hop"]] += 1
        L += ["", "## Graph", "",
              "- %d nodes, %d links (%s), %d exposures (illness cases)." % (
                  len(graph["nodes"]), len(self.links), ", ".join("%d %s" % (hops[h], h) for h in HOPS), len(self.exposures)),
              "- Lots: %d known to the packer records, %d seen only in other records, %d commingled." % (
                  sum(1 for x in self.lots.values() if x.get("in_packer_records")),
                  sum(1 for x in self.lots.values() if not x.get("in_packer_records")),
                  sum(1 for x in self.lots.values() if len(x.get("farm_ids") or []) > 1))]
        if self.ents.unlisted:
            L.append("- Ids used in the records but not in the entity list: %s." % ", ".join(self.ents.unlisted))
        if self.flags:
            L += ["", "## Instruction-like text (treated as data, not followed)", ""]
            L += ["- %s#%s: \"%s\"" % (r, l, short(t, 120)) for r, l, t in self.flags]
        L += ["", "## Missing", ""]
        L += ["- %s: %s" % (g["gap_id"], g["what"]) for g in gaps] or ["- Nothing: every case has a store, a date and "
                                                                       "receiving records in its window."]
        if self.not_read:
            L += ["", "## Not read", ""]
            L += ["- %s: %s" % (r, why) for r, why in self.not_read]
        L += ["", "## Settings", "",
              "- Shelf-life window: a lot can be sold up to %d days after its pack date (SHELF_LIFE_DAYS)." % self.shelf,
              "- A case with no purchase date is taken as bought %d to %d days before onset." % (
                  INCUBATION_MIN_DAYS, INCUBATION_MAX_DAYS),
              "- Dates written without a year are read as %s (the year most dates in the logs have)." % (
                  self.dates.year or "the current year"),
              "- Confidence: %.2f clean log row, %.2f email, %.2f legible note, %.2f smudged or partial code in a note, "
              "%.2f transcription of a scanned note." % (CONF_CSV, CONF_EMAIL, CONF_NOTE, CONF_NOTE_PARTIAL, CONF_SCAN), ""]
        return "\n".join(L)

    def run(self):
        self.collect()
        self.load_entities()
        self.init_dates()
        self.build_vocab()
        self.load_lots()
        self.load_shipments()
        self.load_receiving()
        for rel, kind, data in self.items:
            if kind == "email":
                self.read_email(rel, data)
            elif kind == "text":
                self.read_text(rel, data)
        for rel, kind, data in self.items:
            if kind == "note":
                self.read_note(rel, data)
            elif kind == "transcription":
                self.read_transcription(rel, data)
        self.load_cases()
        self.find_gaps()
        return self.write()


ONE = days(1)


def split_farms(v):
    return [x.strip() for x in re.split(r"[;|,/]+|\s+and\s+|\s*&\s*", str(v or "")) if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Data Care trace scan: build the trace graph of a food-outbreak case.")
    ap.add_argument("--case-dir", required=True, help="folder with the case files")
    ap.add_argument("--case", required=True, help="Data Care case id, e.g. C-0001")
    ap.add_argument("--out-dir", default="evidence", help="where to write trace_graph.json, fragments.json, gaps.json, inventory.md")
    ap.add_argument("--shelf-life-days", type=int, default=SHELF_LIFE_DAYS,
                    help="window after the pack date in which a lot can be sold (default %d)" % SHELF_LIFE_DAYS)
    a = ap.parse_args(argv)
    if not os.path.isdir(a.case_dir):
        print("case dir not found: %s" % a.case_dir, file=sys.stderr)
        return 2
    s = Scan(a.case_dir, a.case, a.out_dir, a.shelf_life_days)
    r = s.run()
    print("%s: %d files, %d nodes, %d links, %d exposures, %d fragments, %d open gaps%s -> %s" % (
        s.case_id, r["files"], r["nodes"], r["links"], r["exposures"], r["fragments"], r["gaps"],
        (", %d instruction-like passages ignored" % r["flags"]) if r["flags"] else "", a.out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
