# Larkspur Payments API reference

Larkspur is a fictional payments provider. A mock of its API ships with this
repository (`server/mock_api.py`) and runs on your machine.

- Base URL: `http://127.0.0.1:8642`
- All responses are JSON.
- All money amounts are integers in the currency's **minor unit**: `1250` in `usd` is $12.50.
- Currency codes are lowercase (`usd`, `eur`, `gbp`). Country codes are uppercase (`US`, `GB`).
- Timestamps (`created`) are Unix timestamps in seconds.

## Authentication

Send the API key as a bearer token on every `/v1` request:

```
Authorization: Bearer lk_test_7f3a9c2e51d84b06
```

A missing or wrong key gets `401`.

## Objects

### Merchant

```json
{
  "id": "acct_tidewater",
  "object": "merchant",
  "name": "Tidewater Surf Co.",
  "country": "US",
  "default_currency": "usd"
}
```

### Charge

```json
{
  "id": "ch_8RkQp2mXv7LwTz",
  "object": "charge",
  "merchant": "acct_tidewater",
  "amount": 4999,
  "currency": "usd",
  "status": "succeeded",
  "card_country": "US",
  "created": 1794318000,
  "description": "Order #1006"
}
```

`status` is one of `succeeded`, `pending`, `failed`. Only `succeeded` charges have moved money.
`card_country` is the country that issued the customer's card.

### Refund

```json
{
  "id": "re_Yb3nH8sKq2WdEf",
  "object": "refund",
  "merchant": "acct_tidewater",
  "charge": "ch_8RkQp2mXv7LwTz",
  "amount": 500,
  "currency": "usd",
  "status": "succeeded",
  "created": 1794330000
}
```

`status` is one of `succeeded`, `pending`, `failed`. Only `succeeded` refunds have moved money.

### Payout

```json
{
  "id": "po_000001",
  "object": "payout",
  "merchant": "acct_tidewater",
  "amount": 34111,
  "currency": "usd",
  "settlement_date": "2026-11-12",
  "status": "pending",
  "created": 1794400000
}
```

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/v1/merchants/{id}` | Retrieve one merchant |
| `GET` | `/v1/charges` | List a merchant's charges, newest first |
| `GET` | `/v1/refunds` | List a merchant's refunds, newest first |
| `GET` | `/v1/payouts` | List a merchant's payouts, newest first |
| `POST` | `/v1/payouts` | Create a payout |

### List endpoints

`GET /v1/charges`, `GET /v1/refunds` and `GET /v1/payouts` take these query parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `merchant` | yes | Merchant id |
| `limit` | no | Page size, 1 to 20. Default 10. |
| `starting_after` | no | An object id. The page starts with the object that follows it in the list. |
| `status` | no | `/v1/charges` only: return only charges with this status |

and return a list object:

```json
{
  "object": "list",
  "url": "/v1/charges",
  "has_more": true,
  "data": [ { "id": "ch_...", "object": "charge", "...": "..." } ]
}
```

#### Pagination

Lists are returned one page at a time. When `has_more` is `true` there are more
objects: request the next page by passing the `id` of the **last object of the
current page** as `starting_after`. Keep going until `has_more` is `false`.

```
GET /v1/charges?merchant=acct_tidewater&limit=3
GET /v1/charges?merchant=acct_tidewater&limit=3&starting_after=ch_...   (id of the 3rd charge)
```

### Create a payout

`POST /v1/payouts` sends money to a merchant. The body must be **form-encoded**
(`Content-Type: application/x-www-form-urlencoded`), not JSON.

| Parameter | Required | Meaning |
| --- | --- | --- |
| `merchant` | yes | Merchant id |
| `amount` | yes | Positive integer, minor units |
| `currency` | yes | `usd`, `eur` or `gbp` |
| `settlement_date` | yes | The day this payout settles, `YYYY-MM-DD` |

Returns the new payout object.

```
curl http://127.0.0.1:8642/v1/payouts \
  -H "Authorization: Bearer lk_test_7f3a9c2e51d84b06" \
  -H "Idempotency-Key: an-example-key" \
  -d merchant=acct_tidewater -d amount=1000 -d currency=usd -d settlement_date=2026-11-12
```

#### Idempotent requests

`POST` requests accept an `Idempotency-Key` header: any string of 1 to 255
characters that you choose.

- The first request with a given key is processed normally and its result is remembered.
- Any later request with the **same key and the same parameters** is *not* processed
  again. It returns the remembered result of the first request, with the response
  header `Idempotent-Replayed: true`.
- The same key with **different parameters** is rejected with `409`.

A request without an `Idempotency-Key` is processed every time it is received.

## Errors

Errors use conventional status codes and a JSON body:

```json
{
  "error": {
    "type": "invalid_request_error",
    "code": "parameter_invalid",
    "message": "Invalid limit: '100'. limit must be an integer between 1 and 20."
  }
}
```

| Status | Meaning | Retry? |
| --- | --- | --- |
| `400` | The request is invalid. The message says why. | No. Fix the request. |
| `401` | Missing or invalid API key. | No. |
| `404` | The object or URL does not exist. | No. |
| `409` | Idempotency key reused with different parameters. | No. |
| `429` | Rate limited. See below. | Yes, after waiting. |
| `503` | Temporary failure. **The request may or may not have been processed.** | See below. |

### Rate limits (429)

The API limits how fast a client may send requests. A rejected request gets
status `429` and a `Retry-After` header holding the number of seconds to wait.
A rate-limited request was **not** processed. Requests sent before the wait is
over are rejected with `429` again.

### Temporary failures (503)

A `503` tells you nothing about whether the request took effect.

- `GET` requests are always safe to retry.
- A `POST` that failed with `503` **may already have created the object**. Retrying
  it is only safe with the same `Idempotency-Key` as the failed attempt.

The payouts endpoint is known to be unreliable in exactly this way.

## About the mock server

The mock is deterministic so that you can reproduce problems:

- It rate-limits **every 4th request** (`Retry-After: 1`).
- The **first attempt** of every new payout creation fails with `503` *after* the
  payout has been created. (Without an `Idempotency-Key`, every other creation
  fails that way.)

Start it with other settings if that helps you:

```
python server/mock_api.py --help
python server/mock_api.py --rate-limit-every 0 --reliable-payouts
```

Two helper endpoints exist only in the mock (no API key needed):

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/_admin/reset` | Forget all payouts, idempotency keys and counters |
| `GET` | `/_admin/state` | Show counters, created payouts and duplicate payouts |

In tests you can run a private mock in-process; see the `mock_api` fixture in
`tests/conftest.py`.
