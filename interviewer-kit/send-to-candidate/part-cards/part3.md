# Part 3 — Fees and available funds

Merchants do not receive the full amount of a charge, and they do not receive
it straight away.

## Fees

Larkspur keeps a fee from every charge:

- **2.9%** of the charge amount, rounded to the nearest minor unit, with exact
  halves rounded **up**,
- plus a **fixed fee** that depends on the currency:

| Currency | Fixed fee |
| --- | --- |
| `USD` | 30 |
| `EUR` | 25 |
| `GBP` | 20 |
| any other | 0 |

The merchant's **net** from a charge is the amount minus the fee.

Refunds do not give the fee back, and the refund rules of Part 2 still compare
against the full charge amount.

## Pending and available

- The net of a charge is **pending** for 48 hours after the charge's timestamp.
  From exactly 48 hours after the timestamp onwards it is **available**.
- An accepted refund is taken out of the **available** balance of its merchant
  and currency, in full, at the refund's timestamp. It does not matter whether
  the refunded charge is still pending, and available may go negative.

## Implement

```python
def balance_breakdown(lines: list[str], as_of: str) -> dict[str, dict[str, dict[str, int]]]:
```

`as_of` is a timestamp in the same format as the log. The result describes the
moment `as_of`: events with a later timestamp have not happened yet and are
ignored completely, while events at exactly `as_of` have happened.

It returns `{merchant_id: {currency: {"pending": int, "available": int}}}`. A
merchant and currency appear if at least one of their events was accepted at or
before `as_of`.

`compute_balances` and `rejected_refunds` keep their current behaviour (whole
log, no fees). Other teams depend on them.

## Example

```text
2026-03-03T08:00:00Z,evt_201,charge,acct_alpha,10000,USD
2026-03-04T08:00:00Z,evt_202,charge,acct_alpha,4000,USD
2026-03-04T09:00:00Z,evt_203,refund,acct_alpha,2500,USD,evt_201
2026-03-04T10:00:00Z,evt_204,charge,acct_beta,2000,EUR
```

Fees: `evt_201` 290 + 30 = 320, `evt_202` 116 + 30 = 146, `evt_204` 58 + 25 = 83.

```python
balance_breakdown(lines, "2026-03-05T08:00:00Z") == {
    "acct_alpha": {"USD": {"pending": 3854, "available": 7180}},  # 9680 - 2500 available
    "acct_beta": {"EUR": {"pending": 1917, "available": 0}},
}
```

```python
balance_breakdown(lines, "2026-03-04T09:30:00Z") == {
    "acct_alpha": {"USD": {"pending": 13534, "available": -2500}},
}
```
