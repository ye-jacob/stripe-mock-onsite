"""Paying merchants what they are owed.

REFERENCE SOLUTION. One reasonable way to do it, not the only one.
"""
from __future__ import annotations

from settlements.client import LarkspurClient
from settlements.models import Payout
from settlements.report import build_settlement


def settle(client: LarkspurClient, merchant_id: str, settlement_date: str) -> list[Payout]:
    """Pay out the merchant's settlement for ``settlement_date``.

    ``settlement_date`` is a calendar date written as "YYYY-MM-DD".
    Returns the payouts, sorted by currency code.

    A merchant is paid at most once per currency and settlement date. The
    idempotency key is derived from exactly those three things, so the API
    recognises a repeated request whether it comes from a retry inside the
    client or from a second run of this function, and answers with the payout
    it already created. The amount is deliberately not part of the key: if the
    net amount has changed since the first run, the API rejects the request
    (409) instead of silently paying a second time.
    """
    payouts = []
    for line in build_settlement(client, merchant_id):  # already sorted by currency
        if line.net <= 0:
            continue
        payouts.append(
            client.create_payout(
                merchant_id,
                line.net,
                line.currency,
                settlement_date,
                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}",
            )
        )
    return payouts
