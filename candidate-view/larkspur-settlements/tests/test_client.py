import pytest

from server.mock_api import API_KEY
from settlements.client import LarkspurClient
from settlements.errors import AuthenticationError, NotFoundError, RateLimitError
from settlements.models import Merchant


def test_get_merchant(client):
    assert client.get_merchant("acct_tidewater") == Merchant(
        id="acct_tidewater",
        name="Tidewater Surf Co.",
        country="US",
        default_currency="usd",
    )


def test_unknown_merchant_raises_not_found(client):
    with pytest.raises(NotFoundError) as excinfo:
        client.get_merchant("acct_does_not_exist")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "resource_missing"


def test_wrong_api_key_raises_authentication_error(api):
    client = LarkspurClient(api_key="lk_test_wrong", base_url=api.base_url)
    with pytest.raises(AuthenticationError):
        client.get_merchant("acct_tidewater")


def test_rate_limit_error_reaches_the_caller_when_the_api_keeps_rejecting(mock_api):
    server = mock_api(rate_limit_every=1)  # this server rejects every single request
    client = LarkspurClient(api_key=API_KEY, base_url=server.base_url)
    with pytest.raises(RateLimitError) as excinfo:
        client.get_merchant("acct_tidewater")
    assert excinfo.value.status == 429
    assert excinfo.value.retry_after == 0
