"""Workbook recalculation engine (wrapper around the `formulas` package).

One correction is applied: `formulas` implements ROUND on the binary float
(x * 10**d), so a value that is exactly half a cent in decimal, such as
18184.635, can round down because its float is 18184.634999... Excel works on
the value rounded to 15 significant digits and rounds half away from zero.
We register an Excel-faithful ROUND/ROUNDUP/ROUNDDOWN so the verifier does not
fail correct candidates on representation noise.
"""

from __future__ import annotations

import functools
import math
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP, ROUND_DOWN

import formulas
from formulas.functions import wrap_ufunc
from formulas.functions import math as fmath


def _excel_round(x: float, d: float, mode=ROUND_HALF_UP) -> float:
    if not math.isfinite(x):
        raise ValueError
    q = Decimal(1).scaleb(-int(d))  # 10**-d
    v = Decimal(f"{x:.15g}").quantize(q, rounding=mode)
    return float(v)


fmath.FUNCTIONS["ROUND"] = wrap_ufunc(_excel_round)
fmath.FUNCTIONS["ROUNDUP"] = wrap_ufunc(functools.partial(_excel_round, mode=ROUND_UP))
fmath.FUNCTIONS["ROUNDDOWN"] = wrap_ufunc(functools.partial(_excel_round, mode=ROUND_DOWN))


class EngineError(Exception):
    """The engine could not load or evaluate the workbook at all."""


def load(path) -> "formulas.ExcelModel":
    try:
        return formulas.ExcelModel().loads(str(path)).finish()
    except Exception as exc:  # noqa: BLE001 - any engine failure is reported, never passed
        raise EngineError(f"{type(exc).__name__}: {exc}") from exc


def ref_key(book: str, ref: str) -> str:
    sheet, cell = ref.split("!")
    return f"'[{book}]{sheet.upper()}'!{cell.upper()}"


def scalar(v):
    """Unwrap a formulas Ranges/array result to a python scalar."""
    val = getattr(v, "value", v)
    try:
        return val[0, 0]
    except (TypeError, IndexError, KeyError):
        return val
