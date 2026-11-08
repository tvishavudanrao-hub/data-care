"""Tests for the patterns seen in the real demo cases (board report in markdown, CFO rules email with numbered
items and tier bullets, ERP export with snake_case columns, a model whose rows are named a little differently).
All fixture text is inline. Run: python3 -m pytest -q tests/"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "context_scan.py")
sys.path.insert(0, ROOT)

import context_scan as cs  # noqa: E402

QUARTERS = ["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]

REPORT = """# Northwind Supply: Board report, Q3 2026

Prepared by the CFO for the board meeting of 14 October 2026.

## Q3 2026 at a glance

- Units sold: 2,362
- Net revenue: $59,440.91 (153.8% vs Q2 2026)
- Gross margin: 62.0%
- Operating income: $17,219.75

## FY2025 summary

| Metric | FY2025 |
|---|---|
| Net revenue | $142,038.15 |
| Gross margin | 62.0% |

## Net revenue by quarter

| Quarter | Net revenue | Gross margin | Growth vs prior quarter |
|---|---|---|---|
| Q1 2025 | $23,540.58 | 62.0% | n/a |
| Q2 2025 | $25,354.85 | 62.0% | 7.7% |
| Q1 2026 | $30,626.41 | 62.0% | -48.3% |

## Notes

- COGS held at 38% of net revenue all year.
"""

EMAIL_WHOLE = """From: CFO <cfo@northwind.example>
To: Finance <finance@northwind.example>
Date: Tue, 20 Oct 2026 16:05:00 +0000
Subject: how the model works
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Hi all,

1. Gross revenue is units sold times list price for the quarter.

2. Volume discount is decided per quarter on that quarter's total units.
   Once a quarter reaches a tier, the tier rate applies to the WHOLE quarter's
   gross revenue, not just the units above the line:
     - 1,000 units or more: 5%
     - 2,500 units or more: 10%
     - below 1,000 units: no discount
   The thresholds and rates live on the Assumptions tab, so reference those
   cells rather than typing the numbers into formulas.

3. COGS is 38% of NET revenue (after discount), rounded to the cent.

4. Gross margin % is gross profit over net revenue. Growth is net revenue vs
   the prior quarter. If the denominator is zero, show 0%, not an error.

One gap: I do not have Q1 2026 operating expenses. Please leave it blank and
flag it rather than estimating.

Thanks
"""

EMAIL_MARGINAL = """From: CFO <cfo@southwind.example>
To: Finance <finance@southwind.example>
Date: Tue, 20 Oct 2026 16:05:00 +0000
Subject: how the model works
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

1. Gross revenue = units x list price for the quarter.

2. Our volume discount is MARGINAL, like tax brackets. Only the units above
   each threshold earn that tier's rate:
     - units above 800 (up to 2,000) get 4% off list price
     - units above 2,000 get 9% off list price
     - the first 800 units each quarter get nothing
   Thresholds and rates are on the Assumptions tab; please reference them.
   Row 6 shows the effective rate (discount over gross revenue).

3. COGS is 42% of GROSS (list) revenue, before any discount.

4. Gross margin % = gross profit / net revenue. Zero denominator: show 0%.

Q4 2026 operating expenses are not closed yet and I cannot give you a number.
Leave them empty.
"""

EXPORT = """quarter,units_sold,list_price,gross_revenue,discount,net_revenue
Q1 2025,942,24.99,23540.58,0.00,23540.58
Q2 2025,1068,24.99,26689.32,1334.47,25354.85
"""


def build_model(path, garble=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Model"
    ws.append(["Line item"] + QUARTERS + ["Total"])
    rows = [("Units sold", 1000), ("List price per unit", 24.99), ("Gross revenue", 25000), ("Discount rate", 0.05),
            ("Volume discount", 1250), ("Net revenue", 23750), ("Cost of goods sold", 9000), ("Gross profit", 14750),
            ("Gross margin %", 0.62), ("Operating expenses", 9000), ("Operating income", 5750),
            ("Net revenue growth vs prior quarter", 0.1)]
    for label, v in rows:
        ws.append([label] + [v] * len(QUARTERS) + [v * 8])
    ws["C6"] = None                       # Volume discount, Q2 2025: the export's "discount" column covers it
    ws["F11"] = None                      # Operating expenses, Q1 2026: the client says it does not exist
    ws["I11"] = None                      # Operating expenses, Q4 2026: same, in the other email
    if garble:
        ws[garble] = "2?.4�"
    a = wb.create_sheet("Assumptions")
    a.append(["Assumption", "Value"])
    a.append(["COGS %", 0.38])
    a.append(["Tier 1 threshold (units per quarter)", 1000])
    a.append(["Tier 1 discount rate", 0.05])
    wb.save(path)


def run_case(files, garble=None):
    tmp = tempfile.mkdtemp(prefix="ctx_demo_")
    case = os.path.join(tmp, "case")
    os.makedirs(case)
    build_model(os.path.join(case, "model_damaged.xlsx"), garble)
    for name, text in files.items():
        with open(os.path.join(case, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    out = os.path.join(tmp, "ev")
    r = subprocess.run([sys.executable, SCRIPT, "--case-dir", case, "--case", "C-0101", "--model",
                        os.path.join(case, "model_damaged.xlsx"), "--out-dir", out],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert r.returncode == 0, r.stderr.decode()
    load = lambda n: json.load(open(os.path.join(out, n), encoding="utf-8"))
    res = load("evidence.json"), load("fragments.json"), load("gaps.json")
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def find(items, **kw):
    return [x for x in items if all(x.get(k) == v for k, v in kw.items())]


def rule(ev, start):
    r = [x for x in ev["rules"] if x["text"].startswith(start)]
    assert len(r) == 1, (start, [x["text"] for x in ev["rules"]])
    return r[0]


class WholeQuarterCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev, cls.fr, cls.gaps = run_case({"board_report_Q3_2026.md": REPORT, "cfo_model_rules.eml": EMAIL_WHOLE,
                                             "erp_export.csv": EXPORT}, garble="H3")
        cls.fid = {f["fragment_id"]: f for f in cls.fr}

    # 1. the period of a figure comes from its heading, not from "vs Q2 2026"
    def test_comparison_period_ignored(self):
        r = find(self.ev["reported"], label="Net revenue", period="Q3 2026", source="board_report_Q3_2026.md#line8")
        self.assertEqual([x["value"] for x in r], [59440.91])
        self.assertFalse(find(self.ev["reported"], label="Net revenue", period="Q2 2026", value=59440.91))

    def test_own_periods_helper(self):
        t = "Net revenue: $59,440.91 (153.8% vs Q2 2026), up from Q1 2026, Q3 2026 compared with Q3 2025"
        self.assertEqual([c for _, _, c in cs.own_periods(t)], [("Q", 3, 2026)])

    # 2. markdown pipe tables, both orientations
    def test_markdown_table_periods_down_the_first_column(self):
        rep = self.ev["reported"]
        self.assertEqual(find(rep, label="Net revenue", period="Q1 2025")[0]["value"], 23540.58)
        self.assertEqual(find(rep, label="Gross margin %", period="Q1 2025")[0]["value"], 0.62)
        g = "Net revenue growth vs prior quarter"
        self.assertEqual(find(rep, label=g, period="Q2 2025")[0]["value"], 0.077)
        self.assertEqual(find(rep, label=g, period="Q1 2026")[0]["value"], -0.483)
        self.assertFalse(find(rep, label=g, period="Q1 2025"))          # "n/a" is skipped
        self.assertFalse([r for r in self.ev["rules"] if "|" in r["text"]])

    def test_markdown_table_periods_across_the_header(self):
        self.assertEqual(find(self.ev["reported"], label="Net revenue", period="FY2025")[0]["value"], 142038.15)
        self.assertEqual(find(self.ev["reported"], label="Gross margin %", period="FY2025")[0]["value"], 0.62)

    # 3. "Label: value" is a figure, not a rule
    def test_bare_figure_is_reported_not_a_rule(self):
        r = find(self.ev["reported"], label="Gross margin %", period="Q3 2026", source="board_report_Q3_2026.md#line9")
        self.assertEqual(r[0]["value"], 0.62)
        self.assertEqual(r[0]["source_label"], "Gross margin")
        self.assertFalse([x for x in self.ev["rules"] if x["text"].startswith("Gross margin: 62")])
        self.assertEqual(find(self.ev["values"], label="Units sold", period="Q3 2026")[0]["value"], 2362.0)
        self.assertEqual(cs.bare_figure("Net revenue: $59,440.91 (153.8% vs Q2 2026)"), ("Net revenue", 59440.91, []))
        self.assertIsNone(cs.bare_figure("1,000 units or more: 5%"))
        self.assertIsNone(cs.bare_figure("Zero denominator: show 0%."))

    # 4. tier bullets: one rule each, not lost, not merged with the next paragraph
    def test_tier_bullets_whole(self):
        self.assertEqual((rule(self.ev, "1,000 units or more")["numbers"], rule(self.ev, "1,000 units or more")["operator_hint"]),
                         ([1000.0, 0.05], ">="))
        self.assertEqual((rule(self.ev, "2,500 units or more")["numbers"], rule(self.ev, "2,500 units or more")["operator_hint"]),
                         ([2500.0, 0.1], ">="))
        below = rule(self.ev, "below 1,000 units")
        self.assertEqual((below["text"], below["numbers"], below["operator_hint"]),
                         ("below 1,000 units: no discount", [1000.0, 0.0], "<"))

    # 6. labels map to the model's rows; source_label keeps the original
    def test_export_columns_map_to_model_rows(self):
        v = self.ev["values"]
        self.assertEqual(find(v, label="List price per unit", period="Q1 2025")[0]["source_label"], "list price")
        d = find(v, label="Volume discount", period="Q2 2025")
        self.assertEqual((d[0]["value"], d[0]["source_label"]), (1334.47, "discount"))
        self.assertFalse([x for x in v if x["label"] in ("list price", "discount")])
        self.assertFalse([g for g in self.gaps if "Volume discount, Q2 2025" in g["what"]])  # covered by the export

    def test_overlap_label_helper(self):
        s = cs.Scan(".", "C-0009")
        s.model_labels = ["Discount rate", "Volume discount", "List price per unit", "Tier 1 discount rate",
                          "Net revenue", "Gross revenue", "Net revenue growth vs prior quarter"]
        s.model_rows = set(s.model_labels[:3] + s.model_labels[4:])
        self.assertEqual(s.overlap_label("discount"), "Volume discount")
        self.assertEqual(s.overlap_label("list_price"), "List price per unit")
        self.assertEqual(s.overlap_label("Growth vs prior quarter"), "Net revenue growth vs prior quarter")
        self.assertIsNone(s.overlap_label("revenue"))                 # two rows fit equally

    # 7. context, row_hint, scope, base, zero_denominator, references_assumptions
    def test_rule_context_and_flags(self):
        r = rule(self.ev, "1,000 units or more")
        self.assertEqual(r["context"], "2. Volume discount is decided per quarter on that quarter's total units.")
        self.assertEqual(r["row_hint"], "Volume discount")
        self.assertEqual((r["scope"], r["base"], r["references_assumptions"]), ("whole", "gross revenue", True))
        cogs = rule(self.ev, "COGS is 38% of NET revenue")
        self.assertEqual((cogs["numbers"], cogs["base"], cogs["row_hint"]), ([0.38], "net revenue", "Cost of goods sold"))
        gm = rule(self.ev, "Gross margin % is gross profit over net revenue")
        self.assertEqual((gm["row_hint"], gm["zero_denominator"], gm["numbers"]), ("Gross margin %", 0, []))
        gr = rule(self.ev, "Growth is net revenue vs the prior quarter")
        self.assertEqual((gr["row_hint"], gr["zero_denominator"]), ("Net revenue growth vs prior quarter", 0))
        self.assertEqual(rule(self.ev, "If the denominator is zero")["zero_denominator"], 0)
        self.assertEqual(rule(self.ev, "Gross revenue is units sold times list price")["row_hint"], "Gross revenue")
        notes = rule(self.ev, "COGS held at 38% of net revenue")
        self.assertEqual((notes["context"], notes["base"], notes["operator_hint"]), ("Notes", "net revenue", None))
        self.assertNotIn("scope", gm)

    # 8. a figure the client says does not exist
    def test_known_missing(self):
        km = self.ev["known_missing"]
        self.assertEqual([(k["label"], k["period"]) for k in km], [("Operating expenses", "Q1 2026")])
        self.assertTrue(km[0]["source"].startswith("cfo_model_rules.eml#line"))
        self.assertIn(km[0]["fragment_id"], self.fid)
        g = [g for g in self.gaps if g["what"].startswith("Operating expenses, Q1 2026")]
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["status"], "open")
        self.assertFalse([g for g in self.gaps if "(Operating expenses, Q1 2026) is blank" in g["what"]])
        self.assertFalse([r for r in self.ev["rules"] if "operating expenses" in r["text"].lower()])

    def test_garbled_model_cell_is_a_gap(self):
        self.assertTrue([g for g in self.gaps if g["what"].startswith("Model!H3 (List price per unit, Q3 2026) is garbled")])


class MarginalCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev, cls.fr, cls.gaps = run_case({"cfo_model_rules.eml": EMAIL_MARGINAL})

    def test_tier_bullets_marginal(self):
        a = rule(self.ev, "units above 800")
        self.assertEqual((a["numbers"], a["operator_hint"], a["scope"]), ([800.0, 2000.0, 0.04], ">", "marginal"))
        b = rule(self.ev, "units above 2,000")
        self.assertEqual((b["numbers"], b["operator_hint"], b["scope"]), ([2000.0, 0.09], ">", "marginal"))
        c = rule(self.ev, "the first 800 units")
        self.assertEqual((c["numbers"], c["scope"], c["row_hint"]), ([800.0, 0.0], "marginal", "Volume discount"))
        self.assertTrue(a["references_assumptions"])

    def test_names_are_not_numbers(self):
        r = rule(self.ev, "Row 6 shows the effective rate")
        self.assertEqual((r["numbers"], r["operator_hint"]), ([], None))
        self.assertEqual(cs.rule_numbers("Tier 1 threshold (units per quarter) is 1,000"), [1000.0])
        self.assertEqual(cs.rule_numbers("Row 6 shows the effective rate"), [])
        self.assertEqual(cs.rule_numbers("1. In Q3 2026 the tier 2 rate is 5% on 2,500 units"), [0.05, 2500.0])
        for x in self.ev["rules"]:
            self.assertNotIn(1.0, x["numbers"], x["text"])

    def test_base_and_zero_denominator(self):
        self.assertEqual(rule(self.ev, "COGS is 42% of GROSS (list) revenue")["base"], "gross revenue")
        self.assertEqual(rule(self.ev, "Zero denominator: show 0%")["zero_denominator"], 0)

    def test_known_missing_not_closed(self):
        self.assertEqual([(k["label"], k["period"]) for k in self.ev["known_missing"]],
                         [("Operating expenses", "Q4 2026")])


class Flags(unittest.TestCase):
    def test_rule_flags(self):
        F = cs.rule_flags
        self.assertEqual(F("the tier rate applies to the WHOLE quarter's gross revenue, not just the units above"),
                         {"scope": "whole", "base": "gross revenue"})
        self.assertEqual(F("Only the units above each threshold earn that tier's rate")["scope"], "marginal")
        self.assertEqual(F("Supplier costs are contracted against list (gross) revenue at 42%."), {"base": "gross revenue"})
        self.assertEqual(F("If the denominator is zero, show 0%, not an error."), {"zero_denominator": 0})
        self.assertEqual(F("The % is on the Assumptions tab."), {"references_assumptions": True})
        self.assertEqual(F("Net revenue is gross minus discount."), {})


if __name__ == "__main__":
    unittest.main()
