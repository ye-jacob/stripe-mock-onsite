#!/usr/bin/env python3
"""Differential fuzzing: reference solution vs the naive oracle (build tooling).

    python fuzz.py <path-to-module-dir-with-balance_engine.py> [rounds]
"""
from __future__ import annotations

import importlib
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle  # noqa: E402

MERCHANTS = ["acct_alpha", "acct_beta", "acct_gamma"]
CURRENCIES = ["USD", "USD", "USD", "EUR", "GBP", "JPY"]
AMOUNTS = [1, 10, 20, 29, 30, 31, 34, 500, 1500, 2500, 4999, 5000, 5150, 5179, 5180, 5200, 10000, 20000, 99999]
BASE = 1772323200  # 2026-03-01T00:00:00Z
assert time.gmtime(BASE)[:6] == (2026, 3, 1, 0, 0, 0)


def stamp(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def interesting_time(rng: random.Random) -> int:
    half_days = rng.randrange(0, 14)
    jitter = rng.choice([0, 0, 0, 1, -1, 3600, 7200, 43199])
    return BASE + half_days * 43200 + jitter


GARBAGE = [
    "",
    "   ",
    "# comment",
    "timestamp,event_id,type,merchant_id,amount,currency",
    "not,a,valid,line",
    "2026-03-01T09:00:00Z,evt_x,payout,acct_alpha,100,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,100,USD,extra",
    "2026-03-01T09:00:00Z,evt_x,refund,acct_alpha,100,USD",
    "2026-03-01T09:00:00Z,evt_x,refund,acct_alpha,100,USD,",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,0,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,-5,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,12.50,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,abc,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,,USD",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,100,usd",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,100,US",
    "2026-03-01T09:00:00Z,evt_x,charge,acct_alpha,100,USDT",
    "2026-03-01T09:00:00Z,evt_x,charge,,100,USD",
    "2026-03-01T09:00:00Z,,charge,acct_alpha,100,USD",
    "2026-03-01 09:00:00,evt_x,charge,acct_alpha,100,USD",
    "2026-03-01T09:00:00,evt_x,charge,acct_alpha,100,USD",
    "2026-02-30T09:00:00Z,evt_x,charge,acct_alpha,100,USD",
    "2026-03-01T24:00:00Z,evt_x,charge,acct_alpha,100,USD",
    "03/01/2026,evt_x,charge,acct_alpha,100,USD",
    "yesterday,evt_x,charge,acct_alpha,100,USD",
]


def make_log(rng: random.Random) -> list[str]:
    lines = []
    ids = []
    size = rng.randrange(0, 40)
    pool = max(3, size // 2 + rng.randrange(0, size + 1))
    for _ in range(size):
        roll = rng.random()
        if roll < 0.12:
            line = rng.choice(GARBAGE)
            if "evt_x" in line and ids and rng.random() < 0.5:
                line = line.replace("evt_x", rng.choice(ids))  # malformed line that reuses a real id
            lines.append(line)
            continue
        if roll < 0.2 and lines:
            lines.append(rng.choice(lines))  # exact duplicate line
            continue
        event_id = "evt_%03d" % rng.randrange(pool)
        ids.append(event_id)
        merchant = rng.choice(MERCHANTS)
        currency = rng.choice(CURRENCIES)
        amount = rng.choice(AMOUNTS) if rng.random() < 0.8 else rng.randrange(1, 30000)
        when = stamp(interesting_time(rng))
        if rng.random() < 0.55 or not ids:
            fields = [when, event_id, "charge", merchant, str(amount), currency]
        else:
            target = rng.choice(ids) if rng.random() < 0.9 else "evt_missing"
            fields = [when, event_id, "refund", merchant, str(amount), currency, target]
        if rng.random() < 0.1:
            fields = [" " + f + "  " for f in fields]
        lines.append(",".join(fields))
    if rng.random() < 0.5:
        rng.shuffle(lines)
    return lines


def main(argv: list[str]) -> int:
    sys.path.insert(0, argv[1])
    engine = importlib.import_module("balance_engine")
    rounds = int(argv[2]) if len(argv) > 2 else 3000
    rng = random.Random(8675309)
    checked = 0
    payouts_seen = 0
    rejected_seen = {"charge_not_found": 0, "charge_mismatch": 0, "exceeds_charge": 0}
    for round_number in range(rounds):
        lines = make_log(rng)
        for name, args in [("compute_balances", ()), ("rejected_refunds", ())] + [
            (name, (stamp(interesting_time(rng) + rng.choice([0, 0, 86400 * 3, 86400 * 9])),))
            for name in ("balance_breakdown", "compute_payouts")
            for _ in range(3)
        ]:
            want = getattr(oracle, name)(lines, *args)
            got = getattr(engine, name)(list(lines), *args)
            checked += 1
            if name == "compute_payouts":
                payouts_seen += len(want)
            if name == "rejected_refunds":
                for _, reason in want:
                    rejected_seen[reason] += 1
            if got != want:
                print("MISMATCH in round %d: %s%r" % (round_number, name, args))
                print("lines = [")
                for line in lines:
                    print("    %r," % line)
                print("]")
                print("oracle:", want)
                print("engine:", got)
                return 1
    print("ok: %d comparisons, %d payouts, rejections %s" % (checked, payouts_seen, rejected_seen))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
