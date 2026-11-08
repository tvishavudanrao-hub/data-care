"""request_draft.py turns open gaps into exact requests. Run: python3 -m pytest -q (or python3 test_request_draft.py)"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, LIB)
import request_draft  # noqa: E402

DEMO = os.path.abspath(os.path.join(LIB, "..", "..", "..", "..", "eval", "demo"))


def write(d, name, obj):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


CONTEXT_GAPS = [
    {"gap_id": "G-0007-01", "what": "Model!E9 (Cost of goods sold, Q4 2025) is blank",
     "why": "No surviving value", "status": "open",
     "where_to_look": ["the sales or ERP export for Q4 2025",
                       "the client's past email threads with the CFO or finance team (search 'Cost of goods sold Q4 2025')",
                       "ask the client"]},
    {"gap_id": "G-0007-02", "what": "Model!C12 (Rent, Q2 2025) is blank \u2014 password: hunter2", "why": "No value",
     "status": "open", "where_to_look": ["the bank statement for Q2 2025 (rent payments)", "ask the client"]},
    {"gap_id": "G-0007-03", "what": "pricing_2024.xlsx is mentioned in cfo_email.eml (line 12) but is not in the case files",
     "why": "may hold rules", "status": "open",
     "where_to_look": ["the client's past email threads (search 'pricing_2024.xlsx', check attachments)",
                       "the client's shared drive or the folder the case came from", "ask the client"]},
    {"gap_id": "G-0007-04", "what": "Operating expenses, Q1 2026: the client says this figure is not available (cfo.eml#line38)",
     "why": "left blank", "status": "open",
     "where_to_look": ["the client, once the figure exists (they said: \"I do not have Q1 2026 operating expenses.\")"]},
]
ENGINE_GAPS = [
    {"gap_id": "G-0007-51", "what": "Operating expenses for Q1 2026 (Model!F12): I do not have Q1 2026 operating expenses.",
     "why": "it is a raw input the client cannot supply, so it stays blank", "status": "open",
     "where_to_look": ["the client, once the figure exists", "cfo.eml#line38"]},
    {"gap_id": "G-0007-52", "what": "Salaries for Q3 2025 (Model!D15): the input value was lost (cell blank) and no evidence gives it",
     "why": "it is a raw input, so no formula can rebuild it", "status": "open",
     "where_to_look": ["payroll export for Q3 2025", "general ledger (salaries account) for Q3 2025"]},
]
EVIDENCE = {"case_id": "C-0007", "values": [], "reported": [], "rules": [], "known_missing": [
    {"label": "Operating expenses", "period": "Q1 2026", "source": "cfo.eml#line38", "fragment_id": "F-0007-051",
     "source_label": "operating expenses", "text": "I do not have Q1 2026 operating expenses."}]}
RULES = [
    {"rule_id": "R-0007-03", "description": "Volume discount = Gross revenue x Discount rate.", "cells": ["Model!B7:I7"],
     "formula_r1c1": "=R[-2]C*R[-1]C", "status": "reconstructed but untested"},
    {"rule_id": "R-0007-06", "description": "Gross profit = Net revenue - Cost of goods sold.", "cells": ["Model!B10:I10"],
     "formula_r1c1": "=R[-2]C-R[-1]C", "status": "reconstructed and tested"},
    {"rule_id": "R-0007-08", "description": "Operating income = Gross profit - Operating expenses.", "cells": ["Model!B13:I13"],
     "formula_r1c1": "=R[-3]C-R[-1]C", "status": "reconstructed and tested"},
]
ITEMS = [{"item": "Model!E9 (Cost of goods sold, Q4 2025)", "label": "reconstructed but untested", "cites": ["R-0007-05"]},
         {"item": "Model!F12 (Operating expenses, Q1 2026)", "label": "unresolved", "cites": ["F-0007-051", "G-0007-51"]}]
QUESTION = {"rule_id": "R-0007-03", "question": "Does a quarter with exactly 2,500 units get the 10% discount?",
            "options": ["Yes, exactly 2,500 qualifies (>=)", "No, only above 2,500 (>)"], "probe": {}}


class RequestDraft(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="requests_")
        self.rb = os.path.join(self.d, "rebuilt")
        os.makedirs(self.rb)
        write(self.d, "gaps.json", CONTEXT_GAPS)
        write(self.d, "evidence.json", EVIDENCE)
        write(self.rb, "gaps.json", ENGINE_GAPS)
        write(self.rb, "rules.json", RULES)
        write(self.rb, "report_items.json", ITEMS)
        write(self.rb, "question.json", QUESTION)

    def run_tool(self, *extra, out=None):
        out = out or self.rb
        request_draft.main(["--case", "C-0007", "--rebuilt-dir", self.rb, "--evidence", os.path.join(self.d, "evidence.json"),
                            "--client", "Acme Tools", "--client-email", "dana@acme.example", "--contact-name", "Dana",
                            "--out-dir", out] + list(extra))
        with open(os.path.join(out, "requests.json"), encoding="utf-8") as fh:
            reqs = json.load(fh)
        with open(os.path.join(out, "requests.md"), encoding="utf-8") as fh:
            return reqs, fh.read()

    def by_gap(self, reqs, gid):
        return next(e for e in reqs if gid in (e.get("gap_ids") or []) or e.get("rule_id") == gid)

    def test_kinds_and_targets(self):
        reqs, _ = self.run_tool()
        self.assertEqual(self.by_gap(reqs, "G-0007-01")["kind"], "ask_client")
        fwd = self.by_gap(reqs, "G-0007-02")
        self.assertEqual((fwd["kind"], fwd["to"]), ("client_forward", "bank"))
        pay = self.by_gap(reqs, "G-0007-52")
        self.assertEqual((pay["kind"], pay["to"]), ("client_forward", "payroll provider"))
        srch = self.by_gap(reqs, "G-0007-03")
        self.assertEqual((srch["kind"], srch["to"]), ("search_more", "mail-scout"))
        self.assertIn("pricing_2024.xlsx", srch["terms"])
        km = self.by_gap(reqs, "G-0007-04")
        self.assertEqual(km["kind"], "leave_unresolved")
        self.assertEqual(km["gap_ids"], ["G-0007-04", "G-0007-51"])          # Context's and the engine's gap merged
        self.assertIn("I do not have Q1 2026 operating expenses", km["body"])
        self.assertIn("F-0007-051", km["why"])
        q = self.by_gap(reqs, "R-0007-03")
        self.assertEqual(q["kind"], "ask_client")
        self.assertEqual(len({e["request_id"] for e in reqs}), len(reqs))
        self.assertTrue(all(e["request_id"].startswith("Q-0007-") and e["status"] == "draft" and e["round"] == 1
                            for e in reqs))

    def test_wording_is_exact_and_plain(self):
        reqs, md = self.run_tool()
        cogs = self.by_gap(reqs, "G-0007-01")
        self.assertIn("Cost of goods sold for Q4 2025 (cell Model!E9)", cogs["body"])
        self.assertIn("your sales or ERP export for Q4 2025", cogs["body"])
        fwd = self.by_gap(reqs, "G-0007-02")
        self.assertIn("Could you please send me a copy of my bank statement for Q2 2025", fwd["body"])
        self.assertIn("Dana\nAcme Tools", fwd["body"])
        self.assertIn("[your account number]", fwd["body"])
        self.assertTrue(md.startswith("To: dana@acme.example\nSubject: Case C-0007: "))
        self.assertIn("Hi Dana,", md)
        self.assertIn("Option 1: Yes, exactly 2,500 qualifies (>=)", md)
        self.assertIn("Documents you could forward to us", md)
        self.assertIn("we never contact them for you", md)
        self.assertNotIn("pricing_2024", md)                  # searches are tasks for our agents, not the client
        self.assertNotIn("Operating expenses for Q1 2026", md)
        for text in (md, json.dumps(reqs, ensure_ascii=False)):
            self.assertNotIn("\u2014", text)
            self.assertNotIn("hunter2", text)

    def test_most_blocking_first_and_at_most_five(self):
        many = list(CONTEXT_GAPS) + [
            {"gap_id": "G-0007-%02d" % n, "what": "Model!%s3 (Units sold, Q%d 2026) is blank" % ("BCDEFG"[n - 10], n - 9),
             "why": "x", "status": "open", "where_to_look": ["the sales or ERP export", "ask the client"]}
            for n in range(10, 16)]
        write(self.d, "gaps.json", many)
        reqs, md = self.run_tool()
        mail = [e for e in reqs if e.get("batch") == 1]
        self.assertEqual(len(mail), 5)
        self.assertEqual(mail[0].get("rule_id"), "R-0007-03")          # the question blocks a whole row (8 cells)
        self.assertEqual(mail[1]["gap_id"], "G-0007-01")               # COGS: itself and the gross profit cell
        self.assertTrue(all(mail[i]["blocks"] >= mail[i + 1]["blocks"] for i in range(4)))
        self.assertTrue(any(e.get("batch") == 2 for e in reqs))
        self.assertEqual(md.count("\n1. ") + md.count("\n2. ") + md.count("\n3. ") + md.count("\n4. ") +
                         md.count("\n5. ") + md.count("\nA. ") + md.count("\nB. "), 5)
        self.assertNotIn("\n6. ", md)

    def test_round_two_repeats_then_round_three_closes(self):
        reqs1, _ = self.run_tool()
        prev = os.path.join(self.d, "round1.json")
        write(self.d, "round1.json", reqs1)
        out2 = os.path.join(self.d, "r2")
        reqs2, md2 = self.run_tool("--previous", prev, out=out2)
        cogs1, cogs2 = self.by_gap(reqs1, "G-0007-01"), self.by_gap(reqs2, "G-0007-01")
        self.assertEqual(cogs2["request_id"], cogs1["request_id"])       # same item keeps its id
        self.assertEqual((cogs2["round"], cogs2["repeat"]), (2, True))
        self.assertTrue(cogs2["subject"].startswith("Second request: "))
        self.assertIn("still missing", md2)
        srch2 = self.by_gap(reqs2, "G-0007-03")                           # searched in round 1: now ask the client
        self.assertEqual((srch2["kind"], srch2["repeat"]), ("ask_client", False))
        self.assertEqual(self.by_gap(reqs2, "G-0007-02")["kind"], "client_forward")
        # --round 2 without --previous marks every ask as a repeat
        reqs2b, _ = self.run_tool("--round", "2", out=os.path.join(self.d, "r2b"))
        self.assertTrue(self.by_gap(reqs2b, "G-0007-01")["repeat"])
        # after round 2: everything still open is left unresolved with the places searched
        write(self.d, "round2.json", reqs2)
        reqs3, md3 = self.run_tool("--previous", os.path.join(self.d, "round2.json"), out=os.path.join(self.d, "r3"))
        self.assertTrue(all(e["kind"] == "leave_unresolved" for e in reqs3))
        cogs3 = self.by_gap(reqs3, "G-0007-01")
        self.assertTrue(cogs3["why"].startswith("searched: the case files; "))
        self.assertIn("the client's past email threads", cogs3["why"])
        self.assertIn("asked the client", cogs3["why"])
        self.assertTrue(md3.startswith("No email this round"))

    def test_found_items_are_closed_and_resolved_gaps_skipped(self):
        reqs1, _ = self.run_tool()
        write(self.d, "round1.json", reqs1)
        write(self.d, "gaps.json", [g for g in CONTEXT_GAPS if g["gap_id"] != "G-0007-01"])
        write(self.rb, "report_items.json", ITEMS[1:] + [
            {"item": "Model!E9 (Cost of goods sold, Q4 2025)", "label": "recovered", "cites": ["F-0007-099"]}])
        reqs2, md2 = self.run_tool("--previous", os.path.join(self.d, "round1.json"), out=os.path.join(self.d, "r2"))
        cogs = self.by_gap(reqs2, "G-0007-01")
        self.assertEqual(cogs["status"], "found")
        self.assertNotIn("Cost of goods sold", md2)
        # a Context gap whose cell the rebuild recovered gets no request at all
        write(self.d, "gaps.json", CONTEXT_GAPS)
        reqs3, _ = self.run_tool(out=os.path.join(self.d, "r3"))
        self.assertFalse(any("G-0007-01" in e["gap_ids"] for e in reqs3))

    def test_figures_built_on_a_missing_one_are_not_asked(self):
        gaps = list(CONTEXT_GAPS) + [{"gap_id": "G-0007-05", "what": "Model!F13 (Operating income, Q1 2026) is blank",
                                      "why": "x", "status": "open", "where_to_look": ["the board report for Q1 2026"]}]
        write(self.d, "gaps.json", gaps)
        reqs, md = self.run_tool()
        oi = self.by_gap(reqs, "G-0007-05")
        self.assertEqual(oi["kind"], "leave_unresolved")
        self.assertIn("Operating expenses for Q1 2026", oi["why"])
        self.assertNotIn("Operating income", md)

    def test_money_movement_gap(self):
        write(self.d, "recon.json", {"gaps": [{"gap_id": "G-0007-91", "date": "2026-03-18", "amount": "73.29",
                                               "description": "AMAZON MKTPLACE", "status": "open", "search_hints": [
            "if still missing: ask the client to request a duplicate receipt from AMAZON MKTPLACE (needs human approval)"]}]})
        reqs, md = self.run_tool("--gaps", os.path.join(self.d, "recon.json"))
        e = self.by_gap(reqs, "G-0007-91")
        self.assertEqual((e["kind"], e["to"]), ("client_forward", "vendor"))
        self.assertIn("for the payment of $73.29 on March 18, 2026", e["body"])


@unittest.skipUnless(os.path.exists(os.path.join(DEMO, "excel_a", "evidence.json")), "demo cases not present")
class DemoCases(unittest.TestCase):
    def test_demo_cases_draft_cleanly(self):
        for case in ("excel_a", "excel_b"):
            d = os.path.join(DEMO, case)
            wb = next(f for f in os.listdir(d) if f.endswith("_damaged.xlsx"))
            out = tempfile.mkdtemp(prefix="rq_" + case)
            subprocess.run([sys.executable, os.path.join(LIB, "formula_infer.py"), "--workbook", os.path.join(d, wb),
                            "--evidence", os.path.join(d, "evidence.json"), "--case", "C-0101", "--out-dir", out],
                           check=True, capture_output=True)
            request_draft.main(["--case", "C-0101", "--rebuilt-dir", out, "--evidence", os.path.join(d, "evidence.json"),
                                "--out-dir", out])
            reqs = json.load(open(os.path.join(out, "requests.json"), encoding="utf-8"))
            md = open(os.path.join(out, "requests.md"), encoding="utf-8").read()
            km = [e for e in reqs if e["kind"] == "leave_unresolved" and "G-0101-51" in e["gap_ids"]]
            self.assertEqual(len(km), 1)                                     # the known-missing opex figure
            # Q1 2025 growth (B14) has no prior quarter: the rebuild keeps it empty, so nobody is asked for it
            self.assertFalse(any("B14" in json.dumps(e) for e in reqs if e["kind"] != "leave_unresolved"))
            self.assertNotIn("B14", md)
            if case == "excel_a":                                            # COGS Q4 2025 is rebuilt but untested
                self.assertTrue(any(e["kind"] == "ask_client" and "E9" in json.dumps(e) for e in reqs))
            self.assertNotIn("\u2014", md)
            self.assertLessEqual(sum(1 for e in reqs if e.get("batch") == 1), 5)


if __name__ == "__main__":
    unittest.main()
