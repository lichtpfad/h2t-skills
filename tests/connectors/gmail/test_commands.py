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
    assert _parser().parse_args(["gmail", "threads", "--max", "5"]).gmail_cmd == "threads"
    assert _parser().parse_args(["gmail", "thread", "T1"]).gmail_cmd == "thread"
    assert _parser().parse_args(["gmail", "attachment", "M1", "A1", "--output", "file.bin"]).gmail_cmd == "attachment"


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["gmail", "list", "--json"]).as_json is True
    assert p.parse_args(["gmail", "read", "MID", "--format", "md"]).fmt == "md"
    assert p.parse_args(
        ["gmail", "send", "a", "s", "--thread-id", "T1", "--reply-to", "M1"]
    ).thread_id == "T1"


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
    def list_threads(self, **k): return [{"id": "t1", "messages": []}]
    def get_message(self, mid): return {"id": mid, "subject": "S", "from": "f",
                                        "to": "t", "date": "d", "labelIds": [], "body": "B", "attachments": []}
    def get_thread(self, tid): return {"id": tid, "messages": [{"id": "m1", "subject": "S", "from": "f", "to": "t", "date": "d", "labelIds": [], "body": "B"}]}
    def download_attachment(self, message_id, attachment_id, output): return {"message_id": message_id, "attachment_id": attachment_id, "saved_path": output, "size": 5}
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


def test_threads_json_returns_raw(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="threads", max=10, unread=False, query=None,
                     as_json=True, fmt="human"))
    assert out == [{"id": "t1", "messages": []}]


def test_thread_human_returns_detail(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="thread", thread_id="T1", as_json=False, fmt="human"))
    assert "Thread T1" in out and "Message ID" in out


def test_attachment_json_returns_saved_path(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="attachment", message_id="M1", attachment_id="A1",
                     output="file.bin", as_json=True, fmt="human"))
    assert out["saved_path"] == "file.bin"


def test_send_no_body_raises_usageerror(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(UsageError):
        gc.run(_ns(gmail_cmd="send", to="a", subject="s", body=None, file=None,
                   attach=None, draft=False, as_json=False, fmt="human"))


def test_send_dispatch_forwards_thread_flags(monkeypatch):
    calls = {}

    class _Stub(_FakeClient):
        def send_message(self, **kwargs):
            calls.update(kwargs)
            return {"id": "m1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="send", to="a@example.com", subject="Subject", body="Body",
                     file=None, attach=None, draft=False, thread_id="T1",
                     reply_to="<mid@x>", as_json=True, fmt="human"))
    assert out == {"id": "m1", "draft": False}
    assert calls["thread_id"] == "T1"
    assert calls["reply_to_message_id"] == "<mid@x>"


from h2t_ops.cli import dispatch


def test_gmail_help_exits_zero(capsys):
    assert dispatch(["gmail", "--help"]) == 0
    assert "gmail" in capsys.readouterr().out


def test_gmail_subcommand_help_exits_zero():
    assert dispatch(["gmail", "list", "--help"]) == 0
    assert dispatch(["gmail", "threads", "--help"]) == 0
    assert dispatch(["gmail", "thread", "--help"]) == 0
    assert dispatch(["gmail", "attachment", "--help"]) == 0


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


def test_ingest_gmail_shim_format_json_normalized_silent(monkeypatch, capsys):
    """`--format json` → `--json` → silent (regression-pins the gmail-only
    shim divergence: gmail consumes ANY `--format <val>`, notion only json/md)."""
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: [{"id": "1"}])
    code = dispatch(["ingest", "gmail", "list", "--format", "json"])
    assert "deprecat" not in capsys.readouterr().err.lower() and code == 0


def test_ingest_gmail_shim_format_plain_dropped_warns(monkeypatch, capsys):
    """`--format plain` dropped → human default → deprecation warning."""
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: "OK")
    code = dispatch(["ingest", "gmail", "list", "--format", "plain"])
    assert "deprecat" in capsys.readouterr().err.lower() and code == 0
