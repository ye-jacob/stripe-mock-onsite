"""Settlement reports: what a merchant is owed, per currency.

REFERENCE SOLUTION. One reasonable way to do it, not the only one.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from settlements.client import LarkspurClient
from settlements.fees import calculate_fee

SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class SettlementLine:
    """Totals for one currency. All amounts are in minor units."""

    currency: str
    gross: int  # sum of the succeeded charges
    fees: int  # processing fees on those charges
    refunds: int  # sum of the succeeded refunds
    charge_count: int  # number of succeeded charges

    @property
    def net(self) -> int:
        """What the merchant is owed: gross - fees - refunds."""
        return self.gross - self.fees - self.refunds


def format_money(amount: int) -> str:
    """Minor units as a decimal string: 123456 -> '1,234.56', -5 -> '-0.05'."""
    sign = "-" if amount < 0 else ""
    units, cents = divmod(abs(amount), 100)
    return f"{sign}{units:,}.{cents:02d}"


_HEADER = ("Currency", "Gross", "Fees", "Refunds", "Net", "Charges")


def format_report(lines: list[SettlementLine]) -> str:
    """Render settlement lines as a plain-text table."""
    if not lines:
        return "Nothing to settle."
    rows = [_HEADER]
    for line in lines:
        rows.append(
            (
                line.currency.upper(),
                format_money(line.gross),
                format_money(line.fees),
                format_money(line.refunds),
                format_money(line.net),
                str(line.charge_count),
            )
        )
    widths = [max(len(row[column]) for row in rows) for column in range(len(_HEADER))]
    rendered = []
    for row in rows:
        cells = [row[0].ljust(widths[0])]
        cells += [cell.rjust(width) for cell, width in zip(row[1:], widths[1:])]
        rendered.append("  ".join(cells))
    return "\n".join(rendered)


def build_settlement(client: LarkspurClient, merchant_id: str) -> list[SettlementLine]:
    """One SettlementLine per currency with a succeeded charge, sorted by currency code."""
    merchant = client.get_merchant(merchant_id)

    gross: dict[str, int] = defaultdict(int)
    fees: dict[str, int] = defaultdict(int)
    charge_count: dict[str, int] = defaultdict(int)
    for charge in client.list_charges(merchant_id):
        if charge.status != SUCCEEDED:
            continue
        gross[charge.currency] += charge.amount
        fees[charge.currency] += calculate_fee(
            charge.amount,
            charge.currency,
            cross_border=charge.card_country != merchant.country,
        )
        charge_count[charge.currency] += 1

    refunds: dict[str, int] = defaultdict(int)
    for refund in client.list_refunds(merchant_id):
        if refund.status == SUCCEEDED:
            refunds[refund.currency] += refund.amount

    return [
        SettlementLine(
            currency=currency,
            gross=gross[currency],
            fees=fees[currency],
            refunds=refunds[currency],
            charge_count=charge_count[currency],
        )
        for currency in sorted(gross)
    ]
