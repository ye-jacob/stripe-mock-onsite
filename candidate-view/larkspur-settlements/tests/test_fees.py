import pytest

from settlements.fees import calculate_fee


@pytest.mark.parametrize(
    "amount, currency, expected",
    [
        (1000, "usd", 59),  # 29 + 30
        (1000, "eur", 54),  # 29 + 25
        (1000, "gbp", 49),  # 29 + 20
        (4999, "usd", 175),  # 144.971 -> 145, + 30
        (100, "usd", 33),  # 2.9 -> 3, + 30
        (250000, "eur", 7275),  # 7250 + 25
    ],
)
def test_calculate_fee(amount, currency, expected):
    assert calculate_fee(amount, currency) == expected


@pytest.mark.parametrize(
    "amount, expected",
    [
        (500, 45),  # 14.5 -> 15, + 30
        (1500, 74),  # 43.5 -> 44, + 30
        (2500, 103),  # 72.5 -> 73, + 30
    ],
)
def test_percentage_is_rounded_half_up(amount, expected):
    assert calculate_fee(amount, "usd") == expected


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
