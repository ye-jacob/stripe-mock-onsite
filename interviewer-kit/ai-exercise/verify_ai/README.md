# Verification suite: AI-enabled programming exercise

Run this against a candidate's solution after the session.

1. Copy this whole `verify_ai` folder into the root of the repository, next to
   `balance_engine.py`.
2. From that root, run the files for the parts the candidate completed:

```bash
python -m pytest verify_ai/test_verify_part1.py -v                                    # after Part 1
python -m pytest verify_ai/test_verify_part1.py verify_ai/test_verify_part2.py -v     # after Part 2
python -m pytest verify_ai --ignore=verify_ai/test_verify_part4.py -v                 # after Part 3
python -m pytest verify_ai -v                                                         # after Part 4
```

| File | What it checks |
| --- | --- |
| `test_verify_part1.py` | Balances, 36 kinds of malformed line, duplicate deliveries |
| `test_verify_part2.py` | Timestamp order, ties, the three rejection reasons and their precedence |
| `test_verify_part3.py` | Fee table, half-up rounding, the 48-hour boundary, `as_of`, refunds against available |
| `test_verify_part3_unspecified.py` | The one rule the statement leaves open: a fee larger than the charge. Failing it is a discussion point, not a bug. |
| `test_verify_part4.py` | Daily payouts: minimum, midnight ordering, debts, sorting, `as_of` |

The later parts never change what the earlier functions return, so every file
stays valid however far the candidate got. A file for a part that was not
reached fails on import; leave it out as shown above.
