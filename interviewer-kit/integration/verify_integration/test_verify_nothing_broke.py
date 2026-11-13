"""The behaviour that existed before the exercise must be unchanged.

These are the tests that shipped in `tests/` on day one (plus one extra check
of the same behaviour), kept here so that edits to `tests/` during the
interview cannot hide a regression.
"""
import socket

import pytest

from verify_helpers import call
from server.mock_api import API_KEY
from settlements.cli import main
from settlements.client import LarkspurClient
from settlements.errors import AuthenticationError, NotFoundError, RateLimitError
from settlements.fees import calculate_fee
from settlements.models import Merchant
from settlements.report import SettlementLine, format_money, format_report


@pytest.fixture
def api(mock_api):
    return mock_api()


@pytest.fixture
def client(api, new_client):
    return new_client(api)


# -- client ---------------------------------------------------------------------


def test_get_merchant(client):
    assert call(client.get_merchant, "acct_tidewater") == Merchant(
        id="acct_tidewater",
        name="Tidewater Surf Co.",
        country="US",
        default_currency="usd",
    )


def test_unknown_merchant_raises_not_found(client):
    with pytest.raises(NotFoundError) as excinfo:
        call(client.get_merchant, "acct_does_not_exist")
    assert excinfo.value.status == 404
    assert excinfo.value.code == "resource_missing"


def test_wrong_api_key_raises_authentication_error(api):
    client = LarkspurClient(api_key="lk_test_wrong", base_url=api.base_url)
    with pytest.raises(AuthenticationError):
        call(client.get_merchant, "acct_tidewater")


def test_client_errors_are_not_retried(api, client):
    with pytest.raises(NotFoundError):
        call(client.get_merchant, "acct_does_not_exist")
    assert api.state.stats["requests"] == 1, "a 404 will never succeed on retry: it must not be retried"


def test_rate_limit_error_reaches_the_caller_when_the_api_keeps_rejecting(mock_api):
    server = mock_api(rate_limit_every=1)  # this server rejects every single request
    client = LarkspurClient(api_key=API_KEY, base_url=server.base_url)
    with pytest.raises(RateLimitError) as excinfo:
        call(client.get_merchant, "acct_tidewater")
    assert excinfo.value.status == 429
    assert excinfo.value.retry_after == 0


# -- fees -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "amount, currency, expected",
    [
        (1000, "usd", 59),
        (1000, "eur", 54),
        (1000, "gbp", 49),
        (4999, "usd", 175),
        (100, "usd", 33),
        (250000, "eur", 7275),
        (500, "usd", 45),
        (1500, "usd", 74),
        (2500, "usd", 103),
    ],
)
def test_calculate_fee(amount, currency, expected):
    assert calculate_fee(amount, currency) == expected


def test_unsupported_currency_is_rejected():
    with pytest.raises(ValueError):
        calculate_fee(1000, "jpy")


@pytest.mark.parametrize("amount", [0, -100])
def test_amount_must_be_positive(amount):
    with pytest.raises(ValueError):
        calculate_fee(amount, "usd")


@pytest.mark.parametrize("amount", [10.5, "1000", True])
def test_amount_must_be_an_integer(amount):
    with pytest.raises(TypeError):
        calculate_fee(amount, "usd")


# -- report formatting ----------------------------------------------------------


@pytest.mark.parametrize(
    "amount, expected",
    [(0, "0.00"), (5, "0.05"), (1999, "19.99"), (123456789, "1,234,567.89"), (-5, "-0.05"), (-123456, "-1,234.56")],
)
def test_format_money(amount, expected):
    assert format_money(amount) == expected


def test_format_report():
    lines = [
        SettlementLine(currency="eur", gross=250000, fees=7275, refunds=0, charge_count=1),
        SettlementLine(currency="usd", gross=10000, fees=320, refunds=11000, charge_count=3),
    ]
    assert lines[1].net == -1320
    assert format_report(lines).splitlines() == [
        "Currency     Gross   Fees  Refunds       Net  Charges",
        "EUR       2,500.00  72.75     0.00  2,427.25        1",
        "USD         100.00   3.20   110.00    -13.20        3",
    ]
    assert format_report([]) == "Nothing to settle."


# -- command line ---------------------------------------------------------------


def test_fee_command(capsys):
    assert main(["fee", "1000", "usd"]) == 0
    assert capsys.readouterr().out.strip() == "Fee for a 10.00 USD charge: 0.59 USD"


def test_merchant_command(api, monkeypatch, capsys):
    monkeypatch.setenv("LARKSPUR_BASE_URL", api.base_url)
    assert call(main, ["merchant", "acct_tidewater"]) == 0
    assert capsys.readouterr().out.strip() == "acct_tidewater  Tidewater Surf Co.  country=US  currency=usd"


def test_unreachable_api_is_reported_without_a_traceback(monkeypatch, capsys):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    monkeypatch.setenv("LARKSPUR_BASE_URL", "http://127.0.0.1:%d" % unused_port)
    assert call(main, ["merchant", "acct_tidewater"]) == 2
    assert "Could not reach the Larkspur API" in capsys.readouterr().err
