"""Secrets in a client's files must never reach evidence.json, fragments.json, gaps.json or inventory.md."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "context_scan.py")
SECRETS = ["hunter22pass", "sk_live_abcdefgh12345678", "AKIAABCDEFGHIJKLMNOP", "ghp_abcdefghijklmnopqrstuvwxyz0123"]


class Redaction(unittest.TestCase):
    def test_no_secret_in_any_output(self):
        case = tempfile.mkdtemp(prefix="ctx_case_")
        out = tempfile.mkdtemp(prefix="ctx_out_")
        with open(os.path.join(case, "settings.yml"), "w") as fh:
            fh.write("discount_rate: 0.10\nthreshold: 5000\npassword: hunter22pass\napi_key: sk_live_abcdefgh12345678\n")
        with open(os.path.join(case, "notes.txt"), "w") as fh:
            fh.write("Orders over $5,000 get 10% off.\nThe old key AKIAABCDEFGHIJKLMNOP and ghp_abcdefghijklmnopqrstuvwxyz0123 were rotated.\n")
        with open(os.path.join(case, "export.csv"), "w") as fh:
            fh.write("quarter,units_sold,token\nQ1 2025,942,sk_live_abcdefgh12345678\n")
        p = subprocess.run([sys.executable, SCRIPT, "--case-dir", case, "--case", "C-0042", "--out-dir", out],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        blob = ""
        for name in ("evidence.json", "fragments.json", "gaps.json", "inventory.md"):
            with open(os.path.join(out, name), encoding="utf-8") as fh:
                blob += fh.read()
        for secret in SECRETS:
            self.assertNotIn(secret, blob)
        ev = json.load(open(os.path.join(out, "evidence.json"), encoding="utf-8"))
        self.assertTrue(any(0.10 in r.get("numbers", []) for r in ev["rules"]), "real rules must survive redaction")


if __name__ == "__main__":
    unittest.main()
