"""sync_records.py end to end: a fake Naive CLI (vetta) that serves a local folder laid out like the Naive file library,
a fake Data Care app that checks x-cc-token and the app's field rules (app/src/db.js), and Andrei's real cc.py between.

    python3 -m pytest -q tests/sync        cc.py is found next to sync_records.py (data-care repo), or set CC_PY=/path/cc.py
    DATACARE_APP=/path/to/data-care/app    also runs the demo case against the real app (node server.js, in-memory db)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", ".."))
SYNC = os.path.join(LIB, "sync_records.py")
FORMULA_INFER = os.path.join(LIB, "formula_infer.py")
DEMO = os.path.abspath(os.path.join(LIB, "..", "..", "..", "..", "eval", "demo", "excel_a"))
TOKEN = "t0ken-for-tests-only"


def find_cc():
    for p in (os.environ.get("CC_PY"), os.path.join(LIB, "cc.py"), os.path.expanduser("~/data-care/naive/lib/cc.py")):
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return None


def find_app():
    for p in (os.environ.get("DATACARE_APP"), os.path.join(LIB, "..", "..", "app"), os.path.expanduser("~/data-care/app")):
        if p and os.path.isfile(os.path.join(p, "server.js")) and \
                os.path.isdir(os.path.join(p, "node_modules", "@electric-sql", "pglite")) and shutil.which("node"):
            return os.path.abspath(p)
    return None


CC = find_cc()
NO_CC = "cc.py not found: set CC_PY=/path/to/cc.py (in the data-care repo it sits next to sync_records.py)"

# ---------------------------------------------------------------- fake Data Care app (mirrors app/src/db.js)
STAGES = ("intake", "forensics", "context", "reconstruction", "waiting_client", "validation", "approval", "delivered",
          "unresolved")
LABELS = ("recovered", "reconstructed and tested", "reconstructed but untested", "unresolved")
TABLES = {  # primary key, columns agents may send, required columns
    "cases": ("case_id", ("case_id", "client_email", "kind", "stage", "retry_count", "quote_usd"),
              ("case_id", "client_email", "kind")),
    "fragments": ("fragment_id", ("fragment_id", "case_id", "source_file", "location", "type", "confidence", "notes",
                                  "created_by"), ("fragment_id", "case_id", "source_file", "type", "created_by")),
    "rules": ("rule_id", ("rule_id", "case_id", "description", "evidence", "alternatives", "status"),
              ("rule_id", "case_id", "description", "evidence", "status")),
    "gaps": ("gap_id", ("gap_id", "case_id", "what", "why", "where_to_look", "status"), ("gap_id", "case_id", "what")),
    "verdicts": (None, ("case_id", "pass", "results", "retry_count", "outcome"), ("case_id", "pass", "results",
                                                                                 "retry_count")),
    "report_items": (None, ("case_id", "item", "label", "cites"), ("case_id", "item", "label", "cites")),
    "events": (None, ("case_id", "agent", "stage", "message", "cost_usd", "human_stepped_in"), ("agent", "stage")),
    "checkups": (None, ("case_id", "team", "repo_url", "high", "medium", "low"), ()),
}
CHECKS = {("cases", "kind"): ("excel", "code", "checkup", "other"), ("cases", "stage"): STAGES,
          ("fragments", "type"): ("code", "record", "clue"), ("rules", "status"): LABELS[1:],
          ("gaps", "status"): ("open", "found", "requested", "unresolved"), ("report_items", "label"): LABELS,
          ("verdicts", "outcome"): ("pass", "fail", "error", "untested")}


class FakeApp:
    def __init__(self):
        self.rows = {t: {} for t, spec in TABLES.items() if spec[0]}
        self.lists = {t: [] for t, spec in TABLES.items() if not spec[0]}
        self.requests = []
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _go(self, method):
                n = int(self.headers.get("content-length") or 0)
                code, obj = app.handle(method, self.path, self.headers, self.rfile.read(n) if n else None)
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_PATCH(self):
                self._go("PATCH")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def writes(self):
        return [r for r in self.requests if r["method"] in ("POST", "PATCH")]

    def handle(self, method, path, headers, raw):
        token_ok = headers.get("x-cc-token") == TOKEN
        try:
            body = json.loads(raw.decode()) if raw else None
        except ValueError:
            body = "<not json>"
        self.requests.append({"method": method, "path": path, "body": body, "token_ok": token_ok})
        if method == "GET":
            if path == "/api/health":
                return 200, {"ok": True, "db": True, "token_valid": token_ok}
            if path == "/api/board":
                return 200, {"cases": [dict(c) for c in self.rows["cases"].values()], "stages": list(STAGES)}
            return 404, {"error": "not found"}
        if not token_ok:
            return 401, {"error": "missing or wrong x-cc-token"}
        if not isinstance(body, dict):
            return 400, {"error": "body must be a JSON object"}
        parts = [p for p in path.split("/") if p]
        if method == "POST" and len(parts) == 2 and parts[1] in TABLES:
            return self.insert(parts[1], body)
        if method == "PATCH" and len(parts) == 3 and parts[1] == "cases":
            return self.patch(urllib.parse.unquote(parts[2]), body)
        return 404, {"error": "no route for %s %s" % (method, path)}

    def insert(self, table, body):
        pk, cols, required = TABLES[table]
        unknown = [k for k in body if k not in cols]
        if unknown:
            return 400, {"error": "unknown field(s) for %s: %s" % (table, ", ".join(unknown))}
        missing = [k for k in required if body.get(k) in (None, "")]
        if missing:
            return 400, {"error": "missing field(s) for %s: %s" % (table, ", ".join(missing))}
        for k in ("evidence", "where_to_look", "cites"):
            if body.get(k) is not None and not isinstance(body[k], list):
                return 400, {"error": "%s: expected a list of strings" % k}
        for (t, k), allowed in CHECKS.items():
            if t == table and body.get(k) is not None and body[k] not in allowed:
                return 400, {"error": "a value is not allowed: %s_%s_check" % (t, k)}
        if table != "cases" and body.get("case_id") is not None and body["case_id"] not in self.rows["cases"]:
            return 400, {"error": "that case_id does not exist yet; open it with case-new first"}
        row = {k: v for k, v in body.items() if v is not None}
        if pk:
            old = self.rows[table].get(row[pk], {"stage": "intake", "retry_count": 0} if table == "cases" else {})
            row = dict(old, **row)
            self.rows[table][row[pk]] = row
        else:
            self.lists[table].append(row)
        return 201, row

    def patch(self, case, body):
        bad = [k for k in body if k not in ("stage", "retry_count", "quote_usd")]
        if bad:
            return 400, {"error": "only stage, retry_count and quote_usd can be patched (got %s)" % ", ".join(bad)}
        if case not in self.rows["cases"]:
            return 404, {"error": "case %s not found" % case}
        if body.get("stage") is not None and body["stage"] not in STAGES:
            return 400, {"error": "stage must be one of: " + ", ".join(STAGES)}
        self.rows["cases"][case].update({k: v for k, v in body.items() if v is not None})
        return 200, self.rows["cases"][case]


# ---------------------------------------------------------------- fake Naive CLI and file library
FAKE_VETTA = r'''#!%(python)s
import hashlib, json, os, sys
root = os.environ["FAKE_NAIVE_ROOT"]
args = sys.argv[1:]
with open(os.path.join(root, ".calls"), "a") as f:
    f.write(json.dumps({"argv": args, "token_seen": "CC_API_TOKEN" in os.environ}) + "\n")
busy = os.path.join(root, ".busy")
if os.path.exists(busy):
    n = int(open(busy).read().strip() or 0)
    if n > 0:
        open(busy, "w").write(str(n - 1))
        sys.stderr.write("Error: rate_limited: the service is at capacity\n")
        sys.exit(1)

def copies(folder):
    """Every copy in a folder, newest first: the current files, then .old/<n>/ (a higher n is newer)."""
    d, out = os.path.join(root, folder), []
    if not os.path.isdir(d):
        return out
    out += [(n, os.path.join(d, n)) for n in sorted(os.listdir(d)) if not n.startswith(".")]
    old = os.path.join(d, ".old")
    for v in (sorted(os.listdir(old), reverse=True) if os.path.isdir(old) else []):
        out += [(n, os.path.join(old, v, n)) for n in sorted(os.listdir(os.path.join(old, v)))]
    return out

def fid(path):
    with open(path, "rb") as f:
        return "fil_" + hashlib.sha256(path.encode() + b"\0" + f.read()).hexdigest()[:20]

def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default

if args[:2] == ["file", "list"]:
    folder, search = opt("--folder"), opt("--search")
    items = [{"id": fid(p), "name": n, "folder": folder} for n, p in copies(folder) if not search or search in n]
    if opt("--order", "desc") == "asc":
        items.reverse()
    print(json.dumps({"data": items[:int(opt("--limit", "50"))]}))
elif args[:2] == ["file", "download"] and len(args) == 3:
    for folder in os.listdir(root):
        for n, p in (copies(folder) if not folder.startswith(".") else []):
            if fid(p) == args[2]:
                with open(p, "rb") as f:
                    sys.stdout.buffer.write(f.read())
                sys.exit(0)
    sys.stderr.write("Error: file not found\n")
    sys.exit(1)
else:
    sys.stderr.write("fake vetta: unsupported command %%s\n" %% args)
    sys.exit(2)
'''


class Library:
    """A local folder laid out like the Naive file library. put() on an existing name keeps the old copy as older."""

    def __init__(self, root):
        self.root, self.n = root, 0
        os.makedirs(root)

    def put(self, folder, name, data):
        d = os.path.join(self.root, folder)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        if os.path.exists(p):
            self.n += 1
            old = os.path.join(d, ".old", "%04d" % self.n)
            os.makedirs(old)
            shutil.move(p, os.path.join(old, name))
        if not isinstance(data, (bytes, str)):
            data = json.dumps(data, indent=1)
        with open(p, "wb") as f:
            f.write(data.encode() if isinstance(data, str) else data)

    def get(self, folder, name):
        with open(os.path.join(self.root, folder, name), encoding="utf-8") as f:
            return json.load(f)

    def calls(self):
        p = os.path.join(self.root, ".calls")
        if not os.path.exists(p):
            return []
        with open(p) as f:
            return [json.loads(line) for line in f if line.strip()]


def small_case(lib, case="C-0101"):
    """A case shaped like the real outputs: Context's evidence files, Reconstruction's rebuilt files."""
    n = case[2:]
    lib.put(case + "-evidence", "evidence.json", {"case_id": case, "values": [], "reported": [], "rules": []})
    lib.put(case + "-evidence", "fragments.json", [
        {"fragment_id": "F-%s-%03d" % (n, i), "source_file": "model.xlsx", "location": "Model!B%d" % i,
         "type": "record", "confidence": 0.9, "notes": "value %d" % i} for i in range(1, 6)])
    lib.put(case + "-evidence", "gaps.json", [
        {"gap_id": "G-%s-%02d" % (n, i), "what": "Model!F%d is blank" % i, "why": "no export has it",
         "where_to_look": ["the client's CFO email", "the Q3 board report"], "status": "open"} for i in (1, 2)])
    lib.put(case + "-rebuilt", "rules.json", [
        {"rule_id": "R-%s-%02d" % (n, i), "description": "Row %d = units x price." % i, "cells": ["Model!B%d:I%d" % (i, i)],
         "formula_pattern": "=B3*B4", "evidence": ["Model!B%d" % i, "F-%s-001" % n],
         "alternatives": [{"formula_pattern": "=B3*B4*0.9", "differs_when": "a discount applies"}],
         "status": "reconstructed and tested"} for i in (1, 2, 3)])
    lib.put(case + "-rebuilt", "gaps.json", [{"gap_id": "G-%s-51" % n, "what": "Operating expenses Q1 2026",
                                             "why": "the client cannot supply it", "where_to_look": ["the client"],
                                             "status": "open"}])
    lib.put(case + "-rebuilt", "report_items.json", [{"item": "Model!B3", "label": "recovered", "cites": ["F-%s-001" % n]},
                                                    {"item": "Model!B5:I5", "label": "reconstructed and tested",
                                                     "cites": ["R-%s-01" % n]}])
    lib.put(case + "-rebuilt", "summary.json", {"status": "done", "counts": {}, "formulas_rebuilt": 3, "questions": 0})
    return {"fragments": 5, "gaps": 3, "rules": 3}


def demo_case(lib):
    """The Alderbank demo (C-0101): Context's real outputs and Reconstruction's from formula_infer.py, when this
    checkout has them; otherwise a smaller case of the same shape."""
    need = ("evidence.json", "fragments.json", "gaps.json", "alderbank_model_damaged.xlsx")
    if not (os.path.isfile(FORMULA_INFER) and all(os.path.isfile(os.path.join(DEMO, n)) for n in need)):
        return small_case(lib)
    for n in need[:3]:
        with open(os.path.join(DEMO, n), "rb") as f:
            lib.put("C-0101-evidence", n, f.read())
    out = tempfile.mkdtemp(prefix="sync-demo-")
    try:
        subprocess.run([sys.executable, FORMULA_INFER, "--workbook", os.path.join(DEMO, need[3]), "--evidence",
                        os.path.join(DEMO, "evidence.json"), "--case", "C-0101", "--out-dir", out],
                       check=True, capture_output=True, timeout=300)
        for n in sorted(os.listdir(out)):
            with open(os.path.join(out, n), "rb") as f:
                lib.put("C-0101-rebuilt", n, f.read())
    finally:
        shutil.rmtree(out, True)
    return {"fragments": len(lib.get("C-0101-evidence", "fragments.json")),
            "gaps": len(lib.get("C-0101-evidence", "gaps.json")) + len(lib.get("C-0101-rebuilt", "gaps.json")),
            "rules": len(lib.get("C-0101-rebuilt", "rules.json"))}


def index_row(case="C-0101", **kw):
    return dict({"case_id": case, "client_email": "cfo@alderbank.example", "kind": "excel", "stage": "context",
                 "retry_count": 0}, **kw)


def feedback(vid, outcome, next_action, items=(), case="C-0101", retry=0):
    """Validation's validation_feedback.json (verify/schema.py to_feedback): case_id is its dataset, job_id the case."""
    return {"verdict_id": vid, "job_id": case, "case_id": "excel_a", "artifact_id": case + "-rebuilt/model.xlsx",
            "artifact_version": "attempt-%d" % (retry + 1), "attempt": retry + 1, "retry_count": retry,
            "max_retries": 3, "outcome": outcome, "verdict": "pass" if outcome == "pass" else "fail",
            "next_action": next_action, "reasons": [], "checks": {"run": 12, "failed": 0 if outcome == "pass" else 2},
            "items": [{"item_id": i, "label": label, "status": "pass", "failed_checks": 0, "failed_check_tags": []}
                      for i, label in items]}


def table_of(req):
    parts = [p for p in req["path"].split("/") if p]
    return parts[1]


class _Base(unittest.TestCase):
    """Fixtures for the tests below; no tests of its own."""
    maxDiff = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sync-test-")
        self.lib = Library(os.path.join(self.tmp, "naive"))
        self.vetta = os.path.join(self.tmp, "bin", "vetta")
        os.makedirs(os.path.dirname(self.vetta))
        with open(self.vetta, "w") as f:
            f.write(FAKE_VETTA % {"python": sys.executable})
        os.chmod(self.vetta, 0o755)
        self.state = os.path.join(self.tmp, "home", ".datacare-sync-state.json")
        self.app = FakeApp()

    def tearDown(self):
        self.app.close()
        shutil.rmtree(self.tmp, True)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CC_")}
        env.update(FAKE_NAIVE_ROOT=self.lib.root, CC_URL=self.app.url, CC_API_TOKEN=TOKEN,
                   DATACARE_SYNC_BACKOFF="0.01", NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
                   PATH=os.path.dirname(self.vetta) + os.pathsep + os.environ.get("PATH", ""))
        for k, v in extra.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def sync(self, *args, cc=True, **env):
        argv = [sys.executable, SYNC, "--cli", self.vetta, "--state", self.state] + (["--cc", CC] if cc else [])
        p = subprocess.run(argv + list(args), env=self.env(**env), capture_output=True, text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr

    def ok(self, *args, **env):
        rc, out = self.sync(*args, **env)
        self.assertEqual(rc, 0, out)
        self.assertNotIn(TOKEN, out)
        return out

    def index(self, *rows):
        self.lib.put("case-index", "index.json", {"cases": list(rows)})


@unittest.skipIf(CC is None, NO_CC)
class SyncTest(_Base):
    def test_demo_case_first_run_sends_everything_and_rerun_sends_nothing(self):
        expect = demo_case(self.lib)
        self.index(index_row())
        self.lib.put("C-0101-evidence", "events_context.json", [
            {"agent": "context", "stage": "context", "message": "scan done", "cost_usd": 0.12, "human": False}])
        self.lib.put("C-0101-rebuilt", "events_reconstruction.json", [
            {"agent": "reconstruction", "stage": "reconstruction", "message": "formulas rebuilt", "cost_usd": 0.4,
             "human": False}])
        out = self.ok("--from-index")
        app = self.app
        case = app.rows["cases"]["C-0101"]
        self.assertEqual((case["client_email"], case["kind"], case["stage"]),
                         ("cfo@alderbank.example", "excel", "reconstruction"))
        self.assertEqual(len(app.rows["fragments"]), expect["fragments"])
        self.assertEqual(len(app.rows["gaps"]), expect["gaps"])
        self.assertEqual(len(app.rows["rules"]), expect["rules"])
        self.assertEqual(app.lists["report_items"], [])  # Reconstruction's report_items.json is never logged
        self.assertEqual(app.lists["verdicts"], [])
        self.assertEqual(sorted(e["agent"] for e in app.lists["events"]), ["context", "reconstruction"])
        self.assertEqual({f["created_by"] for f in app.rows["fragments"].values()}, {"context"})
        self.assertTrue(all(r["token_ok"] for r in app.writes()))
        self.assertIn("C-0101: case created; stage intake -> reconstruction; %d fragments, %d gaps, %d rules, 2 events "
                      "sent; 0 failed" % (expect["fragments"], expect["gaps"], expect["rules"]), out)
        order = ["cases", "fragments", "gaps", "rules", "verdicts", "report_items", "events"]
        tables = [table_of(r) for r in app.writes()]
        self.assertEqual(tables, sorted(tables, key=order.index))  # cases first, events last
        self.assertFalse(any(c["token_seen"] for c in self.lib.calls()))  # the Naive CLI never gets the token

        writes, calls = len(app.writes()), len(self.lib.calls())
        out = self.ok("--from-index")
        self.assertEqual(len(app.writes()), writes)
        self.assertIn("C-0101: nothing new; 0 failed", out)
        downloads = [c for c in self.lib.calls()[calls:] if c["argv"][:2] == ["file", "download"]]
        self.assertEqual(len(downloads), 1, downloads)  # only case-index/index.json; the case files are known

    def test_changed_record_is_resent(self):
        small_case(self.lib)
        self.index(index_row())
        self.ok("--case", "C-0101")
        writes = len(self.app.writes())
        frags = self.lib.get("C-0101-evidence", "fragments.json")
        frags[1]["notes"] = "corrected by Context"
        self.lib.put("C-0101-evidence", "fragments.json", frags)  # a newer copy; the old one stays in the library
        out = self.ok("--case", "C-0101")
        new = self.app.writes()[writes:]
        self.assertEqual([(r["path"], r["body"]["fragment_id"]) for r in new], [("/api/fragments", "F-0101-002")])
        self.assertEqual(self.app.rows["fragments"]["F-0101-002"]["notes"], "corrected by Context")
        self.assertIn("C-0101: 1 fragment sent; 0 failed", out)

    def test_ownership_by_file_and_id_range(self):
        self.index(index_row(stage=None))
        ev, rb, inc = "C-0101-evidence", "C-0101-rebuilt", "C-0101-incoming"
        frag = {"source_file": "model.xlsx", "type": "clue", "confidence": 0.5}
        gap = {"what": "a gap", "status": "open"}
        rule = {"description": "x", "evidence": ["Model!B5"], "status": "reconstructed and tested"}
        self.lib.put(ev, "fragments.json", [dict(frag, fragment_id="F-0101-001"), dict(frag, fragment_id="F-0101-950"),
                                            dict(frag, fragment_id="F-0102-003")])
        self.lib.put(ev, "forensics_fragments.json", [dict(frag, fragment_id="F-0101-901"),
                                                      dict(frag, fragment_id="F-0101-002")])
        self.lib.put(ev, "gaps.json", [dict(gap, gap_id="G-0101-01"), dict(gap, gap_id="G-0101-60")])
        self.lib.put(ev, "rules.json", [dict(rule, rule_id="R-0101-09")])  # rules only come from -rebuilt
        self.lib.put(rb, "fragments.json", [dict(frag, fragment_id="F-0101-500")])  # fragments only from -evidence
        self.lib.put(rb, "gaps.json", [dict(gap, gap_id="G-0101-51"), dict(gap, gap_id="G-0101-02")])
        self.lib.put(rb, "rules.json", [dict(rule, rule_id="R-0101-01")])
        self.lib.put(rb, "report_items.json", [{"item": "Model!B3", "label": "recovered", "cites": ["F-0101-001"]}])
        self.lib.put(inc, "events_client.json", [{"agent": "x", "stage": "y"}])  # client files are never read
        self.lib.put(inc, "fragments.jsonl", json.dumps(dict(frag, fragment_id="F-0101-003", case_id="C-0101",
                                                             created_by="x")) + "\n")
        out = self.ok("--from-index")
        rows = self.app.rows
        self.assertEqual({k: v["created_by"] for k, v in rows["fragments"].items()},
                         {"F-0101-001": "context", "F-0101-901": "forensics"})
        self.assertEqual(sorted(rows["gaps"]), ["G-0101-01", "G-0101-51"])
        self.assertEqual(sorted(rows["rules"]), ["R-0101-01"])
        self.assertEqual((self.app.lists["report_items"], self.app.lists["events"]), ([], []))
        for text in ("F-0101-950 is outside Context's range F-0101-001 to 899", "F-0102-003 belongs to C-0102",
                     "F-0101-002 is outside Forensics' range F-0101-901 to 999", "G-0101-60 is outside Context's range",
                     "G-0101-02 is outside Reconstruction's range G-0101-51 to 89"):
            self.assertIn(text, out)
        self.assertNotIn("incoming", out)

    def test_verdicts_and_report_items_come_only_from_validation(self):
        small_case(self.lib)
        rp = "C-0101-report"
        self.lib.put(rp, "report_draft.md", "# draft")
        self.lib.put(rp, "verdict.json", feedback("vrd_other", "pass", "x", case="C-0999"))  # another case's verdict
        self.lib.put(rp, "validation_feedback.json", feedback(
            "vrd_1", "fail", "return_to_rebuild_via_recovery_manager", [("Model row 5: Gross revenue", "unresolved")]))
        out = self.ok("--case", "C-0101", "--client-email", "cfo@alderbank.example", "--kind", "excel")
        verdicts = self.app.lists["verdicts"]
        self.assertEqual([(v["outcome"], v["pass"], v["retry_count"]) for v in verdicts], [("fail", False, 0)])
        res = verdicts[0]["results"][0]
        self.assertEqual((res["verdict_id"], res["expected"], res["checks_failed"]),
                         ("vrd_1", "withheld (private to Validation)", 2))
        self.assertEqual(self.app.lists["report_items"], [])  # not final yet: back to Reconstruction
        self.assertEqual(self.app.rows["cases"]["C-0101"]["stage"], "validation")
        self.assertIn("verdict.json skipped: it is for C-0999", out)

        items = [("surviving inputs", "recovered"), ("Model row 5: Gross revenue", "reconstructed and tested"),
                 ("Model!F12", "unresolved")]
        self.lib.put(rp, "validation_feedback.json", feedback("vrd_2", "pass", "send_to_deliverable_via_recovery_manager",
                                                              items, retry=1))
        out = self.ok("--case", "C-0101")
        self.assertEqual([v["outcome"] for v in self.app.lists["verdicts"]], ["fail", "pass"])
        self.assertEqual(sorted((r["item"], r["label"], tuple(r["cites"])) for r in self.app.lists["report_items"]),
                         sorted((i, l, (i,)) for i, l in items))
        self.assertIn("C-0101: 1 verdict, 3 report items sent; 0 failed", out)
        self.assertNotIn("Model!B3", json.dumps(self.app.lists["report_items"]))  # Reconstruction's items stay out

    def test_case_created_when_missing_and_stage_only_moves_forward(self):
        self.lib.put("C-0101-evidence", "fragments.json", [{"fragment_id": "F-0101-001", "source_file": "a.csv",
                                                            "type": "record"}])
        out = self.ok("--case", "C-0101", "--case", "C-0102")
        self.assertNotIn("C-0101", self.app.rows["cases"])
        self.assertIn("C-0101: not in the app yet, and case-index/index.json has no client email for it", out)
        self.assertEqual(self.app.writes(), [])

        self.index(index_row(stage="forensics", kind="excel", client_email="cfo@alderbank.example"))
        out = self.ok("--case", "C-0101")
        self.assertEqual(self.app.rows["cases"]["C-0101"]["stage"], "context")  # the files say Context has run
        self.assertIn("C-0101: case created; stage intake -> context; 1 fragment sent; 0 failed", out)

        self.app.rows["cases"]["C-0101"]["stage"] = "validation"  # the case has moved on
        small_case(self.lib)
        writes = len(self.app.writes())
        self.index(index_row(stage="reconstruction", retry_count=1))  # a retry: the stage does not go back
        out = self.ok("--case", "C-0101")
        patches = [r["body"] for r in self.app.writes()[writes:] if r["method"] == "PATCH"]
        self.assertEqual(patches, [{"retry_count": 1}])
        self.assertEqual(self.app.rows["cases"]["C-0101"]["stage"], "validation")
        self.assertIn("retry_count 0 -> 1", out)

        self.index(index_row(stage="approval", retry_count=1))
        self.ok("--case", "C-0101")
        self.assertEqual(self.app.rows["cases"]["C-0101"]["stage"], "approval")

    def test_malformed_files_are_skipped_and_reported_once(self):
        self.index(index_row())
        ev, rb, rp = "C-0101-evidence", "C-0101-rebuilt", "C-0101-report"
        self.lib.put(ev, "fragments.json", "{not json")
        self.lib.put(ev, "gaps.json", ["not an object", {"gap_id": "G-0101-01", "what": "a gap"}, {"gap_id": "G-0101-02"}])
        self.lib.put(rb, "rules.json", {"rules": "not a list"})
        self.lib.put(rb, "events_reconstruction.json", "[1, 2")
        self.lib.put(rp, "validation_feedback.json", "[]")
        self.lib.put(rp, "events.jsonl", "nope\n" + json.dumps({"case_id": "C-0101", "agent": "validation",
                                                               "stage": "validation", "cost_usd": 0.2}) + "\n")
        self.lib.put(rp, "notes.jsonl", "{}\n")
        out = self.ok("--from-index")
        self.assertEqual(sorted(self.app.rows["gaps"]), ["G-0101-01"])
        self.assertEqual(len(self.app.lists["events"]), 1)
        for text in ("C-0101-evidence/fragments.json skipped: not valid JSON",
                     "C-0101-evidence/gaps.json: 2 records skipped (an entry that is not an object; G-0101-02 has no what)",
                     "C-0101-rebuilt/rules.json skipped: expected a JSON list",
                     "C-0101-rebuilt/events_reconstruction.json skipped: not valid JSON",
                     "C-0101-report/validation_feedback.json skipped: not a JSON object",
                     "C-0101-report/events.jsonl: 1 record skipped (line 1 is not JSON)",
                     "C-0101-report/notes.jsonl skipped: not one of cc.py's tables"):
            self.assertIn(text, out)
        out = self.ok("--from-index")
        self.assertIn("C-0101: nothing new; 0 failed", out)
        self.assertNotIn("skipped", out)

    def test_missing_env_vars_and_wrong_token(self):
        self.index(index_row())
        small_case(self.lib)
        for missing in ("CC_URL", "CC_API_TOKEN"):
            rc, out = self.sync("--from-index", **{missing: None})
            self.assertEqual(rc, 2, out)
            self.assertIn("%s is not set in this terminal" % missing, out)
            self.assertIn("Nothing was sent", out)
        self.assertEqual(self.app.requests, [])
        self.assertEqual(self.lib.calls(), [])
        rc, out = self.sync("--from-index", CC_API_TOKEN="wrong-secret-value")
        self.assertEqual(rc, 1, out)
        self.assertIn("does not accept CC_API_TOKEN", out)
        self.assertNotIn("wrong-secret-value", out)
        self.assertEqual(self.app.writes(), [])

    def test_dry_run_prints_and_changes_nothing(self):
        small_case(self.lib)
        self.index(index_row())
        self.lib.put("C-0101-evidence", "events_context.json", [{"agent": "context", "stage": "context",
                                                                 "cost_usd": 0.1}])
        out = self.ok("--from-index", "--dry-run")
        self.assertIn("C-0101 (dry run): would create the case (client c***@alderbank.example, kind excel); would "
                      "move stage intake -> reconstruction; would send 5 fragments, 3 gaps, 3 rules, 1 event", out)
        self.assertIn("would send fragments: F-0101-001, F-0101-002, F-0101-003, F-0101-004, F-0101-005", out)
        self.assertEqual(self.app.writes(), [])
        self.assertFalse(os.path.exists(self.state))
        out = self.ok("--from-index", "--dry-run", cc=False, CC_URL=None, CC_API_TOKEN=None)
        self.assertIn("C-0101 (dry run): case and stage not checked; would send 5 fragments", out)
        self.assertFalse(os.path.exists(self.state))

    def test_events_are_logged_once_each(self):
        self.index(index_row(stage=None))
        e1 = {"agent": "context", "stage": "context", "message": "scan done", "cost_usd": 0.12, "human": False}
        e2 = {"agent": "context", "stage": "context", "message": "asked a person", "cost_usd": 0.05, "human": True}
        self.lib.put("C-0101-evidence", "events_context.json", [e1])  # Context's first publish...
        self.lib.put("C-0101-evidence", "events_context.json", [e1, e2, e2])  # ...repeated in its last; e2 twice is two
        self.lib.put("C-0101-rebuilt", "events_reconstruction.json", {"events": [
            {"agent": "reconstruction", "stage": "reconstruction", "message": "rebuilt", "cost_usd": "0.40"}]})
        self.lib.put("C-0101-report", "events_validation.json", [{"agent": "validation", "stage": "validation",
                                                                  "message": "pass", "cost_usd": 0.3},
                                                                 dict(e1, case_id="C-0999")])
        out = self.ok("--from-index")
        ev = self.app.lists["events"]
        self.assertEqual([(e["agent"], e.get("message"), e["cost_usd"], e["human_stepped_in"]) for e in ev], [
            ("context", "scan done", 0.12, False), ("context", "asked a person", 0.05, True),
            ("context", "asked a person", 0.05, True), ("reconstruction", "rebuilt", 0.4, False),
            ("validation", "pass", 0.3, False)])
        self.assertTrue(all(e["case_id"] == "C-0101" for e in ev))
        self.assertIn("an event for C-0999", out)
        self.ok("--from-index")
        self.assertEqual(len(self.app.lists["events"]), 5)
        e4 = dict(e1, message="second scan", cost_usd=0.2)
        self.lib.put("C-0101-evidence", "events_context.json", [e1, e2, e2, e4])  # Context ran again
        out = self.ok("--from-index")
        self.assertEqual([e.get("message") for e in self.app.lists["events"][5:]], ["second scan"])
        self.assertIn("C-0101: 1 event sent; 0 failed", out)

    def test_cc_fallback_jsonl_files_are_replayed(self):
        small_case(self.lib)
        self.index(index_row(stage=None))
        fb = os.path.join(self.tmp, "cc_records")
        env = self.env(CC_URL=None, CC_FALLBACK_DIR=fb)
        for args in (["event", "--case", "C-0101", "--agent", "validation", "--stage", "validation", "--message",
                      "attempt 1: pass", "--cost", "0.3"],
                     ["verdict", "--case", "C-0101", "--pass", "--retry-count", "0", "--results",
                      '[{"example_id": "_outcome", "verdict_id": "vrd_9", "expected": "withheld", "actual": "withheld"}]'],
                     ["report-item", "--case", "C-0101", "--item", "Model row 5", "--label", "reconstructed and tested",
                      "--cites", "R-0101-01"],
                     ["case-stage", "--case", "C-0101", "--stage", "validation"],
                     ["case-stage", "--case", "C-0101", "--stage", "context"],
                     ["fragment", "--id", "F-0101-001", "--case", "C-0101", "--source-file", "x", "--type", "clue",
                      "--by", "forensics"],
                     ["fragment", "--id", "F-0101-950", "--case", "C-0101", "--source-file", "x", "--type", "clue",
                      "--by", "forensics"],
                     ["event", "--case", "C-0999", "--agent", "x", "--stage", "y"]):
            subprocess.run([sys.executable, CC] + args, env=env, check=True, capture_output=True)
        for name in sorted(os.listdir(fb)):
            with open(os.path.join(fb, name), "rb") as f:
                self.lib.put("C-0101-evidence" if name == "fragments.jsonl" else "C-0101-report", name, f.read())
        self.lib.put("C-0101-report", "validation_feedback.json", feedback(
            "vrd_9", "pass", "send_to_deliverable_via_recovery_manager", [("Model row 5", "reconstructed and tested")]))
        out = self.ok("--from-index")
        app = self.app
        self.assertEqual([(v["pass"], v["results"][0]["verdict_id"]) for v in app.lists["verdicts"]], [(True, "vrd_9")])
        self.assertEqual([(r["item"], r["cites"]) for r in app.lists["report_items"]], [("Model row 5", ["R-0101-01"])])
        self.assertEqual([(e["agent"], e["cost_usd"]) for e in app.lists["events"]], [("validation", 0.3)])
        self.assertEqual(app.rows["fragments"]["F-0101-001"]["created_by"], "context")  # Context's file wins
        self.assertEqual(app.rows["fragments"]["F-0101-950"]["created_by"], "forensics")
        self.assertEqual(app.rows["cases"]["C-0101"]["stage"], "validation")  # the later "context" is not a step back
        self.assertFalse(any("_logged_at" in json.dumps(r["body"]) for r in app.writes()))
        self.assertIn("line 1 (F-0101-001) also comes from the agent's fragments file, which wins", out)
        self.assertIn("line 2 is for C-0999", out)
        self.assertIn("0 failed", out)
        writes = len(app.writes())
        self.assertIn("C-0101: nothing new; 0 failed", self.ok("--from-index"))
        self.assertEqual(len(app.writes()), writes)

    def test_naive_busy_is_retried(self):
        small_case(self.lib)
        self.index(index_row())
        with open(os.path.join(self.lib.root, ".busy"), "w") as f:
            f.write("2")
        out = self.ok("--from-index")
        self.assertIn("Naive is busy, trying again", out)
        self.assertEqual(len(self.app.rows["fragments"]), 5)

    def test_index_shapes(self):
        self.lib.put("case-index", "index.json", {
            "updated_at": "2026-11-08T09:00:00Z",
            "cases": {"C-0101": {"client": {"name": "Alderbank", "email": "cfo@alderbank.example"},
                                 "asset_type": "excel", "stage": "context"},
                      "C-0102": {"client": "Brightline", "kind": "code"}, "c-0103": "waiting_client", "junk": 5}})
        out = self.ok("--from-index")
        cases = self.app.rows["cases"]
        self.assertEqual({k: (v["client_email"], v["kind"], v["stage"]) for k, v in cases.items()},
                         {"C-0101": ("cfo@alderbank.example", "excel", "context"),
                          "C-0102": ("Brightline", "code", "intake")})
        self.assertIn("C-0103: not in the app yet, and case-index/index.json has no client email", out)
        self.assertIn("case-index/index.json: 1 entry skipped", out)
        self.lib.put("case-index", "index.json", [{"case_id": "C-0104", "client_email": "a@b.example", "kind": "other"},
                                                  "garbage", {"case_id": "../etc"}])
        out = self.ok("--from-index")
        self.assertIn("C-0104", self.app.rows["cases"])
        self.assertIn("2 entries skipped", out)

    def test_cc_naive_is_the_newest_in_the_tools_folder(self):
        small_case(self.lib)
        self.index(index_row())
        self.lib.put("tools", "cc.py", "raise SystemExit('an old copy')\n")
        with open(CC, "rb") as f:
            self.lib.put("tools", "cc.py", f.read())
        self.lib.put("tools", "formula_infer.py", "# not cc.py\n")
        out = self.ok("--from-index", "--cc", "naive", cc=False)
        self.assertIn("C-0101: case created", out)
        self.assertEqual(len(self.app.rows["rules"]), 3)
        self.lib.put("tools", "cc.py", "print('hello')\n")
        rc, out = self.sync("--from-index", "--cc", "naive", cc=False)
        self.assertEqual(rc, 2, out)
        self.assertIn("does not look like Andrei's cc.py", out)

    def test_default_cc_is_the_copy_next_to_the_script_never_the_naive_one(self):
        small_case(self.lib)
        self.index(index_row())
        self.lib.put("tools", "cc.py", "print('a swapped copy')\n")      # never run unless --cc naive
        d = tempfile.mkdtemp(prefix="sync_copy_")
        script = os.path.join(d, "sync_records.py")
        shutil.copy(SYNC, script)
        run = lambda: subprocess.run([sys.executable, script, "--cli", self.vetta, "--state", self.state, "--from-index"],
                                     env=self.env(), capture_output=True, text=True, timeout=600)
        p = run()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("cc.py not found next to sync_records.py", p.stdout + p.stderr)
        self.assertEqual(self.app.writes(), [])
        shutil.copy(CC, os.path.join(d, "cc.py"))
        p = run()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("C-0101: case created", p.stdout + p.stderr)

    def test_sync_once_is_importable_and_never_raises(self):
        small_case(self.lib)
        self.index(index_row())
        sys.path.insert(0, LIB)
        bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            import sync_records
        finally:
            sys.path.remove(LIB)
            sys.dont_write_bytecode = bytecode
        saved = dict(os.environ)
        lines = []
        try:
            os.environ.update(self.env())
            s = sync_records.sync_once(from_index=True, cc=CC, cli=self.vetta, state=self.state, log=lines.append)
            self.assertTrue(s["ok"], lines)
            self.assertEqual((s["sent"], s["failed"]), (11, 0))
            self.assertEqual(s["cases"]["C-0101"]["sent"], {"fragments": 5, "gaps": 3, "rules": 3})
            self.assertIn("case created", s["cases"]["C-0101"]["notes"])
            self.assertTrue(any(line.startswith("C-0101: case created") for line in lines))
            lines[:] = []
            s = sync_records.sync_once(from_index=True, cc=CC, cli=self.vetta, state=self.state, quiet=True,
                                       log=lines.append)
            self.assertEqual((s["ok"], s["sent"], lines), (True, 0, []))
            del os.environ["CC_API_TOKEN"]
            s = sync_records.sync_once(from_index=True, cc=CC, cli=self.vetta, state=self.state, log=None)
            self.assertEqual((s["ok"], s["error_kind"]), (False, "setup"))
            self.assertIn("CC_API_TOKEN is not set", s["error"])
        finally:
            os.environ.clear()
            os.environ.update(saved)


APP = find_app()


@unittest.skipIf(CC is None, NO_CC)
@unittest.skipIf(APP is None, "the Data Care app was not found: set DATACARE_APP=/path/to/data-care/app (after npm install)")
class RealAppTest(_Base):
    """The demo case against the real app (app/server.js on an in-memory Postgres), so every record shape is checked
    by the app's own SQL and constraints."""

    def setUp(self):
        _Base.setUp(self)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        env = dict(os.environ, PORT=str(port), CC_API_TOKEN=TOKEN)
        env.pop("NEON_DATABASE_URL", None)
        self.node = subprocess.Popen(["node", "server.js"], cwd=APP, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        self.url = "http://127.0.0.1:%d" % port
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                urllib.request.urlopen(self.url + "/api/health", timeout=1)
                return
            except Exception:
                time.sleep(0.3)
        self.node.kill()
        raise RuntimeError("the app did not start: " + self.node.stdout.read().decode())

    def tearDown(self):
        self.node.terminate()
        self.node.wait(timeout=10)
        _Base.tearDown(self)

    def env(self, **extra):
        return _Base.env(self, **dict({"CC_URL": self.url}, **extra))

    def test_demo_case_on_the_real_app(self):
        expect = demo_case(self.lib)
        self.index(index_row())
        self.lib.put("C-0101-evidence", "events_context.json", [{"agent": "context", "stage": "context",
                                                                 "message": "scan done", "cost_usd": 0.12}])
        self.lib.put("C-0101-report", "validation_feedback.json", feedback(
            "vrd_1", "pass", "send_to_deliverable_via_recovery_manager",
            [("surviving inputs", "recovered"), ("Model row 5: Gross revenue", "reconstructed and tested"),
             ("Model!F12", "unresolved")]))
        out = self.ok("--from-index")
        self.assertIn("C-0101: case created; stage intake -> validation; %d fragments, %d gaps, %d rules, 1 verdict, "
                      "3 report items, 1 event sent; 0 failed" % (expect["fragments"], expect["gaps"], expect["rules"]),
                      out)
        board = json.load(urllib.request.urlopen(self.url + "/api/board", timeout=10))
        case = [c for c in board["cases"] if c["case_id"] == "C-0101"][0]
        self.assertEqual((case["stage"], case["kind"]), ("validation", "excel"))
        self.assertAlmostEqual(case["cost"], 0.12)
        self.assertEqual(board["labels"], {"recovered": 1, "reconstructed and tested": 1, "unresolved": 1})
        self.assertEqual((board["latest_verdict"]["outcome"], board["latest_verdict"]["pass"]), ("pass", True))
        self.assertIn("C-0101: nothing new; 0 failed", self.ok("--from-index"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
