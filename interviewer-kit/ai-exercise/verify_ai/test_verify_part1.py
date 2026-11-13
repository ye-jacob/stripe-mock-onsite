"""Part 1: balances, malformed lines, duplicate deliveries.

Every log here is also valid under the rules of the later parts, so this file
keeps passing however far the candidate got.
"""
import pytest

from balance_engine import compute_balances
from log_helpers import assert_all_ints, charge, refund

OK = charge("2026-03-01T09:00:00Z", "evt_ok", "acct_alpha", 1000)


def test_example_from_the_problem_statement():
    lines = [
        "2026-03-01T09:00:00Z,evt_001,charge,acct_alpha,12000,USD",
        "2026-03-01T09:05:00Z,evt_002,charge,acct_beta,8000,EUR",
        "2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001",
        "2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001",
        "# nightly export follows",
        "2026-03-01T10:15:00Z,evt_004,charge,acct_alpha,5000,EUR",
        "2026-03-01T11:00:00Z,evt_005,charge,acct_beta,-300,EUR",
    ]
    assert compute_balances(lines) == {
        "acct_alpha": {"USD": 10000, "EUR": 5000},
        "acct_beta": {"EUR": 8000},
    }


def test_empty_log():
    assert compute_balances([]) == {}


def test_balances_are_kept_per_merchant_and_per_currency():
    lines = [
        charge("2026-03-01T09:00:00Z", "evt_1", "acct_alpha", 1000),
        charge("2026-03-01T09:01:00Z", "evt_2", "acct_alpha", 2500),
        charge("2026-03-01T09:02:00Z", "evt_3", "acct_alpha", 700, "EUR"),
        charge("2026-03-01T09:03:00Z", "evt_4", "acct_beta", 50),
        refund("2026-03-01T09:04:00Z", "evt_5", "acct_alpha", 400, "evt_1"),
    ]
    result = compute_balances(lines)
    assert result == {"acct_alpha": {"USD": 3100, "EUR": 700}, "acct_beta": {"USD": 50}}
    assert_all_ints(result)


def test_a_zero_balance_is_still_reported():
    lines = [
        charge("2026-03-01T09:00:00Z", "evt_1", "acct_alpha", 900),
        refund("2026-03-01T10:00:00Z", "evt_2", "acct_alpha", 900, "evt_1"),
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 0}}


def test_an_event_delivered_twice_counts_once():
    line = charge("2026-03-01T09:00:00Z", "evt_1", "acct_alpha", 1000)
    assert compute_balances([line, line, line]) == {"acct_alpha": {"USD": 1000}}


def test_later_lines_with_a_known_event_id_are_ignored_even_if_they_differ():
    lines = [
        charge("2026-03-01T09:00:00Z", "evt_1", "acct_alpha", 1000),
        charge("2026-03-01T09:30:00Z", "evt_1", "acct_beta", 7777, "EUR"),
        charge("2026-03-01T09:45:00Z", "evt_2", "acct_alpha", 200),
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1200}}


def test_a_malformed_line_does_not_use_up_its_event_id():
    lines = [
        "2026-03-01T09:00:00Z,evt_1,charge,acct_alpha,12.50,USD",  # malformed: amount
        charge("2026-03-01T09:00:00Z", "evt_1", "acct_alpha", 1250),  # the first WELL-FORMED evt_1
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1250}}


def test_spaces_around_fields_are_ignored():
    lines = [
        " 2026-03-01T09:00:00Z , evt_1 , charge , acct_alpha , 1250 , USD ",
        "2026-03-01T09:10:00Z,evt_2,refund,acct_alpha,  250,USD,  evt_1  ",
        "   2026-03-01T09:20:00Z,evt_1,charge,acct_alpha,9999,USD",  # same id as the first line once trimmed
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


MALFORMED = {
    "empty line": "",
    "blank line": "     ",
    "comment": "# exported 2026-03-01",
    "header row": "timestamp,event_id,type,merchant_id,amount,currency",
    "prose": "connection reset by peer",
    "too few fields": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100",
    "charge with a seventh field": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,USD,evt_ok",
    "refund without charge_id": "2026-03-01T10:00:00Z,evt_bad,refund,acct_alpha,100,USD",
    "refund with empty charge_id": "2026-03-01T10:00:00Z,evt_bad,refund,acct_alpha,100,USD,",
    "refund with an eighth field": "2026-03-01T10:00:00Z,evt_bad,refund,acct_alpha,100,USD,evt_ok,extra",
    "unknown type": "2026-03-01T10:00:00Z,evt_bad,payout,acct_bad,100,USD",
    "empty type": "2026-03-01T10:00:00Z,evt_bad,,acct_bad,100,USD",
    "empty event_id": "2026-03-01T10:00:00Z,,charge,acct_bad,100,USD",
    "empty merchant_id": "2026-03-01T10:00:00Z,evt_bad,charge,,100,USD",
    "amount zero": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,0,USD",
    "amount negative": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,-100,USD",
    "refund amount negative": "2026-03-01T10:00:00Z,evt_bad,refund,acct_alpha,-100,USD,evt_ok",
    "amount with decimals": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,12.50,USD",
    "amount not a number": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,abc,USD",
    "amount empty": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,,USD",
    "currency lowercase": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,usd",
    "currency two letters": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,US",
    "currency four letters": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,USDT",
    "currency with a symbol": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,U$D",
    "currency empty": "2026-03-01T10:00:00Z,evt_bad,charge,acct_bad,100,",
    "timestamp with a space instead of T": "2026-03-01 10:00:00Z,evt_bad,charge,acct_bad,100,USD",
    "timestamp without Z": "2026-03-01T10:00:00,evt_bad,charge,acct_bad,100,USD",
    "timestamp with a numeric offset": "2026-03-01T10:00:00+00:00,evt_bad,charge,acct_bad,100,USD",
    "timestamp without seconds": "2026-03-01T10:00Z,evt_bad,charge,acct_bad,100,USD",
    "timestamp date only": "2026-03-01,evt_bad,charge,acct_bad,100,USD",
    "timestamp on a day that does not exist": "2026-02-30T10:00:00Z,evt_bad,charge,acct_bad,100,USD",
    "timestamp in month 13": "2026-13-01T10:00:00Z,evt_bad,charge,acct_bad,100,USD",
    "timestamp at hour 24": "2026-03-01T24:00:00Z,evt_bad,charge,acct_bad,100,USD",
    "timestamp in another format": "03/01/2026 10:00,evt_bad,charge,acct_bad,100,USD",
    "timestamp as epoch seconds": "1772359200,evt_bad,charge,acct_bad,100,USD",
    "timestamp empty": ",evt_bad,charge,acct_bad,100,USD",
}


@pytest.mark.parametrize("bad_line", list(MALFORMED.values()), ids=list(MALFORMED.keys()))
def test_malformed_lines_are_skipped(bad_line):
    try:
        result = compute_balances([OK, bad_line])
    except Exception as error:  # noqa: BLE001 - any crash on bad input is the finding
        pytest.fail("compute_balances crashed on a malformed line %r: %r" % (bad_line, error))
    assert result == {"acct_alpha": {"USD": 1000}}, "this line should have been skipped: %r" % bad_line
