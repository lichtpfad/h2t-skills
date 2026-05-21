"""TelegramClientAdapter - Telethon provider adapter for #135.

Telethon imports are lazy so registry/help paths stay lightweight.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

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


class TelegramClientAdapter:
    """Pure Telegram/Telethon adapter."""

    def __init__(self, *, config_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self.session_base = self.config_dir / "session"
        self.auth_state_file = self.config_dir / "auth_state.json"

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

    def _client(self):
        cfg = self._load_config()
        client_cls = self._telegram_client_class()
        return client_cls(self.session_file, cfg["api_id"], cfg["api_hash"])

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
            with self._client() as client:
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
            with self._client() as client:
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
            with self._client() as client:
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
