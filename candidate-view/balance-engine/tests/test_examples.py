"""The example from PROBLEM.md. Add your own tests in this folder."""
from balance_engine import compute_balances

PART_1_EXAMPLE = [
    "2026-03-01T09:00:00Z,evt_001,charge,acct_alpha,12000,USD",
    "2026-03-01T09:05:00Z,evt_002,charge,acct_beta,8000,EUR",
    "2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001",
    "2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001",
    "# nightly export follows",
    "2026-03-01T10:15:00Z,evt_004,charge,acct_alpha,5000,EUR",
    "2026-03-01T11:00:00Z,evt_005,charge,acct_beta,-300,EUR",
]


def test_part_1_example():
    lines = PART_1_EXAMPLE
    assert compute_balances(lines) == {
        "acct_alpha": {"USD": 10000, "EUR": 5000},
        "acct_beta": {"EUR": 8000},
    }
