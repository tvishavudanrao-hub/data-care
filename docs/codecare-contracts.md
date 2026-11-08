# Data Care: contracts for the Reconstruction and Context tools

Data Care is an agent-run company (Naive Autonomous Company Hackathon, YC, Nov 7-8 2026) that rebuilds lost or damaged
business assets from what survives. Main demo: a financial model (.xlsx) whose formulas were pasted over as values
(plus a few blank cells and one #REF!). The agents rebuild the formulas from surviving values, a past board report,
an export CSV and a CFO email, then a separate Validation agent checks the rebuilt model on scenarios the rebuilder
never saw. Second demo: a deleted invoicing module (covered by naive/lib/backtest.py and naive/lib/probe_diff.py).

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
Each agent mints ids in its own range, because the app upserts on id and a clash silently overwrites a row:
- Context: fragments F-<n>-001 to 899, gaps G-<n>-01 to 49.
- Reconstruction (formula_infer.py): rules R-<n>-01 and up, gaps G-<n>-51 to 89.
- Forensics: fragments F-<n>-901 to 999, gaps G-<n>-91 to 99 (or G-<n>-901 and up).

## Who logs which records (cc.py)
- Recovery Manager: cases and their stage changes. Everyone: one event per step, with cost.
- Forensics and Context: fragments and gaps. Reconstruction: rules and the gaps it opens.
- Validation: verdicts (with outcome) and report_items. Reconstruction does not log report_items.

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
Optional fields (added Nov 7; readers must ignore fields they do not know, and none of the fields above changed):
- values[] / reported[] "source_label": the label as the source wrote it ("list price"); "label" is the model's row label it maps to ("List price per unit"), by word overlap when needed.
- rules[] "context": the numbered item or heading the rule sits under ("2. Volume discount is decided per quarter on that quarter's total units."), or null.
- rules[] "row_hint": the model row label the rule talks about ("Volume discount"), or null.
- rules[] "scope": "whole" (the tier rate applies to the whole quarter) or "marginal" (only the units above each threshold, like tax brackets); present only when the text says so.
- rules[] "base": "net revenue" or "gross revenue" when the text says a percent is of that base; present only when stated.
- rules[] "zero_denominator": 0 when the text says a zero denominator shows 0% (wrap the division in IF(den=0,0,...)); present only when stated.
- rules[] "references_assumptions": true when the text says the numbers live on / should be referenced from the Assumptions tab; present only when stated.
- rules[] may have "numbers": [] for a rule in words with no numbers ("Net revenue is gross minus discount."); operator_hint is then null.
- top-level "known_missing": [{"label", "period", "source", "fragment_id", "source_label", "text"}]: figures the client says do not exist ("I do not have Q1 2026 operating expenses ... leave it blank"); leave the cell blank, label it unresolved and cite the fragment. Each also appears in gaps.json.

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
- manifest.json       for the Validation checker: {"case_id","unresolved":["Model!F12"],"rules":{"<row>":{"rule_id","evidence":[...]}},"needs_signoff":[rows]}
- summary.json        {"status": "done" | "needs_client" | "failed","counts": {label: n},"formulas_rebuilt": n,"questions": n}
Re-run after the client answers with --answer R-0001-03=1 (index into options); the chosen reading is locked and cited as "client answer".

## Hand-off message between Naive agents
The Recovery Manager starts each member's session with the request as the message. The member replies by ending its turn
with the reply JSON as its final message (not send_to_agent, not job objects).
request: {"case_id":"C-0001","stage":"reconstruction","kind":"excel","files":["C-0001-working/model.xlsx"],"note":"..."}
reply:   {"case_id":"C-0001","stage":"reconstruction","status":"done|needs_client|failed","outputs":["C-0001-rebuilt/model.xlsx"],"question":null,"mismatches":[]}
Validation's request adds "retry_count" (0 on the first check) and "dataset"; its reply adds "outcome" (pass|fail|error|untested)
and "next_action". On error or escalate_to_human the Recovery Manager asks a person (ask_operator) instead of re-sending to Reconstruction.

## Folders in the Naive file library
Library folder names cannot contain "/", so each case uses one flat folder per stage:
<case_id>-incoming (what the client sent), <case_id>-quarantine (flagged files, never sent downstream), <case_id>-working
(clean copies from Forensics, including email.txt), <case_id>-evidence, <case_id>-rebuilt, <case_id>-report (e.g. C-0001-working).
In hand-off JSON a file is "<folder>/<file name>". Other folders: intake (raw mail before a case id exists), case-index (index.json).
<case_id>-evidence holds Context's evidence.json, fragments.json, gaps.json, inventory.md and Forensics' damage_report.json,
forensics_fragments.json, forensics_gaps.json. Files are uploaded with --scope published.

## The tools folder (shared code, fetched with find_files + fetch_file, never retyped)
context_scan.py, formula_infer.py, backtest.py, probe_diff.py, reconcile.py (Balthazar); forensics_scan.py, forensics_checkup.py
(Nash); cc.py (Andrei). Whoever merges a change to one of these re-uploads it. Hidden validation data never goes in tools.
