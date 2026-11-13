#!/usr/bin/env python3
"""Check that the AI-exercise verification suite catches known mistakes (build tooling).

Each mutation is a small, realistic bug applied to the reference solution. The
suite must catch it, and must first catch it in the part where that rule is
introduced (so that a failure points the interviewer at the right part).

    python mutation_check.py <reference-dir-containing-balance_engine.py-and-verify_ai>
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VALID = "valid"  # the mutation is a legitimate alternative and must pass everything

# (name, first part expected to catch it, [(old, new), ...])
MUTATIONS = [
    # ---- Part 1 -------------------------------------------------------------------------
    ("no de-duplication", "part1", [("        if event is None or event.event_id in seen:\n", "        if event is None:\n")]),
    (
        "a malformed line uses up its event_id",
        "part1",
        [
            (
                "        event = parse_line(line)\n        if event is None or event.event_id in seen:\n            continue\n        seen.add(event.event_id)\n",
                "        raw = [value.strip() for value in line.split(\",\")]\n        raw_id = raw[1] if len(raw) > 1 else None\n        if raw_id in seen:\n            continue\n        seen.add(raw_id)\n        event = parse_line(line)\n        if event is None:\n            continue\n",
            )
        ],
    ),
    ("fields are not trimmed", "part1", [('    fields = [value.strip() for value in line.split(",")]\n', '    fields = line.split(",")\n')]),
    (
        "lenient timestamps (fromisoformat)",
        "part1",
        [
            (
                "    if not _TIMESTAMP_SHAPE.fullmatch(text):\n        return None\n    try:\n        return datetime.strptime(text, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)\n",
                '    try:\n        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))\n        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)\n',
            )
        ],
    ),
    (
        "timestamps are not validated at all",
        "part1",
        [
            (
                "    timestamp = parse_timestamp(fields[0])\n    if timestamp is None:\n        return None\n",
                "    timestamp = parse_timestamp(fields[0]) or datetime(2026, 3, 1, tzinfo=timezone.utc)\n",
            )
        ],
    ),
    (
        "zero and negative amounts accepted",
        "part1",
        [
            (
                "    if not _WHOLE_NUMBER.fullmatch(fields[4]) or int(fields[4]) <= 0:\n",
                '    if not fields[4].lstrip("-").isdigit():\n',
            )
        ],
    ),
    (
        "amounts parsed as floats",
        "part1",
        [
            (
                "    if not _WHOLE_NUMBER.fullmatch(fields[4]) or int(fields[4]) <= 0:\n        return None\n",
                "    try:\n        if float(fields[4]) <= 0:\n            return None\n    except ValueError:\n        return None\n    fields[4] = str(int(float(fields[4])))\n",
            )
        ],
    ),
    ("currency only checked for length", "part1", [("    if not _CURRENCY.fullmatch(fields[5]):\n", "    if len(fields[5]) != 3:\n")]),
    ("currency upper-cased before validation", "part1", [("    if not _CURRENCY.fullmatch(fields[5]):\n", "    fields[5] = fields[5].upper()\n    if not _CURRENCY.fullmatch(fields[5]):\n")]),
    (
        "field count not tied to the event type",
        "part1",
        [
            ("    if len(fields) != _FIELD_COUNT[fields[2]] or not all(fields):\n", "    if len(fields) not in (6, 7) or not all(fields[:6]):\n"),
            ("        charge_id=fields[6] if fields[2] == REFUND else None,\n", "        charge_id=fields[6] if len(fields) == 7 else None,\n"),
        ],
    ),
    (
        "zero balances dropped",
        "part1",
        [
            (
                "    return balances\n\n\ndef rejected_refunds",
                "    return {m: {c: v for c, v in per.items() if v} for m, per in balances.items() if any(per.values())}\n\n\ndef rejected_refunds",
            )
        ],
    ),
    (
        "crashes on a blank line",
        "part1",
        [("    if len(fields) < 3 or fields[2] not in _FIELD_COUNT:\n", "    if fields[2] not in _FIELD_COUNT:\n")],
    ),
    # ---- Part 2 -------------------------------------------------------------------------
    (
        "sorted before de-duplicating (earliest timestamp wins)",
        "part2",
        [
            (
                "    seen: set[str] = set()\n    events = []\n    for line in lines:\n        event = parse_line(line)\n        if event is None or event.event_id in seen:\n            continue\n        seen.add(event.event_id)\n        events.append(event)\n    events.sort(key=lambda event: event.timestamp)  # stable: ties keep their input order\n    return events\n",
                "    parsed = [event for event in map(parse_line, lines) if event is not None]\n    parsed.sort(key=lambda event: event.timestamp)\n    seen: set[str] = set()\n    events = []\n    for event in parsed:\n        if event.event_id in seen:\n            continue\n        seen.add(event.event_id)\n        events.append(event)\n    return events\n",
            )
        ],
    ),
    (
        "ties broken by event_id",
        "part2",
        [("    events.sort(key=lambda event: event.timestamp)  # stable", "    events.sort(key=lambda event: (event.timestamp, event.event_id))  # stable")],
    ),
    (
        "ties: charges always before refunds",
        "part2",
        [("    events.sort(key=lambda event: event.timestamp)  # stable", "    events.sort(key=lambda event: (event.timestamp, event.type != CHARGE))  # stable")],
    ),
    ("no sorting: input order", "part2", [("    events.sort(key=lambda event: event.timestamp)  # stable: ties keep their input order\n", "")]),
    (
        "sorted newest first",
        "part1",  # breaks even the Part 1 logs, which contain (valid) refunds
        [("    events.sort(key=lambda event: event.timestamp)  # stable", "    events.sort(key=lambda event: event.timestamp, reverse=True)  # stable")],
    ),
    (
        "a refund can refund a refund",
        "part2",
        [
            (
                "            refunded[charge.event_id] += event.amount\n            ledger.accepted.append(event)\n",
                "            refunded[charge.event_id] += event.amount\n            ledger.accepted.append(event)\n            charges[event.event_id] = event\n            refunded[event.event_id] = 0\n",
            )
        ],
    ),
    ("mismatch ignores the currency", "part2", [("        elif charge.account != event.account:\n", "        elif charge.merchant_id != event.merchant_id:\n")]),
    ("mismatch ignores the merchant", "part2", [("        elif charge.account != event.account:\n", "        elif charge.currency != event.currency:\n")]),
    (
        "exceeds checked before mismatch",
        "part2",
        [
            (
                "        elif charge.account != event.account:\n            ledger.rejected.append((event, CHARGE_MISMATCH))\n        elif refunded[charge.event_id] + event.amount > charge.amount:\n            ledger.rejected.append((event, EXCEEDS_CHARGE))\n",
                "        elif refunded[charge.event_id] + event.amount > charge.amount:\n            ledger.rejected.append((event, EXCEEDS_CHARGE))\n        elif charge.account != event.account:\n            ledger.rejected.append((event, CHARGE_MISMATCH))\n",
            )
        ],
    ),
    (
        "rejected refunds still use up the charge",
        "part2",
        [
            (
                "        elif refunded[charge.event_id] + event.amount > charge.amount:\n            ledger.rejected.append((event, EXCEEDS_CHARGE))\n",
                "        elif refunded[charge.event_id] + event.amount > charge.amount:\n            refunded[charge.event_id] += event.amount\n            ledger.rejected.append((event, EXCEEDS_CHARGE))\n",
            )
        ],
    ),
    ("refunding exactly the full amount is rejected", "part1", [("event.amount > charge.amount:", "event.amount >= charge.amount:")]),
    (
        "each refund checked on its own, not cumulatively",
        "part2",
        [("        elif refunded[charge.event_id] + event.amount > charge.amount:\n", "        elif event.amount > charge.amount:\n")],
    ),
    (
        "one refund budget shared by all charges",
        "part2",
        [
            ("        elif refunded[charge.event_id] + event.amount > charge.amount:\n", "        elif sum(refunded.values()) + event.amount > charge.amount:\n"),
        ],
    ),
    (
        "accounts with only rejected events show up with 0",
        "part2",
        [
            (
                "    return balances\n\n\ndef rejected_refunds",
                "    for event, _ in _ledger(lines).rejected:\n        balances.setdefault(event.merchant_id, {}).setdefault(event.currency, 0)\n    return balances\n\n\ndef rejected_refunds",
            )
        ],
    ),
    (
        "rejected refunds listed in event_id order",
        "part2",
        [
            (
                "    return [(event.event_id, reason) for event, reason in _ledger(lines).rejected]\n",
                "    return sorted((event.event_id, reason) for event, reason in _ledger(lines).rejected)\n",
            )
        ],
    ),
    (
        "rejected refunds still change the balance",
        "part2",
        [
            (
                "    for event in _ledger(lines).accepted:\n        signed = event.amount if event.type == CHARGE else -event.amount\n",
                "    ledger = _ledger(lines)\n    for event in ledger.accepted + [event for event, _ in ledger.rejected]:\n        signed = event.amount if event.type == CHARGE else -event.amount\n",
            )
        ],
    ),
    # ---- Part 3 -------------------------------------------------------------------------
    ("banker's rounding via round()", "part3", [("    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000", "    percentage = round(amount * 0.029)")]),
    # Not idiomatic for money, but numerically right for every amount up to 5e10 (checked), so it must pass.
    ("VALID: float arithmetic with int(x + 0.5)", VALID, [("    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000", "    percentage = int(amount * 0.029 + 0.5)")]),
    ("percentage truncated", "part3", [("    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000", "    percentage = amount * FEE_PER_MILLE // 1000")]),
    ("percentage always rounded up", "part3", [("    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000", "    percentage = -(-amount * FEE_PER_MILLE // 1000)")]),
    ("fee rounded after adding the fixed part, as a float", "part3", [("    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000", "    percentage = round(amount * 0.029 + 0.0)")]),
    ("unknown currencies charged the USD fixed fee", "part3", [("FIXED_FEES.get(currency, 0)", "FIXED_FEES.get(currency, 30)")]),
    ("same fixed fee for every currency", "part3", [('FIXED_FEES = {"USD": 30, "EUR": 25, "GBP": 20}', 'FIXED_FEES = {"USD": 30, "EUR": 30, "GBP": 30}')]),
    ("fee not capped at the charge amount", "part3_unspecified", [("    return min(amount, percentage + FIXED_FEES.get(currency, 0))\n", "    return percentage + FIXED_FEES.get(currency, 0)\n")]),
    (
        "hold boundary exclusive",
        "part3",
        [
            (
                '            bucket["available"] -= event.amount\n        elif event.timestamp + HOLD <= cutoff:\n',
                '            bucket["available"] -= event.amount\n        elif event.timestamp + HOLD < cutoff:\n',
            )
        ],
    ),
    ("hold is 24 hours", "part3", [("HOLD = timedelta(hours=48)", "HOLD = timedelta(hours=24)")]),
    (
        "hold ends at the start of the day two days later",
        "part3",
        [
            (
                '            bucket["available"] -= event.amount\n        elif event.timestamp + HOLD <= cutoff:\n',
                '            bucket["available"] -= event.amount\n        elif (event.timestamp + HOLD).replace(hour=0, minute=0, second=0) <= cutoff:\n',
            )
        ],
    ),
    ("events at exactly as_of ignored", "part3", [("        events = [event for event in events if event.timestamp <= as_of]\n", "        events = [event for event in events if event.timestamp < as_of]\n")]),
    ("events after as_of still counted", "part3", [("        events = [event for event in events if event.timestamp <= as_of]\n", "        pass\n")]),
    ("refunds taken out of pending", "part3", [('            bucket["available"] -= event.amount\n', '            bucket["pending"] -= event.amount\n')]),
    (
        "refund only hits available once its charge is available",
        "part3",
        [
            (
                '        if event.type == REFUND:\n            bucket["available"] -= event.amount\n',
                '        if event.type == REFUND:\n            key = "available" if event.timestamp + HOLD <= cutoff else "pending"\n            bucket[key] -= event.amount\n',
            )
        ],
    ),
    ("refund limited by the net instead of the amount", "part1", [("event.amount > charge.amount:", "event.amount > net_of(charge):")]),
    (
        "compute_balances became net of fees",
        "part1",  # a regression: the Part 1 tests are the ones that notice
        [("        signed = event.amount if event.type == CHARGE else -event.amount\n", "        signed = net_of(event) if event.type == CHARGE else -event.amount\n")],
    ),
    (
        "breakdown returns floats",
        "part3",
        [
            (
                '            bucket["available"] += net_of(event)\n        else:\n            bucket["pending"] += net_of(event)\n    return breakdown\n',
                '            bucket["available"] += float(net_of(event))\n        else:\n            bucket["pending"] += float(net_of(event))\n    return breakdown\n',
            )
        ],
    ),
    (
        "accounts with only rejected events appear in the breakdown",
        "part3",
        [
            (
                "    return breakdown\n",
                "    for event, _ in _ledger(lines, cutoff).rejected:\n        breakdown.setdefault(event.merchant_id, {}).setdefault(event.currency, {\"pending\": 0, \"available\": 0})\n    return breakdown\n",
            )
        ],
    ),
    # ---- Part 4 -------------------------------------------------------------------------
    ("minimum payout exclusive", "part4", [("            if available[account] >= MINIMUM_PAYOUT:\n", "            if available[account] > MINIMUM_PAYOUT:\n")]),
    ("no minimum payout", "part4", [("            if available[account] >= MINIMUM_PAYOUT:\n", "            if available[account] > 0:\n")]),
    (
        "movements at exactly midnight miss that run",
        "part4",
        [("        while position < len(movements) and movements[position][0] <= run:\n", "        while position < len(movements) and movements[position][0] < run:\n")],
    ),
    ("a run at exactly as_of is skipped", "part4", [("        if run > cutoff:\n", "        if run >= cutoff:\n")]),
    ("runs after as_of are simulated too", "part4", [("        if run > cutoff:\n            break\n", "")]),
    (
        "debts are forgiven at each run",
        "part4",
        [
            (
                "            if available[account] >= MINIMUM_PAYOUT:\n",
                "            if available[account] < 0:\n                available[account] = 0\n            if available[account] >= MINIMUM_PAYOUT:\n",
            )
        ],
    ),
    (
        "refunds ignored by payouts",
        "part4",
        [("            movements.append((event.timestamp, event.account, -event.amount))\n", "            pass\n")],
    ),
    (
        "refund applied when the charge is released, not at its own timestamp",
        "part4",
        [("            movements.append((event.timestamp, event.account, -event.amount))\n", "            movements.append((event.timestamp + HOLD, event.account, -event.amount))\n")],
    ),
    ("payout uses gross amounts", "part4", [("            movements.append((event.timestamp + HOLD, event.account, net_of(event)))\n", "            movements.append((event.timestamp + HOLD, event.account, event.amount))\n")]),
    ("no hold before payout", "part4", [("            movements.append((event.timestamp + HOLD, event.account, net_of(event)))\n", "            movements.append((event.timestamp, event.account, net_of(event)))\n")]),
    ("payout dated the day before", "part4", [('run.strftime("%Y-%m-%d")', '(run - timedelta(days=1)).strftime("%Y-%m-%d")')]),
    ("payouts sorted by merchant before date", "part4", [("    return payouts\n", "    return sorted(payouts, key=lambda p: (p[1], p[2], p[0]))\n")]),
    ("payouts not sorted within a day", "part4", [("        for account in sorted(available):\n", "        for account in sorted(available, reverse=True):\n")]),
    (
        "balance is not reset after a payout",
        "part4",
        [("                available[account] = 0\n", "                pass\n")],
    ),
    (
        "balance_breakdown now subtracts payouts",
        "part3",  # a regression: the Part 3 tests are the ones that notice
        [
            (
                "    return payouts\n",
                "    return payouts\n\n\n_breakdown_before_payouts = balance_breakdown\n\n\ndef balance_breakdown(lines, as_of):\n    result = _breakdown_before_payouts(lines, as_of)\n    for _, merchant, currency, amount in compute_payouts(lines, as_of):\n        result[merchant][currency][\"available\"] -= amount\n    return result\n",
            )
        ],
    ),
    # ---- legitimate alternatives: everything must still pass --------------------------------
    (
        "VALID: Decimal with ROUND_HALF_UP",
        VALID,
        [
            (
                "    percentage = (2 * amount * FEE_PER_MILLE + 1000) // 2000",
                '    from decimal import ROUND_HALF_UP, Decimal\n    percentage = int((Decimal(amount) * Decimal("0.029")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))',
            )
        ],
    ),
    (
        "VALID: every midnight simulated one by one",
        VALID,
        [
            (
                "    runs = sorted({_midnight_at_or_after(when) for when, _, _ in movements})\n",
                "    runs = []\n    if movements:\n        run = _midnight_at_or_after(movements[0][0])\n        while run <= cutoff:\n            runs.append(run)\n            run += timedelta(days=1)\n",
            )
        ],
    ),
    (
        "VALID: results returned as lists instead of tuples",
        VALID,
        [
            ("    return [(event.event_id, reason) for event, reason in _ledger(lines).rejected]\n", "    return [[event.event_id, reason] for event, reason in _ledger(lines).rejected]\n"),
            ('                payouts.append((run.strftime("%Y-%m-%d"), account[0], account[1], available[account]))\n', '                payouts.append([run.strftime("%Y-%m-%d"), account[0], account[1], available[account]])\n'),
        ],
    ),
    (
        "VALID: strptime without a separate shape check",
        VALID,
        [("    if not _TIMESTAMP_SHAPE.fullmatch(text):\n        return None\n", "")],
    ),
]

PART_ORDER = ["part1", "part2", "part3", "part3_unspecified", "part4"]


def part_of(test_id: str) -> str:
    match = re.search(r"test_verify_(part\d(?:_unspecified)?)\.py", test_id)
    return match.group(1) if match else "?"


def run_one(reference: Path, mutation) -> tuple[str, bool, str]:
    name, expected_part, replacements = mutation
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(reference, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        target = repo / "balance_engine.py"
        source = target.read_text(encoding="utf-8")
        for old, new in replacements:
            if source.count(old) != 1:
                return name, False, "PATCH DID NOT APPLY (%d matches): %r" % (source.count(old), old[:60])
            source = source.replace(old, new)
        target.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "verify_ai", "-q", "-p", "no:cacheprovider", "-rfE", "--tb=no"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=300,
        )
        failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", proc.stdout, flags=re.M)
        summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-300:]
        if expected_part == VALID:
            return name, proc.returncode == 0, summary + ("" if proc.returncode == 0 else "  failed: %s" % failed[:4])
        parts = sorted({part_of(test) for test in failed}, key=PART_ORDER.index)
        if not failed:
            return name, False, "SURVIVED: no test failed"
        ok = parts[0] == expected_part
        per_part = ", ".join("%s: %d" % (part, sum(part_of(t) == part for t in failed)) for part in parts)
        note = "" if ok else "   <-- expected to be caught first in %s" % expected_part
        return name, ok, "%s%s" % (per_part, note)


def main(argv: list[str]) -> int:
    reference = Path(argv[1]).resolve()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda m: run_one(reference, m), MUTATIONS))
    bad = 0
    for (name, expected_part, _), (_, ok, detail) in zip(MUTATIONS, results):
        print("%s %-18s %-62s %s" % ("ok  " if ok else "GAP ", expected_part, name, detail))
        bad += not ok
    print("\n%d mutations, %d problems" % (len(results), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
