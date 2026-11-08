#!/usr/bin/env python3
"""cc.py: write Data Care records (cases, fragments, rules, gaps, verdicts, report items, events, checkups).

Standard library only, Python 3.8+, so every Naive agent can paste or fetch it into its sandbox.

    python3 cc.py case-new   --case C-0001 --client-email a@b.com --kind excel --quote 250
    python3 cc.py case-stage --case C-0001 --stage forensics [--retry-count 1]
    python3 cc.py fragment   --id F-0001-001 --case C-0001 --source-file model.xlsx --type record --by forensics
    python3 cc.py rule       --id R-0001-01 --case C-0001 --description "..." --evidence F-0001-001 F-0001-002 --status "reconstructed and tested"
    python3 cc.py gap        --id G-0001-01 --case C-0001 --what "..." --where-to-look "CFO email" "Q3 report"
    python3 cc.py verdict    --case C-0001 --fail --results @verdict.json --retry-count 1
    python3 cc.py report-item --case C-0001 --item "Model!E12" --label recovered --cites F-0001-003
    python3 cc.py event      --case C-0001 --agent forensics --stage forensics --message "scan done" --cost 0.12 [--human]
    python3 cc.py checkup    --case C-0002 --team "Team X" --repo-url https://... --high 1 --medium 2 --low 5
    python3 cc.py ping

Environment: CC_URL (the Data Care app, e.g. https://datacare.example) and CC_API_TOKEN (sent as x-cc-token).
When CC_URL is not set, records are appended to JSON Lines files in CC_FALLBACK_DIR (default ./cc_records)
so an agent can keep working before the app is live. Prints the stored row as JSON on success.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

LABELS = ("recovered", "reconstructed and tested", "reconstructed but untested", "unresolved")
RULE_STATUSES = LABELS[1:]
GAP_STATUSES = ("open", "found", "requested", "unresolved")
KINDS = ("excel", "code", "checkup", "other")
STAGES = ("intake", "forensics", "context", "reconstruction", "waiting_client",
          "validation", "approval", "delivered", "unresolved")
FRAGMENT_TYPES = ("code", "record", "clue")

RETRY_STATUSES = (429, 500, 502, 503, 504)
ATTEMPTS = 4


class CCError(Exception):
    pass


def _json_arg(value):
    """Accept inline JSON, or @path to a JSON file."""
    if value.startswith("@"):
        with open(value[1:], encoding="utf-8") as f:
            return json.load(f)
    return json.loads(value)


def _request(method, path, body=None):
    base = os.environ.get("CC_URL", "").rstrip("/")
    token = os.environ.get("CC_API_TOKEN", "")
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"content-type": "application/json", "x-cc-token": token, "user-agent": "cc.py"}
    last = None
    for attempt in range(ATTEMPTS):
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code not in RETRY_STATUSES:
                raise CCError("HTTP %d from %s %s: %s" % (e.code, method, path, detail))
            last = "HTTP %d: %s" % (e.code, detail)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = str(e)
        if attempt < ATTEMPTS - 1:
            time.sleep(2 ** attempt)
    raise CCError("gave up after %d attempts on %s %s: %s" % (ATTEMPTS, method, path, last))


def _fallback(table, body):
    folder = os.environ.get("CC_FALLBACK_DIR", "cc_records")
    os.makedirs(folder, exist_ok=True)
    row = dict(body, _logged_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(os.path.join(folder, table + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print("cc.py: CC_URL not set, wrote %s to %s/%s.jsonl" % (table, folder, table), file=sys.stderr)
    return row


def post(table, body):
    body = {k: v for k, v in body.items() if v is not None}
    if not os.environ.get("CC_URL"):
        return _fallback(table, body)
    return _request("POST", "/api/" + table, body)


def patch_case(case_id, body):
    body = {k: v for k, v in body.items() if v is not None}
    if not os.environ.get("CC_URL"):
        return _fallback("case_updates", dict(body, case_id=case_id))
    return _request("PATCH", "/api/cases/" + urllib.request.quote(case_id, safe=""), body)


def build_parser():
    p = argparse.ArgumentParser(prog="cc.py", description="Write Data Care records.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("case-new", help="open a case")
    s.add_argument("--case", required=True)
    s.add_argument("--client-email", required=True)
    s.add_argument("--kind", required=True, choices=KINDS)
    s.add_argument("--quote", type=float, help="quote in USD")
    s.add_argument("--stage", choices=STAGES)

    s = sub.add_parser("case-stage", help="move a case to a stage")
    s.add_argument("--case", required=True)
    s.add_argument("--stage", choices=STAGES)
    s.add_argument("--retry-count", type=int)
    s.add_argument("--quote", type=float)

    s = sub.add_parser("fragment", help="log a fragment")
    s.add_argument("--id", required=True, help="F-0001-001")
    s.add_argument("--case", required=True)
    s.add_argument("--source-file", required=True)
    s.add_argument("--location")
    s.add_argument("--type", required=True, choices=FRAGMENT_TYPES)
    s.add_argument("--confidence", type=float)
    s.add_argument("--notes")
    s.add_argument("--by", required=True, help="created_by: the agent name")

    s = sub.add_parser("rule", help="log a rule")
    s.add_argument("--id", required=True, help="R-0001-01")
    s.add_argument("--case", required=True)
    s.add_argument("--description", required=True)
    s.add_argument("--evidence", required=True, nargs="+", help="fragment or example ids")
    s.add_argument("--alternatives", type=_json_arg, help="JSON list, or @file.json")
    s.add_argument("--status", required=True, choices=RULE_STATUSES)

    s = sub.add_parser("gap", help="log a gap")
    s.add_argument("--id", required=True, help="G-0001-01")
    s.add_argument("--case", required=True)
    s.add_argument("--what", required=True)
    s.add_argument("--why")
    s.add_argument("--where-to-look", nargs="+")
    s.add_argument("--status", choices=GAP_STATUSES)

    s = sub.add_parser("verdict", help="log a Validation verdict")
    s.add_argument("--case", required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--pass", dest="passed", action="store_true")
    g.add_argument("--fail", dest="failed", action="store_true")
    s.add_argument("--results", required=True, type=_json_arg,
                   help='JSON list [{"example_id","expected","actual"}], or @file.json')
    s.add_argument("--retry-count", required=True, type=int)

    s = sub.add_parser("report-item", help="log one labeled report line")
    s.add_argument("--case", required=True)
    s.add_argument("--item", required=True)
    s.add_argument("--label", required=True, choices=LABELS)
    s.add_argument("--cites", required=True, nargs="+")

    s = sub.add_parser("event", help="log a step and its cost")
    s.add_argument("--case")
    s.add_argument("--agent", required=True)
    s.add_argument("--stage", required=True)
    s.add_argument("--message")
    s.add_argument("--cost", type=float, default=0.0, help="USD, from session_spend")
    s.add_argument("--human", action="store_true", help="a person had to step in")

    s = sub.add_parser("checkup", help="log a clinic checkup")
    s.add_argument("--case")
    s.add_argument("--team")
    s.add_argument("--repo-url")
    s.add_argument("--high", type=int, default=0)
    s.add_argument("--medium", type=int, default=0)
    s.add_argument("--low", type=int, default=0)

    sub.add_parser("ping", help="check the app is reachable and the token works")
    return p


def run(argv=None):
    a = build_parser().parse_args(argv)
    if a.cmd == "case-new":
        return post("cases", {"case_id": a.case, "client_email": a.client_email, "kind": a.kind,
                              "quote_usd": a.quote, "stage": a.stage})
    if a.cmd == "case-stage":
        if a.stage is None and a.retry_count is None and a.quote is None:
            raise CCError("case-stage needs --stage, --retry-count or --quote")
        return patch_case(a.case, {"stage": a.stage, "retry_count": a.retry_count, "quote_usd": a.quote})
    if a.cmd == "fragment":
        return post("fragments", {"fragment_id": a.id, "case_id": a.case, "source_file": a.source_file,
                                  "location": a.location, "type": a.type, "confidence": a.confidence,
                                  "notes": a.notes, "created_by": a.by})
    if a.cmd == "rule":
        return post("rules", {"rule_id": a.id, "case_id": a.case, "description": a.description,
                              "evidence": a.evidence, "alternatives": a.alternatives, "status": a.status})
    if a.cmd == "gap":
        return post("gaps", {"gap_id": a.id, "case_id": a.case, "what": a.what, "why": a.why,
                             "where_to_look": a.where_to_look, "status": a.status})
    if a.cmd == "verdict":
        return post("verdicts", {"case_id": a.case, "pass": bool(a.passed), "results": a.results,
                                 "retry_count": a.retry_count})
    if a.cmd == "report-item":
        return post("report_items", {"case_id": a.case, "item": a.item, "label": a.label, "cites": a.cites})
    if a.cmd == "event":
        return post("events", {"case_id": a.case, "agent": a.agent, "stage": a.stage, "message": a.message,
                               "cost_usd": a.cost, "human_stepped_in": a.human})
    if a.cmd == "checkup":
        return post("checkups", {"case_id": a.case, "team": a.team, "repo_url": a.repo_url,
                                 "high": a.high, "medium": a.medium, "low": a.low})
    if a.cmd == "ping":
        if not os.environ.get("CC_URL"):
            raise CCError("CC_URL is not set")
        return _request("GET", "/api/health")
    raise CCError("unknown command " + a.cmd)


def main(argv=None):
    try:
        out = run(argv)
    except CCError as e:
        print("cc.py: " + str(e), file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
