"""Google OAuth substrate for h2t-ops connectors (non-interactive).

Owns: token load + "normal" wrap normalize + scope→scopes split, upfront scope
validation, in-memory refresh (no browser), the login write and the one-way 3.x mirror,
lazy import seams. Files are read through core.secrets: the client from secrets/shared,
this machine's token from secrets/local (#548 §4, R11, R19).

Authority: docs/superpowers/specs/2026-05-20-h2t-ops-calendar-parity-design.md,
docs/superpowers/specs/2026-10-17-storage-and-governance.md
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime

from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import AuthError, ConfigError, broken_install_hint

_BOOTSTRAP_HINT = (
    "Google OAuth bootstrap: run `h2t-ops google auth` once (opens a browser), then retry."
)

# Every scope any Google connector checks, so one consent serves all three (#532).
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

_CLIENT_HINT = (
    "Create a Desktop OAuth client: Google Cloud Console → a project with the Gmail, "
    "Calendar and Drive APIs enabled → APIs & Services → Credentials → Create credentials → "
    "OAuth client ID → Desktop app → Download JSON. Save it as {path}, then rerun "
    "`h2t-ops google auth`."
)

_GOOGLE_HINT = broken_install_hint("google-api-python-client", "google-auth", "google-auth-oauthlib")


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


_SERVICES = ("gmail", "calendar", "drive")
_DURABLE = ("refresh_token", "scopes", "client_id", "client_secret", "token_uri")


def durable_token(data: dict) -> dict:
    """The long-lived part of a token in any 3.x shape; no access token, no expiry (§4, R37)."""
    d = dict(data.get("normal", data))
    if "scope" in d and "scopes" not in d:
        d["scopes"] = d.pop("scope")
    if isinstance(d.get("scopes"), str):
        d["scopes"] = d["scopes"].split()
    return {k: d[k] for k in _DURABLE if k in d}


def _refresh_sha(data: dict | None) -> str:
    # through durable_token: a 3.x token wrapped in {"normal": …} is the same refresh token,
    # and treating it as rotated would write on every refresh (R11, round 5)
    return store.sha256((durable_token(data or {}).get("refresh_token") or "").encode())


def mirror_legacy(creds_json: dict) -> str:
    """One-way copy of this machine's token to the 3.x path POS reads (§9), in the 3.x shape.
    Removed in 4.1. Both copies belong to this machine, so there is nothing to compare."""
    legacy = paths.legacy("google.store") / "tokens.json"
    if not legacy.is_file():
        return "absent"
    store.replace(legacy, json.dumps(creds_json, ensure_ascii=False, indent=2),
                  place="legacy", compat=True, mode=0o600, keys=tuple(creds_json))
    return "written"


def _save_login(creds) -> None:
    new = json.loads(creds.to_json())
    secrets.write_json("google.token", durable_token(new))
    mirror_legacy(new)


def _load_credentials(token_data: dict, client_data: dict | None):
    """'normal' wrap normalize + scope→scopes split + client merge, on data core.secrets read.

    Returns a google.oauth2.credentials.Credentials instance, or None when the token does
    not parse. The catch list `(KeyError, ValueError)` is deliberately narrow: unexpected
    runtime bugs (AttributeError) surface instead of reading as "no token".
    """
    Credentials, _ = _import_google()
    try:
        token_data = dict(token_data)
        if "normal" in token_data:
            token_data = dict(token_data["normal"])
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
        if "client_id" not in token_data and client_data is not None:
            installed = client_data.get("installed", client_data)
            token_data["client_id"] = installed.get("client_id")
            token_data["client_secret"] = installed.get("client_secret")
            token_data.setdefault(
                "token_uri",
                installed.get("token_uri", "https://oauth2.googleapis.com/token"),
            )
        scopes = token_data.get("scopes") or []
        return Credentials.from_authorized_user_info(token_data, scopes)
    except (KeyError, ValueError):
        return None


def _client_for(token_data: dict) -> dict | None:
    """The client file is read only when the token does not carry its own client."""
    if "client_id" in durable_token(token_data):
        return None
    return secrets.read_json("google.client")[0]


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

    The token is this machine's (secrets/local, then its 3.x files — core.secrets owns the
    order). An access token lives only in this process: a refresh writes nothing unless
    Google rotated the refresh token (§4, R11).
    """
    if service_name not in _SERVICES:
        raise ConfigError(
            f"google_auth: unknown service_name {service_name!r}",
            hint="expected 'gmail', 'calendar', or 'drive'",
        )
    token_data, _ = secrets.read_json("google.token")
    creds = None if token_data is None else _load_credentials(token_data, _client_for(token_data))
    if creds is None:
        raise ConfigError(
            f"Google OAuth token not found for service {service_name!r}.",
            hint=_BOOTSTRAP_HINT,
        )
    _validate_scopes(getattr(creds, "scopes", None) or [], required_scopes)
    if not creds.valid:
        # Not only `expired`: a durable token has no access token and no expiry, which
        # google-auth reports as invalid yet not expired.
        if creds.refresh_token:
            try:
                creds.refresh(_request())          # in memory; nothing is cached on disk (R11)
            except Exception as e:
                raise AuthError(
                    f"Google OAuth token refresh failed: {e}",
                    hint=_BOOTSTRAP_HINT,
                ) from e
            if _refresh_sha(json.loads(creds.to_json())) != _refresh_sha(token_data):
                _save_login(creds)                 # Google rotated the refresh token
        else:
            raise AuthError(
                "Google OAuth token is invalid and no refresh token is available.",
                hint=_BOOTSTRAP_HINT,
            )
    return creds


def bootstrap_google_token(*, force: bool = False, open_browser: bool = True) -> dict:
    """Mint this machine's token once — the only path that reaches the browser flow.

    A token that already carries every scope and can refresh itself is left alone unless
    `force`, so setup can call this on every run without a consent screen each time.
    """
    client, _ = secrets.read_json("google.client")
    if client is None:
        where = secrets.json_path("google.client")
        raise ConfigError(f"Google OAuth client not found: {where}",
                          hint=_CLIENT_HINT.format(path=where))

    if not force:
        data, found = secrets.read_json("google.token")
        current = None if data is None else _load_credentials(data, client)
        have = set(getattr(current, "scopes", None) or [])
        if current is not None and set(GOOGLE_SCOPES) <= have and (current.valid or current.refresh_token):
            return {"status": "already_authorized", "token_path": str(found),
                    "scopes": sorted(have)}

    # A dict, not a path: the library never opens the secret file itself.
    flow = _install_app_flow().from_client_config(client, GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0, open_browser=open_browser)
    _save_login(creds)
    return {"status": "authorized", "token_path": str(secrets.json_path("google.token")),
            "scopes": sorted(creds.scopes or GOOGLE_SCOPES)}


def build_google_service(api: str, version: str, creds):
    """Lazy wrapper around googleapiclient.discovery.build."""
    _, build = _import_google()
    return build(api, version, credentials=creds)
