#!/usr/bin/env python3
"""Find inputs where two candidate rebuilds disagree, and draft the question for the client.

Use it when two readings of a rule both pass the backtest. If they never disagree on the
probes, either reading is safe. If they do, ask the client before choosing.

    python3 probe_diff.py --a rebuilt_a/invoicing.py --b rebuilt_b/invoicing.py \
        --template probe.json --thresholds-from discounts.yml [--values 250,7500]

probe.json is one input with "{value}" where the probe number goes, for example
  {"invoice_id": "PROBE", "lines": [{"qty": 1, "unit_price": "{value}", "category": "goods"}]}
--thresholds-from reads every number in a config file and probes just below, at and just above it.
Standard library only, Python 3.8+.
"""
import argparse
import json
import re
import sys
from decimal import Decimal

from backtest import fill, run_candidate, same


def probes_from(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    values = set()
    for m in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", text):
        n = Decimal(m.group(1))
        if n >= 1:
            for v in (n - Decimal("0.01"), n, n + Decimal("0.01")):
                values.add(v.quantize(Decimal("0.01")))
    return sorted(values)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", required=True, help="candidate A script")
    p.add_argument("--b", required=True, help="candidate B script")
    p.add_argument("--template", required=True)
    p.add_argument("--thresholds-from")
    p.add_argument("--values", default="")
    p.add_argument("--args", default="--invoice {input_file}")
    p.add_argument("--fields", default="", help="comma-separated output fields to compare (default: all)")
    p.add_argument("--out")
    a = p.parse_args()

    with open(a.template) as f:
        template = json.load(f)
    values = [Decimal(v) for v in a.values.split(",") if v.strip()]
    if a.thresholds_from:
        values += probes_from(a.thresholds_from)
    values = sorted(set(v.quantize(Decimal("0.01")) for v in values))
    args = a.args.split()
    fields = [x for x in a.fields.split(",") if x]

    disagreements = []
    for v in values:
        payload = fill(template, {"value": str(v)})
        out_a, err_a = run_candidate(a.a, args, payload, 10)
        out_b, err_b = run_candidate(a.b, args, payload, 10)
        if err_a or err_b:
            disagreements.append({"value": str(v), "error_a": err_a, "error_b": err_b})
            continue
        keys = fields or sorted(set(out_a) | set(out_b))
        diff = {k: {"a": out_a.get(k), "b": out_b.get(k)} for k in keys if not same(out_a.get(k), out_b.get(k))}
        if diff:
            disagreements.append({"value": str(v), "differences": diff})

    question = None
    real = [d for d in disagreements if "differences" in d]
    if real:
        d = real[0]
        field, pair = next(iter(d["differences"].items()))
        others = ", ".join(x["value"] for x in real[1:4])
        question = ("Two readings of your rules match every invoice you sent, but they disagree for an order "
                    "of exactly %s: one gives a %s of %s, the other %s.%s Which one is right?"
                    % (d["value"], field, pair["a"], pair["b"],
                       (" They also differ at " + others + ".") if others else ""))
    report = {"probes": [str(v) for v in values], "disagreements": disagreements, "client_question": question}
    if a.out:
        with open(a.out, "w") as f:
            json.dump(report, f, indent=2)
    print("probed %d values: %d disagreements" % (len(values), len(disagreements)))
    if question:
        print("ask the client: " + question)
    sys.exit(1 if disagreements else 0)


if __name__ == "__main__":
    main()
