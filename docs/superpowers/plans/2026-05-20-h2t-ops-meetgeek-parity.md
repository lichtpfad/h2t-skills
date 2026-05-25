---
title: "h2t-ops MeetGeek Parity Migration — Implementation Plan (#134)"
status: "draft"
date: "2026-05-20"
milestone: ""
---
# h2t-ops MeetGeek Parity Migration — Implementation Plan (#134)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate 10 pure-API verbs from `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` into the `h2t_ops` connector runtime (three-file pattern), preserving the existing legacy recovery workflow via the skill path until #149.

**Architecture:** Three-file connector (`client.py` + `commands.py` + `__init__.py`) following the Calendar/Drive pattern. `MeetGeekClient` is a stateless HTTP wrapper consuming `h2t_ops.core.secrets.load_secrets()` lazily. All formatters (md frontmatter, transcript/summary/highlights/insights) live in `commands.py` as private helpers — the client returns raw API dicts. No sync, no webhook-server, no manifest, no local file writes.

**Tech Stack:** Python, `requests` (lazy import), `h2t_ops.core.{secrets,errors,registry,output}`, `pytest`, `uv run h2t-ops dev`.

**Authoritative inputs:**

| Input | Path |
|---|---|
| Design spec | `docs/superpowers/specs/2026-05-20-h2t-ops-meetgeek-parity-design.md` |
| Connector runbook | `plugins/h2t-ops/references/h2t-connector-runbook.md` |
| Legacy script (re-wrap source) | `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` |
| Calendar client (pattern) | `h2t_ops/connectors/calendar/client.py` |
| Calendar commands (pattern) | `h2t_ops/connectors/calendar/commands.py` |
| Calendar tests (pattern) | `tests/connectors/calendar/` |
| Secrets module | `h2t_ops/core/secrets.py` |
| Errors module | `h2t_ops/core/errors.py` |

**Hard constraints (every task obeys):**

1. **T0 is GET-only / no-commit.** No `POST /v1/upload` in T0. Any live submit requires explicit maintainer approval before T2.
2. **`submit-url` is the new CLI verb** for `POST /v1/upload`. Legacy `upload --download-url` becomes a compatibility alias in SKILL.md pointing to `h2t-ops meetgeek submit-url` (done in T3).
3. **`upload --from-file`, `convert`, `drive-upload`, `manifest/resume`** — not touched. Preserved as legacy skill path. Pointer → #149.
4. **`webhook-server`** — not migrated. Future POS/VPS work.
5. **`list` client method returns raw API response.** Display normalization (meeting_id|id, timestamp_start_utc|start_time) happens in `commands.py` formatters only.
6. **No module-level `requests` import** anywhere in `h2t_ops/connectors/meetgeek/`. `dev check lazy-registry` must stay green after every task.
7. **No POS imports**, no `~/.dor` writes, no `DOR_ROOT`/`VAULT_ROOT`/`MEETINGS_DIR` in new code.
8. **Stage only named task files.** Never `git add -A`. The repo has 26+ unrelated tracked-modified files.
9. **Outward-facing actions (push, GitHub comment, close issue) are user-gated.** STOP at T4 for maintainer approval.

## File Map (this plan touches ONLY these files)

| File | Action | Task |
|---|---|---|
| `h2t_ops/connectors/meetgeek/__init__.py` | Create (T1 marker) → Modify (T2 full CONNECTOR body) | T1, T2 |
| `h2t_ops/connectors/meetgeek/client.py` | Create | T1 |
| `h2t_ops/connectors/meetgeek/commands.py` | Create | T2 |
| `h2t_ops/cli.py` | Modify — add `"meetgeek"` to `_MIGRATED` | T2 |
| `tests/connectors/meetgeek/__init__.py` | Create (empty) | T1 |
| `tests/connectors/meetgeek/test_client.py` | Create | T1 |
| `tests/connectors/meetgeek/test_commands.py` | Create | T2 |
| `plugins/h2t-ops/skills/meetgeek/SKILL.md` | Modify — delegate migrated verbs; alias upload --download-url; preserve legacy | T3 |

**File-state checks (run BEFORE starting T1):**

```bash
test -d h2t_ops/connectors/meetgeek/ && echo "T1: PRE-EXISTING — STOP" || echo "T1: clean Create"
test -d tests/connectors/meetgeek/   && echo "T1: PRE-EXISTING — STOP" || echo "T1: clean Create"
grep -q '"meetgeek"' h2t_ops/cli.py  && echo "T2: already in _MIGRATED" || echo "T2: clean Modify"
```

## Per-task verification (run at the END of every task)

```bash
# A. scope gate
git status --porcelain -- h2t_ops/ tests/ plugins/h2t-ops/skills/meetgeek/ | sort

# B. no out-of-scope connector files
git diff --name-only origin/main..HEAD -- h2t_ops/ tests/ plugins/h2t-ops/skills/meetgeek/ \
  | grep -vE '^(h2t_ops/(cli\.py|connectors/meetgeek/(__init__|client|commands)\.py)|tests/connectors/meetgeek/(__init__|test_client|test_commands)\.py|plugins/h2t-ops/skills/meetgeek/SKILL\.md)$' \
  | head && echo "OUT-OF-SCOPE FILE" || echo "OK: plan-scope only"

# C. lazy-registry
uv run h2t-ops dev check lazy-registry

# D. existing connectors regression
uv run h2t-ops dev pytest tests/connectors/gmail tests/connectors/calendar tests/connectors/drive -q
```

If any of A/B/C/D surfaces a violation, STOP and report BLOCKED.

---

## Task 0: API discovery — no code commit

**Purpose:** Verify actual MeetGeek API field names before writing client.py. Prevents writing the wrong field names into tests and implementation.

**Output (assembled in your reply, NOT committed):**
- Field matrix for `POST /v1/upload`
- Field names for `POST /v1/meetings/{id}/download` response
- GET-only live smoke results

- [ ] **Step 1: Check official MeetGeek API documentation**

Visit `https://api.meetgeek.ai/docs` or check any OpenAPI spec in the repo:

```bash
grep -r "language_code\|template_name\|download_url\|download_link" \
  plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py | head -20
```

In `meetgeek_cli.py:811-816`, the legacy `_post_upload()` sends:
```python
body = {"download_url": download_url}
if title: body["title"] = title
if language: body["language"] = language   # ← legacy uses "language"
```

Official docs may specify `language_code` and `template_name`. Record what the docs say. If docs are unavailable, proceed to Step 2 with the live smoke using GET-only endpoints.

- [ ] **Step 2: Run GET-only live smoke**

These calls are read-only and safe to run:

```bash
uv run h2t-ops dev pytest tests/connectors/ -q   # baseline before T1
```

Then check that the legacy skill still works (regression baseline):

```bash
H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
CLI="$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py"
$CLI auth-check
$CLI list --limit 2 2>&1 | head -30
```

Record: exit codes, whether `id` or `meeting_id` appears in list output, whether timestamps appear as `timestamp_start_utc` or `start_time`.

- [ ] **Step 3: Build field matrix**

From docs + live smoke, fill in this matrix (replace `?` with confirmed values):

```
POST /v1/upload:
  - download_url: required (confirmed: yes / ?)
  - title: optional (confirmed: yes / ?)
  - language vs language_code: (confirmed: language_code / language / both / ?)
  - template_name: optional (confirmed: yes / ?)

POST /v1/meetings/{id}/download response:
  - download_link vs download_url vs url: (confirmed: download_link / download_url / ?)

GET /v1/meetings items:
  - id vs meeting_id key: (confirmed: id / meeting_id / both)
  - timestamp_start_utc vs start_time: (confirmed: timestamp_start_utc / start_time / both)
```

- [ ] **Step 4: Decision**

Based on Step 1–3, decide:
- **`submit_url()` field name**: use `language_code` if confirmed, otherwise use both `language_code` and `language` as fallback.
- **`get_download_url()` normalization**: client normalizes `download_link|download_url|url` → always returns `download_url` key.
- **`list_meetings()` normalization**: client returns raw response; commands.py `_normalize_meeting()` handles `id|meeting_id` and `timestamp_start_utc|start_time` aliases for display.

Record decision in your reply. **Do not commit anything in T0.** Do not run `POST /v1/upload`.

---

## Task 1: Create `MeetGeekClient` + client tests

**Files:**
- Create: `h2t_ops/connectors/meetgeek/__init__.py` (minimal package marker)
- Create: `h2t_ops/connectors/meetgeek/client.py`
- Create: `tests/connectors/meetgeek/__init__.py` (empty)
- Create: `tests/connectors/meetgeek/test_client.py`

- [ ] **Step 1: Write failing client tests**

Create `tests/connectors/meetgeek/__init__.py` (empty file).

Create `tests/connectors/meetgeek/test_client.py`:

```python
"""Tests for h2t_ops.connectors.meetgeek.client.MeetGeekClient."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError, UsageError,
)


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client_obj(monkeypatch):
    """MeetGeekClient bypassing __init__ (no network / secrets)."""
    monkeypatch.setenv("MEETGEEK_API_KEY", "test-key")
    from h2t_ops.connectors.meetgeek.client import MeetGeekClient
    c = object.__new__(MeetGeekClient)
    c._api_key = "test-key"
    c._base_url = "https://api.meetgeek.ai"
    c._timeout = 10
    c._session = MagicMock()
    return c


# ─── Module-scope import guard ────────────────────────────────────────────────

def test_module_has_no_module_level_requests_import():
    """requests must not appear at module scope — lazy-import regression guard."""
    src = (
        __import__("pathlib").Path("h2t_ops/connectors/meetgeek/client.py")
        .read_text(encoding="utf-8")
    )
    lines = src.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith(("import requests", "from requests")):
            # Allow inside function bodies (indented), block module-scope (no indent)
            assert line[0] == " ", (
                f"line {i}: module-scope 'requests' import forbidden in client.py: {line!r}"
            )


# ─── Init / auth ─────────────────────────────────────────────────────────────

def test_init_missing_api_key_raises_configerror(monkeypatch):
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    # Prevent load_secrets from picking up real key from disk
    with patch("h2t_ops.connectors.meetgeek.client.load_secrets"):
        from h2t_ops.connectors.meetgeek.client import MeetGeekClient
        with pytest.raises(ConfigError) as ei:
            MeetGeekClient()
    assert "MEETGEEK_API_KEY" in str(ei.value)
    assert ei.value.hint is not None


def test_init_calls_load_secrets_before_reading_env(monkeypatch):
    """load_secrets() must be called before checking os.environ."""
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    call_log = []

    def fake_load():
        os.environ["MEETGEEK_API_KEY"] = "injected-key"
        call_log.append("load_secrets")

    with patch("h2t_ops.connectors.meetgeek.client.load_secrets", side_effect=fake_load):
        from h2t_ops.connectors.meetgeek.client import MeetGeekClient
        client = MeetGeekClient()
    assert call_log == ["load_secrets"]
    assert client._api_key == "injected-key"
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)


def test_auth_check_returns_true_on_200(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    client_obj._request = MagicMock(return_value=resp)
    assert client_obj.auth_check() is True


def test_auth_check_raises_autherror_on_401(client_obj):
    resp = MagicMock()
    resp.status_code = 401
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(AuthError):
        client_obj.auth_check()


def test_auth_check_raises_providererror_on_500(client_obj):
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "err"
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(ProviderError):
        client_obj.auth_check()


# ─── list_meetings ────────────────────────────────────────────────────────────

def test_list_meetings_returns_rows_and_next_cursor(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "meetings": [{"id": "m1"}, {"id": "m2"}],
        "pagination": {"next_cursor": "tok123"},
    }
    client_obj._get = MagicMock(return_value=resp.json())
    result = client_obj.list_meetings(limit=2)
    assert result["rows"] == [{"id": "m1"}, {"id": "m2"}]
    assert result["next_cursor"] == "tok123"


def test_list_meetings_handles_list_response_shape(client_obj):
    """API may return a bare list instead of {meetings: [...]}."""
    client_obj._get = MagicMock(return_value=[{"id": "m1"}])
    result = client_obj.list_meetings()
    assert result["rows"] == [{"id": "m1"}]
    assert result["next_cursor"] is None


def test_list_meetings_raw_rows_preserve_api_fields(client_obj):
    """Client must NOT normalize meeting_id|id or timestamp fields — that is commands layer."""
    raw = {"meeting_id": "abc", "timestamp_start_utc": "2026-05-01T10:00:00Z", "title": "T"}
    client_obj._get = MagicMock(return_value={"meetings": [raw], "pagination": {}})
    result = client_obj.list_meetings()
    assert result["rows"][0] is raw  # same object, no transformation


# ─── get_meeting ──────────────────────────────────────────────────────────────

def test_get_meeting_calls_singular_endpoint(client_obj):
    """/v1/meeting/{id} — note singular, not /v1/meetings/{id}."""
    client_obj._get = MagicMock(return_value={"id": "m1"})
    client_obj.get_meeting("m1")
    client_obj._get.assert_called_once_with("/v1/meeting/m1")


def test_get_meeting_returns_raw_response(client_obj):
    payload = {"id": "m1", "title": "Test", "language_code": "ru"}
    client_obj._get = MagicMock(return_value=payload)
    result = client_obj.get_meeting("m1")
    assert result is payload


# ─── get_transcript ───────────────────────────────────────────────────────────

def test_get_transcript_returns_combined_sentences(client_obj):
    page1 = {
        "meeting_id": "m1",
        "sentences": [{"speaker": "A", "text": "Hello"}],
        "pagination": {"next_cursor": "tok2"},
    }
    page2 = {
        "sentences": [{"speaker": "B", "text": "World"}],
        "pagination": {},
    }
    client_obj._get = MagicMock(side_effect=[page1, page2])
    result = client_obj.get_transcript("m1")
    assert result["meeting_id"] == "m1"
    assert len(result["sentences"]) == 2
    assert result["sentences"][0]["text"] == "Hello"
    assert result["sentences"][1]["text"] == "World"


def test_get_transcript_single_page_no_cursor(client_obj):
    page = {"sentences": [{"text": "Solo"}], "pagination": {}}
    client_obj._get = MagicMock(return_value=page)
    result = client_obj.get_transcript("m1")
    assert len(result["sentences"]) == 1
    client_obj._get.assert_called_once()


# ─── get_summary / highlights / insights ──────────────────────────────────────

def test_get_summary_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"summary": "text"})
    client_obj.get_summary("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/summary")


def test_get_highlights_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"highlights": []})
    client_obj.get_highlights("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/highlights")


def test_get_insights_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={})
    client_obj.get_insights("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/insights")


# ─── get_download_url ─────────────────────────────────────────────────────────

def test_get_download_url_normalizes_download_link(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"download_link": "https://media.meetgeek.ai/file.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.get_download_url("m1")
    assert result["meeting_id"] == "m1"
    assert result["download_url"] == "https://media.meetgeek.ai/file.mp4"


def test_get_download_url_normalizes_url_field(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"url": "https://media.meetgeek.ai/file.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.get_download_url("m1")
    assert result["download_url"] == "https://media.meetgeek.ai/file.mp4"


def test_get_download_url_raises_providererror_when_no_url(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"message": "ok"}  # no url field
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(ProviderError):
        client_obj.get_download_url("m1")


def test_download_url_never_opens_file(client_obj, tmp_path):
    """get_download_url must never open/write a file — URL-only verb."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"download_link": "https://example.com/f.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    with patch("builtins.open") as mock_open:
        client_obj.get_download_url("m1")
    mock_open.assert_not_called()


# ─── get_teams ────────────────────────────────────────────────────────────────

def test_get_teams_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"teams": []})
    client_obj.get_teams()
    client_obj._get.assert_called_once_with("/v1/teams")


# ─── submit_url ───────────────────────────────────────────────────────────────

def test_submit_url_posts_with_canonical_fields(client_obj):
    resp = MagicMock()
    resp.status_code = 202
    resp.json.return_value = {"message": "Processing"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.submit_url(
        "https://example.com/f.mp4",
        title="Meeting 2026-05-20",
        language_code="ru",
        template_name="default",
    )
    call_kwargs = client_obj._request.call_args
    body = call_kwargs[1]["json_body"]
    assert body["download_url"] == "https://example.com/f.mp4"
    assert body["language_code"] == "ru"
    assert body["title"] == "Meeting 2026-05-20"
    assert body["template_name"] == "default"
    assert result["message"] == "Processing"


def test_submit_url_omits_none_optional_fields(client_obj):
    resp = MagicMock()
    resp.status_code = 202
    resp.json.return_value = {"message": "ok"}
    client_obj._request = MagicMock(return_value=resp)
    client_obj.submit_url("https://example.com/f.mp4")
    body = client_obj._request.call_args[1]["json_body"]
    assert "title" not in body
    assert "language_code" not in body
    assert "template_name" not in body


def test_submit_url_empty_url_raises_usageerror(client_obj):
    with pytest.raises(UsageError):
        client_obj.submit_url("")


def test_submit_url_raises_autherror_on_401(client_obj):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "Unauthorized"
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(AuthError):
        client_obj.submit_url("https://example.com/f.mp4")


# ─── Error mapping (_raise_for_status) ────────────────────────────────────────

def test_raise_for_status_401_autherror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "Unauthorized"
    with pytest.raises(AuthError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_404_notfounderror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 404
    resp.text = "Not Found"
    with pytest.raises(NotFoundError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_400_usageerror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "Bad request"
    with pytest.raises(UsageError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_429_providererror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 429
    resp.text = "Rate limited"
    with pytest.raises(ProviderError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_500_providererror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Server error"
    with pytest.raises(ProviderError):
        _raise_for_status(resp, "/v1/test")


def test_network_exception_raises_networkerror(client_obj, monkeypatch):
    """ConnectionError from requests → NetworkError."""
    import requests as _r

    def _fail(*a, **k):
        raise _r.ConnectionError("connection refused")

    monkeypatch.setattr(
        "h2t_ops.connectors.meetgeek.client.MeetGeekClient._request",
        _fail,
    )
    with pytest.raises(NetworkError):
        client_obj._get("/v1/meetings")
```

**Bare-Ellipsis sentinel (run before Step 2):**

```bash
python -c "
import re, sys
src = open('tests/connectors/meetgeek/test_client.py').read()
for i, line in enumerate(src.splitlines(), 1):
    if re.match(r'^\s*\.\.\.\s*$', line):
        print(f'BLOCKED: bare Ellipsis body at line {i}'); sys.exit(1)
print('OK: no bare Ellipsis bodies')
"
```

- [ ] **Step 2: Run failing tests**

```bash
uv run h2t-ops dev pytest tests/connectors/meetgeek/test_client.py -v
```

Expected: ALL FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.meetgeek'`.

- [ ] **Step 3: Create minimal package marker**

Create `h2t_ops/connectors/meetgeek/__init__.py`:

```python
"""MeetGeek connector — package marker.

T1 ships this marker + client.py only; T2 wires CONNECTOR and commands.py.
"""
```

- [ ] **Step 4: Create `h2t_ops/connectors/meetgeek/client.py`**

```python
"""MeetGeekClient — pure API adapter (parity for #134).

Re-wraps ten verbs from meetgeek_cli.py. No sync, no webhook, no local state.
Requests imported lazily; h2t_ops.core.secrets.load_secrets() called on init.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import load_secrets

MEETGEEK_API_SCOPES = None  # Bearer key only — no OAuth


def _raise_for_status(resp: Any, context: str) -> None:
    """Map HTTP status to typed h2t_ops errors. Raises if status >= 400."""
    status = resp.status_code
    if status == 401:
        raise AuthError(f"MEETGEEK_API_KEY invalid (401 from {context})")
    if status == 404:
        raise NotFoundError(f"Not found: {context}")
    if status == 400:
        raise UsageError(f"Bad request ({context}): {resp.text[:300]}")
    if status == 429:
        raise ProviderError(f"MeetGeek rate limit exceeded ({context})")
    if status >= 500:
        raise ProviderError(f"MeetGeek server error {status} ({context}): {resp.text[:200]}")


class MeetGeekClient:
    """MeetGeek API client — 10 pure-API verbs, no local state."""

    def __init__(self) -> None:
        load_secrets()  # merges ~/.dor/secrets.env into os.environ (no-override)
        api_key = os.environ.get("MEETGEEK_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "MEETGEEK_API_KEY not set.",
                hint="Add MEETGEEK_API_KEY to ~/.dor/secrets.env or set in environment. "
                     "Registry: ~/.h2t/config/secrets/meetgeek.md",
            )
        self._api_key = api_key
        self._base_url = os.environ.get(
            "MEETGEEK_BASE_URL", "https://api.meetgeek.ai"
        ).rstrip("/")
        self._timeout = int(os.environ.get("MEETGEEK_TIMEOUT", "30"))

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}

    def _request(self, method: str, path: str, *,
                 params: Optional[Dict] = None,
                 json_body: Optional[Any] = None) -> Any:
        import requests as _r  # lazy — module-scope import forbidden
        url = (
            f"{self._base_url}{path}"
            if path.startswith("/")
            else f"{self._base_url}/{path}"
        )
        backoff = 1.0
        last_exc = None
        for attempt in range(3):
            try:
                resp = _r.request(
                    method, url,
                    headers=self._headers(),
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                )
            except _r.RequestException as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise NetworkError(
                    f"MeetGeek request failed after 3 attempts: {exc}"
                ) from exc
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", backoff))
                time.sleep(retry_after)
                backoff *= 2
                continue
            if resp.status_code >= 500 and attempt < 2:
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        raise NetworkError(
            f"MeetGeek request failed after 3 attempts: {last_exc or 'server error'}"
        )

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        import requests as _r
        try:
            resp = self._request("GET", path, params=params)
        except _r.RequestException as exc:
            raise NetworkError(f"Network error on GET {path}: {exc}") from exc
        _raise_for_status(resp, path)
        try:
            return resp.json()
        except ValueError:
            raise ProviderError(f"Malformed JSON from {path}")

    # ─── Read verbs ───────────────────────────────────────────────────────────

    def auth_check(self) -> bool:
        """Returns True if API key is valid; raises AuthError on 401."""
        resp = self._request("GET", "/v1/meetings", params={"limit": 1})
        if resp.status_code == 200:
            return True
        if resp.status_code == 401:
            raise AuthError("MEETGEEK_API_KEY invalid (401)")
        raise ProviderError(f"auth-check: unexpected status {resp.status_code}")

    def list_meetings(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns {rows: [...raw...], next_cursor: str|None}.

        Rows are raw API items — normalization (meeting_id|id, timestamps)
        is the commands layer's responsibility (spec §"list normalization").
        """
        params: Dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if limit:
            params["limit"] = limit
        data = self._get("/v1/meetings", params=params)
        if isinstance(data, list):
            rows = data
            next_cursor = None
        else:
            rows = data.get("meetings") or data.get("items") or data.get("data") or []
            pagination = data.get("pagination") or {}
            next_cursor = (
                pagination.get("next_cursor")
                or data.get("next_cursor")
                or data.get("cursor")
            )
        return {"rows": rows, "next_cursor": next_cursor}

    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """/v1/meeting/{id} — note singular endpoint."""
        return self._get(f"/v1/meeting/{meeting_id}")

    def get_transcript(self, meeting_id: str) -> Dict[str, Any]:
        """Fetches all transcript pages; returns {sentences: [...], ...metadata}."""
        sentences = []
        base: Dict[str, Any] = {}
        cursor: Optional[str] = None
        pages = 0
        max_pages = int(os.environ.get("MEETGEEK_MAX_PAGES", "1000"))
        while True:
            if pages >= max_pages:
                break
            params = {"cursor": cursor} if cursor else None
            page = self._get(f"/v1/meetings/{meeting_id}/transcript", params=params)
            if pages == 0:
                base = {
                    k: v for k, v in page.items()
                    if k not in ("sentences", "transcript", "pagination")
                }
            page_sentences = page.get("sentences") or page.get("transcript") or []
            sentences.extend(page_sentences)
            pagination = page.get("pagination") or {}
            cursor = pagination.get("next_cursor") or page.get("next_cursor")
            pages += 1
            if not cursor or not page_sentences:
                break
        return {**base, "sentences": sentences}

    def get_summary(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/summary")

    def get_highlights(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/highlights")

    def get_insights(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/insights")

    def get_teams(self) -> Any:
        return self._get("/v1/teams")

    def get_download_url(self, meeting_id: str) -> Dict[str, Any]:
        """POST /v1/meetings/{id}/download → {meeting_id, download_url}.

        Returns URL only — never writes file to disk.
        Normalizes download_link|download_url|url → always 'download_url'.
        """
        resp = self._request("POST", f"/v1/meetings/{meeting_id}/download")
        _raise_for_status(resp, f"/v1/meetings/{meeting_id}/download")
        try:
            info = resp.json()
        except ValueError:
            raise ProviderError(f"Malformed JSON from /download for {meeting_id}")
        url = (
            info.get("download_link")
            or info.get("download_url")
            or info.get("url")
        )
        if not url:
            raise ProviderError(f"No download URL in response for {meeting_id}: {info!r}")
        return {"meeting_id": meeting_id, "download_url": url}

    # ─── Write verb ───────────────────────────────────────────────────────────

    def submit_url(
        self,
        download_url: str,
        *,
        title: Optional[str] = None,
        language_code: Optional[str] = None,
        template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v1/upload — single provider-write verb.

        Named submit_url to distinguish from the upload --from-file pipeline (#149).
        Sends canonical field names: download_url, language_code, title, template_name.
        """
        if not download_url:
            raise UsageError("submit-url: download_url is required and must be non-empty")
        body: Dict[str, Any] = {"download_url": download_url}
        if title:
            body["title"] = title
        if language_code:
            body["language_code"] = language_code
        if template_name:
            body["template_name"] = template_name
        resp = self._request("POST", "/v1/upload", json_body=body)
        _raise_for_status(resp, "/v1/upload")
        try:
            return resp.json()
        except ValueError:
            return {"message": resp.text[:500]}
```

- [ ] **Step 5: Run client tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/meetgeek/test_client.py -v
```

Expected: all tests pass (≈ 28 tests). If any fail, fix the client before proceeding.

- [ ] **Step 6: Per-task verification (A/B/C/D)**

Run the four-gate block from the plan header. Expected: A shows only T1 files; B `OK: plan-scope only`; C `OK lazy-registry`; D Gmail+Calendar+Drive green.

- [ ] **Step 7: Commit (T1)**

```bash
git add h2t_ops/connectors/meetgeek/__init__.py h2t_ops/connectors/meetgeek/client.py tests/connectors/meetgeek/__init__.py tests/connectors/meetgeek/test_client.py
git diff --cached --stat
```

```bash
git commit -m "feat(meetgeek): MeetGeekClient parity surface + client tests (#134)

Re-wrap 10 pure-API verbs from meetgeek_cli.py as a typed h2t-ops client.

Read verbs: auth-check, list-meetings, get-meeting, get-transcript
(paginated), get-summary, get-highlights, get-insights, get-teams,
get-download-url. Single write verb: submit-url (POST /v1/upload with
canonical field names: download_url, language_code, title, template_name).

Key contracts:
- list_meetings returns raw API rows; normalization is commands layer.
- get_download_url normalizes download_link|download_url|url -> download_url.
- get_download_url never writes file to disk (URL-only verb).
- submit_url raises UsageError for empty download_url.
- requests imported lazily (dev check lazy-registry covers this).

sync, webhook-server, upload --from-file, convert, drive-upload, manifest
are NOT migrated here -- disposition tracked in #149 / future POS/VPS."
```

---

## Task 2: `commands.py` + registry + `cli.py` + commands tests

**Files:**
- Modify: `h2t_ops/connectors/meetgeek/__init__.py` (replace T1 marker with CONNECTOR body)
- Create: `h2t_ops/connectors/meetgeek/commands.py`
- Modify: `h2t_ops/cli.py` — add `"meetgeek"` to `_MIGRATED`
- Create: `tests/connectors/meetgeek/test_commands.py`

- [ ] **Step 1: Write failing commands tests**

Create `tests/connectors/meetgeek/test_commands.py`:

```python
"""Tests for h2t_ops.connectors.meetgeek.commands."""
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import ConfigError, UsageError


def _build_parser():
    from h2t_ops.connectors.meetgeek.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


# ─── Registration ─────────────────────────────────────────────────────────────

def test_register_creates_subparsers_for_ten_verbs():
    parser = _build_parser()
    for verb, extra in [
        ("auth-check", []),
        ("teams", []),
        ("list", []),
        ("get", ["m1"]),
        ("transcript", ["m1"]),
        ("summary", ["m1"]),
        ("highlights", ["m1"]),
        ("insights", ["m1"]),
        ("download-url", ["m1"]),
        ("submit-url", ["https://example.com/f.mp4"]),
    ]:
        ns = parser.parse_args(["meetgeek", verb, *extra])
        assert ns.meetgeek_cmd == verb, f"verb {verb!r} not registered"


def test_json_flag_available_on_all_verbs():
    parser = _build_parser()
    for verb, extra in [
        ("list", []),
        ("get", ["m1"]),
        ("transcript", ["m1"]),
        ("teams", []),
        ("download-url", ["m1"]),
        ("submit-url", ["https://example.com/f.mp4"]),
    ]:
        ns = parser.parse_args(["meetgeek", verb, "--json", *extra])
        assert ns.as_json is True, f"--json missing from {verb!r}"


def test_transcript_summary_highlights_insights_have_format_flag():
    parser = _build_parser()
    for verb in ("transcript", "summary", "highlights", "insights"):
        ns = parser.parse_args(["meetgeek", verb, "--format", "md", "m1"])
        assert ns.fmt == "md"
        ns2 = parser.parse_args(["meetgeek", verb, "--format", "json", "m1"])
        assert ns2.fmt == "json"


def test_submit_url_requires_url_positional():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["meetgeek", "submit-url"])


# ─── Client lazily imported ────────────────────────────────────────────────────

def test_commands_module_does_not_import_client_at_module_scope():
    src = Path("h2t_ops/connectors/meetgeek/commands.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if "meetgeek.client" in stripped or "MeetGeekClient" in stripped:
            assert line[0] == " ", (
                f"line {i}: MeetGeekClient must not be imported at module scope: {line!r}"
            )


# ─── Dispatch — happy path ────────────────────────────────────────────────────

def _stub_client(monkeypatch, methods: dict):
    """Patch MeetGeekClient constructor to return a stub with given method returns."""
    import h2t_ops.connectors.meetgeek.client as client_mod
    stub = MagicMock()
    for name, ret in methods.items():
        getattr(stub, name).return_value = ret
    monkeypatch.setattr(client_mod, "MeetGeekClient", lambda: stub)
    return stub


def test_list_dispatch_returns_rows(monkeypatch):
    stub = _stub_client(monkeypatch, {"list_meetings": {"rows": [{"id": "m1"}], "next_cursor": None}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(
        meetgeek_cmd="list", limit=None, cursor=None,
        from_date=None, to_date=None, as_json=True, fmt="human",
    )
    result = cmds.run(args)
    assert result["rows"][0]["id"] == "m1"


def test_get_dispatch_returns_meeting(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_meeting": {"id": "m1", "title": "Test"}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="get", meeting_id="m1", as_json=True, fmt="human")
    result = cmds.run(args)
    assert result["id"] == "m1"


def test_transcript_dispatch_json_format(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_transcript": {"sentences": [{"text": "Hi"}]}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="transcript", meeting_id="m1", fmt="json", as_json=False)
    result = cmds.run(args)
    assert result["sentences"][0]["text"] == "Hi"


def test_transcript_dispatch_md_format_returns_string(monkeypatch):
    stub = _stub_client(monkeypatch, {
        "get_meeting": {"id": "m1", "title": "T"},
        "get_transcript": {"sentences": [{"speaker": "A", "text": "Hello", "timestamp": 0}]},
    })
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="transcript", meeting_id="m1", fmt="md", as_json=False)
    result = cmds.run(args)
    assert isinstance(result, str)
    assert "---" in result  # frontmatter present
    assert "Hello" in result


def test_download_url_dispatch_returns_envelope(monkeypatch):
    stub = _stub_client(monkeypatch, {
        "get_download_url": {"meeting_id": "m1", "download_url": "https://example.com/f.mp4"},
    })
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="download-url", meeting_id="m1", as_json=True, fmt="human")
    result = cmds.run(args)
    assert result["download_url"] == "https://example.com/f.mp4"


def test_submit_url_dispatch_calls_submit_url(monkeypatch):
    stub = _stub_client(monkeypatch, {"submit_url": {"message": "Processing"}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(
        meetgeek_cmd="submit-url",
        download_url="https://example.com/f.mp4",
        title=None, language_code=None, template_name=None,
        as_json=True, fmt="human",
    )
    result = cmds.run(args)
    stub.submit_url.assert_called_once_with(
        "https://example.com/f.mp4",
        title=None, language_code=None, template_name=None,
    )
    assert result["message"] == "Processing"


def test_auth_check_dispatch_returns_ok(monkeypatch):
    stub = _stub_client(monkeypatch, {"auth_check": True})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="auth-check", as_json=False, fmt="human")
    result = cmds.run(args)
    assert result is True or result == {"status": "ok"}


def test_teams_dispatch_returns_teams(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_teams": {"teams": []}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="teams", as_json=True, fmt="human")
    result = cmds.run(args)
    assert "teams" in result


def test_unknown_subcommand_raises_usageerror(monkeypatch):
    _stub_client(monkeypatch, {})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="bogus", as_json=False, fmt="human")
    with pytest.raises(UsageError):
        cmds.run(args)


# ─── Formatter helpers ────────────────────────────────────────────────────────

def test_normalize_meeting_prefers_timestamp_start_utc():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"id": "m1", "title": "T", "timestamp_start_utc": "2026-05-01T10:00:00Z", "start_time": "old"}
    result = _normalize_meeting(m)
    assert result["timestamp_start_utc"] == "2026-05-01T10:00:00Z"
    assert result["date"] == "2026-05-01"


def test_normalize_meeting_falls_back_to_start_time():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"meeting_id": "m2", "title": "T", "start_time": "2026-04-01T09:00:00Z"}
    result = _normalize_meeting(m)
    assert result["meeting_id"] == "m2"
    assert result["timestamp_start_utc"] == "2026-04-01T09:00:00Z"
    assert result["date"] == "2026-04-01"


def test_normalize_meeting_supports_id_alias():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"id": "m3", "title": "T"}
    result = _normalize_meeting(m)
    assert result["meeting_id"] == "m3"
```

**Bare-Ellipsis sentinel:**

```bash
python -c "
import re, sys
src = open('tests/connectors/meetgeek/test_commands.py').read()
for i, line in enumerate(src.splitlines(), 1):
    if re.match(r'^\s*\.\.\.\s*$', line):
        print(f'BLOCKED: bare Ellipsis at line {i}'); sys.exit(1)
print('OK: no bare Ellipsis bodies')
"
```

- [ ] **Step 2: Run failing commands tests**

```bash
uv run h2t-ops dev pytest tests/connectors/meetgeek/test_commands.py -v
```

Expected: ALL FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.meetgeek.commands'`.

- [ ] **Step 3: Replace `__init__.py` marker with CONNECTOR body**

```python
"""MeetGeek connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="meetgeek",
    help="Work with MeetGeek meetings, transcripts, and summaries",
    client="h2t_ops.connectors.meetgeek.client:MeetGeekClient",  # lazy ref
    register=register,
)
```

- [ ] **Step 4: Create `h2t_ops/connectors/meetgeek/commands.py`**

```python
"""MeetGeek CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

PROVIDER = "meetgeek"

# ─── Display helpers (private — display layer only) ───────────────────────────

_YAML_UNSAFE = (":", "#", "'", '"', ",", "[", "]", "{", "}", "\n", "&", "*", "!", "|", ">", "%", "@", "`")


def _yaml_value(v: Any) -> str:
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return ""
    s = str(v)
    if not s:
        return '""'
    if any(c in s for c in _YAML_UNSAFE) or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for k, val in fields.items():
        if val is None or val == "":
            continue
        lines.append(f"{k}: {_yaml_value(val)}")
    lines.append("---")
    return "\n".join(lines)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_meeting(m: dict) -> dict:
    """Normalize API field aliases for display/frontmatter.

    Supports both id|meeting_id and timestamp_start_utc|start_time per spec
    and the e29804a date-field regression guard.
    """
    attendees = m.get("attendees") or m.get("participants") or []
    names = []
    for a in attendees:
        if isinstance(a, dict):
            names.append(a.get("name") or a.get("email") or "")
        elif isinstance(a, str):
            names.append(a)
    start_ts = (
        m.get("timestamp_start_utc")
        or m.get("start_time")
        or m.get("created_at")
    )
    end_ts = m.get("timestamp_end_utc") or m.get("end_time")
    meeting_id = m.get("id") or m.get("meeting_id")
    return {
        "meeting_id": meeting_id,
        "title": m.get("title") or m.get("name") or "",
        "attendees": [n for n in names if n],
        "date": (start_ts or "")[:10],
        "timestamp_start_utc": start_ts,
        "timestamp_end_utc": end_ts,
        "duration_seconds": m.get("duration") or m.get("duration_seconds"),
        "language": m.get("language") or m.get("language_code"),
    }


def _fmt_transcript_md(meeting: dict, transcript: dict) -> str:
    meta = _normalize_meeting(meeting)
    speakers = []
    for s in transcript.get("sentences") or []:
        sp = (s.get("speaker") or s.get("speaker_name") or "").strip()
        if sp and sp not in speakers:
            speakers.append(sp)
    if not meta["attendees"]:
        meta = {**meta, "attendees": speakers}
    fm = _frontmatter({**meta, "source": "meetgeek-api", "fetched_at": _now_iso(), "api_version": "v1"})
    title = meta["title"] or meta["meeting_id"] or "Meeting"
    lines = [fm, "", f"# {title}", "", "## Transcript", ""]
    for s in transcript.get("sentences") or []:
        speaker = s.get("speaker") or s.get("speaker_name") or "Speaker"
        ts = s.get("timestamp") or s.get("start_time") or ""
        text = s.get("transcript") or s.get("text") or ""
        if isinstance(ts, (int, float)):
            mins, secs = divmod(int(ts), 60)
            hrs, mins = divmod(mins, 60)
            ts = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        elif isinstance(ts, str) and "T" in ts:
            ts = ts[11:19]
        lines.append(f"**{speaker}** [{ts}] — {text}")
    return "\n".join(lines) + "\n"


def _fmt_summary_md(meeting: dict, summary: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "summary", "source": "meetgeek-api", "fetched_at": _now_iso()})
    body = summary.get("summary") or summary.get("text") or ""
    parts = [fm, "", f"# Summary — {meta['title'] or meta['meeting_id']}", "", body, ""]
    actions = summary.get("action_items") or []
    if actions:
        parts.append("## Action Items\n")
        for a in actions:
            owner = a.get("owner") or a.get("assignee") or "—"
            text = a.get("text") or a.get("description") or ""
            parts.append(f"- [ ] **{owner}**: {text}")
    return "\n".join(parts) + "\n"


def _fmt_highlights_md(meeting: dict, highlights: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "highlights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    items = highlights.get("highlights") or highlights.get("items") or []
    parts = [fm, "", f"# Highlights — {meta['title'] or meta['meeting_id']}", ""]
    for h in items:
        text = h.get("text") or h.get("description") or ""
        ts = h.get("timestamp") or ""
        parts.append(f"- [{ts}] {text}" if ts else f"- {text}")
    return "\n".join(parts) + "\n"


def _fmt_insights_md(meeting: dict, insights: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "insights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    return fm + "\n\n# Insights\n\n```json\n" + json.dumps(insights, ensure_ascii=False, indent=2) + "\n```\n"


# ─── Registration ──────────────────────────────────────────────────────────────

def register(subparsers: Any) -> None:
    p = subparsers.add_parser("meetgeek", help="Work with MeetGeek meetings, transcripts, and summaries")
    cmds = p.add_subparsers(dest="meetgeek_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/frontmatter, human = concise (default)")

    # auth-check
    ac = cmds.add_parser("auth-check", help="Validate MEETGEEK_API_KEY")
    ac.add_argument("--json", dest="as_json", action="store_true")

    # teams
    tp = cmds.add_parser("teams", help="List user teams")
    add_fmt(tp)

    # list
    lp = cmds.add_parser("list", help="List meetings")
    lp.add_argument("--limit", type=int, default=None)
    lp.add_argument("--cursor", default=None)
    lp.add_argument("--from-date", dest="from_date", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--to-date", dest="to_date", default=None, metavar="YYYY-MM-DD")
    add_fmt(lp)

    # get
    gp = cmds.add_parser("get", help="Get one meeting by ID")
    gp.add_argument("meeting_id")
    add_fmt(gp)

    # transcript / summary / highlights / insights
    for verb in ("transcript", "summary", "highlights", "insights"):
        vp = cmds.add_parser(verb, help=f"Get {verb} for a meeting")
        vp.add_argument("meeting_id")
        vp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md")
        vp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")

    # download-url
    dp = cmds.add_parser("download-url", help="Get signed recording URL for a meeting")
    dp.add_argument("meeting_id")
    add_fmt(dp)

    # submit-url (provider-write verb)
    sp = cmds.add_parser("submit-url", help="Submit a public URL to MeetGeek for transcription (POST /v1/upload)")
    sp.add_argument("download_url", help="Publicly accessible URL of the recording")
    sp.add_argument("--title", default=None)
    sp.add_argument("--language-code", dest="language_code", default=None, metavar="CODE",
                    help="e.g. ru, en, auto")
    sp.add_argument("--template", dest="template_name", default=None)
    sp.add_argument("--json", dest="as_json", action="store_true")

    p.set_defaults(_handler=run)


# ─── Dispatch ──────────────────────────────────────────────────────────────────

def run(args: Any) -> Any:
    """Dispatch a meetgeek subcommand. Returns result or raises core.errors."""
    from h2t_ops.connectors.meetgeek.client import MeetGeekClient  # lazy
    from h2t_ops.core.errors import UsageError

    client = MeetGeekClient()
    cmd = args.meetgeek_cmd

    if cmd == "auth-check":
        return client.auth_check()

    if cmd == "teams":
        return client.get_teams()

    if cmd == "list":
        return client.list_meetings(
            limit=args.limit,
            cursor=args.cursor,
            from_date=args.from_date,
            to_date=args.to_date,
        )

    if cmd == "get":
        return client.get_meeting(args.meeting_id)

    if cmd == "transcript":
        transcript = client.get_transcript(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_transcript_md(meeting, transcript)
        return transcript

    if cmd == "summary":
        summary = client.get_summary(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_summary_md(meeting, summary)
        return summary

    if cmd == "highlights":
        highlights = client.get_highlights(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_highlights_md(meeting, highlights)
        return highlights

    if cmd == "insights":
        insights = client.get_insights(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_insights_md(meeting, insights)
        return insights

    if cmd == "download-url":
        return client.get_download_url(args.meeting_id)

    if cmd == "submit-url":
        return client.submit_url(
            args.download_url,
            title=args.title,
            language_code=args.language_code,
            template_name=args.template_name,
        )

    raise UsageError(f"unknown meetgeek subcommand: {cmd}")
```

- [ ] **Step 5: Wire `h2t_ops/cli.py`**

Open `h2t_ops/cli.py` and update line 18:

```python
_MIGRATED = {"notion", "gmail", "calendar", "drive", "meetgeek"}
```

- [ ] **Step 6: Run commands tests to verify they pass**

```bash
uv run h2t-ops dev pytest tests/connectors/meetgeek/ -v
```

Expected: all client + commands tests pass.

- [ ] **Step 7: Per-task verification (A/B/C/D)**

Expected: A shows only T2 files + `h2t_ops/cli.py`; B `OK: plan-scope only`; C `OK lazy-registry`; D green.

- [ ] **Step 8: Commit (T2)**

```bash
git add h2t_ops/connectors/meetgeek/__init__.py h2t_ops/connectors/meetgeek/commands.py h2t_ops/cli.py tests/connectors/meetgeek/test_commands.py
git diff --cached --stat
```

```bash
git commit -m "feat(meetgeek): CLI commands + registry entry (#134)

Wire 10 argparse subparsers onto MeetGeekClient from T1, add meetgeek
to cli._MIGRATED. Formatters (_normalize_meeting, _fmt_transcript_md,
_fmt_summary_md, _fmt_highlights_md, _fmt_insights_md) live in
commands.py as private display-layer helpers.

_normalize_meeting preserves the e29804a date-field fix: supports both
timestamp_start_utc (canonical) and start_time (fallback) aliases, and
both id and meeting_id. Raw rows from list_meetings are not transformed
by the client — normalization only at display time.

submit-url is the only provider-write verb. MeetGeekClient is imported
lazily inside run() — module-scope google/requests imports remain
forbidden (dev check lazy-registry covers this)."
```

---

## Task 3: `SKILL.md` rewrite — delegate migrated verbs

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/SKILL.md`

- [ ] **Step 1: Update `## Переменные` section**

Replace the `CLI=` line so migrated verbs use `h2t-ops meetgeek` and legacy verbs still use the legacy script:

```bash
# New connector CLI (migrated verbs)
H2T_OPS="h2t-ops"

# Legacy script (recovery workflow — tracked in #149)
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-ops:setup" && exit 1
LEGACY_CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/meetgeek_cli.py"
```

- [ ] **Step 2: Update `## Команды` — migrated verbs**

Replace auth-check, teams, list, get, transcript, summary, highlights, insights, download, upload --download-url command blocks to delegate to `h2t-ops meetgeek`:

```markdown
### Auth-check
```bash
$H2T_OPS meetgeek auth-check
```
Validate `MEETGEEK_API_KEY`. Exit 0 = ok.

### Teams
```bash
$H2T_OPS meetgeek teams [--json]
```

### List meetings
```bash
$H2T_OPS meetgeek list [--limit N] [--cursor C] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD] [--json]
```

### Single meeting
```bash
$H2T_OPS meetgeek get <meeting-id> [--json]
$H2T_OPS meetgeek transcript <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek summary    <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek highlights <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek insights   <meeting-id> [--format md|json] [--json]
```

### Download recording URL
```bash
$H2T_OPS meetgeek download-url <meeting-id> [--json]
```
Returns `{meeting_id, download_url}` — signed URL only, no file download.

### Submit URL for transcription
```bash
$H2T_OPS meetgeek submit-url <URL> [--title T] [--language-code CODE] [--template NAME] [--json]
```
`POST /v1/upload`. Submit a public recording URL directly to MeetGeek API.
Alias: the legacy `$LEGACY_CLI upload --download-url <URL>` routes here.
```

- [ ] **Step 3: Add `### Legacy / Recovery workflow (tracked in #149)` section**

After the migrated commands section, add:

```markdown
### Legacy: upload local recordings (tracked in #149)

**Do not delete these commands** — they are production functionality preserved until #149 extracts
and refactors the recovery workflow.

```bash
# Convert (webm → mp4)
$LEGACY_CLI convert <in.webm> [-o out.mp4] [--audio-only] [--mix-mode amix|first|keep] [--probe]

# Upload to Drive (creates MeetGeek Uploads/{YYYY-MM-DD}/, shares publicly)
$LEGACY_CLI drive-upload <file> [--folder "MeetGeek Uploads/2026-05-06"] [--no-make-public]

# Full pipeline: convert + drive-upload + submit (manifest/resume in ~/.dor/lake/meetgeek/)
$LEGACY_CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' \
            [--audio-only] [--mix-mode amix|first|keep] \
            [--language ru] [--no-skip-existing] [--dry-run]
```

State for resume: `~/.dor/lake/meetgeek/uploads-staging/manifest.jsonl`

These commands depend on `google-api-python-client` and `imageio-ffmpeg`. See `$LEGACY_CLI --help`.
#149 will extract this workflow and replace the embedded Drive logic with the Drive connector (#133).

### Legacy: sync and webhook-server

`sync` and `webhook-server` are **not migrated** to the h2t-ops connector.

- `sync` writes to `~/.dor/lake/meetgeek/`, cursor, manifest — coordinator/lake layer, not connector.
- `webhook-server` is dev-only; production webhook integration belongs to POS/VPS (stable public
  endpoint, signature verification, `pos_ingest` routing).

```bash
# Legacy sync (still works via legacy script)
$LEGACY_CLI sync --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/ --since-cursor --include transcripts

# Legacy webhook server (dev only)
$LEGACY_CLI webhook-server --port 8765 --bind 127.0.0.1 --out ~/.dor/lake/meetgeek/webhooks/
```
```

- [ ] **Step 4: Bump skill version**

In SKILL.md frontmatter, change:
```yaml
  version: 1.1.0
```
to:
```yaml
  version: 1.2.0
```

- [ ] **Step 5: Lint the skill**

```bash
uv run h2t-dev docs-lint plugins/h2t-ops/skills/meetgeek/SKILL.md
```

- [ ] **Step 6: Verify legacy recovery workflow still accessible**

```bash
H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
LEGACY_CLI="$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py"
$LEGACY_CLI convert --help
$LEGACY_CLI upload --help
$LEGACY_CLI sync --help
$LEGACY_CLI webhook-server --help
```

Expected: all four print help without error. If any fails, STOP — #149 hard non-regression violated.

- [ ] **Step 7: Per-task verification (A/B/C/D)**

Expected: A shows only `M plugins/h2t-ops/skills/meetgeek/SKILL.md`; B/C/D green.

- [ ] **Step 8: Commit (T3)**

```bash
git add plugins/h2t-ops/skills/meetgeek/SKILL.md
git diff --cached --stat
```

```bash
git commit -m "docs(meetgeek): skill delegates to h2t-ops meetgeek ... (#134)

Rewrite SKILL.md: migrated verbs (auth-check, teams, list, get,
transcript, summary, highlights, insights, download-url, submit-url)
now delegate to h2t-ops meetgeek <verb>.

upload --download-url becomes a compatibility alias: SKILL.md routes it
to 'h2t-ops meetgeek submit-url'; legacy _post_upload no longer called
for this path after this commit.

Legacy section preserved with explicit pointer to #149:
- convert, drive-upload, upload --from-file (recovery pipeline)
- sync (lake/coordinator, not connector)
- webhook-server (dev-only; production = future POS/VPS)

Skill version 1.1.0 → 1.2.0 (partial delegation is a contract change)."
```

---

## Task 4: Closure — full sweep + live smoke + evidence (STOP)

**Files:** None modified (verification + evidence assembly only).

- [ ] **Step 1: Full mocked test sweep**

```bash
uv run h2t-ops dev pytest tests/core tests/connectors -v
```

Record: total count, pass/fail.
Expected: pre-#134 baseline + ≈ 28 (T1 client) + ≈ 18 (T2 commands) net-new.

- [ ] **Step 2: `dev check lazy-registry`**

```bash
uv run h2t-ops dev check lazy-registry
```

Expected: `OK lazy-registry`.

- [ ] **Step 3: Runbook §4 9-item gate self-review**

| Gate | #134 Evidence |
|---|---|
| 1 legacy parity | T1 MeetGeekClient: 10 verbs re-wrapped |
| 2 provider API gaps | sync, webhook, upload --from-file NOT addressed — tracked #149/POS |
| 3 auth/secrets | load_secrets() lazy in __init__; ConfigError with hint on missing key |
| 4 lazy imports | No module-level requests in connectors/meetgeek/*; lazy-registry OK |
| 5 tests | T1 ≈ 28 client + T2 ≈ 18 commands net-new |
| 6 live smoke | Step 4 below |
| 7 POS boundary | No ~/.dor writes; no DOR_ROOT/VAULT_ROOT/MEETINGS_DIR; no sync/manifest |
| 8 dist-without-POS | No pos/dor.db/vault/lake imports in new files |
| 9 write side effects | submit-url is only write verb; requires explicit URL arg; not auto-triggered |

- [ ] **Step 4: Install and run read-only live smoke**

```bash
uv tool install --reinstall "C:/dev/h2t-skills"
```

```bash
h2t-ops --version
h2t-ops doctor
h2t-ops connectors
h2t-ops meetgeek --help
h2t-ops meetgeek auth-check
```

```bash
h2t-ops meetgeek list --limit 2 --json 2>&1 | head -c 600
h2t-ops meetgeek teams --json 2>&1 | head -c 400
```

Pass criteria:
- `--version`, `doctor`, `connectors`, `meetgeek --help` exit 0; `connectors` lists `meetgeek`.
- `auth-check` exits 0 (valid key) or exits 1 with AuthError (key missing/invalid — not a code failure).
- `list --json` exits 0 with valid JSON, or exits 3 with ConfigError if key missing.
- Token-leak scan over stdout: `MEETGEEK_API_KEY|Bearer [A-Za-z0-9._\-]{20,}` → must be empty.

Live `submit-url` is **not** part of automatic smoke — it is a provider write and runs only if the user explicitly requests it.

- [ ] **Step 5: Verify #149 non-regression**

```bash
H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py convert --help
$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --help
$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py sync --help
$H2T_PYTHON plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py webhook-server --help
```

All four must print help without error. If any fails, STOP — #149 non-regression violated before push.

- [ ] **Step 6: Prepare evidence block (DO NOT POST, DO NOT PUSH)**

Format ready-to-paste on #134:

```md
## #134 MeetGeek parity — local evidence (not yet posted)

Date: 2026-05-20
Machine: AUTOMATA
Source: local C:/dev/h2t-skills (commits T1: <sha>, T2: <sha>, T3: <sha>; not pushed)

### Mocked tests
- `tests/core tests/connectors`: <N> passed, 0 failed (+<delta> vs pre-#134).
- `uv run h2t-ops dev check lazy-registry`: OK lazy-registry.

### Live read-only smoke
- `h2t-ops --version`: exit 0
- `h2t-ops doctor`: exit 0
- `h2t-ops connectors`: exit 0, lists notion / gmail / calendar / drive / meetgeek
- `h2t-ops meetgeek --help`: exit 0, 10 verbs listed
- `h2t-ops meetgeek auth-check`: exit <0|1>, <ok|key missing>
- `h2t-ops meetgeek list --limit 2 --json`: exit <0|3>, <JSON rows|ConfigError>
- `h2t-ops meetgeek teams --json`: exit <0|3>

### #149 non-regression
- `meetgeek_cli.py convert --help`: exit 0
- `meetgeek_cli.py upload --help`: exit 0 (--from-file visible)
- `meetgeek_cli.py sync --help`: exit 0
- `meetgeek_cli.py webhook-server --help`: exit 0

### Guards
- Token leak scan: <empty|hits>
- File scope: git log T1^..T3 --name-only — all within plan's file map.

### Runbook §4 9-item gate
(paste table from Step 3)

### Follow-ups deferred (not part of #134)
- #149 — local recording recovery workflow extraction (convert + drive-upload + upload --from-file + manifest/resume).
- sync migration — #149 / future.
- webhook-server — future POS/VPS.
- Drive client de-duplication in meetgeek_cli.py:612–755 — #149.
```

- [ ] **Step 7: Final report — STOP**

Surface in reply: T1/T2/T3 SHAs, test count, lazy-registry result, live smoke exit codes, #149 non-regression verdict, evidence block, and explicit:

> "Did NOT push. Did NOT post any GitHub comment. Did NOT close #134. STOPPING for maintainer approval."

---

## Constraints recap (every task)

- Re-wrap not rewrite; three-file pattern verbatim.
- No module-level `requests` anywhere in `h2t_ops/connectors/meetgeek/`.
- No POS imports, no `~/.dor` writes, no DOR_ROOT/VAULT_ROOT/MEETINGS_DIR.
- `list_meetings()` returns raw rows — normalization in commands layer only.
- `get_download_url()` returns URL only — never writes binary to disk.
- `submit_url()` is the only write verb; `upload --from-file` pipeline is #149.
- `sync` and `webhook-server` are NOT migrated.
- `upload --download-url` becomes compatibility alias → `h2t-ops meetgeek submit-url` in T3.
- Stage only named task files per task; never `git add -A`.
- Outward-facing actions (push, GitHub comment, close issue) are user-gated.
- #149 is a hard non-regression: `convert`, `drive-upload`, `upload --from-file`, `sync`, `webhook-server` must remain accessible via legacy script throughout #134.
