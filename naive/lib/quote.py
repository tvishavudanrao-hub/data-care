#!/usr/bin/env python3
"""quote.py: price a case from its workload, write the client approval email, and read the client's reply.

    python3 quote.py quote --kind trace --docs 120 --scanned-pages 40 --requests 6 --case C-0003 --client "Alderbank"
    python3 quote.py reply --file client_reply.txt
    python3 quote.py final --kind trace --quote-usd 2500 --docs 140 --scanned-pages 50 --requests 6 --retries 3 --review-hours 2

Rates, floors and multipliers live in naive/pricing/pricing.json (or --pricing / $DATACARE_PRICING).
Any input left out falls back to that kind's default workload (marked "assumed" in the output).
Standard library only, Python 3.8+. Prints JSON. The cost basis stays internal: the email shows scope and price only.
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = ("docs", "scanned_pages", "requests", "retries", "lookups", "review_hours")


def load_pricing(path=None):
    for p in (path, os.environ.get("DATACARE_PRICING"), os.path.join(HERE, "..", "pricing", "pricing.json"),
              os.path.join(HERE, "pricing.json"), "pricing.json"):
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    raise SystemExit("pricing.json not found: pass --pricing or set DATACARE_PRICING")


def resolve_kind(pricing, kind):
    k = (kind or "").strip().lower()
    k = pricing.get("aliases", {}).get(k, k)
    if k not in pricing["kinds"]:
        raise SystemExit("unknown kind %r; use one of: %s" % (kind, ", ".join(sorted(pricing["kinds"]))))
    return k


def ceil_step(x, step):
    return int(math.ceil(round(x, 6) / step) * step)


def compute(pricing, kind, given, urgency=None):
    kk = resolve_kind(pricing, kind)
    spec = pricing["kinds"][kk]
    r = pricing["rates"]
    vals, assumed = {}, []
    for name in INPUTS:
        if given.get(name) is None:
            vals[name] = spec["defaults"][name]
            assumed.append(name)
        else:
            vals[name] = given[name]
    urg_name = urgency or spec.get("default_urgency", "normal")
    urg = pricing["urgency"][urg_name]
    v = vals["docs"] * r["doc"] + vals["scanned_pages"] * r["scanned_page"] + vals["retries"] * r["retry"] + vals["lookups"] * r["lookup"]
    human = vals["review_hours"] * r["hourly"]
    requests_fee = vals["requests"] * r["request_fee"]
    formula = r["k"] * v + human + requests_fee
    floor = spec["floor"]
    base = max(floor, formula)
    total = 0 if spec.get("free") else ceil_step(base * spec["risk"] * urg, r["round_up_to"])
    return {"kind": kk, "label": spec["label"], "inputs": vals, "assumed_inputs": assumed, "urgency": urg_name,
            "internal": {"variable_cost": round(v, 2), "formula_amount": round(formula, 2), "floor": floor,
                         "floor_applied": floor >= formula, "risk": spec["risk"], "urgency_multiplier": urg},
            "quote_usd": total}


def email_for(result, case, client):
    i, label, total = result["inputs"], result["label"], result["quote_usd"]
    who = client or "there"
    if total == 0:
        return ("Checkup %s: no charge" % case,
                "Hello %s,\n\nWe received your repository and will send a plain-English checkup report. There is no charge.\n\n"
                "Data Care\n" % who)
    scope = ["%d source documents" % i["docs"]]
    if i["scanned_pages"]:
        scope.append("%d scanned pages read visually" % i["scanned_pages"])
    if i["requests"]:
        scope.append("up to %d records requests to the organizations that hold your missing data" % i["requests"])
    subject = "Quote %s: %s, $%s. Reply APPROVE to start" % (case, label, format(total, ","))
    body = (
        "Hello %s,\n\n"
        "Here is our quote for %s (case %s).\n\n"
        "Scope: %s.\n"
        "Price: $%s, a not-to-exceed amount. If the work costs us less, you pay less, down to our minimum for this kind of job. "
        "We will not bill above $%s without your written OK.\n\n"
        "What you get: the rebuilt asset and a report in which every item is labeled recovered, reconstructed and tested, "
        "reconstructed but untested, or unresolved, each with its source. We never invent a value that no source supports.\n\n"
        "Nothing starts until you approve. To start, reply to this email with the single word APPROVE. "
        "To cancel, reply DECLINE. Questions are welcome; we will answer on this thread.\n\n"
        "Data Care\n" % (who, label.lower(), case, "; ".join(scope), format(total, ","), format(total, ",")))
    return subject, body


def classify_reply(text):
    new = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(">"):
            continue
        if re.match(r"^On .+wrote:?$", s, re.I) or re.match(r"^-{2,}\s*(original|forwarded)", s, re.I) or re.match(r"^from:\s", s, re.I):
            break
        if s:
            new.append(s)
    body = re.sub(r"[^a-z0-9' ]", " ", " ".join(new)[:400].lower())
    if re.search(r"\bnot approved?\b", body):
        return "decline"
    neg = re.search(r"\b(decline|reject|cancel|stop|no thanks|do not|don'?t|not approved?|not yet|never)\b|\bno\b", body)
    pos = re.search(r"\b(approve|approved|yes|go ahead|proceed|accept|agreed|confirmed?)\b", body)
    if neg and pos:
        return "unclear"
    if neg:
        return "decline"
    if pos:
        return "approve"
    return "unclear"


def final_invoice(pricing, result, quote_usd):
    over_pct = pricing["rates"]["overrun_needs_person_pct"]
    actual = result["quote_usd"]
    invoice = min(actual, quote_usd) if quote_usd else actual
    needs_person = bool(quote_usd) and actual > quote_usd * (1 + over_pct / 100.0)
    return {"invoice_usd": invoice, "actual_usd": actual, "quoted_usd": quote_usd,
            "needs_person": needs_person,
            "note": "invoice is never above the quote; a person decides if actual runs over by %d%%" % over_pct if needs_person else "within quote"}


def add_inputs(p):
    p.add_argument("--kind", required=True)
    p.add_argument("--docs", type=float)
    p.add_argument("--scanned-pages", type=float, dest="scanned_pages")
    p.add_argument("--requests", type=float)
    p.add_argument("--retries", type=float)
    p.add_argument("--lookups", type=float)
    p.add_argument("--review-hours", type=float, dest="review_hours")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rush", action="store_true")
    g.add_argument("--normal", action="store_true")
    p.add_argument("--pricing")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote")
    add_inputs(q)
    q.add_argument("--case", default="C-XXXX")
    q.add_argument("--client", default="")
    f = sub.add_parser("final")
    add_inputs(f)
    f.add_argument("--quote-usd", type=float, required=True)
    r = sub.add_parser("reply")
    r.add_argument("--file", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "reply":
        with open(a.file, encoding="utf-8", errors="replace") as fh:
            print(json.dumps({"decision": classify_reply(fh.read())}))
        return 0
    pricing = load_pricing(a.pricing)
    given = {n: getattr(a, n) for n in INPUTS}
    urgency = "rush" if a.rush else ("normal" if a.normal else None)
    res = compute(pricing, a.kind, given, urgency)
    if a.cmd == "quote":
        res["email_subject"], res["email_body"] = email_for(res, a.case, a.client)
        res["approval_word"] = "APPROVE"
    else:
        res["final"] = final_invoice(pricing, res, a.quote_usd)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
