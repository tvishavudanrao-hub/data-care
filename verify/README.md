# Validation (owner: Tvisha, @tvishavudanrao-hub)

This folder verifies rebuilt candidates against private held-out checks. It records a verdict and returns limited feedback to the Recovery Manager. It never repairs a candidate.

## Setup

```bash
pip install -r verify/requirements.txt
```

The private bundle is needed for any verification. It holds `verify/hidden/`: the oracle, answer keys, held-out scenarios, expected outputs and fixtures. It is gitignored and lives only with Tvisha and the Validation agent's sandbox. To rebuild it:

```bash
python -m verify.hidden.oracle.build_private
```

To run the self-test against the known fixtures:

```bash
python -m verify.selftest
```

## Run

```bash
python -m verify.cli excel --case excel_a --candidate cand.xlsx --job-id J --artifact-id A --artifact-version v1 --attempt 1 --retry-count 0 [--manifest m.json] [--neon]
```

```bash
python -m verify.cli code --case code_a --candidate invoicing.py --job-id J --artifact-id A --artifact-version v1 --attempt 1 --retry-count 0
```

- **stdout:** the limited feedback JSON.
- **Full verdict:** `verify/hidden/results/<case>/<verdict_id>.json`.
- **Exit code:** 0 pass, 1 fail, 2 error or untested.

## Contracts

### Candidate in, from the Recovery Manager

- **Excel:** a `.xlsx` that keeps the layout in `data/public/<case>/layout.json`, plus an optional manifest:
  ```json
  {"case_id": "excel_a", "unresolved": ["Model!F12"],
   "rules": {"7": {"rule_id": "R-7", "evidence": ["frag_12", "frag_31"]}},
   "needs_signoff": ["9"]}
  ```
  Rule and fragment ids follow the Rule and Fragment records in `CLAUDE.md`. They are cited in the report.
  Rows listed in `needs_signoff` stay "reconstructed but untested" until approved.
- **Code:** the full `invoicing.py`, keeping `compute_discount(subtotal, total_units, customer_tier, config) -> Decimal`.

### Verdict out (`verify/schema.py`)

It follows `CLAUDE.md`'s Verdict format (pass/fail, per-example results, expected vs actual, retry count), with these **additive proposals**:

- **`outcome`:** pass, fail, error or untested. The legacy `verdict` is "pass" only when `outcome` is "pass".
- **`items[]`:** per-item labels. Labels are exactly one of: recovered, reconstructed and tested, reconstructed but untested, unresolved.
- **Identifiers:** `job_id`, `case_id`, `artifact_id`, `artifact_version`, `artifact_sha256`, `attempt`, `retry_count`, `max_retries` and `next_action`.

The Verdict comes in two views:

- **Private:** `to_private()`, with every mismatch's expected and actual values.
- **Feedback:** `to_feedback()`, with labels, row status, failing check tags and counts. It never contains expected values or scenario inputs. Fresh final checks show only as `fresh-final-check`.

### Retry policy (`verify/retry.py`)

`attempt` is 1-based and `retry_count = attempt - 1`. The cap is 3 retries, so at most 4 attempts. A failure at `retry_count = 3` leads to `escalate_to_human`. A submission with `retry_count > 3` is refused.

The Coordinator's code was not available, so **confirm this with the Coordinator owner**. If the cap means 3 attempts in total, set `VERIFY_MAX_RETRIES=2`.

## What the Excel check does

1. **Layout contract.** Labels and cell addresses must match. Inputs must be constants and calculated cells must be formulas.
2. **Damaged inputs vs evidence.**
   - Supported by the evidence: "recovered" if stated outright, "reconstructed and tested" if inferred.
   - No evidence: "unresolved". A value typed into such a cell fails as invented.
3. **Surviving inputs are unchanged.** The candidate is only read from a temp copy, and its sha256 is checked before and after.
4. **Historical recalculation** with `formulas`, using an Excel-faithful ROUND. The candidate must reproduce the surviving values and the hidden ones. Cells that depend on an unresolved input are skipped.
5. **Retry pool.** Changed units, prices and cross-sheet assumptions; tier boundaries at t-1, t and t+1; zero revenue; opex changes. Pasted values fail here.
6. **Final pool.** Fresh scenarios, run only after steps 1 to 5 pass.

Money is compared to the cent (half-up) and ratios to within 1e-6. An unsupported function or an engine failure gives "untested" or "error", never "pass".

The answer keys were cross-checked in both `formulas` and LibreOffice against the Decimal oracle.

## Integration status

| Piece | Status |
|---|---|
| Neon | Adapter in `store.py`, reading `NEON_DATABASE_URL` from the vault. **Not written to.** Andy's schema was not available, so `neon/proposed_schema.sql` is a proposal. Map the column names in `store.SHARED_COLUMNS`. |
| Naive sandbox (code case) | Adapter in `sandbox.py`. **Not integration-tested.** Naive was unreachable, and there was no API key or agent id. Until it is configured, the code verdict is `untested` with `blocked_integration_escalate_to_human`. Only inputs enter the sandbox; expected values stay with Validation. |
| Naive agent | `naive/agents/validation/validation.agent.yaml` is a **template**, not an export. `SKILL.md` is ready. |
