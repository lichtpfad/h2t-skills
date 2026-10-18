"""Tests for h2t_ops.core.google_auth — Google OAuth substrate."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core import paths
from h2t_ops.core.errors import AuthError, ConfigError

CAL_SCOPE = "https://www.googleapis.com/auth/calendar"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)


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
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert creds is not None


def test_resolve_calendar_uses_shared_store_only(tmp_path, monkeypatch):
    """service_name=calendar: NO ~/.config/calendar/ fallback."""
    bogus_calendar_store = tmp_path / ".config" / "calendar" / "token.json"
    _write_token(bogus_calendar_store, [CAL_SCOPE])
    _home(tmp_path, monkeypatch)
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
    _home(tmp_path, monkeypatch)
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
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert "scope" in str(ei.value).lower() or "scope" in (ei.value.hint or "").lower()
    assert "gmail_cli" not in (ei.value.hint or "")


def test_resolve_raises_autherror_when_expired_without_refresh_token(tmp_path, monkeypatch):
    """Expired token with no refresh_token → AuthError (no silent browser).

    Bypass google-auth's strict input format (which requires `refresh_token`
    to be present in the JSON payload) by stubbing `_load_credentials` to
    return a Credentials-shaped SimpleNamespace directly. This test exercises
    `resolve_google_credentials` branching, NOT google-auth's input validation.
    A token file still has to exist: core.secrets reads it before the stub runs.
    """
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text("{}")
    fake_creds = SimpleNamespace(
        valid=False,
        expired=True,
        refresh_token=None,
        scopes=[CAL_SCOPE],
    )
    monkeypatch.setattr(mod, "_load_credentials",
                        lambda data, client: fake_creds)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(AuthError):
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])


def test_install_app_flow_seam_exists_but_never_called_in_resolve(tmp_path, monkeypatch):
    """Test contract: _install_app_flow is a seam, used only to assert non-reach.

    Must point HOME at tmp_path so the test runs in an isolated FS
    and does NOT read the developer's real ~/.config/google-calendar-mcp/
    tokens.json (which could be a valid token and break the no-creds setup).
    """
    _home(tmp_path, monkeypatch)
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
    _home(tmp_path, monkeypatch)
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
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("drive", [DRIVE_SCOPE])
    assert creds is not None


# --- #548 §4, R11, R19: per-machine token, access token only in memory, one-way mirror ---

def _fake(refresh_token="fake-r1"):
    state = {"refresh_token": refresh_token, "client_id": "fake-id", "client_secret": "fake-cs",
             "token_uri": "https://oauth2.googleapis.com/token",
             "scopes": ["https://www.googleapis.com/auth/calendar"]}
    return SimpleNamespace(valid=False, expired=True, refresh_token=refresh_token,
                           scopes=state["scopes"], refresh=lambda req: None,
                           to_json=lambda: json.dumps({"token": "fake-access",
                                                       "expiry": "2099-01-01T00:00:00Z", **state}))


def _files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_durable_token_drops_short_lived_fields():
    wrapped = {"normal": {"refresh_token": "fake-r1", "token": "fake-access",
                          "expiry_date": 4102444800000, "client_id": "fake-id",
                          "scope": "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/drive"}}
    assert mod.durable_token(wrapped) == {
        "refresh_token": "fake-r1", "client_id": "fake-id",
        "scopes": ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/drive"]}


def test_refresh_of_a_wrapped_legacy_token_writes_nothing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"normal": {"refresh_token": "fake-r1", "scope": "x"}}')
    before = (_files(tmp_path), legacy.stat().st_mtime_ns)
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r1"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert (_files(tmp_path), legacy.stat().st_mtime_ns) == before   # same token, no write


def test_refresh_writes_nothing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text('{"refresh_token": "fake-r1"}')
    before = (_files(tmp_path), token.stat().st_mtime_ns)
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake())
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert (_files(tmp_path), token.stat().st_mtime_ns) == before   # no cache, no rewrite


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_new_refresh_token_rewrites_local_and_mirrors(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text('{"refresh_token": "fake-r1"}')
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-r1"}')
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r2"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    old = os.umask(0o022)
    try:
        mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    finally:
        os.umask(old)
    main = json.loads(token.read_text())
    assert main["refresh_token"] == "fake-r2" and "token" not in main
    mirror = json.loads(legacy.read_text())
    assert mirror["refresh_token"] == "fake-r2" and mirror["token"] == "fake-access"   # 3.x shape
    assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert stat.S_IMODE(legacy.stat().st_mode) == 0o600
    assert not (paths.secrets_shared() / "google.token.json").exists()   # never shared (R19)


def test_new_refresh_token_on_an_unmigrated_machine_lands_in_local(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-r1"}')
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r2"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert json.loads((paths.secrets_local() / "google.token.json").read_text())["refresh_token"] == "fake-r2"


def test_mirror_without_the_legacy_file_creates_nothing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    assert mod.mirror_legacy({"refresh_token": "fake-r2"}) == "absent"
    assert not (paths.legacy("google.store") / "tokens.json").exists()
