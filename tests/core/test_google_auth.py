"""Tests for h2t_ops.core.google_auth — Google OAuth substrate."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core.errors import AuthError, ConfigError

CAL_SCOPE = "https://www.googleapis.com/auth/calendar"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _write_token(path: Path, scopes: list[str], *, with_refresh: bool = True,
                 expiry: str | None = None) -> None:
    """Write a minimal token.json that mod._load_credentials accepts.

    expiry: ISO-8601 timestamp string (e.g. "2000-01-01T00:00:00Z") to force
    `creds.expired = True` for refresh/expiry tests; default None lets the
    google library treat the token as having no explicit expiry.
    """
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": "id.apps.googleusercontent.com",
        "client_secret": "secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "access_t",
        "scopes": list(scopes),
    }
    if with_refresh:
        payload["refresh_token"] = "refresh_t"
    if expiry is not None:
        payload["expiry"] = expiry
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_returns_credentials_for_matching_scope(tmp_path, monkeypatch):
    """Happy path: token has required scope, creds returned without browser.

    Explicit future expiry — without it, google-auth defaults to immediate
    expiry, making creds.expired==True and triggering a live refresh call
    against the network. The future expiry keeps the test deterministic and
    fully offline.
    """
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [CAL_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert creds is not None


def test_resolve_calendar_uses_shared_store_only(tmp_path, monkeypatch):
    """service_name=calendar: NO ~/.config/calendar/ fallback."""
    bogus_calendar_store = tmp_path / ".config" / "calendar" / "token.json"
    _write_token(bogus_calendar_store, [CAL_SCOPE])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert "Google OAuth bootstrap" in ei.value.hint
    assert "gmail_cli" not in ei.value.hint
    assert "gmail skill" not in ei.value.hint


def test_resolve_gmail_falls_back_to_gmail_store(tmp_path, monkeypatch):
    """service_name=gmail: shared store missing, fall back to ~/.config/gmail/token.json.

    Explicit future expiry (same rationale as the happy-path test above).
    """
    gmail_store = tmp_path / ".config" / "gmail" / "token.json"
    _write_token(gmail_store, [GMAIL_READ_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("gmail", [GMAIL_READ_SCOPE])
    assert creds is not None


def test_resolve_raises_configerror_when_token_missing_required_scope(tmp_path, monkeypatch):
    """Upfront scope validation — token has Gmail scope but not Calendar scope.

    This is the NEW stricter behavior (vs legacy's confusing 403 at API call time).
    """
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [GMAIL_READ_SCOPE])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert "scope" in str(ei.value).lower() or "scope" in (ei.value.hint or "").lower()
    assert "gmail_cli" not in (ei.value.hint or "")


def test_resolve_raises_autherror_when_expired_without_refresh_token(monkeypatch):
    """Expired token with no refresh_token → AuthError (no silent browser).

    Bypass google-auth's strict input format (which requires `refresh_token`
    to be present in the JSON payload) by stubbing `_load_credentials` to
    return a Credentials-shaped SimpleNamespace directly. This test exercises
    `resolve_google_credentials` branching, NOT google-auth's input validation.
    """
    fake_creds = SimpleNamespace(
        valid=False,
        expired=True,
        refresh_token=None,
        scopes=[CAL_SCOPE],
    )
    monkeypatch.setattr(mod, "_load_credentials",
                        lambda token_path, creds_path: fake_creds)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(AuthError):
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])


def test_install_app_flow_seam_exists_but_never_called_in_resolve(tmp_path, monkeypatch):
    """Test contract: _install_app_flow is a seam, used only to assert non-reach.

    Must monkeypatch Path.home → tmp_path so the test runs in an isolated FS
    and does NOT read the developer's real ~/.config/google-calendar-mcp/
    tokens.json (which could be a valid token and break the no-creds setup).
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    called = {"n": 0}
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: called.__setitem__("n", called["n"] + 1))
    # Resolve will fail (no creds in tmp_path), but it must NOT call the browser seam.
    with pytest.raises((ConfigError, AuthError)):
        mod.resolve_google_credentials("calendar",
                                       ["https://www.googleapis.com/auth/calendar"])
    assert called["n"] == 0


def test_resolve_drive_uses_shared_store_only(tmp_path, monkeypatch):
    """service_name='drive': shared OAuth store only, NO drive-specific fallback."""
    # A bogus drive-specific token at ~/.config/drive/ must be ignored.
    bogus_drive_store = tmp_path / ".config" / "drive" / "token.json"
    _write_token(bogus_drive_store, [DRIVE_SCOPE])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("drive", [DRIVE_SCOPE])
    # Hint stays neutral (same constant Calendar uses).
    assert "Google OAuth bootstrap" in ei.value.hint
    assert "drive_cli" not in (ei.value.hint or "")


def test_resolve_drive_happy_path_via_shared_store(tmp_path, monkeypatch):
    """service_name='drive': token in shared store with drive scope -> creds returned."""
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [DRIVE_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("drive", [DRIVE_SCOPE])
    assert creds is not None
