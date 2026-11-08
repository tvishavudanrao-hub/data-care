# Demo data (owner: Tvisha, @tvishavudanrao-hub)

Synthetic businesses only. Names, people and `example.com` addresses are invented.

## Public evidence: `data/public/`

These files are safe for every agent, including Rebuild.

| Case | Path | What it is |
|---|---|---|
| excel_a (main demo) | `data/public/excel_a/alderbank_model_damaged.xlsx` | 8-quarter model: formulas replaced by values, some cells blank or corrupted |
| | `data/public/excel_a/alderbank_erp_export_2025Q1-2026Q3.csv` | ERP export: units, list price, gross, discount, net for 7 quarters |
| | `data/public/excel_a/alderbank_board_report_Q3_2026.md` | Previous-quarter board report |
| | `data/public/excel_a/alderbank_cfo_model_rules.eml` | CFO email stating the business rules |
| | `data/public/excel_a/layout.json` | Layout contract: which cells are inputs and which are calculated |
| excel_b (different rule) | `data/public/excel_b/brightwell_*` | Same layout. Marginal discount tiers, COGS on gross revenue |
| code_a | `data/public/code_a/invoicing.py` | Invoicing script with the body of `compute_discount()` removed |
| | `data/public/code_a/invoices.csv` | 30 surviving invoices; row `INV-2026-0117` is unreadable (invalid bytes) |
| | `data/public/code_a/discounts.yml` | Tier and loyalty settings. The 10% cap is not in it |
| | `data/public/code_a/CHANGELOG_excerpt.md` | States the cap, inclusive tiers and rounding |
| scanner | `data/public/scanner_fixtures/` | Harmless EICAR test marker for Salvage's scanner (written locally, not committed) |
| | `data/public/MANIFEST.json` | Content hash of every public file |

### What the evidence supports

| Damaged cell | Supported by | Expected label |
|---|---|---|
| A `Model!D3` units Q3 2025 | ERP export (and total J3) | recovered |
| A `Model!I4` price Q4 2026 | inferred: gross I5 / units I3 | reconstructed and tested |
| A `Assumptions!B7` tier 2 rate | CFO email | recovered |
| A `Model!F12` opex Q1 2026 | **nothing**: the CFO says it is lost | unresolved |
| B `Model!E3`, `Model!G4` | ERP export | recovered |
| B `Assumptions!B5` tier 1 rate | CFO email | recovered |
| B `Model!I12` opex Q4 2026 | **nothing**: not closed yet | unresolved |
| Every formula row | CFO email + layout + surviving values | reconstructed and tested, once the verifier passes it |

**Company A:** whole-quarter tiers. The tier reached applies to all units; thresholds are inclusive. COGS is a % of net revenue.
**Company B:** marginal tiers. Only units above each threshold earn that tier's rate. COGS is a % of gross revenue.
A model built with A's rules fails on B.

## Who may receive what

| Agent | May receive | Must never receive |
|---|---|---|
| Salvage | `data/public/<case>/`, `data/public/scanner_fixtures/` | anything under `verify/hidden/` |
| Rebuild | `data/public/<case>/` (including `layout.json`), Salvage fragments | `verify/hidden/`, `data/generate.py`, `verify/selftest.py`, Validation verdict details, the repo as a whole |
| Validation | the public verifier code, the candidate, and the private bundle uploaded by Tvisha | none of the above restrictions apply |
| Recovery Manager / Comms / Deliverable | candidates, limited feedback JSON, report labels | `verify/hidden/`, private verdicts |

Gitignore alone is not isolation. Do not mount the repo into the Rebuild sandbox. Upload only the case folder from `data/public/`.

## Regenerating

`data/drivers.py` (seeded inputs) and `data/generate.py` (renderer) are public. The numbers come from the private oracle in `verify/hidden/oracle/`. That oracle is Tvisha's only and is not in git, so only Tvisha can regenerate:

```bash
pip install -r verify/requirements.txt
```

```bash
python -m data.generate --check
```

Everyone else uses the committed files. `--check` regenerates the data into a temp folder and compares it to `MANIFEST.json`.
