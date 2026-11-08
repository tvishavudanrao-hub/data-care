"""Seeded input drivers for the synthetic demo companies.

Only raw inputs live here (units sold, list prices, operating expenses and the
assumption values). These numbers are visible in the damaged workbooks anyway.
How outputs are calculated from them is private to the Verify owner and is not
in this file.
"""

from __future__ import annotations

import random
from decimal import Decimal

DEFAULT_SEED = 20261107  # kickoff day


def _money(x: float) -> Decimal:
    return Decimal(str(round(x, 2)))


def drivers(case: str, seed: int = DEFAULT_SEED) -> dict:
    # Each case gets its own stream so adding a case never shifts another.
    rng = random.Random(f"{seed}:{case}")
    if case == "excel_a":
        # Outdoor goods wholesaler. Volumes chosen to sit in every discount band.
        bands = [(820, 960), (1050, 1400), (1100, 1600), (2550, 2900),
                 (1150, 1500), (880, 990), (2300, 2470), (2700, 3200)]
        units = [rng.randint(lo, hi) for lo, hi in bands]
        price = [Decimal("24.99")] * 4 + [Decimal("26.49")] * 3 + [Decimal("27.49")]
        opex = [_money(rng.uniform(17500, 23500)) for _ in range(8)]
        assumptions = {"cogs_pct": Decimal("0.38"), "t1": 1000, "r1": Decimal("0.05"),
                       "t2": 2500, "r2": Decimal("0.10")}
    elif case == "excel_b":
        # Tool hire business: higher volumes, different discount structure.
        bands = [(600, 780), (900, 1300), (1700, 1990), (2100, 2600),
                 (1250, 1600), (2050, 2400), (2600, 3400), (1500, 1900)]
        units = [rng.randint(lo, hi) for lo, hi in bands]
        price = [Decimal("38.00")] * 2 + [Decimal("39.50")] * 4 + [Decimal("41.00")] * 2
        opex = [_money(rng.uniform(26000, 34000)) for _ in range(8)]
        assumptions = {"cogs_pct": Decimal("0.42"), "t1": 800, "r1": Decimal("0.04"),
                       "t2": 2000, "r2": Decimal("0.09")}
    else:
        raise KeyError(case)
    return {"units": units, "price": price, "opex": opex, **assumptions}
