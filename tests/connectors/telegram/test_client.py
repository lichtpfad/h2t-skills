"""Tests for h2t_ops.connectors.telegram.client."""
from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import AuthError, ConfigError


def test_module_has_no_module_level_telethon_import():
    src = Path("h2t_ops/connectors/telegram/client.py").read_text(encoding="utf-8")
    forbidden = ("import telethon", "from telethon")
    top_level = [ln for ln in src.splitlines() if ln and not ln.startswith((" ", "\t"))]
    assert not any(ln.startswith(forbidden) for ln in top_level)


def test_missing_config_raises_configerror(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._load_config()
    assert "config.json" in str(ei.value)
    assert "auth request-code" in (ei.value.hint or "")


def test_invalid_config_missing_api_hash_raises_configerror(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 123}), encoding="utf-8")
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._load_config()
    assert "api_id" in str(ei.value)
    assert "api_hash" in str(ei.value)


def test_missing_telethon_dependency_raises_configerror(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.sync":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._telegram_client_class()
    assert "Telethon not installed" in str(ei.value)
    assert "telethon" in (ei.value.hint or "")


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("too many values to unpack"),
        sqlite3.OperationalError("no column"),
    ],
)
def test_session_incompatible_errors_include_marker(exc):
    from h2t_ops.connectors.telegram.client import _session_incompatible_error

    err = _session_incompatible_error(exc)
    assert isinstance(err, AuthError)
    assert "SESSION_INCOMPATIBLE" in str(err)
    assert "auth request-code" in (err.hint or "")


def test_auth_status_without_session_reports_configured_not_authorized(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    client = TelegramClientAdapter(config_dir=tmp_path)
    assert client.auth_status() == {
        "configured": True,
        "session_exists": False,
        "authorized": False,
        "user": None,
    }


def test_auth_status_maps_authorized_user(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    (tmp_path / "session.session").write_text("fake", encoding="utf-8")

    class FakeClient:
        def __init__(self, session, api_id, api_hash):
            self.session = session
            self.api_id = api_id
            self.api_hash = api_hash

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def is_user_authorized(self):
            return True

        def get_me(self):
            return SimpleNamespace(id=7, username="stan", first_name="Stan", last_name="G")

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_telegram_client_class", lambda self: FakeClient)
    client = tmod.TelegramClientAdapter(config_dir=tmp_path)
    status = client.auth_status()
    assert status["configured"] is True
    assert status["session_exists"] is True
    assert status["authorized"] is True
    assert status["user"]["username"] == "stan"


def test_request_code_uses_connect_without_context_prompt(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    calls = []

    class FakeClient:
        def __init__(self, session, api_id, api_hash):
            self.session = session

        def __enter__(self):
            raise AssertionError("Telethon context manager would call start() and prompt")

        def connect(self):
            calls.append("connect")

        def disconnect(self):
            calls.append("disconnect")

        def send_code_request(self, phone):
            calls.append(("send_code_request", phone))
            return SimpleNamespace(phone_code_hash="hash1")

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_telegram_client_class", lambda self: FakeClient)
    result = tmod.TelegramClientAdapter(config_dir=tmp_path).request_code("+100")
    assert result == {"phone": "+100", "code_requested": True}
    assert calls == ["connect", ("send_code_request", "+100"), "disconnect"]


class _CtxClient:
    def __init__(self, inner):
        self.inner = inner

    def __enter__(self):
        return self.inner

    def __exit__(self, exc_type, exc, tb):
        return False


def test_list_dialogs_maps_dialog_rows(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    dialog = SimpleNamespace(
        entity=SimpleNamespace(id=11, username="chatname", bot=False, megagroup=True, broadcast=False),
        name="Work Chat",
        title="Work Chat",
        unread_count=3,
        archived=False,
    )

    class FakeInner:
        def iter_dialogs(self, limit=None):
            assert limit == 5
            return [dialog]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_dialogs(limit=5)
    assert rows == [{
        "id": 11,
        "title": "Work Chat",
        "username": "chatname",
        "kind": "group",
        "unread_count": 3,
        "is_archived": False,
    }]


def test_list_messages_maps_rows_and_urls(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class UrlEntity:
        offset = 6
        length = 19
        url = None

    msg = SimpleNamespace(
        id=5,
        chat_id=99,
        date=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        sender_id=7,
        sender=SimpleNamespace(first_name="Ada", last_name="L"),
        text="link: https://example.com",
        entities=[UrlEntity()],
        reply_to_msg_id=None,
    )

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            assert entity == "chat"
            assert limit == 10
            return [msg]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_messages("chat", limit=10)
    assert rows[0]["id"] == 5
    assert rows[0]["sender_name"] == "Ada L"
    assert rows[0]["text"] == "link: https://example.com"
    assert rows[0]["urls"] == ["https://example.com"]


def test_list_saved_messages_uses_me_entity(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    seen = {}

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            seen["entity"] = entity
            return []

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_saved_messages(limit=3)
    assert rows == []
    assert seen["entity"] == "me"


def test_list_mentions_filters_messages_with_me_marker(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    msg_hit = SimpleNamespace(
        id=1, chat_id=10, date=None, sender_id=None, sender=None,
        text="hello @stan", entities=[], reply_to_msg_id=None,
    )
    msg_miss = SimpleNamespace(
        id=2, chat_id=10, date=None, sender_id=None, sender=None,
        text="hello", entities=[], reply_to_msg_id=None,
    )

    class FakeInner:
        def get_me(self):
            return SimpleNamespace(username="stan", id=7, first_name="Stan", last_name="")

        def iter_messages(self, entity, limit=None):
            return [msg_hit, msg_miss]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_mentions(["10"], limit=50)
    assert [r["id"] for r in rows] == [1]


def test_list_folders_uses_raw_dialog_filters_request(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class Filter:
        id = 2
        title = "Work"
        include_peers = [SimpleNamespace(channel_id=1), SimpleNamespace(chat_id=2)]

    class FakeInner:
        def __call__(self, request):
            return [Filter()]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_dialog_filters_request_class", lambda self: object)
    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_folders()
    assert rows == [{"id": 2, "title": "Work", "peer_ids": [1, 2]}]


def test_bootstrap_dialogs_writes_timestamp_without_chats_yaml(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class FakeInner:
        def iter_dialogs(self, limit=None):
            return [SimpleNamespace(entity=SimpleNamespace(id=1))]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    result = tmod.TelegramClientAdapter(config_dir=tmp_path).bootstrap_dialogs(force=True)
    assert result["count"] == 1
    assert (tmp_path / "dialogs_bootstrapped").exists()
    assert not (tmp_path / "chats.yaml").exists()
