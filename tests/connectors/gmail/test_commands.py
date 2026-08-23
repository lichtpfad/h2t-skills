import argparse
import builtins
import sys

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
    def list_messages_page(self, **k): return {"items": self.list_messages(**k),
                                               "truncated": True, "estimated_total": 42}
    def list_threads(self, **k): return [{"id": "t1", "messages": []}]
    def get_message(self, mid): return {"id": mid, "subject": "S", "from": "f",
                                        "to": "t", "date": "d", "labelIds": [], "body": "B", "attachments": []}
    def get_thread(self, tid): return {"id": tid, "messages": [{"id": "m1", "subject": "S", "from": "f", "to": "t", "date": "d", "labelIds": [], "body": "B"}]}
    def download_attachment(self, message_id, attachment_id, output): return {"message_id": message_id, "attachment_id": attachment_id, "saved_path": output, "size": 5}
    def send_message(self, **k): return {"id": "m1"}
    def reply_to_thread(self, thread_id, *, body, body_file=None, send=False, confirm_send=False): return {"id": "reply1"}
    def forward_message(self, message_id, *, to, body=None, send=False, confirm_send=False): return {"id": "fwd1"}
    def create_label(self, name): return {"id": "Label_new", "name": name}
    def delete_label(self, label_id, *, confirm_name): return {"label_id": label_id, "name": confirm_name, "deleted": True}
    def modify_labels(self, message_id, add_labels=None, remove_labels=None): return {"labelIds": add_labels or []}
    def list_labels(self): return [{"id": "INBOX", "name": "INBOX"}]
    def trash_thread(self, thread_id, confirm_subject): return {"thread_id": thread_id, "subject": confirm_subject, "trashed": True}
    def untrash_thread(self, thread_id): return {"thread_id": thread_id, "trashed": False}
    def delete_thread(self, thread_id, confirm_subject): return {"thread_id": thread_id, "subject": confirm_subject, "deleted": True}


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
    assert out.items == [{"id": "1", "subject": "S", "from": "f", "date": "d",
                          "snippet": "x", "labelIds": []}]
    # A full page must not read as a complete result.
    assert out.meta() == {"count": 1, "truncated": True, "limit": 10,
                          "estimated_total": 42}


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


def test_trash_dispatch(monkeypatch):
    _patch(monkeypatch)
    from h2t_ops.connectors.gmail import commands as cmds_mod
    out = cmds_mod.run(_ns(gmail_cmd="trash", thread_id="thr1",
                           confirm_subject="Weekly Sync", as_json=True, fmt="human"))
    assert out == {"thread_id": "thr1", "subject": "Weekly Sync", "trashed": True}


def test_untrash_dispatch(monkeypatch):
    _patch(monkeypatch)
    from h2t_ops.connectors.gmail import commands as cmds_mod
    out = cmds_mod.run(_ns(gmail_cmd="untrash", thread_id="thr1", as_json=True, fmt="human"))
    assert out == {"thread_id": "thr1", "trashed": False}


def test_delete_without_confirm_permanent_raises(monkeypatch):
    _patch(monkeypatch)
    from h2t_ops.connectors.gmail import commands as cmds_mod
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError, match="--confirm-permanent"):
        cmds_mod.run(_ns(gmail_cmd="delete", thread_id="thr1",
                         confirm_subject="Smoke", confirm_permanent=False,
                         as_json=True, fmt="human"))


def test_delete_dispatch_with_both_flags(monkeypatch):
    _patch(monkeypatch)
    from h2t_ops.connectors.gmail import commands as cmds_mod
    out = cmds_mod.run(_ns(gmail_cmd="delete", thread_id="thr1",
                           confirm_subject="Smoke Test", confirm_permanent=True,
                           as_json=True, fmt="human"))
    assert out == {"thread_id": "thr1", "subject": "Smoke Test", "deleted": True}


def test_trash_parser_requires_confirm_subject():
    import argparse

    from h2t_ops.connectors.gmail.commands import register
    p = argparse.ArgumentParser()
    register(p.add_subparsers(dest="c"))
    with pytest.raises(SystemExit):
        p.parse_args(["gmail", "trash", "thr1"])  # missing --confirm-subject


def test_delete_parser_has_confirm_permanent_flag():
    import argparse

    from h2t_ops.connectors.gmail.commands import register
    p = argparse.ArgumentParser()
    register(p.add_subparsers(dest="c"))
    ns = p.parse_args(["gmail", "delete", "thr1", "--confirm-subject", "S", "--confirm-permanent"])
    assert ns.confirm_permanent is True


# --- Task 3 P0: parser surface ---

def test_gmail_p0_parser_surface():
    p = _parser()
    assert p.parse_args(["gmail", "reply", "T1", "--body", "ok"]).gmail_cmd == "reply"
    assert p.parse_args(["gmail", "forward", "M1", "--to", "me@example.com"]).gmail_cmd == "forward"
    assert p.parse_args(["gmail", "label-create", "Project X"]).gmail_cmd == "label-create"
    assert p.parse_args(["gmail", "label-delete", "Label_1", "--confirm-name", "Project X"]).gmail_cmd == "label-delete"


# --- Task 3 P0: command dispatch ---

def test_reply_dispatch_defaults_to_draft(monkeypatch):
    _patch(monkeypatch)
    calls = {}

    class _Stub(_FakeClient):
        def reply_to_thread(self, thread_id, *, body, body_file=None, send=False, confirm_send=False):
            calls["send"] = send
            calls["confirm_send"] = confirm_send
            return {"id": "reply1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="reply", thread_id="T1", body="OK", file=None,
                     send=False, confirm_send=False, as_json=True, fmt="human"))
    assert out["draft"] is True
    assert calls["send"] is False


def test_reply_requires_body(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(UsageError, match="body"):
        gc.run(_ns(gmail_cmd="reply", thread_id="T1", body=None, file=None,
                   send=False, confirm_send=False, as_json=False, fmt="human"))


def test_reply_send_requires_confirm_send_dispatch(monkeypatch):
    """Dispatch passes send/confirm_send flags to client; client raises UsageError."""
    from h2t_ops.core.errors import UsageError as _UE

    class _Stub(_FakeClient):
        def reply_to_thread(self, thread_id, *, body, body_file=None, send=False, confirm_send=False):
            if send and not confirm_send:
                raise _UE("gmail reply: --confirm-send is required with --send")
            return {"id": "r1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    with pytest.raises(_UE, match="--confirm-send"):
        gc.run(_ns(gmail_cmd="reply", thread_id="T1", body="Hi", file=None,
                   send=True, confirm_send=False, as_json=False, fmt="human"))


def test_forward_dispatch_defaults_to_draft(monkeypatch):
    calls = {}

    class _Stub(_FakeClient):
        def forward_message(self, message_id, *, to, body=None, send=False, confirm_send=False):
            calls["send"] = send
            return {"id": "fwd1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="forward", message_id="M1", to="a@x.com", body=None,
                     send=False, confirm_send=False, as_json=True, fmt="human"))
    assert out["draft"] is True
    assert calls["send"] is False


def test_forward_send_requires_confirm_send_dispatch(monkeypatch):
    from h2t_ops.core.errors import UsageError as _UE

    class _Stub(_FakeClient):
        def forward_message(self, message_id, *, to, body=None, send=False, confirm_send=False):
            if send and not confirm_send:
                raise _UE("gmail forward: --confirm-send is required with --send")
            return {"id": "f1"}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    with pytest.raises(_UE, match="--confirm-send"):
        gc.run(_ns(gmail_cmd="forward", message_id="M1", to="a@x.com", body=None,
                   send=True, confirm_send=False, as_json=False, fmt="human"))


def test_label_create_dispatch(monkeypatch):
    calls = {}

    class _Stub(_FakeClient):
        def create_label(self, name):
            calls["name"] = name
            return {"id": "Label_new", "name": name}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="label-create", name="Project X", as_json=True, fmt="human"))
    assert out["name"] == "Project X"
    assert calls["name"] == "Project X"


def test_label_delete_dispatch(monkeypatch):
    calls = {}

    class _Stub(_FakeClient):
        def delete_label(self, label_id, *, confirm_name):
            calls["label_id"] = label_id
            calls["confirm_name"] = confirm_name
            return {"label_id": label_id, "name": confirm_name, "deleted": True}

    import h2t_ops.connectors.gmail.client as client_mod
    monkeypatch.setattr(client_mod, "GmailClient", lambda: _Stub())
    out = gc.run(_ns(gmail_cmd="label-delete", label_id="Label_1",
                     confirm_name="Project X", as_json=True, fmt="human"))
    assert out["deleted"] is True
    assert calls["confirm_name"] == "Project X"


def test_label_delete_parser_requires_confirm_name():
    p = _parser()
    with pytest.raises(SystemExit):
        p.parse_args(["gmail", "label-delete", "Label_1"])  # missing --confirm-name
