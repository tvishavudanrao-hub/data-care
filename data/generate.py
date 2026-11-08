"""Seeded generator for the PUBLIC demo evidence.

    python -m data.generate            # (re)write data/public/
    python -m data.generate --check    # regenerate in a temp dir, compare to data/public/

This file renders public artifacts only: damaged workbooks, a board report, an
ERP CSV export, a CFO email, the damaged invoicing script and its surviving
records, and the scanner fixture. The numbers come from the Verify owner's
private oracle (verify/hidden/oracle/), which is NOT in git. Without it this
script stops; the committed data/public/ files are the source of truth for
everyone else.

All companies, people and addresses are synthetic (example.com domains).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import shutil
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.drivers import DEFAULT_SEED, drivers  # noqa: E402
from verify import layout as L  # noqa: E402

try:
    from verify.hidden.oracle import excel_models, invoicing_ref  # noqa: E402
except ImportError:  # pragma: no cover - expected on every machine but the Verify owner's
    excel_models = invoicing_ref = None

FIXED_TIME = datetime(2026, 10, 14, 9, 30)

# Damage applied to each workbook. Blank = cell emptied; corrupt = replaced by junk.
DAMAGE = {
    "excel_a": {
        "blank": ["Model!D3", "Model!F12", "Model!F13", "Model!G7", "Model!E9",
                  "Model!J8", "Model!J12", "Model!J13"],
        "corrupt": {"Model!H5": "#REF!", "Model!C11": "#####",
                    "Assumptions!B7": "#VALUE!", "Model!I4": "2?.4�"},
    },
    "excel_b": {
        "blank": ["Model!E3", "Model!I12", "Model!I13", "Model!D7", "Model!J10",
                  "Model!J12", "Model!J13"],
        "corrupt": {"Assumptions!B5": "#VALUE!", "Model!F8": "#N/A", "Model!G4": "3�.5?"},
    },
}

COMPANY = {
    "excel_a": {
        "name": "Alderbank Outfitters", "slug": "alderbank", "domain": "alderbank.example.com",
        "cfo": "Dana Okafor", "cfo_email": "dana.okafor@alderbank.example.com",
        "product": "trail packs and outdoor kit",
    },
    "excel_b": {
        "name": "Brightwell Tool Hire", "slug": "brightwell", "domain": "brightwell.example.com",
        "cfo": "Marek Lindqvist", "cfo_email": "marek.lindqvist@brightwell.example.com",
        "product": "tool and equipment hire",
    },
}

SCANNER_README = """# Scanner fixture (harmless)

`EICAR_TEST_MARKER_harmless.txt` holds the standard EICAR antivirus test
string. It is inert text that antivirus tools detect on purpose. It is not
malware. The Salvage agent's static scanner should flag and quarantine it.
**Never execute it.**

The file is not committed, because antivirus on teammates' machines would
quarantine it on checkout. `python -m data.generate` writes it locally
(Verify owner), or build it from the two halves in `data/generate.py`
(`EICAR_PARTS`). Its sha256 is listed in `data/public/MANIFEST.json`.
"""

EICAR_PARTS = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$", "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")


def _require_oracle() -> None:
    if excel_models is None:
        sys.exit("data/generate.py needs the private oracle in verify/hidden/oracle/ (Verify owner "
                 "only). Use the committed files in data/public/ instead.")


def _f(x) -> float:
    return float(x)


def _money(x: Decimal) -> str:
    return f"{x:,.2f}"


def _pct(x: Decimal, dp: int = 1) -> str:
    return f"{x * 100:.{dp}f}%"


# ---------------------------------------------------------------- Excel cases

def _historical(case: str):
    inp = drivers(case)
    return inp, excel_models.compute(case, inp)


def write_damaged_workbook(case: str, inp: dict, values: dict, path: Path) -> None:
    wb = openpyxl.Workbook()
    wb.properties.creator = COMPANY[case]["name"] + " finance"
    wb.properties.created = wb.properties.modified = FIXED_TIME
    m = wb.active
    m.title = L.MODEL
    a = wb.create_sheet(L.ASSUMPTIONS)
    bold = Font(bold=True)

    m["A1"] = f"{COMPANY[case]['name']} quarterly model (recovered copy)"
    m["A1"].font = bold
    m["A2"] = "Line item"
    for col, q in zip(L.QCOLS, L.QUARTERS):
        m[f"{col}2"] = q
    m[f"{L.TOTAL_COL}2"] = "Total"
    for c in m[2]:
        c.font = bold
    fmt = {"money": "#,##0.00", "ratio": "0.0%", "count": "#,##0", "input": None}
    for row, (key, _label, kind) in L.MODEL_ROWS.items():
        m[f"A{row}"] = L.row_label(case, row)
        for i, col in enumerate(L.QCOLS):
            ref = f"Model!{col}{row}"
            if kind == "input":
                v = inp[key][i]
                m[f"{col}{row}"] = int(v) if key == "units" else _f(v)
                m[f"{col}{row}"].number_format = "#,##0" if key == "units" else "#,##0.00"
            elif ref in values:
                m[f"{col}{row}"] = _f(values[ref])
                m[f"{col}{row}"].number_format = fmt[kind]
        tref = f"Model!{L.TOTAL_COL}{row}"
        if tref in values:
            m[f"{L.TOTAL_COL}{row}"] = _f(values[tref])
            m[f"{L.TOTAL_COL}{row}"].number_format = fmt[L.TOTAL_ROWS[row]]
    m.column_dimensions["A"].width = 38
    for col in L.QCOLS + [L.TOTAL_COL]:
        m.column_dimensions[col].width = 13

    a["A1"] = "Assumptions"
    a["A1"].font = bold
    a["A2"], a["B2"] = "Assumption", "Value"
    for row, (key, label) in L.ASSUMPTION_ROWS.items():
        a[f"A{row}"] = label
        v = inp[key]
        a[f"B{row}"] = int(v) if key in ("t1", "t2") else _f(v)
        a[f"B{row}"].number_format = "#,##0" if key in ("t1", "t2") else "0.0%"
    a.column_dimensions["A"].width = 40

    dmg = DAMAGE[case]
    for ref in dmg["blank"]:
        sheet, cell = ref.split("!")
        wb[sheet][cell].value = None
    for ref, junk in dmg["corrupt"].items():
        sheet, cell = ref.split("!")
        wb[sheet][cell].value = junk
    wb.save(path)


def write_csv_export(case: str, inp: dict, values: dict, path: Path) -> None:
    """ERP export run after Q3 2026 close: seven quarters, no opex or COGS."""
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["quarter", "units_sold", "list_price", "gross_revenue", "discount", "net_revenue"])
        for i, (col, q) in enumerate(zip(L.QCOLS[:7], L.QUARTERS[:7])):
            w.writerow([q, inp["units"][i], f"{inp['price'][i]:.2f}",
                        f"{values[f'Model!{col}5']:.2f}", f"{values[f'Model!{col}7']:.2f}",
                        f"{values[f'Model!{col}8']:.2f}"])


def write_board_report(case: str, inp: dict, values: dict, path: Path) -> None:
    c = COMPANY[case]
    v = values
    fy = {k: sum((v[f"Model!{col}{r}"] for col in L.QCOLS[:4]), Decimal(0))
          for k, r in (("net", 8), ("gp", 10), ("opinc", 13))}
    fy_opex = sum((Decimal(str(o)) for o in inp["opex"][:4]), Decimal(0))
    q3 = "H"
    lines = [
        f"# {c['name']}: Board report, Q3 2026",
        "",
        f"Prepared by {c['cfo']} (CFO) for the board meeting of 14 October 2026. Synthetic demo data.",
        "",
        "## Q3 2026 at a glance",
        "",
        f"- Units sold: {inp['units'][6]:,}",
        f"- Net revenue: ${_money(v[f'Model!{q3}8'])} ({_pct(v[f'Model!{q3}14'])} vs Q2 2026)",
        f"- Gross margin: {_pct(v[f'Model!{q3}11'])}",
        f"- Operating income: ${_money(v[f'Model!{q3}13'])}",
        "",
        "## FY2025 summary",
        "",
        "| Metric | FY2025 |",
        "|---|---|",
        f"| Net revenue | ${_money(fy['net'])} |",
        f"| Gross profit | ${_money(fy['gp'])} |",
        f"| Gross margin | {_pct(fy['gp'] / fy['net'])} |",
        f"| Operating expenses | ${_money(fy_opex)} |",
        f"| Operating income | ${_money(fy['opinc'])} |",
        "",
        "## Net revenue by quarter",
        "",
        "| Quarter | Net revenue | Gross margin | Growth vs prior quarter |",
        "|---|---|---|---|",
    ]
    for i, (col, q) in enumerate(zip(L.QCOLS[:7], L.QUARTERS[:7])):
        g = "n/a" if i == 0 else _pct(v[f"Model!{col}14"])
        lines.append(f"| {q} | ${_money(v[f'Model!{col}8'])} | {_pct(v[f'Model!{col}11'])} | {g} |")
    lines += ["", "## Notes", ""]
    if case == "excel_a":
        lines += [
            "- Volume discounts follow the tiers on the model's Assumptions tab and are applied per quarter.",
            "- COGS held at 38% of net revenue all year under the current supplier agreement.",
        ]
    else:
        lines += [
            "- Volume discounts follow the tiered schedule on the model's Assumptions tab.",
            "- Supplier costs are contracted against list (gross) revenue at 42%.",
        ]
    path.write_text("\n".join(lines) + "\n")


def write_cfo_email(case: str, inp: dict, path: Path) -> None:
    c = COMPANY[case]
    msg = EmailMessage()
    msg["From"] = f"{c['cfo']} <{c['cfo_email']}>"
    msg["To"] = f"Finance team <finance@{c['domain']}>"
    msg["Date"] = format_datetime(datetime(2026, 10, 20, 16, 5).astimezone())
    msg["Message-ID"] = f"<model-rules-{c['slug']}@{c['domain']}>"
    msg["Subject"] = "Re: rebuilding the quarterly model - how the numbers work"
    t1, t2 = inp["t1"], inp["t2"]
    r1, r2 = _pct(inp["r1"], 0), _pct(inp["r2"], 0)
    if case == "excel_a":
        body = f"""Hi all,

Since the model file got damaged, here is how it is supposed to work so you
can rebuild it. Please keep the layout as it was.

1. Gross revenue is units sold times list price for the quarter.

2. Volume discount is decided per quarter on that quarter's total units.
   Once a quarter reaches a tier, the tier rate applies to the WHOLE quarter's
   gross revenue, not just the units above the line:
     - {t1:,} units or more: {r1}
     - {t2:,} units or more: {r2}
     - below {t1:,} units: no discount
   The thresholds and rates live on the Assumptions tab, so reference those
   cells rather than typing the numbers into formulas.

3. Round the discount to the cent each quarter. Net revenue is gross minus
   discount.

4. COGS is {_pct(inp['cogs_pct'], 0)} of NET revenue (after discount), also
   rounded to the cent each quarter. The % is on the Assumptions tab.

5. Gross margin % is gross profit over net revenue. Growth is net revenue vs
   the prior quarter. If the denominator is zero, show 0%, not an error.

6. Totals in column J are sums, except the two rates, which are recalculated
   from the totals.

One gap: I do not have Q1 2026 operating expenses. That figure only lived in
the model and the backup is gone. Please leave it blank and flag it rather
than estimating.

Thanks,
{c['cfo']}
CFO, {c['name']}
"""
    else:
        body = f"""Hi team,

For the rebuild of the quarterly model:

1. Gross revenue = units x list price for the quarter.

2. Our volume discount is MARGINAL, like tax brackets. Only the units above
   each threshold earn that tier's rate:
     - units above {t1:,} (up to {t2:,}) get {r1} off list price
     - units above {t2:,} get {r2} off list price
     - the first {t1:,} units each quarter get nothing
   Thresholds and rates are on the Assumptions tab; please reference them.
   Round the discount amount to the cent. Row 6 shows the effective rate
   (discount over gross revenue).

3. COGS is {_pct(inp['cogs_pct'], 0)} of GROSS (list) revenue, before any
   discount, because the supplier contract is priced on list. Round to the
   cent each quarter.

4. Gross margin % = gross profit / net revenue. Growth = net revenue vs the
   prior quarter. Zero denominator: show 0%.

5. Column J totals are sums; the two rate rows are recalculated from totals.

Q4 2026 operating expenses are not closed yet and I cannot give you a number.
Leave them empty.

Marek
"""
    msg.set_content(body)
    path.write_bytes(bytes(msg))


def write_excel_case(case: str, out: Path) -> None:
    inp, values = _historical(case)
    d = out / case
    d.mkdir(parents=True, exist_ok=True)
    slug = COMPANY[case]["slug"]
    write_damaged_workbook(case, inp, values, d / L.CASES[case]["workbook"])
    write_csv_export(case, inp, values, d / f"{slug}_erp_export_2025Q1-2026Q3.csv")
    write_board_report(case, inp, values, d / f"{slug}_board_report_Q3_2026.md")
    write_cfo_email(case, inp, d / f"{slug}_cfo_model_rules.eml")
    (d / "layout.json").write_text(json.dumps(L.as_json(case), indent=2) + "\n")


# ---------------------------------------------------------------- Code case

DAMAGED_INVOICING = '''"""Alderbank Outfitters invoicing script (recovered copy).

Reads invoices (one row per invoice, totals already summed from line items),
applies the discount policy from discounts.yml and writes net totals.

RECOVERY NOTE: the body of compute_discount() was lost when the repository
was damaged. Everything else in this file survived.
"""

from __future__ import annotations

import csv
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

CENT = Decimal("0.01")


def load_config(path: str | Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def compute_discount(subtotal: Decimal, total_units: int, customer_tier: str, config: dict) -> Decimal:
    """Return the discount amount for one invoice, in dollars, rounded to the cent."""
    # ---- function body lost in recovery (original lines 31-52 unreadable) ----
    raise NotImplementedError("compute_discount body was lost")


def invoice_totals(row: dict, config: dict) -> dict:
    subtotal = Decimal(row["subtotal"])
    discount = compute_discount(subtotal, int(row["total_units"]), row["customer_tier"], config)
    return {"invoice_id": row["invoice_id"], "subtotal": f"{subtotal:.2f}",
            "discount": f"{discount:.2f}", "net_total": f"{subtotal - discount:.2f}"}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: invoicing.py discounts.yml invoices_in.csv", file=sys.stderr)
        return 2
    config = load_config(argv[1])
    with open(argv[2], newline="") as fh:
        rows = list(csv.DictReader(fh))
    w = csv.DictWriter(sys.stdout, fieldnames=["invoice_id", "subtotal", "discount", "net_total"])
    w.writeheader()
    for row in rows:
        w.writerow(invoice_totals(row, config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''

DISCOUNTS_YML = """# Alderbank Outfitters invoice discount settings
# Exported from the billing admin panel on 2026-09-30. Synthetic demo data.
currency: USD
rounding: half_up_to_cent      # round the final discount amount once
volume_tiers:                  # by total units on the invoice
  - min_units: 100
    rate: 0.03
  - min_units: 500
    rate: 0.06
  - min_units: 1000
    rate: 0.09
loyalty_bonus:                 # added on top of the volume rate
  standard: 0.00
  silver: 0.01
  gold: 0.02
# max_combined_rate: see finance policy FIN-112 (setting not exported)
"""

CHANGELOG = """# billing-service CHANGELOG (excerpt recovered from the damaged repository)

## 2026-03-02
- FIN-112: combined discount (volume tier + loyalty bonus) is now capped at 10%
  of the invoice subtotal. Cap lives in code, not in discounts.yml.

## 2025-11-18
- Volume tiers are inclusive: an invoice with exactly 500 units gets the 500 tier.
- Discount is rounded half-up to the cent once, after rates are combined.

## 2025-06-04
- Loyalty bonus added for silver and gold customers (see discounts.yml).
"""


def _invoice_rows() -> list[dict]:
    rng = random.Random(f"{DEFAULT_SEED}:code_a")
    cfg = yaml.safe_load(DISCOUNTS_YML)
    tiers = ["standard"] * 5 + ["silver"] * 3 + ["gold"] * 2
    units_pool = [12, 40, 99, 100, 180, 260, 499, 500, 640, 880, 999, 1000, 1250, 1600]
    rows = []
    for n in range(1, 31):
        tier = tiers[rng.randrange(len(tiers))]
        units = units_pool[rng.randrange(len(units_pool))]
        if n in (7, 19):  # make sure the capped case appears in surviving evidence
            tier, units = "gold", rng.choice([1000, 1250, 1600])
        unit_price = Decimal(str(round(rng.uniform(14, 42), 2)))
        subtotal = (unit_price * units).quantize(Decimal("0.01"))
        disc = invoicing_ref.compute_discount(subtotal, units, tier, cfg)
        rows.append({"invoice_id": f"INV-2026-{100 + n:04d}",
                     "invoice_date": f"2026-{(n - 1) // 4 + 2:02d}-{(n * 3) % 27 + 1:02d}",
                     "customer_id": f"C-{rng.randint(1000, 1099)}", "customer_tier": tier,
                     "total_units": units, "subtotal": f"{subtotal:.2f}",
                     "discount": f"{disc:.2f}", "net_total": f"{subtotal - disc:.2f}"})
    return rows


UNREADABLE_ROW_ID = "INV-2026-0117"


def write_code_case(out: Path) -> None:
    d = out / "code_a"
    d.mkdir(parents=True, exist_ok=True)
    (d / "invoicing.py").write_text(DAMAGED_INVOICING)
    (d / "discounts.yml").write_text(DISCOUNTS_YML)
    (d / "CHANGELOG_excerpt.md").write_text(CHANGELOG)
    rows = _invoice_rows()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    data = buf.getvalue().encode()
    for r in rows:
        if r["invoice_id"] == UNREADABLE_ROW_ID:
            # Disk damage: the row's bytes are partly overwritten; not valid UTF-8.
            data += b"INV-2026-0117,2026-0\xff\xfe-1\x00,C-10\x9f\x9f,g\xc3\x28ld,\x00\x00\x00,4\xfe\xff9.1,,\n"
            continue
        b = io.StringIO()
        csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator="\n").writerow(r)
        data += b.getvalue().encode()
    (d / "invoices.csv").write_bytes(data)


def write_scanner_fixture(out: Path) -> None:
    d = out / "scanner_fixtures"
    d.mkdir(parents=True, exist_ok=True)
    # The file starts with the standard EICAR test string, which antivirus
    # tools detect by design. It is inert text, not malware. Never execute it.
    (d / "EICAR_TEST_MARKER_harmless.txt").write_text("".join(EICAR_PARTS))
    (d / "README.md").write_text(SCANNER_README)


# ---------------------------------------------------------------- manifest

def _canonical_hash(path: Path) -> str:
    """xlsx files are zipped with timestamps, so hash their cell contents instead."""
    h = hashlib.sha256()
    if path.suffix == ".xlsx":
        wb = openpyxl.load_workbook(path)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if c.value is not None:
                        h.update(f"{ws.title}!{c.coordinate}={c.value!r}\n".encode())
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


def manifest(out: Path) -> dict:
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    return {str(p.relative_to(out)): _canonical_hash(p) for p in files}


def generate(out: Path) -> None:
    _require_oracle()
    for case in L.CASES:
        write_excel_case(case, out)
    write_code_case(out)
    write_scanner_fixture(out)
    m = manifest(out)
    (out / "MANIFEST.json").write_text(json.dumps({"seed": DEFAULT_SEED, "files": m}, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "public")
    ap.add_argument("--check", action="store_true", help="regenerate to a temp dir and diff")
    args = ap.parse_args()
    if not args.check:
        generate(args.out)
        print(f"wrote public evidence to {args.out}")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        generate(Path(tmp))
        fresh = manifest(Path(tmp))
    current = manifest(args.out)
    # EICAR fixture is not committed, so it may be absent from a fresh checkout.
    diffs = [k for k in sorted(set(fresh) | set(current)) if fresh.get(k) != current.get(k)
             and not (k.startswith("scanner_fixtures/EICAR") and k not in current)]
    for k in diffs:
        print("differs:", k)
    print("public data matches the seeded generator" if not diffs else f"{len(diffs)} file(s) differ")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
