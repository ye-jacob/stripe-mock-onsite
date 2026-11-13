#!/usr/bin/env python3
"""Checks that this machine is ready for the mock interview sessions.

    python check_env.py

Prints one line per check. Exit status 0 means nothing failed.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOCK_API_PORT = 8642  # the port the Integration exercise uses by default

results = []


def report(status: str, title: str, detail: str = "") -> None:
    results.append(status)
    label = {"ok": "[ ok ]", "warn": "[warn]", "fail": "[FAIL]"}[status]
    print("%s %s%s" % (label, title, (": " + detail) if detail else ""))


def check_python() -> None:
    version = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info >= (3, 9):
        report("ok", "Python version", version)
    else:
        report("fail", "Python version", "%s found, 3.9 or newer is required" % version)


def check_virtualenv() -> None:
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        report("ok", "Virtual environment", sys.prefix)
    else:
        report("warn", "Virtual environment", "not active. Create and activate one as described in README.md")


def check_packages() -> bool:
    ready = True
    for name in ("requests", "pytest"):
        try:
            module = __import__(name)
        except ImportError:
            report("fail", "Package %s" % name, "not installed. Run: pip install -r requirements.txt")
            ready = False
        else:
            report("ok", "Package %s" % name, getattr(module, "__version__", "installed"))
    return ready


class _Echo(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - name fixed by the base class
        body = json.dumps({"hello": "interview", "path": self.path}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def check_local_http() -> None:
    import requests

    server = HTTPServer(("127.0.0.1", 0), _Echo)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    url = "http://127.0.0.1:%d/ping" % server.server_address[1]
    try:
        session = requests.Session()
        session.trust_env = False  # talk to this machine directly, never through a proxy
        answer = session.get(url, timeout=5).json()
        if answer.get("hello") == "interview":
            report("ok", "HTTP request to a server on this machine", url)
        else:
            report("fail", "HTTP request to a server on this machine", "unexpected answer %r" % (answer,))
    except Exception as error:  # noqa: BLE001 - any failure is worth showing as-is
        report("fail", "HTTP request to a server on this machine", repr(error))
    finally:
        server.shutdown()
        server.server_close()


def check_port() -> None:
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", MOCK_API_PORT))
    except OSError:
        report(
            "warn",
            "Port %d" % MOCK_API_PORT,
            "already in use. The Integration exercise uses it by default; close whatever is listening on it",
        )
    else:
        report("ok", "Port %d is free" % MOCK_API_PORT)
    finally:
        probe.close()


def check_proxy() -> None:
    names = [name for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy") if os.environ.get(name)]
    if names:
        report("warn", "Proxy settings", "%s is set. The exercises talk to 127.0.0.1 and ignore it" % ", ".join(names))
    else:
        report("ok", "No HTTP proxy in the environment")


def check_pytest_runs() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "checks")],
        capture_output=True,
        text=True,
        cwd=str(HERE),
    )
    last_line = (completed.stdout.strip().splitlines() or ["no output"])[-1]
    if completed.returncode == 0:
        report("ok", "pytest runs", last_line)
    else:
        report("fail", "pytest runs", last_line + " " + completed.stderr.strip()[-200:])


def check_git() -> None:
    if shutil.which("git"):
        report("ok", "git is installed")
    else:
        report("warn", "git", "not found. Not required for the mock, but a real interview has you clone a repository")


def main() -> int:
    print("Mock interview environment check\n")
    check_python()
    check_virtualenv()
    if check_packages():
        check_local_http()
        check_pytest_runs()
    check_port()
    check_proxy()
    check_git()

    failed = results.count("fail")
    warned = results.count("warn")
    print()
    if failed:
        print("%d check(s) failed. Fix them and run this script again." % failed)
        return 1
    if warned:
        print("Ready, with %d warning(s). Read them, then carry on with step 2 in README.md." % warned)
    else:
        print("Ready. Carry on with step 2 in README.md (your AI coding agent).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
