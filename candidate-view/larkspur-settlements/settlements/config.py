"""Where the Larkspur API lives and how we authenticate against it."""
from __future__ import annotations

import os

DEFAULT_BASE_URL = "http://127.0.0.1:8642"

# Key for the local mock API. A real key would never be committed.
TEST_API_KEY = "lk_test_7f3a9c2e51d84b06"


def base_url() -> str:
    return os.environ.get("LARKSPUR_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def api_key() -> str:
    return os.environ.get("LARKSPUR_API_KEY", TEST_API_KEY)
