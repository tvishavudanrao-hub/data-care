"""Hand-off adapter between the Naive agents and the verifier.

Speaks the message format in docs/codecare-contracts.md:

  request (from Recovery Manager, via send_to_agent):
    {"case_id": "C-0001", "stage": "validation", "kind": "excel" | "code",
     "files": ["cases/C-0001/rebuilt/model.xlsx", "cases/C-0001/rebuilt/rules.json", ...],
     "note": "...",
     # optional extras this adapter understands:
     "dataset": "excel_a", "retry_count": 1, "artifact_version": "v2"}
  The job-object spelling in the agents' system prompts is accepted too
  (job_id -> case_id, asset_type -> kind).

  reply (to Recovery Manager):
    {"case_id": "C-0001", "stage": "validation", "status": "done" | "failed",
     "outcome": "pass" | "fail" | "error" | "untested", "next_action": "...",
     "outputs": ["cases/C-0001/report/validation_feedback.json"], "question": null,
     "mismatches": [limited: item, label, failed_check_tags, failed_checks], "retry_count": n}

The Validation agent fetches the listed files from the Naive file library into
--files-root (fetch_file), runs this, then publishes <out-dir>/validation_feedback.json
to cases/<case_id>/report/ (publish_file) and sends the reply. No expected
values ever appear in the reply, the feedback file or the shared records.

    python -m verify.handoff --request request.json --files-root ./incoming --out-dir ./validation_out [--cc]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from verify import layout as L
from verify import retry

CELL = re.compile(r"(Model|Assumptions)!\$?([A-J])\$?(\d+)")
FEEDBACK_NAME = "validation_feedback.json"


class HandoffError(Exception):
    pass


def normalise(req: dict) -> dict:
    r = dict(req)
    r.setdefault("case_id", r.get("job_id"))
    r.setdefault("kind", r.get("asset_type"))
    if not r.get("case_id"):
        raise HandoffError("request has no case_id")
    if r.get("kind") not in ("excel", "code"):
        raise HandoffError(f"kind must be excel or code, got {r.get('kind')!r}")
    if not r.get("files"):
        raise HandoffError("request lists no files")
    return r


def resolve_dataset(req: dict, candidate: Path) -> str:
    """Which private suite to use. Request field > case map > workbook company name."""
    if req.get("dataset"):
        return req["dataset"]
    cmap = os.environ.get("VERIFY_CASE_MAP")
    if cmap and Path(cmap).exists():
        m = json.loads(Path(cmap).read_text())
        if req["case_id"] in m:
            return m[req["case_id"]]
    if req["kind"] == "code":
        return "code_a"
    import openpyxl
    title = str(openpyxl.load_workbook(candidate, read_only=True)["Model"]["A1"].value or "")
    for ds, info in L.CASES.items():
        if info["company"].split(" (")[0].split()[0].lower() in title.lower():
            return ds
    raise HandoffError("cannot tell which dataset this case is: add \"dataset\" to the request "
                       "or map the case id in VERIFY_CASE_MAP")


def _rows(cells: list[str]) -> set[int]:
    rows = set()
    for c in cells:
        m = re.match(r"Model!\$?[A-J]\$?(\d+)(?::\$?[A-J]\$?(\d+))?", c)
        if m:
            lo = int(m.group(1))
            hi = int(m.group(2) or lo)
            rows.update(range(lo, hi + 1))
    return rows


def manifest_from_rebuild(files: list[Path]) -> dict:
    """Build the verifier manifest from Reconstruction's rules.json / report_items.json."""
    man: dict = {"rules": {}, "unresolved": [], "needs_signoff": []}
    by_name = {p.name: p for p in files}
    if "rules.json" in by_name:
        for r in json.loads(by_name["rules.json"].read_text()):
            for row in _rows(r.get("cells", [])):
                man["rules"][str(row)] = {"rule_id": r.get("rule_id", ""),
                                          "evidence": [str(e) for e in r.get("evidence", [])]}
                # an unconfirmed client choice stays untested until approved
                if r.get("status") == "reconstructed but untested" and r.get("alternatives"):
                    man["needs_signoff"].append(str(row))
    if "report_items.json" in by_name:
        for it in json.loads(by_name["report_items.json"].read_text()):
            if it.get("label") == "unresolved":
                for sheet, col, row in CELL.findall(it.get("item", "")):
                    man["unresolved"].append(f"{sheet}!{col}{row}")
    man["needs_signoff"] = sorted(set(man["needs_signoff"]))
    return man


def prior_attempts(case_id: str) -> int:
    from verify.store import HIDDEN
    n = 0
    for p in (HIDDEN / "results").glob("*/*.json"):
        try:
            if json.loads(p.read_text()).get("job_id") == case_id:
                n += 1
        except (OSError, ValueError):
            continue
    return n


def handle(req: dict, files_root: Path, out_dir: Path, *, write_cc: bool) -> dict:
    req = normalise(req)
    files = [files_root / f for f in req["files"]]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise HandoffError(f"files not found under {files_root}: {missing} (fetch them from the file library first)")
    ext = ".xlsx" if req["kind"] == "excel" else ".py"
    cands = [f for f in files if f.suffix == ext]
    if len(cands) != 1:
        raise HandoffError(f"expected exactly one {ext} candidate in files, got {len(cands)}")
    candidate = cands[0]

    reasons = []
    if "retry_count" in req:
        retry_count = int(req["retry_count"])
    else:
        retry_count = prior_attempts(req["case_id"])
        reasons.append(f"retry_count not in request; using {retry_count} prior verdicts held by Validation "
                       "(Recovery Manager should send cases.retry_count)")
    artifact_id = next(f for f in req["files"] if (files_root / f) == candidate)
    meta = dict(job_id=req["case_id"], artifact_id=artifact_id,
                artifact_version=str(req.get("artifact_version") or f"attempt-{retry_count + 1}"),
        attempt=retry_count + 1, retry_count=retry_count)

    try:
        if req["kind"] == "excel":
            from verify.excel_verifier import verify_excel  # needs openpyxl + formulas
            dataset = resolve_dataset(req, candidate)
            v = verify_excel(dataset, candidate, manifest=manifest_from_rebuild(files), **meta)
        else:
            from verify.code_verifier import verify_code
            dataset = resolve_dataset(req, candidate)
            v = verify_code(dataset, candidate, **meta)
    except ImportError as exc:
        return {"case_id": req["case_id"], "stage": "validation", "status": "failed", "outcome": "error",
                "next_action": retry.BLOCKED, "outputs": [], "question": None, "mismatches": [],
                "retry_count": retry_count,
                "reasons": [f"verifier dependencies missing in this sandbox ({exc}); run "
                            "pip install -r verify/requirements.txt"]}
    v.reasons = reasons + v.reasons

    from verify import store
    store.write_local(v)
    fb = v.to_feedback()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / FEEDBACK_NAME).write_text(json.dumps(fb, indent=2) + "\n")
    reply = {
        "case_id": req["case_id"], "stage": "validation",
        "status": "done" if v.outcome == "pass" else "failed",
        "outcome": v.outcome, "next_action": v.next_action,
        "outputs": [f"cases/{req['case_id']}/report/{FEEDBACK_NAME}"],
        "question": None,
        "mismatches": [{k: it[k] for k in ("item_id", "label", "status", "failed_check_tags", "failed_checks")}
                       for it in fb["items"] if it["status"] not in ("pass", "unresolved")],
        "retry_count": retry_count,
        "reasons": v.reasons,
    }
    if write_cc:
        final = v.outcome == "pass" or v.next_action in (retry.ESCALATE, retry.BLOCKED)
        reply["stored"] = store.write_cc(v, req["case_id"], report_items=final)
    return reply


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True, type=Path)
    ap.add_argument("--files-root", type=Path, default=Path("."))
    ap.add_argument("--out-dir", type=Path, default=Path("validation_out"))
    ap.add_argument("--cc", action="store_true", help="write verdict/report items via naive/lib/cc.py")
    a = ap.parse_args(argv)
    try:
        reply = handle(json.loads(a.request.read_text()), a.files_root, a.out_dir, write_cc=a.cc)
    except HandoffError as exc:
        reply = {"stage": "validation", "status": "failed", "outcome": "error",
                 "next_action": retry.ESCALATE, "reasons": [str(exc)], "mismatches": []}
    print(json.dumps(reply, indent=2))
    return {"pass": 0, "fail": 1}.get(reply.get("outcome"), 2)


if __name__ == "__main__":
    sys.exit(main())
