#!/usr/bin/env python3
"""Check a rebuilt ledger or spreadsheet against money that really moved, and list the gaps to hunt.

    python3 reconcile.py --rows rebuilt_ledger.csv --bank bank_statement.csv --out reconcile.json

rebuilt_ledger.csv needs date, amount and source columns (source = the receipt, email or
record each row came from). bank_statement.csv needs date, amount and description.
Column names can be changed with --row-cols date,amount,source and --bank-cols date,amount,description.

Each bank line is matched to one rebuilt row with the same amount (to the cent, sign ignored)
within --window-days. What is left over is reported:
  gaps                 money moved but no row explains it: hunt for the missing receipt or record
  unsupported_rows     rebuilt rows with no source: evidence is missing, do not deliver them as fact
  rows_without_bank    rows the bank never saw: cash, not cleared yet, or a wrong amount
Exit code 0 only when there are no gaps and no unsupported rows.
Standard library only, Python 3.8+.
"""
import argparse
import csv
import json
import sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


def read(path, cols):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    out, unreadable = [], []
    for n, r in enumerate(rows, start=2):
        try:
            d = date.fromisoformat((r.get(cols[0]) or "").strip()[:10])
            amt = abs(Decimal((r.get(cols[1]) or "").replace(",", "").replace("$", "").strip()))
        except (ValueError, InvalidOperation):
            unreadable.append(n)
            continue
        out.append({"row": n, "date": d, "amount": amt.quantize(Decimal("0.01")),
                    "text": (r.get(cols[2]) or "").strip(), "raw": r})
    return out, unreadable


def hints(line):
    who = line["text"] or "this payee"
    when = line["date"].strftime("%B %Y")
    return ["email: search for \"%s\" and the amount %s around %s" % (who, line["amount"], when),
            "files and drive: search for an invoice or receipt for %s" % line["amount"],
            "accounting or card exports: look for a line dated %s" % line["date"].isoformat(),
            "if still missing: ask the client to request a duplicate receipt from %s (needs human approval)" % who]


def reconcile(rows, bank, window):
    used = set()
    matched = 0
    gaps = []
    for b in sorted(bank, key=lambda x: x["date"]):
        best = None
        for i, r in enumerate(rows):
            if i in used or r["amount"] != b["amount"]:
                continue
            gap_days = abs((r["date"] - b["date"]).days)
            if gap_days <= window and (best is None or gap_days < best[1]):
                best = (i, gap_days)
        if best:
            used.add(best[0])
            matched += 1
        else:
            gaps.append({"gap_id": "G%d" % (len(gaps) + 1), "bank_row": b["row"], "date": b["date"].isoformat(),
                         "amount": str(b["amount"]), "description": b["text"], "search_hints": hints(b),
                         "status": "open"})
    unsupported = [{"row": r["row"], "date": r["date"].isoformat(), "amount": str(r["amount"])}
                   for r in rows if not r["text"]]
    without_bank = [{"row": r["row"], "date": r["date"].isoformat(), "amount": str(r["amount"]), "source": r["text"]}
                    for i, r in enumerate(rows) if i not in used]
    months = {}
    for side, items in (("rows", rows), ("bank", bank)):
        for x in items:
            m = months.setdefault(x["date"].strftime("%Y-%m"), {"rows": Decimal("0"), "bank": Decimal("0")})
            m[side] += x["amount"]
    by_month = [{"month": k, "rebuilt_total": str(v["rows"]), "bank_total": str(v["bank"]),
                 "difference": str(v["bank"] - v["rows"])} for k, v in sorted(months.items())]
    return {"bank_lines": len(bank), "rebuilt_rows": len(rows), "matched": matched, "gaps": gaps,
            "unsupported_rows": unsupported, "rows_without_bank": without_bank, "by_month": by_month}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rows", required=True)
    p.add_argument("--bank", required=True)
    p.add_argument("--row-cols", default="date,amount,source")
    p.add_argument("--bank-cols", default="date,amount,description")
    p.add_argument("--window-days", type=int, default=5)
    p.add_argument("--out")
    a = p.parse_args()
    rows, bad_rows = read(a.rows, a.row_cols.split(","))
    bank, bad_bank = read(a.bank, a.bank_cols.split(","))
    r = reconcile(rows, bank, a.window_days)
    r["unreadable"] = {"rows": bad_rows, "bank": bad_bank}
    if a.out:
        with open(a.out, "w") as f:
            json.dump(r, f, indent=2)
    print("reconcile: %d of %d bank lines explained; %d gaps to hunt; %d rows with no source; %d rows the bank never saw"
          % (r["matched"], r["bank_lines"], len(r["gaps"]), len(r["unsupported_rows"]), len(r["rows_without_bank"])))
    for g in r["gaps"][:10]:
        print("  %s %s %s %s" % (g["gap_id"], g["date"], g["amount"], g["description"]))
    sys.exit(0 if not r["gaps"] and not r["unsupported_rows"] else 1)


if __name__ == "__main__":
    main()
