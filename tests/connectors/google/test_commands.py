"""`h2t-ops google auth` — the one command that may open a browser (#532)."""
from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core import paths, secrets
from h2t_ops.core.errors import ConfigError


def _creds(scopes):
    from google.oauth2.credentials import Credentials

    return Credentials(
        token="fake-access", refresh_token="fake-refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="fake-id.apps.googleusercontent.com", client_secret="fake-secret",
        scopes=list(scopes), expiry=datetime.utcnow() + timedelta(hours=1),
    )


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)
    return tmp_path


CLIENT = {"installed": {"client_id": "fake-id", "client_secret": "fake-secret"}}


@pytest.fixture
def client(home):
    path = secrets.json_path("google.client")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(CLIENT), encoding="utf-8")
    return path


@pytest.fixture
def token(client):
    return secrets.json_path("google.token")


@pytest.fixture
def flow(monkeypatch):
    """A fake InstalledAppFlow that records how it was driven."""
    calls = SimpleNamespace(config=None, scopes=None, kwargs=None)

    class _Flow:
        @classmethod
        def from_client_config(cls, config, scopes):
            calls.config, calls.scopes = config, list(scopes)
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
    assert str(secrets.json_path("google.client")) in str(ei.value)
    assert str(secrets.json_path("google.client")) in ei.value.hint
    assert "Desktop" in ei.value.hint


def test_auth_writes_a_token_every_connector_then_accepts(token, flow, monkeypatch):
    from google.oauth2.credentials import Credentials

    from h2t_ops.connectors.calendar.client import CALENDAR_SCOPES
    from h2t_ops.connectors.drive.client import DRIVE_SCOPES
    from h2t_ops.connectors.gmail.client import _GMAIL_SCOPES

    result = _auth()

    assert result["status"] == "authorized"
    assert result["token_path"] == str(token)
    assert flow.config == CLIENT                    # a dict: the library opens no file
    saved = json.loads(token.read_text(encoding="utf-8"))
    assert "token" not in saved and "expiry" not in saved   # the access token is not kept (R11)
    assert saved["refresh_token"] == "fake-refresh"
    if os.name != "nt":  # Windows keeps no POSIX mode bits: chmod(0o600) reads back as 0o666
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert not (paths.legacy("google.store") / "tokens.json").exists()   # no mirror to keep

    def refresh(self, request):             # each process gets its access token in memory
        self.token, self.expiry = "fake-access-2", datetime.utcnow() + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    monkeypatch.setattr(mod, "_request", lambda: None)
    for service, scopes in (("gmail", _GMAIL_SCOPES), ("calendar", CALENDAR_SCOPES),
                            ("drive", DRIVE_SCOPES)):
        assert mod.resolve_google_credentials(service, scopes).valid


def test_auth_mirrors_into_an_existing_3x_tokens_file(token, flow):
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-old"}', encoding="utf-8")

    _auth(force=True)

    mirror = json.loads(legacy.read_text(encoding="utf-8"))
    assert mirror["refresh_token"] == "fake-refresh" and mirror["token"] == "fake-access"
    if os.name != "nt":
        assert stat.S_IMODE(legacy.stat().st_mode) == 0o600


def test_a_token_that_already_covers_everything_is_left_alone(token, flow):
    token.parent.mkdir(parents=True)
    token.write_text(_creds(mod.GOOGLE_SCOPES).to_json(), encoding="utf-8")
    assert _auth()["status"] == "already_authorized"
    assert flow.kwargs is None


def test_force_and_a_missing_scope_both_reconsent(token, flow):
    token.parent.mkdir(parents=True)
    token.write_text(_creds(mod.GOOGLE_SCOPES).to_json(), encoding="utf-8")
    assert _auth(force=True)["status"] == "authorized"

    flow.kwargs = None
    token.write_text(_creds(mod.GOOGLE_SCOPES[:1]).to_json(), encoding="utf-8")
    assert _auth()["status"] == "authorized"
    assert flow.kwargs is not None


def test_no_browser_prints_the_url_instead_of_opening_one(token, flow):
    _auth(no_browser=True)
    assert flow.kwargs["open_browser"] is False


def test_the_hint_on_a_missing_token_names_the_command(home):
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert "h2t-ops google auth" in ei.value.hint
