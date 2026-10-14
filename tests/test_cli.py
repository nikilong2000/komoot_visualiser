import sys

from komoot_visualiser import cli


def test_starts_the_app_reachable_only_from_this_computer(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.streamlit_cli, "main", lambda args, prog_name: calls.append(args))
    monkeypatch.setattr(sys, "argv", ["komoot-visualiser", "--server.port=8600"])

    cli.main()

    [args] = calls
    assert args[:2] == ["run", str(cli.APP)]
    assert cli.APP.is_file()
    assert "--server.address=localhost" in args
    assert args[-1] == "--server.port=8600"
