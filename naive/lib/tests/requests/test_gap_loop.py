"""Gap loop: an input is missing -> Context opens a gap -> request_draft asks the client -> the client's reply (.eml)
arrives -> Context and the formula engine run again -> the gap is closed, the value recovered and cited.
Uses the real scripts via subprocess and openpyxl to build the small model (dev only). Run: python3 -m pytest -q"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", ".."))
CONTEXT_SCAN = os.environ.get("CONTEXT_SCAN") or os.path.join(LIB, "context", "context_scan.py")
CASE = "C-0042"
UNITS = [1180.0, 1325.0, None, 1410.0]          # Q3 2025 units were lost with the whole Q3 column
PRICE = [19.5, 19.5, 21.0, 21.0]
REPLY_UNITS = 1290.0


def build_model(path):
    wb = openpyxl.Workbook()
    m = wb.active
    m.title = "Model"
    m["A1"] = "Quarterly sales model"
    m["A2"] = "Line item"
    for i, p in enumerate(["Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"]):
        m.cell(2, i + 2, p)
    m["A3"], m["A4"], m["A5"], m["A6"], m["A7"] = "Units sold", "Price per unit", "Gross revenue", "Rent", "Headcount"
    for i in range(4):
        m.cell(3, i + 2, UNITS[i])
        m.cell(4, i + 2, PRICE[i])
        m.cell(5, i + 2, None if UNITS[i] is None else round(UNITS[i] * PRICE[i], 2))   # formulas pasted as values
        m.cell(6, i + 2, 4200.0)                    # inputs that survived, so the Q3 column reads as damaged,
        m.cell(7, i + 2, 6.0 + i)                   # not as a column left empty on purpose
    wb.save(path)


REPLY = """From: Dana Reyes <dana@client.example>
To: codecare-recover@agentmail.to
Date: Sat, 07 Nov 2026 21:40:00 +0000
Subject: Re: Case C-0042: items we need to finish your recovery

Hi,

Here is the number you asked for, from our order system.

Units sold Q3 2025: 1,290

Thanks,
Dana
"""


def run(*args):
    r = subprocess.run([sys.executable] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("%s failed:\n%s\n%s" % (args[0], r.stdout, r.stderr))
    return r.stdout


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class GapLoop(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="gaploop_")
        self.case = os.path.join(self.d, "incoming")
        os.makedirs(self.case)
        self.model = os.path.join(self.case, "model.xlsx")
        build_model(self.model)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def pipeline(self, tag, previous=None):
        ev, rb = os.path.join(self.d, "evidence_" + tag), os.path.join(self.d, "rebuilt_" + tag)
        run(CONTEXT_SCAN, "--case-dir", self.case, "--case", CASE,
            "--model", self.model, "--out-dir", ev)
        run(os.path.join(LIB, "formula_infer.py"), "--workbook", self.model, "--evidence",
            os.path.join(ev, "evidence.json"), "--case", CASE, "--out-dir", rb)
        args = [os.path.join(LIB, "request_draft.py"), "--case", CASE, "--rebuilt-dir", rb, "--evidence",
                os.path.join(ev, "evidence.json"), "--contact-name", "Dana", "--out-dir", rb]
        if previous:
            args += ["--previous", previous]
        run(*args)
        return ev, rb

    def test_reply_closes_the_gap(self):
        cell = "Model!D3"
        # 1. before the reply: the gap is open and the client is asked for exactly that figure
        ev1, rb1 = self.pipeline("1")
        ctx1 = load(os.path.join(ev1, "gaps.json"))
        self.assertTrue(any(g["what"].startswith(cell + " (Units sold, Q3 2025)") for g in ctx1))
        items1 = {i["item"]: i for i in load(os.path.join(rb1, "report_items.json"))}
        self.assertEqual(items1[cell + " (Units sold, Q3 2025)"]["label"], "unresolved")
        reqs1 = load(os.path.join(rb1, "requests.json"))
        ask = next(e for e in reqs1 if e.get("item", {}).get("cell") == cell)
        self.assertEqual((ask["kind"], ask["to"], ask.get("batch")), ("ask_client", "client", 1))
        self.assertIn("Units sold for Q3 2025 (cell Model!D3)", ask["body"])
        with open(os.path.join(rb1, "requests.md"), encoding="utf-8") as fh:
            self.assertIn("Units sold for Q3 2025 (cell Model!D3)", fh.read())

        # 2. the client's reply lands in the case (the Mail Scout saves it to <case>-incoming)
        with open(os.path.join(self.case, "mail_reply_1.eml"), "w", encoding="utf-8") as fh:
            fh.write(REPLY)
        ev2, rb2 = self.pipeline("2", previous=os.path.join(rb1, "requests.json"))

        # 3. the gap is closed: no open gap for the cell, the value is recovered and cites the reply
        self.assertFalse(any(cell in g["what"] for g in load(os.path.join(ev2, "gaps.json"))))
        self.assertFalse(any(cell in g["what"] for g in load(os.path.join(rb2, "gaps.json"))))
        evd = load(os.path.join(ev2, "evidence.json"))
        val = next(v for v in evd["values"] if v["label"] == "Units sold" and v["period"] == "Q3 2025")
        self.assertEqual(val["value"], REPLY_UNITS)
        self.assertTrue(val["source"].startswith("mail_reply_1.eml#line"))
        item = next(i for i in load(os.path.join(rb2, "report_items.json")) if i["item"].startswith(cell + " "))
        self.assertEqual(item["label"], "recovered")
        self.assertIn(val["fragment_id"], item["cites"])
        # the revenue cell rebuilt on it now computes from the client's figure
        rev = next(i for i in load(os.path.join(rb2, "report_items.json")) if i["item"].startswith("Model!D5 "))
        self.assertIn(rev["label"], ("reconstructed and tested", "reconstructed but untested"))
        # 4. the request is marked found, keeps its id, and the next email does not ask for it again
        reqs2 = load(os.path.join(rb2, "requests.json"))
        done = next(e for e in reqs2 if e["request_id"] == ask["request_id"])
        self.assertEqual(done["status"], "found")
        with open(os.path.join(rb2, "requests.md"), encoding="utf-8") as fh:
            self.assertNotIn("Units sold for Q3 2025", fh.read())


if __name__ == "__main__":
    unittest.main()
