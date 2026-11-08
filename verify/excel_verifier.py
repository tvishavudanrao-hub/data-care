"""Excel candidate verifier.

Input: a candidate workbook from the Recovery Manager, a case id and attempt
metadata. Expected results come from verify/hidden/<case>/expected.json, which
the private oracle computed independently of any candidate.

Checks, in order:
  1. layout contract (verify/layout.py): sheets, row labels, constants in input
     cells, formulas in calculated cells
  2. damaged inputs against the evidence class of each (recovered / inferred /
     no evidence). Values typed into a no-evidence cell fail as invented.
  3. surviving inputs unchanged (originals preserved)
  4. historical recalculation: reproduces surviving values and the values the
     Rebuild agent never saw
  5. retry pool: changed units, prices, cross-sheet assumptions, tier
     boundaries, zero revenue. Pasted values fail here.
  6. final pool: fresh scenarios, run only once 1-5 all pass

Engine failures and unsupported functions give outcome error/untested, never
pass. The candidate file is copied before use and its hash checked afterwards.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import openpyxl

from verify import engine, layout as L, retry
from verify.schema import (RECOVERED, TESTED, UNRESOLVED, UNTESTED, Example, Item, Mismatch,
                           Verdict)

HIDDEN = Path(os.environ.get("VERIFY_HIDDEN_DIR", Path(__file__).resolve().parent / "hidden"))
RATIO_TOL = Decimal("0.000001")
CENT = Decimal("0.01")
BOOK = "candidate.xlsx"
UNSUPPORTED_ERRORS = {"#NAME?", "#NULL!"}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_expected(case: str) -> dict:
    p = HIDDEN / case / "expected.json"
    if not p.exists():
        raise FileNotFoundError(f"private expectations missing: {p} (Validation owner only)")
    return json.loads(p.read_text())


def _num(v) -> Decimal | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return Decimal(str(float(v)))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _kind(ref: str) -> str:
    cell = ref.split("!")[1]
    col, row = cell[0], int(cell[1:])
    if col == L.TOTAL_COL:
        return L.TOTAL_ROWS[row]
    return L.MODEL_ROWS[row][2]


def _same(kind: str, expected: str, actual) -> bool:
    e = Decimal(expected)
    a = _num(actual)
    if a is None:
        return False
    if kind == "ratio":
        return abs(a - e) <= RATIO_TOL
    if kind in ("count",) or (kind == "input" and e == e.to_integral_value()):
        return a == e
    return a.quantize(CENT, ROUND_HALF_UP) == e.quantize(CENT, ROUND_HALF_UP)


def _fmt(v) -> str:
    if v is None:
        return "<blank>"
    return str(v)


def _is_error_value(v) -> str | None:
    s = str(v)
    if s.startswith("#") and (s.endswith("!") or s.endswith("?") or s == "#N/A"):
        return s
    return None


def _compare(exp_values: dict, sol: dict, skip: set, example: Example) -> set[str]:
    """Compare outputs; returns set of cells that hit an unsupported-function error."""
    unsupported = set()
    for sheet, cell, row, _kind_ in L.output_cells():
        ref = f"{sheet}!{cell}"
        if ref in skip or ref not in exp_values:
            continue
        key = engine.ref_key(BOOK, ref)
        actual = engine.scalar(sol[key]) if key in sol else None
        example.n_checked += 1
        err = _is_error_value(actual) if actual is not None else None
        if err in UNSUPPORTED_ERRORS:
            unsupported.add(ref)
            example.mismatches.append(Mismatch(ref, L.MODEL_ROWS[row][1], exp_values[ref], err))
            continue
        if not _same(_kind(ref), exp_values[ref], actual):
            example.mismatches.append(Mismatch(ref, L.MODEL_ROWS[row][1], exp_values[ref], _fmt(actual)))
    return unsupported


def verify_excel(case: str, candidate: Path, *, job_id: str, artifact_id: str, artifact_version: str,
                 attempt: int, retry_count: int, manifest: dict | None = None,
                 max_retries: int = retry.MAX_RETRIES) -> Verdict:
    candidate = Path(candidate)
    digest = sha256(candidate)
    v = Verdict(job_id=job_id, case_id=case, artifact_id=artifact_id, artifact_version=artifact_version,
                artifact_sha256=digest, attempt=attempt, retry_count=retry_count, max_retries=max_retries)
    v.engine = {"name": "formulas", "round": "excel-faithful (15 sig. digits, half away from zero)"}
    manifest = manifest or {}

    meta = retry.check_metadata(attempt, retry_count, max_retries)
    v.reasons += meta
    if retry.over_cap(retry_count, max_retries):
        v.outcome, v.next_action = "error", retry.ESCALATE
        v.reasons.append("not verified: retry cap exceeded")
        return v
    if case not in L.CASES:
        v.outcome, v.next_action = "error", retry.ESCALATE
        v.reasons.append(f"unknown case {case}")
        return v

    exp = load_expected(case)
    hist = exp["historical"]
    work = Path(tempfile.mkdtemp(prefix="verify_"))
    try:
        local = work / BOOK
        shutil.copyfile(candidate, local)
        _verify(case, local, exp, hist, manifest, v)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if sha256(candidate) != digest:  # we never write to it; this proves it
            v.reasons.append("candidate file changed during verification")
            v.outcome = "error"
    v.next_action = retry.next_action(v.outcome, retry_count, max_retries)
    return v


def _verify(case, local: Path, exp: dict, hist: dict, manifest: dict, v: Verdict) -> None:
    # ---- 1. layout contract
    try:
        wb = openpyxl.load_workbook(local)  # formulas as text
    except Exception as exc:  # noqa: BLE001
        v.outcome = "error"
        v.reasons.append(f"cannot open workbook: {type(exc).__name__}")
        return
    problems = []
    for s in (L.MODEL, L.ASSUMPTIONS):
        if s not in wb.sheetnames:
            problems.append(f"missing sheet {s}")
    if problems:
        v.outcome = "error"
        v.reasons += [f"layout: {p}" for p in problems]
        return
    m, a = wb[L.MODEL], wb[L.ASSUMPTIONS]
    for row in L.MODEL_ROWS:
        if (m[f"A{row}"].value or "").strip() != L.row_label(case, row):
            problems.append(f"Model!A{row} label is {m[f'A{row}'].value!r}, expected {L.row_label(case, row)!r}")
    for row, (_k, label) in L.ASSUMPTION_ROWS.items():
        if (a[f"A{row}"].value or "").strip() != label:
            problems.append(f"Assumptions!A{row} label changed")
    if problems:
        v.outcome = "error"
        v.reasons += [f"layout: {p}" for p in problems]
        return

    def raw(ref):
        s, c = ref.split("!")
        return wb[s][c].value

    def is_formula(x):
        return isinstance(x, str) and x.startswith("=")

    fails, untested = False, False

    # ---- 2/3. inputs
    damaged = set(exp["damaged_cells"])
    evidence = exp["evidence"]
    surviving_bad, input_formula, surviving_cells = [], [], []
    for sheet, cell, _key in L.input_cells():
        ref = f"{sheet}!{cell}"
        val = raw(ref)
        if is_formula(val):
            input_formula.append(ref)
            continue
        if ref in evidence:
            cls, src = evidence[ref]["class"], evidence[ref]["source"]
            num = _num(val)
            if cls == "none":
                if val is None or (manifest.get("unresolved") and ref in manifest["unresolved"] and num is None):
                    v.items.append(Item(ref, UNRESOLVED, "unresolved", [ref],
                                        "no surviving evidence; left blank as required", [src]))
                else:
                    fails = True
                    v.items.append(Item(ref, UNRESOLVED, "invented", [ref],
                                        "value supplied for an item with no surviving evidence", [src]))
                continue
            if num is not None and _same("input", hist[ref], num):
                label = RECOVERED if cls == "direct" else TESTED
                v.items.append(Item(ref, label, "pass", [ref],
                                    "matches surviving evidence" if cls == "direct"
                                    else "inferred from surviving cells; reproduces them", [src]))
            else:
                fails = True
                v.items.append(Item(ref, UNRESOLVED, "fail", [ref],
                                    "evidence exists but the value was not recovered correctly", [src]))
        elif ref in damaged:
            pass  # damaged non-input cells are handled with their rows
        else:
            surviving_cells.append(ref)
            if not _same("input", hist[ref], val):
                surviving_bad.append(ref)
    if input_formula:
        fails = True
        v.reasons.append(f"input cells must hold constants: {', '.join(input_formula)}")
    if surviving_bad:
        fails = True
        v.reasons.append(f"surviving original inputs were altered: {', '.join(surviving_bad)}")
    v.items.insert(0, Item("surviving inputs", RECOVERED if not surviving_bad else UNRESOLVED,
                           "pass" if not surviving_bad else "fail",
                           surviving_cells, "unchanged from the damaged workbook" if not surviving_bad
                           else "originals altered", ["damaged workbook"]))

    static = {f"{s}!{c}" for s, c, _r, _k in L.output_cells() if not is_formula(raw(f"{s}!{c}"))}

    # ---- engine
    try:
        xl = engine.load(local)
    except engine.EngineError as exc:
        v.outcome = "error"
        v.reasons.append(f"calculation engine could not evaluate the workbook: {exc}")
        for row in _formula_rows():
            v.items.append(Item(_row_item(case, row), UNTESTED, "untested", _row_cells(row),
                                "not evaluated (engine error)", _row_evidence(manifest, row)))
        return

    all_inputs = {f"{s}!{c}" for s, c, _k in L.input_cells()}
    unsupported: set[str] = set()

    def run(example: Example, inputs: dict | None, expected: dict, skip: set):
        try:
            if inputs:
                known = {engine.ref_key(BOOK, r): float(x) for r, x in inputs.items()
                         if engine.ref_key(BOOK, r) in xl.dsp.data_nodes}
                sol = xl.calculate(inputs=known)
            else:
                sol = xl.calculate()
        except Exception as exc:  # noqa: BLE001
            example.result, example.error = "error", f"{type(exc).__name__}: {exc}"
            return
        unsupported.update(_compare(expected, sol, skip, example))
        if not example.mismatches:
            example.result = "pass"
        elif all(mm.actual in UNSUPPORTED_ERRORS for mm in example.mismatches):
            example.result, example.error = "error", "unsupported function; not evaluated"
        else:
            example.result = "fail"

    # ---- 4. historical
    h = Example("historical", "historical", ["historical"], "not_run")
    run(h, None, hist, set(exp["depends_on_unresolved"]))
    v.examples.append(h)

    # ---- 5. retry pool
    for sc in exp["scenarios"]:
        if sc["pool"] != "retry":
            continue
        ex = Example(sc["id"], "retry", sc["tags"], "not_run")
        run(ex, {r: x for r, x in sc["inputs"].items() if r in all_inputs}, sc["expected"], set())
        v.examples.append(ex)

    engine_errors = [e for e in v.examples if e.result == "error"]
    if unsupported or engine_errors:
        untested = True

    # ---- per-row items
    def row_status(row):
        cells = _row_cells(row)
        hit = [e for e in v.examples if any(mm.cell in cells for mm in e.mismatches)]
        if any(c in unsupported for c in cells) or engine_errors:
            return "untested", "contains a function the engine cannot evaluate" if unsupported else "engine error"
        if any(c in static for c in cells):
            return "static", "pasted values: cells do not respond when inputs change"
        if hit:
            return "fail", f"failed {len(hit)} check(s)"
        return "pass", ""

    rows_pass = True
    for row in _formula_rows():
        st, why = row_status(row)
        if st == "pass":
            label = UNTESTED if str(row) in manifest.get("needs_signoff", []) else TESTED
            if label == UNTESTED:
                why = "tests pass; awaiting client sign-off"
        elif st == "untested":
            label = UNTESTED
        else:
            label, rows_pass = UNRESOLVED, False
        v.items.append(Item(_row_item(case, row), label, st, _row_cells(row), why, _row_evidence(manifest, row)))
    if not rows_pass:
        fails = True

    # ---- 6. final pool, only for an otherwise clean candidate
    if not fails and not untested:
        for sc in exp["scenarios"]:
            if sc["pool"] != "final":
                continue
            ex = Example(sc["id"], "final", ["final"], "not_run")
            run(ex, {r: x for r, x in sc["inputs"].items() if r in all_inputs}, sc["expected"], set())
            v.examples.append(ex)
            if ex.result != "pass":
                fails = True
        if fails:
            v.reasons.append("failed fresh final acceptance checks")
            for it in v.items:
                if it.label == TESTED and any(mm.cell in it.cells for e in v.examples if e.pool == "final"
                                              for mm in e.mismatches):
                    it.label, it.status, it.reason = UNRESOLVED, "fail", "failed fresh final checks"
    else:
        for sc in exp["scenarios"]:
            if sc["pool"] == "final":
                v.examples.append(Example(sc["id"], "final", ["final"], "not_run"))

    if fails:
        v.outcome = "fail"
    elif untested:
        v.outcome = "untested"
        v.reasons.append("some behaviour could not be evaluated; not a pass")
    else:
        v.outcome = "pass"
        v.reasons.append("passed historical, changed-input and fresh final checks. Tested behaviour "
                         "matches; this does not prove the original formulas were recovered verbatim.")


def _formula_rows() -> list[int]:
    return [r for r, (_k, _l, kind) in L.MODEL_ROWS.items() if kind != "input"] + [12]


def _row_cells(row: int) -> list[str]:
    return [f"{s}!{c}" for s, c, r, _k in L.output_cells() if r == row]


def _row_item(case: str, row: int) -> str:
    if row == 12:
        return "Model row 12: Operating expenses total (J12)"
    return f"Model row {row}: {L.row_label(case, row)}"


def _row_evidence(manifest: dict, row: int) -> list[str]:
    r = manifest.get("rules", {}).get(str(row))
    if not r:
        return []
    return [r["rule_id"], *r.get("evidence", [])]
