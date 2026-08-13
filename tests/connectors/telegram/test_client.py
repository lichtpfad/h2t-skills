"""Tests for h2t_ops.connectors.telegram.client."""
from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from contextlib import contextmanager

from h2t_ops.core.errors import AuthError, ConfigError, ProviderError


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


def test_list_folders_accepts_dialog_filters_wrapper(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    wrapped_filter = SimpleNamespace(
        id=4,
        title="WORK",
        include_peers=[SimpleNamespace(channel_id=10), SimpleNamespace(user_id=20)],
    )

    class FakeInner:
        def __call__(self, request):
            return SimpleNamespace(filters=[wrapped_filter])

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_dialog_filters_request_class", lambda self: object)
    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_folders()
    assert rows == [{"id": 4, "title": "WORK", "peer_ids": [10, 20]}]


def test_list_folders_flattens_text_with_entities_title(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    wrapped_filter = SimpleNamespace(
        id=5,
        title=SimpleNamespace(text="Research"),
        include_peers=[],
    )

    class FakeInner:
        def __call__(self, request):
            return SimpleNamespace(filters=[wrapped_filter])

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_dialog_filters_request_class", lambda self: object)
    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_folders()
    assert rows == [{"id": 5, "title": "Research", "peer_ids": []}]


def test_send_message_returns_normalized_row(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    sent = SimpleNamespace(
        id=9,
        chat_id=77,
        date=datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc),
        text="hello",
    )

    class FakeInner:
        def send_message(self, entity, text):
            assert entity == "me"
            assert text == "hello"
            return sent

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).send_message("me", "hello")
    assert out["entity"] == "me"
    assert out["message_id"] == 9
    assert out["chat_id"] == 77
    assert out["text"] == "hello"


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


# ── P0 Coverage: send_file / forward_message / delete_message ─────────────


def test_send_file_returns_normalized_row(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    sent = SimpleNamespace(
        id=20,
        chat_id=55,
        date=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        sender_id=7,
        sender=SimpleNamespace(first_name="Stan", last_name="G"),
        text="",
        entities=[],
        reply_to_msg_id=None,
    )

    class FakeInner:
        def send_file(self, entity, path, caption=None):
            assert entity == "me"
            assert path == "/tmp/file.pdf"
            assert caption == "my cap"
            return sent

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).send_file("me", "/tmp/file.pdf", caption="my cap")
    assert out["message_id"] == 20
    assert out["chat_id"] == 55
    assert out["entity"] == "me"


def test_send_file_without_caption(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    sent = SimpleNamespace(
        id=21, chat_id=56, date=None,
        sender_id=None, sender=None, text="", entities=[], reply_to_msg_id=None,
    )

    class FakeInner:
        def send_file(self, entity, path, caption=None):
            assert caption is None
            return sent

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).send_file("chatname", "photo.jpg")
    assert out["message_id"] == 21


def test_forward_message_returns_normalized_row(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    fwd = SimpleNamespace(
        id=30,
        chat_id=77,
        date=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
        sender_id=None,
        sender=None,
        text="forwarded text",
        entities=[],
        reply_to_msg_id=None,
    )

    class FakeInner:
        def forward_messages(self, to_entity, message_id, from_peer=None):
            assert to_entity == "me"
            assert message_id == 99
            assert from_peer == "chatname"
            return fwd

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).forward_message(
        "me", from_entity="chatname", message_id=99
    )
    assert out["message_id"] == 30
    assert out["entity"] == "me"


def test_forward_message_normalizes_list_result(tmp_path, monkeypatch):
    """Telethon may return a list when forwarding; we normalize to single message."""
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    fwd = SimpleNamespace(
        id=31, chat_id=78, date=None,
        sender_id=None, sender=None, text="fwd", entities=[], reply_to_msg_id=None,
    )

    class FakeInner:
        def forward_messages(self, to_entity, message_id, from_peer=None):
            return [fwd]  # Telethon list return

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).forward_message(
        "me", from_entity="chat", message_id=31
    )
    assert out["message_id"] == 31


def test_delete_message_returns_deleted_dict(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class FakeInner:
        def delete_messages(self, entity, message_ids):
            assert entity == "me"
            assert message_ids == [5]
            return [SimpleNamespace(pts=1)]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    out = tmod.TelegramClientAdapter(config_dir=tmp_path).delete_message("me", 5)
    assert out["entity"] == "me"
    assert out["message_id"] == 5
    assert out["deleted"] is True
    assert "raw" in out


# ── search helpers ────────────────────────────────────────────────────────────

def test_missing_telethon_raises_configerror_for_search_request(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.tl.functions.contacts":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._search_request_class()
    assert "Telethon" in str(ei.value)


def test_missing_telethon_raises_configerror_for_flood_wait(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.errors":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._flood_wait_error_class()
    assert "Telethon" in str(ei.value)


# ── search_channels ───────────────────────────────────────────────────────────

def _make_adapter_with_fake_connection(tmp_path, monkeypatch, fake_client):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    adapter = TelegramClientAdapter(config_dir=tmp_path)

    @contextmanager
    def fake_connected():
        yield fake_client

    monkeypatch.setattr(adapter, "_connected_client", fake_connected)
    return adapter


def test_search_channels_returns_shaped_rows(tmp_path, monkeypatch):
    chan = SimpleNamespace(
        id=100, username="testchan", title="Test Channel",
        participants_count=500, broadcast=True, megagroup=False, verified=False,
    )
    user_obj = SimpleNamespace(
        id=200, username="testuser", first_name="John", last_name="Doe", verified=True,
    )
    fake_result = SimpleNamespace(chats=[chan], users=[user_obj])

    class FakeClient:
        def __call__(self, req):
            return fake_result

    class FakeSearchReq:
        def __init__(self, q, limit):
            self.q = q

    class FakeFloodWait(Exception):
        seconds = 0

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    rows = adapter.search_channels("test query", limit=10)
    assert len(rows) == 2

    ch = next(r for r in rows if r["id"] == 100)
    assert ch["type"] == "channel"
    assert ch["username"] == "testchan"
    assert ch["title"] == "Test Channel"
    assert ch["participants_count"] == 500  # attribute present → returned as-is
    assert ch["is_channel"] is True
    assert ch["is_megagroup"] is False
    assert ch["verified"] is False

    usr = next(r for r in rows if r["id"] == 200)
    assert usr["type"] == "user"
    assert usr["title"] == "John Doe"
    assert usr["participants_count"] is None  # users never have participants_count
    assert usr["is_channel"] is False
    assert usr["verified"] is True


def test_search_channels_megagroup_type(tmp_path, monkeypatch):
    grp = SimpleNamespace(
        id=300, username="mygroup", title="My Group",
        participants_count=None, broadcast=False, megagroup=True, verified=False,
    )
    fake_result = SimpleNamespace(chats=[grp], users=[])

    class FakeClient:
        def __call__(self, req):
            return fake_result

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    class FakeFloodWait(Exception):
        seconds = 0

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    rows = adapter.search_channels("group")
    assert rows[0]["type"] == "group"
    assert rows[0]["is_megagroup"] is True
    assert rows[0]["is_channel"] is False
    assert rows[0]["participants_count"] is None  # absent attribute → None, not 0


def test_search_channels_raises_provider_error_on_flood_wait(tmp_path, monkeypatch):
    class FakeFloodWait(Exception):
        def __init__(self):
            super().__init__()
            self.seconds = 42  # instance attribute, matching real Telethon FloodWaitError

    class FakeClient:
        def __call__(self, req):
            raise FakeFloodWait()

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    with pytest.raises(ProviderError) as ei:
        adapter.search_channels("flood test")
    assert "FLOOD_WAIT" in str(ei.value)
    assert ei.value.details["wait_seconds"] == 42


# ── download-media / media serialization ──────────────────────────────────────


def test_message_row_includes_media_info(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    file_obj = SimpleNamespace(name="report.pdf", size=1234, mime_type="application/pdf", ext=".pdf")
    media = SimpleNamespace()  # stands in for MessageMediaDocument
    msg = SimpleNamespace(
        id=8, chat_id=42, date=None, sender_id=1, sender=None,
        text="", entities=[], reply_to_msg_id=None, media=media, file=file_obj,
    )

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            return [msg]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_messages("chat", limit=5)
    assert rows[0]["media"] == {
        "kind": "SimpleNamespace",
        "name": "report.pdf",
        "size": 1234,
        "mime_type": "application/pdf",
        "ext": ".pdf",
    }


def test_message_row_media_is_none_without_attachment(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    msg = SimpleNamespace(
        id=9, chat_id=42, date=None, sender_id=1, sender=None,
        text="hi", entities=[], reply_to_msg_id=None, media=None,
    )

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            return [msg]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_messages("chat", limit=5)
    assert rows[0]["media"] is None


def test_download_media_saves_file_and_returns_row(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    saved = out_dir / "report.pdf"

    file_obj = SimpleNamespace(name="report.pdf", size=3, mime_type="application/pdf", ext=".pdf")
    msg = SimpleNamespace(media=SimpleNamespace(), file=file_obj)

    calls = {}

    class FakeClient:
        def get_messages(self, entity, ids=None):
            calls["entity"] = entity
            calls["ids"] = ids
            return msg

        def download_media(self, message, file=None):
            calls["download_file"] = file
            Path(file).mkdir(parents=True, exist_ok=True)
            saved.write_bytes(b"pdf")
            return str(saved)

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    out = adapter.download_media("chat", 55, out_dir=str(out_dir))
    assert calls["entity"] == "chat"
    assert calls["ids"] == 55
    assert out["message_id"] == 55
    assert out["filename"] == "report.pdf"
    assert out["size"] == 3
    assert out["path"] == str(saved)
    assert out["media"]["mime_type"] == "application/pdf"


def test_download_media_raises_when_no_media(tmp_path, monkeypatch):
    msg = SimpleNamespace(media=None)

    class FakeClient:
        def get_messages(self, entity, ids=None):
            return msg

        def download_media(self, message, file=None):
            raise AssertionError("must not download when message has no media")

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    with pytest.raises(ProviderError, match="no downloadable media"):
        adapter.download_media("chat", 55, out_dir=str(tmp_path / "out"))


def test_download_media_raises_when_download_returns_none(tmp_path, monkeypatch):
    msg = SimpleNamespace(media=SimpleNamespace(), file=None)

    class FakeClient:
        def get_messages(self, entity, ids=None):
            return msg

        def download_media(self, message, file=None):
            return None  # Telethon returns None on failure

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    with pytest.raises(ProviderError, match="failed to download"):
        adapter.download_media("chat", 55, out_dir=str(tmp_path / "out"))


def test_search_channels_flood_wait_missing_seconds_fallback(tmp_path, monkeypatch):
    class FakeFloodWait(Exception):
        pass  # no .seconds attribute — graceful fallback

    class FakeClient:
        def __call__(self, req):
            raise FakeFloodWait()

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    with pytest.raises(ProviderError) as ei:
        adapter.search_channels("flood test")
    assert "FLOOD_WAIT" in str(ei.value)
    assert ei.value.details["wait_seconds"] == 0  # fallback when .seconds absent
