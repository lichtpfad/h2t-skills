"""GmailClient — bidirectional Gmail adapter (re-wrapped, typed errors).

Auth / config-dir lookup / token-load / refresh logic is byte-identical to
lib/clients/gmail.py `_get_service` (~lines 50-109) per spec §10.1 (re-wrap,
not rewrite). Only the enumerated Task-2 deltas changed:

  1. module-level dotenv + google imports -> lazy, inside functions; google
     import failure -> ConfigError (was bare ImportError at import time).
  2. `print("Warning: Could not load token…")` -> dropped; `creds = None` kept.
  3. `creds.refresh` failure: RuntimeError -> AuthError(hint=...).
  4. missing credentials.json: FileNotFoundError/sys.exit -> ConfigError(hint=...).
  5. interactive InstalledAppFlow.run_local_server branch -> REMOVED, replaced
     with ConfigError (§4.1: non-interactive CLI must not launch a browser).

Read/write API methods (list_messages, send_message, …) are added in Tasks
3-4 — intentionally omitted here to keep Task 2's diff minimal. The verbatim
helpers (_attach_file, _parse_message, _get_message_body, _html_to_text,
format_message_list, format_message_detail) are transcribed now for later tasks.

Module-level seams `_install_app_flow()` / `_load_credentials()` / `_request()`
are thin lazy-import indirections (test seams, not logic changes).
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart  # noqa: F401  (used by Task 3-4 helpers)
from email.mime.text import MIMEText  # noqa: F401  (used by Task 3-4 helpers)
from pathlib import Path
from typing import Any, Dict, List

from h2t_ops.core.errors import AuthError, ConfigError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

_GOOGLE_HINT = (
    "pip install google-api-python-client google-auth google-auth-oauthlib"
    "  (or run /h2t-core:setup)"
)


def _load_dotenv() -> None:
    """Re-wrap of module-level `load_dotenv(...)` — moved inside (spec §10.1)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return  # dotenv optional; secrets.env merely augments the environment
    load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)


def _import_google():
    """Lazy google import guard (delta 1). Returns (Credentials, build).

    `from google...` at module scope is removed per spec §4.1; a missing
    google stack must surface as ConfigError, not a bare import-time crash.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.",
            hint=_GOOGLE_HINT,
        ) from e
    return Credentials, build


def _request():
    """Lazy `google.auth.transport.requests.Request()` seam."""
    try:
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.",
            hint=_GOOGLE_HINT,
        ) from e
    return Request()


def _install_app_flow():
    """Lazy `InstalledAppFlow` seam.

    §4.1 enforcement: a non-interactive connector CLI MUST NOT launch a browser
    OAuth flow. This seam exists only so tests can assert it is never reached;
    `_get_service` no longer calls it.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.",
            hint=_GOOGLE_HINT,
        ) from e
    return InstalledAppFlow


def _load_credentials(token_path: Path, creds_path: Path):
    """Token-load + 'normal' normalization + client-creds merge.

    Byte-identical to lib/clients/gmail.py `_get_service` lines 64-90, with the
    ONLY delta: the `print("Warning: Could not load token…")` side-effect is
    dropped (delta 2); `creds = None` (return None) is preserved.
    """
    Credentials, _ = _import_google()
    creds = None
    if token_path.exists():
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
            if "client_id" not in token_data and creds_path.exists():
                with open(creds_path) as f:
                    creds_data = json.load(f)
                installed = creds_data.get("installed", creds_data)
                token_data["client_id"] = installed["client_id"]
                token_data["client_secret"] = installed["client_secret"]
                token_data.setdefault(
                    "token_uri",
                    installed.get("token_uri", "https://oauth2.googleapis.com/token"),
                )
            effective_scopes = token_data.get("scopes") or SCOPES
            creds = Credentials.from_authorized_user_info(token_data, effective_scopes)
        except Exception:
            creds = None
    return creds


class GmailClient:
    """Gmail API client — read and write."""

    def __init__(self) -> None:
        _load_dotenv()
        self.service = self._get_service()

    def _get_service(self):
        shared_config = Path.home() / ".config" / "google-calendar-mcp"
        gmail_config = Path.home() / ".config" / "gmail"

        if (shared_config / "credentials.json").exists():
            config_dir = shared_config
            token_path = config_dir / "tokens.json"
            creds_path = config_dir / "credentials.json"
        else:
            config_dir = gmail_config
            token_path = config_dir / "token.json"
            creds_path = config_dir / "credentials.json"

        creds = _load_credentials(token_path, creds_path)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(_request())
                except Exception as e:
                    raise AuthError(
                        f"Gmail token refresh failed: {e}",
                        hint="delete the token file and re-run interactive auth",
                    ) from e
            else:
                if not creds_path.exists():
                    raise ConfigError(
                        f"Gmail credentials.json not found at {creds_path}.",
                        hint=(
                            "Download OAuth credentials from Google Cloud Console "
                            "to ~/.config/gmail/ (or ~/.config/google-calendar-mcp/)"
                        ),
                    )
                # §4.1 enforcement: a non-interactive connector CLI MUST NOT
                # launch a browser OAuth flow.
                raise ConfigError(
                    "Gmail not authenticated and no refresh token available.",
                    hint=(
                        "Bootstrap credentials interactively once via the legacy "
                        "gmail skill, then ~/.config/gmail/token.json is reused."
                    ),
                )
            config_dir.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

        _, build = _import_google()
        return build("gmail", "v1", credentials=creds)

    # --- Helpers (verbatim from lib/clients/gmail.py; used by Tasks 3-4) ---

    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
        return {
            "id": message["id"],
            "threadId": message["threadId"],
            "labelIds": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "body": self._get_message_body(message["payload"]),
        }

    def _get_message_body(self, payload: Dict[str, Any]) -> str:
        if "body" in payload and "data" in payload["body"]:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                elif part["mimeType"] == "text/html" and "data" in part["body"]:
                    html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                    return self._html_to_text(html)
                elif "parts" in part:
                    body = self._get_message_body(part)
                    if body:
                        return body
        return ""

    def _html_to_text(self, html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        import html as html_module
        text = html_module.unescape(text)
        return re.sub(r"\n\s*\n", "\n\n", text).strip()

    def _attach_file(self, message: MIMEMultipart, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Attachment not found: {file_path}")
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={path.name}")
        message.attach(part)


# --- Formatting helpers (used by CLI) ---

def format_message_list(messages: List[Dict[str, Any]]) -> str:
    if not messages:
        return "No messages found."
    lines = [f"Found {len(messages)} message(s):\n"]
    for i, msg in enumerate(messages, 1):
        is_unread = "UNREAD" in msg.get("labelIds", [])
        mark = "📩 " if is_unread else "   "
        lines += [
            f"{mark}{i}. **{msg['subject']}**",
            f"   From: {msg['from']}",
            f"   Date: {msg['date']}",
            f"   ID: `{msg['id']}`",
            f"   Snippet: {msg['snippet'][:100]}...",
            "",
        ]
    return "\n".join(lines)


def format_message_detail(message: Dict[str, Any]) -> str:
    lines = [
        f"# {message['subject']}\n",
        f"**From:** {message['from']}",
        f"**To:** {message['to']}",
        f"**Date:** {message['date']}",
        f"**Labels:** {', '.join(message.get('labelIds', []))}",
        "\n---\n",
        message["body"],
    ]
    return "\n".join(lines)
