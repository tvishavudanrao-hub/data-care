"""Context keeps its ids inside its contract ranges: fragments 001-899, gaps 01-49."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import context_scan  # noqa: E402


def run(case_dir, out):
    context_scan.main(["--case-dir", case_dir, "--case", "C-0042", "--out-dir", out])
    load = lambda n: json.load(open(os.path.join(out, n), encoding="utf-8"))
    return load("fragments.json"), load("gaps.json"), load("evidence.json")


class IdCaps(unittest.TestCase):
    def setUp(self):
        self.saved = context_scan.FRAG_CAP, context_scan.GAP_CAP
        self.d = tempfile.mkdtemp(prefix="caps_")
        os.makedirs(os.path.join(self.d, "case"))
        with open(os.path.join(self.d, "case", "export.csv"), "w", encoding="utf-8") as fh:
            fh.write("period,units_sold,list_price,revenue\n")
            for y in range(2015, 2027):
                for q in range(1, 5):
                    fh.write("Q%d %d,%d,%d.50,%d\n" % (q, y, 1000 + q * 7 + y, 20 + q, 30000 + q * 11 + y))
        for n in range(12):
            with open(os.path.join(self.d, "case", "note_%02d.md" % n), "w", encoding="utf-8") as fh:
                fh.write("See the attached appendix_%02d.xlsx for the figures.\n" % n)

    def tearDown(self):
        context_scan.FRAG_CAP, context_scan.GAP_CAP = self.saved

    def test_fragment_ids_stop_at_the_cap_and_citations_stay_valid(self):
        context_scan.FRAG_CAP = 10
        frags, gaps, ev = run(os.path.join(self.d, "case"), os.path.join(self.d, "out1"))
        ids = [f["fragment_id"] for f in frags]
        self.assertEqual(len(ids), 10)
        self.assertEqual(ids[-1], "F-0042-010")
        self.assertIn("Fragment ids are full", frags[-1]["notes"])
        self.assertNotIn("_more", frags[-1])
        cited = {v["fragment_id"] for v in ev["values"] + ev["reported"]}
        self.assertTrue(cited <= set(ids))                      # every citation points at a real fragment
        self.assertTrue(all("#" in v["source"] for v in ev["values"]))   # and keeps its own file and line

    def test_gap_ids_stop_at_the_cap(self):
        context_scan.GAP_CAP = 5
        frags, gaps, ev = run(os.path.join(self.d, "case"), os.path.join(self.d, "out2"))
        self.assertEqual(len(gaps), 5)                          # 12 gaps found, 4 kept + 1 summary
        self.assertEqual(gaps[-1]["gap_id"], "G-0042-05")
        self.assertIn("8 more gaps", gaps[-1]["what"])


if __name__ == "__main__":
    unittest.main()
