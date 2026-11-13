# Part 1 — Balances

Larkspur is a payments platform. Every payment event is appended to a log, one
event per line. Finance wants to know each merchant's balance.

## The log

Each line is one event: comma-separated fields, no quoting.

```text
timestamp,event_id,type,merchant_id,amount,currency              a charge has 6 fields
timestamp,event_id,type,merchant_id,amount,currency,charge_id    a refund has 7 fields
```

| Field | Rules |
| --- | --- |
| `timestamp` | UTC, exactly `YYYY-MM-DDTHH:MM:SSZ`, and a real date and time |
| `event_id` | not empty; identifies the event |
| `type` | `charge` or `refund` |
| `merchant_id` | not empty |
| `amount` | a whole number of minor units, greater than zero: `1250` means 12.50 |
| `currency` | exactly three uppercase letters A to Z, such as `USD` |
| `charge_id` | refunds only, not empty: the `event_id` of the charge being refunded. You do not need it in this part. |

Spaces around a field are not part of the field: ` 1250 ` is `1250`.

## Rules

1. **Skip malformed lines.** A line is malformed if it breaks any rule above,
   including having the wrong number of fields for its type. The log is noisy:
   expect blank lines, comments and garbage.
2. **Count each event once.** Events are delivered at least once, so the same
   `event_id` can appear on several lines. Only the first well-formed line with
   a given `event_id` counts. Later lines with that `event_id` are ignored, even
   if their other fields differ.
3. A charge adds its amount to the balance of its merchant in its currency.
   A refund subtracts its amount.

## Implement

In `balance_engine.py`:

```python
def compute_balances(lines: list[str]) -> dict[str, dict[str, int]]:
```

It returns `{merchant_id: {currency: balance}}` in minor units. A merchant and
currency appear in the result as soon as one of their events is counted, even
when the balance is zero.

## Example

```text
2026-03-01T09:00:00Z,evt_001,charge,acct_alpha,12000,USD
2026-03-01T09:05:00Z,evt_002,charge,acct_beta,8000,EUR
2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001
2026-03-01T09:30:00Z,evt_003,refund,acct_alpha,2000,USD,evt_001
# nightly export follows
2026-03-01T10:15:00Z,evt_004,charge,acct_alpha,5000,EUR
2026-03-01T11:00:00Z,evt_005,charge,acct_beta,-300,EUR
```

```python
compute_balances(lines) == {
    "acct_alpha": {"USD": 10000, "EUR": 5000},
    "acct_beta": {"EUR": 8000},
}
```

The fourth line repeats `evt_003`. The fifth and the last line are malformed.

---

This is Part 1. Your interviewer gives you the next part when this one is done.
