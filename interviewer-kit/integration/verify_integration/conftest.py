"""Fixtures for the integration verification suite.

Copy the whole `verify_integration` folder into the root of the candidate's
repository (next to `settlements/` and `server/`) and run, from that root:

    python -m pytest verify_integration -v

The suite is self-contained: it does not use the fixtures in `tests/`.
"""
import pytest

from server.mock_api import API_KEY, MockApi
from settlements.client import LarkspurClient
from verify_helpers import EXPECTED


@pytest.fixture
def mock_api():
    """Start private mock APIs; they are stopped after the test."""
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
def new_client():
    def make(server):
        return LarkspurClient(api_key=API_KEY, base_url=server.base_url)

    return make


@pytest.fixture
def expected():
    return EXPECTED
