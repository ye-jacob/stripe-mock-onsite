#!/usr/bin/env python3
"""Mock server for the (fictional) Larkspur Payments API.

Standard library only. Start it from the repository root with:

    python server/mock_api.py              # serves http://127.0.0.1:8642
    python server/mock_api.py --help       # all options

How the API behaves is described in docs/API.md. You should not need to read
or change this file to complete the exercise.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

API_KEY = "lk_test_7f3a9c2e51d84b06"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8642
DEFAULT_LIMIT = 10
MAX_LIMIT = 20
SUPPORTED_CURRENCIES = ("eur", "gbp", "usd")
PAYOUT_PARAMS = ("merchant", "amount", "currency", "settlement_date")
FIXTURES_PATH = Path(__file__).resolve().with_name("fixtures.json")

# Tolerance for clocks with coarse resolution: a client that waited for the
# full Retry-After must never be told it came back too early.
_COOLDOWN_GRACE = 0.05


class ApiProblem(Exception):
    """Raised to produce an error response."""

    def __init__(self, status, error_type, code, message, headers=None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.code = code
        self.message = message
        self.headers = dict(headers or {})

    def body(self):
        return {"error": {"type": self.error_type, "code": self.code, "message": self.message}}


def _invalid(code, message, status=400):
    return ApiProblem(status, "invalid_request_error", code, message)


class MockState:
    """Everything the mock API knows. One instance per running server."""

    def __init__(self, *, rate_limit_every=4, retry_after=1.0, flaky_payouts=True, fixtures=None):
        if rate_limit_every < 0:
            raise ValueError("rate_limit_every must be 0 (off) or a positive number")
        if retry_after < 0:
            raise ValueError("retry_after must not be negative")
        self.rate_limit_every = int(rate_limit_every)
        self.retry_after = float(retry_after)
        self.flaky_payouts = bool(flaky_payouts)
        if fixtures is None:
            fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        self.merchants = {merchant["id"]: merchant for merchant in fixtures["merchants"]}
        self.charges = list(fixtures["charges"])  # newest first
        self.refunds = list(fixtures["refunds"])  # newest first
        self.lock = threading.RLock()
        self.reset()

    # -- lifecycle -----------------------------------------------------------

    def reset(self):
        with self.lock:
            self.payouts = []  # oldest first
            self.idempotency = {}  # key -> (fingerprint, payout)
            self.limited_counter = 0
            self.cooldown_until = 0.0
            self.keyless_payouts = 0
            self.request_seq = 0
            self.stats = {
                "requests": 0,
                "rate_limited": 0,
                "early_retries": 0,
                "payout_requests": 0,
                "payouts_created": 0,
                "payout_503s": 0,
                "idempotent_replays": 0,
            }
            self.log = []

    def next_request_id(self):
        with self.lock:
            self.request_seq += 1
            return "req_%05d" % self.request_seq

    def record(self, method, target, status):
        with self.lock:
            self.stats["requests"] += 1
            self.log.append({"method": method, "target": target, "status": status})
            del self.log[:-500]

    # -- cross-cutting checks -----------------------------------------------

    def authenticate(self, header):
        if not header:
            raise ApiProblem(
                401,
                "authentication_error",
                "api_key_missing",
                "No API key provided. Send it as 'Authorization: Bearer <key>'.",
            )
        scheme, _, token = header.partition(" ")
        if scheme != "Bearer" or token.strip() != API_KEY:
            raise ApiProblem(401, "authentication_error", "api_key_invalid", "Invalid API key provided.")

    def rate_limit(self):
        if not self.rate_limit_every:
            return
        with self.lock:
            now = time.monotonic()
            remaining = self.cooldown_until - now
            if remaining > _COOLDOWN_GRACE:
                self.stats["early_retries"] += 1
                raise self._too_many_requests(remaining)
            self.limited_counter += 1
            if self.limited_counter % self.rate_limit_every == 0:
                self.cooldown_until = now + self.retry_after
                self.stats["rate_limited"] += 1
                raise self._too_many_requests(self.retry_after)

    @staticmethod
    def _too_many_requests(seconds):
        wait = max(0, math.ceil(seconds))
        return ApiProblem(
            429,
            "rate_limit_error",
            "rate_limited",
            "Too many requests. Wait %d second(s) before sending another request." % wait,
            headers={"Retry-After": str(wait)},
        )

    # -- reads ---------------------------------------------------------------

    def get_merchant(self, merchant_id):
        merchant = self.merchants.get(merchant_id)
        if merchant is None:
            raise _invalid("resource_missing", "No such merchant: '%s'." % merchant_id, status=404)
        return merchant

    def _require_merchant_param(self, query):
        merchant_id = query.get("merchant")
        if not merchant_id:
            raise _invalid("parameter_missing", "Missing required parameter: merchant.")
        if merchant_id not in self.merchants:
            raise _invalid("resource_missing", "No such merchant: '%s'." % merchant_id)
        return merchant_id

    @staticmethod
    def _check_params(query, allowed):
        unknown = sorted(set(query) - set(allowed))
        if unknown:
            raise _invalid("parameter_unknown", "Received unknown parameter: %s." % unknown[0])

    @staticmethod
    def _page(items, query, url):
        raw_limit = query.get("limit")
        if raw_limit is None:
            limit = DEFAULT_LIMIT
        else:
            if not re.fullmatch(r"\d+", raw_limit) or not 1 <= int(raw_limit) <= MAX_LIMIT:
                raise _invalid(
                    "parameter_invalid",
                    "Invalid limit: '%s'. limit must be an integer between 1 and %d." % (raw_limit, MAX_LIMIT),
                )
            limit = int(raw_limit)
        start = 0
        cursor = query.get("starting_after")
        if cursor is not None:
            position = next((index for index, item in enumerate(items) if item["id"] == cursor), None)
            if position is None:
                raise _invalid("resource_missing", "No such object in this list: '%s'." % cursor)
            start = position + 1
        page = items[start : start + limit]
        return {"object": "list", "url": url, "has_more": start + limit < len(items), "data": page}

    def list_charges(self, query):
        self._check_params(query, ("merchant", "limit", "starting_after", "status"))
        merchant_id = self._require_merchant_param(query)
        status = query.get("status")
        if status is not None and status not in ("succeeded", "pending", "failed"):
            raise _invalid("parameter_invalid", "Invalid status: '%s'." % status)
        items = [
            charge
            for charge in self.charges
            if charge["merchant"] == merchant_id and (status is None or charge["status"] == status)
        ]
        return self._page(items, query, "/v1/charges")

    def list_refunds(self, query):
        self._check_params(query, ("merchant", "limit", "starting_after"))
        merchant_id = self._require_merchant_param(query)
        items = [refund for refund in self.refunds if refund["merchant"] == merchant_id]
        return self._page(items, query, "/v1/refunds")

    def list_payouts(self, query):
        self._check_params(query, ("merchant", "limit", "starting_after"))
        merchant_id = self._require_merchant_param(query)
        with self.lock:
            items = [payout for payout in reversed(self.payouts) if payout["merchant"] == merchant_id]
        return self._page(items, query, "/v1/payouts")

    # -- payouts -------------------------------------------------------------

    def create_payout(self, content_type, raw_body, idempotency_key):
        media_type = (content_type or "").split(";")[0].strip().lower()
        if media_type != "application/x-www-form-urlencoded":
            raise _invalid(
                "invalid_content_type",
                "Request bodies must be form-encoded "
                "(Content-Type: application/x-www-form-urlencoded). JSON bodies are not accepted.",
            )
        try:
            text = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            raise _invalid("invalid_body", "The request body is not valid UTF-8.")
        params = {key: values[-1] for key, values in parse_qs(text, keep_blank_values=True).items()}
        self._check_params(params, PAYOUT_PARAMS)
        for name in PAYOUT_PARAMS:
            if not params.get(name):
                raise _invalid("parameter_missing", "Missing required parameter: %s." % name)
        if params["merchant"] not in self.merchants:
            raise _invalid("resource_missing", "No such merchant: '%s'." % params["merchant"])
        if not re.fullmatch(r"[1-9][0-9]*", params["amount"]):
            raise _invalid(
                "parameter_invalid",
                "Invalid amount: '%s'. amount must be a positive integer in minor units." % params["amount"],
            )
        if params["currency"] not in SUPPORTED_CURRENCIES:
            raise _invalid(
                "parameter_invalid",
                "Invalid currency: '%s'. Supported currencies: %s."
                % (params["currency"], ", ".join(SUPPORTED_CURRENCIES)),
            )
        if not _is_iso_date(params["settlement_date"]):
            raise _invalid(
                "parameter_invalid",
                "Invalid settlement_date: '%s'. Use the format YYYY-MM-DD." % params["settlement_date"],
            )
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 255:
            raise _invalid("parameter_invalid", "Idempotency-Key must be between 1 and 255 characters long.")

        fingerprint = tuple(params[name] for name in PAYOUT_PARAMS)
        with self.lock:
            self.stats["payout_requests"] += 1
            if idempotency_key is not None and idempotency_key in self.idempotency:
                original_fingerprint, payout = self.idempotency[idempotency_key]
                if original_fingerprint != fingerprint:
                    raise ApiProblem(
                        409,
                        "idempotency_error",
                        "idempotency_key_reuse",
                        "This Idempotency-Key was already used for a request with different parameters.",
                    )
                self.stats["idempotent_replays"] += 1
                return 200, payout, {"Idempotent-Replayed": "true"}

            payout = {
                "id": "po_%06d" % (len(self.payouts) + 1),
                "object": "payout",
                "merchant": params["merchant"],
                "amount": int(params["amount"]),
                "currency": params["currency"],
                "settlement_date": params["settlement_date"],
                "status": "pending",
                "created": int(time.time()),
            }
            self.payouts.append(payout)
            self.stats["payouts_created"] += 1

            fail = False
            if idempotency_key is not None:
                self.idempotency[idempotency_key] = (fingerprint, payout)
                fail = self.flaky_payouts  # first time this key is seen
            elif self.flaky_payouts:
                self.keyless_payouts += 1
                fail = self.keyless_payouts % 2 == 1
            if fail:
                self.stats["payout_503s"] += 1
                raise ApiProblem(
                    503,
                    "api_error",
                    "service_unavailable",
                    "The service is temporarily unavailable. Your request may or may not have been processed.",
                )
            return 200, payout, {}

    # -- helpers for people ---------------------------------------------------

    def duplicates(self):
        """Groups of payouts that pay the same merchant/currency/date more than once."""
        with self.lock:
            groups = {}
            for payout in self.payouts:
                key = (payout["merchant"], payout["currency"], payout["settlement_date"])
                groups.setdefault(key, []).append(payout["id"])
        return [
            {"merchant": key[0], "currency": key[1], "settlement_date": key[2], "payouts": ids}
            for key, ids in sorted(groups.items())
            if len(ids) > 1
        ]

    def snapshot(self):
        with self.lock:
            return {
                "settings": {
                    "rate_limit_every": self.rate_limit_every,
                    "retry_after": self.retry_after,
                    "flaky_payouts": self.flaky_payouts,
                },
                "stats": dict(self.stats),
                "payouts": list(self.payouts),
                "duplicate_payouts": self.duplicates(),
                "recent_requests": list(self.log[-25:]),
            }


def _is_iso_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


class _Handler(BaseHTTPRequestHandler):
    server_version = "LarkspurMock/1.0"

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def _handle(self):
        state = self.server.state
        split = urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        query = {key: values[-1] for key, values in parse_qs(split.query, keep_blank_values=True).items()}
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw_body = self.rfile.read(length) if length > 0 else b""
        try:
            status, body, headers = self._route(state, self.command, path, query, raw_body)
        except ApiProblem as problem:
            status, body, headers = problem.status, problem.body(), problem.headers
        except Exception as exc:  # a bug in the mock itself: surface it clearly
            status, headers = 500, {}
            body = {"error": {"type": "api_error", "code": "mock_server_bug", "message": repr(exc)}}
        if not path.startswith("/_admin/") and path != "/healthz":
            state.record(self.command, self.path, status)
        self._send(status, body, headers)

    def _route(self, state, method, path, query, raw_body):
        if path == "/healthz":
            return 200, {"status": "ok"}, {}
        if path == "/_admin/reset" and method == "POST":
            state.reset()
            return 200, {"reset": True}, {}
        if path == "/_admin/state" and method == "GET":
            return 200, state.snapshot(), {}
        if not path.startswith("/v1/"):
            raise _invalid("unknown_route", "Unrecognized request URL (%s %s)." % (method, path), status=404)

        state.authenticate(self.headers.get("Authorization"))
        state.rate_limit()

        routes = {
            "/v1/charges": {"GET": lambda: (200, state.list_charges(query), {})},
            "/v1/refunds": {"GET": lambda: (200, state.list_refunds(query), {})},
            "/v1/payouts": {
                "GET": lambda: (200, state.list_payouts(query), {}),
                "POST": lambda: state.create_payout(
                    self.headers.get("Content-Type"), raw_body, self.headers.get("Idempotency-Key")
                ),
            },
        }
        merchant_match = re.fullmatch(r"/v1/merchants/([^/]+)", path)
        if merchant_match:
            if method != "GET":
                raise _invalid("method_not_allowed", "%s is not supported on %s." % (method, path), status=405)
            return 200, state.get_merchant(merchant_match.group(1)), {}
        if path not in routes:
            raise _invalid("unknown_route", "Unrecognized request URL (%s %s)." % (method, path), status=404)
        if method not in routes[path]:
            raise _invalid("method_not_allowed", "%s is not supported on %s." % (method, path), status=405)
        return routes[path][method]()

    def _send(self, status, body, headers):
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Request-Id", self.server.state.next_request_id())
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A002 - signature fixed by the base class
        if self.server.quiet:
            return
        sys.stderr.write("%s  %s\n" % (time.strftime("%H:%M:%S"), format % args))


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR would let two servers share one port silently.
    allow_reuse_address = sys.platform != "win32"


class MockApi:
    """A mock Larkspur API you can start and stop from Python (handy in tests).

        server = MockApi(rate_limit_every=0).start()
        ...  # talk to server.base_url
        server.stop()

    Options:
        port              0 picks a free port (default).
        rate_limit_every  reject every Nth request with 429; 0 turns rate limiting off.
        retry_after       seconds a rate-limited client has to wait.
        flaky_payouts     when True, payout creation fails the way docs/API.md describes.
    """

    def __init__(self, port=0, host=DEFAULT_HOST, quiet=True, **options):
        self.state = MockState(**options)
        self._httpd = _Server((host, port), _Handler)
        self._httpd.state = self.state
        self._httpd.quiet = quiet
        self._thread = None

    @property
    def base_url(self):
        host, port = self._httpd.server_address[:2]
        return "http://%s:%d" % (host, port)

    def start(self):
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.05},  # makes stop() quick, which keeps tests fast
            name="mock-api",
            daemon=True,
        )
        self._thread.start()
        return self

    def serve_forever(self):
        self._httpd.serve_forever()

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mock server for the fictional Larkspur Payments API.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="port to listen on (default %(default)s)")
    parser.add_argument(
        "--rate-limit-every",
        type=int,
        default=4,
        metavar="N",
        help="reject every Nth request with 429; 0 disables rate limiting (default %(default)s)",
    )
    parser.add_argument(
        "--retry-after",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="how long a rate-limited client must wait (default %(default)s)",
    )
    parser.add_argument("--reliable-payouts", action="store_true", help="never fail payout creation with 503")
    parser.add_argument("--quiet", action="store_true", help="do not log requests")
    args = parser.parse_args(argv)

    try:
        server = MockApi(
            port=args.port,
            quiet=args.quiet,
            rate_limit_every=args.rate_limit_every,
            retry_after=args.retry_after,
            flaky_payouts=not args.reliable_payouts,
        )
    except OSError as exc:
        print("Could not start the mock API on port %d: %s" % (args.port, exc), file=sys.stderr)
        print("Is it already running? Try another port with --port.", file=sys.stderr)
        return 1

    print("Larkspur mock API listening on %s" % server.base_url)
    print("API key: %s" % API_KEY)
    print("Reset state: POST %s/_admin/reset   Inspect state: GET %s/_admin/state" % (server.base_url, server.base_url))
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
