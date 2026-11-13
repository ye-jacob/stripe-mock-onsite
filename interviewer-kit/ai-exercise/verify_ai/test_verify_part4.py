"""Part 4: daily payouts.

Useful nets (USD unless noted): 10000 -> 9680, 12000 -> 11622, 3000 -> 2883,
4000 -> 3854, 5180 -> 5000, 5179 -> 4999, 20000 -> 19390, EUR 10000 -> 9685,
EUR 4000 -> 3859.
"""
from balance_engine import balance_breakdown, compute_balances, compute_payouts, rejected_refunds
from log_helpers import as_tuples, assert_all_ints, charge, refund

FAR = "2026-04-30T00:00:00Z"


def payouts(lines, as_of):
    result = compute_payouts(lines, as_of)
    assert_all_ints([row[3] for row in result], "payout amounts")
    return as_tuples(result)


def test_example_from_the_problem_statement():
    lines = [
        "2026-03-03T08:00:00Z,evt_201,charge,acct_alpha,10000,USD",
        "2026-03-04T08:00:00Z,evt_202,charge,acct_alpha,4000,USD",
        "2026-03-04T09:00:00Z,evt_203,refund,acct_alpha,2500,USD,evt_201",
        "2026-03-04T10:00:00Z,evt_204,charge,acct_beta,2000,EUR",
        "2026-03-06T15:00:00Z,evt_205,refund,acct_alpha,5000,USD,evt_201",
        "2026-03-06T16:00:00Z,evt_206,charge,acct_alpha,9000,USD",
    ]
    assert payouts(lines, "2026-03-09T00:00:00Z") == [
        ("2026-03-06", "acct_alpha", "USD", 7180),
        ("2026-03-09", "acct_alpha", "USD", 7563),
    ]
    assert payouts(lines, "2026-03-08T23:59:59Z") == [("2026-03-06", "acct_alpha", "USD", 7180)]


def test_no_events_no_payouts():
    assert payouts([], FAR) == []


def test_a_simple_payout_happens_at_the_first_midnight_after_the_hold():
    lines = [charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000)]  # available 03-03 10:00
    assert payouts(lines, "2026-03-03T23:59:59Z") == []
    assert payouts(lines, "2026-03-04T00:00:00Z") == [("2026-03-04", "acct_alpha", "USD", 9680)]
    assert payouts(lines, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]  # paid once, not every night


def test_minimum_payout_is_inclusive():
    exactly = [charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 5180)]  # net 5000
    just_below = [charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 5179)]  # net 4999
    assert payouts(exactly, FAR) == [("2026-03-04", "acct_alpha", "USD", 5000)]
    assert payouts(just_below, FAR) == []


def test_funds_released_exactly_at_midnight_join_that_run():
    at_midnight = [charge("2026-03-01T00:00:00Z", "evt_1", "acct_alpha", 10000)]  # available 03-03 00:00:00
    one_second_late = [charge("2026-03-01T00:00:01Z", "evt_1", "acct_alpha", 10000)]
    assert payouts(at_midnight, FAR) == [("2026-03-03", "acct_alpha", "USD", 9680)]
    assert payouts(one_second_late, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]


def test_an_event_at_exactly_midnight_is_processed_before_the_run():
    refund_at_midnight = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),  # 9680 available 03-03 10:00
        refund("2026-03-04T00:00:00Z", "evt_2", "acct_alpha", 5000, "evt_1"),  # leaves 4680: below the minimum
    ]
    refund_one_second_later = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),
        refund("2026-03-04T00:00:01Z", "evt_2", "acct_alpha", 5000, "evt_1"),
    ]
    assert payouts(refund_at_midnight, FAR) == []
    assert payouts(refund_one_second_later, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]


def test_a_run_at_exactly_as_of_is_included():
    lines = [charge("2026-03-01T00:00:00Z", "evt_1", "acct_alpha", 10000)]  # run of 03-03 00:00:00
    assert payouts(lines, "2026-03-02T23:59:59Z") == []
    assert payouts(lines, "2026-03-03T00:00:00Z") == [("2026-03-03", "acct_alpha", "USD", 9680)]


def test_small_balances_accumulate_until_they_reach_the_minimum():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 3000),  # net 2883, available 03-03 10:00
        charge("2026-03-03T10:00:00Z", "evt_2", "acct_alpha", 3000),  # net 2883, available 03-05 10:00
    ]
    assert payouts(lines, "2026-03-05T23:59:59Z") == []
    assert payouts(lines, FAR) == [("2026-03-06", "acct_alpha", "USD", 5766)]


def test_a_refund_after_a_payout_creates_a_debt_that_later_funds_repay_first():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),  # paid out on 03-04: 9680
        refund("2026-03-04T12:00:00Z", "evt_2", "acct_alpha", 6000, "evt_1"),  # available is now -6000
        charge("2026-03-04T13:00:00Z", "evt_3", "acct_alpha", 12000),  # net 11622, available 03-06 13:00
    ]
    assert payouts(lines, FAR) == [
        ("2026-03-04", "acct_alpha", "USD", 9680),
        ("2026-03-07", "acct_alpha", "USD", 5622),  # -6000 + 11622
    ]


def test_a_debt_that_is_not_repaid_blocks_payouts():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),  # paid out on 03-04: 9680
        refund("2026-03-04T12:00:00Z", "evt_2", "acct_alpha", 10000, "evt_1"),  # available is now -10000
        charge("2026-03-04T13:00:00Z", "evt_3", "acct_alpha", 12000),  # net 11622: only 1622 after the debt
    ]
    assert payouts(lines, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]


def test_each_merchant_and_currency_is_paid_on_its_own():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 4000, "USD"),  # net 3854
        charge("2026-03-01T10:00:00Z", "evt_2", "acct_alpha", 4000, "EUR"),  # net 3859
        charge("2026-03-01T10:00:00Z", "evt_3", "acct_beta", 4000, "USD"),  # net 3854
    ]
    assert payouts(lines, FAR) == []  # 3854 + 3859 would pass the minimum, but balances are never combined


def test_payouts_are_sorted_by_date_then_merchant_then_currency():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_beta", 20000, "USD"),  # 19390 on 03-04
        charge("2026-03-01T10:00:00Z", "evt_2", "acct_alpha", 10000, "USD"),  # 9680 on 03-04
        charge("2026-03-01T10:00:00Z", "evt_3", "acct_alpha", 10000, "EUR"),  # 9685 on 03-04
        charge("2026-02-27T10:00:00Z", "evt_4", "acct_gamma", 10000, "USD"),  # 9680 on 03-02
    ]
    assert payouts(lines, FAR) == [
        ("2026-03-02", "acct_gamma", "USD", 9680),
        ("2026-03-04", "acct_alpha", "EUR", 9685),
        ("2026-03-04", "acct_alpha", "USD", 9680),
        ("2026-03-04", "acct_beta", "USD", 19390),
    ]


def test_events_after_as_of_have_not_happened():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),
        refund("2026-03-03T12:00:00Z", "evt_2", "acct_alpha", 9000, "evt_1"),
    ]
    # Seen from 03-03 11:00 the refund does not exist, but no run has happened since the funds became available.
    assert payouts(lines, "2026-03-03T11:00:00Z") == []
    # Seen from 03-04 the refund came first: 9680 - 9000 = 680, below the minimum.
    assert payouts(lines, "2026-03-04T00:00:00Z") == []


def test_rejected_refunds_do_not_reduce_payouts():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),
        refund("2026-03-02T10:00:00Z", "evt_2", "acct_alpha", 10001, "evt_1"),  # exceeds_charge
        refund("2026-03-02T11:00:00Z", "evt_3", "acct_beta", 5000, "evt_1"),  # charge_mismatch
    ]
    assert payouts(lines, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]


def test_payout_dates_cross_month_ends_and_leap_days():
    lines = [
        charge("2028-02-27T00:00:00Z", "evt_1", "acct_alpha", 10000),  # available 2028-02-29 00:00:00
        charge("2026-12-30T08:00:00Z", "evt_2", "acct_beta", 10000),  # available 2027-01-01 08:00, run of 01-02
    ]
    assert payouts(lines, "2028-12-31T00:00:00Z") == [
        ("2027-01-02", "acct_beta", "USD", 9680),
        ("2028-02-29", "acct_alpha", "USD", 9680),
    ]


def test_the_log_is_still_deduplicated_and_ordered_by_timestamp():
    lines = [
        refund("2026-03-04T12:00:00Z", "evt_2", "acct_alpha", 6000, "evt_1"),
        "not an event",
        charge("2026-03-04T13:00:00Z", "evt_3", "acct_alpha", 12000),
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),
        charge("2026-03-04T13:00:00Z", "evt_3", "acct_alpha", 12000),
    ]
    assert payouts(lines, FAR) == [
        ("2026-03-04", "acct_alpha", "USD", 9680),
        ("2026-03-07", "acct_alpha", "USD", 5622),
    ]


def test_earlier_functions_are_unchanged_by_payouts():
    lines = [
        charge("2026-03-01T10:00:00Z", "evt_1", "acct_alpha", 10000),
        refund("2026-03-04T12:00:00Z", "evt_2", "acct_alpha", 6000, "evt_1"),
    ]
    assert payouts(lines, FAR) == [("2026-03-04", "acct_alpha", "USD", 9680)]
    # balance_breakdown still reports funds as if nothing had been paid out
    assert balance_breakdown(lines, FAR) == {"acct_alpha": {"USD": {"pending": 0, "available": 3680}}}
    assert compute_balances(lines) == {"acct_alpha": {"USD": 4000}}
    assert as_tuples(rejected_refunds(lines)) == []
