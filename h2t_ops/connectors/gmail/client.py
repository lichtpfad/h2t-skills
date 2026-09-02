"""GmailClient — bidirectional Gmail adapter (re-wrapped, typed errors).

Auth / token-load / refresh logic now lives in `h2t_ops/core/google_auth.py`
(T1 of #132). Gmail consumes it via `resolve_google_credentials("gmail", ...)`
+ `build_google_service(...)`. Public API (constructor + method signatures +
behavior) is byte-identical to the previous re-wrapped client; the 30
existing Gmail tests are the regression guard.
"""
from __future__ import annotations

import base64
import re
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import AuthError, ConfigError, UsageError, broken_install_hint
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Back-compat alias — pre-T1 code referenced `SCOPES` at module scope.
SCOPES = _GMAIL_SCOPES


class _UnboundHttpError(Exception):
    """Placeholder so `except HttpError` is a valid target before google is bound.

    `from googleapiclient.errors import HttpError` at module scope is removed per
    spec §4.1 (google libs are an optional dep). `_get_service` binds the real
    class once auth has succeeded; tests monkeypatch this name.
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
                hint=broken_install_hint("google-api-python-client", "google-auth", "google-auth-oauthlib"),
            ) from e
        HttpError = _real


def _map_http_error(e: Exception, *, op: str):
    """Map a googleapiclient HttpError (or arbitrary exc) to a typed H2TError.

    Mirrors notion `_map_sdk_exc`: an already-typed `H2TError` passes through
    UNCHANGED (ТЗ-0 CRITICAL: re-wrapped typed errors must not be downgraded).
    """
    from h2t_ops.core.errors import (
        H2TError,
        NetworkError,
        NotFoundError,
        ProviderError,
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


class GmailClient:
    """Gmail API client — read and write."""

    def __init__(self) -> None:
        self.service = self._get_service()

    def _get_service(self):
        creds = resolve_google_credentials("gmail", _GMAIL_SCOPES)
        service = build_google_service("gmail", "v1", creds)
        _bind_http_error()  # bind real HttpError now that google is importable
        return service

    # --- Read ---
    #
    # API / pagination / query logic is byte-identical to the legacy methods.
    # ONLY delta: `except HttpError as e: raise Exception(...)` becomes
    # `raise _map_http_error(e, op=...) from e` (typed errors, spec §5).

    def list_messages(
        self,
        max_results: int = 10,
        query: str | None = None,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        return self.list_messages_page(
            max_results=max_results, query=query, unread_only=unread_only
        )["items"]

    def list_messages_page(
        self,
        max_results: int = 10,
        query: str | None = None,
        unread_only: bool = False,
    ) -> dict[str, Any]:
        """Same as list_messages, plus what Gmail said about the rest."""
        try:
            if unread_only and query:
                query = f"is:unread {query}"
            elif unread_only:
                query = "is:unread"
            results = self.service.users().messages().list(
                userId="me", maxResults=max_results, q=query
            ).execute()
            messages = results.get("messages", [])
            return {
                "items": [self.get_message(m["id"]) for m in messages],
                "truncated": bool(results.get("nextPageToken")),
                "estimated_total": results.get("resultSizeEstimate"),
            }
        except HttpError as e:
            raise _map_http_error(e, op="list messages") from e

    def get_message(self, message_id: str) -> dict[str, Any]:
        try:
            message = self.service.users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute()
            return self._parse_message(message)
        except HttpError as e:
            raise _map_http_error(e, op=f"get message {message_id}") from e

    def search_messages(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        return self.list_messages(max_results=max_results, query=query)

    def list_threads(
        self,
        max_results: int = 10,
        query: str | None = None,
        unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            if unread_only and query:
                query = f"is:unread {query}"
            elif unread_only:
                query = "is:unread"
            results = self.service.users().threads().list(
                userId="me", maxResults=max_results, q=query
            ).execute()
            threads = results.get("threads", [])
            return [self.get_thread(row["id"]) for row in threads]
        except HttpError as e:
            raise _map_http_error(e, op="list threads") from e

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        try:
            thread = self.service.users().threads().get(
                userId="me", id=thread_id, format="full"
            ).execute()
            return {
                "id": thread["id"],
                "messages": [self._parse_message(msg) for msg in thread.get("messages", [])],
            }
        except HttpError as e:
            raise _map_http_error(e, op=f"get thread {thread_id}") from e

    def list_labels(self) -> list[dict[str, str]]:
        try:
            results = self.service.users().labels().list(userId="me").execute()
            return results.get("labels", [])
        except HttpError as e:
            raise _map_http_error(e, op="list labels") from e

    def download_attachment(
        self,
        message_id: str,
        attachment_id: str,
        output_path: str | Path,
    ) -> dict[str, Any]:
        try:
            result = self.service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=attachment_id
            ).execute()
            data = result.get("data", "")
            payload = self._decode_base64_data(data)
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            return {
                "message_id": message_id,
                "attachment_id": attachment_id,
                "saved_path": str(target),
                "size": len(payload),
            }
        except HttpError as e:
            raise _map_http_error(
                e, op=f"download attachment {attachment_id} from {message_id}"
            ) from e

    # --- Write ---

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        as_draft: bool = False,
        thread_id: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
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
                draft_body: dict[str, Any] = {"raw": raw}
                if thread_id:
                    draft_body["threadId"] = thread_id
                return self.service.users().drafts().create(
                    userId="me", body={"message": draft_body}
                ).execute()
            else:
                send_body: dict[str, Any] = {"raw": raw}
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
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            body: dict[str, Any] = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            return self.service.users().messages().modify(
                userId="me", id=message_id, body=body
            ).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"modify labels for {message_id}") from e

    def reply_to_thread(
        self,
        thread_id: str,
        *,
        body: str,
        body_file: str | None = None,
        send: bool = False,
        confirm_send: bool = False,
    ) -> dict[str, Any]:
        if send and not confirm_send:
            raise UsageError("gmail reply: --confirm-send is required with --send")
        thread = self.get_thread(thread_id)
        messages = thread.get("messages") or []
        if not messages:
            raise UsageError(f"gmail reply: thread has no messages: {thread_id}")
        last = messages[-1]
        subject = last.get("subject") or ""
        to_addr = last.get("from") or ""
        reply_body = Path(body_file).read_text(encoding="utf-8") if body_file else body
        return self.send_message(
            to=to_addr,
            subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
            body=reply_body,
            thread_id=thread_id,
            reply_to_message_id=last.get("id"),
            as_draft=not send,
        )

    def forward_message(
        self,
        message_id: str,
        *,
        to: str,
        body: str | None = None,
        send: bool = False,
        confirm_send: bool = False,
    ) -> dict[str, Any]:
        if send and not confirm_send:
            raise UsageError("gmail forward: --confirm-send is required with --send")
        msg = self.get_message(message_id)
        subject = msg.get("subject") or ""
        orig_body = msg.get("body") or ""
        fwd_subject = subject if subject.lower().startswith("fwd:") else f"Fwd: {subject}"
        quoted = "\n\n---------- Forwarded message ----------\n" + orig_body
        fwd_body = (body + quoted) if body else quoted
        return self.send_message(
            to=to,
            subject=fwd_subject,
            body=fwd_body,
            as_draft=not send,
        )

    def create_label(self, name: str) -> dict[str, Any]:
        try:
            body = {
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            }
            return self.service.users().labels().create(userId="me", body=body).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"create label {name!r}") from e

    def delete_label(self, label_id: str, *, confirm_name: str) -> dict[str, Any]:
        labels = self.list_labels()
        match = next((lb for lb in labels if lb.get("id") == label_id), None)
        actual = (match or {}).get("name", "")
        if actual.strip().lower() != confirm_name.strip().lower():
            raise UsageError(
                f'label mismatch — expected "{confirm_name}", got "{actual}"'
            )
        try:
            self.service.users().labels().delete(userId="me", id=label_id).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"delete label {label_id}") from e
        return {"label_id": label_id, "name": actual, "deleted": True}

    def _thread_subject(self, thread_id: str) -> str:
        """Fetch first message subject — used for confirm-subject validation."""
        thread = self.get_thread(thread_id)
        messages = thread.get("messages", [])
        return messages[0].get("subject", "") if messages else ""

    def _validate_subject(self, thread_id: str, confirm_subject: str) -> str:
        actual = self._thread_subject(thread_id)
        if actual.strip().lower() != confirm_subject.strip().lower():
            from h2t_ops.core.errors import UsageError
            raise UsageError(
                f"subject mismatch — got {actual!r}, confirm-subject was {confirm_subject!r}"
            )
        return actual

    def trash_thread(self, thread_id: str, confirm_subject: str) -> dict[str, Any]:
        actual = self._validate_subject(thread_id, confirm_subject)
        try:
            self.service.users().threads().trash(userId="me", id=thread_id).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"trash thread {thread_id}") from e
        return {"thread_id": thread_id, "subject": actual, "trashed": True}

    def untrash_thread(self, thread_id: str) -> dict[str, Any]:
        try:
            self.service.users().threads().untrash(userId="me", id=thread_id).execute()
        except HttpError as e:
            raise _map_http_error(e, op=f"untrash thread {thread_id}") from e
        return {"thread_id": thread_id, "trashed": False}

    def delete_thread(self, thread_id: str, confirm_subject: str) -> dict[str, Any]:
        actual = self._validate_subject(thread_id, confirm_subject)
        try:
            self.service.users().threads().delete(userId="me", id=thread_id).execute()
        except HttpError as e:
            mapped = _map_http_error(e, op=f"delete thread {thread_id}")
            if getattr(mapped, "hint", None) is None and "insufficientPermissions" in str(e):
                from h2t_ops.core.errors import AuthError
                raise AuthError(
                    str(mapped),
                    hint="Permanent delete requires 'gmail' OAuth scope. "
                         "Re-authorize with full scope: delete the token file and re-run.",
                ) from e
            raise mapped from e
        return {"thread_id": thread_id, "subject": actual, "deleted": True}

    # --- Helpers ---

    def _parse_message(self, message: dict[str, Any]) -> dict[str, Any]:
        # RFC 5322 field names are case-insensitive, and Gmail returns them in the
        # case the sender wrote them: our own drafts arrive as "to" / "subject".
        headers = {h["name"].lower(): h["value"] for h in message["payload"]["headers"]}
        return {
            "id": message["id"],
            "threadId": message["threadId"],
            "labelIds": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body": self._get_message_body(message["payload"]),
            "attachments": self._collect_attachments(message["payload"]),
        }

    def _get_message_body(self, payload: dict[str, Any]) -> str:
        if "body" in payload and "data" in payload["body"]:
            return self._decode_base64_data(payload["body"]["data"]).decode("utf-8")
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    return self._decode_base64_data(part["body"]["data"]).decode("utf-8")
                elif part["mimeType"] == "text/html" and "data" in part["body"]:
                    html = self._decode_base64_data(part["body"]["data"]).decode("utf-8")
                    return self._html_to_text(html)
                elif "parts" in part:
                    body = self._get_message_body(part)
                    if body:
                        return body
        return ""

    def _collect_attachments(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for part in payload.get("parts", []) or []:
            filename = part.get("filename", "") or ""
            body = part.get("body", {}) or {}
            attachment_id = body.get("attachmentId")
            if filename and attachment_id:
                rows.append({
                    "attachmentId": attachment_id,
                    "filename": filename,
                    "mimeType": part.get("mimeType", ""),
                    "size": body.get("size", 0),
                })
            if part.get("parts"):
                rows.extend(self._collect_attachments(part))
        return rows

    @staticmethod
    def _decode_base64_data(data: str) -> bytes:
        if not data:
            return b""
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)

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
            # legacy raised FileNotFoundError; re-typed to UsageError so a bad
            # attachment path is exit-2 (usage). Raised during MIME assembly
            # byte-identically BEFORE base64/send.
            raise UsageError(f"attachment not found: {file_path}")
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={path.name}")
        message.attach(part)


# --- Formatting helpers (used by CLI) ---

def format_message_list(messages: list[dict[str, Any]]) -> str:
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


def format_message_detail(message: dict[str, Any]) -> str:
    lines = [
        f"# {message['subject']}\n",
        f"**From:** {message['from']}",
        f"**To:** {message['to']}",
        f"**Date:** {message['date']}",
        f"**Labels:** {', '.join(message.get('labelIds', []))}",
        "\n---\n",
        message["body"],
    ]
    attachments = message.get("attachments", [])
    if attachments:
        lines.extend([
            "\n---\n",
            "**Attachments:**",
        ])
        lines.extend([
            f"- {row['filename']} (ID: `{row['attachmentId']}`)"
            for row in attachments
        ])
    return "\n".join(lines)


def format_thread_list(threads: list[dict[str, Any]]) -> str:
    if not threads:
        return "No threads found."
    lines = [f"Found {len(threads)} thread(s):\n"]
    for i, thread in enumerate(threads, 1):
        messages = thread.get("messages", [])
        latest = messages[-1] if messages else {}
        unread = any("UNREAD" in msg.get("labelIds", []) for msg in messages)
        mark = "📩 " if unread else "   "
        lines += [
            f"{mark}{i}. Thread `{thread['id']}`",
            f"   Messages: {len(messages)}",
            f"   Latest subject: {latest.get('subject', '')}",
            f"   Latest from: {latest.get('from', '')}",
            f"   Latest date: {latest.get('date', '')}",
            "",
        ]
    return "\n".join(lines)


def format_thread_detail(thread: dict[str, Any]) -> str:
    lines = [f"# Thread {thread['id']}", ""]
    for msg in thread.get("messages", []):
        lines.extend([
            f"## {msg.get('subject', '')}",
            f"**From:** {msg.get('from', '')}",
            f"**To:** {msg.get('to', '')}",
            f"**Date:** {msg.get('date', '')}",
            f"**Labels:** {', '.join(msg.get('labelIds', []))}",
            f"**Message ID:** `{msg.get('id', '')}`",
            "",
            msg.get("body", ""),
            "",
        ])
    return "\n".join(lines).strip()
