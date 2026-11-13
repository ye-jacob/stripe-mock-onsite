"""Typed views of the JSON objects returned by the Larkspur API.

All money amounts are integers in the currency's minor unit (cents, pence).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Merchant:
    id: str
    name: str
    country: str  # ISO 3166-1 alpha-2, e.g. "US"
    default_currency: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Merchant":
        return cls(
            id=data["id"],
            name=data["name"],
            country=data["country"],
            default_currency=data["default_currency"],
        )


@dataclass(frozen=True)
class Charge:
    id: str
    merchant: str
    amount: int
    currency: str  # lowercase ISO 4217, e.g. "usd"
    status: str  # "succeeded", "pending" or "failed"
    card_country: str  # country that issued the card, e.g. "US"
    created: int  # Unix timestamp
    description: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Charge":
        return cls(
            id=data["id"],
            merchant=data["merchant"],
            amount=data["amount"],
            currency=data["currency"],
            status=data["status"],
            card_country=data["card_country"],
            created=data["created"],
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class Refund:
    id: str
    merchant: str
    charge: str  # id of the refunded charge
    amount: int
    currency: str
    status: str  # "succeeded", "pending" or "failed"
    created: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Refund":
        return cls(
            id=data["id"],
            merchant=data["merchant"],
            charge=data["charge"],
            amount=data["amount"],
            currency=data["currency"],
            status=data["status"],
            created=data["created"],
        )


@dataclass(frozen=True)
class Payout:
    id: str
    merchant: str
    amount: int
    currency: str
    settlement_date: str  # "YYYY-MM-DD"
    status: str
    created: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Payout":
        return cls(
            id=data["id"],
            merchant=data["merchant"],
            amount=data["amount"],
            currency=data["currency"],
            settlement_date=data["settlement_date"],
            status=data["status"],
            created=data["created"],
        )
