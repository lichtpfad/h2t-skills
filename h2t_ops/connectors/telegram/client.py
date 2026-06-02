"""TelegramClientAdapter - Telethon provider adapter for #135.

Telethon imports are lazy so registry/help paths stay lightweight.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from h2t_ops.core.errors import AuthError, ConfigError


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "telegram"


def _session_incompatible_error(exc: BaseException) -> AuthError:
    return AuthError(
        "SESSION_INCOMPATIBLE: Telethon session file is incompatible with this "
        f"Telethon version: {exc}",
        hint=(
            "Move ~/.config/telegram/session aside, then run "
            "h2t-ops telegram auth request-code --phone +..."
        ),
    )


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _peer_candidates(entity: str) -> list[Any]:
    """Return int candidates for a numeric peer ID string.

    Telethon requires int for peer lookup; groups/channels are negative.
    folders() returns positive IDs, so we try: -abs, abs, -100abs (supergroup).
    """
    if not entity.lstrip("-").isdigit():
        return [entity]
    n = abs(int(entity))
    return [-n, n, int(f"-100{n}")]


def _dialog_kind(entity: Any) -> str:
    if bool(_get_attr(entity, "bot", False)):
        return "bot"
    if bool(_get_attr(entity, "megagroup", False)):
        return "group"
    if bool(_get_attr(entity, "broadcast", False)):
        return "channel"
    if _get_attr(entity, "username", None) is not None:
        return "user"
    return "unknown"


def _sender_name(sender: Any) -> str:
    if sender is None:
        return ""
    first = _get_attr(sender, "first_name", "") or ""
    last = _get_attr(sender, "last_name", "") or ""
    title = _get_attr(sender, "title", "") or ""
    name = " ".join(part for part in (first, last) if part).strip()
    return name or title


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    text = _get_attr(value, "text", None)
    if text is not None:
        return str(text)
    return str(value)


def _extract_urls(msg: Any) -> list[str]:
    text = _get_attr(msg, "text", "") or ""
    urls: list[str] = []
    for ent in _get_attr(msg, "entities", []) or []:
        explicit = _get_attr(ent, "url", None)
        if explicit:
            urls.append(explicit)
            continue
        offset = _get_attr(ent, "offset", None)
        length = _get_attr(ent, "length", None)
        if isinstance(offset, int) and isinstance(length, int):
            value = text[offset : offset + length]
            if value.startswith(("http://", "https://")):
                urls.append(value)
    return urls


class TelegramClientAdapter:
    """Pure Telegram/Telethon adapter."""

    def __init__(self, *, config_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self.session_base = self.config_dir / "session"
        self.auth_state_file = self.config_dir / "auth_state.json"
        self.dialogs_bootstrap_file = self.config_dir / "dialogs_bootstrapped"

    @property
    def session_file(self) -> str:
        return str(self.session_base)

    @property
    def session_sqlite_file(self) -> Path:
        return self.config_dir / "session.session"

    def _load_config(self) -> dict[str, Any]:
        if not self.config_file.exists():
            raise ConfigError(
                f"Telegram config not found: {self.config_file}",
                hint=(
                    'Create ~/.config/telegram/config.json with {"api_id": ..., '
                    '"api_hash": "..."}, then run h2t-ops telegram auth '
                    "request-code --phone +..."
                ),
            )
        data = json.loads(self.config_file.read_text(encoding="utf-8"))
        missing = [key for key in ("api_id", "api_hash") if not data.get(key)]
        if missing:
            raise ConfigError(
                "Telegram config.json must contain api_id and api_hash "
                f"(missing: {', '.join(missing)})",
                hint="Get api_id/api_hash from https://my.telegram.org/apps",
            )
        return data

    def _telegram_client_class(self):
        try:
            from telethon.sync import TelegramClient
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return TelegramClient

    def _session_password_error_class(self):
        try:
            from telethon.errors import SessionPasswordNeededError
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return SessionPasswordNeededError

    def _dialog_filters_request_class(self):
        try:
            from telethon.tl.functions.messages import GetDialogFiltersRequest
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return GetDialogFiltersRequest

    def _client(self):
        cfg = self._load_config()
        client_cls = self._telegram_client_class()
        return client_cls(self.session_file, cfg["api_id"], cfg["api_hash"])

    @contextmanager
    def _connected_client(self) -> Iterator[Any]:
        """Connect without Telethon's context-manager start() prompt.

        Telethon's ``with TelegramClient(...)`` calls ``start()``, which may
        prompt for a phone on unauthenticated sessions. The CLI owns phone/code
        explicitly, so use connect/disconnect instead.
        """
        client = self._client()
        if hasattr(client, "connect"):
            client.connect()
            try:
                yield client
            finally:
                if hasattr(client, "disconnect"):
                    client.disconnect()
            return
        with client as connected:
            yield connected

    def auth_status(self) -> dict[str, Any]:
        self._load_config()
        session_exists = self.session_sqlite_file.exists()
        if not session_exists:
            return {
                "configured": True,
                "session_exists": False,
                "authorized": False,
                "user": None,
            }
        try:
            with self._connected_client() as client:
                authorized = bool(client.is_user_authorized())
                user = self._user_row(client.get_me()) if authorized else None
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return {
            "configured": True,
            "session_exists": True,
            "authorized": authorized,
            "user": user,
        }

    def request_code(self, phone: str) -> dict[str, Any]:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with self._connected_client() as client:
                sent = client.send_code_request(phone)
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        phone_code_hash = _get_attr(sent, "phone_code_hash", None)
        self.auth_state_file.write_text(
            json.dumps({"phone": phone, "phone_code_hash": phone_code_hash}, indent=2),
            encoding="utf-8",
        )
        return {"phone": phone, "code_requested": True}

    def complete_auth(
        self,
        phone: str,
        code: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        state: dict[str, Any] = {}
        if self.auth_state_file.exists():
            state = json.loads(self.auth_state_file.read_text(encoding="utf-8"))
        phone_code_hash = state.get("phone_code_hash")
        password_needed = self._session_password_error_class()
        try:
            with self._connected_client() as client:
                try:
                    if code:
                        client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                    elif password:
                        client.sign_in(password=password)
                    else:
                        raise ConfigError(
                            "Telegram auth complete requires code or password.",
                            hint="Run auth complete --phone +... --code CODE.",
                        )
                except password_needed:
                    if not password:
                        raise AuthError(
                            "Telegram account requires 2FA password.",
                            hint="Run auth complete again with --password.",
                        )
                    client.sign_in(password=password)
                user = self._user_row(client.get_me())
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return {"authorized": True, "user": user}

    def _user_row(self, user: Any) -> dict[str, Any] | None:
        if user is None:
            return None
        first_name = _get_attr(user, "first_name", "") or ""
        last_name = _get_attr(user, "last_name", "") or ""
        return {
            "id": _get_attr(user, "id", None),
            "username": _get_attr(user, "username", None),
            "first_name": first_name,
            "last_name": last_name,
            "name": " ".join(part for part in (first_name, last_name) if part),
        }

    def _dialog_row(self, dialog: Any) -> dict[str, Any]:
        entity = _get_attr(dialog, "entity")
        return {
            "id": _get_attr(entity, "id"),
            "title": _get_attr(dialog, "title", None) or _get_attr(dialog, "name", "") or "",
            "username": _get_attr(entity, "username"),
            "kind": _dialog_kind(entity),
            "unread_count": int(_get_attr(dialog, "unread_count", 0) or 0),
            "is_archived": bool(_get_attr(dialog, "archived", False)),
        }

    def _message_row(self, msg: Any) -> dict[str, Any]:
        return {
            "id": _get_attr(msg, "id"),
            "chat_id": _get_attr(msg, "chat_id"),
            "date": _iso(_get_attr(msg, "date")),
            "sender_id": _get_attr(msg, "sender_id"),
            "sender_name": _sender_name(_get_attr(msg, "sender")),
            "text": _get_attr(msg, "text", "") or "",
            "urls": _extract_urls(msg),
            "reply_to_msg_id": _get_attr(msg, "reply_to_msg_id"),
        }

    def list_dialogs(
        self,
        *,
        limit: int | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            with self._connected_client() as client:
                rows = [self._dialog_row(dialog) for dialog in client.iter_dialogs(limit=limit)]
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        if kind:
            rows = [row for row in rows if row["kind"] == kind]
        return rows

    def list_messages(
        self,
        entity: str,
        *,
        limit: int | None = 200,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        cutoff = None
        if days is not None:
            from datetime import timedelta

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        candidates = _peer_candidates(entity) if isinstance(entity, str) else [entity]
        try:
            with self._connected_client() as client:
                rows = []
                last_exc: Exception | None = None
                for candidate in candidates:
                    try:
                        for msg in client.iter_messages(candidate, limit=limit):
                            msg_date = _get_attr(msg, "date")
                            if cutoff is not None and isinstance(msg_date, datetime) and msg_date < cutoff:
                                continue
                            rows.append(self._message_row(msg))
                        last_exc = None
                        break
                    except ValueError as exc:
                        last_exc = exc
                if last_exc is not None:
                    raise last_exc
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return rows

    def list_saved_messages(
        self,
        *,
        limit: int | None = 200,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.list_messages("me", limit=limit, days=days)

    def list_mentions(
        self,
        chat_ids: list[str],
        *,
        days: int | None = None,
        limit: int | None = 500,
    ) -> list[dict[str, Any]]:
        cutoff = None
        if days is not None:
            from datetime import timedelta

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            with self._connected_client() as client:
                me = client.get_me()
                username = (_get_attr(me, "username", "") or "").lower()
                needle = f"@{username}" if username else ""
                rows: list[dict[str, Any]] = []
                for chat_id in chat_ids:
                    for msg in client.iter_messages(chat_id, limit=limit):
                        msg_date = _get_attr(msg, "date")
                        if cutoff is not None and isinstance(msg_date, datetime) and msg_date < cutoff:
                            continue
                        text = (_get_attr(msg, "text", "") or "").lower()
                        if needle and needle in text:
                            rows.append(self._message_row(msg))
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return rows

    def list_folders(self) -> list[dict[str, Any]]:
        request_cls = self._dialog_filters_request_class()
        try:
            with self._connected_client() as client:
                response = client(request_cls())
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        filters = _get_attr(response, "filters", response) or []
        rows = []
        for item in filters:
            peer_ids = []
            for peer in _get_attr(item, "include_peers", []) or []:
                peer_id = (
                    _get_attr(peer, "channel_id", None)
                    or _get_attr(peer, "chat_id", None)
                    or _get_attr(peer, "user_id", None)
                )
                if peer_id is not None:
                    peer_ids.append(peer_id)
            rows.append(
                {
                    "id": _get_attr(item, "id"),
                    "title": _plain_text(_get_attr(item, "title", "")),
                    "peer_ids": peer_ids,
                }
            )
        return rows

    def send_file(
        self,
        entity: str,
        path: str,
        *,
        caption: str | None = None,
    ) -> dict[str, Any]:
        try:
            with self._connected_client() as client:
                msg = client.send_file(entity, path, caption=caption)
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        row = self._message_row(msg)
        return {
            "entity": entity,
            "message_id": row["id"],
            "chat_id": row["chat_id"],
            "date": row["date"],
            "text": row["text"],
        }

    def forward_message(
        self,
        to_entity: str,
        *,
        from_entity: str,
        message_id: int,
    ) -> dict[str, Any]:
        try:
            with self._connected_client() as client:
                result = client.forward_messages(to_entity, message_id, from_peer=from_entity)
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        # Telethon may return a list; normalise to a single message
        msg = result[0] if isinstance(result, list) else result
        row = self._message_row(msg)
        return {
            "entity": to_entity,
            "message_id": row["id"],
            "chat_id": row["chat_id"],
            "date": row["date"],
            "text": row["text"],
        }

    def delete_message(self, entity: str, message_id: int) -> dict[str, Any]:
        resolved: Any = int(entity) if entity.lstrip("-").isdigit() else entity
        try:
            with self._connected_client() as client:
                result = client.delete_messages(resolved, [message_id])
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return {
            "entity": entity,
            "message_id": message_id,
            "deleted": True,
            "raw": str(result),
        }

    def send_message(self, entity: str, text: str) -> dict[str, Any]:
        resolved: Any = int(entity) if entity.lstrip("-").isdigit() else entity
        try:
            with self._connected_client() as client:
                msg = client.send_message(resolved, text)
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return {
            "entity": entity,
            "message_id": _get_attr(msg, "id"),
            "chat_id": _get_attr(msg, "chat_id"),
            "date": _iso(_get_attr(msg, "date")),
            "text": _get_attr(msg, "text", "") or text,
        }

    def bootstrap_dialogs(self, *, force: bool = False) -> dict[str, Any]:
        if self.dialogs_bootstrap_file.exists() and not force:
            return {
                "refreshed": False,
                "count": 0,
                "timestamp_path": str(self.dialogs_bootstrap_file),
            }
        try:
            with self._connected_client() as client:
                count = sum(1 for _ in client.iter_dialogs(limit=None))
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.dialogs_bootstrap_file.write_text(
            str(datetime.now(timezone.utc).timestamp()),
            encoding="utf-8",
        )
        return {
            "refreshed": True,
            "count": count,
            "timestamp_path": str(self.dialogs_bootstrap_file),
        }
