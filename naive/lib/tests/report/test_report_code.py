"""report_draft.py on a code case (rules.json, modification_log.json, backtest.json). Run: python3 -m pytest -q"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, LIB)
import report_draft  # noqa: E402


def write(d, name, obj):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


class CodeReport(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="report_code_")
        write(self.d, "rules.json", [{"rule_id": "R-0009-01", "description": "Discount = tier rate + bonus, capped at 10%",
                                      "evidence": ["F-0009-001"], "alternatives": ["Bonus multiplies: fails 3"],
                                      "status": "reconstructed and tested"}])
        write(self.d, "modification_log.json", [
            {"change_id": "M-1", "file": "billing.py", "lines": "1-20, 31-40", "kind": "restored", "rule_id": None},
            {"change_id": "M-2", "file": "billing.py", "lines": "21-30", "kind": "reconstructed", "rule_id": "R-0009-01"}])
        write(self.d, "backtest.json", {"script": "rebuilt/billing.py", "rows_checked": 12, "passed": 12, "failed": 0,
                                        "unreadable_rows": [5], "unreadable": [{"row": 5, "id": "INV-7", "reason": "unreadable characters (U+FFFD)"}]})
        write(self.d, "gaps.json", [{"gap_id": "G-0009-01", "what": "invoices.csv row 5 is unreadable: password: hunter2", "status": "open"}])

    def test_code_report(self):
        text = report_draft.draft_code(self.d, "C-0009", client="Acme")
        self.assertIn("module billing.py", text)
        self.assertIn("tested the rebuilt code against 12 past invoices: every one matches to the cent", text)
        self.assertIn("billing.py, lines 1-20, 31-40", text)
        self.assertIn("(billing.py lines 21-30): rebuilt and checked", text)
        self.assertIn("**INV-7** (row 5)", text)
        self.assertIn("## Left unresolved", text)
        self.assertIn("no questions for you", text)
        self.assertIn("## What the labels mean", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("—", text)

    def test_cli_picks_code_mode_and_lists_question(self):
        write(self.d, "question.json", {"question": "Is it A or B?", "options": ["A", "B"]})
        out = os.path.join(self.d, "r.md")
        subprocess.run([sys.executable, os.path.join(LIB, "report_draft.py"), "--rebuilt-dir", self.d, "--case", "C-0009",
                        "--out", out], check=True, capture_output=True)
        text = open(out, encoding="utf-8").read()
        self.assertIn("**Question:** Is it A or B?", text)
        self.assertIn("Option 2: B", text)


if __name__ == "__main__":
    unittest.main()
