"""Command line interface: ``python -m settlements <command>``."""
from __future__ import annotations

import argparse
import sys

import requests

from settlements import config
from settlements.client import LarkspurClient
from settlements.errors import ApiError
from settlements.fees import calculate_fee
from settlements.report import build_settlement, format_money, format_report
from settlements.settle import settle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m settlements",
        description="Settlement tooling on top of the Larkspur Payments API.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    merchant = commands.add_parser("merchant", help="show a merchant")
    merchant.add_argument("merchant_id")

    fee = commands.add_parser("fee", help="processing fee for a single charge")
    fee.add_argument("amount", type=int, help="charge amount in minor units")
    fee.add_argument("currency", help="lowercase currency code, e.g. usd")

    charges = commands.add_parser("charges", help="list every charge of a merchant")
    charges.add_argument("merchant_id")

    report = commands.add_parser("report", help="settlement report for a merchant")
    report.add_argument("merchant_id")

    settle_command = commands.add_parser("settle", help="pay out a merchant's settlement")
    settle_command.add_argument("merchant_id")
    settle_command.add_argument("--date", required=True, help="settlement date, YYYY-MM-DD")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _run(args)
    except requests.ConnectionError:
        print(
            f"Could not reach the Larkspur API at {config.base_url()}.\n"
            "Is the mock server running?  python server/mock_api.py",
            file=sys.stderr,
        )
        return 2
    except ApiError as error:
        print(f"Larkspur API error: {error}", file=sys.stderr)
        return 1
    return 0


def _run(args: argparse.Namespace) -> None:
    if args.command == "fee":
        fee = calculate_fee(args.amount, args.currency)
        currency = args.currency.upper()
        print(f"Fee for a {format_money(args.amount)} {currency} charge: {format_money(fee)} {currency}")
        return

    client = LarkspurClient()
    if args.command == "merchant":
        merchant = client.get_merchant(args.merchant_id)
        print(f"{merchant.id}  {merchant.name}  country={merchant.country}  currency={merchant.default_currency}")
    elif args.command == "charges":
        charges = client.list_charges(args.merchant_id)
        for charge in charges:
            print(
                f"{charge.id}  {charge.status:<9}  {charge.currency}  "
                f"{format_money(charge.amount):>10}  {charge.card_country}  {charge.description}"
            )
        print(f"{len(charges)} charge(s)")
    elif args.command == "report":
        print(format_report(build_settlement(client, args.merchant_id)))
    elif args.command == "settle":
        payouts = settle(client, args.merchant_id, args.date)
        for payout in payouts:
            print(
                f"{payout.id}  {payout.currency}  {format_money(payout.amount):>10}  "
                f"{payout.settlement_date}  {payout.status}"
            )
        print(f"{len(payouts)} payout(s)")
