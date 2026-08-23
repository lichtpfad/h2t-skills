"""Google OAuth substrate for h2t-ops connectors (non-interactive).

Owns: credential discovery (service-aware token store paths), token load +
"normal" wrap normalize + scope→scopes split, upfront scope validation,
expired-token refresh (no browser), atomic token writeback, lazy import seams.

Authority: docs/superpowers/specs/2026-05-20-h2t-ops-calendar-parity-design.md
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Optional  # noqa: F401

from h2t_ops.core.errors import AuthError, ConfigError


def _oauth_store_dir() -> Path:
    """Google OAuth token store path.

    Legacy compat path — folder name `google-calendar-mcp` is kept for backward
    compatibility with existing local installs. Comments/docs call this the
    "Google OAuth token store" (the name is not a forward architectural
    commitment).

    Wrapped in a function so `Path.home()` is evaluated at call time, allowing
    tests to `monkeypatch.setattr(Path, "home", ...)`.
    """
    return Path.home() / ".config" / "google-calendar-mcp"


_BOOTSTRAP_HINT = (
    "Run an explicit Google OAuth bootstrap/setup flow to create the "
    "Google OAuth token store, then retry."
)

_GOOGLE_HINT = (
    "pip install google-api-python-client google-auth google-auth-oauthlib"
    "  (or run /h2t-core:setup)"
)


def _load_dotenv() -> None:
    """Optional dotenv merge — re-wrap of legacy module-level call."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)


def _import_google():
    """Lazy import guard — returns (Credentials, build)."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return Credentials, build


def _request():
    """Lazy `google.auth.transport.requests.Request()` seam."""
    try:
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return Request()


def _install_app_flow():
    """Lazy InstalledAppFlow seam. §4.1 enforcement: normal connector commands
    MUST NOT reach this; tests assert via monkeypatch.setattr.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return InstalledAppFlow


def _candidate_paths(service_name: str) -> list[tuple[Path, Path]]:
    """Return (token_path, creds_path) candidates by service.

    Token fallback policy (per design doc):
      - "gmail":    shared OAuth store → ~/.config/gmail/  fallback
      - "calendar": shared OAuth store only (no calendar-specific fallback)
      - "drive":    shared OAuth store only (no drive-specific fallback)
    """
    shared = (_oauth_store_dir() / "tokens.json",
              _oauth_store_dir() / "credentials.json")
    if service_name == "gmail":
        gmail_dir = Path.home() / ".config" / "gmail"
        return [shared, (gmail_dir / "token.json", gmail_dir / "credentials.json")]
    if service_name == "calendar":
        return [shared]
    if service_name == "drive":
        return [shared]
    raise ConfigError(
        f"google_auth: unknown service_name {service_name!r}",
        hint="expected 'gmail', 'calendar', or 'drive'",
    )


def _load_credentials(token_path: Path, creds_path: Path):
    """Token-load + 'normal' wrap normalize + creds.json client-creds merge.

    Returns a google.oauth2.credentials.Credentials instance, or None when the
    token file is absent / unreadable. Behavior preserved from the previous
    Gmail-inlined version of this helper (delta 2: silent on warnings).

    Note: the exception catch list `(json.JSONDecodeError, KeyError, ValueError)`
    is a DELIBERATE stricter-than-legacy choice. The legacy Gmail-inlined helper
    used bare `except Exception`, which would also swallow unexpected runtime
    bugs (e.g. AttributeError). The narrowed catch surfaces such bugs instead
    of silently returning None — known token-parse failure modes (malformed
    JSON, missing required fields, value-shape mismatches like the google-auth
    "missing refresh_token" ValueError) remain caught.
    """
    Credentials, _ = _import_google()
    if not token_path.exists():
        return None
    try:
        with open(token_path) as f:
            token_data = json.load(f)
        if "normal" in token_data:
            token_data = token_data["normal"]
            if "expiry_date" in token_data:
                expiry_ms = token_data.pop("expiry_date")
                expiry_dt = datetime.fromtimestamp(expiry_ms / 1000)
                token_data["expiry"] = expiry_dt.isoformat() + "Z"
            if "scope" in token_data:
                token_data.setdefault("scopes", token_data.pop("scope").split())
        if "scope" in token_data and "scopes" not in token_data:
            token_data["scopes"] = token_data.pop("scope").split()
        if isinstance(token_data.get("scopes"), str):
            token_data["scopes"] = token_data["scopes"].split()
        if "client_id" not in token_data and creds_path.exists():
            with open(creds_path) as f:
                creds_data = json.load(f)
            installed = creds_data.get("installed", creds_data)
            token_data["client_id"] = installed.get("client_id")
            token_data["client_secret"] = installed.get("client_secret")
            token_data.setdefault(
                "token_uri",
                installed.get("token_uri", "https://oauth2.googleapis.com/token"),
            )
        scopes = token_data.get("scopes") or []
        return Credentials.from_authorized_user_info(token_data, scopes)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _validate_scopes(token_scopes: Iterable[str], required: Iterable[str]) -> None:
    """Upfront scope check (NEW vs legacy). Stricter than the legacy 403-at-call-time.

    No silent re-bootstrap; raise ConfigError with the neutral hint instead.
    """
    have = set(token_scopes or [])
    missing = [s for s in required if s not in have]
    if missing:
        raise ConfigError(
            f"Google OAuth token is missing required scope(s): {', '.join(missing)}",
            hint=_BOOTSTRAP_HINT,
        )


def resolve_google_credentials(service_name: str,
                               required_scopes: list[str]):
    """Non-interactive resolution of Google OAuth credentials. Never opens a browser.

    See module docstring + design 2026-05-20-h2t-ops-calendar-parity-design.md.
    """
    _load_dotenv()
    candidates = _candidate_paths(service_name)
    creds = None
    found_token_path: Path | None = None
    for token_path, creds_path in candidates:
        loaded = _load_credentials(token_path, creds_path)
        if loaded is not None:
            creds = loaded
            found_token_path = token_path
            break
    if creds is None:
        raise ConfigError(
            f"Google OAuth token not found for service {service_name!r}.",
            hint=_BOOTSTRAP_HINT,
        )
    _validate_scopes(getattr(creds, "scopes", None) or [], required_scopes)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(_request())
            except Exception as e:
                raise AuthError(
                    f"Google OAuth token refresh failed: {e}",
                    hint=_BOOTSTRAP_HINT,
                ) from e
            assert found_token_path is not None
            found_token_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = found_token_path.with_suffix(found_token_path.suffix + ".tmp")
            tmp.write_text(creds.to_json())
            os.replace(tmp, found_token_path)
        else:
            raise AuthError(
                "Google OAuth token is invalid and no refresh token is available.",
                hint=_BOOTSTRAP_HINT,
            )
    return creds


def build_google_service(api: str, version: str, creds):
    """Lazy wrapper around googleapiclient.discovery.build."""
    _, build = _import_google()
    return build(api, version, credentials=creds)
