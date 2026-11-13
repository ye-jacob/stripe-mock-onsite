"""Balance engine: REFERENCE SOLUTION for all four parts.

One reasonable design, not the only one. The shape to notice:

    lines --parse--> events --dedupe, sort--> ordered events --validate--> ledger

Every public function is a small query on top of that one pipeline, so each
new part adds a query instead of another copy of the parsing and ordering rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

CHARGE = "charge"
REFUND = "refund"

CHARGE_NOT_FOUND = "charge_not_found"
CHARGE_MISMATCH = "charge_mismatch"
EXCEEDS_CHARGE = "exceeds_charge"

FEE_PER_MILLE = 29  # 2.9%
FIXED_FEES = {"USD": 30, "EUR": 25, "GBP": 20}  # any other currency: 0
HOLD = timedelta(hours=48)
MINIMUM_PAYOUT = 5000

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_TIMESTAMP_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_WHOLE_NUMBER = re.compile(r"[0-9]+")
_CURRENCY = re.compile(r"[A-Z]{3}")
_FIELD_COUNT = {CHARGE: 6, REFUND: 7}


@dataclass(frozen=True)
class Event:
    timestamp: datetime
    event_id: str
    type: str
    merchant_id: str
    amount: int
    currency: str
    charge_id: Optional[str] = None  # refunds only

    @property
    def account(self) -> tuple[str, str]:
        return (self.merchant_id, self.currency)


@dataclass
class Ledger:
    """The log after de-duplication, ordering and refund validation."""

    accepted: list[Event] = field(default_factory=list)  # in processing order
    rejected: list[tuple[Event, str]] = field(default_factory=list)  # in processing order


# --- parsing -----------------------------------------------------------------------


def parse_timestamp(text: str) -> Optional[datetime]:
    """Parse exactly ``YYYY-MM-DDTHH:MM:SSZ``; None for anything else."""
    if not _TIMESTAMP_SHAPE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:  # right shape, impossible date or time
        return None


def parse_line(line: str) -> Optional[Event]:
    """One well-formed line -> Event; None when the line is malformed."""
    fields = [value.strip() for value in line.split(",")]
    if len(fields) < 3 or fields[2] not in _FIELD_COUNT:
        return None
    if len(fields) != _FIELD_COUNT[fields[2]] or not all(fields):
        return None
    timestamp = parse_timestamp(fields[0])
    if timestamp is None:
        return None
    if not _WHOLE_NUMBER.fullmatch(fields[4]) or int(fields[4]) <= 0:
        return None
    if not _CURRENCY.fullmatch(fields[5]):
        return None
    return Event(
        timestamp=timestamp,
        event_id=fields[1],
        type=fields[2],
        merchant_id=fields[3],
        amount=int(fields[4]),
        currency=fields[5],
        charge_id=fields[6] if fields[2] == REFUND else None,
    )


def load_events(lines: list[str]) -> list[Event]:
    """Well-formed events, first occurrence of each event_id, in processing order."""
    seen: set[str] = set()
    events = []
    for line in lines:
        event = parse_line(line)
        if event is None or event.event_id in seen:
            continue
        seen.add(event.event_id)
        events.append(event)
    events.sort(key=lambda event: event.timestamp)  # stable: ties keep their input order
    return events


# --- refund validation ---------------------------------------------------------------


def build_ledger(events: list[Event]) -> Ledger:
    """Apply the refund rules to events that are already in processing order."""
    ledger = Ledger()
    charges: dict[str, Event] = {}
    refunded: dict[str, int] = {}
    for event in events:
        if event.type == CHARGE:
            charges[event.event_id] = event
            refunded[event.event_id] = 0
            ledger.accepted.append(event)
            continue
        charge = charges.get(event.charge_id)
        if charge is None:
            ledger.rejected.append((event, CHARGE_NOT_FOUND))
        elif charge.account != event.account:
            ledger.rejected.append((event, CHARGE_MISMATCH))
        elif refunded[charge.event_id] + event.amount > charge.amount:
            ledger.rejected.append((event, EXCEEDS_CHARGE))
        else:
            refunded[charge.event_id] += event.amount
            ledger.accepted.append(event)
    return ledger


def _ledger(lines: list[str], as_of: Optional[datetime] = None) -> Ledger:
    events = load_events(lines)
    if as_of is not None:
        events = [event for event in events if event.timestamp <= as_of]
    return build_ledger(events)


def _require_timestamp(text: str) -> datetime:
    timestamp = parse_timestamp(text)
    if timestamp is None:
        raise ValueError("as_of must look like 2026-03-05T08:00:00Z, got %r" % (text,))
    return timestamp


# --- fees ----------------------------------------------------------------------------


def fee_for(amount: int, currency: str) -> int:
    """2.9% rounded half up, plus the fixed fee; never more than the charge itself."""
    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000  # integers only: no float surprises
    return min(amount, percentage + FIXED_FEES.get(currency, 0))


def net_of(charge: Event) -> int:
    return charge.amount - fee_for(charge.amount, charge.currency)


# --- Part 1 and 2 --------------------------------------------------------------------


def compute_balances(lines: list[str]) -> dict[str, dict[str, int]]:
    """Gross balance per merchant and currency: charges minus accepted refunds."""
    balances: dict[str, dict[str, int]] = {}
    for event in _ledger(lines).accepted:
        signed = event.amount if event.type == CHARGE else -event.amount
        per_currency = balances.setdefault(event.merchant_id, {})
        per_currency[event.currency] = per_currency.get(event.currency, 0) + signed
    return balances


def rejected_refunds(lines: list[str]) -> list[tuple[str, str]]:
    """(event_id, reason) for every rejected refund, in processing order."""
    return [(event.event_id, reason) for event, reason in _ledger(lines).rejected]


# --- Part 3 --------------------------------------------------------------------------


def balance_breakdown(lines: list[str], as_of: str) -> dict[str, dict[str, dict[str, int]]]:
    """Pending and available funds per merchant and currency as they stood at ``as_of``."""
    cutoff = _require_timestamp(as_of)
    breakdown: dict[str, dict[str, dict[str, int]]] = {}
    for event in _ledger(lines, cutoff).accepted:
        bucket = breakdown.setdefault(event.merchant_id, {}).setdefault(event.currency, {"pending": 0, "available": 0})
        if event.type == REFUND:
            bucket["available"] -= event.amount
        elif event.timestamp + HOLD <= cutoff:
            bucket["available"] += net_of(event)
        else:
            bucket["pending"] += net_of(event)
    return breakdown


# --- Part 4 --------------------------------------------------------------------------


def _midnight_at_or_after(moment: datetime) -> datetime:
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight if midnight == moment else midnight + timedelta(days=1)


def compute_payouts(lines: list[str], as_of: str) -> list[tuple[str, str, str, int]]:
    """(date, merchant_id, currency, amount) for every payout made at or before ``as_of``."""
    cutoff = _require_timestamp(as_of)

    # Everything that changes an available balance, and when it does so.
    movements: list[tuple[datetime, tuple[str, str], int]] = []
    for event in _ledger(lines, cutoff).accepted:
        if event.type == REFUND:
            movements.append((event.timestamp, event.account, -event.amount))
        elif event.timestamp + HOLD <= cutoff:
            movements.append((event.timestamp + HOLD, event.account, net_of(event)))
    movements.sort(key=lambda movement: movement[0])

    # A balance can only reach the minimum at the first midnight after it changed,
    # so those are the only payout runs worth simulating.
    runs = sorted({_midnight_at_or_after(when) for when, _, _ in movements})

    payouts = []
    available: dict[tuple[str, str], int] = {}
    position = 0
    for run in runs:
        if run > cutoff:
            break
        while position < len(movements) and movements[position][0] <= run:
            _, account, delta = movements[position]
            available[account] = available.get(account, 0) + delta
            position += 1
        for account in sorted(available):
            if available[account] >= MINIMUM_PAYOUT:
                payouts.append((run.strftime("%Y-%m-%d"), account[0], account[1], available[account]))
                available[account] = 0
    return payouts
