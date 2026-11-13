# Part 2 — Refund rules

Finance found refunds in the log that should never have been honoured. From now
on a refund only counts if it passes validation.

## Processing order

Events are processed in **timestamp order**, earliest first. The log is **not**
sorted. Events with the same timestamp are processed in the order in which they
appear in the input.

Rule 2 of Part 1 is unchanged: among lines with the same `event_id`, the first
one *in the input* is the one that counts, whatever its timestamp.

## Refund validation

When a refund is processed, apply these checks in order. The first one that
fails gives the reason.

| # | The refund is valid only if | Reason when it fails |
| --- | --- | --- |
| 1 | its `charge_id` is the `event_id` of a charge that has already been processed | `charge_not_found` |
| 2 | its merchant and its currency are the same as that charge's | `charge_mismatch` |
| 3 | the accepted refunds of that charge, this one included, add up to no more than the charge amount | `exceeds_charge` |

A refund that fails is **rejected**. It changes no balance and does not count
towards check 3 for later refunds. Partial refunds are fine: a charge can be
refunded several times, up to its amount.

## Implement

```python
def rejected_refunds(lines: list[str]) -> list[tuple[str, str]]:
```

It returns `(event_id, reason)` for every rejected refund, in the order in which
the refunds were processed.

`compute_balances` must now ignore rejected refunds. A merchant and currency
whose only events were rejected do not appear in its result.

## Example

```text
2026-03-02T12:00:00Z,evt_103,refund,acct_alpha,4000,USD,evt_101
2026-03-02T10:00:00Z,evt_101,charge,acct_alpha,10000,USD
2026-03-02T11:00:00Z,evt_102,refund,acct_alpha,7000,USD,evt_101
2026-03-02T09:00:00Z,evt_104,refund,acct_beta,500,EUR,evt_105
2026-03-02T09:30:00Z,evt_105,charge,acct_beta,2500,EUR
2026-03-02T13:00:00Z,evt_106,refund,acct_gamma,1000,USD,evt_101
2026-03-02T14:00:00Z,evt_107,refund,acct_alpha,3000,USD,evt_101
```

```python
rejected_refunds(lines) == [
    ("evt_104", "charge_not_found"),  # 09:00, before its charge at 09:30
    ("evt_103", "exceeds_charge"),    # 7000 already refunded, 4000 more is too much
    ("evt_106", "charge_mismatch"),   # another merchant's charge
]
```

```python
compute_balances(lines) == {
    "acct_alpha": {"USD": 0},      # 10000 - 7000 - 3000
    "acct_beta": {"EUR": 2500},
}
```
