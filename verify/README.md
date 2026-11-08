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

To ship the verifier to Naive, pack the public code (never `verify/hidden/`) and upload it to the shared `tools` folder:

```bash
python -m verify.pack
```

```bash
vetta file upload --file validation_tools.zip --folder tools --scope published
```


From a Naive agent, using the hand-off in `docs/codecare-contracts.md`:

```bash
VERIFY_IN_NAIVE_SANDBOX=1 python -m verify.handoff --request incoming/request.json --files-root incoming --out-dir validation_out --cc
```

- **Request:** `{case_id, stage, kind, files, note}` plus the optional `retry_count`, `dataset` and `artifact_version`. The job-object spelling (`job_id`, `asset_type`) also works.
- **Reply:** `{case_id, stage, status, outcome, next_action, outputs, question, mismatches, retry_count}`. The `mismatches` list has only item, label, status, failing check tags and counts.
- **Which private suite to use:** the request's `dataset` field. Failing that, a `VERIFY_CASE_MAP` json file (`{"C-0001": "excel_a"}`). Failing that, the company name in `Model!A1`.
- **Manifest:** built from Reconstruction's `rules.json` (rule ids and evidence per row) and `report_items.json` (unresolved cells).
- **`VERIFY_IN_NAIVE_SANDBOX=1`:** declares that the process is inside the Validation agent's Naive sandbox, so the code case runs there. Never set it on a laptop.

Directly, for testing:

```bash
python -m verify.cli excel --case excel_a --candidate cand.xlsx --job-id C-0001 --artifact-id A --artifact-version v1 --attempt 1 --retry-count 0 [--manifest m.json] [--cc-case C-0001 --final-report]
```

```bash
python -m verify.cli code --case code_a --candidate invoicing.py --job-id C-0001 --artifact-id A --artifact-version v1 --attempt 1 --retry-count 0
```

- **stdout:** the limited feedback JSON.
- **Full verdict:** `verify/hidden/results/<dataset>/<verdict_id>.json`.
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
| Code Care records (Neon) | Writes go through `naive/lib/cc.py` to Andy's app, never straight to Neon (see `app/AGENTS.md`). Each attempt writes a `verdicts` row (`pass`, `retry_count`, and `results` with expected and actual "withheld") and an `events` row. The final outcome (pass or escalation) also writes `report_items`. **Tested against the app running locally with its in-memory database.** Not yet against Neon: that needs `CC_URL` and `CC_API_TOKEN` in the vault. Without `CC_URL`, cc.py writes JSON Lines and the reply says "NOT in Neon". |
| Shared schema gap | `verdicts.pass` is a boolean, so error and untested are stored as `pass=false`, with the real outcome in `results[0]` (`example_id: "_outcome"`). |
| Naive sandbox (code case) | Inside the Validation agent's sandbox: `InSandboxRunner`, which uses a temp folder, a timeout, and inputs only. From outside: `NaiveSandboxRunner` via vetta. **Neither has been run against Naive yet.** |
| Sandbox packages | The Excel verifier needs `openpyxl` and `formulas`. Balthazar's contract says the sandboxes have the standard library only. If pip isn't available there, the hand-off replies `blocked_integration_escalate_to_human`. **This needs a test on Naive.** |
| Private results | `verify/hidden/results/` lives in the sandbox and disappears with it. The shared record keeps only the limited view. |
| Naive agent | `naive/agents/validation/validation.agent.yaml` uses the teammates' export format, with web tools off. **Not deployed.** The skill is `naive/skills/validation-harness/SKILL.md`. |
