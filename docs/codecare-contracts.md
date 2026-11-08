# Data Care: contracts for the Reconstruction and Context tools

Data Care is an agent-run company (Naive Autonomous Company Hackathon, YC, Nov 7-8 2026) that rebuilds lost or damaged
business assets from what survives. Main demo: a financial model (.xlsx) whose formulas were pasted over as values
(plus a few blank cells and one #REF!). The agents rebuild the formulas from surviving values, a past board report,
an export CSV and a CFO email, then a separate Validation agent checks the rebuilt model on scenarios the rebuilder
never saw. Second demo: a deleted invoicing module (already covered by rebuild/backtest.py and rebuild/probe_diff.py).

These tools run inside a Naive agent sandbox: Python 3.8+ STANDARD LIBRARY ONLY (no openpyxl, no pandas, no formulas,
no network). Tests and fixture generators may use openpyxl and formulas (installed in this container only).

## Labels (exactly these four strings)
recovered | reconstructed and tested | reconstructed but untested | unresolved
- recovered: survived intact, or copied exactly from evidence (an export row, a report line).
- reconstructed and tested: rebuilt formula that reproduces every surviving value it can be checked against (at least one).
- reconstructed but untested: rebuilt, but there is no surviving value to check it against (e.g. a blank cell filled by its row's formula), OR it depends on a choice the client has not confirmed yet.
- unresolved: nothing reliable fits. Never guess.

## Ids
case C-0001, fragment F-0001-001, rule R-0001-01, gap G-0001-01 (case number without "C-" in child ids).

## evidence.json (written by context_scan.py, read by formula_infer.py)
{
  "case_id": "C-0001",
  "values":   [{"label": "Units sold", "period": "Q5", "value": 1200.0, "source": "sales_export.csv#row7", "fragment_id": "F-0001-012"}],
  "reported": [{"label": "Net revenue", "period": "Q3", "value": 48210.5, "source": "board_report_q3.csv#row3", "fragment_id": "F-0001-005"}],
  "rules":    [{"text": "Orders over $5,000 get 10% off.", "numbers": [5000.0, 0.10], "operator_hint": ">", "source": "cfo_email.eml#line12", "fragment_id": "F-0001-020"}]
}
- values: raw inputs found in exports (used to fill blank or broken INPUT cells, label recovered, cite the fragment).
- reported: computed figures reported elsewhere (used to TEST rebuilt formulas, e.g. a board report total for Q3).
- rules: rule statements in words with the numbers they contain (percent as fraction: 10% -> 0.10). operator_hint is one of ">", ">=", "<", "<=", or null.
- label/period matching is fuzzy: case-insensitive, punctuation and extra spaces ignored, "Q3" matches "Q3 2025" and "2025 Q3".

## fragments.json and gaps.json (context_scan.py output)
fragments: [{"fragment_id","source_file","location","type": "code"|"record"|"clue","confidence": 0..1,"notes"}]
gaps:      [{"gap_id","what","why","where_to_look": [ranked strings],"status": "open"}]

## formula_infer.py output folder (--out-dir)
- model.xlsx          the rebuilt workbook: original file with formulas injected into the cells that lost them; values,
                      styles and sheets otherwise unchanged; workbook set to recalculate on open.
- rules.json          [{"rule_id","description","cells": ["Model!C12:J12"],"formula_r1c1" or "formula_pattern","evidence": [cell refs / fragment ids],
                        "alternatives": [{"formula_pattern","differs_when"}],"status": one of the three non-recovered labels}]
- report_items.json   [{"item": "Model!E12 (Discount, Q3)","label": one of the four labels,"cites": [rule ids / fragment ids / cell refs]}]
- gaps.json           [{"gap_id","what","why","where_to_look","status":"open"}] for anything unresolved or missing
- question.json       null, or {"rule_id","question": one plain-English sentence the client can answer,"options":[...],"probe": {"input": ..., "outputs": [...]}}
- summary.json        {"status": "done" | "needs_client" | "failed","counts": {label: n},"formulas_rebuilt": n,"questions": n}
Re-run after the client answers with --answer R-0001-03=1 (index into options); the chosen reading is locked and cited as "client answer".

## Hand-off message between Naive agents (send_to_agent)
request: {"case_id":"C-0001","stage":"reconstruction","kind":"excel","files":["cases/C-0001/working/model.xlsx"],"note":"..."}
reply:   {"case_id":"C-0001","stage":"reconstruction","status":"done|needs_client|failed","outputs":["cases/C-0001/rebuilt/model.xlsx"],"question":null,"mismatches":[]}
Files live in the Naive file library under cases/<case_id>/{incoming,quarantine,working,evidence,rebuilt,report}/.
