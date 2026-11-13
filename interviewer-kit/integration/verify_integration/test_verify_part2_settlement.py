"""Part 2: build_settlement produces the right numbers per currency."""
import pytest

from verify_helpers import call
from settlements.cli import main
from settlements.fees import calculate_fee
from settlements.report import SettlementLine, build_settlement

FIELDS = ("gross", "fees", "refunds", "charge_count", "net")


def _check_settlement(lines, merchant_id, expected):
    want = expected[merchant_id]["settlement"]
    mistakes = expected[merchant_id]["common_mistakes"]

    assert isinstance(lines, list), "build_settlement must return a list"
    assert all(isinstance(line, SettlementLine) for line in lines), "build_settlement must return SettlementLine objects"
    got_currencies = [line.currency for line in lines]
    want_currencies = [line["currency"] for line in want]
    assert got_currencies == want_currencies, "expected one line per currency with a succeeded charge, sorted by currency code"

    problems = []
    for line, want_line in zip(lines, want):
        for field in FIELDS:
            got_value = getattr(line, field)
            if got_value == want_line[field]:
                continue
            message = "%s %s.%s: expected %d, got %d" % (merchant_id, line.currency, field, want_line[field], got_value)
            for description, wrong_value in mistakes[line.currency].get(field, {}).items():
                if wrong_value == got_value:
                    message += "  <- this is the total %s" % description
            problems.append(message)
    assert not problems, "\n" + "\n".join(problems)


def test_tidewater_matches_the_readme_example(mock_api, new_client):
    """Hand-checked numbers, the same ones the README shows."""
    lines = call(build_settlement, new_client(mock_api()), "acct_tidewater")
    assert [(l.currency, l.gross, l.fees, l.refunds, l.net, l.charge_count) for l in lines] == [
        ("usd", 37999, 1411, 2000, 34588, 4)
    ]


@pytest.mark.parametrize("merchant_id", ["acct_tidewater", "acct_nimbus", "acct_orchard", "acct_sprout", "acct_breakeven"])
def test_settlement_numbers(mock_api, new_client, expected, merchant_id):
    lines = call(build_settlement, new_client(mock_api()), merchant_id)
    _check_settlement(lines, merchant_id, expected)


def test_merchant_without_activity_has_no_lines(mock_api, new_client):
    assert call(build_settlement, new_client(mock_api()), "acct_ghost") == []


def test_settlement_is_correct_when_requests_are_rate_limited(mock_api, new_client, expected):
    server = mock_api(rate_limit_every=2)
    lines = call(build_settlement, new_client(server), "acct_nimbus")
    _check_settlement(lines, "acct_nimbus", expected)
    assert server.state.stats["rate_limited"] > 0


def test_existing_callers_of_calculate_fee_still_get_the_standard_fee():
    assert calculate_fee(1000, "usd") == 59
    assert calculate_fee(12500, "usd") == 393  # 362.5 -> 363, + 30: no surcharge unless asked for


def test_report_command_prints_the_readme_example(mock_api, monkeypatch, capsys):
    monkeypatch.setenv("LARKSPUR_BASE_URL", mock_api().base_url)
    assert call(main, ["report", "acct_tidewater"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Currency   Gross   Fees  Refunds     Net  Charges",
        "USD       379.99  14.11    20.00  345.88        4",
    ]
