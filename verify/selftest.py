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

    width = max(len(n) for n, _ok, _d in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}")
    bad = sum(not ok for _n, ok, _d in results)
    print(f"\n{len(results) - bad}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
