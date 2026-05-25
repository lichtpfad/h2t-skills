---
title: "TZ-1 Gmail Connector Implementation Plan"
status: "draft"
date: "2026-05-19"
milestone: ""
---
# TZ-1 Gmail Connector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Gmail from legacy `lib/clients/gmail.py` + `h2t ingest gmail` to the `h2t_ops` connector standard (`h2t-ops gmail …`) as the first TZ-1 connector, mirroring the Notion walking skeleton.

**Architecture:** New `h2t_ops/connectors/gmail/{__init__.py, client.py, commands.py}` mirroring `connectors/notion/`. `client.py` is a **re-wrap** of `lib/clients/gmail.py` (spec §10.1: API/auth/pagination logic byte-identical; only `print`/`sys.exit`/raw `Exception` replaced by typed `core.errors`). The interactive OAuth fallback (`flow.run_local_server`) is **removed and converted to `ConfigError`** — this is **spec §4.1 enforcement** ("expensive SDK construction/auth deferred; no OAuth/network at non-interactive CLI"), NOT a §10 deviation: the token-load and refresh branches stay byte-identical, only the terminal "no creds AND no refresh token" branch changes its side effect. `commands.py` carries argparse only at module scope (no client import); `cli.py` gains `gmail` in `_MIGRATED` plus an `ingest gmail` deprecation shim per §10.2. Legacy `lib/` and the standalone `plugins/h2t/skills/gmail/scripts/gmail_cli.py` are **not touched** — `h2t ingest gmail`, `gmail_cli.py`, and `tests/clients/test_gmail.py` + `tests/cli/test_ingest_cli.py` keep working by construction.

**Tech Stack:** Python 3.11, argparse, pytest, `google-api-python-client` / `google-auth` / `google-auth-oauthlib` (declared in `[project.dependencies]`, mirroring how Notion declares `notion-client`/`httpx`; client still does a defensive lazy import → `ConfigError` per §4.1). Execution contract: `uv run h2t-ops dev pytest …` (never raw Python paths).

---

## Provenance / Constraints (read before Task 1)

- **Re-wrap source of truth:** `lib/clients/gmail.py` only. Do NOT modify `lib/clients/gmail.py`, `lib/cli/main.py`, or `plugins/h2t/skills/gmail/scripts/gmail_cli.py`. The standalone `gmail_cli.py` is self-contained (its own inline `GmailClient`) — its contract is preserved trivially by leaving it alone.
- **Shared Google auth:** `_get_service`'s config-dir lookup (`~/.config/google-calendar-mcp` → fallback `~/.config/gmail`, plural `tokens.json` vs `token.json`, the `"normal"` nested-format normalization, scope merge) is **byte-identical** in the re-wrap. Calendar (TZ-1, #132) depends on this exact prefix lookup.
- **`read --format plain|json`:** legacy had `--format plain|json`. The connector standard (spec §6) is `--json` / `--format md` / human-default. Do NOT reproduce a `plain` choice — human default replaces it. JSON via `--json`. Markdown detail via `--format md`.
- **Baseline (verified 2026-05-19 on this worktree):** `uv run h2t-ops dev pytest tests/core tests/connectors -q` → **63 passed**. The full `tests` tree does NOT collect under `uv run` (pre-existing: `tests/clients/test_gmail.py`/`test_calendar.py` need `google`, `tests/h2t_creative` needs `yaml`) — scope every baseline/regression run to `tests/core tests/connectors`.
- **Notion reference files** to mirror: `h2t_ops/connectors/notion/{__init__.py,client.py,commands.py}`, `tests/connectors/notion/{test_client.py,test_commands.py}`, `plugins/h2t-ops/skills/notion/SKILL.md`.

## File Structure

| File | Responsibility |
|---|---|
| `h2t_ops/connectors/gmail/__init__.py` | `CONNECTOR = ConnectorSpec(...)`; `from .commands import register` (no heavy imports) |
| `h2t_ops/connectors/gmail/commands.py` | argparse `register()` at module scope; `run(args)` dispatch, lazy client import, render via format helpers; raises `core.errors` |
| `h2t_ops/connectors/gmail/client.py` | re-wrapped `GmailClient` + `_map_http_error` + module-level `format_message_list`/`format_message_detail`; typed `core.errors`; no argparse/print/sys.exit |
| `h2t_ops/cli.py` | add `"gmail"` to `_MIGRATED`; add `ingest gmail` deprecation shim (§10.2) |
| `pyproject.toml` | add google-* to `[project.dependencies]` |
| `tests/connectors/gmail/__init__.py` | package marker |
| `tests/connectors/gmail/test_client.py` | API coverage (mocked) + each typed error + non-interactive guarantee |
| `tests/connectors/gmail/test_commands.py` | CLI contract: subcmds, `--json`/`--format`, run dispatch, shim, help exit 0, lazy discipline |
| `plugins/h2t-ops/skills/gmail/SKILL.md` | §8 contract (mirror notion SKILL.md) |

---

### Task 1: Connector registry wiring (`__init__.py` + `commands.py` skeleton)

**Files:**
- Create: `h2t_ops/connectors/gmail/__init__.py`
- Create: `h2t_ops/connectors/gmail/commands.py`
- Create: `tests/connectors/gmail/__init__.py`
- Test: `tests/connectors/gmail/test_commands.py`

- [ ] **Step 1: Write the failing test**

`tests/connectors/gmail/__init__.py` → empty file.

`tests/connectors/gmail/test_commands.py`:

```python
import argparse
import sys
import builtins
from h2t_ops.connectors.gmail.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t-ops")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_gmail_subcommands():
    ns = _parser().parse_args(["gmail", "list", "--max", "5"])
    assert ns.connector == "gmail" and ns.gmail_cmd == "list" and ns.max == 5


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["gmail", "list", "--json"]).as_json is True
    assert p.parse_args(["gmail", "read", "MID", "--format", "md"]).fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    # delitem (not raw pop) so the popped client module is restored at
    # teardown -- a raw pop leaks a sys.modules-vs-package-attr desync that
    # breaks string-target monkeypatching in later tests.
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t_ops.connectors.gmail.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t_ops.connectors.gmail.commands"))
    assert seen["client"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t-ops dev pytest tests/connectors/gmail/test_commands.py -q`
Expected: FAIL — `ModuleNotFoundError: h2t_ops.connectors.gmail`.

- [ ] **Step 3: Write minimal implementation**

`h2t_ops/connectors/gmail/commands.py` (mirror notion `commands.py`; argparse only at module scope):

```python
"""Gmail CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from typing import Any

PROVIDER = "gmail"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("gmail", help="Work with Gmail messages and labels")
    cmds = p.add_subparsers(dest="gmail_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown detail, human = concise (default)")

    lp = cmds.add_parser("list", help="List messages")
    lp.add_argument("--max", type=int, default=10)
    lp.add_argument("--unread", action="store_true")
    lp.add_argument("--query", default=None); add_fmt(lp)

    rp = cmds.add_parser("read", help="Read a message")
    rp.add_argument("message_id"); add_fmt(rp)

    sp = cmds.add_parser("search", help="Search messages")
    sp.add_argument("query"); sp.add_argument("--max", type=int, default=10); add_fmt(sp)

    snp = cmds.add_parser("send", help="Send a message")
    snp.add_argument("to"); snp.add_argument("subject"); snp.add_argument("body", nargs="?")
    snp.add_argument("--file"); snp.add_argument("--attach", nargs="+")
    snp.add_argument("--draft", action="store_true"); add_fmt(snp)

    dp = cmds.add_parser("draft", help="Create a draft")
    dp.add_argument("to"); dp.add_argument("subject"); dp.add_argument("body", nargs="?")
    dp.add_argument("--file"); dp.add_argument("--attach", nargs="+")
    dp.add_argument("--thread-id", dest="thread_id")
    dp.add_argument("--reply-to", dest="reply_to"); add_fmt(dp)

    lbl = cmds.add_parser("labels", help="List all labels"); add_fmt(lbl)

    lm = cmds.add_parser("label", help="Modify message labels")
    lm.add_argument("message_id"); lm.add_argument("--add", nargs="+")
    lm.add_argument("--remove", nargs="+"); add_fmt(lm)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    raise NotImplementedError  # body filled in Task 5
```

> **Defect mirror (Task 1 code-quality review):** do NOT add `# noqa: C901` to the
> stub — it suppresses nothing on a complexity-1 body and diverges from the bare
> Notion `def run(args) -> Any:` reference. If Task 5's real dispatch body trips
> C901, add the suppression there, against real code.

`h2t_ops/connectors/gmail/__init__.py` (mirror notion `__init__.py`):

```python
"""Gmail connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="gmail",
    help="Work with Gmail messages and labels",
    client="h2t_ops.connectors.gmail.client:GmailClient",  # lazy ref (spec §4.1)
    register=register,
)
```

`tests/connectors/gmail/__init__.py` → empty.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t-ops dev pytest tests/connectors/gmail/test_commands.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/__init__.py h2t_ops/connectors/gmail/commands.py tests/connectors/gmail/__init__.py tests/connectors/gmail/test_commands.py
git commit -m "feat(gmail): connector registry wiring + argparse skeleton (TZ-1 #131)"
```

---

### Task 2: `client.py` — auth re-wrap (§4.1 enforcement)

**Files:**
- Create: `h2t_ops/connectors/gmail/client.py`
- Test: `tests/connectors/gmail/test_client.py`

**Re-wrap rules for `_get_service` (transcribe from `lib/clients/gmail.py:50-109`):**
- Module-level `from dotenv import load_dotenv; load_dotenv(...)` and `import google.*` → move **inside** `__init__`/`_get_service`; wrap the google import in `try/except ImportError → ConfigError(hint="pip install google-api-python-client google-auth google-auth-oauthlib  (or run /h2t-core:setup)")`.
- Config-dir lookup, token-load, `"normal"` nested-format normalization, scope merge, `Credentials.from_authorized_user_info`, the `creds.refresh(Request())` branch: **byte-identical** logic.
- `print("Warning: Could not load token…")` → drop the print; keep `creds = None`.
- `creds.refresh` failure: `raise AuthError(f"Gmail token refresh failed: {e}", hint="delete the token file and re-run interactive auth")` (was `RuntimeError`).
- Missing `credentials.json` (was `FileNotFoundError`/`sys.exit(1)`) → `raise ConfigError(f"Gmail credentials.json not found at {creds_path}.", hint="Download OAuth credentials from Google Cloud Console to ~/.config/gmail/ (or ~/.config/google-calendar-mcp/)")`.
- **The interactive branch** (`flow = InstalledAppFlow.from_client_secrets_file(...); creds = flow.run_local_server(port=0)`): **removed**. Replace with `raise ConfigError("Gmail not authenticated and no refresh token available.", hint="Bootstrap credentials interactively once via the legacy gmail skill, then ~/.config/gmail/token.json is reused.")`. Comment it: `# §4.1 enforcement: a non-interactive connector CLI MUST NOT launch a browser OAuth flow.`

- [ ] **Step 1: Write the failing test**

`tests/connectors/gmail/test_client.py`:

```python
import sys
import builtins
import pytest


def test_missing_google_libs_raises_configerror(monkeypatch):
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise ImportError(f"No module named {name!r}")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    from h2t_ops.connectors.gmail.client import GmailClient
    from h2t_ops.core.errors import ConfigError
    with pytest.raises(ConfigError):
        GmailClient()


def test_no_creds_no_refresh_raises_configerror_not_browser(monkeypatch, tmp_path):
    """§4.1 enforcement: must raise ConfigError, must NOT launch run_local_server.

    Create credentials.json so delta-4 (missing-creds) is skipped, AND stub
    `_load_credentials -> None` so delta-1 (missing google libs) is skipped —
    only then does control reach the §4.1 branch and the no-browser assertion
    become meaningful.
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import ConfigError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text("{}")
    monkeypatch.setattr(gmod.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(gmod, "_load_credentials", lambda *a, **k: None)

    launched = {"browser": False}

    class _Flow:
        @staticmethod
        def from_client_secrets_file(*a, **k):
            launched["browser"] = True
            raise AssertionError("run_local_server must never be reached")

    monkeypatch.setattr(gmod, "_install_app_flow", lambda: _Flow)
    with pytest.raises(ConfigError):
        gmod.GmailClient()
    assert launched["browser"] is False


def test_refresh_failure_raises_autherror(monkeypatch, tmp_path):
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import AuthError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text('{"installed":{"client_id":"x","client_secret":"y"}}')
    (cfg / "token.json").write_text('{"refresh_token":"r","client_id":"x","client_secret":"y","scopes":["s"]}')
    monkeypatch.setattr(gmod.Path, "home", staticmethod(lambda: tmp_path))

    class _Creds:
        valid = False
        expired = True
        refresh_token = "r"
        def refresh(self, _req): raise RuntimeError("invalid_grant")

    monkeypatch.setattr(gmod, "_load_credentials", lambda *a, **k: _Creds())
    # Seam (discretion): stub the lazy Request() import — google libs absent in test env.
    monkeypatch.setattr(gmod, "_request", lambda: object())
    with pytest.raises(AuthError):
        gmod.GmailClient()
```

> **Defect mirror (Task 2 code-quality review):** do NOT pass `raising=False` to
> the seam `monkeypatch.setattr`s. The seams exist in production, so `raising=False`
> is a no-op today but lets a future rename/delete of a seam (esp. the
> never-production-called `_install_app_flow`) pass silently — the test is the only
> pin on that seam. In `client.py`, add a one-line comment at the `_request()` seam
> (`# test seam: lazy Request() — google libs absent until Task 7 declares deps`)
> and at the §10.1-locked bare `except Exception:` in `_load_credentials`
> (`# delta 2: legacy printed a warning here; dropped per §10.1, creds=None kept`).
> Do NOT narrow the `except` — that breaks byte-identical fidelity (accepted
> tradeoff). Sibling Google connectors (#132 Calendar) inherit these.

> **Defect mirror (Task 2 spec review — CONFIRMED via two-way discriminator):**
> The original plan draft of `test_no_creds_no_refresh…` (no `credentials.json`,
> real `_load_credentials`) was a **non-functional §4.1 guard**: with google libs
> absent it short-circuits at delta 1, and even with them it short-circuits at
> delta 4 — the §4.1 branch is never reached, so the test passed even when the
> legacy `flow.run_local_server` branch was restored. Fixed above (create
> `credentials.json` + stub `_load_credentials → None`). `test_refresh_failure…`
> additionally needs a third `_request()` seam because google libs are absent in
> the `uv run` env until Task 7 — without it the byte-identical
> `creds.refresh(_request())` raises `ConfigError`, masking the asserted
> `AuthError`. **Sibling-connector note:** Calendar (#132) and any Google
> connector plan reusing this auth test pattern MUST carry the same three fixes.
>
> **Implementer seam discipline:** `_install_app_flow()`, `_load_credentials(...)`,
> `_request()` are thin module-level indirections wrapping byte-identical logic —
> test seams, NOT logic changes. The 3 behavioral assertions must still hit real
> code paths: ConfigError on missing libs; ConfigError + no-browser on
> no-creds/no-refresh; AuthError on refresh fail.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py -q`
Expected: FAIL — `ModuleNotFoundError: h2t_ops.connectors.gmail.client`.

- [ ] **Step 3: Write minimal implementation**

Create `h2t_ops/connectors/gmail/client.py`: transcribe `GmailClient.__init__`/`_get_service` and the `SCOPES`, `_attach_file`, `_parse_message`, `_get_message_body`, `_html_to_text`, `format_message_list`, `format_message_detail` from `lib/clients/gmail.py` **verbatim**, applying only the Task-2 auth re-wrap rules above. Wrap google imports lazily. Expose `_install_app_flow()` / `_load_credentials(...)` / `_request()` thin module-level seams around the (now ConfigError-raising) terminal branch, the credentials construction, and the lazy `Request()` import so the logic is unit-testable without google libs. `from h2t_ops.core.errors import AuthError, ConfigError`. Read/write API methods are added in Tasks 3–4 (leave them out or stubbed `raise NotImplementedError` for now — Step 4 only needs auth paths).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/client.py tests/connectors/gmail/test_client.py
git commit -m "feat(gmail): re-wrap auth — typed errors + §4.1 non-interactive enforcement (#131)"
```

---

### Task 3: `client.py` — read methods + HTTP error mapping

**Files:**
- Modify: `h2t_ops/connectors/gmail/client.py`
- Test: `tests/connectors/gmail/test_client.py`

**Re-wrap (transcribe `list_messages`/`get_message`/`search_messages`/`list_labels` from `lib/clients/gmail.py:113-149` verbatim; replace `except HttpError as e: raise Exception(...)` with `raise _map_http_error(e, op=...) from e`).**

`_map_http_error` (mirror notion `_map_sdk_exc`, but for `googleapiclient.errors.HttpError` whose status is `e.resp.status` / `e.status_code`):

```python
def _map_http_error(e: Exception, *, op: str):
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
```

- [ ] **Step 1: Write the failing test** — append to `tests/connectors/gmail/test_client.py`:

```python
import types


class _FakeService:
    def __init__(self, **resp): self._r = resp
    def users(self): return self
    def messages(self): return self
    def labels(self): return self
    def list(self, **k): return _Exec(self._r.get("list", {}))
    def get(self, **k): return _Exec(self._r.get("get", {}))


class _Exec:
    def __init__(self, v): self._v = v
    def execute(self): return self._v


def _client_with(service):
    from h2t_ops.connectors.gmail import client as gmod
    c = gmod.GmailClient.__new__(gmod.GmailClient)  # bypass __init__/_get_service
    c.service = service
    return c, gmod


def test_list_messages_happy():
    svc = _FakeService(list={"messages": [{"id": "1"}]},
                       get={"id": "1", "threadId": "t", "labelIds": [], "snippet": "",
                            "payload": {"headers": [{"name": "Subject", "value": "S"}]}})
    c, _ = _client_with(svc)
    out = c.list_messages(max_results=1)
    assert out[0]["id"] == "1" and out[0]["subject"] == "S"


def test_get_message_404_maps_notfound(monkeypatch):
    from h2t_ops.core.errors import NotFoundError

    class _HttpErr(Exception):
        resp = types.SimpleNamespace(status=404)

    class _Svc(_FakeService):
        def get(self, **k):
            raise _HttpErr("not found")

    c, gmod = _client_with(_Svc())
    monkeypatch.setattr(gmod, "HttpError", _HttpErr)
    with pytest.raises(NotFoundError):
        c.get_message("missing")


@pytest.mark.parametrize("status,exc_name", [
    (401, "AuthError"), (403, "AuthError"), (404, "NotFoundError"),
    (500, "ProviderError"), (503, "ProviderError"), (0, "ProviderError"),
])
def test_map_http_error_status_branches(status, exc_name):
    from h2t_ops.connectors.gmail import client as gmod
    import h2t_ops.core.errors as errs
    e = type("_E", (Exception,), {"resp": types.SimpleNamespace(status=status)})("boom")
    assert isinstance(gmod._map_http_error(e, op="x"), getattr(errs, exc_name))


def test_map_http_error_network_substring():
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import NetworkError
    assert isinstance(gmod._map_http_error(Exception("connection timed out"), op="x"),
                      NetworkError)


def test_map_http_error_passthrough_does_not_downgrade():
    """ТЗ-0 CRITICAL: an already-typed H2TError must pass through unchanged."""
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import NotFoundError
    nf = NotFoundError("x")
    assert gmod._map_http_error(nf, op="y") is nf
```

> **Implementer note:** `except HttpError` must catch the real `googleapiclient.errors.HttpError`. Bind `HttpError` lazily (module sentinel + one-shot bind after `build()`, or equivalent lazy seam — same §4.1 discipline) so `monkeypatch.setattr(gmod, "HttpError", ...)` works; `_map_http_error` dispatches on `.resp.status`. Keep `_parse_message`/`_get_message_body` byte-identical (already present from Task 2).
>
> **Defect mirror (Task 3 code-quality review):** (1) Do NOT pass `raising=False` to the `HttpError` `monkeypatch.setattr` — `HttpError` is a real module attr, so `raising=False` only silences a future rename (same precedent as Task 2's seam-pin hardening). (2) `_client_with` must NOT take an unused `monkeypatch` param. (3) `_map_http_error` is the ТЗ-0-CRITICAL error-downgrade trust boundary — it MUST have direct branch coverage incl. the `isinstance(H2TError) → return e` passthrough (the 3 added `test_map_http_error_*` tests above), not only the indirect 404-via-`get_message` path. Sibling Google connectors (#132 Calendar) inherit this test shape.

- [ ] **Step 2: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py -q` → FAIL (`list_messages` NotImplemented / AttributeError).

- [ ] **Step 3: Implement** read methods + `_map_http_error` per above.

- [ ] **Step 4: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py -q` → all passed.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/client.py tests/connectors/gmail/test_client.py
git commit -m "feat(gmail): re-wrap read methods + typed HTTP error mapping (#131)"
```

---

### Task 4: `client.py` — write methods + attachment error

**Files:**
- Modify: `h2t_ops/connectors/gmail/client.py`
- Test: `tests/connectors/gmail/test_client.py`

**Re-wrap (transcribe `send_message`/`modify_labels`/`_attach_file` from `lib/clients/gmail.py:153-263` verbatim; `except HttpError → _map_http_error`; `_attach_file`'s `FileNotFoundError("Attachment not found…")` → `raise UsageError(f"attachment not found: {file_path}")`).** MIME assembly, base64, draft-vs-send, thread/reply headers: byte-identical.

- [ ] **Step 1: Write the failing test** — append:

```python
def test_send_message_happy():
    sent = {}

    class _Svc(_FakeService):
        def send(self, userId, body): sent.update(body); return _Exec({"id": "m1"})

    c, _ = _client_with(_Svc())
    out = c.send_message(to="a@b.com", subject="S", body="B")
    assert out["id"] == "m1" and "raw" in sent


def test_draft_with_thread_and_reply_header():
    created = {}

    class _Svc(_FakeService):
        def drafts(self): return self
        def create(self, userId, body): created.update(body); return _Exec({"id": "d1"})

    c, _ = _client_with(_Svc())
    out = c.send_message(to="a@b.com", subject="S", body="B", as_draft=True,
                         thread_id="T", reply_to_message_id="<mid@x>")
    assert out["id"] == "d1" and created["message"]["threadId"] == "T"
    import base64
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    assert "In-Reply-To: <mid@x>" in raw and "References: <mid@x>" in raw


def test_attachment_not_found_raises_usageerror():
    from h2t_ops.core.errors import UsageError
    c, _ = _client_with(_FakeService())
    with pytest.raises(UsageError):
        c.send_message(to="a@b.com", subject="S", body="B",
                       attachments=["/no/such/file.bin"])
```

> **Defect mirror (Task 4 reviews):** (1) Plan draft used the pre-Task-3
> `_client_with(monkeypatch, …)` signature — the real helper is
> `_client_with(service)` (no `monkeypatch`); these tests reflect the corrected
> signature. (2) Code-quality: the SEND-only happy test left the DRAFT/`thread_id`/
> `reply_to_message_id` header path uncovered — `test_draft_with_thread_and_reply_header`
> closes it (same coverage-discipline as Task 3's `_map_http_error` tests).
> (3) Separately, in `client.py` the email-MIME imports' `# noqa: F401  (used by
> Task 3-4 helpers)` parenthetical is now FALSE (Task 4 makes `MIMEMultipart`/
> `MIMEText` directly used by `send_message`) — drop the dead `# noqa: F401`
> comment. Sibling Google connectors (#132 Calendar) inherit these.

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** write methods per re-wrap rules.
- [ ] **Step 4: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py -q` → all passed.
- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/client.py tests/connectors/gmail/test_client.py
git commit -m "feat(gmail): re-wrap write methods + attachment UsageError (#131)"
```

---

### Task 5: `commands.py` — `run()` dispatch + rendering

**Files:**
- Modify: `h2t_ops/connectors/gmail/commands.py`
- Test: `tests/connectors/gmail/test_commands.py`

**`run(args)` mirrors notion `commands.run`: lazy `from h2t_ops.connectors.gmail.client import GmailClient, format_message_list, format_message_detail`; build client; dispatch on `args.gmail_cmd`; return raw objects when `_fmt(args)=="json"`, else rendered string.** Mapping (legacy `_cmd_gmail` semantics, output via `core.output.emit` upstream in `cli.py`):

- `list`/`search`: `msgs = client.list_messages(...)` / `search_messages(...)`; json → return `msgs`; else → `format_message_list(msgs)`.
- `read`: `msg = client.get_message(args.message_id)`; json → return `msg`; `fmt=="md"` → `format_message_detail(msg)`; human → `format_message_detail(msg)` (same renderer; `plain` NOT reproduced).
- `send`/`draft`: resolve body as **`body = _read_file(args.file) if args.file else args.body`** (legacy `--file` OVERRIDES a positional body — and this matches notion's own `create`/`update` idiom; do NOT use `args.body or _read_file(...)`, which silently ignores `--file` when both are given); empty → `raise UsageError(f"{cmd}: provide body arg or --file")` (use `{cmd}` so the `draft` path doesn't mis-say "send:"); `as_draft = args.gmail_cmd=="draft" or getattr(args,"draft",False)`; call `client.send_message(...)`; json → `{"id": result["id"], "draft": as_draft}`, else `✓ {'Draft created' if as_draft else 'Message sent'} (ID: {id})` (legacy tone).
- `labels`: `client.list_labels()` → json returns list; else legacy tone: `Found N label(s):\n` header + `- {name} (ID: {id})` lines (NOT `"- name (id)"` — legacy `_cmd_gmail` is the byte-exact tone source).
- `label`: `client.modify_labels(...)` → json `{"labelIds": result.get("labelIds", [])}`; else `✓ Labels modified. Current: {', '.join(labelIds)}` (legacy tone).
- `_read_file` helper identical to notion's (`Path(path).read_text("utf-8")`, `FileNotFoundError → UsageError(f"file not found: {path}")`).

> **Defect mirror (Task 5 code-quality review):** the original plan draft said
> `body = args.body or _read_file(args.file)` and `UsageError("send: …")` and a
> `"- name (id)"` label shorthand. All three diverged from legacy `_cmd_gmail`
> (`lib/cli/main.py`): (1) legacy `--file` OVERRIDES positional body — corrected
> to `_read_file(args.file) if args.file else args.body` (also the notion
> `create`/`update` idiom); (2) the error must not hardcode `"send:"` on the
> shared send/draft block — use `f"{cmd}:"`; (3) labels/label/confirmation
> strings are byte-identical to legacy tone. Sibling Google connectors
> (#132 Calendar) inherit the `_read_file`-override precedence + `{cmd}` lesson.

- [ ] **Step 1: Write the failing test** — append to `tests/connectors/gmail/test_commands.py`:

```python
import types
import pytest
from h2t_ops.connectors.gmail import commands as gc
from h2t_ops.core.errors import UsageError


class _FakeClient:
    def list_messages(self, **k): return [{"id": "1", "subject": "S", "from": "f",
                                           "date": "d", "snippet": "x", "labelIds": []}]
    def get_message(self, mid): return {"id": mid, "subject": "S", "from": "f",
                                        "to": "t", "date": "d", "labelIds": [], "body": "B"}
    def send_message(self, **k): return {"id": "m1"}


def _ns(**kw): return types.SimpleNamespace(**kw)


def _patch(monkeypatch):
    # Patch GmailClient on the LIVE client module object (resolves via
    # sys.modules, the same path run()'s lazy `from ...client import
    # GmailClient` uses). A string target would resolve via package attrs
    # and desync if an upstream test raw-popped the client from sys.modules.
    import h2t_ops.connectors.gmail.client as m
    monkeypatch.setattr(m, "GmailClient", lambda *a, **k: _FakeClient())


def test_list_json_returns_raw(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="list", max=10, unread=False, query=None,
                     as_json=True, fmt="human"))
    assert out == [{"id": "1", "subject": "S", "from": "f", "date": "d",
                    "snippet": "x", "labelIds": []}]


def test_read_human_returns_detail(monkeypatch):
    _patch(monkeypatch)
    out = gc.run(_ns(gmail_cmd="read", message_id="X", as_json=False, fmt="human"))
    assert "# S" in out and "B" in out


def test_send_no_body_raises_usageerror(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(UsageError):
        gc.run(_ns(gmail_cmd="send", to="a", subject="s", body=None, file=None,
                   attach=None, draft=False, as_json=False, fmt="human"))
```

- [ ] **Step 2: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_commands.py -q` → FAIL (`NotImplementedError`).
- [ ] **Step 3: Implement** `run()` per mapping above.
- [ ] **Step 4: Run** `uv run h2t-ops dev pytest tests/connectors/gmail -q` → all passed.
- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/gmail/commands.py tests/connectors/gmail/test_commands.py
git commit -m "feat(gmail): commands.run dispatch + rendering (#131)"
```

---

### Task 6: `cli.py` — register gmail + `ingest gmail` shim (§10.2)

**Files:**
- Modify: `h2t_ops/cli.py`
- Test: `tests/connectors/gmail/test_commands.py`

**Changes:**
1. `_MIGRATED = {"notion", "gmail"}`.
2. `_doctor()`: connectors loop already lists discovered connectors (gmail auto-appears via registry) — no change needed; add a secrets line `gmail: ~/.config/{gmail,google-calendar-mcp}/credentials.json present?` (best-effort, no network).
3. New shim branch in `dispatch`, **before** the generic `("gather","ingest")→_legacy` branch, mirroring the `ingest notion` block: when `argv[0]=="ingest" and argv[1]=="gmail"`, normalize legacy flags → connector flags: `--format json` → `--json`; `--format plain` → drop; legacy `--json` passes through unchanged (already the connector flag). Emit the one-line stderr deprecation notice when resolved format ≠ json; forward via `_run_connector(["gmail", *norm])`.

```python
    # ingest gmail shim → new connector (spec §10.2).
    # Gmail legacy accepted `--format plain` (& friends); notion did not — so we
    # consume ANY `--format <val>` (json→--json, others dropped), unlike the
    # notion shim above which only consumes json/markdown. Do not unify.
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "gmail":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest):
                if rest[j + 1] == "json":
                    norm.append("--json")
                # "plain" (and any non-json) → drop; connector human default
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            print("deprecated: `h2t-ops ingest gmail` → use `h2t-ops gmail` (spec §10)",
                  file=sys.stderr)
        return _run_connector(["gmail", *norm])
```

- [ ] **Step 1: Write the failing test** — append to `tests/connectors/gmail/test_commands.py`:

```python
from h2t_ops.cli import dispatch


def test_gmail_help_exits_zero(capsys):
    assert dispatch(["gmail", "--help"]) == 0
    assert "gmail" in capsys.readouterr().out


def test_gmail_subcommand_help_exits_zero():
    assert dispatch(["gmail", "list", "--help"]) == 0


def test_connectors_list_includes_gmail_no_heavy_import(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise AssertionError("connectors list must not import Google SDK")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert dispatch(["connectors"]) == 0
    assert "gmail" in capsys.readouterr().out


def test_ingest_gmail_shim_warns_on_human(monkeypatch, capsys):
    called = {}

    def fake_run(args):
        called["ran"] = True
        return "OK"

    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run", fake_run)
    code = dispatch(["ingest", "gmail", "list"])
    err = capsys.readouterr().err
    assert called.get("ran") is True and "deprecat" in err.lower() and code == 0


def test_ingest_gmail_shim_silent_on_json(monkeypatch, capsys):
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: [{"id": "1"}])
    code = dispatch(["ingest", "gmail", "list", "--json"])
    assert "deprecat" not in capsys.readouterr().err.lower() and code == 0


def test_ingest_gmail_shim_format_json_normalized_silent(monkeypatch, capsys):
    """`--format json` → `--json` → silent (regression-pins the gmail-only
    shim divergence: gmail consumes ANY `--format <val>`, notion only json/md)."""
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: [{"id": "1"}])
    code = dispatch(["ingest", "gmail", "list", "--format", "json"])
    assert "deprecat" not in capsys.readouterr().err.lower() and code == 0


def test_ingest_gmail_shim_format_plain_dropped_warns(monkeypatch, capsys):
    """`--format plain` dropped → human default → deprecation warning."""
    monkeypatch.setattr("h2t_ops.connectors.gmail.commands.run",
                        lambda a: "OK")
    code = dispatch(["ingest", "gmail", "list", "--format", "plain"])
    assert "deprecat" in capsys.readouterr().err.lower() and code == 0
```

- [ ] **Step 2: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_commands.py -q` → FAIL (shim/`_MIGRATED` not wired; `gmail --help` falls to `_legacy`).
- [ ] **Step 3: Implement** the 3 `cli.py` changes above.
- [ ] **Step 4: Run** `uv run h2t-ops dev pytest tests/core tests/connectors -q` → all passed (63 + new gmail tests, 0 fail; notion tests unaffected).
- [ ] **Step 5: Commit**

```bash
git add h2t_ops/cli.py tests/connectors/gmail/test_commands.py
git commit -m "feat(gmail): register in _MIGRATED + ingest gmail deprecation shim (#131)"
```

---

### Task 7: Declare Google deps in `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (regenerated)

- [ ] **Step 1: Write the failing test** — append to `tests/connectors/gmail/test_client.py`:

```python
def test_google_deps_declared_in_pyproject():
    import tomllib
    from pathlib import Path
    # test_client.py is <root>/tests/connectors/gmail/ → parents[3] = <root>
    # (parents[2] = tests/, which has no pyproject.toml).
    root = Path(__file__).resolve().parents[3]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    # Match on parsed dep NAMES, not substring-in-joined-string: a bare
    # `"google-auth" in joined` falsely passes when only the longer
    # `google-auth-oauthlib` is present (substring match).
    names = {d.split(">=")[0].split("==")[0].strip().lower()
             for d in data["project"]["dependencies"]}
    assert "google-api-python-client" in names
    assert "google-auth" in names
    assert "google-auth-oauthlib" in names
```

> **Defect mirror (Task 7 reviews):** the plan draft had two bugs reused by
> sibling connectors if uncorrected — (1) `parents[2]` resolves to `tests/`,
> not repo root → must be `parents[3]`; (2) `" ".join(deps)` substring asserts
> false-pass (`"google-auth"` ⊂ `"google-auth-oauthlib"`) → assert against the
> parsed dep-name set. Both fixed above. (Code-quality also noted this packaging
> assertion lives in `test_client.py`; acceptable for the chore — notion has no
> equivalent and a dedicated packaging-test file would be net scope; left as-is.)

- [ ] **Step 2: Run** `uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py::test_google_deps_declared_in_pyproject -q` → FAIL (KeyError/assert).

- [ ] **Step 3: Implement** — add to `pyproject.toml` `[project] dependencies` (alongside notion-client/httpx):

```toml
  "google-api-python-client>=2.0",
  "google-auth>=2.0",
  "google-auth-oauthlib>=1.0",
```

Then regenerate the lock: `uv lock`.

- [ ] **Step 4: Run** `uv run h2t-ops dev pytest tests/core tests/connectors -q` → all passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/connectors/gmail/test_client.py
git commit -m "chore(gmail): declare google-api deps for h2t-ops (#131)"
```

---

### Task 8: `SKILL.md` → §8 contract

**Files:**
- Modify: `plugins/h2t-ops/skills/gmail/SKILL.md`

- [ ] **Step 1:** Read `plugins/h2t-ops/skills/notion/SKILL.md` and the current `plugins/h2t-ops/skills/gmail/SKILL.md`.

- [ ] **Step 2:** Rewrite `plugins/h2t-ops/skills/gmail/SKILL.md` mirroring the notion SKILL.md structure exactly: frontmatter (`name: gmail`, description with triggers incl. `h2t-ops:gmail`, `compatibility` line, `metadata.author: lichtpfad`, `version` bumped), Availability contract (`h2t-ops --version`), Secrets, Commands table (list/read/search/send/draft/labels/label with flags), Output flags, Examples, Exit codes table (0–6), When to use / not use, Deprecated section (`h2t-ops ingest gmail …` forwards, prints deprecation to stderr unless `--json`), and the **verbatim** umbrella note from spec §8:
  > In the internal umbrella CLI, `h2t gmail …` may be available later via h2t-ai delegation. Skills should call `h2t-ops …` directly unless a project explicitly provides the umbrella bridge.

  **Secrets section — must be agent-actionable (Task 8 code-quality defect mirror):** do NOT just say "bootstrap via the legacy gmail skill" (agent can't resolve that on exit-3 → dead end). State both exit-3 cases concretely, aligned with `client.py`'s actual ConfigError hints: (a) **missing `credentials.json`** → "Download OAuth credentials from Google Cloud Console to `~/.config/gmail/` (or `~/.config/google-calendar-mcp/`)"; (b) **have creds, no token + no refresh** (§4.1 no-browser) → first-time auth is a ONE-TIME interactive bootstrap run OUTSIDE this connector: run the standalone legacy script `plugins/h2t/skills/gmail/scripts/gmail_cli.py` once (e.g. `python …/gmail_cli.py labels`) — it performs the browser OAuth and writes `token.json`/`tokens.json`; thereafter `h2t-ops gmail` reuses & silently refreshes it. Paths: `~/.config/google-calendar-mcp/` (shared w/ calendar, `tokens.json` plural) or `~/.config/gmail/` (`token.json` singular) + `credentials.json`; missing/unauth → exit 3 `config`. **Commands/Examples polish (Minor mirror):** the `--query`/`search` doc must show a date/attachment operator example (e.g. `from:alice after:2024/01/01 has:attachment`) not just `from:… subject:…`; the `read` row description must note "use `--format md` for full formatted detail". Sibling Google connectors (#132 Calendar) inherit the concrete-bootstrap-instruction requirement (same OAuth model).

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/skills/gmail/SKILL.md
git commit -m "docs(gmail): SKILL.md to §8 connector contract (#131)"
```

---

### Task 9: DoD verification

**Files:** none (verification only)

- [ ] **Step 1:** `uv run h2t-ops --version` → exits 0.
- [ ] **Step 2:** `uv run h2t-ops gmail --help` → exits 0, shows subcommands.
- [ ] **Step 3:** `uv run python -c "from h2t_ops.connectors.gmail.client import GmailClient; print('ok')"` → ok.
- [ ] **Step 4:** `uv run h2t-ops connectors` → lists `gmail`. `uv run h2t-ops doctor` → mentions gmail.
- [ ] **Step 5:** `uv run h2t-ops dev pytest tests/core tests/connectors -q` → **all passed** (63 baseline + new gmail tests; 0 failures; notion unaffected).
- [ ] **Step 6:** Legacy untouched — `git diff --stat origin/main -- lib/ plugins/h2t/skills/gmail/` is **empty**.
- [ ] **Step 7:** Lazy discipline — the Task-6 `test_connectors_list_includes_gmail_no_heavy_import` is green (no Google SDK import on `connectors`).
- [ ] **Step 8:** Non-interactive guarantee — the Task-2 `test_no_creds_no_refresh_raises_configerror_not_browser` is green.
- [ ] **Step 9:** Final commit if any verification touched docs/notes; otherwise none.

---

## Self-Review (completed by plan author)

**Spec coverage vs issue #131 DoD:** "Create `h2t_ops/connectors/gmail/`" → Tasks 1–5. "Wrap existing Gmail API logic in `client.py`" → Tasks 2–4 (re-wrap, byte-identical logic). "Add `commands.py`, `CONNECTOR`, tests, and legacy shim" → Tasks 1,5,6. "Preserve config/auth behavior with typed `ConfigError`/`AuthError`" → Task 2 (+ §4.1 enforcement framing). "API tests cover happy path and typed error mapping" → Tasks 3,4. "CLI tests cover `--json`, human output, help, and shim behavior" → Tasks 1,5,6. "Lazy registry test remains green" → Task 6 Step 4 + Task 9 Step 7.

**Spec standard coverage:** §4 contract (CONNECTOR/register/Client/tests-outside-package) → Tasks 1,2; §4.1 import discipline → Tasks 1,2,6 (no-heavy-import test); §4.2 layer boundary → client raises errors / commands renders (Tasks 2–5); §5 typed errors → Tasks 2–4; §6 output `--json`/`--format md`/human → Tasks 1,5; §10.1 re-wrap → Tasks 2–4 (verbatim transcription, only side-effects/error-types changed); §10.2 shim policy (stderr human, silent json, forwarded exit, stateless) → Task 6; §13 testing standard → Tasks 1–6.

**Placeholder scan:** every code step contains real code; re-wrap steps point to exact legacy line ranges to transcribe verbatim with the enumerated rule deltas (mechanical, diff-reviewable per §10.1).

**Type consistency:** `GmailClient`, `_map_http_error`, `format_message_list`/`format_message_detail`, `run`, `register`, `_fmt`, `_MIGRATED`, `CONNECTOR`/`ConnectorSpec(name,help,client,register)` consistent across tasks and match the Notion reference signatures.

**Open risk (noted, not blocking):** the Task-2 auth test seams (`_install_app_flow`/`_load_credentials`) are introduced to make byte-identical auth unit-testable without google libs; the implementer may adjust the exact seam shape to fit the verbatim transcription, provided the three behavioral assertions hold (ConfigError on missing libs; ConfigError + no browser on no-creds/no-refresh; AuthError on refresh failure). This is the only place implementation discretion is permitted; everything else is mechanical.
