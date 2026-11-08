"""End-to-end test: cc.py against the real app code (app/server.js with an in-memory Postgres).

    python3 naive/lib/test_cc.py        (needs node, and `npm install` run once in app/)
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CC = os.path.join(HERE, "cc.py")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class CCEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        env = dict(os.environ, PORT=str(cls.port), CC_API_TOKEN="t0ken")
        env.pop("NEON_DATABASE_URL", None)
        cls.server = subprocess.Popen(["node", "server.js"], cwd=os.path.join(REPO, "app"), env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/health" % cls.port, timeout=1)
                return
            except Exception:
                time.sleep(0.3)
        cls.server.kill()
        raise RuntimeError("server did not start: " + cls.server.stdout.read().decode())

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=10)

    def cc(self, *args, token="t0ken", url=True, extra_env=None):
        env = dict(os.environ, CC_API_TOKEN=token)
        if url:
            env["CC_URL"] = "http://127.0.0.1:%d" % self.port
        else:
            env.pop("CC_URL", None)
        env.update(extra_env or {})
        p = subprocess.run([sys.executable, CC] + list(args), env=env, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def ok(self, *args):
        code, out, err = self.cc(*args)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_whole_case(self):
        self.assertEqual(self.ok("ping")["token_valid"], True)
        row = self.ok("case-new", "--case", "C-0100", "--client-email", "cfo@acme.com", "--kind", "excel", "--quote", "250")
        self.assertEqual(row["stage"], "intake")
        self.ok("case-stage", "--case", "C-0100", "--stage", "forensics")
        self.ok("fragment", "--id", "F-0100-001", "--case", "C-0100", "--source-file", "model.xlsx",
                "--location", "Model!C12", "--type", "record", "--confidence", "0.9", "--by", "forensics")
        self.ok("rule", "--id", "R-0100-01", "--case", "C-0100", "--description", "Revenue = units x price",
                "--evidence", "F-0100-001", "F-0100-002", "--alternatives", '[{"formula_pattern":"x"}]',
                "--status", "reconstructed and tested")
        self.ok("gap", "--id", "G-0100-01", "--case", "C-0100", "--what", "Q2 discount",
                "--where-to-look", "CFO email", "Q3 board report")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"example_id": "S1", "expected": 10, "actual": 11}], f)
        self.ok("verdict", "--case", "C-0100", "--fail", "--results", "@" + f.name, "--retry-count", "1")
        os.unlink(f.name)
        self.ok("report-item", "--case", "C-0100", "--item", "Model!E12", "--label", "unresolved", "--cites", "G-0100-01")
        self.ok("event", "--case", "C-0100", "--agent", "validation", "--stage", "validation",
                "--message", "1 mismatch", "--cost", "0.2", "--human")
        self.ok("checkup", "--team", "Team X", "--high", "2")
        moved = self.ok("case-stage", "--case", "C-0100", "--stage", "reconstruction", "--retry-count", "1")
        self.assertEqual(moved["retry_count"], 1)

        board = json.load(urllib.request.urlopen("http://127.0.0.1:%d/api/board" % self.port))
        case = [c for c in board["cases"] if c["case_id"] == "C-0100"][0]
        self.assertEqual(case["stage"], "reconstruction")
        self.assertAlmostEqual(case["cost"], 0.2)
        self.assertGreaterEqual(board["humans_stepped_in"], 1)
        self.assertEqual(board["latest_verdict"]["case_id"], "C-0100")

    def test_errors_are_readable(self):
        code, _, err = self.cc("case-new", "--case", "C-0101", "--client-email", "a@b.c", "--kind", "excel", token="nope")
        self.assertEqual(code, 1)
        self.assertIn("401", err)
        code, _, err = self.cc("fragment", "--id", "F-x", "--case", "C-9999", "--source-file", "x",
                               "--type", "clue", "--by", "x")
        self.assertEqual(code, 1)
        self.assertIn("does not exist", err)
        code, _, err = self.cc("report-item", "--case", "C-0100", "--item", "x", "--label", "guessed", "--cites", "a")
        self.assertEqual(code, 2)  # argparse rejects labels outside the four

    def test_verdict_outcomes(self):
        self.ok("case-new", "--case", "C-0102", "--client-email", "v@x.io", "--kind", "code")
        row = self.ok("verdict", "--case", "C-0102", "--outcome", "error", "--results", "[]", "--retry-count", "0")
        self.assertEqual((row["pass"], row["outcome"]), (False, "error"))
        row = self.ok("verdict", "--case", "C-0102", "--pass", "--results", "[]", "--retry-count", "1")
        self.assertEqual((row["pass"], row["outcome"]), (True, "pass"))
        code, _, err = self.cc("verdict", "--case", "C-0102", "--pass", "--outcome", "error", "--results", "[]",
                               "--retry-count", "1")
        self.assertEqual(code, 1)
        self.assertIn("contradicts", err)
        code, _, err = self.cc("verdict", "--case", "C-0102", "--results", "[]", "--retry-count", "1")
        self.assertEqual(code, 1)
        self.assertIn("needs --pass", err)

    def test_fallback_without_url(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self.cc("event", "--agent", "context", "--stage", "context", "--cost", "0.05",
                                     url=False, extra_env={"CC_FALLBACK_DIR": d})
            self.assertEqual(code, 0, err)
            with open(os.path.join(d, "events.jsonl")) as f:
                row = json.loads(f.readline())
            self.assertEqual(row["agent"], "context")
            self.assertEqual(row["cost_usd"], 0.05)
            self.assertIn("NOT LOGGED", err)
            self.assertTrue(json.loads(out)["_not_logged"])
            code, _, err = self.cc("event", "--agent", "x", "--stage", "y", url=False,
                                   extra_env={"CC_FALLBACK_DIR": d, "CC_REQUIRE_URL": "1"})
            self.assertEqual(code, 1)
            self.assertIn("NOT LOGGED", err)

    def test_case_get(self):
        self.ok("case-new", "--case", "C-0103", "--client-email", "rm@x.io", "--kind", "excel")
        self.ok("case-stage", "--case", "C-0103", "--stage", "validation", "--retry-count", "2")
        row = self.ok("case-get", "--case", "C-0103")
        self.assertEqual((row["stage"], row["retry_count"]), ("validation", 2))
        code, _, err = self.cc("case-get", "--case", "C-4040")
        self.assertEqual(code, 1)
        self.assertIn("404", err)
        code, _, err = self.cc("case-get", "--case", "C-0103", url=False)
        self.assertEqual(code, 1)
        self.assertIn("needs CC_URL", err)

    def test_retries_then_gives_up(self):
        start = time.time()
        code, _, err = self.cc("ping", extra_env={"CC_URL": "http://127.0.0.1:%d" % free_port()})
        self.assertEqual(code, 1)
        self.assertIn("gave up after 4 attempts", err)
        self.assertGreaterEqual(time.time() - start, 6)  # waited 1 + 2 + 4 seconds between tries


if __name__ == "__main__":
    unittest.main(verbosity=2)
