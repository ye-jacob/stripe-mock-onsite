"""Part 3: settle pays each positive net exactly once, whatever the API does."""
import pytest

from verify_helpers import call
from settlements.models import Payout
from settlements.settle import settle

DATE = "2026-11-12"


def _summary(payouts):
    return [(payout.currency, payout.amount, payout.settlement_date) for payout in payouts]


def _want(expected, merchant_id, date=DATE):
    return [(payout["currency"], payout["amount"], date) for payout in expected[merchant_id]["payouts"]]


def _server_summary(server, merchant_id):
    return sorted(
        (payout["currency"], payout["amount"], payout["settlement_date"])
        for payout in server.state.payouts
        if payout["merchant"] == merchant_id
    )


def _describe_duplicates(server):
    return "; ".join(
        "%s %s %s was paid %d times (%s)"
        % (group["merchant"], group["currency"], group["settlement_date"], len(group["payouts"]), ", ".join(group["payouts"]))
        for group in server.state.duplicates()
    )


@pytest.mark.parametrize("merchant_id", ["acct_tidewater", "acct_nimbus", "acct_orchard"])
def test_pays_the_net_amount_of_every_positive_currency(mock_api, new_client, expected, merchant_id):
    server = mock_api()  # a reliable API
    payouts = call(settle, new_client(server), merchant_id, DATE)

    assert isinstance(payouts, list), "settle must return a list"
    assert all(isinstance(payout, Payout) for payout in payouts), "settle must return Payout objects"
    assert _summary(payouts) == _want(expected, merchant_id), "wrong payouts returned (expected one per positive net, sorted by currency)"
    assert _server_summary(server, merchant_id) == sorted(_want(expected, merchant_id)), "the API holds different payouts from the ones expected"
    assert sorted(payout.id for payout in payouts) == sorted(p["id"] for p in server.state.payouts), "returned payout ids do not match the payouts the API created"


@pytest.mark.parametrize("merchant_id", ["acct_sprout", "acct_breakeven", "acct_ghost"])
def test_nothing_is_paid_when_no_net_is_positive(mock_api, new_client, merchant_id):
    server = mock_api()
    assert call(settle, new_client(server), merchant_id, DATE) == []
    assert server.state.payouts == [], "no payout should have been created"
    assert server.state.stats["payout_requests"] == 0, "no payout request should even have been sent"


def test_no_duplicate_when_a_request_fails_after_creating_the_payout(mock_api, new_client, expected):
    server = mock_api(flaky_payouts=True)  # first attempt of every new payout: created, then 503
    payouts = call(settle, new_client(server), "acct_nimbus", DATE)

    assert server.state.stats["payout_503s"] > 0, "the test server should have failed at least one payout request"
    assert _summary(payouts) == _want(expected, "acct_nimbus")
    assert not server.state.duplicates(), "Merchant was paid twice: " + _describe_duplicates(server)
    assert _server_summary(server, "acct_nimbus") == sorted(_want(expected, "acct_nimbus"))


def test_second_run_returns_the_same_payouts_and_creates_none(mock_api, new_client, expected):
    server = mock_api(flaky_payouts=True)
    first = call(settle, new_client(server), "acct_nimbus", DATE)
    created_after_first_run = len(server.state.payouts)
    # A brand-new client, as if the tool had been started again later.
    second = call(settle, new_client(server), "acct_nimbus", DATE)

    assert _summary(first) == _want(expected, "acct_nimbus")
    assert len(server.state.payouts) == created_after_first_run, (
        "running settle again created %d more payout(s). %s"
        % (len(server.state.payouts) - created_after_first_run, _describe_duplicates(server))
    )
    assert [payout.id for payout in second] == [payout.id for payout in first], "the second run should return the same payouts as the first"
    assert _summary(second) == _summary(first)


def test_each_settlement_date_is_paid_separately(mock_api, new_client, expected):
    server = mock_api(flaky_payouts=True)
    client = new_client(server)
    first = call(settle, client, "acct_tidewater", "2026-11-12")
    second = call(settle, client, "acct_tidewater", "2026-11-13")

    assert _summary(first) == _want(expected, "acct_tidewater", "2026-11-12")
    assert _summary(second) == _want(expected, "acct_tidewater", "2026-11-13"), "a different settlement date is a different settlement"
    assert not server.state.duplicates(), "Merchant was paid twice: " + _describe_duplicates(server)
    assert len(server.state.payouts) == 2


def test_settle_survives_rate_limits_and_failing_payouts_together(mock_api, new_client, expected):
    server = mock_api(rate_limit_every=3, flaky_payouts=True)
    payouts = call(settle, new_client(server), "acct_nimbus", DATE)

    assert _summary(payouts) == _want(expected, "acct_nimbus")
    assert not server.state.duplicates(), "Merchant was paid twice: " + _describe_duplicates(server)
    assert _server_summary(server, "acct_nimbus") == sorted(_want(expected, "acct_nimbus"))
