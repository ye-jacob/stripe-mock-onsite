"""Client for the Larkspur Payments API (see docs/API.md).

REFERENCE SOLUTION. One reasonable way to do it, not the only one.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Iterator

import requests

from settlements import config
from settlements.errors import ApiError, AuthenticationError, NotFoundError, RateLimitError
from settlements.models import Charge, Merchant, Payout, Refund

MAX_ATTEMPTS = 5
PAGE_SIZE = 20  # the largest page the API allows


class LarkspurClient:
    """Talks to the Larkspur API and returns typed objects."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 5.0,
        session: requests.Session | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.api_key()
        self.base_url = (base_url if base_url is not None else config.base_url()).rstrip("/")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self._sleep = sleep
        if session is None:
            session = requests.Session()
            # The API runs on this machine: never send requests through a system proxy.
            session.trust_env = False
        self._session = session

    # -- transport -----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Send a request, retrying when that is safe, and return the decoded JSON body.

        * 429: the request was not processed. Wait for Retry-After, then try again.
        * 5xx: the request may have been processed. Only retry when repeating it
          cannot do harm: a GET, or a POST that carries an idempotency key.

        Gives up after ``max_attempts`` attempts and raises the last error.
        """
        retry_on_server_error = method == "GET" or idempotency_key is not None
        attempt = 1
        while True:
            try:
                return self._send(method, path, params=params, data=data, idempotency_key=idempotency_key)
            except RateLimitError as error:
                if attempt >= self.max_attempts:
                    raise
                self._sleep(error.retry_after)
            except ApiError as error:
                if error.status < 500 or not retry_on_server_error or attempt >= self.max_attempts:
                    raise
                self._sleep(min(0.1 * 2 ** (attempt - 1), 2.0))
            attempt += 1

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """Send exactly one HTTP request."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        response = self._session.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            data=data,  # a dict here is sent form-encoded, which is what the API expects
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise _error_from_response(response)
        return response.json()

    def _list_all(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Yield every object of a list endpoint, following the pagination cursor."""
        query = dict(params, limit=PAGE_SIZE)
        while True:
            page = self._request("GET", path, params=query)
            yield from page["data"]
            if not page["has_more"] or not page["data"]:
                return
            query["starting_after"] = page["data"][-1]["id"]

    # -- endpoints -----------------------------------------------------------

    def get_merchant(self, merchant_id: str) -> Merchant:
        return Merchant.from_api(self._request("GET", f"/v1/merchants/{merchant_id}"))

    def list_charges(self, merchant_id: str) -> list[Charge]:
        """Return every charge of the merchant, in the order the API lists them (newest first)."""
        return [Charge.from_api(item) for item in self._list_all("/v1/charges", {"merchant": merchant_id})]

    def list_refunds(self, merchant_id: str) -> list[Refund]:
        """Return every refund of the merchant, newest first."""
        return [Refund.from_api(item) for item in self._list_all("/v1/refunds", {"merchant": merchant_id})]

    def list_payouts(self, merchant_id: str) -> list[Payout]:
        """Return every payout of the merchant, newest first."""
        return [Payout.from_api(item) for item in self._list_all("/v1/payouts", {"merchant": merchant_id})]

    def create_payout(
        self,
        merchant_id: str,
        amount: int,
        currency: str,
        settlement_date: str,
        *,
        idempotency_key: str,
    ) -> Payout:
        """Create a payout. The idempotency key makes the request safe to retry."""
        data = {
            "merchant": merchant_id,
            "amount": amount,
            "currency": currency,
            "settlement_date": settlement_date,
        }
        return Payout.from_api(self._request("POST", "/v1/payouts", data=data, idempotency_key=idempotency_key))


def _error_from_response(response: requests.Response) -> ApiError:
    try:
        error = response.json()["error"]
        code, message = error["code"], error["message"]
    except (ValueError, KeyError, TypeError):
        code, message = "unknown_error", response.text.strip() or response.reason
    status = response.status_code
    if status == 401:
        return AuthenticationError(status, code, message)
    if status == 404:
        return NotFoundError(status, code, message)
    if status == 429:
        return RateLimitError(status, code, message, retry_after=_retry_after_seconds(response))
    return ApiError(status, code, message)


def _retry_after_seconds(response: requests.Response) -> float:
    try:
        return max(0.0, float(response.headers.get("Retry-After", "")))
    except ValueError:
        return 1.0
