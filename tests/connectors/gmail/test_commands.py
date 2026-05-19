import argparse
import sys
import builtins
from h2t_ops.connectors.gmail.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t-ops")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_gmail_subcommands():
    ns = _parser().parse_args(["gmail", "list", "--max", "5"])
    assert ns.connector == "gmail" and ns.gmail_cmd == "list" and ns.max == 5


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["gmail", "list", "--json"]).as_json is True
    assert p.parse_args(["gmail", "read", "MID", "--format", "md"]).fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    # delitem (not raw pop) so the popped client module is restored at
    # teardown -- a raw pop leaks a sys.modules-vs-package-attr desync that
    # breaks string-target monkeypatching in later tests.
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t_ops.connectors.gmail.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t_ops.connectors.gmail.commands"))
    assert seen["client"] is False


import types
import pytest
from h2t_ops.connectors.gmail import commands as gc
from h2t_ops.core.errors import UsageError


class _FakeClient:
    def list_messages(self, **k): return [{"id": "1", "subject": "S", "from": "f",
                                           "date": "d", "snippet": "x", "labelIds": []}]
    def get_message(self, mid): return {"id": mid, "subject": "S", "from": "f",
                                        "to": "t", "date": "d", "labelIds": [], "body": "B"}
    def send_message(self, **k): return {"id": "m1"}


def _ns(**kw): return types.SimpleNamespace(**kw)


def _patch(monkeypatch):
    # Patch GmailClient on the LIVE client module object (resolves via
    # sys.modules, the same path run()'s lazy `from ...client import
    # GmailClient` uses). A string target would resolve via package attrs
    # and desync if an upstream test raw-popped the client from sys.modules.
    import h2t_ops.connectors.gmail.client as m
    monkeypatch.setattr(m, "GmailClient", lambda *a, **k: _FakeClient())


def test_list_json_returns_raw(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="list", max=10, unread=False, query=None,
                     as_json=True, fmt="human"))
    assert out == [{"id": "1", "subject": "S", "from": "f", "date": "d",
                    "snippet": "x", "labelIds": []}]


def test_read_human_returns_detail(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="read", message_id="X", as_json=False, fmt="human"))
    assert "# S" in out and "B" in out


def test_send_no_body_raises_usageerror(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(UsageError):
        gc.run(_ns(gmail_cmd="send", to="a", subject="s", body=None, file=None,
                   attach=None, draft=False, as_json=False, fmt="human"))


from h2t_ops.cli import dispatch


def test_gmail_help_exits_zero(capsys):
    assert dispatch(["gmail", "--help"]) == 0
    assert "gmail" in capsys.readouterr().out


def test_gmail_subcommand_help_exits_zero():
    assert dispatch(["gmail", "list", "--help"]) == 0


def test_connectors_list_includes_gmail_no_heavy_import(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise AssertionError("connectors list must not import Google SDK")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert dispatch(["connectors"]) == 0
    assert "gmail" in capsys.readouterr().out


def test_ingest_gmail_shim_warns_on_human(monkeypatch, capsys):
    called = {}

    def fake_run(args):
        called["ran"] = True
        return "OK"

    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run", fake_run)
    code = dispatch(["ingest", "gmail", "list"])
    err = capsys.readouterr().err
    assert called.get("ran") is True and "deprecat" in err.lower() and code == 0


def test_ingest_gmail_shim_silent_on_json(monkeypatch, capsys):
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: [{"id": "1"}])
    code = dispatch(["ingest", "gmail", "list", "--json"])
    assert "deprecat" not in capsys.readouterr().err.lower() and code == 0
