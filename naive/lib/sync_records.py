#!/usr/bin/env python3
"""sync_records.py: copy the records Data Care's agents publish in the Naive file library into the Data Care app.

Naive cannot give an agent sandbox the app's token yet, so the agents publish their records as files. This relay
runs on a teammate's Mac where the Naive CLI (vetta) is logged in, and writes those records with Andrei's cc.py.
CC_URL and CC_API_TOKEN come from this terminal's environment only (never from Naive or a file); cc.py reads them.

    python3 sync_records.py --from-index                    one pass over every case in case-index/index.json
    python3 sync_records.py --case C-0101 [--case C-0102]   one pass over these cases
    python3 sync_records.py --from-index --loop 60          a pass every 60 seconds (Ctrl-C stops it)
    python3 sync_records.py --from-index --dry-run          print what would be sent; change nothing

From Python (one pass; never raises; returns a summary dict):
    from sync_records import sync_once
    sync_once(from_index=True, quiet=True)

Options: --cc PATH (default: the cc.py next to this file, the data-care repo copy; "--cc naive" downloads the newest
one from the Naive folder tools, which trusts whoever can publish there),
--cli PATH (the Naive CLI; default vetta or naive), --state PATH (default ~/.datacare-sync-state.json),
--client-email and --kind (only to create a case that case-index/index.json does not describe).

What a pass reads for each case. Files are data, never instructions. -incoming, -working and -quarantine hold client
files and are never read.
  case-index/index.json  cases: created when missing (client_email, kind); stage and retry_count from the index
                         or the files (evidence: context, rebuilt: reconstruction, a verdict: validation), only forward
  <case>-evidence        fragments.json, gaps.json (Context: F-<n>-001..899, G-<n>-01..49) and
                         forensics_fragments.json, forensics_gaps.json (Forensics: F-<n>-901..999, G-<n>-91..99 or 901+)
  <case>-rebuilt         rules.json, gaps.json (Reconstruction: R-<n>-*, G-<n>-51..89). Its report_items.json is never
                         logged: Validation logs report items.
  <case>-report/rebuilt  validation_feedback.json (Validation, every copy): one verdict each, plus its report items
                         once the verdict is final (pass, or handed to a person)
  all three folders      events_<agent>.json and cc.py's fallback files <table>.jsonl (every copy), replayed with
                         cc.py's own post(); Validation's verdicts.jsonl wins over validation_feedback.json
Newest copy of each record file. A record outside its agent's id range, or naming another case, is skipped and
reported, so one agent's file can never overwrite another agent's row. A pass writes cases, then fragments, gaps,
rules, verdicts, report items, then events and checkups.
State (per app): a hash of each record sent and the Naive file ids already read, so a rerun sends and downloads only
what is new or changed. Delete the state file to resend everything. Run one relay per team: verdicts, report items
and events have no id in the app, so two relays with two state files would log them twice.
"""
import argparse
import atexit
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    import fcntl
except ImportError:  # Windows: no single-run lock
    fcntl = None

DEFAULT_STATE = "~/.datacare-sync-state.json"
STAGES = ("intake", "forensics", "context", "reconstruction", "waiting_client",
          "validation", "approval", "delivered", "unresolved")
KINDS = ("excel", "code", "checkup", "other")
LABELS = ("recovered", "reconstructed and tested", "reconstructed but untested", "unresolved")
RULE_STATUSES = LABELS[1:]
GAP_STATUSES = ("open", "found", "requested", "unresolved")
FRAGMENT_TYPES = ("code", "record", "clue")
OUTCOMES = ("pass", "fail", "error", "untested")
FINAL_ACTIONS = ("escalate_to_human", "blocked_integration_escalate_to_human")
WITHHELD = "withheld (private to Validation)"

CASE_RE = re.compile(r"^C-\d{1,8}$")
ID_RE = re.compile(r"^([FGR])-(\d{1,8})-(\d{1,6})$")
FILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
EVENTS_RE = re.compile(r"^events_([A-Za-z0-9_-]{1,40})\.json$")
JSONL_RE = re.compile(r"^([a-z_]{1,40})\.jsonl$")
BUSY_RE = re.compile(r"rate_limited|at capacity", re.I)
MISSING_RE = re.compile(r"not found|no such|does not exist", re.I)

FOLDERS = ("evidence", "rebuilt", "report")
RECORD_FILES = {  # folder -> file name -> (table, agent that owns it)
    "evidence": {"fragments.json": ("fragments", "context"), "gaps.json": ("gaps", "context"),
                 "forensics_fragments.json": ("fragments", "forensics"), "forensics_gaps.json": ("gaps", "forensics")},
    "rebuilt": {"rules.json": ("rules", "reconstruction"), "gaps.json": ("gaps", "reconstruction")},
}
RANGES = {  # contract "Ids": each agent mints in its own range, because the app upserts on id
    ("fragments", "context"): (((1, 899),), "F-{c}-001 to 899"),
    ("fragments", "forensics"): (((901, 999),), "F-{c}-901 to 999"),
    ("gaps", "context"): (((1, 49),), "G-{c}-01 to 49"),
    ("gaps", "reconstruction"): (((51, 89),), "G-{c}-51 to 89"),
    ("gaps", "forensics"): (((91, 99), (901, 999999)), "G-{c}-91 to 99 or 901 and up"),
    ("rules", "reconstruction"): (((1, 999999),), "R-{c}-01 and up"),
}
VERDICT_FILES = ("validation_feedback.json", "verdict.json", "validation_verdict.json")
CONTEXT_FILES = frozenset(("evidence.json", "fragments.json", "gaps.json", "inventory.md", "events_context.json"))
PHASES = ("cases", "fragments", "gaps", "rules", "verdicts", "report_items", "events", "checkups")
PARALLEL = ("fragments", "gaps", "rules", "report_items")  # independent upserts; events keep their order
NOUNS = {"cases": ("case row", "case rows"), "fragments": ("fragment", "fragments"), "gaps": ("gap", "gaps"),
         "rules": ("rule", "rules"), "verdicts": ("verdict", "verdicts"), "report_items": ("report item", "report items"),
         "events": ("event", "events"), "checkups": ("checkup", "checkups")}
JSONL_PHASE = {"cases": "cases", "case_updates": "cases", "fragments": "fragments", "gaps": "gaps", "rules": "rules",
               "verdicts": "verdicts", "report_items": "report_items", "events": "events", "checkups": "checkups"}
PK = {"fragments": "fragment_id", "gaps": "gap_id", "rules": "rule_id"}
CC_COMMANDS = ("case-new", "case-stage", "fragment", "rule", "gap", "verdict", "report-item", "event", "ping")
ENV_FOR_CC = frozenset(("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP",
                        "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "http_proxy",
                        "https_proxy", "no_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"))
WORKERS = 4
MAX_FILE_BYTES = 20 * 1024 * 1024
MARK = "@@sync-result "
# Replays cc.py fallback rows through cc.py's own post()/patch_case(), in a child process with a minimal environment.
REPLAY = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("datacare_cc", sys.argv[1])
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
for job in json.loads(sys.stdin.buffer.read().decode("utf-8")):
    try:
        if job["api"] == "case_updates":
            row = cc.patch_case(job["case_id"], job["body"])
        else:
            row = cc.post(job["api"], job["body"])
        res = {"ok": True, "row": row if isinstance(row, dict) else None}
    except Exception as e:
        res = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    sys.stdout.write("\n@@sync-result " + json.dumps(res) + "\n")
    sys.stdout.flush()
"""
_CACHE = {"cc_id": None, "cc_path": None, "cc_dir": None, "cc_ok": None, "index_id": None, "index": None}
_CACHED = object()  # a file this relay already read in full


class _Fatal(Exception):
    def __init__(self, message, kind="setup"):
        Exception.__init__(self, message)
        self.kind = kind


class _Skip(Exception):
    pass


class NaiveError(Exception):
    pass


# ---------------------------------------------------------------- small helpers

def _redact(text):
    text, token = str(text), os.environ.get("CC_API_TOKEN") or ""
    return text.replace(token, "[secret removed]") if len(token) >= 4 else text


def _last_line(text):
    lines = [x.strip() for x in str(text or "").splitlines() if x.strip()]
    return lines[-1] if lines else ""


def _mask(client):
    if client and "@" in client:
        user, _, domain = client.partition("@")
        return user[:1] + "***@" + domain
    return client


def _hash(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\0")
    return h.hexdigest()[:32]


def _text(v, limit=4000):
    """A record value as one string for cc.py (no NUL bytes), or None."""
    if v is None:
        return None
    if isinstance(v, bool):
        v = "true" if v else "false"
    elif isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    elif not isinstance(v, str):
        v = str(v)
    return v.replace("\x00", "")[:limit]


def _texts(v, limit=200):
    out = []
    for x in (v if isinstance(v, list) else [] if v is None else [v]):
        t = _text(x, 1000)
        if t and t.strip():
            out.append(t)
    return out[:limit]


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _newest(files):
    """Newest copy of each name (the CLI lists newest first, and a name can appear more than once)."""
    seen, out = set(), []
    for f in files:
        if f["name"] not in seen:
            seen.add(f["name"])
            out.append(f)
    return out


def _required(rec, field, rid, limit=4000):
    v = _text(rec.get(field), limit)
    if not v or not v.strip():
        raise _Skip("%s has no %s" % (rid, field))
    return v


def _owned(table, agent, case, rid):
    prefix = {"fragments": "F", "gaps": "G", "rules": "R"}[table]
    m = ID_RE.match(rid or "")
    if not m or m.group(1) != prefix:
        raise _Skip("%r is not an id like %s-%s-01" % ((rid or "")[:40], prefix, case[2:]))
    if int(m.group(2)) != int(case[2:]):
        raise _Skip("%s belongs to C-%s" % (rid, m.group(2)))
    spans, text = RANGES[(table, agent)]
    if not any(lo <= int(m.group(3)) <= hi for lo, hi in spans):
        owner = agent.capitalize() + ("'" if agent.endswith("s") else "'s")
        raise _Skip("%s is outside %s range %s" % (rid, owner, text.format(c=case[2:])))


# ---------------------------------------------------------------- records -> cc.py command lines

def fragment_args(case, rec, agent):
    fid = _text(rec.get("fragment_id"), 64)
    _owned("fragments", agent, case, fid)
    src = _required(rec, "source_file", fid, 500)
    if rec.get("type") not in FRAGMENT_TYPES:
        raise _Skip("%s has type %s (code, record or clue)" % (fid, _text(rec.get("type"), 30)))
    args = ["fragment", "--id=" + fid, "--case=" + case, "--source-file=" + src, "--type=" + rec["type"], "--by=" + agent]
    loc, conf, notes = _text(rec.get("location"), 500), _num(rec.get("confidence")), _text(rec.get("notes"))
    if loc:
        args.append("--location=" + loc)
    if conf is not None:
        args.append("--confidence=" + repr(conf))
    if notes:
        args.append("--notes=" + notes)
    return fid, args


def gap_args(case, rec, agent):
    gid = _text(rec.get("gap_id"), 64)
    _owned("gaps", agent, case, gid)
    args = ["gap", "--id=" + gid, "--case=" + case, "--what=" + _required(rec, "what", gid)]
    why, places = _text(rec.get("why")), _texts(rec.get("where_to_look"))
    if why:
        args.append("--why=" + why)
    if rec.get("status") in GAP_STATUSES:
        args.append("--status=" + rec["status"])
    if places:
        args += ["--where-to-look"] + places
    return gid, args


def rule_args(case, rec, agent):
    rid = _text(rec.get("rule_id"), 64)
    _owned("rules", agent, case, rid)
    desc = _required(rec, "description", rid)
    if rec.get("status") not in RULE_STATUSES:
        raise _Skip("%s has status %s (a rule is reconstructed and tested, reconstructed but untested or unresolved)"
                    % (rid, _text(rec.get("status"), 40)))
    evidence = _texts(rec.get("evidence"))
    if not evidence:
        raise _Skip("%s has no evidence (cc.py rule needs at least one)" % rid)
    args = ["rule", "--id=" + rid, "--case=" + case, "--description=" + desc, "--status=" + rec["status"]]
    if isinstance(rec.get("alternatives"), list):
        args.append("--alternatives=" + json.dumps(rec["alternatives"], ensure_ascii=False, sort_keys=True))
    return rid, args + ["--evidence"] + evidence


BUILDERS = {"fragments": fragment_args, "gaps": gap_args, "rules": rule_args}


def event_args(case, entry, file_agent):
    other = entry.get("case_id")
    if other not in (None, "") and str(other).strip().upper() != case:
        raise _Skip("an event for %s" % _text(other, 20))
    agent = (_text(entry.get("agent"), 80) or "").strip() or file_agent
    stage = (_text(entry.get("stage"), 80) or "").strip() or file_agent
    msg = _text(entry.get("message"), 2000)
    cost = _num(entry.get("cost_usd", entry.get("cost")))
    human = entry.get("human", entry.get("human_stepped_in"))
    args = ["event", "--case=" + case, "--agent=" + agent, "--stage=" + stage]
    if msg:
        args.append("--message=" + msg)
    if cost is not None:
        args.append("--cost=" + repr(cost))
    if human is True or (isinstance(human, str) and human.strip().lower() in ("true", "yes")):
        args.append("--human")
    return args


def feedback_jobs(case, data):
    """Validation's validation_feedback.json -> (verdict id, verdict args), [(item, label, args)], skip reasons."""
    if not isinstance(data, dict):
        raise _Skip("not a JSON object")
    for k in ("job_id", "case_id"):  # job_id is the case; Validation's own case_id is its dataset (excel_a)
        v = str(data.get(k) or "").strip().upper()
        if CASE_RE.match(v):
            if v != case:
                raise _Skip("it is for %s" % v)
            break
    outcome = str(data.get("outcome") or "").strip().lower()
    if outcome not in OUTCOMES:
        raise _Skip("it has no outcome (pass, fail, error or untested)")
    vid = (_text(data.get("verdict_id"), 80) or "").strip() or "sha-" + _hash(data)[:16]
    retry = _int(data.get("retry_count"))
    attempt = _int(data.get("attempt"))
    if retry is None or retry < 0:
        retry = attempt - 1 if attempt and attempt > 0 else 0
    row = {"example_id": "_outcome", "result": outcome, "expected": WITHHELD, "actual": WITHHELD, "verdict_id": vid}
    for k in ("next_action", "artifact_version"):
        if isinstance(data.get(k), str) and data[k]:
            row[k] = data[k][:200]
    if attempt is not None:
        row["attempt"] = attempt
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    for k in ("run", "failed"):
        if _int(checks.get(k)) is not None:
            row["checks_" + k] = _int(checks.get(k))
    verdict = (vid, ["verdict", "--case=" + case, "--outcome=" + outcome,
                     "--results=" + json.dumps([row], ensure_ascii=False), "--retry-count=%d" % retry])
    items, skipped = [], []
    if outcome == "pass" or data.get("next_action") in FINAL_ACTIONS:  # report items only once the loop has ended
        for it in data.get("items") if isinstance(data.get("items"), list) else []:
            if not isinstance(it, dict):
                skipped.append("an item that is not an object")
                continue
            item = (_text(it.get("item_id") or it.get("item"), 500) or "").strip()
            if not item or it.get("label") not in LABELS:
                skipped.append("item %s has no item_id or no label of the four" % (item or "?"))
                continue
            cites = _texts(it.get("evidence") or it.get("cites")) or [item]
            items.append((item, it["label"], ["report-item", "--case=" + case, "--item=" + item,
                                              "--label=" + it["label"], "--cites"] + cites))
    return verdict, items, skipped


def parse_index(data):
    """case-index/index.json in whatever shape: a list of case rows, {"cases": [...]}, or rows keyed by case id."""
    if isinstance(data, dict):
        for k in ("cases", "data", "items", "index", "rows"):
            if isinstance(data.get(k), (list, dict)):
                data = data[k]
                break
    if isinstance(data, dict):
        rows = []
        for k, v in data.items():
            if isinstance(v, dict):
                rows.append(dict(v, case_id=v.get("case_id") or k))
            elif isinstance(v, str) and v.strip().lower() in STAGES:
                rows.append({"case_id": k, "stage": v})
            else:
                rows.append(None)
    elif isinstance(data, list):
        rows = data
    else:
        return {}, 1
    index, skipped = {}, 0
    for r in rows:
        cid = str((r.get("case_id") or r.get("id") or r.get("case") or "") if isinstance(r, dict) else "").strip().upper()
        if not CASE_RE.match(cid):
            skipped += 1
            continue
        kind = str(r.get("kind") or r.get("asset_type") or "").strip().lower()
        stage = str(r.get("stage") or "").strip().lower()
        retry = _int(r.get("retry_count"))
        index.setdefault(cid, {"client": _client(r), "kind": kind if kind in KINDS else None,
                               "stage": stage if stage in STAGES else None,
                               "retry_count": retry if retry is not None and retry >= 0 else None,
                               "quote": _num(r.get("quote_usd", r.get("quote")))})
    return index, skipped


def _client(r):
    for k in ("client_email", "email", "from"):
        if isinstance(r.get(k), str) and "@" in r[k]:
            return r[k].strip()[:200]
    c = r.get("client")
    if isinstance(c, dict):
        for k in ("email", "client_email", "address"):
            if isinstance(c.get(k), str) and "@" in c[k]:
                return c[k].strip()[:200]
        c = c.get("name")
    if isinstance(c, str) and c.strip():
        return c.strip()[:200]
    return None


def _file_stage(names):
    """How far the files say a case has come: evidence -> context, rebuilt -> reconstruction (a verdict, checked
    later, -> validation)."""
    if names["rebuilt"]:
        return "reconstruction"
    if names["evidence"] & CONTEXT_FILES:
        return "context"
    return "forensics" if names["evidence"] else None


def _forward(target, current):
    return (target in STAGES and (current or "intake") in STAGES
            and STAGES.index(target) > STAGES.index(current or "intake"))


def _stage_plan(cur, idx, file_stage):
    """Stage and retry_count to set: the further of the index's stage and the files' stage, only ever forward."""
    cands = [s for s in (idx.get("stage"), file_stage) if s in STAGES]
    target = max(cands, key=STAGES.index) if cands else None
    stage = target if _forward(target, cur.get("stage")) else None
    retry = idx.get("retry_count")
    return stage, retry if retry is not None and retry > (_int(cur.get("retry_count")) or 0) else None


def _find_cli(cli=None):
    if cli:
        return shutil.which(os.path.expanduser(cli))
    for name in ("vetta", "naive"):
        if shutil.which(name):
            return shutil.which(name)
    for name in ("vetta", "naive"):
        p = os.path.expanduser("~/.npm-global/bin/" + name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


# ---------------------------------------------------------------- state and lock

class _State:
    def __init__(self, path, app_key, write):
        self.path, self.write = path, write
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError) as e:
            raise _Fatal("the state file %s cannot be read (%s); fix or delete it (deleting it resends everything)"
                         % (path, e))
        if not isinstance(data, dict) or not isinstance(data.setdefault("apps", {}), dict):
            raise _Fatal("the state file %s is not a sync_records.py state file; fix or delete it" % path)
        data["version"] = 1
        app = data["apps"].setdefault(app_key, {})
        self.sent, self.files, self.data = app.setdefault("sent", {}), app.setdefault("files", {}), data

    def reset_case(self, case):
        """The app does not have this case (new, or its database was reset): send all of its records again."""
        tag = ":%s:" % case
        for k in [k for k in self.sent if tag in k]:
            del self.sent[k]
        for k in [k for k, v in self.files.items() if v == case]:
            del self.files[k]

    def save(self):
        if not self.write:
            return
        folder = os.path.dirname(self.path) or "."
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".datacare-sync-", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


class _Lock:
    def __init__(self, state_path):
        self.path, self.f = state_path + ".lock", None

    def acquire(self):
        if fcntl is None:
            return True
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.f = open(self.path, "a")
        try:
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.f.close()
            self.f = None
            return False

    def release(self):
        if self.f:
            fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
            self.f.close()
            self.f = None


class _Case:
    def __init__(self, case):
        self.case, self.sent, self.would, self.failed = case, {}, {}, 0
        self.notes, self.problems, self.failures, self.blocked, self.file_stage = [], [], [], None, None

    def active(self):
        return bool(self.notes or self.sent or self.would or self.failed or self.problems or self.blocked)

    def line(self, dry):
        tail = "" if dry else "; %d failed" % self.failed
        if self.blocked:
            return "%s: %s; nothing sent%s" % (self.case, self.blocked, tail)
        counts = {p: len(v) for p, v in self.would.items()} if dry else self.sent
        items = ["%d %s" % (counts[p], NOUNS[p][counts[p] != 1]) for p in PHASES if counts.get(p)]
        parts = list(self.notes)
        if items:
            parts.append(("would send " if dry else "") + ", ".join(items) + ("" if dry else " sent"))
        return "%s%s: %s%s" % (self.case, " (dry run)" if dry else "", "; ".join(parts) or "nothing new", tail)


# ---------------------------------------------------------------- one pass

class _Pass:
    def __init__(self, opts, say):
        self.o, self.say, self.dry = opts, say, opts["dry_run"]
        backoff = _num(os.environ.get("DATACARE_SYNC_BACKOFF"))
        self.backoff = backoff if backoff is not None and backoff >= 0 else 10.0
        self.cli = self.cc = self.state = self.view = None
        self.cli_env = {k: v for k, v in os.environ.items() if k != "CC_API_TOKEN"}  # the Naive CLI never needs it
        self.cc_env = {k: v for k, v in os.environ.items() if k in ENV_FOR_CC or k.startswith("CC_")}
        self.file_left = {}  # Naive file id -> [case, jobs not yet sent, a job failed]
        self.queued = set()  # keys queued this pass (two copies of a cumulative file share entries)

    # -- Naive CLI
    def _naive(self, args):
        last = ""
        for attempt in range(1, 8):
            try:
                p = subprocess.run([self.cli] + args, env=self.cli_env, capture_output=True, timeout=180)
            except subprocess.TimeoutExpired:
                raise NaiveError("the Naive CLI timed out on: %s" % " ".join(args[:2]))
            except OSError as e:
                raise NaiveError("could not run the Naive CLI: %s" % e)
            if p.returncode == 0:
                return p.stdout
            text = p.stderr.decode("utf-8", "replace") + "\n" + p.stdout[:4000].decode("utf-8", "replace")
            last = _last_line(text) or "exit code %d" % p.returncode
            if not BUSY_RE.search(text) or attempt == 7:
                break
            self.say("  Naive is busy, trying again in %g seconds..." % (attempt * self.backoff))
            time.sleep(attempt * self.backoff)
        raise NaiveError(_redact(last)[:300])

    def _list(self, folder, search=None):
        args = ["file", "list", "--folder", folder, "--limit", "50", "--order", "desc"]
        try:
            out = self._naive(args + (["--search", search] if search else []))
        except NaiveError as e:
            if MISSING_RE.search(str(e)):
                return []
            raise
        try:
            data = json.loads(out.decode("utf-8", "replace"))
        except ValueError:
            raise NaiveError("file list for %s did not print JSON" % folder)
        items = data.get("data") if isinstance(data, dict) else data
        return [{"id": x["id"], "name": x["name"]} for x in (items if isinstance(items, list) else [])
                if isinstance(x, dict) and isinstance(x.get("id"), str) and FILE_ID_RE.match(x["id"])
                and isinstance(x.get("name"), str) and 0 < len(x["name"]) <= 255]

    def _download(self, fid):
        data = self._naive(["file", "download", fid])
        if len(data) > MAX_FILE_BYTES:
            raise NaiveError("larger than 20 MB")
        return data

    # -- cc.py
    def _resolve_cc(self):
        # cc.py runs with the app token, so by default it is the repo copy next to this file. Downloading it from the
        # Naive folder tools ("--cc naive") trusts whoever can publish there, agents included.
        choice = self.o["cc"]
        if not choice:
            here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc.py")
            if not os.path.isfile(here):
                raise _Fatal("cc.py not found next to sync_records.py; pass --cc /path/to/cc.py (the data-care repo "
                             "copy), or --cc naive to download the newest one from the Naive folder tools")
            choice = here
        if choice != "naive":
            path = os.path.abspath(os.path.expanduser(choice))
            if not os.path.isfile(path):
                raise _Fatal("cc.py not found at %s" % path)
        else:
            try:
                hit = next((f for f in self._list("tools", search="cc.py") if f["name"] == "cc.py"), None)
                if not hit:
                    raise _Fatal("there is no cc.py in the Naive folder tools; pass --cc /path/to/cc.py")
                if _CACHE["cc_id"] != hit["id"] or not os.path.isfile(_CACHE["cc_path"] or ""):
                    data = self._download(hit["id"])
                    if not _CACHE["cc_dir"]:
                        _CACHE["cc_dir"] = tempfile.mkdtemp(prefix="datacare-cc-")
                        atexit.register(shutil.rmtree, _CACHE["cc_dir"], True)
                    path = os.path.join(_CACHE["cc_dir"], "cc.py")
                    with open(path, "wb") as f:
                        f.write(data)
                    _CACHE.update(cc_id=hit["id"], cc_path=path)
            except NaiveError as e:
                raise _Fatal("could not fetch cc.py from the Naive folder tools: %s" % e, "naive")
            path = _CACHE["cc_path"]
        sig = [path, os.path.getmtime(path), os.path.getsize(path)]
        if _CACHE["cc_ok"] != sig:
            try:
                p = subprocess.run([sys.executable, "-I", path, "--help"], env=self.cc_env, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=60)
                out = p.stdout + p.stderr
            except (OSError, subprocess.TimeoutExpired) as e:
                out = str(e)
            missing = [c for c in CC_COMMANDS if c not in out]
            if missing:
                raise _Fatal("%s does not look like Andrei's cc.py (its --help has no %s)" % (path, ", ".join(missing)))
            _CACHE["cc_ok"] = sig
        return path

    def _cc(self, args):
        try:
            p = subprocess.run([sys.executable, "-I", self.cc] + args, env=self.cc_env, capture_output=True,
                               encoding="utf-8", errors="replace", timeout=150)
        except subprocess.TimeoutExpired:
            return False, "cc.py did not finish within 150 seconds", None
        except (OSError, ValueError) as e:
            return False, "could not run cc.py: %s" % e, None
        if p.returncode != 0:
            why = _last_line(p.stderr) or _last_line(p.stdout) or "cc.py exit code %d" % p.returncode
            return False, _redact(why[7:] if why.startswith("cc.py: ") else why)[:300], None
        for line in reversed(p.stdout.splitlines()):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            return True, "", row if isinstance(row, dict) else None
        return True, "", None

    def _replay(self, calls):
        out, err = "", ""
        try:
            p = subprocess.run([sys.executable, "-I", "-c", REPLAY, self.cc], input=json.dumps(calls), env=self.cc_env,
                               capture_output=True, encoding="utf-8", errors="replace", timeout=120 + 15 * len(calls))
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = "cc.py did not finish in time"
        except (OSError, ValueError) as e:
            err = "could not run cc.py: %s" % e
        results = []
        for line in out.splitlines():
            if line.startswith(MARK):
                try:
                    r = json.loads(line[len(MARK):])
                except ValueError:
                    continue
                results.append((bool(r.get("ok")), _redact(r.get("error") or "")[:300], r.get("row")))
        why = _redact(_last_line(err) or "cc.py stopped early")[:300]
        return (results + [(False, why, None)] * len(calls))[:len(calls)]

    # -- the app's current cases (public board)
    def _read_board(self, url):
        req = urllib.request.Request(url.rstrip("/") + "/api/board", headers={"user-agent": "sync_records.py"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                rows = json.loads(resp.read().decode("utf-8")).get("cases")
            if not isinstance(rows, list):
                raise ValueError("the board has no case list")
        except Exception as e:  # noqa: BLE001 - any failure means "unknown"
            self.say("sync: could not read the app's board (%s); no case is created or moved this pass"
                     % _redact(_last_line(e))[:200])
            return None
        return {r["case_id"].strip().upper(): {"stage": r.get("stage"), "retry_count": _int(r.get("retry_count"))}
                for r in rows if isinstance(r, dict) and isinstance(r.get("case_id"), str)}

    def _read_index(self):
        """-> (index, note, failed)"""
        try:
            hit = next((f for f in self._list("case-index") if f["name"] == "index.json"), None)
            if not hit:
                return {}, None, False
            if _CACHE["index_id"] == hit["id"]:
                return _CACHE["index"], None, False
            raw = self._download(hit["id"])
        except NaiveError as e:
            return {}, "sync: could not read case-index/index.json: %s" % e, True
        try:
            index, skipped = parse_index(json.loads(raw.decode("utf-8-sig")))
        except ValueError as e:
            return {}, "sync: case-index/index.json is not valid JSON (%s)" % _last_line(e)[:120], True
        _CACHE.update(index_id=hit["id"], index=index)
        note = "sync: case-index/index.json: %d entr%s skipped (no case id like C-0101)" % (
            skipped, "y" if skipped == 1 else "ies") if skipped else None
        return index, note, False

    # -- planning: read the case folders and turn files into jobs
    def _read(self, case, sfx, f, st, as_json=True):
        if f["id"] in self.state.files:
            return _CACHED
        where = "%s-%s/%s" % (case, sfx, f["name"])
        try:
            raw = self._download(f["id"])
        except NaiveError as e:
            st.problems.append("%s could not be downloaded: %s" % (where, e))
            return None
        try:
            text = raw.decode("utf-8-sig")
            data = json.loads(text) if as_json else text
        except ValueError as e:
            self._bad(case, sfx, f, st, "not valid %s (%s)" % ("JSON" if as_json else "UTF-8", _last_line(e)[:80]))
            return None
        self.file_left[f["id"]] = [case, 0, False]
        return data

    def _bad(self, case, sfx, f, st, why):
        st.problems.append("%s-%s/%s skipped: %s" % (case, sfx, f["name"], why))
        self.file_left.pop(f["id"], None)
        if not self.dry:
            self.state.files[f["id"]] = case  # the same file id never changes, so report it once

    def _skipped(self, case, sfx, f, st, reasons):
        if reasons:
            st.problems.append("%s-%s/%s: %d record%s skipped (%s%s)" % (
                case, sfx, f["name"], len(reasons), "" if len(reasons) == 1 else "s", "; ".join(reasons[:3]),
                "; ..." if len(reasons) > 3 else ""))

    def _job(self, jobs, phase, key, label, fid, args=None, call=None, value=None, also=()):
        value = value or _hash(args if args is not None else call)
        if self.state.sent.get(key) == value or key in self.queued:
            return  # already sent and unchanged, or queued from another copy of the same file
        self.queued.add(key)
        jobs[phase].append({"phase": phase, "key": key, "label": label, "file": fid, "args": args, "call": call,
                            "value": value, "also": list(also)})
        if fid in self.file_left:
            self.file_left[fid][1] += 1

    def _plan(self, case, st):
        if self.view is not None and case not in self.view:
            self.state.reset_case(case)
        listing, names = {}, {}
        for sfx in FOLDERS:
            try:
                listing[sfx] = self._list("%s-%s" % (case, sfx))
            except NaiveError as e:
                listing[sfx] = []
                st.problems.append("could not list %s-%s: %s" % (case, sfx, e))
            names[sfx] = {f["name"] for f in listing[sfx]}
        st.file_stage = _file_stage(names)
        jobs, planned = {p: [] for p in PHASES}, set()

        # 1. each agent's own record files (newest copy), owner checked by file name and id range
        for sfx, owned in RECORD_FILES.items():
            for f in _newest(listing[sfx]):
                if f["name"] not in owned:
                    continue
                table, agent = owned[f["name"]]
                data = self._read(case, sfx, f, st)
                if data is _CACHED or data is None:
                    continue
                if not isinstance(data, list):
                    self._bad(case, sfx, f, st, "expected a JSON list")
                    continue
                skipped = []
                for rec in data:
                    try:
                        if not isinstance(rec, dict):
                            raise _Skip("an entry that is not an object")
                        label, args = BUILDERS[table](case, rec, agent)
                    except _Skip as e:
                        skipped.append(str(e))
                        continue
                    key = "%s:%s:%s" % (table, case, label)
                    if key in planned:
                        skipped.append("%s appears twice; kept the first" % label)
                        continue
                    planned.add(key)
                    self._job(jobs, table, key, label, f["id"], args=args)
                self._skipped(case, sfx, f, st, skipped)

        # 2. Validation's verdicts (every copy, oldest first), unless Validation published its own cc.py output
        if "verdicts.jsonl" not in names["evidence"] | names["rebuilt"] | names["report"]:
            for sfx in ("report", "rebuilt"):
                for f in reversed(listing[sfx]):
                    if f["name"] not in VERDICT_FILES:
                        continue
                    data = self._read(case, sfx, f, st)
                    if data is _CACHED or data is None:
                        continue
                    try:
                        (vid, vargs), items, skipped = feedback_jobs(case, data)
                    except _Skip as e:
                        self._bad(case, sfx, f, st, str(e))
                        continue
                    vkey = "vid:%s:%s" % (case, vid)
                    if vkey in planned or vkey in self.state.sent:
                        continue  # this verdict is already logged
                    planned.add(vkey)
                    self._job(jobs, "verdicts", vkey, vid, f["id"], args=vargs, value="1")
                    for item, label, iargs in items:
                        ri = "ri:%s:%s:%s" % (case, item, label)
                        if ri not in self.state.sent:
                            self._job(jobs, "report_items", "report_items:%s:%s" % (case, item), item, f["id"],
                                      args=iargs, also=[ri])
                    self._skipped(case, sfx, f, st, skipped)
        if "verdicts.jsonl" in names["evidence"] | names["rebuilt"] | names["report"] or \
                any(k.startswith("vid:%s:" % case) for k in list(planned) + list(self.state.sent)):
            st.file_stage = "validation"  # a verdict, not just a verdict file name

        # 3. events_<agent>.json (every copy, oldest first); an event has no id, so it is keyed on its own hash
        for sfx in FOLDERS:
            for f in reversed(listing[sfx]):
                m = EVENTS_RE.match(f["name"])
                if not m:
                    continue
                data = self._read(case, sfx, f, st)
                if data is _CACHED or data is None:
                    continue
                entries = data.get("events") if isinstance(data, dict) else data
                if not isinstance(entries, list):
                    self._bad(case, sfx, f, st, "expected a JSON list of events")
                    continue
                seen, skipped = {}, []
                for n, entry in enumerate(entries, 1):
                    try:
                        if not isinstance(entry, dict):
                            raise _Skip("an entry that is not an object")
                        args = event_args(case, entry, m.group(1))
                    except _Skip as e:
                        skipped.append(str(e))
                        continue
                    h = _hash(args)
                    seen[h] = seen.get(h, 0) + 1  # two identical entries in one file are two events
                    self._job(jobs, "events", "events:%s:%s:%d" % (case, h, seen[h]), "%s #%d" % (f["name"], n),
                              f["id"], args=args, value="1")
                self._skipped(case, sfx, f, st, skipped)

        # 4. cc.py's fallback output, <table>.jsonl (every copy, oldest first): each row as cc.py would have sent it
        for sfx in FOLDERS:
            for f in reversed(listing[sfx]):
                m = JSONL_RE.match(f["name"])
                if not m:
                    continue
                api = m.group(1)
                if api not in JSONL_PHASE:
                    if f["id"] not in self.state.files:
                        self._bad(case, sfx, f, st, "not one of cc.py's tables")
                    continue
                text = self._read(case, sfx, f, st, as_json=False)
                if text is _CACHED or text is None:
                    continue
                skipped = []
                for n, line in enumerate(text.splitlines(), 1):
                    try:
                        job = self._jsonl_job(case, api, line.strip(), planned)
                    except _Skip as e:
                        skipped.append("line %d %s" % (n, e))
                        continue
                    if job:
                        key, label, call, also = job
                        self._job(jobs, JSONL_PHASE[api], key, label or "%s line %d" % (f["name"], n), f["id"],
                                  call=call, value="1", also=also)
                self._skipped(case, sfx, f, st, skipped)
        return jobs

    def _jsonl_job(self, case, api, line, planned):
        if not line:
            return None
        try:
            row = json.loads(line)
        except ValueError:
            raise _Skip("is not JSON")
        if not isinstance(row, dict):
            raise _Skip("is not a JSON object")
        other = row.get("case_id")
        if other in (None, ""):
            if api not in ("events", "checkups"):
                raise _Skip("has no case_id")
        elif str(other).strip().upper() != case:
            raise _Skip("is for %s" % _text(other, 20))
        if api == "case_updates":
            body = {k: row[k] for k in ("stage", "retry_count", "quote_usd") if row.get(k) is not None}
        else:
            body = {k: v for k, v in row.items() if not str(k).startswith("_")}  # drops cc.py's _logged_at
        key, label, also = "jsonl:%s:%s" % (case, _hash(api, row)), None, []
        if key in self.state.sent:
            return None
        if api in PK:
            label = _text(row.get(PK[api]), 64) or ""
            fkey = "%s:%s:%s" % (api, case, label)
            if fkey in planned or fkey in self.state.sent:
                raise _Skip("(%s) also comes from the agent's %s file, which wins" % (label, api))
        elif api == "verdicts":
            results = row.get("results") if isinstance(row.get("results"), list) else []
            vid = next((str(r["verdict_id"]) for r in results if isinstance(r, dict) and r.get("verdict_id")), None)
            if vid:
                vkey = "vid:%s:%s" % (case, vid)
                if vkey in self.state.sent:
                    return None  # already logged from validation_feedback.json
                label = vid
                also.append(vkey)
        elif api == "report_items":
            ri = "ri:%s:%s:%s" % (case, row.get("item"), row.get("label"))
            if ri in self.state.sent:
                return None
            label = _text(row.get("item"), 80)
            also.append(ri)
        return key, label, {"api": api, "case_id": case, "body": body}, also

    # -- sending
    def _send(self, case, st, jobs, parallel=False):
        if not jobs:
            return
        if self.dry:
            for j in jobs:
                st.would.setdefault(j["phase"], []).append(j["label"])
            return
        cli = [j for j in jobs if j["args"] is not None]
        if cli:
            if parallel and len(cli) > 1:
                with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                    results = list(ex.map(lambda j: self._cc(j["args"]), cli))
            else:
                results = [self._cc(j["args"]) for j in cli]
            for j, r in zip(cli, results):
                self._done(case, st, j, *r)
        rows = [j for j in jobs if j["call"] is not None]
        if rows:
            for j, r in zip(rows, self._replay([j["call"] for j in rows])):
                self._done(case, st, j, *r)

    def _done(self, case, st, job, ok, err, row, count=True):
        left = self.file_left.get(job["file"])
        if not ok:
            st.failed += 1
            st.failures.append("%s %s: %s" % (NOUNS[job["phase"]][0], job["label"], err))
            if left:
                left[2] = True
            return
        self.state.sent[job["key"]] = job["value"]
        for k in job["also"]:
            self.state.sent[k] = "1"
        if count:
            st.sent[job["phase"]] = st.sent.get(job["phase"], 0) + 1
        if left:
            left[1] -= 1
        if job["phase"] == "cases" and isinstance(row, dict) and self.view is not None:
            self.view[case] = {"stage": row.get("stage"), "retry_count": _int(row.get("retry_count"))}

    def _case_rows(self, case, st, jobs):
        """Replay the Recovery Manager's own cc.py output for this case, without ever moving its stage back."""
        for j in jobs:
            body, cur = j["call"]["body"], (self.view or {}).get(case)
            if "stage" in body and (self.view is None or (cur and not _forward(body["stage"], cur.get("stage")))):
                body = {k: v for k, v in body.items() if k != "stage"}
                j = dict(j, call=dict(j["call"], body=body))
            if j["call"]["api"] == "case_updates" and not body:
                if not self.dry:
                    self._done(case, st, j, True, "", None, count=False)  # nothing left to change
                continue
            self._send(case, st, [j])

    def _case_phase(self, case, st, jobs, idx):
        self._case_rows(case, st, [j for j in jobs if j["call"]["api"] == "cases"])
        if self.view is not None and case not in self.view:  # create the case when the app does not have it yet
            client = idx.get("client") or self.o["client_email"]
            if not client:
                st.blocked = ("not in the app yet, and case-index/index.json has no client email for it "
                              "(pass --client-email and --kind to create it)")
                return
            kind = idx.get("kind") or self.o["kind"] or "other"
            args = ["case-new", "--case=" + case, "--client-email=" + client, "--kind=" + kind]
            if idx.get("quote") is not None:
                args.append("--quote=" + repr(idx["quote"]))
            if self.dry:
                st.notes.append("would create the case (client %s, kind %s)" % (_mask(client), kind))
                self.view[case] = {"stage": "intake", "retry_count": 0}
            else:
                ok, err, row = self._cc(args)
                if not ok:
                    st.failed += 1
                    st.blocked = "could not create the case (%s)" % err
                    return
                st.notes.append("case created")
                row = row or {}
                self.view[case] = {"stage": row.get("stage") or "intake", "retry_count": _int(row.get("retry_count"))}
        self._case_rows(case, st, [j for j in jobs if j["call"]["api"] == "case_updates"])
        if self.view is None:
            return
        # stage and retry_count, only forward
        cur = self.view[case]
        stage, retry = _stage_plan(cur, idx, st.file_stage)
        if not stage and retry is None:
            return
        args = ["case-stage", "--case=" + case]
        notes = []
        if stage:
            args.append("--stage=" + stage)
            notes.append("stage %s -> %s" % (cur.get("stage") or "intake", stage))
        if retry is not None:
            args.append("--retry-count=%d" % retry)
            notes.append("retry_count %s -> %d" % (_int(cur.get("retry_count")) or 0, retry))
        if self.dry:
            st.notes.append("would move " + ", ".join(notes))
            return
        ok, err, row = self._cc(args)
        if ok:
            st.notes.append(", ".join(notes))
            self.view[case] = {"stage": stage or cur.get("stage"),
                               "retry_count": retry if retry is not None else cur.get("retry_count")}
        else:
            st.failed += 1
            st.failures.append("case-stage %s: %s" % (case, err))

    def run(self, summary, quiet):
        o = self.o
        url = os.environ.get("CC_URL", "").strip()
        if not self.dry:
            for name in ("CC_URL", "CC_API_TOKEN"):
                if not os.environ.get(name, "").strip():
                    raise _Fatal("%s is not set in this terminal. Set CC_URL and CC_API_TOKEN first (export CC_URL="
                                 "https://<the Data Care app>; export CC_API_TOKEN=<the token>). Nothing was sent."
                                 % name)
        if url and not re.match(r"^https?://", url, re.I):
            raise _Fatal("CC_URL must start with https:// (or http:// for a local app). Nothing was sent.")
        cases = []
        for c in o["cases"]:
            cid = str(c).strip().upper()
            if not CASE_RE.match(cid):
                raise _Fatal("%r is not a case id like C-0101" % str(c)[:40])
            if cid not in cases:
                cases.append(cid)
        self.cli = _find_cli(o["cli"])
        if not self.cli:
            raise _Fatal("the Naive CLI was not found (%s). Pass --cli /path/to/vetta, or install it with: "
                         "npm i -g @usenaive-sdk/cli" % (o["cli"] or "tried vetta and naive"))
        state_path = os.path.abspath(os.path.expanduser(o["state"]))
        lock = _Lock(state_path)
        if not self.dry and not lock.acquire():
            raise _Fatal("another sync is already running (lock %s); skipped this pass" % lock.path, "busy")
        try:
            app_key = hashlib.sha256(url.rstrip("/").encode("utf-8")).hexdigest()[:16] if url else "none"
            self.state = _State(state_path, app_key, write=not self.dry)
            if not self.dry:
                self.cc = self._resolve_cc()
                ok, err, row = self._cc(["ping"])
                if not ok:
                    raise _Fatal("cannot reach the Data Care app at CC_URL (cc.py ping: %s). Nothing was sent." % err,
                                 "app")
                if isinstance(row, dict) and row.get("token_valid") is False:
                    raise _Fatal("the Data Care app does not accept CC_API_TOKEN (cc.py ping says token_valid is "
                                 "false). Nothing was sent.", "app")
            index, note, failed = self._read_index()
            if note:
                self.say(note)
            if o["from_index"]:
                if failed and not cases:
                    raise _Fatal(note.replace("sync: ", ""), "naive")
                cases += [c for c in sorted(index) if c not in cases]
            if not cases:
                self.say("sync: no cases to sync yet (case-index/index.json lists none)")
                return
            self.view = self._read_board(url) if url else None
            sts = {c: _Case(c) for c in cases}
            plans = {c: self._plan(c, sts[c]) for c in cases}
            for c in cases:
                self._case_phase(c, sts[c], plans[c]["cases"], index.get(c) or {})
                if self.view is None and not sts[c].blocked:
                    sts[c].notes.append("case and stage not checked")
            self.state.save()
            for phase in PHASES[1:]:
                for c in cases:
                    if not sts[c].blocked:
                        self._send(c, sts[c], plans[c][phase], parallel=phase in PARALLEL)
                self.state.save()
            for fid, (case, left, failed_job) in self.file_left.items():
                if left <= 0 and not failed_job and not self.dry:
                    self.state.files[fid] = case
            self.state.save()
        finally:
            lock.release()
        for c in cases:
            st = sts[c]
            summary["cases"][c] = {"sent": dict(st.sent), "failed": st.failed, "notes": list(st.notes),
                                   "problems": list(st.problems), "failures": list(st.failures),
                                   "blocked": st.blocked, "would_send": {k: list(v) for k, v in st.would.items()}}
            summary["sent"] += sum(st.sent.values())
            summary["failed"] += st.failed
            if quiet and not st.active():
                continue
            self.say(st.line(self.dry))
            for p in st.problems[:12] + (["... and %d more" % (len(st.problems) - 12)] if len(st.problems) > 12 else []):
                self.say("  " + p)
            for f in st.failures[:5] + (["... and %d more" % (len(st.failures) - 5)] if len(st.failures) > 5 else []):
                self.say("  failed " + f)
            for phase in PHASES:
                ids = st.would.get(phase)
                if ids:
                    self.say("  would send %s: %s%s" % (NOUNS[phase][1], ", ".join(ids[:12]),
                                                        " ... (+%d more)" % (len(ids) - 12) if len(ids) > 12 else ""))


def sync_once(cases=(), from_index=False, cc=None, cli=None, state=DEFAULT_STATE, dry_run=False,
              client_email=None, kind=None, quiet=False, log=print):
    """One full pass. Never raises for an expected problem: it is in the summary's "error" (and printed).

    cases: case ids like "C-0101"; from_index: also every case in case-index/index.json; cc: path to cc.py
    (default: the cc.py next to this file; "naive": the newest one in the Naive folder tools); cli: the Naive CLI; state: the state file; quiet: print a
    case's line only when something happened; log: where lines go (None: nowhere).
    Returns {"ok", "error", "error_kind", "dry_run", "sent", "failed", "cases": {case: {...}}}.
    """
    out = log or (lambda line: None)

    def say(line):
        out(_redact(line))

    if isinstance(cases, str):
        cases = [cases]
    summary = {"ok": False, "error": None, "error_kind": None, "dry_run": bool(dry_run), "sent": 0, "failed": 0,
               "cases": {}}
    opts = {"cases": list(cases or ()), "from_index": bool(from_index), "cc": cc, "cli": cli, "state": state,
            "dry_run": bool(dry_run), "client_email": client_email, "kind": kind if kind in KINDS else None}
    try:
        _Pass(opts, say).run(summary, quiet)
    except _Fatal as e:
        summary["error"], summary["error_kind"] = _redact(e), e.kind
        say("sync: %s" % e)
    except Exception as e:  # noqa: BLE001 - never break the caller's loop
        summary["error"], summary["error_kind"] = _redact("%s: %s" % (type(e).__name__, e)), "internal"
        say("sync: unexpected error: %s" % summary["error"])
    summary["ok"] = summary["error"] is None and summary["failed"] == 0
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(prog="sync_records.py",
                                description="Copy Data Care records from the Naive file library into the Data Care app.")
    p.add_argument("--case", action="append", default=[], metavar="C-0101", help="a case to sync (repeat for more)")
    p.add_argument("--from-index", action="store_true", help="every case in case-index/index.json")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="one pass, then stop (the default)")
    g.add_argument("--loop", type=float, metavar="SECONDS", help="a pass every SECONDS (at least 10)")
    p.add_argument("--dry-run", action="store_true", help="print what would be sent; send and save nothing")
    p.add_argument("--cc", help="path to cc.py (default: the cc.py next to this file; 'naive': the newest one in the Naive folder tools)")
    p.add_argument("--cli", help="the Naive CLI (default: vetta or naive)")
    p.add_argument("--state", default=DEFAULT_STATE, help="state file (default %(default)s)")
    p.add_argument("--client-email", help="client email for a case that case-index/index.json does not describe")
    p.add_argument("--kind", choices=KINDS, help="kind for a case that case-index/index.json does not describe")
    a = p.parse_args(argv)
    if not a.case and not a.from_index:
        p.error("give --case C-0101 (one or more) or --from-index")
    if a.loop is not None and a.loop < 10:
        p.error("--loop needs at least 10 seconds")

    def printer(line):
        print(line, flush=True)

    kw = dict(cases=a.case, from_index=a.from_index, cc=a.cc, cli=a.cli, state=a.state, dry_run=a.dry_run,
              client_email=a.client_email, kind=a.kind, log=printer)
    try:
        s = sync_once(**kw)
        while a.loop is not None and s["error_kind"] != "setup":
            time.sleep(a.loop)
            s = sync_once(quiet=True, **kw)
    except KeyboardInterrupt:
        return 130
    if s["error"]:
        return {"setup": 2, "busy": 0}.get(s["error_kind"], 1)
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
