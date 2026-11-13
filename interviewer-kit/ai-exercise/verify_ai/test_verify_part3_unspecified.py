"""Part 3: behaviour the problem statement deliberately leaves open.

The statement never says what happens when the fee is larger than the charge
itself: a 17-cent USD charge would carry a 30-cent fixed fee.

The interviewer's answer, when asked: "The fee is capped at the charge amount,
so the net of a charge is never negative."

A candidate who did not ask will usually fail this file. Treat that as a
discussion point about spotting gaps in a spec, not as a wrong answer.
"""
import pytest

from balance_engine import balance_breakdown
from log_helpers import charge

LATER = "2026-03-20T00:00:00Z"


@pytest.mark.parametrize(
    "amount, currency",
    [
        (17, "USD"),  # fee would be 0 + 30
        (30, "USD"),  # fee would be 1 + 30
        (1, "USD"),
        (20, "EUR"),  # fee would be 1 + 25
        (5, "GBP"),  # fee would be 0 + 20
    ],
)
def test_fee_is_capped_at_the_charge_amount(amount, currency):
    lines = [charge("2026-03-10T10:00:00Z", "evt_1", "acct_alpha", amount, currency)]
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {currency: {"pending": 0, "available": 0}}}


def test_a_tiny_charge_does_not_eat_into_other_funds():
    lines = [
        charge("2026-03-10T10:00:00Z", "evt_1", "acct_alpha", 10000),  # net 9680
        charge("2026-03-10T10:05:00Z", "evt_2", "acct_alpha", 10),  # fee capped at 10: net 0, not -20
    ]
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {"USD": {"pending": 0, "available": 9680}}}
