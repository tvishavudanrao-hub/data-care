"""Where verdicts go.

  private full verdict -> verify/hidden/results/<dataset>/<verdict_id>.json   (Validation only)
  limited feedback     -> verify/out/feedback/<verdict_id>.json               (safe for Recovery Manager)
  Code Care records    -> naive/lib/cc.py -> Code Care app -> Neon            (shared, team-readable)

Agents never connect to Neon directly (app/AGENTS.md); they write through the
Code Care app with cc.py. cc.py needs CC_URL and CC_API_TOKEN (Naive vault).
Without CC_URL, cc.py appends JSON Lines to CC_FALLBACK_DIR instead, and we
report that honestly rather than claiming a database write.

What goes into the SHARED verdicts table (db/schema.sql: case_id, pass,
results, retry_count): pass is true only for outcome "pass". `results` holds
one entry per check with its result and the number of failing cells. Expected
and actual values are written as "withheld": the table is readable by the
whole team and the board, and the expected values are the hidden suite.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from verify.schema import Verdict

VERIFY_DIR = Path(__file__).resolve().parent
ROOT = VERIFY_DIR.parent
HIDDEN = Path(os.environ.get("VERIFY_HIDDEN_DIR", VERIFY_DIR / "hidden"))
OUT = Path(os.environ.get("VERIFY_OUT_DIR", VERIFY_DIR / "out"))
CC_PATH = Path(os.environ.get("CC_PY", ROOT / "naive" / "lib" / "cc.py"))
WITHHELD = "withheld (private to Validation)"


def write_local(v: Verdict) -> dict[str, Path]:
    priv = HIDDEN / "results" / v.case_id / f"{v.verdict_id}.json"
    priv.parent.mkdir(parents=True, exist_ok=True)
    priv.write_text(json.dumps(v.to_private(), indent=2) + "\n")
    fb = OUT / "feedback" / f"{v.verdict_id}.json"
    fb.parent.mkdir(parents=True, exist_ok=True)
    fb.write_text(json.dumps(v.to_feedback(), indent=2) + "\n")
    return {"private": priv, "feedback": fb}


def _cc():
    spec = importlib.util.spec_from_file_location("cc", CC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shared_results(v: Verdict) -> list[dict]:
    """The `results` jsonb for the shared verdicts table. No hidden values."""
    rows = [{"example_id": "_outcome", "result": v.outcome, "expected": WITHHELD, "actual": WITHHELD,
             "verdict_id": v.verdict_id, "dataset": v.case_id, "artifact_version": v.artifact_version,
             "artifact_sha256": v.artifact_sha256, "attempt": v.attempt, "next_action": v.next_action}]
    for e in v.examples:
        # final-pool ids are not even named, so repeated attempts learn nothing about them
        eid = "fresh-final-check" if e.pool == "final" else e.example_id
        rows.append({"example_id": eid, "pool": e.pool, "result": e.result,
                     "failed_cells": len(e.mismatches), "expected": WITHHELD, "actual": WITHHELD})
    return rows


def write_cc(v: Verdict, case_id: str, *, report_items: bool) -> dict:
    """Write the verdict (and, at the end of the loop, the labeled report items) via cc.py.

    case_id is the Code Care case (C-0001); v.case_id is our dataset id (excel_a).
    Returns a status dict; never raises for a write failure.
    """
    status: dict = {"via": "cc.py"}
    try:
        cc = _cc()
    except (OSError, ImportError) as exc:
        return {**status, "written": False, "error": f"cannot load cc.py: {exc}"}
    target = "app" if os.environ.get("CC_URL") else f"local fallback {os.environ.get('CC_FALLBACK_DIR', 'cc_records')}/"
    status["target"] = target
    try:
        cc.post("verdicts", {"case_id": case_id, "pass": v.outcome == "pass",
                             "results": shared_results(v), "retry_count": v.retry_count})
        n = 0
        if report_items:
            for it in v.items:
                cites = it.evidence or [it.item_id]
                cc.post("report_items", {"case_id": case_id, "item": it.item_id, "label": it.label,
                                         "cites": cites})
                n += 1
        cc.post("events", {"case_id": case_id, "agent": "validation", "stage": "validation",
                           "message": f"attempt {v.attempt}: {v.outcome} -> {v.next_action}",
                           "cost_usd": 0.0, "human_stepped_in": False})
        status.update(written=True, report_items=n,
                      note="database write via the Code Care app" if target == "app"
                      else "NOT in Neon: CC_URL not set, cc.py wrote JSON Lines locally")
    except Exception as exc:  # noqa: BLE001 - report, never claim success
        status.update(written=False, error=f"{type(exc).__name__}: {exc}")
    return status
