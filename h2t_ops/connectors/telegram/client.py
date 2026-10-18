"""TelegramClientAdapter - Telethon provider adapter for #135.

Telethon imports are lazy so registry/help paths stay lightweight.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import AuthError, ConfigError, NotFoundError, ProviderError


def _session_incompatible_error(exc: BaseException) -> AuthError:
    return AuthError(
        "SESSION_INCOMPATIBLE: Telethon session file is incompatible with this "
        f"Telethon version: {exc}",
        hint=(
            f"Move {paths.secrets_local() / 'telegram.session'} aside, then run "
            "h2t-ops telegram auth request-code --phone +..."
        ),
    )


_QR_HINT = "Log in by QR instead — no code needed: h2t-ops telegram auth qr"

# Where a login code went, keyed by the Telethon class name of SentCode.type (SentCodeType*)
# or SentCode.next_type (CodeType*). The CLI used to drop this and print only
# `code_requested: true`, so nobody knew where to look (2026-10-14).
_CODE_CHANNELS = {
    "App": ("app", "in the Telegram app: the verified 'Telegram' chat on a logged-in device"),
    "Sms": ("sms", "by SMS"),
    "SmsWord": ("sms", "by SMS (a word)"),
    "SmsPhrase": ("sms", "by SMS (a phrase)"),
    "FirebaseSms": ("sms", "by SMS"),
    "FragmentSms": ("fragment", "through Fragment"),
    "Call": ("call", "by a phone call"),
    "FlashCall": ("call", "by a flash call: the code is the last digits of the calling number"),
    "MissedCall": ("call", "by a missed call: the code is the last digits of the calling number"),
    "EmailCode": ("email", "by email, to the account's login email"),
}


def _code_channel(code_type: Any) -> tuple[str, str] | None:
    if code_type is None:
        return None
    name = type(code_type).__name__.removeprefix("SentCodeType").removeprefix("CodeType")
    return _CODE_CHANNELS.get(name, (name.lower(), name))


def _sent_code_view(sent: Any) -> dict[str, Any]:
    code_type = _get_attr(sent, "type")
    if type(code_type).__name__ == "SentCodeTypeSetUpEmailRequired":
        raise AuthError(
            "Telegram sent no code: it requires a login email on this account first.",
            hint=_QR_HINT,
        )
    channel, where = _code_channel(code_type) or ("unknown", "unknown")
    following = _code_channel(_get_attr(sent, "next_type"))
    view = {
        "code_requested": True,
        "channel": channel,
        "where": where,
        "next_channel": following[0] if following else None,
        "resend_after_s": _get_attr(sent, "timeout"),
    }
    pattern = _get_attr(code_type, "email_pattern")
    if pattern:
        view["email_pattern"] = pattern
    return view


def _peer_unresolved_error(entity: Any, exc: BaseException) -> NotFoundError:
    return NotFoundError(
        f"PEER_UNRESOLVED: could not resolve telegram peer {entity!r}: {exc}",
        hint=(
            "Pass the chat title or @username. A numeric id from `dialogs` only "
            "resolves once the peer is cached in the session — run "
            "h2t-ops telegram bootstrap --force first."
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
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()
    return str(dt)


_CHANNEL_OFFSET = 10 ** 12


def _peer_candidates(entity: str) -> list[Any]:
    """Return int candidates for a numeric peer ID string.

    Telethon requires int for peer lookup; groups/channels are negative.
    folders() returns positive IDs, so we try: -abs, abs, -100abs (supergroup).
    """
    if not entity.lstrip("-").isdigit():
        return [entity]
    n = abs(int(entity))
    return [-n, n, int(f"-100{n}")]


def _input_peer_from_sqlite(session_file: Path, peer_id: int, dest: bool = False) -> Any | None:
    """Build InputPeer directly from Telethon's SQLite session, no API call.

    Telethon stores channels as -(10^12 + peer_id) and legacy groups as -peer_id.
    Reading the session DB lets us build InputPeerChannel / InputPeerChat without
    triggering get_entity() → GetContactsRequest → FloodWait. dest: the session lives in
    a directory the caller named (config_dir=), not in secrets/local.
    """
    if not session_file.exists():
        return None
    try:
        from telethon.tl.types import InputPeerChannel, InputPeerChat
    except ImportError:
        return None
    n = abs(peer_id)
    candidates = [
        -(_CHANNEL_OFFSET + n),  # channel: stored as -(10^12 + peer_id)
        -n,                       # legacy group: stored as -peer_id
    ]
    try:
        with store.connect_sqlite(session_file, place="secrets.local", library="telethon",
                                  dest=dest) as conn:
            for stored_id in candidates:
                row = conn.execute(
                    "SELECT id, hash FROM entities WHERE id=?", (stored_id,)
                ).fetchone()
                if row is not None:
                    entity_id, access_hash = row
                    if abs(entity_id) > _CHANNEL_OFFSET:
                        channel_id = abs(entity_id) - _CHANNEL_OFFSET
                        return InputPeerChannel(channel_id=channel_id, access_hash=access_hash)
                    return InputPeerChat(chat_id=abs(entity_id))
    except sqlite3.Error:
        return None
    return None


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


def _media_info(msg: Any) -> dict[str, Any] | None:
    """Summarise a message's attachment, or None if there is no media."""
    media = _get_attr(msg, "media", None)
    if media is None:
        return None
    f = _get_attr(msg, "file", None)
    return {
        "kind": type(media).__name__,
        "name": _get_attr(f, "name", None),
        "size": _get_attr(f, "size", None),
        "mime_type": _get_attr(f, "mime_type", None),
        "ext": _get_attr(f, "ext", None),
    }


def _plain_name(raw: str) -> str:
    """One path segment on every platform: no / or \\, no drive colon, no leading dot."""
    for ch in ("/", "\\", ":"):
        raw = raw.replace(ch, "_")
    return raw.strip().lstrip(".")


def _media_filename(msg: Any, entity: str, message_id: int) -> str:
    """The attachment's own name, last segment only ("../../x.pdf" is x.pdf), else
    <entity>-<id><ext> — the adapter names the file, not Telethon (R47)."""
    f = _get_attr(msg, "file", None)
    name = _plain_name(str(_get_attr(f, "name", None) or "").replace("\\", "/").rsplit("/", 1)[-1])
    return name or _plain_name(f"{entity}-{message_id}{_get_attr(f, 'ext', None) or ''}")


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
        """config_dir: the 3.x layout under a directory the caller names (tests); every file
        there is written with dest=True and read through core.secrets (R42). Without it:
        keys in telegram.env, session and auth state in secrets/local, marker in state."""
        self.config_dir = Path(config_dir) if config_dir is not None else None
        self._dest = self.config_dir is not None
        self._config: dict[str, Any] | None = None
        if self.config_dir is not None:
            self.config_file = self.config_dir / "config.json"
            self.session_base = self.config_dir / "session"
            self.auth_state_file = self.config_dir / "auth_state.json"
            self.dialogs_bootstrap_file = self.config_dir / "dialogs_bootstrapped"
        else:
            self.session_base = paths.secrets_local() / "telegram"   # Telethon adds .session
            self.auth_state_file = secrets.json_path("telegram.auth-state")
            self.dialogs_bootstrap_file = paths.state_dir() / "telegram" / "dialogs_bootstrapped"

    @property
    def session_file(self) -> str:
        return str(self.session_base)

    @property
    def session_sqlite_file(self) -> Path:
        return self.session_base.with_name(self.session_base.name + ".session")

    def _load_config(self) -> dict[str, Any]:
        if self.config_dir is not None:
            return self._load_config_dir()
        api_id, api_hash = secrets.get("TELEGRAM_API_ID"), secrets.get("TELEGRAM_API_HASH")
        env_file = secrets.provider_file("telegram")
        source = env_file
        if not (api_id and api_hash):
            legacy = secrets.telegram_legacy_config()   # 4.0.x fallback, per key: the 3.x config.json
            if legacy is not None:
                legacy = self._checked(legacy, "the 3.x config.json")
                if not api_id:
                    api_id, source = str(legacy["api_id"]), "the 3.x config.json"
                api_hash = api_hash or legacy["api_hash"]
        missing = [k for k, v in (("TELEGRAM_API_ID", api_id), ("TELEGRAM_API_HASH", api_hash)) if not v]
        if missing:
            raise ConfigError(
                f"Telegram API keys not found in {env_file} (missing: {', '.join(missing)})",
                hint=(
                    f"Put TELEGRAM_API_ID and TELEGRAM_API_HASH (from https://my.telegram.org/apps) "
                    f"in {env_file}, then run h2t-ops telegram auth qr — or, without a second "
                    "device, h2t-ops telegram auth request-code --phone +..."
                ),
            )
        try:
            return {"api_id": int(api_id), "api_hash": api_hash}   # Telethon wants an int
        except ValueError:
            raise ConfigError(f"TELEGRAM_API_ID in {source} is not a number",
                              hint="Get api_id from https://my.telegram.org/apps") from None

    def _load_config_dir(self) -> dict[str, Any]:
        data = secrets.telegram_legacy_config(self.config_dir)
        if data is None:
            raise ConfigError(
                f"Telegram config not found: {self.config_file}",
                hint=(
                    f'Create {self.config_file} with {{"api_id": ..., '
                    '"api_hash": "..."} (from https://my.telegram.org/apps), then run '
                    "h2t-ops telegram auth qr — or, without a second device, "
                    "h2t-ops telegram auth request-code --phone +..."
                ),
            )
        return self._checked(data, "config.json")

    @staticmethod
    def _checked(data: dict[str, Any], source: str) -> dict[str, Any]:
        missing = [key for key in ("api_id", "api_hash") if not data.get(key)]
        if missing:
            raise ConfigError(
                f"Telegram {source} must contain api_id and api_hash "
                f"(missing: {', '.join(missing)})",
                hint="Get api_id/api_hash from https://my.telegram.org/apps",
            )
        return data

    def _adopt_legacy_session(self) -> None:
        """Until the migration, Telethon works on a copy: it writes the file it opens, and the
        3.x path is not the package's to write (§7.3). backup() reads a consistent snapshot
        even if a 3.x process holds the old session open."""
        if self._dest:
            return
        new, old = self.session_sqlite_file, paths.legacy("telegram") / "session.session"
        if new.exists() or not old.is_file():
            return
        store.sqlite_copy(old, new, place="secrets.local")
        print(f"telegram: session copied to {new}; the old one is left as is", file=sys.stderr)

    def _read_auth_state(self) -> dict[str, Any] | None:
        if self.config_dir is not None:
            return secrets.read_json_at(self.auth_state_file, root=self.config_dir)
        return secrets.read_json("telegram.auth-state")[0]

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

    def _search_request_class(self):
        try:
            from telethon.tl.functions.contacts import SearchRequest
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return SearchRequest

    def _flood_wait_error_class(self):
        try:
            from telethon.errors import FloodWaitError
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return FloodWaitError

    def _client(self):
        cfg = self._config if self._config is not None else self._load_config()
        client_cls = self._telegram_client_class()
        return client_cls(self.session_file, cfg["api_id"], cfg["api_hash"])

    @contextmanager
    def _connected_client(self) -> Iterator[Any]:
        """Connect without Telethon's context-manager start() prompt.

        Telethon's ``with TelegramClient(...)`` calls ``start()``, which may
        prompt for a phone on unauthenticated sessions. The CLI owns phone/code
        explicitly, so use connect/disconnect instead.

        Telethon opens and writes the session itself: store.managed hands it the file for
        the life of the client, and leaves it 0600.
        """
        self._config = self._load_config()   # before managed: a missing config touches nothing
        self._adopt_legacy_session()
        with store.managed(self.session_sqlite_file, place="secrets.local", library="telethon",
                           dest=self._dest):
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
        self._adopt_legacy_session()
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
        try:
            with self._connected_client() as client:
                sent = client.send_code_request(phone)
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        view = _sent_code_view(sent)
        self._save_auth_state(phone, _get_attr(sent, "phone_code_hash", None))
        return {"phone": phone, **view}

    def _save_auth_state(self, phone: str, phone_code_hash: str | None) -> None:
        state = {"phone": phone, "phone_code_hash": phone_code_hash}
        if self.config_dir is None:
            secrets.write_json("telegram.auth-state", state)
            return
        store.replace(self.auth_state_file, json.dumps(state, indent=2), place="secrets.local",
                      dest=True, keys=tuple(state))

    def resend_code(self) -> dict[str, Any]:
        """Ask Telegram to deliver the pending code by its next channel (auth.resendCode)."""
        from h2t_ops.core.errors import UsageError

        state = self._read_auth_state()
        if state is None:
            raise UsageError("No pending code request.",
                             hint="Run h2t-ops telegram auth request-code --phone +... first.")
        try:
            from telethon.errors import SendCodeUnavailableError
            from telethon.tl.functions.auth import ResendCodeRequest
        except ImportError as exc:
            raise ConfigError("Telethon not installed.",
                              hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.") from exc
        try:
            with self._connected_client() as client:
                sent = client(ResendCodeRequest(state["phone"], state["phone_code_hash"]))
        except SendCodeUnavailableError as exc:
            raise AuthError("Telegram has no other channel left for this code.",
                            hint=_QR_HINT) from exc
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        view = _sent_code_view(sent)
        self._save_auth_state(state["phone"], _get_attr(sent, "phone_code_hash", None))
        return {"phone": state["phone"], **view}

    def qr_login(
        self,
        *,
        render: Any,
        password_prompt: Any = None,
        attempts: int = 5,
        wait_s: int = 60,
    ) -> dict[str, Any]:
        """Log in by scanning a QR on a device already logged in — no code is sent.

        `render(url)` shows each QR; it is called again with a fresh token after every
        timeout. `password_prompt()` returns the 2FA password when the account has one.
        """
        password_needed = self._session_password_error_class()
        try:
            with self._connected_client() as client:
                if client.is_user_authorized():
                    return {"authorized": True, "already": True, "user": self._user_row(client.get_me())}
                qr = client.qr_login()
                for _ in range(attempts):
                    render(qr.url)
                    try:
                        client.loop.run_until_complete(qr.wait(wait_s))
                        break
                    except TimeoutError:
                        client.loop.run_until_complete(qr.recreate())
                    except password_needed:
                        if password_prompt is None:
                            raise AuthError("Telegram account requires its 2FA password.",
                                            hint="Run h2t-ops telegram auth qr in a terminal.") from None
                        client.sign_in(password=password_prompt())
                        break
                if not client.is_user_authorized():
                    raise AuthError(f"The QR was not scanned within {attempts} tries.",
                                    hint="Run h2t-ops telegram auth qr again; scan with "
                                         "Settings → Devices → Link Desktop Device.")
                user = self._user_row(client.get_me())
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return {"authorized": True, "user": user}

    def complete_auth(
        self,
        phone: str,
        code: str | None = None,
        password: str | None = None,
        password_prompt: Any = None,
    ) -> dict[str, Any]:
        state: dict[str, Any] = self._read_auth_state() or {}
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
                    if not password and password_prompt is not None:
                        password = password_prompt()
                    if not password:
                        raise AuthError(
                            "Telegram account requires 2FA password.",
                            hint="Run auth complete --phone +... --password (no value: it asks, hidden).",
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
            "media": _media_info(msg),
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

    def _entity_candidates(self, entity: Any) -> list[Any]:
        """Peer forms to try, most specific first.

        Prefer the InputPeer cached in the SQLite session: get_entity() on an
        uncached numeric peer triggers GetContactsRequest and a FloodWait.
        """
        if isinstance(entity, str) and entity.lstrip("-").isdigit():
            self._adopt_legacy_session()
            input_peer = _input_peer_from_sqlite(self.session_sqlite_file, int(entity), self._dest)
            if input_peer is not None:
                return [input_peer]
        return _peer_candidates(entity) if isinstance(entity, str) else [entity]

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

            cutoff = datetime.now(UTC) - timedelta(days=days)
        candidates: list[Any] = self._entity_candidates(entity)
        try:
            with self._connected_client() as client:
                rows = []
                last_exc: Exception | None = None
                for candidate in candidates:
                    # A candidate can yield rows and then fail mid-iteration, so
                    # collect per candidate and keep only a run that completed.
                    found: list[dict[str, Any]] = []
                    try:
                        for msg in client.iter_messages(candidate, limit=limit):
                            msg_date = _get_attr(msg, "date")
                            if cutoff is not None and isinstance(msg_date, datetime) and msg_date < cutoff:
                                continue
                            found.append(self._message_row(msg))
                    except ValueError as exc:
                        last_exc = exc
                        continue
                    last_exc = None
                    rows.extend(found)
                    break
                if last_exc is not None:
                    raise _peer_unresolved_error(entity, last_exc) from last_exc
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

            cutoff = datetime.now(UTC) - timedelta(days=days)
        try:
            with self._connected_client() as client:
                me = client.get_me()
                username = (_get_attr(me, "username", "") or "").lower()
                needle = f"@{username}" if username else ""
                rows: list[dict[str, Any]] = []
                for chat_id in chat_ids:
                    last_exc: Exception | None = None
                    for candidate in self._entity_candidates(chat_id):
                        # A candidate can yield rows and then fail mid-iteration, so
                        # collect per candidate and keep only a run that completed.
                        found: list[dict[str, Any]] = []
                        try:
                            for msg in client.iter_messages(candidate, limit=limit):
                                msg_date = _get_attr(msg, "date")
                                if cutoff is not None and isinstance(msg_date, datetime) and msg_date < cutoff:
                                    continue
                                text = (_get_attr(msg, "text", "") or "").lower()
                                if needle and needle in text:
                                    found.append(self._message_row(msg))
                        except ValueError as exc:
                            last_exc = exc
                            continue
                        last_exc = None
                        rows.extend(found)
                        break
                    if last_exc is not None:
                        raise _peer_unresolved_error(chat_id, last_exc) from last_exc
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
        # Resolve the peer as reads do: a numeric id given as text would reach
        # Telethon as a string and be looked up as a username.
        candidates: list[Any] = self._entity_candidates(entity)
        msg: Any = None
        try:
            with self._connected_client() as client:
                last_exc: Exception | None = None
                for candidate in candidates:
                    try:
                        msg = client.send_file(candidate, path, caption=caption)
                        last_exc = None
                        break
                    except ValueError as exc:
                        last_exc = exc
                if last_exc is not None:
                    raise _peer_unresolved_error(entity, last_exc) from last_exc
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

    def download_media(
        self,
        entity: str,
        message_id: int,
        *,
        out_dir: str | None = None,
    ) -> dict[str, Any]:
        """Download the attachment of a single message to a local directory.

        Mirrors list_messages' peer resolution (SQLite InputPeer first) to avoid
        get_entity() → FloodWait on uncached numeric peers. Fails loud via
        ProviderError when the message carries no downloadable media.

        The directory is --out or the inbox place (R28); the adapter picks the file name and
        Telethon writes into a store.writer handle, created and never over a file already
        there — that one keeps its bytes and the new file takes -2, -3 (R47).
        """
        inbox, defaulted = paths.place_or_default("inbox")
        if out_dir:
            dest = paths.expand_user_dest(out_dir)
            named = os.path.realpath(dest) != os.path.realpath(inbox)
        else:
            dest, named = inbox, False
        place = "inbox" if named or not defaulted else "data"
        candidates: list[Any] = self._entity_candidates(entity)
        path: Path | None = None
        msg: Any = None
        try:
            with self._connected_client() as client:
                last_exc: Exception | None = None
                for candidate in candidates:
                    try:
                        msg = client.get_messages(candidate, ids=message_id)
                        last_exc = None
                        break
                    except ValueError as exc:
                        last_exc = exc
                if last_exc is not None:
                    raise _peer_unresolved_error(entity, last_exc) from last_exc
                if msg is None or _get_attr(msg, "media", None) is None:
                    raise ProviderError(
                        f"message {message_id} in {entity} has no downloadable media"
                    )
                first = dest / _media_filename(msg, entity, message_id)
                if Path(os.path.realpath(first)).parent != Path(os.path.realpath(dest)):
                    raise store.WriteRefused(f"attachment name {first.name!r} leaves {dest}",
                                             hint="the file is written only directly into that directory")
                for target in store.unique_name(first):
                    if target.exists():
                        continue
                    try:
                        with store.writer(target, place=place, dest=named, exclusive=True) as fh:
                            if client.download_media(msg, file=fh) is None:
                                raise ProviderError(
                                    f"failed to download media from message {message_id} in {entity}"
                                )
                    except store.AlreadyExists:
                        continue            # taken between the check and the link: next name
                    path = target
                    break
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        if not out_dir and defaulted:
            print(f"saved to {path} (inbox not set: h2t-ops paths set inbox <path>)", file=sys.stderr)
        return {
            "entity": entity,
            "message_id": message_id,
            "path": str(path),
            "filename": path.name,
            "size": path.stat().st_size,
            "media": _media_info(msg),
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
        # The 3.x marker counts too (checked, never written), so an upgrade does not rerun it.
        markers = [self.dialogs_bootstrap_file]
        if not self._dest:
            markers.append(paths.legacy("telegram") / "dialogs_bootstrapped")
        found = next((m for m in markers if m.exists()), None)
        if found is not None and not force:
            return {
                "refreshed": False,
                "count": 0,
                "timestamp_path": str(found),
            }
        try:
            with self._connected_client() as client:
                count = sum(1 for _ in client.iter_dialogs(limit=None))
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        store.replace(self.dialogs_bootstrap_file, str(datetime.now(UTC).timestamp()),
                      place="state", dest=self._dest)
        return {
            "refreshed": True,
            "count": count,
            "timestamp_path": str(self.dialogs_bootstrap_file),
        }

    def search_channels(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search public channels/users by keyword via contacts.SearchRequest.

        Fails loud on FloodWait — raises ProviderError with wait_seconds in details.
        participants_count is None when Telegram returns a partial Channel object.
        is_channel means broadcast channel (not megagroup); is_megagroup covers supergroups.
        """
        search_req_cls = self._search_request_class()
        flood_wait_cls = self._flood_wait_error_class()
        try:
            with self._connected_client() as client:
                try:
                    result = client(search_req_cls(q=query, limit=limit))
                except flood_wait_cls as exc:
                    wait = getattr(exc, "seconds", 0)
                    raise ProviderError(
                        f"FLOOD_WAIT: Telegram requires {wait}s wait before next search",
                        details={"wait_seconds": wait},
                    ) from exc
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc

        rows: list[dict[str, Any]] = []
        for chat in (_get_attr(result, "chats", []) or []):
            is_mega = bool(_get_attr(chat, "megagroup", False))
            rows.append({
                "type": "group" if is_mega else "channel",
                "id": _get_attr(chat, "id"),
                "username": _get_attr(chat, "username"),
                "title": _get_attr(chat, "title", "") or "",
                "participants_count": _get_attr(chat, "participants_count"),  # None = unknown
                "is_channel": bool(_get_attr(chat, "broadcast", False)),
                "is_megagroup": is_mega,
                "verified": bool(_get_attr(chat, "verified", False)),
            })
        for user in (_get_attr(result, "users", []) or []):
            first = _get_attr(user, "first_name", "") or ""
            last = _get_attr(user, "last_name", "") or ""
            rows.append({
                "type": "user",
                "id": _get_attr(user, "id"),
                "username": _get_attr(user, "username"),
                "title": " ".join(p for p in (first, last) if p),
                "participants_count": None,  # users never have participants_count
                "is_channel": False,
                "is_megagroup": False,
                "verified": bool(_get_attr(user, "verified", False)),
            })
        return rows
