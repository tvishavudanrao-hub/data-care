"""Alderbank Outfitters invoicing script (recovered copy).

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
