# settlements — integration exercise

You have just joined the team that owns **settlements**, a small Python tool that
finance uses to work out what each merchant is owed and to pay it out. It talks
to the Larkspur Payments API. Larkspur is a fictional payments provider; a mock
of its API runs on your machine.

Today the tool can look up a merchant and compute the processing fee for a
charge. Your job is to add the three features described below, in order.

Read this page first, then skim [`docs/API.md`](docs/API.md). Everything you
need is in this repository.

## Ground rules

- 60 minutes, in your own editor, sharing your screen. Think out loud.
- You may look things up: official docs, Stack Overflow, a search engine.
- **No AI assistance of any kind.** No chat assistants, no AI code completion in
  your editor, no AI answers in search results.
- Your interviewer is your teammate. Ask whenever something is unclear.
- You are not expected to finish everything. Working, tested code for part of
  the task beats untested code for all of it.

## Setup

You need Python 3.9 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest                     # all tests pass before you change anything
```

In a **second terminal**, start the mock API and leave it running. It prints
every request it receives, which is useful while you work.

```bash
python3 server/mock_api.py           # Windows: python server\mock_api.py
```

Back in the first terminal, check that the tool can reach it:

```bash
python -m settlements merchant acct_tidewater
python -m settlements fee 1000 usd
```

## What is already here

| Path | What it is |
| --- | --- |
| `settlements/client.py` | `LarkspurClient`, the HTTP client for the API. It can fetch a merchant. |
| `settlements/models.py` | Typed objects for API responses: `Merchant`, `Charge`, `Refund`, `Payout`. |
| `settlements/errors.py` | The exceptions the client raises. |
| `settlements/fees.py` | `calculate_fee`: the processing fee for one charge. |
| `settlements/report.py` | `SettlementLine` and a plain-text report formatter. |
| `settlements/settle.py` | Where payouts will be created. |
| `settlements/cli.py` | The command line tool. Try `python -m settlements --help`. |
| `tests/` | The existing tests. `tests/conftest.py` has fixtures that start a private mock API for a test. |
| `docs/API.md` | Reference for the Larkspur API. |
| `server/` | The mock API. You should not need to read or change it. |

Merchants you can use: `acct_tidewater` (small, 6 charges), `acct_nimbus`
(large), `acct_orchard`, `acct_sprout`, `acct_breakeven` and `acct_ghost`.

## The task

### Part 1 — Fetch every charge

Implement `LarkspurClient.list_charges(merchant_id)` in `settlements/client.py`.

- It returns **all** of the merchant's charges as `Charge` objects, in the order
  the API lists them (newest first).
- The API returns lists one page at a time.
- The API rate-limits its clients. A rate-limited request must be retried once
  the wait the API asks for is over. Do not retry forever: after a reasonable
  number of attempts, give up and let the existing `RateLimitError` reach the
  caller.

When this works:

```
$ python -m settlements charges acct_tidewater
ch_Lw4AgKWTB9K3TS  succeeded  usd       49.99  US  Order #1006
ch_CCUQDYZtytEnUk  succeeded  usd      125.00  CA  Order #1005
ch_MyrZXozXmAponE  failed     usd       25.00  US  Order #1004
ch_5YmiyN7w9RViHJ  succeeded  usd        5.00  US  Order #1003
ch_yLR9mhKdE6iEp7  pending    usd       82.50  GB  Order #1002
ch_Nujzf9Dr64YYJB  succeeded  usd      200.00  US  Order #1001
6 charge(s)
```

and `python -m settlements charges acct_nimbus` ends with `57 charge(s)`.

### Part 2 — Settlement report

Implement `build_settlement(client, merchant_id)` in `settlements/report.py`.
It returns one `SettlementLine` for each currency in which the merchant has at
least one succeeded charge, sorted by currency code.

| Field | Value |
| --- | --- |
| `gross` | Sum of the merchant's **succeeded** charges in that currency |
| `fees` | Sum of the processing fees of those charges (see below) |
| `refunds` | Sum of the merchant's **succeeded** refunds in that currency |
| `charge_count` | Number of succeeded charges in that currency |

Charges and refunds that are `pending` or `failed` are ignored. `net` is derived
for you: `gross - fees - refunds`.

**Fees.** `settlements/fees.py` computes our standard processing fee. Finance
has introduced a rule that it does not know about yet:

> **Cross-border surcharge.** When the card was issued in a different country
> from the merchant's country, the fee for that charge goes up by 1.5% of the
> charge amount. The surcharge is rounded half up to a whole minor unit on its
> own, and then added to the standard fee.

`calculate_fee` already has callers: the `fee` command and other teams' scripts.
They must keep working exactly as they do today.

When this works:

```
$ python -m settlements report acct_tidewater
Currency   Gross   Fees  Refunds     Net  Charges
USD       379.99  14.11    20.00  345.88        4
```

### Part 3 — Pay out

Implement `settle(client, merchant_id, settlement_date)` in
`settlements/settle.py`.

- For every currency whose net amount is **greater than zero**, create a payout
  of the net amount with `POST /v1/payouts`. A currency whose net is zero or
  negative gets no payout.
- Return the payouts as `Payout` objects, sorted by currency code.
- **Never pay a merchant twice for the same settlement date.** The payouts
  endpoint is unreliable: a request can fail *after* the payout was created
  (see "Temporary failures" in `docs/API.md`). No duplicate payout may result
  from a retried request, or from running `settle` again for the same merchant
  and date. A second run returns the same payouts as the first.

When this works (payout ids depend on what the mock has created so far):

```
$ python -m settlements settle acct_tidewater --date 2026-11-12
po_000001  usd      345.88  2026-11-12  pending
1 payout(s)
```

Running the same command again prints the same payout, and
`GET /v1/payouts?merchant=acct_tidewater` still lists exactly one.

## What your interviewer is looking at

- Whether you can find your way around code and documentation you did not write.
- How you fit new code into what exists: structure, naming, reuse.
- How you convince yourself, and us, that it works and that nothing else broke.
- How you communicate while you work.
