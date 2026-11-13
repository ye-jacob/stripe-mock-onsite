"""A second, deliberately naive implementation of the balance engine.

Build tooling only. It is written in a different style from the reference
solution (integer timestamps, no regular expressions, everything recomputed
from scratch) so that the two can be fuzzed against each other.
"""
from __future__ import annotations

import calendar

DAY = 86400
HOLD_SECONDS = 48 * 3600
FIXED = {"USD": 30, "EUR": 25, "GBP": 20}
DIGITS = "0123456789"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def to_epoch(text):
    """Seconds since 1970 for an exact YYYY-MM-DDTHH:MM:SSZ string, else None."""
    if len(text) != 20:
        return None
    for index, char in enumerate(text):
        if index in (4, 7):
            if char != "-":
                return None
        elif index == 10:
            if char != "T":
                return None
        elif index in (13, 16):
            if char != ":":
                return None
        elif index == 19:
            if char != "Z":
                return None
        elif char not in DIGITS:
            return None
    year, month, day = int(text[0:4]), int(text[5:7]), int(text[8:10])
    hour, minute, second = int(text[11:13]), int(text[14:16]), int(text[17:19])
    if year < 1 or not 1 <= month <= 12:
        return None
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None
    if hour > 23 or minute > 59 or second > 59:
        return None
    return calendar.timegm((year, month, day, hour, minute, second))


def parse(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) == 6:
        if parts[2] != "charge":
            return None
    elif len(parts) == 7:
        if parts[2] != "refund":
            return None
    else:
        return None
    for p in parts:
        if p == "":
            return None
    ts = to_epoch(parts[0])
    if ts is None:
        return None
    for ch in parts[4]:
        if ch not in DIGITS:
            return None
    amount = int(parts[4])
    if amount < 1:
        return None
    if len(parts[5]) != 3:
        return None
    for ch in parts[5]:
        if ch not in UPPER:
            return None
    record = {"ts": ts, "id": parts[1], "type": parts[2], "merchant": parts[3], "amount": amount, "currency": parts[5]}
    if parts[2] == "refund":
        record["charge"] = parts[6]
    return record


def ordered(lines):
    first = {}
    for position, line in enumerate(lines):
        record = parse(line)
        if record is None:
            continue
        if record["id"] not in first:
            record["position"] = position
            first[record["id"]] = record
    return sorted(first.values(), key=lambda r: (r["ts"], r["position"]))


def classify(records):
    """Return (accepted, rejected) where rejected is a list of (record, reason)."""
    accepted, rejected = [], []
    for index, record in enumerate(records):
        if record["type"] == "charge":
            accepted.append(record)
            continue
        target = None
        for earlier in records[:index]:
            if earlier["type"] == "charge" and earlier["id"] == record["charge"]:
                target = earlier
        if target is None:
            rejected.append((record, "charge_not_found"))
            continue
        if target["merchant"] != record["merchant"] or target["currency"] != record["currency"]:
            rejected.append((record, "charge_mismatch"))
            continue
        already = sum(a["amount"] for a in accepted if a["type"] == "refund" and a["charge"] == target["id"])
        if already + record["amount"] > target["amount"]:
            rejected.append((record, "exceeds_charge"))
            continue
        accepted.append(record)
    return accepted, rejected


def fee(amount, currency):
    doubled = amount * 29 * 2  # in two-thousandths
    whole, remainder = divmod(doubled, 2000)
    percentage = whole + (1 if remainder >= 1000 else 0)
    total = percentage + FIXED.get(currency, 0)
    return amount if total > amount else total


def compute_balances(lines):
    accepted, _ = classify(ordered(lines))
    out = {}
    for record in accepted:
        merchant = out.setdefault(record["merchant"], {})
        merchant.setdefault(record["currency"], 0)
        if record["type"] == "charge":
            merchant[record["currency"]] += record["amount"]
        else:
            merchant[record["currency"]] -= record["amount"]
    return out


def rejected_refunds(lines):
    _, rejected = classify(ordered(lines))
    return [(record["id"], reason) for record, reason in rejected]


def _accepted_until(lines, as_of):
    cutoff = to_epoch(as_of)
    assert cutoff is not None
    accepted, _ = classify(ordered(lines))
    return [r for r in accepted if r["ts"] <= cutoff], cutoff


def balance_breakdown(lines, as_of):
    accepted, cutoff = _accepted_until(lines, as_of)
    out = {}
    for record in accepted:
        slot = out.setdefault(record["merchant"], {}).setdefault(record["currency"], {"pending": 0, "available": 0})
        if record["type"] == "refund":
            slot["available"] -= record["amount"]
        else:
            net = record["amount"] - fee(record["amount"], record["currency"])
            if record["ts"] + HOLD_SECONDS <= cutoff:
                slot["available"] += net
            else:
                slot["pending"] += net
    return out


def compute_payouts(lines, as_of):
    accepted, cutoff = _accepted_until(lines, as_of)
    if not accepted:
        return []
    accounts = sorted({(r["merchant"], r["currency"]) for r in accepted})
    paid = {account: 0 for account in accounts}
    payouts = []
    midnight = (min(r["ts"] for r in accepted) // DAY) * DAY
    while midnight <= cutoff:
        for account in accounts:
            available = -paid[account]
            for r in accepted:
                if (r["merchant"], r["currency"]) != account:
                    continue
                if r["type"] == "refund":
                    if r["ts"] <= midnight:
                        available -= r["amount"]
                elif r["ts"] + HOLD_SECONDS <= midnight:
                    available += r["amount"] - fee(r["amount"], r["currency"])
            if available >= 5000:
                year, month, day = _civil(midnight)
                payouts.append(("%04d-%02d-%02d" % (year, month, day), account[0], account[1], available))
                paid[account] += available
        midnight += DAY
    return payouts


def _civil(epoch):
    import time

    parts = time.gmtime(epoch)
    return parts.tm_year, parts.tm_mon, parts.tm_mday
