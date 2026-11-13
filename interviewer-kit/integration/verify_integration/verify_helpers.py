"""Helpers shared by the integration verification suite."""
import json
import threading
from pathlib import Path

EXPECTED = json.loads(Path(__file__).with_name("expected.json").read_text(encoding="utf-8"))


class CallTimedOut(AssertionError):
    pass


def call(function, *args, timeout=20, **kwargs):
    """Run candidate code with a deadline.

    An endless retry loop then fails the test instead of hanging the whole run.
    """
    outcome = {}

    def target():
        try:
            outcome["value"] = function(*args, **kwargs)
        except BaseException as error:  # noqa: BLE001 - re-raised in the calling thread
            outcome["error"] = error

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise CallTimedOut(
            "%s did not return within %d seconds. Is something retrying without a limit?"
            % (getattr(function, "__name__", "the call"), timeout)
        )
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]
