"""report_draft.py turns formula_infer.py outputs into a plain client report. Run: python3 -m pytest -q"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import report_draft  # noqa: E402


def write(d, name, obj):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


class ReportDraft(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="report_")
        write(self.d, "summary.json", {"status": "done", "formulas_rebuilt": 3, "questions": 0, "case_id": "C-0007",
                                       "counts": {"recovered": 4, "reconstructed and tested": 2,
                                                  "reconstructed but untested": 1, "unresolved": 1}})
        write(self.d, "rules.json", [{"rule_id": "R-0007-01", "description": "Gross revenue = Units x Price.",
                                      "cells": ["Model!B5:E5"], "status": "reconstructed and tested"}])
        write(self.d, "report_items.json", [
            {"item": "Model!B3:E3 (Units, Q1-Q4)", "label": "recovered", "cites": ["Model!B3:E3"]},
            {"item": "Model!E12 (Opex, Q4)", "label": "unresolved", "cites": ["G-0007-51"]}])
        write(self.d, "gaps.json", [{"gap_id": "G-0007-51", "what": "Opex for Q4 (Model!E12): password: hunter2 was in a note",
                                     "why": "no source", "where_to_look": ["the client"], "status": "open"}])
        write(self.d, "question.json", None)

    def test_report_reads_plainly(self):
        text = report_draft.draft(self.d, "C-0007", client="Acme Tools")
        self.assertIn("# Data Care recovery report: Acme Tools", text)
        self.assertIn("We rebuilt 3 formulas", text)
        self.assertIn("**Opex for Q4 (Model!E12)**", text)
        self.assertIn("Gross revenue = Units x Price (Model!B5:E5): rebuilt and checked", text)
        self.assertIn("Units, Q1-Q4 (Model!B3:E3)", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("—", text)

    def test_question_is_listed(self):
        write(self.d, "question.json", {"rule_id": "R-0007-02", "question": "Does exactly 2,500 units get 10%?",
                                        "options": ["No, only above", "Yes, exactly 2,500 qualifies"]})
        text = report_draft.draft(self.d, "C-0007")
        self.assertIn("**Question:** Does exactly 2,500 units get 10%?", text)
        self.assertIn("Option 2: Yes, exactly 2,500 qualifies", text)


if __name__ == "__main__":
    unittest.main()
