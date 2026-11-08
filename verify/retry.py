"""Retry policy for the rebuild-verify loop.

CLAUDE.md: the Coordinator "runs the rebuild-verify loop with a retry cap
(start at 3), escalates to a human". The Coordinator's code was not available
when this was written, so the interpretation below is ours and must be
confirmed with the Coordinator owner:

  attempt      1-based count of candidates submitted for one case in one job.
               attempt 1 is the first rebuild; it is not a retry.
  retry_count  number of re-submissions after a failed verdict = attempt - 1.
  cap          max_retries = 3 -> at most 4 verification attempts per case
               (1 initial + 3 retries). After the 4th failed attempt, or any
               attempt with retry_count > cap, the next action is escalation.

Set VERIFY_MAX_RETRIES if the Coordinator uses a different cap. If the
Coordinator meant "3 attempts in total", set VERIFY_MAX_RETRIES=2.
"""

from __future__ import annotations

import os

MAX_RETRIES = int(os.environ.get("VERIFY_MAX_RETRIES", "3"))

RETURN = "return_to_rebuild_via_recovery_manager"
ESCALATE = "escalate_to_human"
DELIVER = "send_to_deliverable_via_recovery_manager"
BLOCKED = "blocked_integration_escalate_to_human"


def check_metadata(attempt: int, retry_count: int, max_retries: int = MAX_RETRIES) -> list[str]:
    """Problems with the attempt metadata. Non-empty over-cap means: do not verify."""
    problems = []
    if attempt < 1:
        problems.append(f"attempt must be >= 1 (got {attempt})")
    if retry_count != attempt - 1:
        problems.append(f"retry_count {retry_count} != attempt-1 ({attempt - 1}); check Coordinator counting")
    if retry_count > max_retries:
        problems.append(f"over cap: retry_count {retry_count} > max_retries {max_retries}")
    return problems


def over_cap(retry_count: int, max_retries: int = MAX_RETRIES) -> bool:
    return retry_count > max_retries


def next_action(outcome: str, retry_count: int, max_retries: int = MAX_RETRIES,
                integration_blocked: bool = False) -> str:
    if outcome == "pass":
        return DELIVER
    if integration_blocked:
        return BLOCKED
    if over_cap(retry_count, max_retries) or retry_count >= max_retries:
        return ESCALATE
    return RETURN
