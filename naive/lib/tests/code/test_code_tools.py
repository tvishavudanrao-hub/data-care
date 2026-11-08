"""backtest.py and probe_diff.py on a code module (kind "code"). Inline fixtures only. Run: python3 -m pytest -q"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

LIB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, LIB)
import backtest  # noqa: E402
import probe_diff  # noqa: E402

CONFIG = """# settings (exported 2026-09-30)
volume_tiers:            # by units
  - min_units: 100
    rate: 0.03
  - min_units: 500
    rate: 0.06
loyalty_bonus:
  standard: 0.00
  gold: 0.02
"""
HEAD = '''from decimal import Decimal, ROUND_HALF_UP
CENT = Decimal("0.01")
def load_config(path):
    import json
    return json.load(open(path)) if path.endswith(".json") else None
'''
BODY_OK = '''def compute_discount(subtotal, total_units, customer_tier, config):
    rate = Decimal("0")
    for t in sorted(config["volume_tiers"], key=lambda t: t["min_units"]):
        if total_units >= t["min_units"]:
            rate = Decimal(str(t["rate"]))
    rate = min(rate + Decimal(str(config["loyalty_bonus"].get(customer_tier, 0))), Decimal("0.07"))
    return (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)
'''
RECORDS = ("﻿invoice_id,customer_tier,total_units,subtotal,discount\n"
           "I-1,standard,100,1001.50,30.05\n"
           "\n"
           "I-2,gold,500,2000.00,140.00\n"
           "I-3,gold,99,1000.00,20.00\n"
           "I-4,standard,,100.00,0.00\n")
MAPPING = {"id_column": "invoice_id",
           "call": {"function": "compute_discount",
                    "args": ["{subtotal:decimal}", "{total_units:int}", "{customer_tier}", "{config}"]},
           "config": {"file": "discounts.yml"}, "returns": "Decimal", "compare": {"return": "discount"}}


class Case(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="codecase_")
        self.put("discounts.yml", CONFIG)
        with open(os.path.join(self.d, "invoices.csv"), "wb") as f:
            f.write(RECORDS.encode("utf-8") + b"I-5,go\xff\xfeld,100,10.00,0.50\n")
        os.mkdir(os.path.join(self.d, "rebuilt"))

    def put(self, name, text):
        path = os.path.join(self.d, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def run_bt(self, body, mapping=None, **kw):
        script = self.put("rebuilt/invoicing.py", HEAD + body)
        return backtest.backtest(script, os.path.join(self.d, "invoices.csv"), mapping or MAPPING,
                                 mapping_dir=self.d, **kw)


class Backtest(Case):
    def test_function_mode_matches_and_skips_unreadable(self):
        r = self.run_bt(BODY_OK)
        self.assertEqual((r["passed"], r["failed"], r["rows_checked"]), (3, 0, 3), r)
        self.assertEqual([u["id"] for u in r["unreadable"]], ["I-4", "I-5"])   # blank units, bad bytes
        self.assertIn("total_units is blank", r["unreadable"][0]["reason"])
        self.assertEqual(r["unreadable_rows"], [6, 7])                          # physical lines (blank line counted)
        self.assertIn("built-in YAML reader", " ".join(r["notes"]))
        self.assertFalse(os.path.exists(os.path.join(self.d, "rebuilt", "__pycache__")))

    def test_unrounded_and_float_results_fail(self):
        r = self.run_bt(BODY_OK.replace(".quantize(CENT, rounding=ROUND_HALF_UP)", ""))
        self.assertEqual(r["failed"], 1)
        self.assertEqual(r["mismatches"][0]["why"], "not rounded to the cent")
        r = self.run_bt(BODY_OK.replace("return (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)",
                                        "return float((subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP))"))
        self.assertEqual(r["passed"], 0)
        self.assertIn("contract says Decimal", r["mismatches"][0]["why"])

    def test_half_even_is_caught_at_a_tie(self):
        r = self.run_bt(BODY_OK.replace("rounding=ROUND_HALF_UP", 'rounding="ROUND_HALF_EVEN"'))
        self.assertEqual([m["id"] for m in r["mismatches"]], ["I-1"])           # 30.045 -> 30.05 vs 30.04

    def test_candidate_prints_and_hangs_safely(self):
        body = BODY_OK.replace("    rate = Decimal(\"0\")\n", "    print('debug', subtotal)\n    rate = Decimal(\"0\")\n"
                               "    while customer_tier == 'gold' and total_units == 99: pass\n")
        r = self.run_bt(body, timeout=1)
        self.assertEqual(r["passed"], 2)
        self.assertIn("timed out", r["errors"][0]["error"])

    def test_refuses_the_clients_original(self):
        original = self.put("invoicing.py", HEAD + BODY_OK)                     # next to the records
        with self.assertRaises(backtest.OriginalFileError):
            backtest.backtest(original, os.path.join(self.d, "invoices.csv"), MAPPING, mapping_dir=self.d)
        with self.assertRaises(backtest.OriginalFileError):                     # unchanged copy in rebuilt/
            self.run_bt(BODY_OK)
        os.remove(original)
        other = self.put("orig_module.py", HEAD + BODY_OK)
        with self.assertRaises(backtest.OriginalFileError):
            self.run_bt(BODY_OK, originals=[other])

    def test_mapping_errors_are_plain(self):
        m = dict(MAPPING, call=dict(MAPPING["call"], args=["{amount:decimal}"]))
        with self.assertRaises(backtest.MappingError):
            self.run_bt(BODY_OK, mapping=m)

    def test_script_mode_still_works(self):
        script = self.put("rebuilt/cli.py", "import json,sys\nd=json.load(open(sys.argv[2]))\nprint('debug')\n"
                          "print(json.dumps({'discount': '%.2f' % (float(d['subtotal']) * 0.07)}))\n")
        r = backtest.backtest(script, os.path.join(self.d, "invoices.csv"),
                              {"id_column": "invoice_id", "input": {"subtotal": "{subtotal}"},
                               "compare": {"discount": "discount"}}, mapping_dir=self.d)
        self.assertEqual(r["rows_checked"], 4)
        self.assertEqual(r["passed"], 1)                                        # only I-2 is 7%


class ProbeDiff(Case):
    def probe(self, body_b, extra=()):
        a = self.put("rebuilt/invoicing.py", HEAD + BODY_OK)
        os.makedirs(os.path.join(self.d, "b"), exist_ok=True)
        b = self.put("b/invoicing.py", HEAD + body_b)
        self.put("mapping.json", json.dumps(MAPPING))
        self.put("row.json", json.dumps({"subtotal": "{subtotal}", "total_units": "{value}", "customer_tier": "{customer_tier}"}))
        out = os.path.join(self.d, "probe.json")
        p = subprocess.run([sys.executable, os.path.join(LIB, "probe_diff.py"), "--a", a, "--b", b,
                            "--mapping", os.path.join(self.d, "mapping.json"), "--template", os.path.join(self.d, "row.json"),
                            "--thresholds-from", os.path.join(self.d, "discounts.yml"), "--step", "1",
                            "--grid", '{"customer_tier": ["standard", "gold"], "subtotal": ["1001.50"]}',
                            "--describe", "a {customer_tier} invoice for {total_units} units, subtotal ${subtotal}",
                            "--a-label", "Half-up", "--b-label", "Half to even", "--out", out] + list(extra),
                           capture_output=True, text=True, cwd=self.d)
        with open(out) as f:
            return p, json.load(f)

    def test_equivalent_readings_ask_nothing(self):
        cap_after = BODY_OK.replace(
            '    rate = min(rate + Decimal(str(config["loyalty_bonus"].get(customer_tier, 0))), Decimal("0.07"))\n'
            '    return (subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP)\n',
            '    rate = rate + Decimal(str(config["loyalty_bonus"].get(customer_tier, 0)))\n'
            '    return min((subtotal * rate).quantize(CENT, rounding=ROUND_HALF_UP),'
            ' (subtotal * Decimal("0.07")).quantize(CENT, rounding=ROUND_HALF_UP))\n')
        p, rep = self.probe(cap_after)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertIsNone(rep["question"])
        self.assertNotIn("2026", rep["probe_values"])                           # comment dates are not thresholds
        self.assertEqual(rep["probe_values"], ["99", "100", "101", "499", "500", "501"])

    def test_disagreement_gives_one_plain_question(self):
        p, rep = self.probe(BODY_OK.replace("rounding=ROUND_HALF_UP", 'rounding="ROUND_HALF_EVEN"'))
        self.assertEqual(p.returncode, 1)
        self.assertIn("standard invoice for 100 units, subtotal $1001.50", rep["question"])
        self.assertIn("$30.05, or $30.04", rep["question"])
        self.assertEqual(rep["options"], ["Half-up: the discount is $30.05", "Half to even: the discount is $30.04"])

    def test_probes_from_skips_comments(self):
        path = self.put("t.yml", "a: 100  # was 2026\nb: 0.5\n")
        self.assertEqual(probe_diff.probes_from(path, Decimal(1)), [Decimal(99), Decimal(100), Decimal(101)])


if __name__ == "__main__":
    unittest.main()
