"""Tests for h2t_ops.connectors.telegram.client."""
from __future__ import annotations

import builtins
import json
import sqlite3
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
