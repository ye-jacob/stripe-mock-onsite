"""Part 3: fees, pending and available funds.

Fee reminder: 2.9% rounded half up, plus USD 30 / EUR 25 / GBP 20 / anything else 0.
"""
import pytest

from balance_engine import balance_breakdown, compute_balances, rejected_refunds
from log_helpers import as_tuples, assert_all_ints, charge, refund

T = "2026-03-10T10:00:00Z"  # when the charge in most tests happens
T_PLUS_48H = "2026-03-12T10:00:00Z"
LATER = "2026-03-20T00:00:00Z"  # long after every hold has ended


def test_example_from_the_problem_statement():
    lines = [
        "2026-03-03T08:00:00Z,evt_201,charge,acct_alpha,10000,USD",
        "2026-03-04T08:00:00Z,evt_202,charge,acct_alpha,4000,USD",
        "2026-03-04T09:00:00Z,evt_203,refund,acct_alpha,2500,USD,evt_201",
        "2026-03-04T10:00:00Z,evt_204,charge,acct_beta,2000,EUR",
    ]
    assert balance_breakdown(lines, "2026-03-05T08:00:00Z") == {
        "acct_alpha": {"USD": {"pending": 3854, "available": 7180}},
        "acct_beta": {"EUR": {"pending": 1917, "available": 0}},
    }
    assert balance_breakdown(lines, "2026-03-04T09:30:00Z") == {
        "acct_alpha": {"USD": {"pending": 13534, "available": -2500}},
    }


def test_empty_log():
    assert balance_breakdown([], LATER) == {}


@pytest.mark.parametrize(
    "currency, net",
    [
        ("USD", 941),  # 1000 - (29 + 30)
        ("EUR", 946),  # 1000 - (29 + 25)
        ("GBP", 951),  # 1000 - (29 + 20)
        ("JPY", 971),  # 1000 - (29 + 0): no fixed fee for other currencies
        ("CHF", 971),
    ],
)
def test_fixed_fee_depends_on_the_currency(currency, net):
    lines = [charge(T, "evt_1", "acct_alpha", 1000, currency)]
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {currency: {"pending": 0, "available": net}}}


@pytest.mark.parametrize(
    "amount, net",
    [
        (500, 455),  # 2.9% = 14.5 -> 15, fee 45
        (1500, 1426),  # 43.5 -> 44, fee 74
        (2500, 2397),  # 72.5 -> 73, fee 103
        (3500, 3368),  # 101.5 -> 102, fee 132
        (4500, 4339),  # 130.5 -> 131, fee 161
        (50, 19),  # 1.45 -> 1, fee 31
        (52, 20),  # 1.508 -> 2, fee 32
        (100, 67),  # 2.9 -> 3, fee 33
        (31, 0),  # 0.899 -> 1, fee 31: exactly the charge amount
        (32, 1),  # 0.928 -> 1, fee 31
        (4999, 4824),  # 144.971 -> 145, fee 175
        (10000, 9680),  # 290, fee 320
        (123456789, 119876512),  # 3580246.881 -> 3580247, fee 3580277
    ],
)
def test_percentage_fee_is_rounded_half_up(amount, net):
    lines = [charge(T, "evt_1", "acct_alpha", amount, "USD")]
    result = balance_breakdown(lines, LATER)
    assert result == {"acct_alpha": {"USD": {"pending": 0, "available": net}}}
    assert_all_ints(result)


def test_a_charge_is_pending_until_exactly_48_hours_have_passed():
    lines = [charge(T, "evt_1", "acct_alpha", 10000)]
    assert balance_breakdown(lines, T) == {"acct_alpha": {"USD": {"pending": 9680, "available": 0}}}
    assert balance_breakdown(lines, "2026-03-12T09:59:59Z") == {"acct_alpha": {"USD": {"pending": 9680, "available": 0}}}
    assert balance_breakdown(lines, T_PLUS_48H) == {"acct_alpha": {"USD": {"pending": 0, "available": 9680}}}
    assert balance_breakdown(lines, "2026-03-12T10:00:01Z") == {"acct_alpha": {"USD": {"pending": 0, "available": 9680}}}


def test_events_after_as_of_have_not_happened():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        charge("2026-03-10T12:00:00Z", "evt_2", "acct_beta", 10000),
        refund("2026-03-10T13:00:00Z", "evt_3", "acct_alpha", 1000, "evt_1"),
    ]
    assert balance_breakdown(lines, "2026-03-10T09:59:59Z") == {}
    assert balance_breakdown(lines, "2026-03-10T11:00:00Z") == {"acct_alpha": {"USD": {"pending": 9680, "available": 0}}}
    assert balance_breakdown(lines, "2026-03-10T12:59:59Z") == {
        "acct_alpha": {"USD": {"pending": 9680, "available": 0}},
        "acct_beta": {"USD": {"pending": 9680, "available": 0}},
    }


def test_events_at_exactly_as_of_have_happened():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        refund("2026-03-10T13:00:00Z", "evt_2", "acct_alpha", 1000, "evt_1"),
    ]
    assert balance_breakdown(lines, "2026-03-10T13:00:00Z") == {"acct_alpha": {"USD": {"pending": 9680, "available": -1000}}}


def test_a_refund_comes_out_of_available_even_while_its_charge_is_pending():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 3000, "evt_1"),
    ]
    assert balance_breakdown(lines, "2026-03-10T12:00:00Z") == {"acct_alpha": {"USD": {"pending": 9680, "available": -3000}}}
    assert balance_breakdown(lines, T_PLUS_48H) == {"acct_alpha": {"USD": {"pending": 0, "available": 6680}}}


def test_refunds_do_not_return_the_fee_and_are_limited_by_the_full_charge_amount():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),  # net 9680
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 10000, "evt_1"),  # the full amount, not the net
    ]
    assert as_tuples(rejected_refunds(lines)) == []
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {"USD": {"pending": 0, "available": -320}}}


def test_rejected_refunds_change_nothing():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 10001, "evt_1"),  # exceeds_charge
        refund("2026-03-10T11:30:00Z", "evt_3", "acct_gamma", 500, "evt_1"),  # charge_mismatch
    ]
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {"USD": {"pending": 0, "available": 9680}}}


def test_a_refund_before_as_of_whose_charge_comes_after_as_of_is_still_rejected():
    lines = [
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 500, "evt_1"),
        charge("2026-03-10T12:00:00Z", "evt_1", "acct_alpha", 10000),
        charge("2026-03-10T09:00:00Z", "evt_0", "acct_alpha", 1000),
    ]
    # at 11:30 only evt_0 and the (rejected) refund have happened
    assert balance_breakdown(lines, "2026-03-10T11:30:00Z") == {"acct_alpha": {"USD": {"pending": 941, "available": 0}}}


def test_several_charges_merchants_and_currencies():
    lines = [
        charge("2026-03-10T10:00:00Z", "evt_1", "acct_alpha", 10000, "USD"),  # net 9680, available 03-12 10:00
        charge("2026-03-11T10:00:00Z", "evt_2", "acct_alpha", 1000, "USD"),  # net 941, available 03-13 10:00
        charge("2026-03-10T10:00:00Z", "evt_3", "acct_alpha", 1000, "EUR"),  # net 946
        charge("2026-03-12T00:00:00Z", "evt_4", "acct_beta", 2000, "EUR"),  # net 1917, available 03-14 00:00
        refund("2026-03-12T12:00:00Z", "evt_5", "acct_alpha", 400, "evt_3", "EUR"),
    ]
    assert balance_breakdown(lines, "2026-03-13T00:00:00Z") == {
        "acct_alpha": {
            "USD": {"pending": 941, "available": 9680},
            "EUR": {"pending": 0, "available": 546},
        },
        "acct_beta": {"EUR": {"pending": 1917, "available": 0}},
    }


def test_the_log_is_still_deduplicated_and_ordered_by_timestamp():
    lines = [
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 3000, "evt_1"),
        charge(T, "evt_1", "acct_alpha", 10000),
        charge(T, "evt_1", "acct_alpha", 10000),
        "garbage",
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 3000, "evt_1"),
    ]
    assert balance_breakdown(lines, T_PLUS_48H) == {"acct_alpha": {"USD": {"pending": 0, "available": 6680}}}


def test_an_account_with_only_rejected_events_is_absent():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_gamma", 500, "evt_1"),
    ]
    assert balance_breakdown(lines, LATER) == {"acct_alpha": {"USD": {"pending": 0, "available": 9680}}}


def test_earlier_functions_are_unchanged_by_fees():
    lines = [
        charge(T, "evt_1", "acct_alpha", 10000),
        refund("2026-03-10T11:00:00Z", "evt_2", "acct_alpha", 3000, "evt_1"),
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 7000}}  # gross, no fees, whole log
    assert as_tuples(rejected_refunds(lines)) == []
