"""Where verdicts go.

  private full verdict -> verify/hidden/results/<case>/<verdict_id>.json   (Validation only)
                       -> Neon private table, if configured                 (Validation role only)
  limited feedback     -> verify/out/feedback/<verdict_id>.json            (safe for Recovery Manager)
                       -> Neon shared verdicts table, if configured

Neon: the team's dev schema (Andy's) was not available when this was written.
Column names below follow CLAUDE.md's Verdict format and verify/neon/proposed_schema.sql.
Map them to the real schema by setting VERIFY_NEON_TABLE / VERIFY_NEON_PRIVATE_TABLE
and, if column names differ, editing SHARED_COLUMNS. The connection string is
read from NEON_DATABASE_URL, injected at runtime from the Naive vault; it is
never stored in the repo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from verify.schema import Verdict

VERIFY_DIR = Path(__file__).resolve().parent
HIDDEN = Path(os.environ.get("VERIFY_HIDDEN_DIR", VERIFY_DIR / "hidden"))
OUT = Path(os.environ.get("VERIFY_OUT_DIR", VERIFY_DIR / "out"))

SHARED_TABLE = os.environ.get("VERIFY_NEON_TABLE", "verdicts")
PRIVATE_TABLE = os.environ.get("VERIFY_NEON_PRIVATE_TABLE", "validation_private.verdict_details")
SHARED_COLUMNS = ("verdict_id", "job_id", "case_id", "artifact_id", "artifact_version", "artifact_sha256",
                  "attempt", "retry_count", "max_retries", "outcome", "verdict", "next_action",
                  "created_at", "feedback")


class NeonUnavailable(Exception):
    pass


def write_local(v: Verdict) -> dict[str, Path]:
    priv = HIDDEN / "results" / v.case_id / f"{v.verdict_id}.json"
    priv.parent.mkdir(parents=True, exist_ok=True)
    priv.write_text(json.dumps(v.to_private(), indent=2) + "\n")
    fb = OUT / "feedback" / f"{v.verdict_id}.json"
    fb.parent.mkdir(parents=True, exist_ok=True)
    fb.write_text(json.dumps(v.to_feedback(), indent=2) + "\n")
    return {"private": priv, "feedback": fb}


def _connect():
    url = os.environ.get("NEON_DATABASE_URL")
    if not url:
        raise NeonUnavailable("NEON_DATABASE_URL is not set (expected from the Naive vault at runtime)")
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise NeonUnavailable("psycopg is not installed: pip install 'psycopg[binary]'") from exc
    return psycopg.connect(url, connect_timeout=10)


def write_neon(v: Verdict) -> str:
    """Insert the shared row and the private detail row. Raises NeonUnavailable."""
    fb = v.to_feedback()
    row = {**{k: fb.get(k) for k in SHARED_COLUMNS if k in fb},
           "artifact_sha256": v.artifact_sha256, "created_at": v.created_at, "feedback": json.dumps(fb)}
    cols = [c for c in SHARED_COLUMNS if c in row]
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO {SHARED_TABLE} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                    [row[c] for c in cols])
        cur.execute(f"INSERT INTO {PRIVATE_TABLE} (verdict_id, detail) VALUES (%s, %s)",
                    [v.verdict_id, json.dumps(v.to_private())])
    return v.verdict_id
