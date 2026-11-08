import json
import os
import tempfile
import unittest

import forensics_checkup as fc


def make_repo(files):
    d = tempfile.mkdtemp()
    root = os.path.join(d, "repo")
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(content)
    return root, os.path.join(d, "out")


class CheckupTests(unittest.TestCase):
    def test_reads_requirements_and_package_json(self):
        root, _ = make_repo({"requirements.txt": b"flask==1.0.2\nrequests>=2\n",
                             "web/package.json": json.dumps({"dependencies": {"lodash": "^4.17.4", "x": "latest"}}).encode()})
        deps = fc.read_deps(root)
        names = sorted((d["ecosystem"], d["name"], d["version"]) for d in deps)
        self.assertEqual(names, [("PyPI", "flask", "1.0.2"), ("npm", "lodash", "4.17.4")])
        self.assertEqual(len(fc.osv_query(deps)["queries"]), 2)

    def test_osv_response_becomes_high_finding(self):
        root, out = make_repo({"requirements.txt": b"flask==1.0.2\n"})
        resp = {"results": [{"vulns": [{"id": "GHSA-test-0001"}]}]}
        counts = fc.run("C-0002", root, out, "Team X", "https://example.test/r", resp)
        self.assertEqual(counts["high"], 1)
        with open(os.path.join(out, "checkup_report.md")) as fh:
            self.assertIn("GHSA-test-0001", fh.read())

    def test_scan_is_recursive_and_secret_value_not_in_outputs(self):
        root, out = make_repo({"src/app/conf.txt": b"a\npassword = s3cretvalue99\n",
                               ".git/config": b"ignored"})
        counts = fc.run("C-0002", root, out, "Team X", "")
        self.assertEqual(counts["medium"], 1)
        for fn in os.listdir(out):
            p = os.path.join(out, fn)
            if os.path.isfile(p):
                with open(p) as fh:
                    self.assertNotIn("s3cretvalue99", fh.read())
        self.assertTrue(os.path.exists(os.path.join(out, "working", "src", "app", "conf.txt")))
        self.assertFalse(os.path.exists(os.path.join(out, "working", ".git")))

    def test_cc_commands_include_checkup_row(self):
        root, out = make_repo({"a.csv": b"a,b\n1,2\n"})
        fc.run("C-0002", root, out, "Team X", "https://example.test/r")
        with open(os.path.join(out, "cc_commands.txt")) as fh:
            text = fh.read()
        self.assertIn("python3 cc.py checkup --case C-0002", text)
        self.assertIn("--high 0 --medium 0 --low 0", text)


if __name__ == "__main__":
    unittest.main()
