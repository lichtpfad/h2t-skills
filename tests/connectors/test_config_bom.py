"""Config files a person edits by hand must survive Windows Notepad (D2, #541).

Measured 2026-10-15 on Windows: a Telegram config.json saved by Notepad carried a UTF-8 BOM,
and the connector answered `Unexpected UTF-8 BOM` as a provider error with no hint. Google's
token and client files were opened without an encoding — cp1252 on Windows — so a BOM there
read as a missing token instead.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from h2t_ops.core.errors import ConfigError

BOM = b"\xef\xbb\xbf"


def test_telegram_config_with_a_bom_loads(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_bytes(BOM + json.dumps({"api_id": 1, "api_hash": "h"}).encode())
    assert TelegramClientAdapter(config_dir=tmp_path)._load_config()["api_id"] == 1


def test_telegram_config_that_is_not_json_says_how_to_fix_it(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text('{"api_id": ТУТ_ЧИСЛО, "api_hash": "x"}', encoding="utf-8")
    with pytest.raises(ConfigError) as ei:
        TelegramClientAdapter(config_dir=tmp_path)._load_config()
    assert "config.json" in str(ei.value)
    assert "line 1" in str(ei.value)
    assert ei.value.hint


def test_google_token_and_client_with_a_bom_resolve(tmp_path, monkeypatch):
    from h2t_ops.core import google_auth as mod

    store = tmp_path / ".config" / "google-calendar-mcp"
    store.mkdir(parents=True)
    token = {"token": "t", "refresh_token": "r", "token_uri": "https://oauth2.googleapis.com/token",
             "scopes": ["https://www.googleapis.com/auth/calendar"], "expiry": "2099-01-01T00:00:00Z"}
    (store / "tokens.json").write_bytes(BOM + json.dumps(token).encode())
    (store / "credentials.json").write_bytes(
        BOM + json.dumps({"installed": {"client_id": "id", "client_secret": "s"}}).encode())
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    creds = mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert creds.client_id == "id"


def test_research_config_with_a_bom_loads(tmp_path):
    from h2t_ops.connectors.research.fetch import load_config

    path = tmp_path / "fetch.json"
    path.write_bytes(BOM + json.dumps({"timeout_s": 7}).encode())
    assert load_config(path)["timeout_s"] == 7
