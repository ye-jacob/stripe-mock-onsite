"""Processing fees.

Larkspur keeps a fee from every successful charge:

    2.9% of the charge amount, rounded half up to the minor unit,
    plus a fixed amount that depends on the currency.

All amounts are integers in the currency's minor unit (cents, pence).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

PERCENTAGE_FEE = Decimal("0.029")
FIXED_FEES = {"usd": 30, "eur": 25, "gbp": 20}


def calculate_fee(amount: int, currency: str) -> int:
    """Processing fee for one successful charge, in minor units."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount must be an integer number of minor units")
    if amount <= 0:
        raise ValueError("amount must be positive")
    if currency not in FIXED_FEES:
        raise ValueError(f"unsupported currency: {currency!r}")
    return _percentage_of(amount, PERCENTAGE_FEE) + FIXED_FEES[currency]


def _percentage_of(amount: int, rate: Decimal) -> int:
    """``rate`` of ``amount``, rounded half up to a whole minor unit."""
    return int((Decimal(amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
