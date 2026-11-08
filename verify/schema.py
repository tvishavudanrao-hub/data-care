"""Verdict and feedback records produced by the Validation Agent.

Based on the shared Verdict format in CLAUDE.md ("pass or fail, per-example
results, each mismatch with expected and actual values, retry count").
Additive extensions, proposed on the board before anyone relies on them:

  outcome      pass | fail | error | untested   (CLAUDE.md only had pass/fail;
               `verdict` keeps that legacy field and is "pass" only when outcome
               is "pass", so error/untested can never read as a pass)
  items        per-item labels using exactly the four report labels
  attempt / retry_count / max_retries / next_action
  artifact     id, version, sha256 of the candidate as received

Two views of one verdict:
  * Verdict (private, full): expected vs actual for every example. Stays with
    the Validation owner (verify/hidden/results/ only; never sent to cc.py).
  * Feedback (limited): what the Recovery Manager may forward to Rebuild:
    labels, row-level pass/fail, failing check TAGS and counts. No expected
    values, no scenario inputs, no hidden values.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

SCHEMA_VERSION = "verdict/v1+outcome-proposal"

RECOVERED = "recovered"
TESTED = "reconstructed and tested"
UNTESTED = "reconstructed but untested"
UNRESOLVED = "unresolved"
LABELS = (RECOVERED, TESTED, UNTESTED, UNRESOLVED)

OUTCOMES = ("pass", "fail", "error", "untested")


@dataclass
class Mismatch:
    cell: str
    label: str
    expected: str
    actual: str


@dataclass
class Example:
    example_id: str
    pool: str                    # historical | retry | final | heldout
    tags: list[str]
    result: str                  # pass | fail | error | not_run
    n_checked: int = 0
    mismatches: list[Mismatch] = field(default_factory=list)
    error: str | None = None


@dataclass
class Item:
    item_id: str
    label: str                   # one of LABELS
    status: str                  # pass | fail | untested | unresolved | invented | static
    cells: list[str] = field(default_factory=list)
    reason: str = ""
    evidence: list[str] = field(default_factory=list)   # fragment ids / rule ids / sources


@dataclass
class Verdict:
    job_id: str
    case_id: str
    artifact_id: str
    artifact_version: str
    artifact_sha256: str
    attempt: int
    retry_count: int
    max_retries: int
    outcome: str = "error"
    next_action: str = ""
    reasons: list[str] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    engine: dict = field(default_factory=dict)
    verdict_id: str = field(default_factory=lambda: f"vrd_{uuid.uuid4().hex[:16]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema: str = SCHEMA_VERSION

    @property
    def verdict(self) -> str:
        return "pass" if self.outcome == "pass" else "fail"

    def report(self) -> dict[str, list[str]]:
        """Report tiers; every entry cites its evidence (fragment/rule ids or sources)."""
        tiers = {label: [] for label in LABELS}
        for it in self.items:
            cite = f" [{', '.join(it.evidence)}]" if it.evidence else ""
            tiers[it.label].append(f"{it.item_id}{cite}" + (f" - {it.reason}" if it.reason else ""))
        return tiers

    def cell_items(self) -> list[dict]:
        """One report line per cell (per item when an item has no cells), so counts match the report.

        Item labels are per row; every cell in a row shares its row's label. Each line cites the
        same evidence as its row (rule ids, fragment ids or sources)."""
        from verify import layout as L  # local: schema stays usable for the code case too
        out = []
        for it in self.items:
            if not it.cells or not all("!" in c for c in it.cells):
                out.append({"item": it.item_id, "label": it.label, "cites": it.evidence or [it.item_id]})
                continue
            for ref in it.cells:
                sheet, cell = ref.split("!")
                col, row = cell[0], int(cell[1:])
                if sheet == L.MODEL and row in L.MODEL_ROWS:
                    what = L.row_label(self.case_id, row) if self.case_id in L.CASES else L.MODEL_ROWS[row][1]
                    when = "Total" if col == L.TOTAL_COL else dict(zip(L.QCOLS, L.QUARTERS)).get(col, col)
                    name = f"{ref} ({what}, {when})"
                elif sheet == L.ASSUMPTIONS and row in L.ASSUMPTION_ROWS:
                    name = f"{ref} ({L.ASSUMPTION_ROWS[row][1]})"
                else:
                    name = ref
                out.append({"item": name, "label": it.label, "cites": it.evidence or [it.item_id]})
        return out

    def counts(self) -> dict[str, int]:
        c = {label: 0 for label in LABELS}
        for ci in self.cell_items():
            c[ci["label"]] += 1
        return c

    def to_private(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict
        d["report"] = self.report()
        d["counts"] = self.counts()
        return d

    def to_feedback(self) -> dict:
        """Limited view for the Recovery Manager. Never includes expected values."""
        fb_items = []
        for it in self.items:
            failing = [e for e in self.examples if e.result in ("fail", "error")
                       and any(m.cell in it.cells for m in e.mismatches)]
            tags = sorted({t for e in failing for t in (["fresh-final-check"] if e.pool == "final" else e.tags)})
            entry = {"item_id": it.item_id, "label": it.label, "status": it.status,
                     "failed_checks": len(failing), "failed_check_tags": tags}
            if it.reason:
                entry["reason"] = it.reason
            fb_items.append(entry)
        return {"verdict_id": self.verdict_id, "job_id": self.job_id, "case_id": self.case_id,
                "artifact_id": self.artifact_id, "artifact_version": self.artifact_version,
                "attempt": self.attempt, "retry_count": self.retry_count, "max_retries": self.max_retries,
                "outcome": self.outcome, "verdict": self.verdict, "next_action": self.next_action,
                "reasons": self.reasons,
                "counts": self.counts(),
                "checks": {"run": sum(e.result != "not_run" for e in self.examples),
                           "failed": sum(e.result in ("fail", "error") for e in self.examples)},
                "items": fb_items}
