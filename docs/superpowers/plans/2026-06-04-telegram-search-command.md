---
title: "Telegram Search Command Implementation Plan"
status: "draft"
date: "2026-06-04"
milestone: ""
issue: ""
---
# Telegram Search Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `h2t-ops telegram search <query>` command that discovers public channels and users via Telethon's `contacts.SearchRequest`, with fail-loud FloodWait handling.

**Architecture:** Two-layer pattern matches existing connector: `commands.py` owns argparse + dispatch, `client.py` owns Telethon calls. Two new lazy-import helpers (`_search_request_class`, `_flood_wait_error_class`) follow the existing `_dialog_filters_request_class` pattern. No per-channel enrichment in this slice — `participants_count` comes from the search result and is `None` when not returned by Telegram (partial Channel objects). `is_channel` means "broadcast channel" (spec field name); `is_megagroup` covers supergroups. Multi-word query uses `nargs="+"` in argparse.

**Tech Stack:** Python stdlib, Telethon (`contacts.SearchRequest`, `FloodWaitError`), h2t_ops error hierarchy (`ProviderError`)

**Closes:** #255

---

## File Map

| File | Change |
|------|--------|
| `h2t_ops/connectors/telegram/client.py` | Add `_search_request_class()`, `_flood_wait_error_class()`, `search_channels()` |
| `h2t_ops/connectors/telegram/commands.py` | Register `search` subparser; dispatch in `run()` |
| `tests/connectors/telegram/test_client.py` | Tests for the two new helpers and `search_channels()` |
| `tests/connectors/telegram/test_commands.py` | Parser + dispatch tests for `search` verb |
| `plugins/h2t-ops/.claude-plugin/plugin.json` | Bump patch version |

---

## Task 1: Client — `search_channels()` method

**Files:**
- Modify: `h2t_ops/connectors/telegram/client.py`
- Test: `tests/connectors/telegram/test_client.py`

- [ ] **Step 1.1: Write failing tests for helpers and `search_channels()`**

Append to `tests/connectors/telegram/test_client.py` (add only these new imports at the top of the appended block — `builtins`, `json`, `sqlite3`, `SimpleNamespace`, `pytest` are already imported in this file):

```python
from contextlib import contextmanager

from h2t_ops.core.errors import ConfigError, ProviderError


# ── search helpers ────────────────────────────────────────────────────────────

def test_missing_telethon_raises_configerror_for_search_request(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.tl.functions.contacts":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._search_request_class()
    assert "Telethon" in str(ei.value)


def test_missing_telethon_raises_configerror_for_flood_wait(tmp_path, monkeypatch):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "telethon.errors":
            raise ImportError("missing telethon")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = TelegramClientAdapter(config_dir=tmp_path)
    with pytest.raises(ConfigError) as ei:
        client._flood_wait_error_class()
    assert "Telethon" in str(ei.value)


# ── search_channels ───────────────────────────────────────────────────────────

def _make_adapter_with_fake_connection(tmp_path, monkeypatch, fake_client):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    (tmp_path / "config.json").write_text(
        json.dumps({"api_id": 123, "api_hash": "hash"}), encoding="utf-8"
    )
    adapter = TelegramClientAdapter(config_dir=tmp_path)

    @contextmanager
    def fake_connected():
        yield fake_client

    monkeypatch.setattr(adapter, "_connected_client", fake_connected)
    return adapter


def test_search_channels_returns_shaped_rows(tmp_path, monkeypatch):
    chan = SimpleNamespace(
        id=100, username="testchan", title="Test Channel",
        participants_count=500, broadcast=True, megagroup=False, verified=False,
    )
    user_obj = SimpleNamespace(
        id=200, username="testuser", first_name="John", last_name="Doe", verified=True,
    )
    fake_result = SimpleNamespace(chats=[chan], users=[user_obj])

    class FakeClient:
        def __call__(self, req):
            return fake_result

    class FakeSearchReq:
        def __init__(self, q, limit):
            self.q = q

    class FakeFloodWait(Exception):
        seconds = 0

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    rows = adapter.search_channels("test query", limit=10)
    assert len(rows) == 2

    ch = next(r for r in rows if r["id"] == 100)
    assert ch["type"] == "channel"
    assert ch["username"] == "testchan"
    assert ch["title"] == "Test Channel"
    assert ch["participants_count"] == 500  # attribute present → returned as-is
    assert ch["is_channel"] is True
    assert ch["is_megagroup"] is False
    assert ch["verified"] is False

    usr = next(r for r in rows if r["id"] == 200)
    assert usr["type"] == "user"
    assert usr["title"] == "John Doe"
    assert usr["participants_count"] is None  # users never have participants_count
    assert usr["is_channel"] is False
    assert usr["verified"] is True


def test_search_channels_megagroup_type(tmp_path, monkeypatch):
    grp = SimpleNamespace(
        id=300, username="mygroup", title="My Group",
        participants_count=None, broadcast=False, megagroup=True, verified=False,
    )
    fake_result = SimpleNamespace(chats=[grp], users=[])

    class FakeClient:
        def __call__(self, req):
            return fake_result

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    class FakeFloodWait(Exception):
        seconds = 0

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    rows = adapter.search_channels("group")
    assert rows[0]["type"] == "group"
    assert rows[0]["is_megagroup"] is True
    assert rows[0]["is_channel"] is False
    assert rows[0]["participants_count"] is None  # absent attribute → None, not 0


def test_search_channels_raises_provider_error_on_flood_wait(tmp_path, monkeypatch):
    class FakeFloodWait(Exception):
        def __init__(self):
            super().__init__()
            self.seconds = 42  # instance attribute, matching real Telethon FloodWaitError

    class FakeClient:
        def __call__(self, req):
            raise FakeFloodWait()

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    with pytest.raises(ProviderError) as ei:
        adapter.search_channels("flood test")
    assert "FLOOD_WAIT" in str(ei.value)
    assert ei.value.details["wait_seconds"] == 42


def test_search_channels_flood_wait_missing_seconds_fallback(tmp_path, monkeypatch):
    class FakeFloodWait(Exception):
        pass  # no .seconds attribute — graceful fallback

    class FakeClient:
        def __call__(self, req):
            raise FakeFloodWait()

    class FakeSearchReq:
        def __init__(self, q, limit): pass

    adapter = _make_adapter_with_fake_connection(tmp_path, monkeypatch, FakeClient())
    monkeypatch.setattr(adapter, "_search_request_class", lambda: FakeSearchReq)
    monkeypatch.setattr(adapter, "_flood_wait_error_class", lambda: FakeFloodWait)

    with pytest.raises(ProviderError) as ei:
        adapter.search_channels("flood test")
    assert "FLOOD_WAIT" in str(ei.value)
    assert ei.value.details["wait_seconds"] == 0  # fallback when .seconds absent
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/test_client.py -k "search" -v
```

Expected: `AttributeError` — `TelegramClientAdapter` has no `_search_request_class` / `search_channels`.

- [ ] **Step 1.3: Implement in `client.py`**

Add after the `_dialog_filters_request_class` method (after line 214):

```python
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
```

Also add `ProviderError` to the existing module-level import in `client.py` (currently line 2):

```python
# change:
from h2t_ops.core.errors import AuthError, ConfigError
# to:
from h2t_ops.core.errors import AuthError, ConfigError, ProviderError
```

Add after `bootstrap_dialogs` (end of class):

```python
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
```

- [ ] **Step 1.4: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/test_client.py -k "search" -v
```

Expected: all 6 new tests PASS.

- [ ] **Step 1.5: Run full test suite to confirm no regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/ -v
```

Expected: all existing + new tests pass.

- [ ] **Step 1.6: Commit**

```
git add h2t_ops/connectors/telegram/client.py tests/connectors/telegram/test_client.py
git commit -m "feat(telegram): add search_channels() with FloodWait fail-loud handling"
```

---

## Task 2: Commands — `search` verb

**Files:**
- Modify: `h2t_ops/connectors/telegram/commands.py`
- Test: `tests/connectors/telegram/test_commands.py`

- [ ] **Step 2.1: Write failing tests**

Append to `tests/connectors/telegram/test_commands.py`:

```python
def test_parser_registers_search_verb():
    parser = _build_parser()
    # nargs="+" joins multi-word queries without shell quoting
    ns = parser.parse_args(["telegram", "search", "real", "estate", "defi"])
    assert ns.telegram_cmd == "search"
    assert ns.query == ["real", "estate", "defi"]


def test_search_default_limit_is_20():
    parser = _build_parser()
    ns = parser.parse_args(["telegram", "search", "crypto"])
    assert ns.limit == 20


def test_search_accepts_limit_override():
    parser = _build_parser()
    ns = parser.parse_args(["telegram", "search", "crypto", "--limit", "5"])
    assert ns.limit == 5


def test_search_json_flag():
    parser = _build_parser()
    ns = parser.parse_args(["telegram", "search", "crypto", "--json"])
    assert ns.as_json is True


def test_search_dispatches_to_client(monkeypatch):
    import h2t_ops.connectors.telegram.client as client_mod
    from h2t_ops.connectors.telegram import commands as cmds

    calls = {}

    class Stub:
        def search_channels(self, query, *, limit=20):
            calls["query"] = query
            calls["limit"] = limit
            return [{"type": "channel", "id": 1, "username": "ch", "title": "Ch",
                      "participants_count": None, "is_channel": True,
                      "is_megagroup": False, "verified": False}]

    monkeypatch.setattr(client_mod, "TelegramClientAdapter", lambda: Stub())
    args = SimpleNamespace(
        telegram_cmd="search",
        query=["defi", "channels"],  # list from nargs="+"
        limit=10,
        as_json=True,
        fmt="human",
    )
    result = cmds.run(args)
    assert calls["query"] == "defi channels"  # joined by run()
    assert calls["limit"] == 10
    assert result["count"] == 1
    assert result["rows"][0]["type"] == "channel"
```

- [ ] **Step 2.2: Run tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/test_commands.py -k "search" -v
```

Expected: `SystemExit` / `AttributeError` — `search` verb not registered yet.

- [ ] **Step 2.3: Register `search` in `commands.py`**

In `register()`, add after the `bootstrap` block (after line 82):

```python
search = cmds.add_parser("search", help="Discover public channels/users by keyword")
search.add_argument("query", nargs="+", help="search keyword (multi-word: telegram search real estate defi)")
search.add_argument("--limit", type=int, default=20, help="max results (default 20)")
add_json(search)
```

In `run()`, add before the final `raise UsageError` (after the `delete-message` block):

```python
if cmd == "search":
    return _rows(client.search_channels(" ".join(args.query), limit=args.limit))
```

- [ ] **Step 2.4: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/test_commands.py -k "search" -v
```

Expected: all 5 new tests PASS.

- [ ] **Step 2.5: Update the existing `test_parser_registers_all_leaf_verbs` test**

The existing test in `test_commands.py` at line 23 lists all known verbs. Add `search` to the `cases` list:

```python
["telegram", "search", "keyword"],  # single-word; nargs="+" accepts it
```

Also update `test_json_flag_available_on_all_leaf_verbs` to include:

```python
["telegram", "search", "keyword", "--json"],
```

- [ ] **Step 2.6: Run the full telegram test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/telegram/ -v
```

Expected: all tests pass.

- [ ] **Step 2.7: Commit**

```
git add h2t_ops/connectors/telegram/commands.py tests/connectors/telegram/test_commands.py
git commit -m "feat(telegram): add search command — expose contacts.SearchRequest via CLI"
```

---

## Task 3: Version bump

**Files:**
- Modify: `plugins/h2t-ops/.claude-plugin/plugin.json`

- [ ] **Step 3.1: Verify current version**

```
grep "version" plugins/h2t-ops/.claude-plugin/plugin.json
```

Expected: `"version": "1.2.12"`. If different, adjust the bump target accordingly.

- [ ] **Step 3.2: Bump patch version**

```
python scripts/bump_plugin.py h2t-ops 1.2.13
```

- [ ] **Step 3.3: Confirm bump applied**

```
grep "version" plugins/h2t-ops/.claude-plugin/plugin.json
```

Expected: `"version": "1.2.13"`.

- [ ] **Step 3.4: Commit**

```
git add plugins/h2t-ops/.claude-plugin/plugin.json
git commit -m "chore(h2t-ops): bump 1.2.12 → 1.2.13 — telegram search command #255"
```

---

## Spec Coverage Check

| Requirement | Covered by |
|---|---|
| `search <query>` verb | Task 2: `register()` argparse |
| `--limit` with default 20 | Task 2: `add_argument("--limit", default=20)` |
| `--json` flag | Task 2: `add_json(search)` |
| Fields: id, username, title, participants_count, is_channel, is_megagroup, verified | Task 1: `search_channels()` return shape |
| FloodWait fail-loud → ProviderError with wait_seconds | Task 1: `_flood_wait_error_class`, `raise ProviderError` |
| No auto-retry | Task 1: single `try/except`, no loop |
| Channels from `.chats[]`, users from `.users[]` | Task 1: loop in `search_channels()` |
| Read-only / non-destructive | inherent — `SearchRequest` is read-only |
| No private data, no message bodies | inherent — SearchRequest returns entities only |

`channel-info` companion command (optional phase 2, mentioned in issue) is **out of scope** for this plan.
