"""Paying merchants what they are owed."""
from __future__ import annotations

from settlements.client import LarkspurClient
from settlements.models import Payout


def settle(client: LarkspurClient, merchant_id: str, settlement_date: str) -> list[Payout]:
    """Pay out the merchant's settlement for ``settlement_date`` (Part 3).

    ``settlement_date`` is a calendar date written as "YYYY-MM-DD".
    Returns the payouts, sorted by currency code.
    """
    raise NotImplementedError("Part 3: settle is not implemented yet")
