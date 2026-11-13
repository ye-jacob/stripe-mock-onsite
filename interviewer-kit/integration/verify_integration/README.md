# Verification suite: Integration

Run this against a candidate's repository after the session.

1. Copy this whole `verify_integration` folder into the root of the repository,
   next to `settlements/` and `server/`.
2. From that root, with the virtual environment active:

```bash
python -m pytest verify_integration -v
```

| File | What it checks |
| --- | --- |
| `test_verify_part1_charges.py` | Part 1: every page is fetched, in order; 429s are retried after `Retry-After`; retries are bounded |
| `test_verify_part2_settlement.py` | Part 2: gross, fees, refunds, net and counts per currency for every merchant |
| `test_verify_part3_payouts.py` | Part 3: one payout per positive net, no duplicates through retries or reruns |
| `test_verify_nothing_broke.py` | The behaviour that existed before the exercise is unchanged |

To check only the parts the candidate reached, name the files, for example:

```bash
python -m pytest verify_integration/test_verify_part1_charges.py verify_integration/test_verify_nothing_broke.py -v
```

The suite starts its own in-process mock API, so the server in the terminal does
not need to be running. A full run takes about 5 seconds on a correct solution.
When a number is wrong, the failure message says which well-known mistake
produces that exact number.
