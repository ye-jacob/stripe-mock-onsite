"""Client for the Larkspur Payments API (see docs/API.md)."""
from __future__ import annotations

from typing import Any

import requests

from settlements import config
from settlements.errors import ApiError, AuthenticationError, NotFoundError, RateLimitError
from settlements.models import Charge, Merchant


class LarkspurClient:
    """Talks to the Larkspur API and returns typed objects."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 5.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.api_key()
        self.base_url = (base_url if base_url is not None else config.base_url()).rstrip("/")
        self.timeout = timeout
        if session is None:
            session = requests.Session()
            # The API runs on this machine: never send requests through a system proxy.
            session.trust_env = False
        self._session = session

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one request and return the decoded JSON body.

        Raises a subclass of ApiError when the API answers with an error status.
        """
        response = self._session.request(
            method,
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise _error_from_response(response)
        return response.json()

    def get_merchant(self, merchant_id: str) -> Merchant:
        return Merchant.from_api(self._request("GET", f"/v1/merchants/{merchant_id}"))

    def list_charges(self, merchant_id: str) -> list[Charge]:
        """Return every charge of the merchant, in the order the API lists them (Part 1)."""
        raise NotImplementedError("Part 1: list_charges is not implemented yet")


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
