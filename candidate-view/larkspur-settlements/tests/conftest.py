"""Shared test fixtures.

`mock_api` starts a private, in-process mock of the Larkspur API for a test, so
tests never depend on the server you run by hand in a terminal.
"""
import pytest

from server.mock_api import API_KEY, MockApi
from settlements.client import LarkspurClient


@pytest.fixture
def mock_api():
    """Start mock API servers; they are stopped automatically after the test.

    By default the server is well behaved: no rate limiting, reliable payouts.
    Pass options to make it misbehave the way docs/API.md describes:

        server = mock_api(rate_limit_every=2)     # every 2nd request gets a 429
        server = mock_api(flaky_payouts=True)     # payout creation fails with 503

    `retry_after` is the wait (in seconds) announced with a 429; it defaults to 0
    here so that tests stay fast.

    The returned server has `.base_url` and `.state`. `.state` exposes what the
    server has seen, for example `.state.payouts` (the payouts created so far)
    and `.state.stats` (counters such as "requests" and "rate_limited").
    """
    servers = []

    def start(rate_limit_every=0, retry_after=0, flaky_payouts=False):
        server = MockApi(
            rate_limit_every=rate_limit_every,
            retry_after=retry_after,
            flaky_payouts=flaky_payouts,
        ).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.stop()


@pytest.fixture
def api(mock_api):
    """A well-behaved mock API."""
    return mock_api()


@pytest.fixture
def client(api):
    """A client connected to the well-behaved mock API."""
    return LarkspurClient(api_key=API_KEY, base_url=api.base_url)
