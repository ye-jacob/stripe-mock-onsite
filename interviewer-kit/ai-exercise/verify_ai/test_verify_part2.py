"""Part 2: processing order and refund validation."""
from balance_engine import compute_balances, rejected_refunds
from log_helpers import as_tuples, charge, refund


def rejected(lines):
    return as_tuples(rejected_refunds(lines))


def test_example_from_the_problem_statement():
    lines = [
        "2026-03-02T12:00:00Z,evt_103,refund,acct_alpha,4000,USD,evt_101",
        "2026-03-02T10:00:00Z,evt_101,charge,acct_alpha,10000,USD",
        "2026-03-02T11:00:00Z,evt_102,refund,acct_alpha,7000,USD,evt_101",
        "2026-03-02T09:00:00Z,evt_104,refund,acct_beta,500,EUR,evt_105",
        "2026-03-02T09:30:00Z,evt_105,charge,acct_beta,2500,EUR",
        "2026-03-02T13:00:00Z,evt_106,refund,acct_gamma,1000,USD,evt_101",
        "2026-03-02T14:00:00Z,evt_107,refund,acct_alpha,3000,USD,evt_101",
    ]
    assert rejected(lines) == [
        ("evt_104", "charge_not_found"),
        ("evt_103", "exceeds_charge"),
        ("evt_106", "charge_mismatch"),
    ]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 0}, "acct_beta": {"EUR": 2500}}


def test_nothing_is_rejected_in_a_clean_log():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_1"),
    ]
    assert rejected(lines) == []
    assert rejected([]) == []


def test_events_are_processed_by_timestamp_not_by_input_order():
    lines = [
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_1"),  # listed first, happens second
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
    ]
    assert rejected(lines) == []
    assert compute_balances(lines) == {"acct_alpha": {"USD": 600}}


def test_a_refund_timestamped_before_its_charge_is_not_found():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),  # listed first, happens second
        refund("2026-03-02T09:59:59Z", "evt_2", "acct_alpha", 400, "evt_1"),
    ]
    assert rejected(lines) == [("evt_2", "charge_not_found")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_equal_timestamps_keep_their_input_order_charge_first():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_9", "acct_alpha", 1000),
        refund("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 400, "evt_9"),
    ]
    assert rejected(lines) == []
    assert compute_balances(lines) == {"acct_alpha": {"USD": 600}}


def test_equal_timestamps_keep_their_input_order_refund_first():
    lines = [
        refund("2026-03-02T10:00:00Z", "evt_9", "acct_alpha", 400, "evt_1"),
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
    ]
    assert rejected(lines) == [("evt_9", "charge_not_found")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_unknown_charge_id():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_404"),
    ]
    assert rejected(lines) == [("evt_2", "charge_not_found")]


def test_a_refund_cannot_refund_another_refund():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_1"),
        refund("2026-03-02T12:00:00Z", "evt_3", "acct_alpha", 100, "evt_2"),  # evt_2 is not a charge
    ]
    assert rejected(lines) == [("evt_3", "charge_not_found")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 600}}


def test_refund_by_another_merchant_is_a_mismatch():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        charge("2026-03-02T10:30:00Z", "evt_2", "acct_beta", 5000),
        refund("2026-03-02T11:00:00Z", "evt_3", "acct_beta", 400, "evt_1"),
    ]
    assert rejected(lines) == [("evt_3", "charge_mismatch")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}, "acct_beta": {"USD": 5000}}


def test_refund_in_another_currency_is_a_mismatch():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000, "USD"),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_1", "EUR"),
    ]
    assert rejected(lines) == [("evt_2", "charge_mismatch")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_checks_run_in_order_mismatch_before_exceeds():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_beta", 5000, "evt_1"),  # wrong merchant AND too large
    ]
    assert rejected(lines) == [("evt_2", "charge_mismatch")]


def test_refunds_may_add_up_to_exactly_the_charge_amount():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_1"),
        refund("2026-03-02T12:00:00Z", "evt_3", "acct_alpha", 600, "evt_1"),  # 400 + 600 = 1000: allowed
        refund("2026-03-02T13:00:00Z", "evt_4", "acct_alpha", 1, "evt_1"),  # one more unit: too much
    ]
    assert rejected(lines) == [("evt_4", "exceeds_charge")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 0}}


def test_a_single_refund_larger_than_the_charge_is_rejected():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 1001, "evt_1"),
    ]
    assert rejected(lines) == [("evt_2", "exceeds_charge")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_a_rejected_refund_does_not_use_up_the_charge():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 600, "evt_1"),
        refund("2026-03-02T12:00:00Z", "evt_3", "acct_alpha", 500, "evt_1"),  # 1100 > 1000: rejected
        refund("2026-03-02T13:00:00Z", "evt_4", "acct_alpha", 400, "evt_1"),  # 600 + 400 = 1000: accepted
    ]
    assert rejected(lines) == [("evt_3", "exceeds_charge")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 0}}


def test_refund_limits_are_tracked_per_charge():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        charge("2026-03-02T10:05:00Z", "evt_2", "acct_alpha", 300),
        refund("2026-03-02T11:00:00Z", "evt_3", "acct_alpha", 300, "evt_2"),
        refund("2026-03-02T12:00:00Z", "evt_4", "acct_alpha", 100, "evt_2"),  # evt_2 is used up, evt_1 is not
        refund("2026-03-02T13:00:00Z", "evt_5", "acct_alpha", 1000, "evt_1"),
    ]
    assert rejected(lines) == [("evt_4", "exceeds_charge")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 0}}


def test_rejected_refunds_are_listed_in_processing_order():
    lines = [
        refund("2026-03-02T15:00:00Z", "evt_a", "acct_alpha", 100, "evt_404"),
        refund("2026-03-02T09:00:00Z", "evt_b", "acct_alpha", 100, "evt_404"),
        refund("2026-03-02T12:00:00Z", "evt_z", "acct_alpha", 100, "evt_404"),  # same time as evt_c, listed before it
        refund("2026-03-02T12:00:00Z", "evt_c", "acct_alpha", 100, "evt_404"),
    ]
    assert rejected(lines) == [
        ("evt_b", "charge_not_found"),
        ("evt_z", "charge_not_found"),
        ("evt_c", "charge_not_found"),
        ("evt_a", "charge_not_found"),
    ]


def test_a_rejected_refund_delivered_twice_is_listed_once():
    line = refund("2026-03-02T11:00:00Z", "evt_2", "acct_alpha", 400, "evt_404")
    assert rejected([line, line]) == [("evt_2", "charge_not_found")]


def test_the_first_line_in_the_input_wins_even_when_a_later_copy_has_an_earlier_timestamp():
    lines = [
        charge("2026-03-02T12:00:00Z", "evt_1", "acct_alpha", 1000),  # this is evt_1
        charge("2026-03-02T08:00:00Z", "evt_1", "acct_alpha", 9999),  # ignored: evt_1 was already seen
        refund("2026-03-02T10:00:00Z", "evt_2", "acct_alpha", 100, "evt_1"),  # evt_1 happens at 12:00, after this
    ]
    assert rejected(lines) == [("evt_2", "charge_not_found")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_an_account_whose_only_events_were_rejected_is_absent_from_balances():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        refund("2026-03-02T11:00:00Z", "evt_2", "acct_gamma", 100, "evt_1"),  # mismatch: acct_gamma has nothing else
        refund("2026-03-02T11:30:00Z", "evt_3", "acct_alpha", 100, "evt_1", "EUR"),  # mismatch: no other EUR event
    ]
    assert rejected(lines) == [("evt_2", "charge_mismatch"), ("evt_3", "charge_mismatch")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}


def test_malformed_lines_are_neither_processed_nor_reported_as_rejected():
    lines = [
        charge("2026-03-02T10:00:00Z", "evt_1", "acct_alpha", 1000),
        "2026-03-02T11:00:00Z,evt_2,refund,acct_alpha,100,USD",  # no charge_id: malformed, not "rejected"
        "2026-03-02T11:00:00Z,evt_3,refund,acct_alpha,100,USD,",  # empty charge_id: malformed
        "2026-03-02T11:00:00Z,evt_4,refund,acct_alpha,0,USD,evt_1",  # amount 0: malformed
        "2026-03-02T09:00:00Z,evt_5,charge,acct_alpha,abc,USD",  # malformed charge
        refund("2026-03-02T12:00:00Z", "evt_6", "acct_alpha", 100, "evt_5"),  # so evt_5 does not exist
    ]
    assert rejected(lines) == [("evt_6", "charge_not_found")]
    assert compute_balances(lines) == {"acct_alpha": {"USD": 1000}}
