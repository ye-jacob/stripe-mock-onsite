"""Part 1: LarkspurClient.list_charges fetches every page and copes with rate limits."""
import pytest
import requests

from verify_helpers import call
from server.mock_api import API_KEY
from settlements.errors import RateLimitError
from settlements.models import Charge

MERCHANTS = ["acct_tidewater", "acct_nimbus", "acct_orchard", "acct_sprout", "acct_breakeven", "acct_ghost"]


def _ids(charges):
    return [charge.id for charge in charges]


@pytest.mark.parametrize("merchant_id", MERCHANTS)
def test_returns_every_charge_in_api_order(mock_api, new_client, expected, merchant_id):
    client = new_client(mock_api())
    charges = call(client.list_charges, merchant_id)
    want = expected[merchant_id]["charge_ids"]

    assert isinstance(charges, list), "list_charges must return a list"
    assert all(isinstance(charge, Charge) for charge in charges), "list_charges must return Charge objects"
    got = _ids(charges)
    if got != want:
        hint = ""
        if len(got) in (10, 20) and got == want[: len(got)]:
            hint = " This is exactly the first page: the remaining pages were never requested."
        elif sorted(got) == sorted(want):
            hint = " All charges are there but not in the order the API lists them (newest first)."
        elif len(got) > len(set(got)):
            hint = " Some charges appear more than once: check which id is passed as starting_after."
        pytest.fail("Expected %d charges for %s, got %d.%s" % (len(want), merchant_id, len(got), hint))


def test_keeps_going_when_some_requests_are_rate_limited(mock_api, new_client, expected):
    server = mock_api(rate_limit_every=2)  # every 2nd request is rejected with 429, Retry-After: 0
    client = new_client(server)
    charges = call(client.list_charges, "acct_nimbus")

    assert _ids(charges) == expected["acct_nimbus"]["charge_ids"]
    assert server.state.stats["rate_limited"] > 0, "the test server should have rate-limited at least once"


def test_waits_as_long_as_retry_after_says_before_retrying(mock_api, new_client, expected):
    server = mock_api(rate_limit_every=2, retry_after=2)
    # Use up the first slot so that the client's very first request is the one that gets rejected.
    requests.get(
        server.base_url + "/v1/merchants/acct_tidewater",
        headers={"Authorization": "Bearer " + API_KEY},
        timeout=5,
    )
    client = new_client(server)
    charges = call(client.list_charges, "acct_tidewater", timeout=40)

    assert _ids(charges) == expected["acct_tidewater"]["charge_ids"]
    assert server.state.stats["rate_limited"] >= 1
    assert server.state.stats["early_retries"] == 0, (
        "The API answered 429 with 'Retry-After: 2', but the client sent its next request "
        "before those 2 seconds were over (%d time(s))." % server.state.stats["early_retries"]
    )


def test_gives_up_with_rate_limit_error_when_the_api_never_recovers(mock_api, new_client):
    server = mock_api(rate_limit_every=1)  # every request is rejected
    client = new_client(server)
    with pytest.raises(RateLimitError):
        call(client.list_charges, "acct_tidewater")

    attempts = server.state.stats["requests"]
    assert attempts >= 2, "a rate-limited request should be retried at least once before giving up"
    assert attempts <= 50, "gave up only after %d attempts: that is not a reasonable limit" % attempts
