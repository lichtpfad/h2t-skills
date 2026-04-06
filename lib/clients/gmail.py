"""GmailClient — bidirectional Gmail adapter (ingest + publish).

Read:  list_messages, get_message, search_messages
Write: send_message (send or draft), modify_labels
"""

import base64
import json
import re
import sys
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    raise ImportError(
        f"Google API libraries not found: {e}\n"
        "Install: pip install google-auth google-auth-oauthlib "
        "google-auth-httplib2 google-api-python-client"
    ) from e

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailClient:
    """Gmail API client — read and write."""

    def __init__(self) -> None:
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
            except Exception as e:
                print(f"Warning: Could not load token: {e}", file=sys.stderr)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    raise RuntimeError(f"Gmail token refresh failed: {e}") from e
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"credentials.json not found at {creds_path}. "
                        "Download OAuth credentials from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            config_dir.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    # --- Read ---

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
            raise Exception(f"Gmail API error: {e}") from e

    def get_message(self, message_id: str) -> Dict[str, Any]:
        try:
            message = self.service.users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute()
            return self._parse_message(message)
        except HttpError as e:
            raise Exception(f"Failed to get message {message_id}: {e}") from e

    def search_messages(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        return self.list_messages(max_results=max_results, query=query)

    def list_labels(self) -> List[Dict[str, str]]:
        try:
            results = self.service.users().labels().list(userId="me").execute()
            return results.get("labels", [])
        except HttpError as e:
            raise Exception(f"Failed to list labels: {e}") from e

    # --- Write ---

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
            action = "create draft" if as_draft else "send message"
            raise Exception(f"Failed to {action}: {e}") from e

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
            raise Exception(f"Failed to modify labels: {e}") from e

    # --- Helpers ---

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
