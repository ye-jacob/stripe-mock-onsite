#!/usr/bin/env python3
"""Check that the verification suite catches the mistakes it is meant to catch.

Build tooling (not shipped to the candidate). For each known mistake it copies
the reference solution, applies the mistake, runs the verification suite and
reports which tests failed. A mutation that survives means the suite has a gap.

    python mutation_check.py <reference-repo-with-verify_integration>
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLIENT = "settlements/client.py"
REPORT = "settlements/report.py"
FEES = "settlements/fees.py"
SETTLE = "settlements/settle.py"

# name, file, old, new, must_fail (substrings of test ids), must_pass (True = mutation is a valid alternative)
MUTATIONS = [
    (
        "first page only (20 per page)",
        CLIENT,
        '            if not page["has_more"] or not page["data"]:\n                return\n',
        "            return\n",
        ["test_returns_every_charge_in_api_order[acct_nimbus]"],
    ),
    (
        "no retry on 429",
        CLIENT,
        "                if attempt >= self.max_attempts:\n                    raise\n                self._sleep(error.retry_after)\n",
        "                raise\n",
        ["test_keeps_going_when_some_requests_are_rate_limited"],
    ),
    (
        "retry on 429 without waiting",
        CLIENT,
        "                self._sleep(error.retry_after)\n",
        "                pass\n",
        ["test_waits_as_long_as_retry_after_says_before_retrying"],
    ),
    (
        "retry on 429 after a fixed 1 second",
        CLIENT,
        "                self._sleep(error.retry_after)\n",
        "                self._sleep(1)\n",
        ["test_waits_as_long_as_retry_after_says_before_retrying"],
    ),
    (
        "unbounded retry on 429",
        CLIENT,
        "                if attempt >= self.max_attempts:\n                    raise\n                self._sleep(error.retry_after)\n",
        "                self._sleep(error.retry_after)\n",
        [
            "test_gives_up_with_rate_limit_error_when_the_api_never_recovers",
            "test_rate_limit_error_reaches_the_caller_when_the_api_keeps_rejecting",
        ],
    ),
    (
        "4xx errors are retried",
        CLIENT,
        "                if error.status < 500 or not retry_on_server_error or attempt >= self.max_attempts:\n",
        "                if attempt >= self.max_attempts:\n",
        ["test_client_errors_are_not_retried"],
    ),
    (
        "charges re-sorted by amount",
        CLIENT,
        '        return [Charge.from_api(item) for item in self._list_all("/v1/charges", {"merchant": merchant_id})]\n',
        '        return sorted((Charge.from_api(item) for item in self._list_all("/v1/charges", {"merchant": merchant_id})), key=lambda c: c.amount)\n',
        ["test_returns_every_charge_in_api_order"],
    ),
    (
        "refunds not paginated",
        CLIENT,
        '        return [Refund.from_api(item) for item in self._list_all("/v1/refunds", {"merchant": merchant_id})]\n',
        '        return [Refund.from_api(item) for item in self._request("GET", "/v1/refunds", params={"merchant": merchant_id})["data"]]\n',
        ["test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "no cross-border surcharge",
        REPORT,
        "            cross_border=charge.card_country != merchant.country,\n",
        "            cross_border=False,\n",
        ["test_tidewater_matches_the_readme_example", "test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "surcharge compares card country with a hard-coded US",
        REPORT,
        "            cross_border=charge.card_country != merchant.country,\n",
        '            cross_border=charge.card_country != "US",\n',
        ["test_settlement_numbers[acct_orchard]"],
    ),
    (
        "4.4% rounded once instead of 2.9% and 1.5% rounded separately",
        FEES,
        "    fee = _percentage_of(amount, PERCENTAGE_FEE) + FIXED_FEES[currency]\n    if cross_border:\n        fee += _percentage_of(amount, CROSS_BORDER_SURCHARGE)\n    return fee\n",
        "    rate = PERCENTAGE_FEE + (CROSS_BORDER_SURCHARGE if cross_border else 0)\n    return _percentage_of(amount, rate) + FIXED_FEES[currency]\n",
        ["test_tidewater_matches_the_readme_example", "test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "surcharge computed with float arithmetic and round()",
        FEES,
        "        fee += _percentage_of(amount, CROSS_BORDER_SURCHARGE)\n",
        "        fee += round(amount * 0.015)\n",
        ["test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "calculate_fee signature no longer backwards compatible",
        FEES,
        "def calculate_fee(amount: int, currency: str, *, cross_border: bool = False) -> int:",
        "def calculate_fee(amount: int, currency: str, cross_border: bool) -> int:",
        ["test_calculate_fee", "test_fee_command", "test_existing_callers_of_calculate_fee_still_get_the_standard_fee"],
    ),
    (
        "pending charges counted",
        REPORT,
        "        if charge.status != SUCCEEDED:\n",
        '        if charge.status == "failed":\n',
        ["test_tidewater_matches_the_readme_example", "test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "failed refunds counted",
        REPORT,
        "        if refund.status == SUCCEEDED:\n",
        "        if True:\n",
        ["test_tidewater_matches_the_readme_example", "test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "lines not sorted by currency",
        REPORT,
        "        for currency in sorted(gross)\n",
        "        for currency in sorted(gross, reverse=True)\n",
        ["test_settlement_numbers[acct_nimbus]"],
    ),
    (
        "new idempotency key on every attempt",
        CLIENT,
        '            headers["Idempotency-Key"] = idempotency_key\n',
        '            headers["Idempotency-Key"] = __import__("uuid").uuid4().hex\n',
        ["test_no_duplicate_when_a_request_fails_after_creating_the_payout"],
    ),
    (
        "random idempotency key per settle run",
        SETTLE,
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}",\n',
        '                idempotency_key=__import__("uuid").uuid4().hex,\n',
        ["test_second_run_returns_the_same_payouts_and_creates_none"],
    ),
    (
        "idempotency key ignores the settlement date",
        SETTLE,
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}",\n',
        '                idempotency_key=f"settlement:{merchant_id}:{line.currency}",\n',
        ["test_each_settlement_date_is_paid_separately"],
    ),
    (
        "idempotency key ignores the currency",
        SETTLE,
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}",\n',
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}",\n',
        ["test_pays_the_net_amount_of_every_positive_currency[acct_nimbus]"],
    ),
    (
        "no idempotency key at all, POST retried on 503",
        CLIENT,
        '            headers["Idempotency-Key"] = idempotency_key\n',
        "            pass\n",
        ["test_no_duplicate_when_a_request_fails_after_creating_the_payout"],
    ),
    (
        "503 on payout creation is not retried",
        CLIENT,
        '        retry_on_server_error = method == "GET" or idempotency_key is not None\n',
        "        retry_on_server_error = False\n",
        ["test_no_duplicate_when_a_request_fails_after_creating_the_payout"],
    ),
    (
        "payout sent as JSON",
        CLIENT,
        "            data=data,  # a dict here is sent form-encoded, which is what the API expects\n",
        "            json=data,\n",
        ["test_pays_the_net_amount_of_every_positive_currency"],
    ),
    (
        "zero and negative nets are paid out too",
        SETTLE,
        "        if line.net <= 0:\n            continue\n",
        "",
        ["test_nothing_is_paid_when_no_net_is_positive[acct_sprout]", "test_nothing_is_paid_when_no_net_is_positive[acct_breakeven]"],
    ),
    (
        "zero net is paid out",
        SETTLE,
        "        if line.net <= 0:\n",
        "        if line.net < 0:\n",
        ["test_nothing_is_paid_when_no_net_is_positive[acct_breakeven]"],
    ),
    (
        "payouts returned in reverse currency order",
        SETTLE,
        "    return payouts\n",
        "    return payouts[::-1]\n",
        ["test_pays_the_net_amount_of_every_positive_currency[acct_nimbus]"],
    ),
    # Valid alternatives: these must still pass everything.
    (
        "VALID: amount is part of the idempotency key",
        SETTLE,
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}",\n',
        '                idempotency_key=f"settlement:{merchant_id}:{settlement_date}:{line.currency}:{line.net}",\n',
        None,
    ),
    (
        "VALID: page size 10 and 3 attempts",
        CLIENT,
        "MAX_ATTEMPTS = 5\nPAGE_SIZE = 20",
        "MAX_ATTEMPTS = 3\nPAGE_SIZE = 10",
        None,
    ),
    (
        "VALID: page size 1",
        CLIENT,
        "PAGE_SIZE = 20",
        "PAGE_SIZE = 1",
        None,
    ),
]


def run_one(reference: Path, mutation) -> tuple[str, bool, str]:
    name, relative, old, new, must_fail = mutation
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(reference, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        target = repo / relative
        source = target.read_text(encoding="utf-8")
        if source.count(old) != 1:
            return name, False, "PATCH DID NOT APPLY (found %d times)" % source.count(old)
        target.write_text(source.replace(old, new), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "verify_integration", "-q", "-p", "no:cacheprovider", "-rf", "--tb=line"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=900,
        )
        failed = re.findall(r"^FAILED (\S+)", proc.stdout, flags=re.M)
        errors = re.findall(r"^ERROR (\S+)", proc.stdout, flags=re.M)
        summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-300:]
        if must_fail is None:
            ok = proc.returncode == 0
            return name, ok, summary
        missing = [want for want in must_fail if not any(want in test for test in failed + errors)]
        ok = proc.returncode != 0 and not missing
        detail = summary + ("" if not missing else "   NOT CAUGHT BY: %s" % missing)
        detail += "\n        failed: " + ", ".join(sorted({t.split("::")[-1] for t in failed + errors}))
        return name, ok, detail


def main(argv: list[str]) -> int:
    reference = Path(argv[1]).resolve()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda m: run_one(reference, m), MUTATIONS))
    bad = 0
    for name, ok, detail in results:
        print("%s  %s\n        %s" % ("ok  " if ok else "GAP ", name, detail))
        bad += not ok
    print("\n%d mutations, %d problems" % (len(results), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
