"""`h2t-ops google auth` — the one command that may open a browser (#532)."""
from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core.errors import ConfigError


def _creds(scopes):
    from google.oauth2.credentials import Credentials

    return Credentials(
        token="access_t", refresh_token="refresh_t",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="id.apps.googleusercontent.com", client_secret="secret",
        scopes=list(scopes), expiry=datetime.utcnow() + timedelta(hours=1),
    )


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def store(home):
    path = home / ".config" / "google-calendar-mcp"
    path.mkdir(parents=True)
    (path / "credentials.json").write_text(
        json.dumps({"installed": {"client_id": "id", "client_secret": "secret"}}), encoding="utf-8")
    return path


@pytest.fixture
def flow(monkeypatch):
    """A fake InstalledAppFlow that records how it was driven."""
    calls = SimpleNamespace(secrets=None, scopes=None, kwargs=None)

    class _Flow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            calls.secrets, calls.scopes = Path(path), list(scopes)
            return cls()

        def run_local_server(self, **kwargs):
            calls.kwargs = kwargs
            return _creds(calls.scopes)

    monkeypatch.setattr(mod, "_install_app_flow", lambda: _Flow)
    return calls


def _auth(**kw):
    from h2t_ops.connectors.google.commands import run

    return run(SimpleNamespace(google_cmd="auth", force=kw.get("force", False),
                               no_browser=kw.get("no_browser", False)))


def test_connector_is_discoverable_and_reaches_the_cli():
    from h2t_ops.cli import _MIGRATED
    from h2t_ops.core.registry import discover

    assert "google" in {spec.name for spec in discover()}
    assert "google" in _MIGRATED


def test_one_consent_covers_every_google_connector():
    """A token minted here must pass every connector's upfront scope check."""
    from h2t_ops.connectors.calendar.client import CALENDAR_SCOPES
    from h2t_ops.connectors.drive.client import DRIVE_SCOPES
    from h2t_ops.connectors.gmail.client import _GMAIL_SCOPES

    assert set(CALENDAR_SCOPES + DRIVE_SCOPES + _GMAIL_SCOPES) <= set(mod.GOOGLE_SCOPES)


def test_without_a_client_file_it_names_the_file_and_never_builds_a_flow(home, monkeypatch):
    monkeypatch.setattr(mod, "_install_app_flow", lambda: pytest.fail("no flow without a client"))
    with pytest.raises(ConfigError) as ei:
        _auth()
    assert "credentials.json" in str(ei.value)
    assert "Desktop" in ei.value.hint


def test_auth_writes_a_token_every_connector_then_accepts(store, flow):
    from h2t_ops.connectors.calendar.client import CALENDAR_SCOPES
    from h2t_ops.connectors.drive.client import DRIVE_SCOPES
    from h2t_ops.connectors.gmail.client import _GMAIL_SCOPES

    result = _auth()

    token = store / "tokens.json"
    assert result["status"] == "authorized"
    assert flow.secrets == store / "credentials.json"
    if os.name != "nt":  # Windows keeps no POSIX mode bits: chmod(0o600) reads back as 0o666
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
    for service, scopes in (("gmail", _GMAIL_SCOPES), ("calendar", CALENDAR_SCOPES),
                            ("drive", DRIVE_SCOPES)):
        assert mod.resolve_google_credentials(service, scopes).valid


def test_a_token_that_already_covers_everything_is_left_alone(store, flow):
    (store / "tokens.json").write_text(_creds(mod.GOOGLE_SCOPES).to_json(), encoding="utf-8")
    assert _auth()["status"] == "already_authorized"
    assert flow.kwargs is None


def test_force_and_a_missing_scope_both_reconsent(store, flow):
    (store / "tokens.json").write_text(_creds(mod.GOOGLE_SCOPES).to_json(), encoding="utf-8")
    assert _auth(force=True)["status"] == "authorized"

    flow.kwargs = None
    (store / "tokens.json").write_text(_creds(mod.GOOGLE_SCOPES[:1]).to_json(), encoding="utf-8")
    assert _auth()["status"] == "authorized"
    assert flow.kwargs is not None


def test_no_browser_prints_the_url_instead_of_opening_one(store, flow):
    _auth(no_browser=True)
    assert flow.kwargs["open_browser"] is False


def test_the_hint_on_a_missing_token_names_the_command(home):
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert "h2t-ops google auth" in ei.value.hint
