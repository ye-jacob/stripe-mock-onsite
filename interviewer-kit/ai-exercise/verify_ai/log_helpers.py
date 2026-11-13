"""Small helpers for writing event logs in the verification suite."""


def charge(timestamp, event_id, merchant_id, amount, currency="USD"):
    return "%s,%s,charge,%s,%s,%s" % (timestamp, event_id, merchant_id, amount, currency)


def refund(timestamp, event_id, merchant_id, amount, charge_id, currency="USD"):
    return "%s,%s,refund,%s,%s,%s,%s" % (timestamp, event_id, merchant_id, amount, currency, charge_id)


def as_tuples(rows):
    """Accept lists or tuples for each row, so that only the content is compared."""
    return [tuple(row) for row in rows]


def assert_all_ints(value, where="result"):
    """Money is a whole number of minor units: no floats, no Decimals, no bools."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert_all_ints(item, "%s[%r]" % (where, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            if not isinstance(item, str):
                assert_all_ints(item, "%s[%d]" % (where, index))
    else:
        assert type(value) is int, "%s is %r (%s); amounts must be plain ints" % (where, value, type(value).__name__)
