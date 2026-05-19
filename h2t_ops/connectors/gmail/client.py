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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import AuthError, ConfigError, UsageError

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
    # test seam: lazy Request() — google libs absent until Task 7 declares deps
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


class _UnboundHttpError(Exception):
    """Placeholder so `except HttpError` is a valid target before google is bound.

    `from googleapiclient.errors import HttpError` at module scope is removed per
    spec §4.1 (google libs are an optional dep, absent until Task 7). `_get_service`
    binds the real class once auth has succeeded; tests monkeypatch this name.
    """


HttpError: type = _UnboundHttpError  # lazy seam — re-bound by _bind_http_error()


def _bind_http_error() -> None:
    """One-shot: swap the placeholder for the real googleapiclient HttpError.

    Called at the end of `_get_service` (after `build()` succeeded, so google is
    importable). Idempotent and a no-op once already bound.
    """
    global HttpError
    if HttpError is _UnboundHttpError:
        try:
            from googleapiclient.errors import HttpError as _real
        except ImportError as e:
            raise ConfigError(
                "Google API libraries not installed.",
                hint=_GOOGLE_HINT,
            ) from e
        HttpError = _real


def _map_http_error(e: Exception, *, op: str):
    """Map a googleapiclient HttpError (or arbitrary exc) to a typed H2TError.

    Mirrors notion `_map_sdk_exc`: an already-typed `H2TError` passes through
    UNCHANGED (ТЗ-0 CRITICAL: re-wrapped typed errors must not be downgraded).
    """
    from h2t_ops.core.errors import (
        AuthError, H2TError, NetworkError, NotFoundError, ProviderError,
    )
    if isinstance(e, H2TError):
        return e
    status = getattr(getattr(e, "resp", None), "status", None) or getattr(e, "status_code", 0)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    if status in (401, 403):
        return AuthError(f"Gmail auth/permission denied (HTTP {status}) during {op}: {e}")
    if status == 404:
        return NotFoundError(f"Gmail resource not found (HTTP {status}) during {op}: {e}")
    if status >= 500:
        return ProviderError(f"Gmail server error (HTTP {status}) during {op}: {e}")
    s = str(e).lower()
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(f"Gmail network error during {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")


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
            # delta 2: legacy printed a warning here; dropped per §10.1, creds=None kept
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
        service = build("gmail", "v1", credentials=creds)
        _bind_http_error()  # bind real HttpError now that google is importable
        return service

    # --- Read (re-wrap of lib/clients/gmail.py ~lines 113-149; §10.1) ---
    #
    # API / pagination / query logic is byte-identical to the legacy methods.
    # ONLY delta: `except HttpError as e: raise Exception(...)` becomes
    # `raise _map_http_error(e, op=...) from e` (typed errors, spec §5).

    def list_messages(
        self,
        max_results: int = 10,
        query: Optional[str] = None,
        unread_only: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            if unread_only and query:
                query = f"is:unread {query}"
            elif unread_only:
                query = "is:unread"
            results = self.service.users().messages().list(
                userId="me", maxResults=max_results, q=query
            ).execute()
            messages = results.get("messages", [])
            return [self.get_message(m["id"]) for m in messages]
        except HttpError as e:
            raise _map_http_error(e, op="list messages") from e

    def get_message(self, message_id: str) -> Dict[str, Any]:
        try:
            message = self.service.users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute()
            return self._parse_message(message)
        except HttpError as e:
            raise _map_http_error(e, op=f"get message {message_id}") from e

    def search_messages(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        return self.list_messages(max_results=max_results, query=query)

    def list_labels(self) -> List[Dict[str, str]]:
        try:
            results = self.service.users().labels().list(userId="me").execute()
            return results.get("labels", [])
        except HttpError as e:
            raise _map_http_error(e, op="list labels") from e

    # --- Write (re-wrap of lib/clients/gmail.py ~lines 153-210; §10.1) ---
    #
    # MIME assembly / base64 / draft-vs-send / threadId / reply-header /
    # addLabelIds-removeLabelIds logic is byte-identical to the legacy methods.
    # ONLY delta: `except HttpError as e: raise Exception(...)` becomes
    # `raise _map_http_error(e, op=...) from e` (typed errors, spec §5).
    # `_attach_file` (a helper) additionally re-types its missing-file error
    # FileNotFoundError -> UsageError so a bad path is exit-2 (usage).

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
        as_draft: bool = False,
        thread_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            message = MIMEMultipart() if attachments else MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            if reply_to_message_id:
                message["In-Reply-To"] = reply_to_message_id
                message["References"] = reply_to_message_id
            if attachments:
                message.attach(MIMEText(body, "plain"))
                for file_path in attachments:
                    self._attach_file(message, file_path)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            if as_draft:
                draft_body: Dict[str, Any] = {"raw": raw}
                if thread_id:
                    draft_body["threadId"] = thread_id
                return self.service.users().drafts().create(
                    userId="me", body={"message": draft_body}
                ).execute()
            else:
                send_body: Dict[str, Any] = {"raw": raw}
                if thread_id:
                    send_body["threadId"] = thread_id
                return self.service.users().messages().send(
                    userId="me", body=send_body
                ).execute()
        except HttpError as e:
            raise _map_http_error(
                e, op="create draft" if as_draft else "send message"
            ) from e

    def modify_labels(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        try:
            body: Dict[str, Any] = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            return self.service.users().messages().modify(
                userId="me", id=message_id, body=body
            ).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"modify labels for {message_id}") from e

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
            # delta (Task 4): legacy raised FileNotFoundError; re-typed to
            # UsageError so a bad attachment path is exit-2 (usage). Raised
            # during MIME assembly — byte-identically BEFORE base64/send.
            raise UsageError(f"attachment not found: {file_path}")
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
