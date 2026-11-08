#!/usr/bin/env python3
"""Find inputs where two candidate rebuilds disagree, and draft the question for the client.

Use it when two readings of a rule both pass the backtest. If they never disagree on the
probes, either reading is safe and there is nothing to ask. If they do, ask the client before choosing.

Function mode (code modules; same mapping.json as backtest.py, with "call" and "config"):
    python3 probe_diff.py --a cand_a/invoicing.py --b cand_b/invoicing.py --mapping mapping.json \
        --template probe_row.json --thresholds-from discounts.yml --step 1 \
        --grid '{"customer_tier": ["standard", "silver", "gold"], "subtotal": ["1000.50", "20312.55"]}' \
        --a-label "the 10% cap is applied before rounding" --b-label "the cap is applied after rounding" \
        --describe "a {customer_tier} customer's invoice for {total_units} units with a ${subtotal} subtotal"
  probe_row.json is one record row, with "{value}" where the threshold probe goes, for example
    {"invoice_id": "PROBE", "subtotal": "{subtotal}", "total_units": "{value}", "customer_tier": "{customer_tier}"}

Script mode (v1, unchanged): the template is one JSON input for a script that prints JSON,
    python3 probe_diff.py --a rebuilt_a/invoicing.py --b rebuilt_b/invoicing.py \
        --template probe.json --thresholds-from discounts.yml [--values 250,7500]

--thresholds-from reads every number >= 1 in a config file (comments are skipped) and probes just below,
at and just above it (--step, default 0.01; use --step 1 for counts such as units). --grid adds more axes;
every combination is probed. Both candidates run only in a subprocess with a timeout; the client's
original file is refused (see backtest.py). Standard library only, Python 3.8+.
"""
import argparse
import itertools
import json
import os
import re
import sys
from decimal import Decimal

from backtest import (MappingError, OriginalFileError, call_function, check_not_original, compare, fill,
                      resolve, run_candidate, same)  # noqa: F401  (same kept for older importers)


def strip_comments(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r"(^|\s)(#|//).*$", "", line)
        out.append(line)
    return "\n".join(out)


def probes_from(path, step=Decimal("0.01")):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = strip_comments(f.read())
    values = set()
    for m in re.finditer(r"(?<![\w.-])(\d+(?:\.\d+)?)(?![\w.])", text):
        n = Decimal(m.group(1))
        if n >= 1:
            for v in (n - step, n, n + step):
                values.add(v)
    return sorted(values)


def fmt(v):
    if isinstance(v, Decimal):
        return str(v.quantize(Decimal(1))) if v == v.to_integral_value() and v.as_tuple().exponent >= 0 else str(v)
    return str(v)


def load_json_arg(text):
    if text and os.path.exists(text):
        with open(text, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(text) if text else {}


def probe_rows(template, values, grid):
    axes = [("value", [fmt(v) for v in values])] if values else []
    axes += [(k, [str(x) for x in v]) for k, v in grid.items()]
    if not axes:
        return [({}, template)]
    rows = []
    for combo in itertools.product(*[vals for _, vals in axes]):
        point = dict(zip([k for k, _ in axes], combo))
        rows.append((point, fill(template, point)))
    return rows


def money(v):
    d = None
    try:
        d = Decimal(str(v))
    except Exception:
        return str(v)
    return "${:,}".format(d) if d.as_tuple().exponent <= -2 else str(v)


def describe(row, point, text):
    if text:
        try:
            return fill(text, {k: str(v) for k, v in row.items()} if isinstance(row, dict) else point)
        except MappingError:
            pass
    shown = row if isinstance(row, dict) else point
    return "an input with " + ", ".join("%s %s" % (k, v) for k, v in shown.items() if "{" not in str(v))


def make_question(real, labels, describe_text, field_words):
    d = real[0]
    field, pair = next(iter(d["differences"].items()))
    word = field_words.get(field, "discount" if field == "return" else field)
    case = describe(d["row"], d["point"], describe_text)
    opt_a = "%s: the %s is %s" % (labels[0], word, money(pair["a"]))
    opt_b = "%s: the %s is %s" % (labels[1], word, money(pair["b"]))
    more = len(real) - 1
    q = ("Two readings of your rules match every past record you sent, but they give a different %s for %s: "
         "%s, or %s. Which one is right?%s" % (word, case, money(pair["a"]), money(pair["b"]),
                                               (" (They also differ on %d other test case%s.)" % (more, "" if more == 1 else "s"))
                                               if more else ""))
    return q, [opt_a, opt_b]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", required=True, help="candidate A script")
    p.add_argument("--b", required=True, help="candidate B script")
    p.add_argument("--template", required=True, help="probe input (script mode) or probe record row (function mode)")
    p.add_argument("--mapping", help="backtest mapping with \"call\" (function mode)")
    p.add_argument("--thresholds-from")
    p.add_argument("--step", default="0.01", help="probe distance around each threshold (1 for whole units)")
    p.add_argument("--values", default="")
    p.add_argument("--grid", default="", help="JSON (or a JSON file): {placeholder: [values]}; all combinations")
    p.add_argument("--args", default="--invoice {input_file}")
    p.add_argument("--fields", default="", help="comma-separated output fields to compare (default: all)")
    p.add_argument("--a-label", default="Reading A")
    p.add_argument("--b-label", default="Reading B")
    p.add_argument("--describe", default="", help="the probe in client words, with {column} placeholders")
    p.add_argument("--original", action="append", default=[], help="client original(s) the tool must never run")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--out")
    a = p.parse_args()

    with open(a.template, encoding="utf-8") as f:
        template = json.load(f)
    step = Decimal(a.step)
    values = [Decimal(v) for v in a.values.split(",") if v.strip()]
    if a.thresholds_from:
        values += probes_from(a.thresholds_from, step)
    values = sorted(set(values))
    grid = load_json_arg(a.grid)
    mapping = load_json_arg(a.mapping) if a.mapping else None
    try:
        for script in (a.a, a.b):
            check_not_original(script, a.original + ([mapping["original"]] if mapping and mapping.get("original") else []))
        rows = probe_rows(template, values, grid)
    except (MappingError, OriginalFileError) as e:
        print("probe_diff: %s" % e, file=sys.stderr)
        sys.exit(2)
    fields = [x for x in a.fields.split(",") if x]

    outs = {}
    if mapping:
        call = mapping["call"]
        cfg = None
        if mapping.get("config"):
            cfg = dict(mapping["config"])
            cfg["file"] = resolve(cfg["file"], os.path.dirname(os.path.abspath(a.mapping)))
        try:
            calls = [{"key": i, "args": fill(call.get("args", []), row, {"config": {"$config": True}}),
                      "kwargs": fill(call.get("kwargs", {}), row, {"config": {"$config": True}})}
                     for i, (_, row) in enumerate(rows)]
        except (MappingError, ValueError) as e:
            print("probe_diff: %s" % e, file=sys.stderr)
            sys.exit(2)
        for name, script in (("a", a.a), ("b", a.b)):
            res, _notes, fatal = call_function(script, call["function"], calls, cfg, a.timeout)
            outs[name] = {i: res.get(str(i), {"error": fatal or "no result"}) for i in range(len(rows))}

    disagreements = []
    for i, (point, row) in enumerate(rows):
        if mapping:
            ra, rb = outs["a"][i], outs["b"][i]
            err_a, err_b = ra.get("error"), rb.get("error")
            out_a = {"return": ra.get("value")} if not err_a else None
            out_b = {"return": rb.get("value")} if not err_b else None
        else:
            out_a, err_a = run_candidate(a.a, a.args.split(), row, a.timeout)
            out_b, err_b = run_candidate(a.b, a.args.split(), row, a.timeout)
        if err_a or err_b:
            if err_a and err_b and err_a.split(":")[0] == err_b.split(":")[0]:
                continue                       # both refuse this input the same way: not a disagreement
            disagreements.append({"point": point, "row": row, "error_a": err_a, "error_b": err_b})
            continue
        keys = fields or sorted(set(out_a) | set(out_b))
        diff = {k: {"a": out_a.get(k), "b": out_b.get(k)} for k in keys if compare(out_a.get(k), out_b.get(k))}
        if diff:
            disagreements.append({"point": point, "row": row, "differences": diff})

    question, options = None, []
    real = [d for d in disagreements if "differences" in d]
    if real:
        question, options = make_question(real, (a.a_label, a.b_label), a.describe, {})
    report = {"probes": len(rows), "probe_values": [fmt(v) for v in values], "grid": grid,
              "disagreements": disagreements, "client_question": question, "question": question,
              "options": options}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
    print("probed %d inputs: %d disagreements" % (len(rows), len(disagreements)))
    if question:
        print("ask the client: " + question)
        for k, o in enumerate(options):
            print("  option %d: %s" % (k + 1, o))
    elif not disagreements:
        print("the two readings agree on every probe: either is safe, nothing to ask the client")
    for d in disagreements:
        if "differences" not in d:
            print("  %s: A error %s, B error %s" % (d["point"], d.get("error_a"), d.get("error_b")))
            break
    sys.exit(1 if disagreements else 0)


if __name__ == "__main__":
    main()
