#!/usr/bin/env python3
"""Replay the client's surviving records through a candidate rebuild.

    python3 backtest.py --script rebuilt/invoicing.py --records invoices_export.csv --mapping mapping.json

mapping.json tells the tool how a record row becomes an input, and what to compare:
{
  "id_column": "invoice_id",
  "input": {"invoice_id": "{invoice_id}", "lines": [
      {"qty": 1, "unit_price": "{goods_subtotal}", "category": "goods"},
      {"qty": 1, "unit_price": "{shipping}", "category": "shipping"}]},
  "args": ["--invoice", "{input_file}"],
  "compare": {"discount": "discount", "tax": "tax", "total": "total"}
}
"{column}" is replaced with that column's value; "compare" maps output field -> record column.
Unreadable rows are skipped and listed, never guessed. Numbers compare to the cent.
Standard library only, Python 3.8+.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation


def fill(template, row):
    if isinstance(template, dict):
        return {k: fill(v, row) for k, v in template.items()}
    if isinstance(template, list):
        return [fill(v, row) for v in template]
    if isinstance(template, str):
        out = template
        for col, val in row.items():
            out = out.replace("{%s}" % col, val)
        return out
    return template


def same(a, b):
    try:
        return Decimal(str(a)).quantize(Decimal("0.01")) == Decimal(str(b)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return str(a).strip() == str(b).strip()


def readable(row, width):
    return len(row) == width and not any("�" in v for v in row)


def run_candidate(script, args, payload, timeout):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    try:
        cmd = [sys.executable, os.path.abspath(script)] + [a.replace("{input_file}", path) for a in args]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=os.path.dirname(os.path.abspath(script)))
        if p.returncode != 0:
            return None, (p.stderr.strip().splitlines() or ["exit %d" % p.returncode])[-1]
        return json.loads(p.stdout), None
    except subprocess.TimeoutExpired:
        return None, "timed out after %ss" % timeout
    except ValueError:
        return None, "output was not JSON"
    finally:
        os.remove(path)


def backtest(script, records, mapping, timeout=10):
    with open(records, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    result = {"script": script, "records": records, "rows_total": len(body), "rows_checked": 0,
              "unreadable_rows": [], "passed": 0, "failed": 0, "mismatches": [], "errors": []}
    args = mapping.get("args", ["--invoice", "{input_file}"])
    for n, raw in enumerate(body, start=2):
        if not readable(raw, len(header)):
            result["unreadable_rows"].append(n)
            continue
        row = dict(zip(header, raw))
        rid = row.get(mapping.get("id_column", ""), "row %d" % n)
        out, err = run_candidate(script, args, fill(mapping["input"], row), timeout)
        result["rows_checked"] += 1
        if err:
            result["failed"] += 1
            result["errors"].append({"row": n, "id": rid, "error": err})
            continue
        bad = [{"row": n, "id": rid, "field": field, "record": row.get(col), "candidate": out.get(field)}
               for field, col in mapping["compare"].items() if not same(out.get(field), row.get(col))]
        if bad:
            result["failed"] += 1
            result["mismatches"].extend(bad)
        else:
            result["passed"] += 1
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--script", required=True)
    p.add_argument("--records", required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("--out")
    p.add_argument("--timeout", type=int, default=10)
    a = p.parse_args()
    with open(a.mapping) as f:
        mapping = json.load(f)
    r = backtest(a.script, a.records, mapping, a.timeout)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(r, f, indent=2)
    print("backtest: %d of %d readable rows match; %d unreadable rows skipped (%s)"
          % (r["passed"], r["rows_checked"], len(r["unreadable_rows"]),
             ", ".join(map(str, r["unreadable_rows"])) or "none"))
    for m in r["mismatches"][:10]:
        print("  row %s %s: %s is %s in the record, %s in the rebuild"
              % (m["row"], m["id"], m["field"], m["record"], m["candidate"]))
    for e in r["errors"][:5]:
        print("  row %s %s: error %s" % (e["row"], e["id"], e["error"]))
    sys.exit(0 if r["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
