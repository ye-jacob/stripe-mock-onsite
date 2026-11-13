"""Errors raised by the Larkspur API client."""
from __future__ import annotations


class ApiError(Exception):
    """The API answered with an error status (4xx or 5xx)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


class AuthenticationError(ApiError):
    """401: the API key is missing or wrong."""


class NotFoundError(ApiError):
    """404: the requested object does not exist."""


class RateLimitError(ApiError):
    """429: we are sending requests too quickly.

    ``retry_after`` is the number of seconds the API asked us to wait.
    """

    def __init__(self, status: int, code: str, message: str, retry_after: float) -> None:
        super().__init__(status, code, message)
        self.retry_after = retry_after
