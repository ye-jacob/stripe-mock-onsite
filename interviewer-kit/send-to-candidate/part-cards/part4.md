# Part 4 — Payouts

Every day at **00:00:00 UTC** Larkspur pays merchants their available funds.

## The payout run

At each midnight, for each merchant and currency:

- if the available balance is **at least 5000** minor units, the whole available
  balance is paid out and available becomes 0;
- otherwise nothing is paid, and the balance is carried over to the next day.
  That includes a negative balance.

What happens at the stroke of midnight, in order:

1. events timestamped exactly at midnight are processed,
2. funds whose 48 hours end exactly at midnight become available,
3. the payout run takes place.

Paying out does not rewrite history. A refund can arrive after the funds of its
charge were paid out. It still comes out of available, which can then go
negative; later funds cover that debt before anything is paid out again.

## Implement

```python
def compute_payouts(lines: list[str], as_of: str) -> list[tuple[str, str, str, int]]:
```

It returns every payout made at or before `as_of` as
`(date, merchant_id, currency, amount)`, where `date` is the day of the payout
run written as `YYYY-MM-DD`. A run at exactly `as_of` is included. Sort the
result by date, then merchant_id, then currency.

As in Part 3, events after `as_of` have not happened yet.

The three earlier functions keep their current behaviour. In particular,
`balance_breakdown` does **not** subtract payouts.

## Example

```text
2026-03-03T08:00:00Z,evt_201,charge,acct_alpha,10000,USD
2026-03-04T08:00:00Z,evt_202,charge,acct_alpha,4000,USD
2026-03-04T09:00:00Z,evt_203,refund,acct_alpha,2500,USD,evt_201
2026-03-04T10:00:00Z,evt_204,charge,acct_beta,2000,EUR
2026-03-06T15:00:00Z,evt_205,refund,acct_alpha,5000,USD,evt_201
2026-03-06T16:00:00Z,evt_206,charge,acct_alpha,9000,USD
```

```python
compute_payouts(lines, "2026-03-09T00:00:00Z") == [
    ("2026-03-06", "acct_alpha", "USD", 7180),  # 9680 available since 03-05 08:00, minus the 2500 refund
    ("2026-03-09", "acct_alpha", "USD", 7563),  # 3854 - 5000 + 8709
]
```

```python
compute_payouts(lines, "2026-03-08T23:59:59Z") == [
    ("2026-03-06", "acct_alpha", "USD", 7180),
]
```

`acct_beta` never reaches 5000, so it is never paid.
