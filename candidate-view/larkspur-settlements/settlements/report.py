"""Settlement reports: what a merchant is owed, per currency."""
from __future__ import annotations

from dataclasses import dataclass

from settlements.client import LarkspurClient


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
    """One SettlementLine per currency, sorted by currency code (Part 2)."""
    raise NotImplementedError("Part 2: build_settlement is not implemented yet")
