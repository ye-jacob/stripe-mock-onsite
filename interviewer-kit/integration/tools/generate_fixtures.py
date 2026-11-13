#!/usr/bin/env python3
"""Regenerate the mock API's data and the expected settlement numbers.

Interviewer tooling: the candidate never sees this file.

    python generate_fixtures.py <fixtures.json> <expected.json>

The data is deterministic (fixed seed). The expected numbers are computed here
with plain integer arithmetic, independently of the reference solution, so the
two can be checked against each other.
"""
from __future__ import annotations

import json
import random
import sys
from calendar import timegm
from pathlib import Path

SEED = 20261111
ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
END_OF_DATA = timegm((2026, 11, 10, 18, 0, 0))  # 2026-11-10T18:00:00Z

FIXED_FEES = {"usd": 30, "eur": 25, "gbp": 20}

MERCHANTS = [
    {"id": "acct_tidewater", "name": "Tidewater Surf Co.", "country": "US", "default_currency": "usd"},
    {"id": "acct_nimbus", "name": "Nimbus Coffee Roasters", "country": "US", "default_currency": "usd"},
    {"id": "acct_orchard", "name": "Orchard Lane Books", "country": "GB", "default_currency": "gbp"},
    {"id": "acct_sprout", "name": "Sprout Analytics GmbH", "country": "DE", "default_currency": "eur"},
    {"id": "acct_breakeven", "name": "Breakeven Bikes", "country": "US", "default_currency": "usd"},
    {"id": "acct_ghost", "name": "Ghost Kitchen Collective", "country": "US", "default_currency": "usd"},
]


class Builder:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.used_ids: set[str] = set()
        self.charges: list[dict] = []
        self.refunds: list[dict] = []

    def new_id(self, prefix: str) -> str:
        while True:
            candidate = prefix + "".join(self.rng.choice(ALPHABET) for _ in range(14))
            if candidate not in self.used_ids:
                self.used_ids.add(candidate)
                return candidate

    def add_charges(self, merchant_id: str, specs: list[tuple], first_order: int, newest: int) -> list[dict]:
        """specs are oldest first: (amount, currency, status, card_country)."""
        created = newest
        timestamps = []
        for _ in specs:
            timestamps.append(created)
            created -= self.rng.randrange(15, 480) * 60
        timestamps.reverse()  # oldest first, like the specs
        made = []
        for index, (amount, currency, status, card_country) in enumerate(specs):
            charge = {
                "id": self.new_id("ch_"),
                "object": "charge",
                "merchant": merchant_id,
                "amount": amount,
                "currency": currency,
                "status": status,
                "card_country": card_country,
                "created": timestamps[index],
                "description": "Order #%d" % (first_order + index),
            }
            made.append(charge)
        self.charges.extend(made)
        return made

    def add_refund(self, charge: dict, amount: int, status: str) -> dict:
        assert charge["status"] == "succeeded", "refunds only make sense on succeeded charges"
        refund = {
            "id": self.new_id("re_"),
            "object": "refund",
            "merchant": charge["merchant"],
            "charge": charge["id"],
            "amount": amount,
            "currency": charge["currency"],
            "status": status,
            "created": min(END_OF_DATA, charge["created"] + self.rng.randrange(1, 72 * 60) * 60),
        }
        self.refunds.append(refund)
        return refund


def build() -> tuple[dict, dict]:
    b = Builder()
    rng = b.rng

    # --- acct_tidewater: the small, hand-checkable merchant used in the README ----
    tidewater = b.add_charges(
        "acct_tidewater",
        [
            (20000, "usd", "succeeded", "US"),
            (8250, "usd", "pending", "GB"),
            (500, "usd", "succeeded", "US"),
            (2500, "usd", "failed", "US"),
            (12500, "usd", "succeeded", "CA"),
            (4999, "usd", "succeeded", "US"),
        ],
        first_order=1001,
        newest=END_OF_DATA - 3 * 3600,
    )
    b.add_refund(tidewater[0], 2000, "succeeded")
    b.add_refund(tidewater[5], 500, "failed")

    # --- acct_nimbus: the big one (several pages, two currencies) -----------------
    required = [
        # amounts chosen to hit exact .5 cases in the 2.9% and 1.5% calculations
        (500, "usd", "succeeded", "US"),
        (1500, "usd", "succeeded", "CA"),
        (2500, "usd", "succeeded", "US"),
        (300, "usd", "succeeded", "GB"),
        (100, "usd", "succeeded", "US"),
        (10500, "usd", "succeeded", "DE"),
        (99999, "usd", "succeeded", "US"),
        (250000, "usd", "succeeded", "FR"),
        (4999, "usd", "succeeded", "US"),
        (1999, "usd", "succeeded", "US"),
        (500, "eur", "succeeded", "DE"),
        (1500, "eur", "succeeded", "US"),
        (7300, "eur", "succeeded", "FR"),
        (2500, "eur", "succeeded", "US"),
    ]
    filler = []
    cards_for_us_merchant = ["US"] * 12 + ["CA", "CA", "GB", "GB", "DE", "FR", "JP", "AU"]
    plan = (
        [("usd", "succeeded")] * 23 + [("usd", "failed")] * 4 + [("usd", "pending")] * 3
        + [("eur", "succeeded")] * 9 + [("eur", "failed")] * 2 + [("eur", "pending")] * 2
    )
    for currency, status in plan:
        style = rng.random()
        if style < 0.35:
            amount = rng.randrange(3, 400) * 100 + 99  # "x.99" prices
        elif style < 0.7:
            amount = rng.randrange(6, 900) * 50
        else:
            amount = rng.randrange(300, 60000)
        filler.append((amount, currency, status, rng.choice(cards_for_us_merchant)))
    nimbus_specs = required + filler
    rng.shuffle(nimbus_specs)
    nimbus = b.add_charges("acct_nimbus", nimbus_specs, first_order=4201, newest=END_OF_DATA - 20 * 60)
    assert len(nimbus) == 57

    def refund_some(charges, currency, succeeded_count, failed_count):
        pool = [c for c in charges if c["status"] == "succeeded" and c["currency"] == currency and c["amount"] >= 1000]
        remaining = {c["id"]: c["amount"] for c in pool}
        made_ok = 0
        while made_ok < succeeded_count:
            charge = rng.choice(pool)
            left = remaining[charge["id"]]
            if left < 200:
                continue
            style = rng.random()
            if style < 0.2:
                amount = left  # refund everything that is left
            else:
                amount = max(100, (rng.randrange(10, 90) * left // 100) // 50 * 50)
            amount = min(amount, left)
            b.add_refund(charge, amount, "succeeded")
            remaining[charge["id"]] -= amount
            made_ok += 1
        for _ in range(failed_count):
            charge = rng.choice(pool)
            b.add_refund(charge, max(100, charge["amount"] // 2), "failed")

    refund_some(nimbus, "usd", succeeded_count=14, failed_count=3)
    refund_some(nimbus, "eur", succeeded_count=6, failed_count=1)

    # --- acct_orchard: UK merchant; EUR nets below zero, GBP is paid out ----------
    cards_for_gb_merchant = ["GB"] * 9 + ["US", "FR", "DE", "IE"]
    orchard_specs = []
    for status in ["succeeded"] * 12 + ["failed"] * 2 + ["pending"]:
        amount = rng.choice([rng.randrange(4, 120) * 100 + 99, rng.randrange(8, 400) * 50, rng.randrange(300, 20000)])
        orchard_specs.append((amount, "gbp", status, rng.choice(cards_for_gb_merchant)))
    orchard_specs += [
        (1500, "gbp", "succeeded", "US"),  # 43.5 -> 44 and 22.5 -> 23
        (3000, "eur", "succeeded", "FR"),
        (1800, "eur", "succeeded", "GB"),
        (4200, "eur", "failed", "FR"),
        (990, "eur", "failed", "DE"),
        (15000, "eur", "failed", "GB"),
        (2650, "eur", "failed", "ES"),
        (7200, "eur", "pending", "FR"),
        (640, "eur", "pending", "GB"),
    ]
    # one of the 15 random GBP charges makes room for the hand-picked one: keep 23 in total
    orchard_specs.pop(0)
    rng.shuffle(orchard_specs)
    orchard = b.add_charges("acct_orchard", orchard_specs, first_order=880, newest=END_OF_DATA - 95 * 60)
    assert len(orchard) == 23
    for charge in orchard:
        if charge["currency"] == "eur" and charge["status"] == "succeeded":
            b.add_refund(charge, charge["amount"], "succeeded")  # refunded in full
    gbp_ok = [c for c in orchard if c["currency"] == "gbp" and c["status"] == "succeeded" and c["amount"] >= 1000]
    for charge, share in zip(rng.sample(gbp_ok, 3), (25, 50, 100)):
        b.add_refund(charge, charge["amount"] * share // 100, "succeeded")
    b.add_refund(rng.choice(gbp_ok), 700, "failed")

    # --- acct_sprout: more refunded than earned, so nothing may be paid out --------
    sprout = b.add_charges(
        "acct_sprout",
        [
            (4000, "eur", "succeeded", "DE"),
            (9900, "eur", "failed", "DE"),
            (2500, "eur", "succeeded", "FR"),
        ],
        first_order=17,
        newest=END_OF_DATA - 26 * 3600,
    )
    b.add_refund(sprout[0], 4000, "succeeded")
    b.add_refund(sprout[2], 2400, "succeeded")

    # --- acct_breakeven: the net is exactly zero, which must not be paid out ---------
    breakeven = b.add_charges(
        "acct_breakeven",
        [(1000, "usd", "succeeded", "US")],  # fee 29 + 30 = 59
        first_order=3,
        newest=END_OF_DATA - 50 * 3600,
    )
    b.add_refund(breakeven[0], 941, "succeeded")

    # --- acct_ghost: no activity at all ------------------------------------------

    charges = sorted(b.charges, key=lambda c: (-c["created"], c["id"]))
    refunds = sorted(b.refunds, key=lambda r: (-r["created"], r["id"]))
    merchants = [dict(m, object="merchant") for m in MERCHANTS]
    fixtures = {"merchants": merchants, "charges": charges, "refunds": refunds}
    return fixtures, expected_results(fixtures)


def half_up(amount: int, per_mille: int) -> int:
    """amount * per_mille / 1000, exact halves rounded up, in integers only."""
    return (2 * amount * per_mille + 1000) // 2000


def expected_results(fixtures: dict) -> dict:
    results = {}
    for merchant in fixtures["merchants"]:
        merchant_id = merchant["id"]
        charges = [c for c in fixtures["charges"] if c["merchant"] == merchant_id]
        refunds = [r for r in fixtures["refunds"] if r["merchant"] == merchant_id]
        per_currency: dict[str, dict] = {}
        for charge in charges:
            if charge["status"] != "succeeded":
                continue
            line = per_currency.setdefault(
                charge["currency"], {"currency": charge["currency"], "gross": 0, "fees": 0, "refunds": 0, "charge_count": 0}
            )
            fee = half_up(charge["amount"], 29) + FIXED_FEES[charge["currency"]]
            if charge["card_country"] != merchant["country"]:
                fee += half_up(charge["amount"], 15)
            line["gross"] += charge["amount"]
            line["fees"] += fee
            line["charge_count"] += 1
        for refund in refunds:
            if refund["status"] == "succeeded":
                per_currency[refund["currency"]]["refunds"] += refund["amount"]
        lines = []
        for currency in sorted(per_currency):
            line = per_currency[currency]
            line["net"] = line["gross"] - line["fees"] - line["refunds"]
            lines.append(line)
        results[merchant_id] = {
            "charge_ids": [c["id"] for c in charges],
            "refund_count": len(refunds),
            "settlement": lines,
            "payouts": [{"currency": l["currency"], "amount": l["net"]} for l in lines if l["net"] > 0],
            "common_mistakes": {
                currency: common_mistakes(merchant, charges, refunds, currency) for currency in sorted(per_currency)
            },
        }
    return results


def common_mistakes(merchant: dict, charges: list[dict], refunds: list[dict], currency: str) -> dict:
    """Totals that well-known wrong implementations produce.

    The verification suite uses them to say *why* a number is wrong.
    """
    from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal

    def rounded(amount: int, per_mille: int, mode: str) -> int:
        return int((Decimal(amount) * per_mille / 1000).quantize(Decimal("1"), rounding=mode))

    mine = [c for c in charges if c["currency"] == currency]
    ok = [c for c in mine if c["status"] == "succeeded"]
    cross = lambda c: c["card_country"] != merchant["country"]  # noqa: E731
    fixed = FIXED_FEES[currency]
    my_refunds = [r for r in refunds if r["currency"] == currency]

    def fees_with(charge_list, surcharge=True, combined=False, mode=None):
        total = 0
        for c in charge_list:
            if combined and cross(c):
                total += half_up(c["amount"], 44) + fixed
                continue
            if mode is None:
                fee = half_up(c["amount"], 29) + fixed
                if surcharge and cross(c):
                    fee += half_up(c["amount"], 15)
            else:
                fee = rounded(c["amount"], 29, mode) + fixed
                if surcharge and cross(c):
                    fee += rounded(c["amount"], 15, mode)
            total += fee
        return total

    def first_page(items, size, field="amount"):
        return sum(i[field] for i in items[:size] if i["status"] == "succeeded" and i["currency"] == currency)

    return {
        "fees": {
            "without the cross-border surcharge": fees_with(ok, surcharge=False),
            "with the surcharge applied to every charge": sum(
                half_up(c["amount"], 29) + fixed + half_up(c["amount"], 15) for c in ok
            ),
            "with 2.9% and 1.5% added before rounding (4.4% rounded once)": fees_with(ok, combined=True),
            "with banker's rounding (round half to even)": fees_with(ok, mode=ROUND_HALF_EVEN),
            "with percentages truncated instead of rounded": fees_with(ok, mode=ROUND_DOWN),
            "with fees charged on pending and failed charges too": fees_with(mine),
            "with fees charged on pending charges too": fees_with([c for c in mine if c["status"] != "failed"]),
        },
        "gross": {
            "with pending and failed charges included": sum(c["amount"] for c in mine),
            "with pending charges included": sum(c["amount"] for c in mine if c["status"] != "failed"),
            "from the first page of charges only (10 per page)": first_page(charges, 10),
            "from the first page of charges only (20 per page)": first_page(charges, 20),
        },
        "refunds": {
            "with failed refunds included": sum(r["amount"] for r in my_refunds),
            "from the first page of refunds only (10 per page)": first_page(refunds, 10),
            "from the first page of refunds only (20 per page)": first_page(refunds, 20),
            "with no refunds subtracted": 0,
        },
        "charge_count": {
            "with pending and failed charges included": len(mine),
            "with pending charges included": len([c for c in mine if c["status"] != "failed"]),
        },
    }


def validate(fixtures: dict) -> None:
    by_id = {c["id"]: c for c in fixtures["charges"]}
    refunded: dict[str, int] = {}
    for refund in fixtures["refunds"]:
        charge = by_id[refund["charge"]]
        assert charge["status"] == "succeeded"
        assert charge["merchant"] == refund["merchant"] and charge["currency"] == refund["currency"]
        assert refund["amount"] > 0
        assert refund["created"] >= charge["created"]
        if refund["status"] == "succeeded":
            refunded[charge["id"]] = refunded.get(charge["id"], 0) + refund["amount"]
            assert refunded[charge["id"]] <= charge["amount"], "over-refunded charge"
    for charge in fixtures["charges"]:
        assert charge["amount"] >= 100 and charge["currency"] in FIXED_FEES
    ids = [c["id"] for c in fixtures["charges"]] + [r["id"] for r in fixtures["refunds"]]
    assert len(ids) == len(set(ids)), "duplicate ids"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    fixtures, expected = build()
    validate(fixtures)
    Path(argv[1]).write_text(json.dumps(fixtures, indent=1) + "\n", encoding="utf-8")
    Path(argv[2]).write_text(json.dumps(expected, indent=1) + "\n", encoding="utf-8")
    for merchant_id, result in expected.items():
        print(merchant_id, len(result["charge_ids"]), "charges,", result["refund_count"], "refunds")
        for line in result["settlement"]:
            print("   ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
