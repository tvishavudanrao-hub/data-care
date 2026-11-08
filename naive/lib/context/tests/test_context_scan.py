"""Tests for context_scan.py. Run: python3 -m pytest -q tests/  (or python3 -m unittest discover tests)"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "context_scan.py")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import context_scan as cs  # noqa: E402
from fixtures import build_case, build_mini_case  # noqa: E402

FRAG_KEYS = {"fragment_id", "source_file", "location", "type", "confidence", "notes"}
GAP_KEYS = {"gap_id", "what", "why", "where_to_look", "status"}
ITEM_KEYS = {"label", "period", "value", "source", "fragment_id"}
RULE_KEYS = {"text", "numbers", "operator_hint", "source", "fragment_id"}


def run_scan(case_dir, case_id, out_dir, model=None):
    cmd = [sys.executable, SCRIPT, "--case-dir", case_dir, "--case", case_id, "--out-dir", out_dir]
    if model:
        cmd += ["--model", model]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=case_dir)
    assert r.returncode == 0, r.stderr.decode()
    load = lambda n: json.load(open(os.path.join(out_dir, n), encoding="utf-8"))
    return load("evidence.json"), load("fragments.json"), load("gaps.json"), \
        open(os.path.join(out_dir, "inventory.md"), encoding="utf-8").read(), r.stdout.decode()


def find(items, **kw):
    return [x for x in items if all(x.get(k) == v for k, v in kw.items())]


class MainCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ctx_main_")
        cls.case = build_case(os.path.join(cls.tmp, "case"))
        cls.out = os.path.join(cls.tmp, "evidence")
        cls.ev, cls.fr, cls.gaps, cls.inv, cls.stdout = run_scan(
            cls.case, "C-0001", cls.out, model=os.path.join(cls.case, "model.xlsx"))
        cls.fid = {f["fragment_id"]: f for f in cls.fr}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # contract shape -------------------------------------------------------
    def test_files_written(self):
        for n in ("evidence.json", "fragments.json", "gaps.json", "inventory.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, n)), n)
        self.assertIn("C-0001:", self.stdout)

    def test_evidence_shape(self):
        self.assertEqual(set(self.ev), {"case_id", "values", "reported", "rules"})
        self.assertEqual(self.ev["case_id"], "C-0001")
        for x in self.ev["values"] + self.ev["reported"]:
            self.assertEqual(set(x), ITEM_KEYS)
            self.assertIsInstance(x["value"], float)
            self.assertIn(x["fragment_id"], self.fid)
            self.assertRegex(x["source"], r"^[^#]+#.+")
        for r in self.ev["rules"]:
            self.assertEqual(set(r), RULE_KEYS)
            self.assertIn(r["operator_hint"], (">", ">=", "<", "<=", None))
            self.assertTrue(all(isinstance(n, float) for n in r["numbers"]))
            self.assertIn(r["fragment_id"], self.fid)

    def test_fragment_shape(self):
        ids = [f["fragment_id"] for f in self.fr]
        self.assertEqual(len(ids), len(set(ids)))
        for f in self.fr:
            self.assertEqual(set(f), FRAG_KEYS)
            self.assertRegex(f["fragment_id"], r"^F-0001-\d{3}$")
            self.assertIn(f["type"], ("code", "record", "clue"))
            self.assertTrue(0.0 <= f["confidence"] <= 1.0)

    def test_gap_shape(self):
        ids = [g["gap_id"] for g in self.gaps]
        self.assertEqual(len(ids), len(set(ids)))
        for g in self.gaps:
            self.assertEqual(set(g), GAP_KEYS)
            self.assertRegex(g["gap_id"], r"^G-0001-\d{2}$")
            self.assertEqual(g["status"], "open")
            self.assertTrue(g["where_to_look"] and all(isinstance(w, str) for w in g["where_to_look"]))

    # values and reported --------------------------------------------------
    def test_export_value_exact(self):
        v = find(self.ev["values"], label="Units sold", period="Q3 2025")
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["value"], 1200.0)
        self.assertEqual(v[0]["source"], "sales_export.csv#row2")
        self.assertEqual(self.fid[v[0]["fragment_id"]]["confidence"], 0.95)
        self.assertEqual(self.fid[v[0]["fragment_id"]]["type"], "record")

    def test_label_normalised_and_fuzzy(self):
        p = find(self.ev["values"], label="Price", period="Q3 2025")       # "Price ($)" in the export
        self.assertEqual(p[0]["value"], 42.0)
        self.assertEqual(self.fid[p[0]["fragment_id"]]["confidence"], 0.9)
        d = find(self.ev["values"], label="Discount", period="Q4 2025")    # "Discounts" in the export
        self.assertEqual(d[0]["value"], 5460.0)
        self.assertEqual(self.fid[d[0]["fragment_id"]]["confidence"], 0.7)

    def test_board_report_is_reported_and_period_from_filename(self):
        r = find(self.ev["reported"], label="Net revenue", period="Q3 2025", source="board_report_q3.csv#row4")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["value"], 45360.0)
        self.assertFalse(find(self.ev["values"], source="board_report_q3.csv#row4"))

    def test_figure_quoted_in_email(self):
        r = find(self.ev["reported"], label="Net revenue", source="cfo_email.eml#line12")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["value"], 45360.0)
        self.assertLessEqual(self.fid[r[0]["fragment_id"]]["confidence"], 0.6)

    def test_unreadable_row_not_used(self):
        self.assertFalse([x for x in self.ev["values"] if x["source"] == "sales_export.csv#row4"])

    # rules ----------------------------------------------------------------
    def test_cfo_rule(self):
        r = [x for x in self.ev["rules"] if x["text"].startswith("Orders over $5,000 get 10% off")]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["numbers"], [5000.0, 0.10, 0.02])
        self.assertEqual(r[0]["operator_hint"], ">")
        self.assertEqual(r[0]["source"], "cfo_email.eml#line11")
        self.assertEqual(self.fid[r[0]["fragment_id"]]["confidence"], 0.6)
        self.assertEqual(self.fid[r[0]["fragment_id"]]["type"], "clue")

    def test_notes_rules(self):
        tier = [x for x in self.ev["rules"] if "at least $5k" in x["text"]][0]
        self.assertEqual(tier["numbers"], [5000.0, 0.1])
        self.assertEqual(tier["operator_hint"], ">=")
        comm = [x for x in self.ev["rules"] if x["text"].startswith("Commission is 3%")][0]
        self.assertEqual(comm["numbers"], [0.03, 2500.0])
        self.assertEqual(comm["operator_hint"], "<=")
        tax = [x for x in self.ev["rules"] if x["text"].startswith("Sales tax")][0]
        self.assertEqual(tax["numbers"], [0.08])
        self.assertIsNone(tax["operator_hint"])

    def test_code_rules_and_constants(self):
        self.assertTrue([x for x in self.ev["rules"] if x["source"] == "invoicing.py#line6" and x["numbers"] == [0.08]])
        self.assertTrue([f for f in self.fr if f["source_file"] == "invoicing.py" and f["type"] == "clue"
                         and "5000" in f["notes"]])
        self.assertTrue([f for f in self.fr if f["source_file"] == "invoicing.py" and f["type"] == "code"
                         and "invoice_total" in f["notes"]])

    def test_model_assumptions(self):
        r = [x for x in self.ev["rules"] if x["source"] == "model.xlsx#Assumptions!B1"]
        self.assertEqual(r[0]["numbers"], [5000.0])

    # gaps -----------------------------------------------------------------
    def gap(self, pattern):
        return [g for g in self.gaps if re.search(pattern, g["what"])]

    def test_blank_and_ref_gaps(self):
        g = self.gap(r"Model!E4 \(Gross revenue, Q4 2025\) is blank")
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["where_to_look"][-1], "ask the client")
        r = self.gap(r"Model!C6 \(Net revenue, Q2 2025\) shows #REF!")
        self.assertEqual(len(r), 1)

    def test_covered_blank_is_not_a_gap(self):
        self.assertFalse(self.gap(r"Model!D2"))
        self.assertIn("Model!D2 (Units sold, Q3 2025) blank is covered by", self.inv)

    def test_damaged_cells_rank_first(self):
        self.assertRegex(self.gaps[0]["what"], r"^Model!(E4|C6)")
        self.assertRegex(self.gaps[1]["what"], r"^Model!(E4|C6)")

    def test_unreadable_row_gap(self):
        g = self.gap(r"sales_export\.csv#row4 is unreadable \(wrong field count: 4 instead of 5\)")
        self.assertEqual(len(g), 1)

    def test_missing_function_gap(self):
        g = self.gap(r"Function `apply_discount` is called in invoicing\.py")
        self.assertEqual(len(g), 1)
        self.assertTrue(g[0]["where_to_look"][0].startswith("notes.txt"))
        self.assertFalse(self.gap(r"`(line_total|round|sum|open)`"))

    def test_missing_file_gap(self):
        self.assertEqual(len(self.gap(r"forecast_q4\.xlsx is mentioned in notes\.txt")), 1)

    def test_missing_report_periods(self):
        for p in ("Q1 2025", "Q2 2025", "Q4 2025"):
            self.assertEqual(len(self.gap(r"No reported figures for %s$" % p)), 1, p)
        self.assertFalse(self.gap(r"No reported figures for Q3 2025"))

    def test_no_conflict_when_sources_agree(self):
        self.assertFalse(self.gap(r"Conflicting"))

    # safety and inventory --------------------------------------------------
    def test_client_code_never_executed(self):
        for d in (self.case, self.tmp, ROOT, os.getcwd()):
            self.assertFalse(os.path.exists(os.path.join(d, "EXECUTED_BY_SCANNER")), d)

    def test_instruction_like_text_flagged_not_followed(self):
        self.assertTrue([f for f in self.fr if f["source_file"] == "notes.txt" and "instruction-like" in f["notes"]])

    def test_inventory_lists_every_file(self):
        for n in ("model.xlsx", "sales_export.csv", "board_report_q3.csv", "cfo_email.eml", "notes.txt", "invoicing.py"):
            self.assertIn("**%s**" % n, self.inv)
        self.assertIn("## Open gaps", self.inv)

    def test_model_autodetected_without_flag(self):
        out2 = os.path.join(self.tmp, "evidence_auto")
        ev, fr, gaps, inv, _ = run_scan(self.case, "C-0001", out2)
        self.assertEqual([g["what"] for g in gaps], [g["what"] for g in self.gaps])
        self.assertEqual(len(ev["values"]), len(self.ev["values"]))


class MiniCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ctx_mini_")
        cls.case = build_mini_case(os.path.join(cls.tmp, "case"))
        cls.out = os.path.join(cls.tmp, "evidence")
        cls.ev, cls.fr, cls.gaps, cls.inv, _ = run_scan(cls.case, "C-0002", cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gap(self, pattern):
        return [g for g in self.gaps if re.search(pattern, g["what"])]

    def test_long_format_and_sequential_quarters(self):
        v = find(self.ev["values"], label="Units sold", period="Q5")
        self.assertEqual(v[0]["value"], 1200.0)
        self.assertEqual(v[0]["source"], "orders_export.csv#row2")
        self.assertFalse(self.gap(r"Plan!F2"))      # covered by the export

    def test_replacement_character_row(self):
        self.assertEqual(len(self.gap(r"orders_export\.csv#row3 is unreadable \(unreadable characters")), 1)

    def test_missing_sheet(self):
        self.assertEqual(len(self.gap(r"Plan!B5 references sheet 'Inputs'")), 1)

    def test_conflict(self):
        g = self.gap(r"Conflicting figures for Revenue, Q4")
        self.assertEqual(len(g), 1)
        self.assertIn("1350", g[0]["what"])
        self.assertIn("1300", g[0]["what"])

    def test_text_table_and_no_table_rules(self):
        self.assertEqual(find(self.ev["reported"], label="Revenue", period="Q4", source="kpi_summary.txt#line4")[0]["value"], 1350.0)
        self.assertFalse([r for r in self.ev["rules"] if "Line item" in r["text"]])

    def test_pdf(self):
        if not cs.shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        self.assertEqual(find(self.ev["reported"], label="Revenue", period="Q5")[0]["value"], 1400.0)
        r = [x for x in self.ev["rules"] if x["source"].startswith("board_pack_q5.pdf")][0]
        self.assertEqual(r["numbers"], [0.015, 1000.0])
        self.assertEqual(r["operator_hint"], ">")

    def test_yaml_and_json(self):
        y = {r["text"]: r for r in self.ev["rules"] if r["source"].startswith("settings.yml")}
        self.assertEqual(y["pricing.discount_rate: 10%"]["numbers"], [0.1])
        self.assertEqual(y["pricing.large_order_threshold: $5,000"]["numbers"], [5000.0])
        self.assertEqual(y["pricing.max_discount: $750"]["operator_hint"], "<=")
        j = find(self.ev["values"], label="Fees", period="Q4", source="metrics.json#metrics[1]")
        self.assertEqual(j[0]["value"], 13.0)
        self.assertTrue([r for r in self.ev["rules"] if r["source"] == "metrics.json#settings.commission_rate"])

    def test_email_attachment_scanned(self):
        r = find(self.ev["reported"], label="Revenue", period="Q1", source="fwd_board.eml/board_report_q1.csv#row2")
        self.assertEqual(r[0]["value"], 1000.0)
        self.assertFalse(self.gap(r"No reported figures for Q1$"))
        self.assertIn("attachment board_report_q1.csv", self.inv)
        fee = [x for x in self.ev["rules"] if x["source"].startswith("fwd_board.eml#line")]
        self.assertEqual(fee[0]["numbers"], [25.0])

    def test_docx(self):
        r = [x for x in self.ev["rules"] if x["source"].startswith("pricing_policy.docx")]
        self.assertEqual(r[0]["numbers"], [50.0, 500.0])
        self.assertEqual(r[0]["operator_hint"], "<")

    def test_dated_transactions_stay_records(self):
        self.assertFalse([x for x in self.ev["values"] + self.ev["reported"] if x["source"].startswith("transactions.csv")])
        self.assertTrue([f for f in self.fr if f["source_file"] == "transactions.csv" and f["type"] == "record"
                         and "order_id=1001" in f["notes"]])

    def test_git_folder_pointed_out(self):
        self.assertIn("**.git**: git history, not scanned here", self.inv)

    def test_unknown_file_noted(self):
        self.assertIn("**blob.bin**: unrecognised file type", self.inv)

    def test_pdf_without_pdftotext_is_a_clue(self):
        out = os.path.join(self.tmp, "nopdf")
        s = cs.Scan(self.case, "C-0002", None, out)
        s.pdftotext = None
        s.run()
        fr = json.load(open(os.path.join(out, "fragments.json")))
        gaps = json.load(open(os.path.join(out, "gaps.json")))
        self.assertTrue([f for f in fr if f["source_file"] == "board_pack_q5.pdf" and f["type"] == "clue"
                         and "needs reading" in f["notes"]])
        self.assertTrue([g for g in gaps if "board_pack_q5.pdf could not be read" in g["what"]])


class Helpers(unittest.TestCase):
    def test_periods(self):
        P = cs.parse_period
        self.assertEqual(P("Q3"), ("Q", 3, None))
        for s in ("Q3 2025", "2025-Q3", "2025 Q3", "Q3-25", "3Q25", "Q3 FY25", "Q3 2025A"):
            self.assertEqual(P(s), ("Q", 3, 2025), s)
        self.assertEqual(P("Mar 2025"), ("M", 3, 2025))
        self.assertEqual(P("March-25"), ("M", 3, 2025))
        self.assertEqual(P("2025-03"), ("M", 3, 2025))
        self.assertEqual(P("FY2025"), ("Y", None, 2025))
        self.assertEqual(P("FY25"), ("Y", None, 2025))
        self.assertEqual(P("Q5"), ("Q", 5, None))
        self.assertIsNone(P("Net revenue"))
        self.assertIsNone(P("Units sold"))

    def test_period_alignment(self):
        s = cs.Scan(".", "C-0009")
        s.model_periods = [(p, cs.parse_period(p)) for p in ("Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025")]
        self.assertEqual(s.align_period(cs.parse_period("2025-Q3"), "2025-Q3", {})[0], "Q3 2025")
        self.assertEqual(s.align_period(cs.parse_period("Q3"), "Q3", {})[0], "Q3 2025")
        self.assertEqual(s.align_period(cs.parse_period("Q3 2024"), "Q3 2024", {})[1], "unmatched")
        s.model_periods = [(p, cs.parse_period(p)) for p in ("Q1", "Q2", "Q3", "Q4", "Q5")]
        self.assertEqual(s.align_period(cs.parse_period("Q3 2025"), "Q3 2025", {"Q": True})[1], "unmatched")

    def test_label_alignment(self):
        s = cs.Scan(".", "C-0009")
        for l in ("Units sold", "Net revenue", "Gross revenue", "Discount"):
            s.model_labels.append(l)
            s.model_norm.setdefault(cs.norm_label(l), set()).add(l)
            s.model_fuzzy.setdefault(cs.fuzzy_key(l), set()).add(l)
        self.assertEqual(s.align_label("UNITS SOLD"), ("Units sold", "normalized"))
        self.assertEqual(s.align_label("Net Revenue ($)"), ("Net revenue", "normalized"))
        self.assertEqual(s.align_label("Discounts"), ("Discount", "fuzzy"))
        self.assertEqual(s.align_label("Revenue"), ("Revenue", "unmatched"))

    def test_numbers(self):
        N = lambda t: [n[0] for n in cs.extract_numbers(t)]
        self.assertEqual(N("Orders over $5,000 get 10% off"), [5000.0, 0.1])
        self.assertEqual(N("anything above $5k"), [5000.0])
        self.assertEqual(N("a $1.2m cap and 2.5% fee"), [1200000.0, 0.025])
        self.assertEqual(N("In Q3 2025, on Nov 7 at 5:30, call 2026-11-07 ref C-0001"), [])
        self.assertEqual(cs.parse_number("(1,200)"), -1200.0)
        self.assertEqual(cs.parse_number("$48,210.50"), 48210.5)
        self.assertEqual(cs.parse_number("12%"), 0.12)
        self.assertIsNone(cs.parse_number("n/a"))

    def test_operator_hints(self):
        H = cs.operator_hint
        self.assertEqual(H("Orders over $5,000 get 10% off"), ">")
        self.assertEqual(H("Orders above $5,000 get 10% off"), ">")
        self.assertEqual(H("Orders that exceed $5,000 get 10% off"), ">")
        self.assertEqual(H("Orders of at least $5,000 get 10% off"), ">=")
        self.assertEqual(H("Orders of $5,000 or more get 10% off"), ">=")
        self.assertEqual(H("Orders of no less than $5,000 get 10% off"), ">=")
        self.assertEqual(H("A minimum order of $500 gets free shipping fee"), ">=")
        self.assertEqual(H("Orders under $1,000 pay a $20 fee"), "<")
        self.assertEqual(H("Orders below $1,000 pay a $20 fee"), "<")
        self.assertEqual(H("Discounts up to 15% need approval"), "<=")
        self.assertEqual(H("Bonus of no more than $2,000"), "<=")
        self.assertEqual(H("Orders of $1,000 or less pay a $20 fee"), "<=")
        self.assertEqual(H("Under the new policy, orders over $5,000 get 10% off"), ">")
        self.assertIsNone(H("Tax is 8%"))

    def test_rule_needs_keyword_and_number(self):
        self.assertIsNone(cs.rule_from_sentence("We should talk about pricing next week."))
        self.assertIsNone(cs.rule_from_sentence("Shipped 1,200 boxes."))
        self.assertIsNotNone(cs.rule_from_sentence("Orders over $5,000 get 10% off."))


class StackedTables(unittest.TestCase):
    def test_second_table_does_not_create_false_blanks(self):
        from openpyxl import Workbook
        tmp = tempfile.mkdtemp(prefix="ctx_tt_")
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Model"
            for row in (["Line item", "Q1", "Q2", "Q3", "Q4"], ["Revenue", 100, 110, None, 130], ["Costs", 50, 55, 60, 65],
                        [], ["Annual", "FY2024", "FY2025"], ["Revenue", 400, 455], ["Costs", 200, 230]):
                ws.append(row)
            wb.save(os.path.join(tmp, "model.xlsx"))
            ev, fr, gaps, inv, _ = run_scan(tmp, "C-0005", os.path.join(tmp, "ev"))
            blanks = [g["what"] for g in gaps if "is blank" in g["what"]]
            self.assertEqual(blanks, ["Model!D2 (Revenue, Q3) is blank"])
            self.assertIn("FY2025", inv)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SkillFile(unittest.TestCase):
    def test_skill_embeds_current_source_and_it_runs(self):
        s = open(os.path.join(ROOT, "CONTEXT_SKILL.md"), encoding="utf-8").read()
        body = s[s.index("```python\n") + 10: s.rindex("```")]
        self.assertEqual(body, open(SCRIPT, encoding="utf-8").read(), "CONTEXT_SKILL.md is out of date")
        for word in ("agentmail.list_threads", "agentmail.search_threads", "agentmail.get_thread",
                     "agentmail.get_attachment", "cc.py", "send_to_agent", "publish_file", "quarantine"):
            self.assertIn(word, s)
        self.assertNotIn("—", s)
        tmp = tempfile.mkdtemp(prefix="ctx_skill_")
        try:
            p = os.path.join(tmp, "context_scan.py")
            open(p, "w", encoding="utf-8").write(body)
            case = build_case(os.path.join(tmp, "case"))
            r = subprocess.run([sys.executable, p, "--case-dir", case, "--case", "C-0001",
                                "--out-dir", os.path.join(tmp, "ev")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            self.assertTrue(os.path.isfile(os.path.join(tmp, "ev", "evidence.json")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
