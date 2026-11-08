"""Code candidate verifier (code_a: the invoicing script).

1. Static checks only on this machine (the file is parsed, never imported or run):
   compute_discount exists with the surviving signature; no process, network,
   file-system or dynamic-code calls inside it; the surviving functions are
   unchanged from the damaged original.
2. Held-out invoices run in an authorized Naive sandbox via verify.sandbox.
   Only inputs go into the sandbox; expected values stay here.
3. Outputs compared to the cent against independently computed expectations.

If the sandbox is unavailable the outcome is "untested", never pass.
"""

from __future__ import annotations

import ast
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from verify import retry, sandbox
from verify.excel_verifier import sha256
from verify.schema import RECOVERED, TESTED, UNRESOLVED, UNTESTED, Example, Item, Mismatch, Verdict

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = Path(os.environ.get("VERIFY_HIDDEN_DIR", Path(__file__).resolve().parent / "hidden"))
PUBLIC_ORIGINAL = ROOT / "data" / "public" / "code_a" / "invoicing.py"
UNREADABLE_ROW_ID = "INV-2026-0117"
SIGNATURE = ["subtotal", "total_units", "customer_tier", "config"]
BANNED_MODULES = {"os", "subprocess", "socket", "shutil", "sys", "importlib", "ctypes", "urllib", "http",
                  "requests", "pathlib", "pickle", "marshal", "builtins", "multiprocessing", "threading"}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "globals", "locals", "getattr",
                "setattr", "breakpoint"}
CENT = Decimal("0.01")


def static_scan(src: str) -> tuple[list[str], ast.FunctionDef | None, ast.Module | None]:
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} (line {exc.lineno})"], None, None
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "compute_discount"), None)
    findings = []
    if fn is None:
        return ["compute_discount is missing"], None, tree
    if [a.arg for a in fn.args.args] != SIGNATURE:
        findings.append(f"compute_discount signature changed: {[a.arg for a in fn.args.args]}")
    allowed = _original_imports()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            top_level = node in tree.body
            for n in names:
                root = n.split(".")[0]
                if root in BANNED_MODULES and not (top_level and root in allowed):
                    findings.append(f"unsafe import {n!r} (line {node.lineno})")
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            findings.append(f"unsafe call {node.func.id}() in compute_discount (line {node.lineno})")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            findings.append(f"dunder access .{node.attr} in compute_discount (line {node.lineno})")
    return findings, fn, tree


def _original_imports() -> set[str]:
    """Top-level imports of the surviving original are allowed (csv, sys, pathlib, ...)."""
    tree = ast.parse(PUBLIC_ORIGINAL.read_text())
    names = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module.split(".")[0])
    return names


def _surviving_unchanged(tree: ast.Module) -> list[str]:
    orig = ast.parse(PUBLIC_ORIGINAL.read_text())
    want = {n.name: ast.dump(n) for n in orig.body if isinstance(n, ast.FunctionDef) and n.name != "compute_discount"}
    have = {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    return [name for name, dump in want.items() if have.get(name) != dump]


def compare(cases: list[dict], outputs: dict) -> list[Example]:
    exs = []
    for c in cases:
        ex = Example(c["id"], c["pool"], c["tags"], "not_run")
        got = outputs.get(c["id"])
        if got is None:
            ex.result, ex.error = "error", "no output"
        elif "error" in got:
            ex.result, ex.error = "fail", got["error"]
            ex.mismatches.append(Mismatch("discount", "discount", c["expected"]["discount"], got["error"]))
        else:
            for k in ("discount", "net_total"):
                ex.n_checked += 1
                try:
                    ok = Decimal(got[k]).quantize(CENT) == Decimal(c["expected"][k]) and \
                        Decimal(got[k]) == Decimal(got[k]).quantize(CENT)  # must already be cents
                except (InvalidOperation, KeyError):
                    ok = False
                if not ok:
                    ex.mismatches.append(Mismatch(k, k, c["expected"][k], str(got.get(k))))
            ex.result = "fail" if ex.mismatches else "pass"
        exs.append(ex)
    return exs


def verify_code(case: str, candidate: Path, *, job_id: str, artifact_id: str, artifact_version: str,
                attempt: int, retry_count: int, runner=None, max_retries: int = retry.MAX_RETRIES) -> Verdict:
    candidate = Path(candidate)
    v = Verdict(job_id=job_id, case_id=case, artifact_id=artifact_id, artifact_version=artifact_version,
                artifact_sha256=sha256(candidate), attempt=attempt, retry_count=retry_count,
                max_retries=max_retries)
    v.engine = {"name": "naive-sandbox", "local_execution": False}
    v.reasons += retry.check_metadata(attempt, retry_count, max_retries)
    if retry.over_cap(retry_count, max_retries):
        v.outcome, v.next_action = "error", retry.ESCALATE
        v.reasons.append("not verified: retry cap exceeded")
        return v

    unreadable = Item(f"invoices.csv row {UNREADABLE_ROW_ID}", UNRESOLVED, "unresolved", [UNREADABLE_ROW_ID],
                      "row bytes unreadable; no other evidence for its values", ["invoices.csv"])
    src = candidate.read_text(errors="replace")
    findings, fn, tree = static_scan(src)
    fn_item = Item("invoicing.py: compute_discount", UNTESTED, "untested", ["compute_discount"],
                   evidence=["discounts.yml", "CHANGELOG_excerpt.md", "invoices.csv"])
    if findings:
        v.outcome = "fail"
        v.reasons.append("static checks failed; candidate quarantined and not executed")
        v.reasons += findings
        fn_item.label, fn_item.status, fn_item.reason = UNRESOLVED, "fail", "; ".join(findings)
        v.items += [fn_item, unreadable]
        v.next_action = retry.next_action(v.outcome, retry_count, max_retries)
        return v
    changed = _surviving_unchanged(tree)
    v.items.append(Item("invoicing.py: surviving functions", RECOVERED if not changed else UNRESOLVED,
                        "pass" if not changed else "fail", [],
                        "unchanged from the damaged original" if not changed
                        else f"originals altered: {', '.join(changed)}", ["data/public/code_a/invoicing.py"]))

    heldout = json.loads((HIDDEN / case / "heldout_cases.json").read_text())["cases"]
    retry_cases = [c for c in heldout if c["pool"] == "retry"]
    runner = runner or sandbox.get_runner()
    blocked = False

    def run_pool(cases):
        cases_input = {"cases": [{"id": c["id"], "input": c["input"]} for c in cases]}
        res = runner.run(sandbox.bundle(candidate, cases_input))
        v.engine["session_id"] = res.get("session_id")
        return compare(cases, res.get("outputs", {}))

    try:
        exs = run_pool(retry_cases)
        v.examples += exs
        ok = all(e.result == "pass" for e in exs) and not changed
        if ok:
            fin = run_pool([c for c in heldout if c["pool"] == "final"])
            for e in fin:
                e.tags = ["final"]
            v.examples += fin
            ok = all(e.result == "pass" for e in fin)
            if not ok:
                v.reasons.append("failed fresh final acceptance checks")
        if ok:
            v.outcome = "pass"
            fn_item.label, fn_item.status = TESTED, "pass"
            fn_item.reason = "held-out invoices pass; does not prove the original source was recovered verbatim"
        else:
            v.outcome = "fail"
            fn_item.label, fn_item.status = UNRESOLVED, "fail"
            fn_item.reason = f"failed {sum(e.result != 'pass' for e in v.examples)} held-out check(s)"
    except sandbox.SandboxUnavailable as exc:
        blocked = True
        v.outcome = "untested"
        v.reasons.append(f"integration blocked: {exc}")
        fn_item.reason = "static checks pass; behaviour not tested because the Naive sandbox is unavailable"
        v.examples += [Example(c["id"], c["pool"], c["tags"], "not_run") for c in heldout]
    fn_item.cells = ["compute_discount"]
    for e in v.examples:  # attach mismatches to the function item for feedback
        for mm in e.mismatches:
            mm.cell = "compute_discount"
    v.items += [fn_item, unreadable]
    v.next_action = retry.next_action(v.outcome, retry_count, max_retries, integration_blocked=blocked)
    return v
