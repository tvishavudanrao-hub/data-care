"""Self-test of the verifier against known fixtures (Validation owner only).

    python -m verify.selftest

The fixtures are explicit, known candidates built by the private oracle in
verify/hidden/fixtures/: one correct, the rest deliberately faulty. They are
verification fixtures, not demo "spontaneous failures".

Rebuilt code is never executed here. Code-case checks cover the static scan,
the real sandbox adapter (expected to report blocked until Naive is wired),
and the comparison layer fed with outputs computed by the private reference
implementation, not by any candidate.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from verify import retry
from verify.code_verifier import compare, verify_code
from verify.excel_verifier import HIDDEN, verify_excel
from verify.schema import LABELS, UNRESOLVED

FX = HIDDEN / "fixtures"
META = dict(job_id="selftest", artifact_version="v1", attempt=1, retry_count=0)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def excel(case, fixture, manifest=None, **meta):
    m = {**META, **meta}
    return verify_excel(case, FX / case / f"{fixture}.xlsx", artifact_id=fixture, manifest=manifest, **m)


def handoff_checks(man_a: dict) -> None:
    import os
    import shutil
    import tempfile
    import openpyxl
    from verify import handoff

    tmp = Path(tempfile.mkdtemp(prefix="handoff_"))
    old_env = {k: os.environ.get(k) for k in ("CC_URL", "CC_FALLBACK_DIR")}
    os.environ.pop("CC_URL", None)
    os.environ["CC_FALLBACK_DIR"] = str(tmp / "cc_records")
    try:
        inc = tmp / "incoming"
        reb = inc / "cases" / "C-0001" / "rebuilt"
        reb.mkdir(parents=True)
        wb = openpyxl.load_workbook(FX / "excel_a" / "correct.xlsx")
        wb["Model"]["A1"] = "Alderbank Outfitters quarterly model (recovered copy)"  # as Rebuild leaves it
        wb.save(reb / "model.xlsx")
        (reb / "rules.json").write_text(json.dumps([
            {"rule_id": "R-0001-03", "description": "whole-quarter tier discount", "cells": ["Model!B7:I7"],
             "evidence": ["F-0001-020"], "alternatives": [], "status": "reconstructed and tested"}]))
        (reb / "report_items.json").write_text(json.dumps([
            {"item": "Model!F12 (Operating expenses, Q1 2026)", "label": "unresolved", "cites": ["G-0001-01"]}]))
        req = {"case_id": "C-0001", "stage": "validation", "kind": "excel", "retry_count": 0,
               "files": ["cases/C-0001/rebuilt/model.xlsx", "cases/C-0001/rebuilt/rules.json",
                         "cases/C-0001/rebuilt/report_items.json"]}
        reply = handoff.handle(req, inc, tmp / "out", write_cc=True)
        check("handoff: contract request -> pass reply (dataset detected from workbook)",
              reply["outcome"] == "pass" and reply["status"] == "done", reply.get("reasons"))
        check("handoff: reply uses contract fields",
              {"case_id", "stage", "status", "outputs", "question", "mismatches"} <= set(reply))
        priv = json.loads(next((HIDDEN / "results" / "excel_a").glob("*.json")).read_text()) \
            if (HIDDEN / "results" / "excel_a").exists() else {}
        check("handoff: Rebuild rule ids are cited in the report",
              any("R-0001-03" in it.get("evidence", []) for it in priv.get("items", [])))
        recs = (tmp / "cc_records" / "verdicts.jsonl").read_text()
        exp = json.loads((HIDDEN / "excel_a" / "expected.json").read_text())
        hidden_vals = {exp["historical"][c] for c in exp["damaged_cells"] if c in exp["historical"]}
        hidden_vals |= {v for sc in exp["scenarios"] for v in list(sc["expected"].values())[:20]}
        check("handoff: shared verdict record withholds every hidden value",
              "withheld" in recs and not any(f'"{h}"' in recs for h in hidden_vals))
        check("handoff: no CC_URL is reported as NOT in Neon",
              "NOT in Neon" in reply["stored"].get("note", ""), reply.get("stored"))
        items = (tmp / "cc_records" / "report_items.jsonl").read_text().splitlines()
        check("handoff: final pass writes labeled report items", len(items) > 5 and
              all(json.loads(x)["label"] in LABELS for x in items))

        bad = dict(req, files=["cases/C-0001/rebuilt/model.xlsx"], retry_count=1)
        shutil.copy(FX / "excel_a" / "pasted_values.xlsx", reb / "model.xlsx")
        r2 = handoff.handle(dict(bad, dataset="excel_a"), inc, tmp / "out", write_cc=True)
        check("handoff: failing candidate -> failed reply, returned via Recovery Manager",
              r2["status"] == "failed" and r2["next_action"] == retry.RETURN and r2["mismatches"])
        check("handoff: mismatch list carries no expected values",
              all(set(m) == {"item_id", "label", "status", "failed_check_tags", "failed_checks"}
                  for m in r2["mismatches"]))
    finally:
        for k, val in old_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(HIDDEN / "results", ignore_errors=True)


def main() -> int:
    if not FX.exists():
        sys.exit("verify/hidden/fixtures missing: run python -m verify.hidden.oracle.build_private")
    man_a = json.loads((FX / "excel_a" / "correct.manifest.json").read_text())
    man_b = json.loads((FX / "excel_b" / "correct.manifest.json").read_text())

    v = excel("excel_a", "correct", man_a)
    check("A: correct candidate passes", v.outcome == "pass", v.outcome)
    check("A: correct candidate ran fresh final checks",
          any(e.pool == "final" and e.result == "pass" for e in v.examples))
    check("A: missing Q1 2026 opex stays unresolved",
          any(i.item_id == "Model!F12" and i.label == UNRESOLVED for i in v.items))
    check("A: every item uses one of the four labels", all(i.label in LABELS for i in v.items))
    fb = json.dumps(v.to_feedback())
    check("A: feedback carries no expected values", '"expected"' not in fb and "scenarios" not in fb)

    v = excel("excel_a", "wrong_discount_exclusive_tiers")
    check("A: wrong discount rule (exclusive tiers) fails", v.outcome == "fail", v.outcome)
    hist = next(e for e in v.examples if e.pool == "historical")
    check("A: ...even though it reproduces every historical number", hist.result == "pass")
    tags = {t for it in v.to_feedback()["items"] for t in it["failed_check_tags"]}
    check("A: ...caught by tier-boundary checks", "tier-boundary" in tags, sorted(tags))
    check("A: ...final pool withheld after a retry-pool failure",
          all(e.result == "not_run" for e in v.examples if e.pool == "final"))

    v = excel("excel_a", "pasted_values")
    hist = next(e for e in v.examples if e.pool == "historical")
    check("A: pasted historical values fail changed-input checks",
          v.outcome == "fail" and hist.result == "pass", v.outcome)
    check("A: ...rows flagged as static", any(i.status == "static" for i in v.items))

    v = excel("excel_a", "invented_missing_input")
    check("A: inventing the missing opex fails",
          v.outcome == "fail" and any(i.status == "invented" for i in v.items), v.outcome)

    v = excel("excel_a", "unsupported_function")
    check("A: unsupported function is untested, never pass", v.outcome == "untested", v.outcome)

    v = excel("excel_b", "correct", man_b)
    check("B: correct candidate passes with B's own rules", v.outcome == "pass", v.outcome)
    check("B: missing Q4 2026 opex stays unresolved",
          any(i.item_id == "Model!I12" and i.label == UNRESOLVED for i in v.items))
    v = excel("excel_b", "company_a_rules_on_b")
    check("B: company A's rules applied to B fail", v.outcome == "fail", v.outcome)
    v = excel("excel_b", "pasted_values")
    check("B: pasted values fail", v.outcome == "fail", v.outcome)

    v = excel("excel_a", "correct", man_a, attempt=4, retry_count=3)
    check("retry: 4th attempt failing would escalate", retry.next_action("fail", 3) == retry.ESCALATE)
    check("retry: 4th attempt (retry 3) is still verified", v.outcome == "pass", v.outcome)
    v = excel("excel_a", "correct", man_a, attempt=5, retry_count=4)
    check("retry: over cap is refused and escalated", v.outcome == "error" and v.next_action == retry.ESCALATE)
    check("retry: attempt 2 failure returns to rebuild", retry.next_action("fail", 1) == retry.RETURN)

    # ---- code case
    meta = {**META}
    v = verify_code("code_a", FX / "code_a" / "malicious_invoicing.py", artifact_id="malicious", **meta)
    check("code: unsafe candidate quarantined, not executed",
          v.outcome == "fail" and any("subprocess" in r for r in v.reasons), v.reasons[:2])
    v = verify_code("code_a", FX / "code_a" / "correct_invoicing.py", artifact_id="correct", **meta)
    check("code: no sandbox -> untested + blocked, never pass",
          v.outcome == "untested" and v.next_action == retry.BLOCKED, v.outcome)
    check("code: unreadable invoice row stays unresolved",
          any(i.item_id.endswith("INV-2026-0117") and i.label == UNRESOLVED for i in v.items))

    from verify.hidden.oracle import invoicing_ref
    cases = json.loads((HIDDEN / "code_a" / "heldout_cases.json").read_text())["cases"]

    def outputs(fn):
        out = {}
        for c in cases:
            i = c["input"]
            d = fn(Decimal(i["subtotal"]), i["total_units"], i["customer_tier"], i["config"])
            out[c["id"]] = {"discount": str(d), "net_total": str(Decimal(i["subtotal"]) - d)}
        return out

    def wrong(sub, units, tier, cfg):  # exclusive boundary, no cap, banker's rounding
        rate = Decimal(0)
        for t in cfg["volume_tiers"]:
            if units > t["min_units"]:
                rate = Decimal(str(t["rate"]))
        rate += Decimal(str(cfg["loyalty_bonus"].get(tier, 0)))
        return (sub * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

    exs = compare(cases, outputs(invoicing_ref.compute_discount))
    check("code compare: reference outputs pass every held-out case", all(e.result == "pass" for e in exs))
    exs = compare(cases, outputs(wrong))
    failed = {t for e in exs if e.result == "fail" for t in e.tags}
    check("code compare: wrong boundary/cap/rounding fails", {"tier-boundary", "cap", "rounding"} <= failed,
          sorted(failed))

    # ---- static scan: candidate code must not reach files in the shared sandbox
    from verify.code_verifier import static_scan
    sneaky = (FX / "code_a" / "correct_invoicing.py").read_text().replace(
        "CENT = Decimal(\"0.01\")", "CENT = Decimal(\"0.01\")\nLEAK = open('verify/hidden/code_a/heldout_cases.json').read()")
    check("code scan: module-level file read is flagged (not executed)",
          any("open()" in f for f in static_scan(sneaky)[0]))

    # ---- hand-off contract (docs/codecare-contracts.md) + cc.py fallback records
    handoff_checks(man_a)

    width = max(len(n) for n, _ok, _d in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}")
    bad = sum(not ok for _n, ok, _d in results)
    print(f"\n{len(results) - bad}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
