"""Validation entry point (what the Validation Agent runs in its sandbox).

    python -m verify.cli excel --case excel_a --candidate cand.xlsx \
        --job-id job_123 --artifact-id art_9 --artifact-version v2 --attempt 2 --retry-count 1 \
        [--manifest manifest.json] [--neon]

    python -m verify.cli code --case code_a --candidate invoicing.py ...

stdout: the LIMITED feedback JSON (safe to return to the Recovery Manager).
The full private verdict is written under verify/hidden/results/ only.
Exit code: 0 pass, 1 fail, 2 error/untested.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verify import store
from verify.code_verifier import verify_code
from verify.excel_verifier import verify_excel


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["excel", "code"])
    ap.add_argument("--case", required=True)
    ap.add_argument("--candidate", required=True, type=Path)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--artifact-id", required=True)
    ap.add_argument("--artifact-version", required=True)
    ap.add_argument("--attempt", required=True, type=int)
    ap.add_argument("--retry-count", required=True, type=int)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--neon", action="store_true", help="also write to Neon (needs NEON_DATABASE_URL)")
    a = ap.parse_args(argv)
    meta = dict(job_id=a.job_id, artifact_id=a.artifact_id, artifact_version=a.artifact_version,
                attempt=a.attempt, retry_count=a.retry_count)
    if a.kind == "excel":
        manifest = json.loads(a.manifest.read_text()) if a.manifest else None
        v = verify_excel(a.case, a.candidate, manifest=manifest, **meta)
    else:
        v = verify_code(a.case, a.candidate, **meta)
    paths = store.write_local(v)
    fb = v.to_feedback()
    fb["stored"] = {"local_private": "verify/hidden/results/ (validation only)",
                    "local_feedback": str(paths["feedback"])}
    if a.neon:
        try:
            store.write_neon(v)
            fb["stored"]["neon"] = "written"
        except store.NeonUnavailable as exc:
            fb["stored"]["neon"] = f"NOT written: {exc}"
        except Exception as exc:  # noqa: BLE001 - report DB failures, never claim success
            fb["stored"]["neon"] = f"NOT written: {type(exc).__name__}: {exc}"
    print(json.dumps(fb, indent=2))
    return {"pass": 0, "fail": 1}.get(v.outcome, 2)


if __name__ == "__main__":
    sys.exit(main())
