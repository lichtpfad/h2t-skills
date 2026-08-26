---
title: "h2t-ops Telegram Parity Implementation Plan"
status: "draft"
date: "2026-05-21"
milestone: ""
---
# h2t-ops Telegram Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `h2t_ops.connectors.telegram` runtime for Telegram auth/session, dialogs, folders, messages, saved-messages, mentions, and bootstrap, while preserving existing Telegram workflow commands outside the connector.

**Architecture:** Build the standard three-file connector (`__init__.py`, `client.py`, `commands.py`) used by Gmail/Calendar/Drive/MeetGeek. The connector owns only Telethon provider I/O and local Telethon session state; Gemini, Notion, DOR/POS storage, `chats.yaml`, and portable workflow scripts stay outside #135. Legacy `telegram_cli.py` remains available for existing `digest/tasks/research/students/sync` workflows.

**Tech Stack:** Python 3.11, argparse, Telethon (`telethon>=1.36,<1.43`), pytest, h2t_ops typed errors/envelopes, existing h2t-ops lazy registry.

---

## Inputs

| Source | Path / Issue | Use |
|---|---|---|
| Design | `docs/superpowers/specs/2026-05-21-h2t-ops-telegram-parity-design.md` | Source of truth for scope and boundaries |
| Roadmap | `docs/h2t-ops-roadmap.md` | M3 connector ordering |
| Issue | `#135` | Telegram connector migration |
| Issue | `#121` | Telethon session schema mismatch hard non-regression |
| Legacy code | `plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` | Behavior reference |
| Legacy docs | `plugins/h2t-ops/skills/telegram/SKILL.md` | Skill rewrite target |
| Connector pattern | `h2t_ops/connectors/{drive,meetgeek}/` | Code/test style |

---

## File Map

| File | Action | Owner task | Responsibility |
|---|---|---|---|
| `pyproject.toml` | Modify | T1 | Add conservative Telethon dependency |
| `uv.lock` | Modify if `uv lock` changes it | T1 | Lock dependency graph |
| `h2t_ops/connectors/telegram/__init__.py` | Create | T3 | ConnectorSpec registration |
| `h2t_ops/connectors/telegram/client.py` | Create | T1/T2 | Telethon config, auth/session, provider reads |
| `h2t_ops/connectors/telegram/commands.py` | Create | T3 | argparse surface + lazy client dispatch |
| `h2t_ops/cli.py` | Modify | T3 | Add `"telegram"` to `_MIGRATED` |
| `tests/connectors/telegram/__init__.py` | Create | T1 | Test package marker |
| `tests/connectors/telegram/test_client.py` | Create | T1/T2 | Client unit tests with Telethon fakes |
| `tests/connectors/telegram/test_commands.py` | Create | T3 | Command parser/dispatch/lazy tests |
| `plugins/h2t-ops/skills/telegram/SKILL.md` | Modify | T4 | Delegate provider reads, preserve legacy workflows |

Do not modify `plugins/h2t/skills/telegram/**` in #135.

---

## Hard Constraints

1. `h2t_ops/connectors/telegram/**` must not import or reference `google.genai`.
2. `h2t_ops/connectors/telegram/**` must not import Notion clients or execute Notion writes.
3. `h2t_ops/connectors/telegram/**` must not reference `DOR_ROOT`, `VAULT_ROOT`, `vault`, `lake`, `pos.db`, `dor.db`, or `context/telegram`.
4. `h2t_ops/connectors/telegram/**` must not read or write `~/.config/telegram/chats.yaml`.
5. Connector live smoke is read-only except explicit Telethon auth/session/bootstrap state.
6. Do not add `cleanup --archive` to the connector in #135.
7. Do not remove or break legacy workflow commands: `saved`, `digest`, `tasks`, `research`, `students`, `sync`, `scan-chats`, `cleanup`.
8. Do not silently delete a Telethon session file.
9. `SESSION_INCOMPATIBLE` must appear in `error.message` for session schema failures.
10. `h2t-ops --help`, `h2t-ops connectors`, and lazy registry checks must not import Telethon.
11. No broad refactors outside the file map.
12. Each commit-bearing task stages only its listed files.

---

## Shared Implementation Details

### Telethon Dependency

Use the conservative dependency from #121:

```toml
"telethon>=1.36,<1.43",
```

If `uv lock` is unavailable or network fails, commit `pyproject.toml` only and record the lock update as a closure concern. Do not use `pip install`.

### Error Mapping

Use existing typed errors from `h2t_ops.core.errors`.

Session mismatch helper contract:

```python
def _session_incompatible_error(exc: BaseException) -> AuthError:
    return AuthError(
        f"SESSION_INCOMPATIBLE: Telethon session file is incompatible with this Telethon version: {exc}",
        hint=(
            "Move ~/.config/telegram/session aside, then run "
            "h2t-ops telegram auth request-code --phone +..."
        ),
    )
```

Catch at Telethon connect/read boundaries:

```python
except (ValueError, sqlite3.OperationalError) as exc:
    raise _session_incompatible_error(exc) from exc
```

### Output Rows

Dialog row:

```python
{
    "id": int_or_str,
    "title": title,
    "username": username_or_none,
    "kind": "user|group|channel|bot|unknown",
    "unread_count": integer,
    "is_archived": boolean,
}
```

Message row:

```python
{
    "id": int_or_str,
    "chat_id": int_or_str_or_none,
    "date": iso_datetime_or_empty,
    "sender_id": int_or_str_or_none,
    "sender_name": string_or_empty,
    "text": string_or_empty,
    "urls": list_of_strings,
    "reply_to_msg_id": int_or_str_or_none,
}
```

---

## Per-Task Verification Gates

Run after each commit-bearing task unless the task says otherwise:

```powershell
git status --short --branch
uv run pytest tests/connectors/telegram -q
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected after T1/T2: Telegram tests may be partial but all existing tests must pass. Expected after T3/T4: all listed commands pass.

Boundary grep after T1+:

```powershell
Select-String -Path h2t_ops/connectors/telegram/*.py -Pattern "google\.genai|from google|notion|DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/telegram|chats\.yaml"
```

Expected: no matches. If a match appears in a test string or comment, remove/reword it; the guard is intentionally strict.

---

## T0 - Baseline And File-State Verification

**Files:**
- Read only

- [ ] **Step 1: Confirm branch and unrelated dirty tree**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## main...origin/main
```

There may be unrelated dirty files already present. Do not stage or modify them.

- [ ] **Step 2: Confirm Telegram connector does not already exist**

Run:

```powershell
Test-Path h2t_ops/connectors/telegram
Test-Path tests/connectors/telegram
```

Expected:

```text
False
False
```

If either path exists, stop and inspect it before continuing.

- [ ] **Step 3: Confirm legacy Telegram commands are present**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py -Pattern "sub.add_parser\('saved'|sub.add_parser\('digest'|sub.add_parser\('tasks'|sub.add_parser\('research'|sub.add_parser\('students'|sub.add_parser\('sync'|sub.add_parser\('cleanup'"
```

Expected: matches for all seven legacy commands.

- [ ] **Step 4: Run current regression baseline**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected: all tests pass and lazy-registry prints OK. If the environment cannot run because dependencies are missing, capture the exact error in T5 closure.

- [ ] **Step 5: Do not commit T0**

Expected: no files changed by T0.

---

## T1 - Telegram Dependency, Config, Auth, And Session Errors

**Files:**
- Modify: `pyproject.toml`
- Modify if lock changes: `uv.lock`
- Create: `h2t_ops/connectors/telegram/client.py`
- Create: `tests/connectors/telegram/__init__.py`
- Create/modify: `tests/connectors/telegram/test_client.py`

- [ ] **Step 1: Add failing client tests for config/dependency/session/auth**

Create `tests/connectors/telegram/__init__.py` as an empty file.

Create `tests/connectors/telegram/test_client.py` with these tests:

```python
"""Tests for h2t_ops.connectors.telegram.client."""
from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import AuthError, ConfigError


def test_module_has_no_module_level_telethon_import():
    src = Path("h2t_ops/connectors/telegram/client.py").read_text(encoding="utf-8")
    forbidden = ("import telethon", "from telethon")
    top_level = [ln for ln in src.splitlines() if ln and not ln.startswith((" ", "\t"))]
    assert not any(ln.startswith(forbidden) for ln in top_level)


def test_missing_config_raises_configerror(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._load_config()
    assert "config.json" in str(ei.value)
    assert "auth request-code" in (ei.value.hint or "")


def test_invalid_config_missing_api_hash_raises_configerror(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 123}), encoding="utf-8")
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._load_config()
    assert "api_id" in str(ei.value)
    assert "api_hash" in str(ei.value)


def test_missing_telethon_dependency_raises_configerror(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.sync":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._telegram_client_class()
    assert "Telethon not installed" in str(ei.value)
    assert "telethon" in (ei.value.hint or "")


@pytest.mark.parametrize("exc", [ValueError("too many values to unpack"), sqlite3.OperationalError("no column")])
def test_session_incompatible_errors_include_marker(exc):
    from h2t_ops.connectors.telegram.client import _session_incompatible_error

    err = _session_incompatible_error(exc)
    assert isinstance(err, AuthError)
    assert "SESSION_INCOMPATIBLE" in str(err)
    assert "auth request-code" in (err.hint or "")


def test_auth_status_without_session_reports_configured_not_authorized(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    client = TelegramClientAdapter(config_dir=tmp_path)
    assert client.auth_status() == {
        "configured": True,
        "session_exists": False,
        "authorized": False,
        "user": None,
    }


def test_auth_status_maps_authorized_user(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}),
        encoding="utf-8",
    )
    (tmp_path / "session.session").write_text("fake", encoding="utf-8")

    class FakeClient:
        def __init__(self, session, api_id, api_hash):
            self.session = session
            self.api_id = api_id
            self.api_hash = api_hash

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def is_user_authorized(self):
            return True

        def get_me(self):
            return SimpleNamespace(id=7, username="stan", first_name="Stan", last_name="G")

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_telegram_client_class", lambda self: FakeClient)
    client = tmod.TelegramClientAdapter(config_dir=tmp_path)
    status = client.auth_status()
    assert status["configured"] is True
    assert status["session_exists"] is True
    assert status["authorized"] is True
    assert status["user"]["username"] == "stan"
```

- [ ] **Step 2: Run tests and verify they fail because connector is missing**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_client.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.telegram'`.

- [ ] **Step 3: Add Telethon dependency**

Modify `pyproject.toml` dependency list:

```toml
  "google-auth-oauthlib>=1.0",
  "telethon>=1.36,<1.43",
]
```

Run if available:

```powershell
uv lock
```

Expected: `uv.lock` updates cleanly. If network or lock resolution fails, keep only the `pyproject.toml` change and record the failure in T5.

- [ ] **Step 4: Create minimal Telegram client module**

Create `h2t_ops/connectors/telegram/client.py`:

```python
"""TelegramClientAdapter - Telethon provider adapter for #135.

Telethon imports are lazy so registry/help paths stay lightweight.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import AuthError, ConfigError, ProviderError


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


def _iso(dt: Any) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class TelegramClientAdapter:
    """Pure Telegram/Telethon adapter.

    The adapter owns provider I/O and Telethon session state only.
    """

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
        missing = [k for k in ("api_id", "api_hash") if not data.get(k)]
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

    def complete_auth(self, phone: str, code: str | None = None,
                      password: str | None = None) -> dict[str, Any]:
        state = {}
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
                            "Telegram auth complete requires --code or --password.",
                            hint="Run auth complete --phone +... --code CODE, or add --password for 2FA.",
                        )
                except password_needed:
                    if not password:
                        raise AuthError(
                            "Telegram account requires 2FA password.",
                            hint="Re-run auth complete with --password, or use the future password-stdin flow.",
                        )
                    client.sign_in(password=password)
                user = self._user_row(client.get_me())
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        self.auth_state_file.unlink(missing_ok=True)
        return {"authorized": True, "user": user}

    def _user_row(self, user: Any) -> dict[str, Any]:
        if user is None:
            return {}
        return {
            "id": _get_attr(user, "id"),
            "username": _get_attr(user, "username"),
            "first_name": _get_attr(user, "first_name") or "",
            "last_name": _get_attr(user, "last_name") or "",
        }
```

- [ ] **Step 5: Run T1 tests**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_client.py -q
```

Expected: PASS for T1 tests. If tests that require read methods fail because they are not yet added, remove those tests from T1 and add them in T2.

- [ ] **Step 6: Run boundary grep**

Run:

```powershell
Select-String -Path h2t_ops/connectors/telegram/*.py -Pattern "google\.genai|from google|notion|DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/telegram|chats\.yaml"
```

Expected: no matches.

- [ ] **Step 7: Run broader regression**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected: all tests pass; lazy-registry OK.

- [ ] **Step 8: Commit T1**

Run:

```powershell
git add pyproject.toml uv.lock h2t_ops/connectors/telegram/client.py tests/connectors/telegram/__init__.py tests/connectors/telegram/test_client.py
git commit -m "feat(telegram): add Telethon auth substrate (#135)"
```

If `uv.lock` did not change, omit it from `git add`.

---

## T2 - Telegram Read Surface

**Files:**
- Modify: `h2t_ops/connectors/telegram/client.py`
- Modify: `tests/connectors/telegram/test_client.py`

- [ ] **Step 1: Add failing tests for dialogs/messages/saved/folders/mentions/bootstrap**

Append to `tests/connectors/telegram/test_client.py`:

```python
class _CtxClient:
    def __init__(self, inner):
        self.inner = inner

    def __enter__(self):
        return self.inner

    def __exit__(self, exc_type, exc, tb):
        return False


def test_list_dialogs_maps_dialog_rows(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    dialog = SimpleNamespace(
        entity=SimpleNamespace(id=11, username="chatname", bot=False, megagroup=True, broadcast=False),
        name="Work Chat",
        title="Work Chat",
        unread_count=3,
        archived=False,
    )

    class FakeInner:
        def iter_dialogs(self, limit=None):
            assert limit == 5
            return [dialog]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_dialogs(limit=5)
    assert rows == [{
        "id": 11,
        "title": "Work Chat",
        "username": "chatname",
        "kind": "group",
        "unread_count": 3,
        "is_archived": False,
    }]


def test_list_messages_maps_rows_and_urls(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class UrlEntity:
        offset = 6
        length = 19
        url = None

    msg = SimpleNamespace(
        id=5,
        chat_id=99,
        date=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        sender_id=7,
        sender=SimpleNamespace(first_name="Ada", last_name="L"),
        text="link: https://example.com",
        entities=[UrlEntity()],
        reply_to_msg_id=None,
    )

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            assert entity == "chat"
            assert limit == 10
            return [msg]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_messages("chat", limit=10)
    assert rows[0]["id"] == 5
    assert rows[0]["sender_name"] == "Ada L"
    assert rows[0]["text"] == "link: https://example.com"
    assert rows[0]["urls"] == ["https://example.com"]


def test_list_saved_messages_uses_me_entity(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    seen = {}

    class FakeInner:
        def iter_messages(self, entity, limit=None):
            seen["entity"] = entity
            return []

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_saved_messages(limit=3)
    assert rows == []
    assert seen["entity"] == "me"


def test_list_mentions_filters_messages_with_me_marker(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    msg_hit = SimpleNamespace(
        id=1, chat_id=10, date=None, sender_id=None, sender=None,
        text="hello @stan", entities=[], reply_to_msg_id=None,
    )
    msg_miss = SimpleNamespace(
        id=2, chat_id=10, date=None, sender_id=None, sender=None,
        text="hello", entities=[], reply_to_msg_id=None,
    )

    class FakeInner:
        def get_me(self):
            return SimpleNamespace(username="stan", id=7, first_name="Stan", last_name="")

        def iter_messages(self, entity, limit=None):
            return [msg_hit, msg_miss]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_mentions(["10"], limit=50)
    assert [r["id"] for r in rows] == [1]


def test_list_folders_uses_raw_dialog_filters_request(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class Filter:
        id = 2
        title = "Work"
        include_peers = [SimpleNamespace(channel_id=1), SimpleNamespace(chat_id=2)]

    class FakeInner:
        def __call__(self, request):
            return [Filter()]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_dialog_filters_request_class", lambda self: object)
    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    rows = tmod.TelegramClientAdapter(config_dir=tmp_path).list_folders()
    assert rows == [{"id": 2, "title": "Work", "peer_ids": [1, 2]}]


def test_bootstrap_dialogs_writes_timestamp_without_chats_yaml(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")

    class FakeInner:
        def iter_dialogs(self, limit=None):
            return [SimpleNamespace(entity=SimpleNamespace(id=1))]

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_client", lambda self: _CtxClient(FakeInner()))
    result = tmod.TelegramClientAdapter(config_dir=tmp_path).bootstrap_dialogs(force=True)
    assert result["count"] == 1
    assert (tmp_path / "dialogs_bootstrapped").exists()
    assert not (tmp_path / "chats.yaml").exists()
```

- [ ] **Step 2: Run tests and verify they fail on missing methods**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_client.py -q
```

Expected: FAIL with `AttributeError` for missing `list_dialogs`, `list_messages`, `list_saved_messages`, `list_mentions`, `list_folders`, or `bootstrap_dialogs`.

- [ ] **Step 3: Implement row mapping and read methods**

Append these helpers and methods to `h2t_ops/connectors/telegram/client.py` inside or near `TelegramClientAdapter`. Keep Telethon-specific imports lazy.

```python
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
            value = text[offset:offset + length]
            if value.startswith(("http://", "https://")):
                urls.append(value)
    return urls
```

Add methods to `TelegramClientAdapter`:

```python
    def _dialog_filters_request_class(self):
        try:
            from telethon.tl.functions.messages import GetDialogFiltersRequest
        except ImportError as exc:
            raise ConfigError(
                "Telethon not installed.",
                hint="Install h2t-ops dependencies with telethon>=1.36,<1.43.",
            ) from exc
        return GetDialogFiltersRequest

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

    def list_dialogs(self, *, limit: int | None = None,
                     kind: str | None = None) -> list[dict[str, Any]]:
        try:
            with self._client() as client:
                rows = [self._dialog_row(d) for d in client.iter_dialogs(limit=limit)]
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        return rows

    def list_messages(self, entity: str, *, limit: int | None = 200,
                      days: int | None = None) -> list[dict[str, Any]]:
        cutoff = None
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            with self._client() as client:
                rows = []
                for msg in client.iter_messages(entity, limit=limit):
                    msg_date = _get_attr(msg, "date")
                    if cutoff is not None and isinstance(msg_date, datetime) and msg_date < cutoff:
                        continue
                    rows.append(self._message_row(msg))
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        return rows

    def list_saved_messages(self, *, limit: int | None = 200,
                            days: int | None = None) -> list[dict[str, Any]]:
        return self.list_messages("me", limit=limit, days=days)

    def list_mentions(self, chat_ids: list[str], *, days: int | None = None,
                      limit: int | None = 500) -> list[dict[str, Any]]:
        cutoff = None
        if days is not None:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        try:
            with self._client() as client:
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
            with self._client() as client:
                filters = client(request_cls())
        except (ValueError, sqlite3.OperationalError) as exc:
            raise _session_incompatible_error(exc) from exc
        rows = []
        for item in filters or []:
            peers = []
            for peer in _get_attr(item, "include_peers", []) or []:
                peer_id = (
                    _get_attr(peer, "channel_id", None)
                    or _get_attr(peer, "chat_id", None)
                    or _get_attr(peer, "user_id", None)
                )
                if peer_id is not None:
                    peers.append(peer_id)
            rows.append({"id": _get_attr(item, "id"), "title": _get_attr(item, "title", ""), "peer_ids": peers})
        return rows

    def bootstrap_dialogs(self, *, force: bool = False) -> dict[str, Any]:
        if self.dialogs_bootstrap_file.exists() and not force:
            return {
                "refreshed": False,
                "count": 0,
                "timestamp_path": str(self.dialogs_bootstrap_file),
            }
        try:
            with self._client() as client:
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
```

- [ ] **Step 4: Run T2 tests**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Run boundary and broader regression**

Run:

```powershell
Select-String -Path h2t_ops/connectors/telegram/*.py -Pattern "google\.genai|from google|notion|DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/telegram|chats\.yaml"
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected: grep no matches; tests pass; lazy-registry OK.

- [ ] **Step 6: Commit T2**

Run:

```powershell
git add h2t_ops/connectors/telegram/client.py tests/connectors/telegram/test_client.py
git commit -m "feat(telegram): add read-only Telethon surface (#135)"
```

---

## T3 - Commands, Registry, And CLI Routing

**Files:**
- Create: `h2t_ops/connectors/telegram/__init__.py`
- Create: `h2t_ops/connectors/telegram/commands.py`
- Modify: `h2t_ops/cli.py`
- Create/modify: `tests/connectors/telegram/test_commands.py`

- [ ] **Step 1: Add failing command tests**

Create `tests/connectors/telegram/test_commands.py`:

```python
"""Tests for h2t_ops.connectors.telegram.commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import AuthError


def _build_parser():
    from h2t_ops.connectors.telegram.commands import register

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_register_creates_subparsers_for_telegram_verbs():
    parser = _build_parser()
    cases = [
        ["telegram", "auth", "status"],
        ["telegram", "auth", "request-code", "--phone", "+100"],
        ["telegram", "auth", "complete", "--phone", "+100", "--code", "12345"],
        ["telegram", "dialogs"],
        ["telegram", "folders"],
        ["telegram", "messages", "chat"],
        ["telegram", "saved-messages"],
        ["telegram", "mentions", "--chat-id", "1"],
        ["telegram", "bootstrap"],
    ]
    for argv in cases:
        ns = parser.parse_args(argv)
        assert ns.telegram_cmd is not None


def test_json_flag_available_on_all_leaf_verbs():
    parser = _build_parser()
    cases = [
        ["telegram", "auth", "status", "--json"],
        ["telegram", "auth", "request-code", "--phone", "+100", "--json"],
        ["telegram", "auth", "complete", "--phone", "+100", "--code", "12345", "--json"],
        ["telegram", "dialogs", "--json"],
        ["telegram", "folders", "--json"],
        ["telegram", "messages", "chat", "--json"],
        ["telegram", "saved-messages", "--json"],
        ["telegram", "mentions", "--chat-id", "1", "--json"],
        ["telegram", "bootstrap", "--json"],
    ]
    for argv in cases:
        ns = parser.parse_args(argv)
        assert ns.as_json is True


def test_commands_module_does_not_import_client_at_module_scope():
    src = Path("h2t_ops/connectors/telegram/commands.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if "telegram.client" in stripped or "TelegramClientAdapter" in stripped:
            assert line[0] == " ", (
                f"line {i}: TelegramClientAdapter must not be imported at module scope: {line!r}"
            )


def test_saved_messages_dispatch_is_distinct_from_legacy_saved(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    class Stub:
        def list_saved_messages(self, limit=None, days=None):
            return [{"id": 1, "text": "saved"}]

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(telegram_cmd="saved-messages", limit=5, days=None, as_json=False, fmt="human")
    result = cmds.run(args)
    assert result == {"rows": [{"id": 1, "text": "saved"}], "count": 1}


def test_mentions_requires_explicit_chat_id():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["telegram", "mentions"])


def test_error_envelope_contains_session_incompatible(monkeypatch, capsys):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds
    from h2t_ops.core.output import emit

    class Stub:
        def auth_status(self):
            raise AuthError("SESSION_INCOMPATIBLE: bad session", hint="recover")

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(telegram_cmd="auth-status", as_json=True, fmt="human")
    try:
        result = cmds.run(args)
    except BaseException as exc:
        rc = emit("telegram", exc=exc, fmt="json")
    else:
        rc = emit("telegram", result=result, fmt="json")
    assert rc == 4
    err = json.loads(capsys.readouterr().err)
    assert "SESSION_INCOMPATIBLE" in err["error"]["message"]


def test_cli_migrated_contains_telegram():
    import h2t_ops.cli as cli

    assert "telegram" in cli._MIGRATED
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_commands.py -q
```

Expected: FAIL because `commands.py` and `__init__.py` do not exist.

- [ ] **Step 3: Create connector registry file**

Create `h2t_ops/connectors/telegram/__init__.py`:

```python
"""Telegram connector - registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register

CONNECTOR = ConnectorSpec(
    name="telegram",
    help="Work with Telegram dialogs and messages",
    client="h2t_ops.connectors.telegram.client:TelegramClientAdapter",
    register=register,
)
```

- [ ] **Step 4: Create command adapter**

Create `h2t_ops/connectors/telegram/commands.py`:

```python
"""Telegram CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

from typing import Any

PROVIDER = "telegram"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("telegram", help="Work with Telegram dialogs and messages")
    cmds = p.add_subparsers(dest="telegram_cmd", required=True)

    def add_json(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["human", "md"], default="human",
                        help="human = concise default, md = markdown/detail output")

    auth = cmds.add_parser("auth", help="Telegram auth/session operations")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)

    auth_status = auth_sub.add_parser("status", help="Check auth/session state")
    add_json(auth_status)
    auth_status.set_defaults(telegram_cmd="auth-status")

    auth_request = auth_sub.add_parser("request-code", help="Request Telegram login code")
    auth_request.add_argument("--phone", required=True)
    add_json(auth_request)
    auth_request.set_defaults(telegram_cmd="auth-request-code")

    auth_complete = auth_sub.add_parser("complete", help="Complete Telegram login")
    auth_complete.add_argument("--phone", required=True)
    auth_complete.add_argument("--code")
    auth_complete.add_argument("--password")
    add_json(auth_complete)
    auth_complete.set_defaults(telegram_cmd="auth-complete")

    dialogs = cmds.add_parser("dialogs", help="List Telegram dialogs")
    dialogs.add_argument("--limit", type=int, default=50)
    dialogs.add_argument("--kind", choices=["user", "group", "channel", "bot", "unknown"])
    add_json(dialogs)

    folders = cmds.add_parser("folders", help="List Telegram dialog folders")
    add_json(folders)

    messages = cmds.add_parser("messages", help="Read messages from an entity")
    messages.add_argument("entity")
    messages.add_argument("--days", type=int)
    messages.add_argument("--limit", type=int, default=200)
    add_json(messages)

    saved = cmds.add_parser("saved-messages", help="Read raw Telegram Saved Messages")
    saved.add_argument("--days", type=int)
    saved.add_argument("--limit", type=int, default=200)
    add_json(saved)

    mentions = cmds.add_parser("mentions", help="Read explicit chats for @mentions")
    mentions.add_argument("--chat-id", dest="chat_ids", action="append", required=True)
    mentions.add_argument("--days", type=int)
    mentions.add_argument("--limit", type=int, default=500)
    add_json(mentions)

    bootstrap = cmds.add_parser("bootstrap", help="Warm Telethon entity cache")
    bootstrap.add_argument("--force", action="store_true")
    add_json(bootstrap)

    p.set_defaults(_handler=run)


def _rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rows": rows, "count": len(rows)}


def run(args) -> Any:
    """Dispatch a Telegram subcommand. Returns a result or raises core.errors."""
    from h2t_ops.core.errors import UsageError
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    client = TelegramClientAdapter()
    cmd = args.telegram_cmd
    if cmd == "auth-status":
        return client.auth_status()
    if cmd == "auth-request-code":
        return client.request_code(args.phone)
    if cmd == "auth-complete":
        return client.complete_auth(args.phone, code=args.code, password=args.password)
    if cmd == "dialogs":
        return _rows(client.list_dialogs(limit=args.limit, kind=args.kind))
    if cmd == "folders":
        return _rows(client.list_folders())
    if cmd == "messages":
        return _rows(client.list_messages(args.entity, limit=args.limit, days=args.days))
    if cmd == "saved-messages":
        return _rows(client.list_saved_messages(limit=args.limit, days=args.days))
    if cmd == "mentions":
        return _rows(client.list_mentions(args.chat_ids, days=args.days, limit=args.limit))
    if cmd == "bootstrap":
        return client.bootstrap_dialogs(force=args.force)
    raise UsageError(f"unknown telegram subcommand: {cmd}")
```

- [ ] **Step 5: Add telegram to CLI routing**

Modify `h2t_ops/cli.py`:

```python
_MIGRATED = {"notion", "gmail", "calendar", "drive", "meetgeek", "telegram"}
```

- [ ] **Step 6: Run T3 tests**

Run:

```powershell
uv run pytest tests/connectors/telegram/test_commands.py tests/connectors/telegram/test_client.py -q
```

Expected: PASS.

- [ ] **Step 7: Run CLI and lazy-registry checks**

Run:

```powershell
uv run h2t-ops --help
uv run h2t-ops connectors
uv run h2t-ops dev check lazy-registry
uv run pytest tests/core tests/connectors -q
```

Expected:

- `connectors` includes `telegram`;
- lazy-registry OK;
- all tests pass.

- [ ] **Step 8: Run boundary grep**

Run:

```powershell
Select-String -Path h2t_ops/connectors/telegram/*.py -Pattern "google\.genai|from google|notion|DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/telegram|chats\.yaml"
```

Expected: no matches.

- [ ] **Step 9: Commit T3**

Run:

```powershell
git add h2t_ops/connectors/telegram/__init__.py h2t_ops/connectors/telegram/commands.py h2t_ops/cli.py tests/connectors/telegram/test_commands.py
git commit -m "feat(telegram): add connector commands and registry entry (#135)"
```

---

## T4 - Skill Compatibility And Legacy Non-Regression

**Files:**
- Modify: `plugins/h2t-ops/skills/telegram/SKILL.md`

- [ ] **Step 1: Rewrite SKILL.md as thin compatibility wrapper**

Replace `plugins/h2t-ops/skills/telegram/SKILL.md` content with:

```markdown
---
name: h2t-ops:telegram
description: "Telegram provider access and compatibility workflows. Use for Telegram auth/session, dialogs, messages, saved messages, mentions, and legacy digest/tasks/research workflows. Triggers: telegram, saved messages, telegram digest, задачи из telegram"
compatibility: "Provider reads use h2t-ops telegram. Legacy workflow commands remain available through scripts/telegram_cli.py until portable workflow extraction."
metadata:
  author: lichtpfad
  version: 1.1.0
---

# Telegram

## Boundary

Telegram provider data is evidence, not truth.

- `h2t-ops telegram ...` is the provider connector: auth/session, dialogs, folders, messages, saved-messages, mentions, bootstrap.
- Legacy `telegram_cli.py` workflows remain available for compatibility: `saved`, `digest`, `tasks`, `research`, `students`, `sync`, `scan-chats`, `cleanup`.
- Gemini summaries/classification are analytics outputs and suggestions.
- POS/coordinator decides which proposals become accepted captures/tasks/decisions or provider writes.
- Notion writes are explicit coordinator actions executed through the Notion connector, not Telegram runtime.

## Provider Connector

```bash
h2t-ops telegram auth status --json
h2t-ops telegram auth request-code --phone +XXXXXXXXXXX
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --code XXXXX
h2t-ops telegram dialogs --limit 20 --json
h2t-ops telegram folders --json
h2t-ops telegram messages <entity> --days 7 --limit 200 --json
h2t-ops telegram saved-messages --days 7 --limit 200 --json
h2t-ops telegram mentions --chat-id 123456 --days 7 --json
h2t-ops telegram bootstrap --force --json
```

`saved-messages` returns raw Telegram rows. The legacy `saved` workflow below still produces the Gemini/markdown digest.

## Legacy Compatibility Workflows

These commands are useful and remain available, but their current placement is not the target architecture. They will move to portable workflow scripts with explicit input/output paths.

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/telegram_cli.py"
```

```bash
$CLI saved [--all]
$CLI digest [--all]
$CLI tasks [--all]
$CLI research [--all]
$CLI students [--all]
$CLI sync
$CLI scan-chats [--import-folders]
$CLI cleanup
```

Do not use `cleanup --archive` unless the user explicitly asks for a Telegram account mutation.

## Troubleshooting

### SESSION_INCOMPATIBLE

If `h2t-ops telegram ... --json` returns `SESSION_INCOMPATIBLE`, the Telethon SQLite session file is incompatible with the installed Telethon version.

The connector will not delete credentials automatically. Recovery is manual:

```bash
# move the old session aside yourself, then re-auth
h2t-ops telegram auth request-code --phone +XXXXXXXXXXX
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --code XXXXX
```

If Telegram asks for 2FA:

```bash
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --password YOUR_PASSWORD
```

Passing `--password` can enter shell history. Prefer a future password-stdin/prompt flow when available.

## Config

```text
~/.config/telegram/
  config.json          {"api_id": N, "api_hash": "..."}
  session.session      Telethon session SQLite credential
  auth_state.json      temporary phone_code_hash between auth steps
  dialogs_bootstrapped entity-cache timestamp
  chats.yaml           workflow configuration owned by scripts/workflows, not connector
```

## Future Extraction

Planned follow-up: extract Telegram analytics/POS workflows into portable scripts.

Target shape:

```bash
h2t-ops telegram saved-messages --days 7 --json > saved.json
python scripts/workflows/telegram_digest.py --input saved.json --output digest.md
```

Portable scripts may call Gemini and write declared output paths. They must not be imported by connector registry/help and must not write POS journal/KB directly.
```

- [ ] **Step 2: Run a markdown sanity check**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/telegram/SKILL.md -Pattern "h2t-ops telegram saved-messages|SESSION_INCOMPATIBLE|Legacy Compatibility Workflows|cleanup --archive|portable scripts"
```

Expected: matches for all terms.

- [ ] **Step 3: Legacy parser non-regression smoke**

Run:

```powershell
$py = "$env:USERPROFILE/.h2t/venv/Scripts/python.exe"
$cli = "plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py"
& $py $cli --help
```

Expected: exit 0 and top-level help lists legacy commands. If the h2t venv is unavailable, record this as an environment skip in T5.

- [ ] **Step 4: Check legacy commands still exist in source**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py -Pattern "sub.add_parser\('saved'|sub.add_parser\('digest'|sub.add_parser\('tasks'|sub.add_parser\('research'|sub.add_parser\('students'|sub.add_parser\('sync'|sub.add_parser\('scan-chats'|sub.add_parser\('cleanup'"
```

Expected: matches for all eight legacy commands.

- [ ] **Step 5: Run full regression**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected: all tests pass; lazy-registry OK.

- [ ] **Step 6: Commit T4**

Run:

```powershell
git add plugins/h2t-ops/skills/telegram/SKILL.md
git commit -m "docs(telegram): delegate provider reads to connector (#135)"
```

---

## T5 - Closure Verification And Evidence

**Files:**
- No commits in T5 unless a previous task failed and needs a reviewed fix.

- [ ] **Step 1: Full mocked test suite**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
```

Expected: all tests pass.

- [ ] **Step 2: Lazy-registry and help checks**

Run:

```powershell
uv run h2t-ops --help
uv run h2t-ops connectors
uv run h2t-ops doctor
uv run h2t-ops dev check lazy-registry
```

Expected:

- help exits 0;
- connectors includes `telegram`;
- doctor exits 0 or reports only expected local secret/session warnings;
- lazy-registry OK.

- [ ] **Step 3: Boundary grep**

Run:

```powershell
Select-String -Path h2t_ops/connectors/telegram/*.py -Pattern "google\.genai|from google|notion|DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/telegram|chats\.yaml"
```

Expected: no matches.

- [ ] **Step 4: Legacy workflow availability check**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py -Pattern "def cmd_saved|def cmd_digest|def cmd_tasks|def cmd_research|def cmd_students|def cmd_sync|def cmd_scan_chats|def cmd_cleanup"
```

Expected: matches for all eight command handlers.

- [ ] **Step 5: Installed CLI smoke**

If the package is installed, reinstall from this repo using the existing project workflow, then run:

```powershell
h2t-ops connectors
h2t-ops telegram auth status --json
```

Expected:

- `connectors` lists `telegram`;
- `auth status --json` exits 0 with auth status if config exists, or exits 3 with typed config error if config is missing.

- [ ] **Step 6: Live read-only smoke**

Only run if Telegram config/session is present on the machine:

```powershell
h2t-ops telegram dialogs --limit 5 --json
h2t-ops telegram saved-messages --limit 5 --json
```

Optional if a known entity is available:

```powershell
h2t-ops telegram messages <known-entity> --limit 5 --json
```

Expected: exit 0 and valid JSON. Do not run `cleanup --archive`. Do not run Notion writes. Do not write DOR/vault/lake.

- [ ] **Step 7: Token/session leak scan**

Run:

```powershell
git diff --cached --name-only
git diff --name-only HEAD
Select-String -Path h2t_ops/connectors/telegram/*.py,tests/connectors/telegram/*.py,plugins/h2t-ops/skills/telegram/SKILL.md -Pattern "api_hash|phone_code_hash|SESSION|auth_key|-----BEGIN|ya29\\.|secret_|ntn_"
```

Expected:

- no staged files unless a fix is intentionally pending;
- matches for literal field names in code/docs are acceptable;
- no real tokens, hashes, phone_code_hash values, or session bytes.

- [ ] **Step 8: Prepare evidence block**

Prepare but do not post without approval:

```markdown
## #135 Telegram connector migration - local evidence

Date: 2026-05-21
Source: local C:/dev/h2t-skills

### Mocked tests
- tests/core tests/connectors: PASS
- lazy-registry: PASS

### Connector surface
- h2t-ops connectors lists telegram
- h2t-ops telegram auth status --json: PASS or typed ConfigError if unconfigured
- h2t-ops telegram dialogs --limit 5 --json: PASS/SKIPPED with reason
- h2t-ops telegram saved-messages --limit 5 --json: PASS/SKIPPED with reason

### Guards
- SESSION_INCOMPATIBLE covered by tests
- Connector grep guard: CLEAN
- Legacy workflows preserved: saved/digest/tasks/research/students/sync/scan-chats/cleanup present
- No cleanup --archive / Notion / DOR writes in live smoke
```

- [ ] **Step 9: Stop for approval**

Do not push, post GitHub comments, or close #135 unless the user explicitly asks.

---

## Self-Review Checklist

### Spec Coverage

- Connector-only Telegram provider I/O: T1, T2, T3.
- Legacy workflow preservation: T4, T5.
- Future portable workflows not implemented: T4 docs and follow-up text only.
- #121 session mismatch: T1 tests/helper and T3 envelope test.
- Telethon lazy imports: T1/T3 tests and T5 lazy-registry.
- No Gemini/Notion/DOR/POS in connector: hard constraints and grep gates.
- `saved-messages` distinct from legacy `saved`: T3 tests and T4 docs.
- Explicit `--chat-id` mentions; no connector `chats.yaml`: T2/T3/T5.
- Live smoke read-only: T5.

### Placeholder Scan

The plan avoids placeholder instructions and unspecified implementation work. Re-run a placeholder scan before execution if the plan is edited.

### Type Consistency

- Client class: `TelegramClientAdapter`.
- Command dispatch attr: `telegram_cmd`.
- Raw saved method: `list_saved_messages`.
- Raw saved command: `saved-messages`.
- Session marker: `SESSION_INCOMPATIBLE` in `error.message`.
