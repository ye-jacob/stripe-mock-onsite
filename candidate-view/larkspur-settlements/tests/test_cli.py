import socket

from settlements.cli import main


def test_fee_command(capsys):
    assert main(["fee", "1000", "usd"]) == 0
    assert capsys.readouterr().out.strip() == "Fee for a 10.00 USD charge: 0.59 USD"


def test_merchant_command(api, monkeypatch, capsys):
    monkeypatch.setenv("LARKSPUR_BASE_URL", api.base_url)
    assert main(["merchant", "acct_tidewater"]) == 0
    assert capsys.readouterr().out.strip() == (
        "acct_tidewater  Tidewater Surf Co.  country=US  currency=usd"
    )


def test_unreachable_api_is_reported_without_a_traceback(monkeypatch, capsys):
    with socket.socket() as probe:  # find a port that nothing is listening on
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    monkeypatch.setenv("LARKSPUR_BASE_URL", f"http://127.0.0.1:{unused_port}")
    assert main(["merchant", "acct_tidewater"]) == 2
    assert "Could not reach the Larkspur API" in capsys.readouterr().err
