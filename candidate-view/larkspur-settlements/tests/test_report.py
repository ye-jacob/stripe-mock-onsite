import pytest

from settlements.report import SettlementLine, format_money, format_report


@pytest.mark.parametrize(
    "amount, expected",
    [
        (0, "0.00"),
        (5, "0.05"),
        (1999, "19.99"),
        (123456789, "1,234,567.89"),
        (-5, "-0.05"),
        (-123456, "-1,234.56"),
    ],
)
def test_format_money(amount, expected):
    assert format_money(amount) == expected


def test_net_is_gross_minus_fees_minus_refunds():
    line = SettlementLine(currency="usd", gross=10000, fees=320, refunds=1500, charge_count=3)
    assert line.net == 8180


def test_format_report():
    lines = [
        SettlementLine(currency="eur", gross=250000, fees=7275, refunds=0, charge_count=1),
        SettlementLine(currency="usd", gross=10000, fees=320, refunds=11000, charge_count=3),
    ]
    assert format_report(lines).splitlines() == [
        "Currency     Gross   Fees  Refunds       Net  Charges",
        "EUR       2,500.00  72.75     0.00  2,427.25        1",
        "USD         100.00   3.20   110.00    -13.20        3",
    ]


def test_format_report_without_lines():
    assert format_report([]) == "Nothing to settle."
