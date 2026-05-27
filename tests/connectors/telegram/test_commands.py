"""Tests for h2t_ops.connectors.telegram.commands."""
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import AuthError


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="h2t-ops")
    sub = parser.add_subparsers(dest="connector")
    from h2t_ops.connectors.telegram.commands import register

    register(sub)
    return parser


def test_parser_registers_all_leaf_verbs():
    parser = _build_parser()
    cases = [
        ["telegram", "auth", "status"],
        ["telegram", "auth", "request-code", "--phone", "+100"],
        ["telegram", "auth", "complete", "--phone", "+100", "--code", "12345"],
        ["telegram", "dialogs"],
        ["telegram", "folders"],
        ["telegram", "messages", "chat"],
        ["telegram", "send", "me", "--message", "hello"],
        ["telegram", "saved-messages"],
        ["telegram", "mentions", "--chat-id", "1"],
        ["telegram", "bootstrap"],
    ]
    for argv in cases:
        ns = parser.parse_args(argv)
        assert ns.telegram_cmd is not None


def test_json_flag_available_on_all_leaf_verbs():
    parser = _build_parser()
    cases = [
        ["telegram", "auth", "status", "--json"],
        ["telegram", "auth", "request-code", "--phone", "+100", "--json"],
        ["telegram", "auth", "complete", "--phone", "+100", "--code", "12345", "--json"],
        ["telegram", "dialogs", "--json"],
        ["telegram", "folders", "--json"],
        ["telegram", "messages", "chat", "--json"],
        ["telegram", "send", "me", "--message", "hello", "--json"],
        ["telegram", "saved-messages", "--json"],
        ["telegram", "mentions", "--chat-id", "1", "--json"],
        ["telegram", "bootstrap", "--json"],
    ]
    for argv in cases:
        ns = parser.parse_args(argv)
        assert ns.as_json is True


def test_commands_module_does_not_import_client_at_module_scope():
    src = Path("h2t_ops/connectors/telegram/commands.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if "telegram.client" in stripped or "TelegramClientAdapter" in stripped:
            assert line[0] == " ", (
                f"line {i}: TelegramClientAdapter must not be imported at module scope: {line!r}"
            )


def test_saved_messages_dispatch_is_distinct_from_legacy_saved(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    class Stub:
        def list_saved_messages(self, limit=None, days=None):
            return [{"id": 1, "text": "saved"}]

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="saved-messages",
        limit=5,
        days=None,
        as_json=False,
        fmt="human",
    )
    result = cmds.run(args)
    assert result == {"rows": [{"id": 1, "text": "saved"}], "count": 1}


def test_send_dispatch_returns_human_success(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    class Stub:
        def send_message(self, entity, text):
            assert entity == "me"
            assert text == "hello"
            return {"entity": entity, "message_id": 9, "chat_id": 77, "date": "", "text": text}

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="send",
        entity="me",
        message="hello",
        file=None,
        as_json=False,
        fmt="human",
    )
    result = cmds.run(args)
    assert "Message sent" in result


def test_send_dispatch_reads_utf8_file(monkeypatch, tmp_path):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    message_file = tmp_path / "msg.txt"
    message_file.write_text("hello", encoding="utf-8")

    class Stub:
        def send_message(self, entity, text):
            return {"entity": entity, "message_id": 9, "chat_id": 77, "date": "", "text": text}

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="send",
        entity="me",
        message=None,
        file=str(message_file),
        as_json=True,
        fmt="human",
    )
    result = cmds.run(args)
    assert result["text"] == "hello"


def test_mentions_requires_explicit_chat_id():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["telegram", "mentions"])


def test_send_requires_message_or_file():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["telegram", "send", "me"])


def test_error_envelope_contains_session_incompatible(monkeypatch, capsys):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds
    from h2t_ops.core.output import emit

    class Stub:
        def auth_status(self):
            raise AuthError("SESSION_INCOMPATIBLE: bad session", hint="recover")

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(telegram_cmd="auth-status", as_json=True, fmt="human")
    try:
        result = cmds.run(args)
    except BaseException as exc:
        rc = emit("telegram", exc=exc, fmt="json")
    else:
        rc = emit("telegram", result=result, fmt="json")
    assert rc == 4
    err = json.loads(capsys.readouterr().err)
    assert "SESSION_INCOMPATIBLE" in err["error"]["message"]


def test_cli_migrated_contains_telegram():
    import h2t_ops.cli as cli

    assert "telegram" in cli._MIGRATED


# ── P0 Coverage Tests ──────────────────────────────────────────────────────


def test_telegram_p0_parser_surface():
    parser = _build_parser()
    ns1 = parser.parse_args(["telegram", "send-file", "me", "file.txt"])
    assert ns1.telegram_cmd == "send-file"
    ns2 = parser.parse_args(
        ["telegram", "forward-message", "me", "--from", "chatname", "--message-id", "1"]
    )
    assert ns2.telegram_cmd == "forward-message"
    ns3 = parser.parse_args(["telegram", "delete-message", "me", "1", "--confirm"])
    assert ns3.telegram_cmd == "delete-message"


def test_send_file_dispatches_path_and_caption(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    calls = {}

    class Stub:
        def send_file(self, entity, path, *, caption=None):
            calls["entity"] = entity
            calls["path"] = path
            calls["caption"] = caption
            return {"entity": entity, "message_id": 42, "chat_id": 1, "date": "", "text": ""}

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="send-file",
        entity="me",
        path="file.txt",
        caption="my caption",
        as_json=True,
        fmt="human",
    )
    result = cmds.run(args)
    assert calls["entity"] == "me"
    assert calls["path"] == "file.txt"
    assert calls["caption"] == "my caption"
    assert result["message_id"] == 42


def test_forward_message_dispatches_entities_and_message_id(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    calls = {}

    class Stub:
        def forward_message(self, to_entity, *, from_entity, message_id):
            calls["to_entity"] = to_entity
            calls["from_entity"] = from_entity
            calls["message_id"] = message_id
            return {"entity": to_entity, "message_id": 99, "chat_id": 1, "date": "", "text": ""}

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="forward-message",
        to_entity="me",
        from_entity="chatname",
        message_id=99,
        as_json=True,
        fmt="human",
    )
    result = cmds.run(args)
    assert calls["to_entity"] == "me"
    assert calls["from_entity"] == "chatname"
    assert calls["message_id"] == 99
    assert result["message_id"] == 99


def test_delete_message_requires_confirm(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds
    from h2t_ops.core.errors import UsageError

    class Stub:
        def delete_message(self, entity, message_id):
            raise AssertionError("should not be called without --confirm")

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="delete-message",
        entity="me",
        message_id=1,
        confirm=False,
        as_json=False,
        fmt="human",
    )
    with pytest.raises(UsageError, match="--confirm"):
        cmds.run(args)


def test_delete_message_dispatches_after_confirm(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    calls = {}

    class Stub:
        def delete_message(self, entity, message_id):
            calls["entity"] = entity
            calls["message_id"] = message_id
            return {"entity": entity, "message_id": message_id, "deleted": True, "raw": ""}

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="delete-message",
        entity="me",
        message_id=5,
        confirm=True,
        as_json=True,
        fmt="human",
    )
    result = cmds.run(args)
    assert calls["entity"] == "me"
    assert calls["message_id"] == 5
    assert result["deleted"] is True
