# h2t-ops Calendar Parity Migration — Implementation Plan (#132)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Calendar to the h2t-ops standard at parity with legacy `lib/clients/calendar.py` (list/search/get/create/delete, primary calendar only). Extract Google OAuth substrate from Gmail into a shared `h2t_ops/core/google_auth.py` and migrate Gmail to use it. Provider-feature expansion lives in #145.

**Architecture:** Re-wrap not rewrite. A new single-responsibility `core/google_auth.py` module owns Google OAuth resolution (lazy imports, scope validation, refresh, atomic token writeback, non-interactive enforcement); Gmail and Calendar both consume it. The Calendar connector follows the established Notion/Gmail three-file shape (`__init__.py` + `client.py` + `commands.py`). The `dev check lazy-registry` guard is extended to `google*` so module-level google imports never sneak in.

**Tech Stack:** Python (`h2t_ops` package), `pytest`, the connector runbook at `plugins/h2t-ops/references/h2t-connector-runbook.md`. No new dependencies — google libs are already in `pyproject.toml`.

**Authoritative inputs (do not duplicate their content into code):**

| Input | Path |
|---|---|
| Design (this plan's spec) | `docs/superpowers/specs/2026-05-20-h2t-ops-calendar-parity-design.md` |
| Connector runbook | `plugins/h2t-ops/references/h2t-connector-runbook.md` |
| API coverage audit (Calendar §3, §6) | `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md` |
| Roadmap section | `docs/h2t-ops-roadmap.md` → `### skills: [M3] Migrate Calendar connector (parity) — #132` |
| POS operational boundary | `plugins/h2t-ops/references/pos-operational-boundary.md` |
| Testing plan | `docs/h2t-ops-testing-plan.md` |
| Legacy client (re-wrap source) | `lib/clients/calendar.py` |
| Gmail connector (helper-extraction source) | `h2t_ops/connectors/gmail/{client.py, __init__.py, commands.py}` |
| Legacy CLI (shim parity) | `lib/cli/main.py` — `_add_calendar_subparser` / `_cmd_calendar` |
| `dev check lazy-registry` impl | `h2t_ops/dev.py:50–70` |

## File map (this plan touches ONLY these files)

| File | Action | Why |
|---|---|---|
| `h2t_ops/core/google_auth.py` | **Create** | new shared Google OAuth substrate (T1) |
| `h2t_ops/connectors/gmail/client.py` | Modify | drop inlined helpers, consume google_auth (T1) |
| `h2t_ops/dev.py` | Modify | extend lazy-registry guard to google* (T1) |
| `h2t_ops/connectors/calendar/__init__.py` | **Create** (T2 minimal package marker) + **Modify** (T3 full `CONNECTOR = ConnectorSpec(...)` body) | registry entry — split across T2/T3 so T2 client tests can import without `commands.py` existing |
| `h2t_ops/connectors/calendar/client.py` | **Create** | CalendarClient parity surface (T2) |
| `h2t_ops/connectors/calendar/commands.py` | **Create** | CLI adapter (T3) |
| `h2t_ops/cli.py` | Modify | add "calendar" to `_MIGRATED`; `ingest calendar` shim (T3) |
| `tests/core/test_google_auth.py` | **Create** | new helper tests (T1) |
| `tests/connectors/gmail/test_client.py` | Modify | UPDATE patches that referenced relocated helpers (`gmod._load_credentials`/`_request` → `h2t_ops.core.google_auth._load_credentials`/`_request`); APPEND new tests only if new coverage is needed (T1) |
| `tests/connectors/calendar/__init__.py` | **Create** | test package marker (T2) |
| `tests/connectors/calendar/test_client.py` | **Create** | client + normalize tests (T2) |
| `tests/connectors/calendar/test_commands.py` | **Create** | commands + missing-scopes tests (T3) |

**File-state verification (run BEFORE each task; #144-T1 overwrite lesson):**

```bash
# T1: helper module + gmail client + dev guard. None of these are "new tests already present" risk.
test -e h2t_ops/core/google_auth.py    && echo "T1: PRE-EXISTING (must reconcile)" || echo "T1: clean Create"
test -e tests/core/test_google_auth.py && echo "T1: PRE-EXISTING test file"      || echo "T1: clean Create"

# T2/T3: calendar package — confirmed absent at plan-writing time (2026-05-20).
test -d h2t_ops/connectors/calendar/   && echo "T2/T3: PRE-EXISTING package"     || echo "T2/T3: clean Create"
test -d tests/connectors/calendar/     && echo "T2/T3: PRE-EXISTING test pkg"    || echo "T2/T3: clean Create"
```

If any line reports `PRE-EXISTING`, STOP and report BLOCKED — APPEND-vs-Create policy must be re-evaluated for that file.

## Hard constraints (every task)

- Patch the existing connector pattern; no new architecture.
- Keep imports lazy: nothing google-related at module scope of `core/google_auth.py` or either connector. `dev check lazy-registry` must remain green after every task.
- No POS dependency added; no `pos`/`dor.db`/`vault`/`lake` imports; no `~/.dor` writes (token writeback stays at the existing Google OAuth token store under `~/.config/google-calendar-mcp/` per legacy compat).
- Token fallback policy is service-aware: `service_name="gmail"` → shared store first, `~/.config/gmail/` fallback; `service_name="calendar"` → shared store only (no calendar fallback in #132).
- The bootstrap hint in `ConfigError` stays neutral — do NOT name `gmail_cli.py`, the legacy gmail skill, or any specific bootstrap implementation. Hint text: `"Run an explicit Google OAuth bootstrap/setup flow to create the Google OAuth token store, then retry."`
- Folder name `google-calendar-mcp` is a compatibility path; comments and docstrings call this the **Google OAuth token store**.
- Gmail's public API surface stays byte-identical through T1 (`GmailClient()` constructor + all methods unchanged); the 30 existing Gmail tests are the regression guard.
- Provider-feature expansion is **out of scope** — Meet links, recurrence, `events.patch`, all-day, multi-calendar, reminders, FreeBusy → #145.
- Stage ONLY the files named in each task's commit step (the repo carries 26 unrelated tracked-modified + 10 untracked files — never `git add -A`).
- Verification snippets are written for Git Bash / Claude Bash on Windows. PowerShell users use `Select-String` / `Test-Path` equivalents — do not skip the checks.

## Per-task verification (run at the END of every task)

```bash
cd C:/dev/h2t-skills
# A. docs-only-style gate: only the named task files were touched
git status --porcelain -- h2t_ops/ tests/ | sort
# B. no unrelated connector code touched (cumulative across the plan)
git diff --name-only origin/main..HEAD -- h2t_ops/ tests/ | grep -vE '^(h2t_ops/(core/google_auth\.py|core/google_auth\.py|cli\.py|dev\.py|connectors/gmail/client\.py|connectors/calendar/(__init__|client|commands)\.py)|tests/(core/test_google_auth\.py|connectors/(gmail/test_client\.py|calendar/(__init__|test_client|test_commands)\.py)))$' | head \
  && echo "OUT-OF-SCOPE FILE" || echo "OK: plan-scope only"
# C. lazy-registry remains green
uv run h2t-ops dev check lazy-registry
# D. existing Gmail regression suite stays at 30/30
uv run h2t-ops dev pytest tests/connectors/gmail -q
```

If any of A/B/C surfaces a violation, STOP and report BLOCKED.

---

### Task 1: extract `core/google_auth.py`, migrate Gmail, extend lazy-registry guard

Runbook gates touched: **3 auth/secrets** (extract single-purpose substrate; remove inlined OAuth duplication); **4 lazy imports** (no module-level google in either file; extend guard); **5 tests** (helper tests + Gmail regression). Gmail API surface byte-identical.

**Files:**

- Create: `h2t_ops/core/google_auth.py`
- Modify: `h2t_ops/connectors/gmail/client.py` (remove `_load_dotenv`/`_import_google`/`_request`/`_install_app_flow`/`_load_credentials` helpers and the inlined `_get_service`; consume `core.google_auth` instead)
- Modify: `h2t_ops/dev.py:50–70` (broaden lazy-registry guard to `google*`)
- Create: `tests/core/test_google_auth.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/core/test_google_auth.py` verbatim:

```python
"""Tests for h2t_ops.core.google_auth — Google OAuth substrate."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core.errors import AuthError, ConfigError


CAL_SCOPE = "https://www.googleapis.com/auth/calendar"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _write_token(path: Path, scopes: list[str], *, with_refresh: bool = True,
                 expiry: str | None = None) -> None:
    """Write a minimal token.json that mod._load_credentials accepts.

    expiry: ISO-8601 timestamp string (e.g. "2000-01-01T00:00:00Z") to force
    `creds.expired = True` for refresh/expiry tests; default None lets the
    google library treat the token as having no explicit expiry.
    """
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": "id.apps.googleusercontent.com",
        "client_secret": "secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "access_t",
        "scopes": list(scopes),
    }
    if with_refresh:
        payload["refresh_token"] = "refresh_t"
    if expiry is not None:
        payload["expiry"] = expiry
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_returns_credentials_for_matching_scope(tmp_path, monkeypatch):
    """Happy path: token has required scope, creds returned without browser.

    Explicit future expiry — without it, google-auth defaults to immediate
    expiry, making creds.expired==True and triggering a live refresh call
    against the network. The future expiry keeps the test deterministic and
    fully offline.
    """
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [CAL_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert creds is not None


def test_resolve_calendar_uses_shared_store_only(tmp_path, monkeypatch):
    """service_name=calendar: NO ~/.config/calendar/ fallback."""
    # Place a token only at ~/.config/calendar/ — the legacy "wrong" path.
    bogus_calendar_store = tmp_path / ".config" / "calendar" / "token.json"
    _write_token(bogus_calendar_store, [CAL_SCOPE])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    # Hint must be neutral — no legacy-skill name.
    assert "Google OAuth bootstrap" in ei.value.hint
    assert "gmail_cli" not in ei.value.hint
    assert "gmail skill" not in ei.value.hint


def test_resolve_gmail_falls_back_to_gmail_store(tmp_path, monkeypatch):
    """service_name=gmail: shared store missing, fall back to ~/.config/gmail/token.json.

    Explicit future expiry (same rationale as the happy-path test above).
    """
    gmail_store = tmp_path / ".config" / "gmail" / "token.json"
    _write_token(gmail_store, [GMAIL_READ_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    creds = mod.resolve_google_credentials("gmail", [GMAIL_READ_SCOPE])
    assert creds is not None


def test_resolve_raises_configerror_when_token_missing_required_scope(tmp_path, monkeypatch):
    """Upfront scope validation — token has Gmail scope but not Calendar scope.

    This is the NEW stricter behavior (vs legacy's confusing 403 at API call time).
    """
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [GMAIL_READ_SCOPE])  # only Gmail scope present
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(ConfigError) as ei:
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])
    assert "scope" in str(ei.value).lower() or "scope" in (ei.value.hint or "").lower()
    # Hint stays neutral
    assert "gmail_cli" not in (ei.value.hint or "")


def test_resolve_raises_autherror_when_expired_without_refresh_token(monkeypatch):
    """Expired token with no refresh_token → AuthError (no silent browser).

    Bypass google-auth's strict input format (which requires `refresh_token`
    to be present in the JSON payload) by stubbing `_load_credentials` to
    return a Credentials-shaped SimpleNamespace directly. This test exercises
    `resolve_google_credentials` branching, NOT google-auth's input validation.
    """
    fake_creds = SimpleNamespace(
        valid=False,
        expired=True,
        refresh_token=None,
        scopes=[CAL_SCOPE],
    )
    monkeypatch.setattr(mod, "_load_credentials",
                        lambda token_path, creds_path: fake_creds)
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: pytest.fail("browser flow MUST NOT be reached"))
    with pytest.raises(AuthError):
        mod.resolve_google_credentials("calendar", [CAL_SCOPE])


def test_install_app_flow_seam_exists_but_never_called_in_resolve(tmp_path, monkeypatch):
    """Test contract: _install_app_flow is a seam, used only to assert non-reach.

    Must monkeypatch Path.home → tmp_path so the test runs in an isolated FS
    and does NOT read the developer's real ~/.config/google-calendar-mcp/
    tokens.json (which could be a valid token and break the no-creds setup).
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    called = {"n": 0}
    monkeypatch.setattr(mod, "_install_app_flow",
                        lambda: called.__setitem__("n", called["n"] + 1))
    # Resolve will fail (no creds in tmp_path), but it must NOT call the browser seam.
    with pytest.raises((ConfigError, AuthError)):
        mod.resolve_google_credentials("calendar",
                                       ["https://www.googleapis.com/auth/calendar"])
    assert called["n"] == 0
```

- [ ] **Step 2: Run helper tests to verify they fail**

```bash
uv run h2t-ops dev pytest tests/core/test_google_auth.py -v
```

Expected: ALL FAIL with `ModuleNotFoundError: No module named 'h2t_ops.core.google_auth'`.

- [ ] **Step 3: Create `h2t_ops/core/google_auth.py`**

Create the file with EXACTLY this body. The content is largely a relocation of Gmail's existing helpers — preserve their behavior verbatim, add the service-aware path resolution and the upfront scope validation:

```python
"""Google OAuth substrate for h2t-ops connectors (non-interactive).

Owns: credential discovery (service-aware token store paths), token load +
"normal" wrap normalize + scope→scopes split, upfront scope validation,
expired-token refresh (no browser), atomic token writeback, lazy import seams.

Authority: docs/superpowers/specs/2026-05-20-h2t-ops-calendar-parity-design.md
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from h2t_ops.core.errors import AuthError, ConfigError


def _oauth_store_dir() -> Path:
    """Google OAuth token store path.

    Legacy compat path — folder name `google-calendar-mcp` is kept for backward
    compatibility with existing local installs. Comments/docs call this the
    "Google OAuth token store" (the name is not a forward architectural
    commitment).

    Wrapped in a function so `Path.home()` is evaluated at call time, allowing
    tests to `monkeypatch.setattr(Path, "home", ...)`.
    """
    return Path.home() / ".config" / "google-calendar-mcp"


_BOOTSTRAP_HINT = (
    "Run an explicit Google OAuth bootstrap/setup flow to create the "
    "Google OAuth token store, then retry."
)

_GOOGLE_HINT = (
    "pip install google-api-python-client google-auth google-auth-oauthlib"
    "  (or run /h2t-core:setup)"
)


def _load_dotenv() -> None:
    """Optional dotenv merge — re-wrap of legacy module-level call."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)


def _import_google():
    """Lazy import guard — returns (Credentials, build)."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return Credentials, build


def _request():
    """Lazy `google.auth.transport.requests.Request()` seam."""
    try:
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return Request()


def _install_app_flow():
    """Lazy InstalledAppFlow seam. §4.1 enforcement: normal connector commands
    MUST NOT reach this; tests assert via monkeypatch.setattr.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.", hint=_GOOGLE_HINT,
        ) from e
    return InstalledAppFlow


def _candidate_paths(service_name: str) -> list[tuple[Path, Path]]:
    """Return (token_path, creds_path) candidates by service.

    Token fallback policy (per design doc):
      - "gmail":    shared OAuth store → ~/.config/gmail/  fallback
      - "calendar": shared OAuth store only (no calendar-specific fallback)
    """
    shared = (_oauth_store_dir() / "tokens.json",
              _oauth_store_dir() / "credentials.json")
    if service_name == "gmail":
        gmail_dir = Path.home() / ".config" / "gmail"
        return [shared, (gmail_dir / "token.json", gmail_dir / "credentials.json")]
    if service_name == "calendar":
        return [shared]
    raise ConfigError(
        f"google_auth: unknown service_name {service_name!r}",
        hint="expected 'gmail' or 'calendar'",
    )


def _load_credentials(token_path: Path, creds_path: Path):
    """Token-load + 'normal' wrap normalize + creds.json client-creds merge.

    Returns a google.oauth2.credentials.Credentials instance, or None when the
    token file is absent / unreadable.

    DELIBERATE STRICTER-THAN-LEGACY: the except clause below is intentionally
    narrow — `(json.JSONDecodeError, KeyError, ValueError)` only — letting
    other exceptions (TypeError, AttributeError, etc.) propagate. Legacy
    `lib/clients/gmail.py` swallowed all exceptions; the narrower catch
    surfaces real bugs instead of silently degrading to "token not found".
    Paired with the upfront scope validation in `_validate_scopes`, both are
    the design's stricter-than-legacy UX improvements.
    """
    Credentials, _ = _import_google()
    if not token_path.exists():
        return None
    try:
        with open(token_path) as f:
            token_data = json.load(f)
        # Legacy "normal" wrap from google-calendar-mcp bootstrap format.
        if "normal" in token_data:
            token_data = token_data["normal"]
            if "expiry_date" in token_data:
                expiry_ms = token_data.pop("expiry_date")
                expiry_dt = datetime.fromtimestamp(expiry_ms / 1000)
                token_data["expiry"] = expiry_dt.isoformat() + "Z"
            if "scope" in token_data:
                token_data.setdefault("scopes", token_data.pop("scope").split())
        # Calendar bootstrap variant: scope as space-separated string at top level.
        if "scope" in token_data and "scopes" not in token_data:
            token_data["scopes"] = token_data.pop("scope").split()
        if isinstance(token_data.get("scopes"), str):
            token_data["scopes"] = token_data["scopes"].split()
        # Merge client_id/client_secret from credentials.json if missing on token.
        if "client_id" not in token_data and creds_path.exists():
            with open(creds_path) as f:
                creds_data = json.load(f)
            installed = creds_data.get("installed", creds_data)
            token_data["client_id"] = installed.get("client_id")
            token_data["client_secret"] = installed.get("client_secret")
            token_data.setdefault(
                "token_uri",
                installed.get("token_uri", "https://oauth2.googleapis.com/token"),
            )
        scopes = token_data.get("scopes") or []
        return Credentials.from_authorized_user_info(token_data, scopes)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _validate_scopes(token_scopes: Iterable[str], required: Iterable[str]) -> None:
    """Upfront scope check (NEW vs legacy). Stricter than the legacy 403-at-call-time.

    No silent re-bootstrap; raise ConfigError with the neutral hint instead.
    """
    have = set(token_scopes or [])
    missing = [s for s in required if s not in have]
    if missing:
        raise ConfigError(
            f"Google OAuth token is missing required scope(s): {', '.join(missing)}",
            hint=_BOOTSTRAP_HINT,
        )


def resolve_google_credentials(service_name: str,
                               required_scopes: list[str]):
    """Non-interactive resolution of Google OAuth credentials. Never opens a browser.

    See module docstring + design 2026-05-20-h2t-ops-calendar-parity-design.md.
    """
    _load_dotenv()
    candidates = _candidate_paths(service_name)
    creds = None
    found_token_path: Optional[Path] = None
    for token_path, creds_path in candidates:
        loaded = _load_credentials(token_path, creds_path)
        if loaded is not None:
            creds = loaded
            found_token_path = token_path
            break
    if creds is None:
        raise ConfigError(
            f"Google OAuth token not found for service {service_name!r}.",
            hint=_BOOTSTRAP_HINT,
        )
    # Upfront scope validation — NEW stricter behavior.
    _validate_scopes(getattr(creds, "scopes", None) or [], required_scopes)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(_request())
            except Exception as e:
                raise AuthError(
                    f"Google OAuth token refresh failed: {e}",
                    hint=_BOOTSTRAP_HINT,
                ) from e
            # Atomic writeback: temp + rename, into the same directory.
            assert found_token_path is not None
            found_token_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = found_token_path.with_suffix(found_token_path.suffix + ".tmp")
            tmp.write_text(creds.to_json())
            os.replace(tmp, found_token_path)
        else:
            raise AuthError(
                "Google OAuth token is invalid and no refresh token is available.",
                hint=_BOOTSTRAP_HINT,
            )
    return creds


def build_google_service(api: str, version: str, creds):
    """Lazy wrapper around googleapiclient.discovery.build."""
    _, build = _import_google()
    return build(api, version, credentials=creds)
```

- [ ] **Step 4: Verify helper tests pass**

```bash
uv run h2t-ops dev pytest tests/core/test_google_auth.py -v
```

Expected: all helper tests PASS.

- [ ] **Step 5: Extend `dev check lazy-registry` to `google*`**

In `h2t_ops/dev.py`, replace the lazy-registry block (currently `if name == "lazy-registry":` block, lines 50–70). The change is the guard tuple/prefix logic:

```python
    if name == "lazy-registry":
        import builtins
        real = builtins.__import__
        # Heavy modules that must NEVER be imported during registry/help dispatch.
        _heavy_exact = {"notion_client", "httpx"}
        _heavy_prefixes = ("google", "googleapiclient", "google_auth_oauthlib")

        def guard(n, *a, **k):
            if n in _heavy_exact or any(
                n == p or n.startswith(p + ".") for p in _heavy_prefixes
            ):
                raise AssertionError(f"registry imported {n}")
            return real(n, *a, **k)

        builtins.__import__ = guard
        try:
            from h2t_ops.core.registry import discover
            names = {s.name for s in discover()}
        except ImportError as e:
            print(f"FAIL lazy-registry (not yet installed: {e})", file=sys.stderr)
            return 1
        finally:
            builtins.__import__ = real
        ok = "notion" in names
        print(("OK" if ok else "FAIL") + " lazy-registry")
        return 0 if ok else 1
```

Verify:

```bash
uv run h2t-ops dev check lazy-registry
```

Expected: `OK lazy-registry`. (At this point Gmail still imports google libs only inside methods, so guard does not fire.)

- [ ] **Step 6: Migrate `h2t_ops/connectors/gmail/client.py` to consume `core.google_auth`**

In `h2t_ops/connectors/gmail/client.py`, do exactly the following:

(a) **Remove** the module-level helpers `_load_dotenv` (line ~51), `_import_google` (line ~62), `_request` (line ~78), `_install_app_flow` (line ~92), `_load_credentials` (line ~165) — they now live in `core/google_auth.py`.

(b) **Replace** the imports near the top so Gmail no longer references `dotenv` / google modules at all (heavy imports stay in `core/google_auth.py`). Keep the existing typed-error / `_map_http_error` / `_GMAIL_SCOPES` definitions intact. Add:

```python
from h2t_ops.core.google_auth import (
    resolve_google_credentials,
    build_google_service,
)
```

(c) **Replace** the `_get_service` method in `class GmailClient` with this single-purpose body:

```python
    def _get_service(self):
        creds = resolve_google_credentials("gmail", _GMAIL_SCOPES)
        service = build_google_service("gmail", "v1", creds)
        _bind_http_error()  # bind real HttpError now that google is importable
        return service
```

(d) **Remove** the call to `_load_dotenv()` in `__init__`, replacing the body with just `self.service = self._get_service()` (the helper now handles dotenv internally).

- [ ] **Step 6.5: Update Gmail tests for relocated helper seams**

Two existing Gmail tests patch helpers that Step 6 just relocated from `gmod` to `h2t_ops.core.google_auth` (`gmod._load_credentials`, `gmod._request`, `gmod._install_app_flow`, `gmod.Path` if `Path` import was dropped from gmail/client.py). After migration those symbols no longer exist in `gmod`; `monkeypatch.setattr(gmod, "_…", …)` raises `AttributeError`. Re-target the patches at the new ownership namespace (`h2t_ops.core.google_auth`). The third test that patches `gmod.HttpError` (line ~155) stays as-is — `HttpError` is bound at runtime via `_bind_http_error()` which Step 6 keeps in `gmail/client.py`; that seam did NOT relocate.

**Patch #1 — `test_no_creds_no_refresh_raises_configerror_not_browser`** (currently around lines 41–76). Replace the function body verbatim with:

```python
def test_no_creds_no_refresh_raises_configerror_not_browser(monkeypatch, tmp_path):
    """§4.1 enforcement: must raise ConfigError, must NOT launch run_local_server.

    After T1 helper relocation, patches target the substrate namespace
    (`h2t_ops.core.google_auth`). The `_Flow` discriminator stub remains as
    a regression guard: if some future refactor reintroduces a browser-
    launching path inside `resolve_google_credentials`, this test fails.
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core import google_auth as ga
    from h2t_ops.core.errors import ConfigError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text("{}")
    monkeypatch.setattr(ga.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(ga, "_load_credentials", lambda *a, **k: None)

    launched = {"browser": False}

    class _Flow:
        @staticmethod
        def from_client_secrets_file(*a, **k):
            launched["browser"] = True
            raise AssertionError("run_local_server must never be reached")

    monkeypatch.setattr(ga, "_install_app_flow", lambda: _Flow)
    with pytest.raises(ConfigError):
        gmod.GmailClient()
    assert launched["browser"] is False
```

**Patch #2 — `test_refresh_failure_raises_autherror`** (currently around lines 79–99). Replace the function body verbatim with:

```python
def test_refresh_failure_raises_autherror(monkeypatch, tmp_path):
    """After T1 helper relocation, this test patches the substrate namespace
    (`h2t_ops.core.google_auth`), not the legacy gmail-local helpers (which
    no longer exist post-migration).
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core import google_auth as ga
    from h2t_ops.core.errors import AuthError

    # Safety: keep Path.home isolated so nothing accidentally reads real
    # ~/.config or ~/.dor during this test.
    monkeypatch.setattr(ga.Path, "home", staticmethod(lambda: tmp_path))

    class _Creds:
        valid = False
        expired = True
        refresh_token = "r"
        # scopes must satisfy _validate_scopes(_GMAIL_SCOPES) — use the exact
        # set the gmail client requires (imported from the same module).
        scopes = list(gmod._GMAIL_SCOPES)
        def refresh(self, _req):
            raise RuntimeError("invalid_grant")

    monkeypatch.setattr(ga, "_load_credentials", lambda *a, **k: _Creds())
    # Stub the lazy Request() seam — google libs absent in test env.
    monkeypatch.setattr(ga, "_request", lambda: object())
    with pytest.raises(AuthError):
        gmod.GmailClient()
```

The file-write block (`cfg / "credentials.json"`, `cfg / "token.json"`) in test #2 is removed — dead code with `_load_credentials` fully stubbed.

Touch ONLY these two tests in `tests/connectors/gmail/test_client.py`; do NOT modify any other test (in particular, leave `test_get_message_404_maps_notfound` and its `gmod.HttpError` monkeypatch unchanged — that seam stays in `gmail/client.py`).

Verify just the two patched tests:

```
uv run h2t-ops dev pytest tests/connectors/gmail/test_client.py::test_no_creds_no_refresh_raises_configerror_not_browser tests/connectors/gmail/test_client.py::test_refresh_failure_raises_autherror -v
```

Expected: 2/2 PASS.

- [ ] **Step 7: Verify Gmail regression — 30 tests stay green**

```bash
uv run h2t-ops dev pytest tests/connectors/gmail -v
```

Expected: 30/30 PASS. If anything fails, STOP and report BLOCKED — Gmail public API must remain byte-identical.

- [ ] **Step 8: Re-run lazy-registry guard + broader sweep**

```bash
uv run h2t-ops dev check lazy-registry
uv run h2t-ops dev pytest tests/core tests/connectors -q
```

Expected: `OK lazy-registry`; total `tests/core + tests/connectors` count = previous baseline + 6 (the 6 new `test_google_auth.py` tests). No regressions.

- [ ] **Step 9: Scope check**

```bash
git status --porcelain
git diff --stat HEAD -- \
  h2t_ops/core/google_auth.py \
  h2t_ops/connectors/gmail/client.py \
  h2t_ops/dev.py \
  tests/core/test_google_auth.py \
  tests/connectors/gmail/test_client.py
```

Expected: ONLY those 5 files modified vs HEAD; no other file staged. If any other file appears, STOP.

- [ ] **Step 10: Commit**

```bash
git add h2t_ops/core/google_auth.py \
        h2t_ops/connectors/gmail/client.py \
        h2t_ops/dev.py \
        tests/core/test_google_auth.py \
        tests/connectors/gmail/test_client.py
git commit -m "feat(core): shared Google OAuth substrate; migrate Gmail; broaden lazy-registry (#132)"
```

---

### Task 2: Create Calendar package — `__init__.py` + `client.py` + client tests

Runbook gates touched: **1 parity** (re-wrap legacy `lib/clients/calendar.py`); **4 lazy** (no module-level google in client.py); **5 tests** (4 normalize migrations + API typed-error tests).

**File-state precondition:** `tests/connectors/calendar/` MUST NOT exist before this task (verify by `test -d tests/connectors/calendar/`; expect "clean Create"). If pre-existing, STOP with BLOCKED (#144-T1 lesson).

**Files:**

- Create: `h2t_ops/connectors/calendar/__init__.py`
- Create: `h2t_ops/connectors/calendar/client.py`
- Create: `tests/connectors/calendar/__init__.py` (empty package marker)
- Create: `tests/connectors/calendar/test_client.py`

- [ ] **Step 1: Create `h2t_ops/connectors/calendar/__init__.py` (minimal package marker only)**

Verbatim — this is a deliberately minimal package marker; `CONNECTOR = ConnectorSpec(...)` is added by T3 once `commands.py` exists. The reason for the split: T2 tests import `h2t_ops.connectors.calendar.client`, which runs this `__init__.py` first; if `__init__.py` tries to `from .commands import register` here, ALL of T2's tests fail with `ModuleNotFoundError` before they can even reach `client.py`. Keeping T2's `__init__.py` empty avoids that.

```python
"""Calendar connector — package marker.

`CONNECTOR = ConnectorSpec(...)` is added by T3 once `commands.py` exists; until
then this is an empty package so that direct imports of `client` (and tests
thereof) work without requiring `commands.py`.
"""
```

To verify the intentional T2 half-state, run:

```bash
uv run h2t-ops --version
uv run h2t-ops connectors
```

Expected: both succeed; `connectors` lists `notion` and `gmail` but NOT `calendar` (because `__init__.py` does not yet define `CONNECTOR` — `registry.discover()` skips subpackages without that attribute). This is acceptable mid-plan state; T3 fills the registry entry.

- [ ] **Step 2: Create the failing client tests**

Create `tests/connectors/calendar/__init__.py` as an empty file (package marker).

Create `tests/connectors/calendar/test_client.py` verbatim:

```python
"""Tests for h2t_ops.connectors.calendar.client.CalendarClient.

API logic mirrors lib/clients/calendar.py; only side effects and error types
differ per the connector standard (spec §10).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError,
)


@pytest.fixture
def client_obj():
    """Construct a CalendarClient WITHOUT running __init__ (no network / SDK)."""
    from h2t_ops.connectors.calendar.client import CalendarClient
    c = object.__new__(CalendarClient)
    c.service = MagicMock()
    return c


# ---------- _normalize_event — migrated verbatim from tests/clients/test_calendar.py ----------

def test_normalize_timed_event(client_obj):
    event = {
        "id": "evt1",
        "summary": "Meeting",
        "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
        "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
        "htmlLink": "https://cal.google.com/...",
    }
    result = client_obj._normalize_event(event)
    assert result["summary"] == "Meeting"
    assert result["time"] == "14:00"
    assert result["duration_min"] == 60
    assert result["date"] == "2026-04-06"
    assert result["id"] == "evt1"


def test_normalize_all_day_event(client_obj):
    event = {
        "id": "evt2",
        "summary": "Holiday",
        "start": {"date": "2026-04-07"},
        "end": {"date": "2026-04-08"},
    }
    result = client_obj._normalize_event(event)
    assert result["time"] == "весь день"
    assert result["duration_min"] is None
    assert result["date"] == "2026-04-07"


def test_normalize_missing_location(client_obj):
    event = {
        "id": "evt3",
        "summary": "No Location",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
    }
    result = client_obj._normalize_event(event)
    assert result["location"] == ""


def test_normalize_description_truncated(client_obj):
    event = {
        "id": "evt4",
        "summary": "With Desc",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
        "description": "A" * 300,
    }
    result = client_obj._normalize_event(event)
    assert len(result["description"]) == 200


# ---------- typed-error mapping (mirror Gmail _map_http_error shape) ----------

def test_map_http_error_401_to_autherror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=401)
    e.reason = "Unauthorized"
    err = _map_http_error(e, op="list events")
    assert isinstance(err, AuthError)


def test_map_http_error_404_to_notfounderror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=404)
    e.reason = "Not Found"
    err = _map_http_error(e, op="get event")
    assert isinstance(err, NotFoundError)


def test_map_http_error_500_to_providererror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=500)
    e.reason = "Server Error"
    err = _map_http_error(e, op="list events")
    assert isinstance(err, ProviderError)


# ---------- happy-path read (stub the google service) ----------

def test_list_events_happy_path_returns_normalized_list(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt1",
                "summary": "M",
                "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
                "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
            }
        ]
    }
    rows = client_obj.list_events(days=1, max_results=1)
    assert isinstance(rows, list) and len(rows) == 1
    assert rows[0]["summary"] == "M"
    assert rows[0]["time"] == "14:00"


# ---------- missing-libs / missing-creds path (re-checked via google_auth) ----------

def test_init_with_missing_google_libs_raises_configerror(monkeypatch):
    """If google_auth._import_google fails, surfacing as ConfigError, the
    CalendarClient constructor must propagate the typed error (not crash).
    """
    from h2t_ops.connectors.calendar import client as cmod
    from h2t_ops.core import google_auth as ga
    monkeypatch.setattr(
        ga, "resolve_google_credentials",
        lambda *a, **k: (_ for _ in ()).throw(
            ConfigError("Google API libraries not installed.", hint="install hint")
        ),
    )
    with pytest.raises(ConfigError):
        cmod.CalendarClient()
```

- [ ] **Step 3: Run failing client tests**

```bash
uv run h2t-ops dev pytest tests/connectors/calendar/test_client.py -v
```

Expected: all FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.calendar.client'`.

- [ ] **Step 4: Create `h2t_ops/connectors/calendar/client.py`**

Verbatim:

```python
"""CalendarClient — Google Calendar adapter (re-wrapped, typed errors).

API logic mirrors lib/clients/calendar.py; only side effects and error types
changed per spec §10 (re-wrap not rewrite). Provider-feature expansion is
tracked in #145 — this module is parity-only.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import (
    AuthError, ConfigError, H2TError, NetworkError, NotFoundError, ProviderError,
)
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _map_http_error(e: Exception, *, op: str):
    """Map googleapiclient.errors.HttpError to typed h2t_ops errors.

    Mirrors h2t_ops/connectors/gmail/client.py:_map_http_error. Defensive:
    google libs may be absent in test contexts, so we check duck-typed.
    """
    if isinstance(e, H2TError):
        return e
    status = getattr(getattr(e, "resp", None), "status", None)
    msg = f"Failed to {op}: {e}"
    if status in (401, 403):
        return AuthError(msg)
    if status == 404:
        return NotFoundError(msg)
    if status is not None and status >= 500:
        return ProviderError(msg)
    s = str(e).lower()
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(msg)
    return ProviderError(msg)


class CalendarClient:
    """Google Calendar API client — primary calendar only (parity scope #132)."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("calendar", CALENDAR_SCOPES)
        self.service = build_google_service("calendar", "v3", creds)

    # ----- Read -----
    def list_events(self, days: int = 1, max_results: int = 20) -> List[Dict[str, Any]]:
        from datetime import timezone
        time_min = datetime.now(timezone.utc).isoformat()
        time_max = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        try:
            res = self.service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op="list events") from e
        return [self._normalize_event(it) for it in res.get("items", [])]

    def search_events(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            res = self.service.events().list(
                calendarId="primary",
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op="search events") from e
        return [self._normalize_event(it) for it in res.get("items", [])]

    def get_event(self, event_id: str) -> Dict[str, Any]:
        try:
            return self.service.events().get(
                calendarId="primary", eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"get event {event_id}") from e

    # ----- Write (explicit user-intent CLI verbs per runbook §7) -----
    def create_event(
        self,
        summary: str,
        date: str,
        time: str,
        duration_min: int = 60,
        description: Optional[str] = None,
        attendees: Optional[str] = None,
        tz: str = "Asia/Jerusalem",
    ) -> Dict[str, Any]:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_min)
        event: Dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        if description:
            event["description"] = description
        if attendees:
            event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
        send_updates = "all" if attendees else "none"
        try:
            return self.service.events().insert(
                calendarId="primary", body=event, sendUpdates=send_updates,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"create event {summary!r}") from e

    def delete_event(self, event_id: str) -> None:
        try:
            self.service.events().delete(
                calendarId="primary", eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"delete event {event_id}") from e

    # ----- Helpers -----
    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Verbatim port from lib/clients/calendar.py._normalize_event."""
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        if "T" in start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            time_str = start_dt.strftime("%H:%M")
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            event_date = start_dt.strftime("%Y-%m-%d")
        else:
            time_str = "весь день"
            duration_min = None
            event_date = start
        return {
            "id": event.get("id", ""),
            "summary": event.get("summary", "(без названия)"),
            "date": event_date,
            "time": time_str,
            "duration_min": duration_min,
            "location": event.get("location", ""),
            "description": (event.get("description") or "")[:200],
            "html_link": event.get("htmlLink", ""),
        }
```

- [ ] **Step 5: Verify client tests pass**

```bash
uv run h2t-ops dev pytest tests/connectors/calendar/test_client.py -v
```

Expected: all PASS.

- [ ] **Step 6: Verify lazy-registry guard still green + broader sweep + Gmail regression**

```bash
uv run h2t-ops dev check lazy-registry
uv run h2t-ops dev pytest tests/connectors/gmail tests/connectors/calendar tests/core -q
```

Expected: `OK lazy-registry`; total green; Gmail 30/30; Calendar adds 11 new tests (4 normalize + 3 map_http_error + 1 list happy + 1 missing-libs + variants).

- [ ] **Step 7: Verify intentional registry half-state (commands.py not yet present)**

```bash
uv run h2t-ops connectors 2>&1 | tee /tmp/conns.txt
grep -E '^- (notion|gmail)$' /tmp/conns.txt    # must list both
grep -E '^- calendar$' /tmp/conns.txt && echo "UNEXPECTED: calendar listed (commands.py not yet present)" || echo "OK: calendar absent (T3 wires it)"
```

- [ ] **Step 8: Scope check**

```bash
git status --porcelain
git diff --stat HEAD -- \
  h2t_ops/connectors/calendar/__init__.py \
  h2t_ops/connectors/calendar/client.py \
  tests/connectors/calendar/__init__.py \
  tests/connectors/calendar/test_client.py
```

Expected: ONLY those 4 files modified; no other file staged.

- [ ] **Step 9: Commit**

```bash
git add h2t_ops/connectors/calendar/__init__.py \
        h2t_ops/connectors/calendar/client.py \
        tests/connectors/calendar/__init__.py \
        tests/connectors/calendar/test_client.py
git commit -m "feat(calendar): CalendarClient parity surface + normalize tests (#132)"
```

---

### Task 3: Create `commands.py` + wire `cli.py` + commands tests + missing-scopes case

Runbook gates touched: **1 parity** (5 subcommands match legacy `lib/cli/main.py:_cmd_calendar`); **5 tests** (commands + ingest shim + missing-scopes); **6 live smoke** (becomes runnable after this task); **9 write side effects** (create/delete are explicit verbs, classified, tested).

**Files:**

- Create: `h2t_ops/connectors/calendar/commands.py`
- Modify: `h2t_ops/connectors/calendar/__init__.py` (replace minimal T2 package-marker body with the full `CONNECTOR = ConnectorSpec(...)` registry entry — now safe because `commands.py` exists)
- Modify: `h2t_ops/cli.py` (add `"calendar"` to `_MIGRATED` at line 18; insert `ingest calendar` shim after the `ingest gmail` shim around line 125)
- Create: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Write the failing commands tests**

Create `tests/connectors/calendar/test_commands.py` verbatim:

```python
"""Tests for h2t_ops.connectors.calendar.commands — registration, dispatch, shim."""
from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import ConfigError, UsageError


def _build_parser():
    from h2t_ops.connectors.calendar.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_register_adds_5_calendar_subcommands():
    parser = _build_parser()
    for cmd, extra in [
        ("list", []),
        ("search", ["q"]),
        ("get", ["evtid"]),
        ("create", ["Title", "2026-04-06", "14:00"]),
        ("delete", ["evtid"]),
    ]:
        ns = parser.parse_args(["calendar", cmd, *extra])
        assert ns.calendar_cmd == cmd


def test_register_has_format_and_json_flags():
    parser = _build_parser()
    ns = parser.parse_args(["calendar", "list", "--json"])
    assert ns.as_json is True
    ns2 = parser.parse_args(["calendar", "list", "--format", "md"])
    assert ns2.fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    import builtins
    real = builtins.__import__
    seen = []
    def guard(n, *a, **k):
        seen.append(n)
        return real(n, *a, **k)
    builtins.__import__ = guard
    try:
        import importlib
        import h2t_ops.connectors.calendar.commands as cmds
        importlib.reload(cmds)
    finally:
        builtins.__import__ = real
    assert not any(s.endswith("calendar.client") for s in seen), (
        f"commands.py must not import client at module scope. Seen: {seen}"
    )


def test_list_dispatch_json_returns_rows(monkeypatch):
    """Happy-path dispatch — stub CalendarClient, assert JSON path returns rows."""
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod

    class _Stub:
        def list_events(self, days=1, max_results=20):
            return [{"id": "evt1", "summary": "M"}]
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list", days=1, max=20, as_json=True, fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "evt1", "summary": "M"}]


def test_delete_dispatch_requires_confirm(monkeypatch):
    """delete without --confirm raises UsageError (parity with legacy)."""
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    args = SimpleNamespace(
        calendar_cmd="delete", event_id="evt1", confirm=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)


def test_unknown_subcommand_raises_usageerror(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    args = SimpleNamespace(
        calendar_cmd="bogus", as_json=False, fmt="human",
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)


# ---------- Missing-scopes upfront detection (NEW behavior, design §"Auth model") ----------

def test_missing_scopes_surfaces_as_configerror_with_neutral_hint(tmp_path, monkeypatch):
    """Calendar client construction with a Gmail-only token must raise
    ConfigError with the neutral bootstrap hint — not the legacy 403-at-call.
    """
    from pathlib import Path
    import json
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    shared.parent.mkdir(parents=True)
    shared.write_text(json.dumps({
        "client_id": "id.apps.googleusercontent.com",
        "client_secret": "secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "access_t",
        "refresh_token": "refresh_t",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from h2t_ops.connectors.calendar.client import CalendarClient
    with pytest.raises(ConfigError) as ei:
        CalendarClient()
    assert "scope" in str(ei.value).lower() or "scope" in (ei.value.hint or "").lower()
    # Hint stays neutral — no legacy-skill name.
    assert "gmail_cli" not in (ei.value.hint or "")
    assert "gmail skill" not in (ei.value.hint or "")
    assert "Google OAuth" in (ei.value.hint or "")


# ---------- Ingest calendar shim (mirror Gmail §10.2) ----------

def test_ingest_calendar_shim_warns_on_human(monkeypatch, capsys):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    import h2t_ops.connectors.calendar.client as client_mod
    class _Stub:
        def list_events(self, **_): return []
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--days", "1"])
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()
    assert "h2t-ops calendar" in err.lower()
    assert rc == 0


def test_ingest_calendar_shim_silent_on_json(monkeypatch, capsys):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    import h2t_ops.connectors.calendar.client as client_mod
    class _Stub:
        def list_events(self, **_): return []
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--format", "json"])
    err = capsys.readouterr().err
    assert "deprecated" not in err.lower()
    assert rc == 0
```

- [ ] **Step 2: Run commands tests; all FAIL (missing module)**

```bash
uv run h2t-ops dev pytest tests/connectors/calendar/test_commands.py -v
```

Expected: all FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.calendar.commands'`.

- [ ] **Step 3: Create `h2t_ops/connectors/calendar/commands.py`**

Verbatim:

```python
"""Calendar CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from typing import Any

PROVIDER = "calendar"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("calendar", help="Work with Google Calendar events")
    cmds = p.add_subparsers(dest="calendar_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/table, human = concise (default)")

    lp = cmds.add_parser("list", help="List upcoming events")
    lp.add_argument("--days", type=int, default=1)
    lp.add_argument("--max", type=int, default=20)
    add_fmt(lp)

    sp = cmds.add_parser("search", help="Search events by free-text query")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=10)
    add_fmt(sp)

    gp = cmds.add_parser("get", help="Get one event by id")
    gp.add_argument("event_id")
    add_fmt(gp)

    cp = cmds.add_parser("create", help="Create a primary-calendar event")
    cp.add_argument("summary")
    cp.add_argument("date", help="YYYY-MM-DD")
    cp.add_argument("time", help="HH:MM (24h)")
    cp.add_argument("--duration-min", dest="duration_min", type=int, default=60)
    cp.add_argument("--description")
    cp.add_argument("--attendees", help="comma-separated emails")
    cp.add_argument("--tz", default="Asia/Jerusalem")
    add_fmt(cp)

    dp = cmds.add_parser("delete", help="Delete an event by id")
    dp.add_argument("event_id")
    dp.add_argument("--confirm", action="store_true",
                    help="required for non-interactive delete (parity with legacy)")
    add_fmt(dp)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a calendar subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.calendar.client import CalendarClient  # lazy (spec §4.1)
    from h2t_ops.core.errors import UsageError

    client = CalendarClient()
    cmd = args.calendar_cmd

    if cmd == "list":
        return client.list_events(days=args.days, max_results=args.max)
    if cmd == "search":
        return client.search_events(args.query, max_results=args.max)
    if cmd == "get":
        return client.get_event(args.event_id)
    if cmd == "create":
        return client.create_event(
            summary=args.summary, date=args.date, time=args.time,
            duration_min=args.duration_min, description=args.description,
            attendees=args.attendees, tz=args.tz,
        )
    if cmd == "delete":
        if not getattr(args, "confirm", False):
            raise UsageError(
                "calendar delete: --confirm is required for non-interactive delete",
            )
        client.delete_event(args.event_id)
        return {"deleted": args.event_id}
    raise UsageError(f"unknown calendar subcommand: {cmd}")
```

- [ ] **Step 3b: Replace `h2t_ops/connectors/calendar/__init__.py` with the full `CONNECTOR = ConnectorSpec(...)` body**

T2 left this file as a minimal package marker (no imports of `.commands`).
Now that `commands.py` exists, replace the file body with the full registry
entry. Overwrite verbatim:

```python
"""Calendar connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="calendar",
    help="Work with Google Calendar events",
    client="h2t_ops.connectors.calendar.client:CalendarClient",  # lazy ref (spec §4.1)
    register=register,
)
```

This is the canonical Notion/Gmail-pattern `__init__.py` shape; `discover()`
will pick up `CONNECTOR` from this module on the next call.

- [ ] **Step 4: Wire `h2t_ops/cli.py`**

(a) At line 18, change:

```python
_MIGRATED = {"notion", "gmail"}
```

to:

```python
_MIGRATED = {"notion", "gmail", "calendar"}
```

(b) Add the `ingest calendar` shim AFTER the existing `ingest gmail` shim. Locate the `if argv and argv[0] in ("gather", "ingest"):` line (currently around line 148) and INSERT this block IMMEDIATELY BEFORE it (so the shim is consulted before the catch-all `ingest` legacy fallback):

```python
    # ingest calendar shim → new connector (spec §10.2). Mirror Gmail variant.
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "calendar":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest):
                if rest[j + 1] == "json":
                    norm.append("--json")
                # non-json (e.g. legacy "markdown") → drop; connector human default
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            _w, _c = _utf8_writer(sys.stderr)
            print("deprecated: `h2t-ops ingest calendar` → use `h2t-ops calendar` (spec §10)",
                  file=_w)
            _finalize(_w, _c)
        return _run_connector(["calendar", *norm])
```

- [ ] **Step 5: Verify commands tests pass**

```bash
uv run h2t-ops dev pytest tests/connectors/calendar/test_commands.py -v
```

Expected: all PASS, including the missing-scopes test and both shim tests.

- [ ] **Step 6: Verify lazy-registry guard + broader sweep**

```bash
uv run h2t-ops dev check lazy-registry
uv run h2t-ops dev pytest tests/core tests/connectors -q
```

Expected: `OK lazy-registry`; full suite green. The calendar registration is now live.

- [ ] **Step 7: Verify `h2t-ops connectors` lists calendar**

```bash
uv run h2t-ops connectors 2>&1
```

Expected: output now includes `calendar` (in addition to `notion` and `gmail`).

- [ ] **Step 8: Scope check**

```bash
git status --porcelain
git diff --stat HEAD -- \
  h2t_ops/connectors/calendar/__init__.py \
  h2t_ops/connectors/calendar/commands.py \
  h2t_ops/cli.py \
  tests/connectors/calendar/test_commands.py
```

Expected: ONLY those 4 files modified vs HEAD.

- [ ] **Step 9: Commit**

```bash
git add h2t_ops/connectors/calendar/__init__.py \
        h2t_ops/connectors/calendar/commands.py \
        h2t_ops/cli.py \
        tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): CLI commands + registry entry + ingest shim + missing-scopes test (#132)"
```

---

### Task 4: Closure — full pytest sweep + runbook §4 9-gate self-review + live smoke + LOCAL evidence (STOP)

Runbook gates touched: **5 tests** (cumulative); **6 live smoke**; **7 POS** + **8 dist-no-POS** + **9 write side effects** (verify none regressed).

**Files:** none modified (verification + evidence). Zero new commits unless drift surfaces.

- [ ] **Step 1: Full mocked test sweep**

```bash
uv run h2t-ops dev pytest tests/core tests/connectors -v
```

Record: total count, pass/fail. Expected: previous baseline (105 after #144) + 6 (T1 google_auth) + 11 (T2 calendar client) + 9 (T3 calendar commands) ≈ **131 passed, 0 failed**. Exact count may vary by ±2 depending on parametrized variants.

- [ ] **Step 2: `dev check lazy-registry`**

```bash
uv run h2t-ops dev check lazy-registry
```

Expected: `OK lazy-registry`.

- [ ] **Step 3: Runbook §4 9-item gate self-review (no file write — assemble for report)**

For each of the 9 gates, record evidence:

| Gate | #132 Evidence |
|---|---|
| 1 legacy parity | T2 CalendarClient list/search/get/create/delete; 4 normalize tests migrated |
| 2 provider API gaps | NOT addressed (#145); design §"Non-goals" |
| 3 auth/secrets | T1 `core/google_auth.py` substrate; no inlined OAuth duplication; neutral bootstrap hint |
| 4 lazy imports | T1 extended `dev check lazy-registry` to `google*`; OK lazy-registry at T1/T2/T3/T4 |
| 5 tests | T1 6 helper + T2 11 client + T3 9 commands = 26 net-new |
| 6 live smoke | Step 4 below |
| 7 POS boundary | Token writeback stays at `~/.config/google-calendar-mcp/` per legacy compat; no `~/.dor` writes |
| 8 dist-without-POS | No `pos`/`dor.db`/`vault`/`lake` imports in any new file |
| 9 write side effects | `calendar create`/`delete` are explicit user-intent CLI verbs; `delete` requires `--confirm`; covered by tests |

- [ ] **Step 4: Install local h2t-ops from local `C:/dev/h2t-skills` and run read-only live smoke**

```bash
UV=$(pwsh -NoProfile -File tools/h2t-ops-runtime-smoke.ps1 -ResolveUvOnly)
"$UV" tool install --reinstall "$(pwd)"
OPS="$HOME/.local/bin/h2t-ops.exe"

# scope-guard hash before reinstall
sha256sum "$HOME/.local/bin/h2t.exe" 2>/dev/null

"$OPS" --version
"$OPS" doctor
"$OPS" connectors                       # must include calendar
"$OPS" calendar list --days 1 --json | head -c 400
"$OPS" calendar list --days 7 --json | head -c 400

# scope-guard hash after
sha256sum "$HOME/.local/bin/h2t.exe" 2>/dev/null
```

Pass criteria:

- `--version`, `doctor`, `connectors` exit 0; `connectors` lists `calendar`.
- `calendar list --days 1 --json` and `--days 7 --json`: **exit 0 with valid JSON** if the current shared OAuth token has the Calendar scope, OR **exit 3 (ConfigError) with the neutral bootstrap hint** if it does not.
- The exit-3 path is NOT a code failure; it is the upfront scope-validation behavior (design §"Auth model"). Classify it in evidence as "blocked on bootstrap/scope, not on code".
- Token-leak scan over the live stdout: `secret_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9._\-]{20,}` → must be empty.
- Scope guard: `~/.local/bin/h2t.exe` SHA256 unchanged before/after reinstall (`5a041e6ca1ba2c74660397056a644df6a44e0cda98d3855c5911471050476c5a`).

- [ ] **Step 5: Prepare the LOCAL evidence block — DO NOT POST OR CLOSE**

Format ready-to-paste on #132 (template below). Replace `<token>` placeholders with actual values. Do **not** post any GitHub comment, do **not** close #132 — outward-facing actions are user-gated.

```md
## #132 Calendar parity — local evidence (not yet posted)

Date: 2026-05-20
Machine: AUTOMATA
Source: local `C:/dev/h2t-skills` (commits <T1>, <T2>, <T3>; not pushed)
Installed binary: `C:\Users\stani\.local\bin\h2t-ops.exe`

### Mocked tests
- `tests/core tests/connectors`: <count> passed, 0 failed (+26 vs pre-#132).
- `uv run h2t-ops dev check lazy-registry`: OK lazy-registry (now covers google*).

### Live read-only smoke
- `h2t-ops --version`: exit 0
- `h2t-ops doctor`: exit 0
- `h2t-ops connectors`: exit 0, lists notion / gmail / calendar
- `h2t-ops calendar list --days 1 --json`: exit <0 | 3>, <JSON ok | ConfigError with neutral hint>
- `h2t-ops calendar list --days 7 --json`: exit <0 | 3>, <JSON ok | ConfigError with neutral hint>
  (Exit 3 here is the upfront missing-scope detection — design's "blocked on
   bootstrap/scope, not code failure" classification.)

### Guards
- Token leak scan: <empty / hits>
- Scope guard h2t-ai SHA256: <before> → <after> (<HELD / VIOLATED>)
- File scope: `git log <T1>^..<T3> --name-only` — all changes inside the plan's file map.

### Runbook §4 9-item gate
(table from Step 3)
```

- [ ] **Step 6: Final report (no commit unless drift surfaced)**

Surface in the implementer's reply: T1/T2/T3 SHAs, the mocked-test count, the lazy-registry result, the live smoke command-by-command exit codes, token-leak and scope-guard verdicts, the assembled evidence block, and explicit:

> "Did NOT push. Did NOT post any GitHub comment. Did NOT close #132. STOPPING for maintainer approval."

If Steps 1–4 surfaced a drift requiring a fix, the fix lives in this task with its own focused commit (file scope: limited to the file that drifted); do not silently expand scope.

---

## Self-Review (run by the plan author after writing — completed)

**1. Spec coverage:**

- design §Goal → Goal. design §Authority order → "Authoritative inputs" table.
- design §Scope-in (`core/google_auth.py`, Gmail migration, Calendar 3-file shape, ingest shim mirror Gmail §10.2, lazy-registry extension, tests including missing-scopes) → all mapped to T1/T2/T3.
- design §Auth model (normal commands no browser; explicit bootstrap allowed; no incremental authz; missing-scopes upfront) → T1 `resolve_google_credentials` impl + T1 `_validate_scopes` + T3 missing-scopes test.
- design §Helper API signature → T1 Step 3 verbatim Python.
- design §Token fallback policy (gmail dual / calendar single; folder name compat) → T1 `_candidate_paths` + module docstring + comments verbatim.
- design §Bootstrap hint (neutral text) → T1 `_BOOTSTRAP_HINT` constant verbatim.
- design §Calendar parity surface (`__init__.py`, client.py methods, commands.py 5 verbs, cli wiring) → T2 + T3 verbatim code blocks.
- design §Tests (Gmail regression, Calendar API, missing-scopes, 4 normalize, ingest shim warn/silent) → T1 Step 7 + T2 test_client.py + T3 test_commands.py.
- design §DoD 9-gate evidence → T4 Step 3 table.
- design §Plan outline (4 tasks) → T1/T2/T3/T4 1:1.
- design §Review gates → user gate after this plan + per-task two-stage review + final holistic (carried by subagent-driven-development skill).

No gap.

**2. Placeholder scan:**

No "TBD/TODO/handle edge cases/add validation/similar to". Every test body is concrete, every code change ships verbatim Python, every verification has explicit commands with expected outputs. The `<T1>`/`<T2>`/`<T3>` tokens in the evidence template are deliberate placeholders for the implementer to fill in their actual commit SHAs at evidence-prep time — not "TBD"s.

**3. Type / signature consistency:**

- `resolve_google_credentials(service_name: str, required_scopes: list[str]) -> Credentials` signature is identical in design doc, T1 module body, T1 tests, T2 CalendarClient.__init__, and the Gmail migration in T1 Step 6.
- `_BOOTSTRAP_HINT` text identical between design (§"Bootstrap hint"), T1 module body, T1 tests (assertion `"Google OAuth bootstrap" in ei.value.hint`), and T3 missing-scopes test (`"Google OAuth" in (ei.value.hint or "")`).
- Calendar method signatures (`list_events(days, max_results)`, etc.) match legacy `lib/clients/calendar.py` 1:1; T2 client tests use them; T3 commands.py dispatches them.
- `_MIGRATED = {"notion", "gmail", "calendar"}` after T3 matches T3 ingest-shim placement assumption.
- `--confirm` flag on `calendar delete`: T3 commands.py adds it; T3 test_commands.py asserts `UsageError` without it.

No issues found.

---

## Constraints recap (every task obeys)

- Patch the existing connector pattern; no new architecture; no new skill scaffold.
- Heavy imports stay lazy: nothing google at module scope of `core/google_auth.py` or either connector. `dev check lazy-registry` covers `google*` after T1 and stays green through every task.
- No POS dependency added; no `~/.dor` writes; token writeback at `~/.config/google-calendar-mcp/` per legacy compat.
- `service_name="calendar"` uses shared store only (no calendar-specific fallback). `service_name="gmail"` retains its dual-path behavior.
- Bootstrap hint stays neutral (no legacy gmail skill name in error text).
- Missing-scopes detection is NEW stricter-than-legacy behavior, by design.
- Stage ONLY the files named in each task's commit step; the 26 + 10 unrelated dirty files stay preserved.
- Outward-facing actions (push, GitHub comment, issue close) are user-gated — the implementer STOPS after T4 evidence preparation.
