"""Public layout contract for the Excel recovery cases.

This file is safe to share with every agent. It says WHERE things live in the
workbook (sheet, row, column) and which cells are inputs versus calculated
outputs. It does not say HOW any output is calculated: that is the job of the
Reconstruction Agent, working from the public evidence.

A candidate workbook must keep this layout: same sheet names, same row labels
in column A, quarters in columns B..I, totals in column J, assumptions in
Assumptions!B3:B7. Input cells must hold constants (or be left blank when there
is no evidence); calculated cells must hold formulas.
"""

from __future__ import annotations

QUARTERS = [
    "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025",
    "Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026",
]
QCOLS = list("BCDEFGHI")  # one column per quarter
TOTAL_COL = "J"

MODEL = "Model"
ASSUMPTIONS = "Assumptions"

# row -> (key, label, kind). kind is one of: input, money, ratio, count
MODEL_ROWS = {
    3: ("units", "Units sold", "input"),
    4: ("price", "List price per unit", "input"),
    5: ("gross", "Gross revenue", "money"),
    6: ("disc_rate", "Discount rate", "ratio"),
    7: ("discount", "Volume discount", "money"),
    8: ("net", "Net revenue", "money"),
    9: ("cogs", "Cost of goods sold", "money"),
    10: ("gp", "Gross profit", "money"),
    11: ("gm", "Gross margin %", "ratio"),
    12: ("opex", "Operating expenses", "input"),
    13: ("opinc", "Operating income", "money"),
    14: ("growth", "Net revenue growth vs prior quarter", "ratio"),
}

# Company B labels row 6 differently because its discount is not a single tier
# rate (see its public evidence). Same cell, different label.
ROW_LABEL_OVERRIDES = {
    "excel_b": {6: "Effective discount rate"},
}

ASSUMPTION_ROWS = {
    3: ("cogs_pct", "COGS %"),
    4: ("t1", "Tier 1 threshold (units per quarter)"),
    5: ("r1", "Tier 1 discount rate"),
    6: ("t2", "Tier 2 threshold (units per quarter)"),
    7: ("r2", "Tier 2 discount rate"),
}

# Total column: which rows carry a total in column J, and its kind.
TOTAL_ROWS = {3: "count", 5: "money", 6: "ratio", 7: "money", 8: "money",
              9: "money", 10: "money", 11: "ratio", 12: "money", 13: "money"}

CASES = {
    "excel_a": {"company": "Alderbank Outfitters (synthetic)", "workbook": "alderbank_model_damaged.xlsx"},
    "excel_b": {"company": "Brightwell Tool Hire (synthetic)", "workbook": "brightwell_model_damaged.xlsx"},
}


def row_label(case: str, row: int) -> str:
    return ROW_LABEL_OVERRIDES.get(case, {}).get(row, MODEL_ROWS[row][1])


def input_cells() -> list[tuple[str, str, str]]:
    """(sheet, cell, key) for every input cell."""
    cells = []
    for row, (key, _label, kind) in MODEL_ROWS.items():
        if kind == "input":
            for i, col in enumerate(QCOLS):
                cells.append((MODEL, f"{col}{row}", f"{key}[{i}]"))
    for row, (key, _label) in ASSUMPTION_ROWS.items():
        cells.append((ASSUMPTIONS, f"B{row}", key))
    return cells


def output_cells() -> list[tuple[str, str, int, str]]:
    """(sheet, cell, row, kind) for every calculated cell."""
    cells = []
    for row, (_key, _label, kind) in MODEL_ROWS.items():
        if kind == "input":
            continue
        for i, col in enumerate(QCOLS):
            if row == 14 and i == 0:
                continue  # first quarter has no prior quarter
            cells.append((MODEL, f"{col}{row}", row, kind))
    for row, kind in TOTAL_ROWS.items():
        cells.append((MODEL, f"{TOTAL_COL}{row}", row, kind))
    return cells


def as_json(case: str) -> dict:
    """The contract as plain data (written next to each public workbook)."""
    return {
        "case_id": case,
        "workbook": CASES[case]["workbook"],
        "sheets": [MODEL, ASSUMPTIONS],
        "quarters": dict(zip(QCOLS, QUARTERS)),
        "total_column": TOTAL_COL,
        "model_rows": {str(r): {"label": row_label(case, r), "kind": k}
                       for r, (_key, _l, k) in MODEL_ROWS.items()},
        "assumption_rows": {str(r): {"cell": f"B{r}", "label": l}
                            for r, (_key, l) in ASSUMPTION_ROWS.items()},
        "total_rows": {str(r): k for r, k in TOTAL_ROWS.items()},
        "rules_for_candidates": [
            "Keep sheet names, row labels (column A) and cell addresses unchanged.",
            "Input cells (kind=input and Assumptions!B3:B7) hold constants, never formulas.",
            "Calculated cells hold formulas that reference the input cells, so the model "
            "responds when inputs change. Pasted values are rejected.",
            "Model!B14 stays empty (no prior quarter).",
            "Leave a cell blank when no surviving evidence supports a value, and list it "
            "as unresolved in the manifest. Do not invent numbers.",
        ],
    }
