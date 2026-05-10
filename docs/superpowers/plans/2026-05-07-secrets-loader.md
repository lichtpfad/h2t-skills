# Minimal h2t_secrets Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `h2t_secrets` loader in `plugins/h2t-core/scripts/`, migrate only `h2t-ops:research` to use it, document rotation runbook. All other skills keep working as-is via shell-export.

**Architecture:** Stdlib-only Python module with `bootstrap()` (env merge from `~/.dor/secrets/secrets.env`, shell-export wins) and `get_blob(relative_path)` (canonical Path to credential blobs). Cross-plugin import via `importlib.util.spec_from_file_location` with relative-path resolution. Fail-loud on missing file or malformed line.

**Tech Stack:** Python 3.11 stdlib (`pathlib`, `os`, `importlib.util`), pytest. Zero pip deps.

**Spec:** `docs/superpowers/specs/2026-05-07-secrets-loader.md`
**Issue:** lichtpfad/h2t-skills#108
**Umbrella:** lichtpfad/h2t-skills#107

---

## File Structure

| Path | Type | Responsibility |
|---|---|---|
| `plugins/h2t-core/scripts/h2t_secrets.py` | NEW | Loader: `bootstrap()`, `get_blob()`, helper consts |
| `plugins/h2t-core/scripts/tests/__init__.py` | NEW (if missing) | Test package marker |
| `plugins/h2t-core/scripts/tests/test_h2t_secrets.py` | NEW | 10 unit tests |
| `plugins/h2t-ops/skills/research/scripts/exa_search.py` | modify | Add `_load_h2t_secrets()` + `bootstrap()` call in `main()` |
| `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | modify | 1 new integration test (bootstrap invoked at startup) |
| `plugins/h2t-core/scripts/secrets-readme-template.md` | NEW | Rotation runbook template, copied by user to `~/.dor/secrets/README.md` |
| `plugins/h2t-core/.claude-plugin/plugin.json` | modify | h2t-core version patch bump |

**Test runner:** `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest <path> -v`

**Frequent commits:** один task = один commit. Conventional Commits scope `(secrets)` или `(research)` где уместно.

**Branch:** `feature/secrets-loader` (создаётся в Task 1).

---

## Task 1: Create branch + scaffold module + first failing test

**Files:**
- Create: `plugins/h2t-core/scripts/h2t_secrets.py` (empty module)
- Create: `plugins/h2t-core/scripts/tests/__init__.py` (empty)
- Create: `plugins/h2t-core/scripts/tests/test_h2t_secrets.py` (test scaffolding)

- [ ] **Step 1: Create feature branch from main**

```
git -C C:/dev/h2t-skills checkout main
git -C C:/dev/h2t-skills pull --ff-only
git -C C:/dev/h2t-skills checkout -b feature/secrets-loader
```

Verify with `git -C C:/dev/h2t-skills branch --show-current` → `feature/secrets-loader`.

- [ ] **Step 2: Scaffold module with version + constants**

Create `plugins/h2t-core/scripts/h2t_secrets.py`:

```python
"""h2t_secrets — single source of truth for h2t skill secrets.

Reads ~/.dor/secrets/secrets.env into os.environ without overriding existing
shell-exported values. See docs/superpowers/specs/2026-05-07-secrets-loader.md.
"""
from __future__ import annotations

__version__ = "0.1.0"

import os
from pathlib import Path
from typing import Final

DEFAULT_SECRETS_FILE: Final[Path] = Path.home() / ".dor" / "secrets" / "secrets.env"
SECRETS_DIR: Final[Path] = Path.home() / ".dor" / "secrets"
ENV_OVERRIDE: Final[str] = "H2T_SECRETS_FILE"


def bootstrap(*, env_file: Path | None = None) -> dict[str, str]:
    """Stub — implemented in Task 2."""
    raise NotImplementedError


def get_blob(relative_path: str) -> Path:
    """Stub — implemented in Task 3."""
    raise NotImplementedError
```

- [ ] **Step 3: Create empty tests/__init__.py**

```
plugins/h2t-core/scripts/tests/__init__.py
```

(empty file — pytest discovers tests).

- [ ] **Step 4: Write smoke test**

Create `plugins/h2t-core/scripts/tests/test_h2t_secrets.py`:

```python
"""Tests for h2t_secrets loader."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Resolve module path: plugins/h2t-core/scripts/
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
import h2t_secrets  # noqa: E402


def test_module_exposes_public_api():
    assert hasattr(h2t_secrets, "bootstrap")
    assert hasattr(h2t_secrets, "get_blob")
    assert hasattr(h2t_secrets, "DEFAULT_SECRETS_FILE")
    assert hasattr(h2t_secrets, "SECRETS_DIR")
    assert hasattr(h2t_secrets, "ENV_OVERRIDE")


def test_default_secrets_file_path():
    assert h2t_secrets.DEFAULT_SECRETS_FILE == Path.home() / ".dor" / "secrets" / "secrets.env"


def test_secrets_dir_path():
    assert h2t_secrets.SECRETS_DIR == Path.home() / ".dor" / "secrets"


def test_env_override_constant():
    assert h2t_secrets.ENV_OVERRIDE == "H2T_SECRETS_FILE"


def test_bootstrap_raises_not_implemented_initially():
    """Will be replaced in Task 2."""
    with pytest.raises(NotImplementedError):
        h2t_secrets.bootstrap()


def test_get_blob_raises_not_implemented_initially():
    """Will be replaced in Task 3."""
    with pytest.raises(NotImplementedError):
        h2t_secrets.get_blob("foo/bar")
```

- [ ] **Step 5: Run tests to verify pass**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/test_h2t_secrets.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/scripts/h2t_secrets.py plugins/h2t-core/scripts/tests/__init__.py plugins/h2t-core/scripts/tests/test_h2t_secrets.py
git -C C:/dev/h2t-skills commit -m "feat(secrets): scaffold h2t_secrets module

Empty module with public API stubs (bootstrap, get_blob), constants
(DEFAULT_SECRETS_FILE, SECRETS_DIR, ENV_OVERRIDE). 6 smoke tests verifying
shape. Implementation in Tasks 2 (bootstrap) and 3 (get_blob).

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 2: Implement bootstrap()

**Files:**
- Modify: `plugins/h2t-core/scripts/h2t_secrets.py`
- Modify: `plugins/h2t-core/scripts/tests/test_h2t_secrets.py`

- [ ] **Step 1: Replace stub tests + write 8 new tests**

Replace `test_bootstrap_raises_not_implemented_initially` with 8 real tests. Append to `test_h2t_secrets.py`:

```python
# --- bootstrap() tests (Task 2) ---


def _write_env(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_bootstrap_loads_keys_into_environ(tmp_path, monkeypatch):
    monkeypatch.delenv("FOO_KEY", raising=False)
    monkeypatch.delenv("BAR_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "FOO_KEY=foo-value\nBAR_KEY=bar-value\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    assert os.environ["FOO_KEY"] == "foo-value"
    assert os.environ["BAR_KEY"] == "bar-value"
    assert new_keys == {"FOO_KEY": "foo-value", "BAR_KEY": "bar-value"}


def test_bootstrap_does_not_override_existing_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("EXISTING_KEY", "from-shell")
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "EXISTING_KEY=from-file\nNEW_KEY=from-file\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    assert os.environ["EXISTING_KEY"] == "from-shell"  # shell wins
    assert os.environ["NEW_KEY"] == "from-file"
    assert "EXISTING_KEY" not in new_keys  # not "newly set"
    assert new_keys == {"NEW_KEY": "from-file"}


def test_bootstrap_fail_loud_on_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.env"
    with pytest.raises(FileNotFoundError) as ei:
        h2t_secrets.bootstrap(env_file=missing)
    msg = str(ei.value)
    assert str(missing) in msg
    assert "~/.dor/secrets/secrets.env" in msg or "secrets.env" in msg


def test_bootstrap_skips_comments_and_blanks(tmp_path, monkeypatch):
    monkeypatch.delenv("REAL_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "# comment line\n\n  \n# another comment\nREAL_KEY=value\n\n")

    new_keys = h2t_secrets.bootstrap(env_file=env_file)

    assert new_keys == {"REAL_KEY": "value"}


def test_bootstrap_handles_quoted_values(tmp_path, monkeypatch):
    monkeypatch.delenv("DOUBLE", raising=False)
    monkeypatch.delenv("SINGLE", raising=False)
    monkeypatch.delenv("UNQUOTED", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, 'DOUBLE="dval"\nSINGLE=\'sval\'\nUNQUOTED=uval\n')

    h2t_secrets.bootstrap(env_file=env_file)

    assert os.environ["DOUBLE"] == "dval"
    assert os.environ["SINGLE"] == "sval"
    assert os.environ["UNQUOTED"] == "uval"


def test_bootstrap_raises_on_malformed_line(tmp_path):
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "GOOD=val\nnot_a_kv_pair\n")

    with pytest.raises(ValueError) as ei:
        h2t_secrets.bootstrap(env_file=env_file)
    assert "line 2" in str(ei.value).lower() or "line=2" in str(ei.value).lower()


def test_bootstrap_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("IDEM_KEY", raising=False)
    env_file = tmp_path / "secrets.env"
    _write_env(env_file, "IDEM_KEY=idem-val\n")

    first = h2t_secrets.bootstrap(env_file=env_file)
    second = h2t_secrets.bootstrap(env_file=env_file)

    assert first == {"IDEM_KEY": "idem-val"}
    assert second == {}  # nothing new on second call


def test_bootstrap_via_env_file_override(tmp_path, monkeypatch):
    monkeypatch.delenv("OVERRIDE_KEY", raising=False)
    env_file = tmp_path / "alt.env"
    _write_env(env_file, "OVERRIDE_KEY=overridden\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(env_file))

    new_keys = h2t_secrets.bootstrap()  # no env_file arg

    assert new_keys == {"OVERRIDE_KEY": "overridden"}
```

Also DELETE the obsolete `test_bootstrap_raises_not_implemented_initially` test from Task 1 — bootstrap is implemented now.

- [ ] **Step 2: Run tests to verify FAIL**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/test_h2t_secrets.py -v
```

Expected: 8 new tests FAIL (bootstrap is still a stub raising NotImplementedError).

- [ ] **Step 3: Implement bootstrap()**

Replace the stub `bootstrap` in `h2t_secrets.py` with:

```python
def bootstrap(*, env_file: Path | None = None) -> dict[str, str]:
    """Read secrets.env and merge missing keys into os.environ.

    Args:
        env_file: Path to secrets file. Defaults to:
            $H2T_SECRETS_FILE env var if set, else DEFAULT_SECRETS_FILE.

    Returns:
        Dict of keys that were newly set (i.e., not already in os.environ).
        Existing os.environ keys are preserved (shell-export wins).

    Raises:
        FileNotFoundError: env_file does not exist.
        ValueError: a non-blank, non-comment line is not in KEY=VALUE form.
    """
    if env_file is None:
        override = os.environ.get(ENV_OVERRIDE)
        env_file = Path(override) if override else DEFAULT_SECRETS_FILE

    if not env_file.is_file():
        raise FileNotFoundError(
            f"h2t_secrets: secrets file not found at {env_file}. "
            f"Create ~/.dor/secrets/secrets.env (see "
            f"docs/superpowers/specs/2026-05-07-secrets-loader.md §5)."
        )

    new_keys: dict[str, str] = {}
    for lineno, raw in enumerate(env_file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(
                f"h2t_secrets: malformed line {lineno} in {env_file}: {raw!r} "
                f"(expected KEY=VALUE)"
            )
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key in os.environ:
            continue  # shell-export wins
        os.environ[key] = value
        new_keys[key] = value
    return new_keys
```

- [ ] **Step 4: Run to verify PASS**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/test_h2t_secrets.py -v
```

Expected: all 13 tests PASS (5 from Task 1 + 8 new).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/scripts/h2t_secrets.py plugins/h2t-core/scripts/tests/test_h2t_secrets.py
git -C C:/dev/h2t-skills commit -m "feat(secrets): implement bootstrap() with shell-export precedence

Reads KEY=VALUE pairs from secrets.env, merges missing keys into os.environ,
preserves existing keys (shell-export wins). Skips comments/blanks. Strips
matching surrounding quotes. Fail-loud on missing file. ValueError with
line number on malformed line. H2T_SECRETS_FILE env override for tests.

8 new tests cover all branches.

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 3: Implement get_blob()

**Files:**
- Modify: `plugins/h2t-core/scripts/h2t_secrets.py`
- Modify: `plugins/h2t-core/scripts/tests/test_h2t_secrets.py`

- [ ] **Step 1: Write failing tests (replace stub test)**

Delete the obsolete `test_get_blob_raises_not_implemented_initially` from Task 1. Append:

```python
# --- get_blob() tests (Task 3) ---


def test_get_blob_returns_existing_path(tmp_path, monkeypatch):
    monkeypatch.setattr(h2t_secrets, "SECRETS_DIR", tmp_path)
    blob_dir = tmp_path / "google"
    blob_dir.mkdir()
    blob = blob_dir / "oauth-client.json"
    blob.write_text('{"client_id": "fake"}', encoding="utf-8")

    result = h2t_secrets.get_blob("google/oauth-client.json")

    assert result == blob.resolve()
    assert result.is_file()


def test_get_blob_fail_loud_on_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(h2t_secrets, "SECRETS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError) as ei:
        h2t_secrets.get_blob("google/missing.json")
    assert "google/missing.json" in str(ei.value) or "missing.json" in str(ei.value)
```

- [ ] **Step 2: Run to verify FAIL**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/test_h2t_secrets.py -v -k "get_blob"
```

Expected: 2 FAIL (NotImplementedError or AttributeError).

- [ ] **Step 3: Implement get_blob()**

Replace stub in `h2t_secrets.py`:

```python
def get_blob(relative_path: str) -> Path:
    """Return absolute Path to a credential blob under SECRETS_DIR.

    Args:
        relative_path: e.g. 'google/gmail-oauth.json' or 'telegram/h2t.session'.

    Returns:
        Absolute resolved Path.

    Raises:
        FileNotFoundError: blob does not exist at the resolved path.
    """
    candidate = (SECRETS_DIR / relative_path).resolve()
    if not candidate.is_file():
        raise FileNotFoundError(
            f"h2t_secrets: blob not found at {candidate} "
            f"(relative_path={relative_path!r})"
        )
    return candidate
```

- [ ] **Step 4: Run to verify PASS**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/test_h2t_secrets.py -v
```

Expected: all 14 tests PASS (4 constants + 8 bootstrap + 2 get_blob).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/scripts/h2t_secrets.py plugins/h2t-core/scripts/tests/test_h2t_secrets.py
git -C C:/dev/h2t-skills commit -m "feat(secrets): implement get_blob() for credential file paths

Returns absolute Path to file under ~/.dor/secrets/. Fail-loud if missing.
2 tests cover success + missing-file. Future use: OAuth JSON path moves
in per-skill migration issues #109/#110/#111.

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 4: Migrate exa_search.py to use h2t_secrets

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing integration test**

Append to `test_exa_search.py` (at the end, after existing 88 tests):

```python
# --- h2t_secrets bootstrap integration (Task 4 of secrets-loader) ---


def test_main_calls_h2t_secrets_bootstrap(monkeypatch, capsys):
    """exa_search.main() must invoke h2t_secrets.bootstrap() before parsing args.

    Mocks the loader so we don't need a real secrets.env. Verifies the call
    happens and that a missing-file error surfaces as exit 4 with EXA_ERROR:ENV.
    """
    bootstrap_called = []

    def fake_bootstrap(*, env_file=None):
        bootstrap_called.append(True)
        return {}

    # Patch the dynamically-loaded bootstrap inside _load_h2t_secrets
    monkeypatch.setattr(exa_search, "_h2t_secrets_bootstrap", fake_bootstrap)
    monkeypatch.setenv("EXA_API_KEY", "stub-for-preflight-skip")

    rc = exa_search.main(["--version"])

    assert rc == 0
    assert bootstrap_called == [True]


def test_main_handles_missing_secrets_file(monkeypatch, capsys):
    """If h2t_secrets.bootstrap raises FileNotFoundError, main exits 4 with EXA_ERROR:ENV."""

    def failing_bootstrap(*, env_file=None):
        raise FileNotFoundError("h2t_secrets: secrets file not found at /tmp/missing")

    monkeypatch.setattr(exa_search, "_h2t_secrets_bootstrap", failing_bootstrap)

    with pytest.raises(SystemExit) as excinfo:
        exa_search.main(["search", "--query", "x", "--mode", "generic"])

    assert excinfo.value.code == 4
    assert "EXA_ERROR:ENV" in capsys.readouterr().err
```

- [ ] **Step 2: Run to verify FAIL**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-ops/skills/research/tests/test_exa_search.py -v -k "h2t_secrets_bootstrap or missing_secrets_file"
```

Expected: 2 FAIL (`AttributeError: _h2t_secrets_bootstrap` not present in module).

- [ ] **Step 3: Add `_load_h2t_secrets()` helper + `bootstrap()` call**

In `exa_search.py`, find the imports block (around lines 6–22). After the existing imports, add:

```python
import importlib.util


def _load_h2t_secrets():
    """Dynamically import h2t_secrets from h2t-core plugin.

    Cross-plugin path resolution:
      1. relative path from this file: ../../../../h2t-core/scripts/h2t_secrets.py
      2. fallback: $H2T_PLUGIN_ROOT/h2t-core/scripts/h2t_secrets.py
      3. else: fail-loud
    """
    here = Path(__file__).resolve()
    relative = here.parents[3] / "h2t-core" / "scripts" / "h2t_secrets.py"
    candidates = [relative]
    plugin_root = os.environ.get("H2T_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "h2t-core" / "scripts" / "h2t_secrets.py")

    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("h2t_secrets", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(
        f"h2t_secrets module not found. Tried: {[str(c) for c in candidates]}. "
        f"Set H2T_PLUGIN_ROOT or restore plugins/h2t-core/scripts/h2t_secrets.py."
    )


# Cached at import time so tests can monkeypatch _h2t_secrets_bootstrap directly
_h2t_secrets_bootstrap = None
```

Then in `main()`, immediately after the stdout/stderr UTF-8 reconfigure block (currently around lines 434–438) and before `parser = _build_parser()`, add:

```python
    # Load secrets from ~/.dor/secrets/secrets.env if available.
    # Shell-exported env vars take precedence (non-overriding merge).
    global _h2t_secrets_bootstrap
    if _h2t_secrets_bootstrap is None:
        try:
            _h2t_secrets_bootstrap = _load_h2t_secrets().bootstrap
        except FileNotFoundError as e:
            die(4, f"EXA_ERROR:ENV {e}")
    try:
        _h2t_secrets_bootstrap()
    except FileNotFoundError as e:
        die(4, f"EXA_ERROR:ENV {e}")
    except (ValueError, OSError) as e:
        die(4, f"EXA_ERROR:ENV malformed secrets.env: {e}")
```

- [ ] **Step 4: Run new tests to verify PASS**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-ops/skills/research/tests/test_exa_search.py -v -k "h2t_secrets_bootstrap or missing_secrets_file"
```

Expected: 2 PASS.

- [ ] **Step 5: Run full research test suite — verify no regressions**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: 90 tests pass (88 existing + 2 new).

**Subtle:** existing tests that call `exa_search.main(...)` directly will trigger `_load_h2t_secrets()`. If the loader itself works (real `~/.dor/secrets/secrets.env` exists) — fine. If not — they fail.

**Mitigation:** during this PR's test run, the developer's machine may not have `~/.dor/secrets/secrets.env` yet (per migration step §5 of spec). Before running tests, ensure either:

   (a) `~/.dor/secrets/secrets.env` exists (even with placeholder content), OR
   (b) Set `H2T_SECRETS_FILE` to a tmp file with valid content, OR
   (c) Add a conftest.py fixture that auto-creates a tmp env file and sets `H2T_SECRETS_FILE`

**Recommended: option (c) — add `conftest.py` for test isolation.**

Create `plugins/h2t-ops/skills/research/tests/conftest.py`:

```python
"""Pytest fixtures for research tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_secrets(tmp_path_factory, monkeypatch):
    """Provide an isolated secrets.env so tests don't depend on the user's
    real ~/.dor/secrets/secrets.env file."""
    sec_dir = tmp_path_factory.mktemp("h2t-secrets")
    env_file = sec_dir / "secrets.env"
    env_file.write_text("# test placeholder\n", encoding="utf-8")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(env_file))
    yield
```

This fixture runs before every test in this directory. Tests that already monkeypatch `_h2t_secrets_bootstrap` are unaffected (their monkeypatch wins). Tests that hit the real loader get a valid empty env file.

- [ ] **Step 6: Run full suite again — confirm 90 PASS**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

- [ ] **Step 7: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py plugins/h2t-ops/skills/research/tests/conftest.py
git -C C:/dev/h2t-skills commit -m "feat(research): bootstrap h2t_secrets at startup

Add _load_h2t_secrets() helper using importlib.util to cross-plugin import.
main() calls bootstrap() before arg parsing. FileNotFoundError surfaces as
exit 4 + EXA_ERROR:ENV (instead of silent missing-EXA_API_KEY drift bug).

conftest.py adds an autouse fixture providing an isolated empty secrets.env
so tests don't depend on the user's real ~/.dor/secrets/.

Closes the drift bug from PR #106 closeout.

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 5: Add rotation runbook template

**Files:**
- Create: `plugins/h2t-core/scripts/secrets-readme-template.md`

- [ ] **Step 1: Create template file**

Create `plugins/h2t-core/scripts/secrets-readme-template.md`:

```markdown
# ~/.dor/secrets/ — h2t Secrets Vault

This directory is the canonical home for all h2t skill secrets. Loader:
`plugins/h2t-core/scripts/h2t_secrets.py`.

## Layout

```
~/.dor/secrets/
  README.md              # this file
  secrets.env            # KEY=VALUE pairs
  google/                # OAuth JSONs (Gmail, Calendar, Drive)
  meetgeek/              # MeetGeek blobs (if any)
  telegram/              # Telethon session
```

## secrets.env format

Standard dotenv. One `KEY=VALUE` per line. Comments start with `#`.
Quoted values are stripped (both `"..."` and `'...'`). No multiline values.

```env
# Exa search (https://dashboard.exa.ai/api-keys)
EXA_API_KEY=<uuid>
EXA_API_KEY_BACKUP=<uuid>

# Google Gemini (https://aistudio.google.com/apikey)
GEMINI_API_KEY=<key>

# MeetGeek (https://meetgeek.ai/settings/api)
MEETGEEK_API_KEY=<key>
MEETGEEK_BASE_URL=https://api.meetgeek.ai
MEETGEEK_TIMEOUT=30
MEETGEEK_MAX_PAGES=1000
MEETGEEK_WEBHOOK_SECRET=<secret>
```

## Loader behaviour

- Reads file at startup of every Python skill that calls `h2t_secrets.bootstrap()`.
- **Shell-exported env vars take precedence.** If `EXA_API_KEY` is already in `os.environ` (e.g. set in `.bashrc`), the value in `secrets.env` is ignored. This allows ad-hoc experimentation without editing the file.
- Fail-loud if `secrets.env` is missing.
- ValueError on malformed lines (with line number).

## Rotation

| Key | Source | Test command |
|---|---|---|
| `EXA_API_KEY` / `EXA_API_KEY_BACKUP` | https://dashboard.exa.ai/api-keys | `~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/research/scripts/exa_search.py preflight` |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | (no built-in preflight; run any Gemini-using skill) |
| `MEETGEEK_API_KEY` | https://meetgeek.ai/settings/api | `python plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py meetings --limit 1` |

## Multi-machine

`~/.dor/` is Syncthing-synced between AUTOMATA and MacBook Pro 3 → identical layout, identical keys on both. No need to re-enter on each machine.

## Distribution safety

This directory is **never** committed to any h2t repo. The loader (which IS in the repo) just gives you the convention; the actual key values stay on your machine. When publishing skills externally, distribute loader + this README; the user creates their own `~/.dor/secrets/` from scratch.

## Adding a new key

1. Edit `secrets.env`, add `NEW_KEY=value` line.
2. Update this README's rotation table.
3. (Future) `h2t-core:setup --secrets` will automate this once issue #112 lands.
```

- [ ] **Step 2: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/scripts/secrets-readme-template.md
git -C C:/dev/h2t-skills commit -m "docs(secrets): rotation runbook template for ~/.dor/secrets/

Template file shipped in repo. User copies to ~/.dor/secrets/README.md
during migration. Documents layout, format, loader behaviour, rotation
sources, multi-machine sync, distribution safety. Future setup wizard
(#112) will copy this automatically.

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 6: Bump h2t-core plugin version

**Files:**
- Modify (via `bump_plugin.py`): `plugins/h2t-core/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: Inspect current h2t-core version**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -c "import json; print(json.load(open('C:/dev/h2t-skills/plugins/h2t-core/.claude-plugin/plugin.json'))['version'])"
```

Note the current version (let's call it `X.Y.Z`).

- [ ] **Step 2: Patch bump**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/scripts/bump_plugin.py h2t-core <X.Y.Z+1>
```

E.g., if current is `1.0.0`, bump to `1.0.1`. Per user CLAUDE.md: minor only after live verification → first PR is patch.

- [ ] **Step 3: Verify**

Use Grep tool with pattern `"version"` in `plugins/h2t-core/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` (the h2t-core entry). Both should show the new patch version.

- [ ] **Step 4: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git -C C:/dev/h2t-skills commit -m "chore(secrets): bump h2t-core to <X.Y.Z+1> for h2t_secrets module

Patch bump per spec §10. Minor deferred until live verification of the
loader in real skill runs.

Refs: lichtpfad/h2t-skills#108"
```

---

## Task 7: Final integration check + push branch

**Files:** none (verification only).

- [ ] **Step 1: Run full test suite — both new and existing**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest C:/dev/h2t-skills/plugins/h2t-core/scripts/tests/ C:/dev/h2t-skills/plugins/h2t-ops/skills/research/tests/ -v
```

Expected: 14 (h2t_secrets) + 90 (research) = 104 tests pass.

- [ ] **Step 2: Verify cross-plugin import path resolution**

Quick smoke without running tests:

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'C:/dev/h2t-skills/plugins/h2t-ops/skills/research/scripts')
import exa_search
mod = exa_search._load_h2t_secrets()
print('loaded:', mod.__file__)
print('has bootstrap:', hasattr(mod, 'bootstrap'))
"
```

Expected stdout:
```
loaded: <abs path>/plugins/h2t-core/scripts/h2t_secrets.py
has bootstrap: True
```

- [ ] **Step 3: Verify git log**

```
git -C C:/dev/h2t-skills log --oneline main..HEAD
```

Expected: 6 commits (one per task) in order: scaffold → bootstrap → get_blob → research migration → readme template → version bump.

- [ ] **Step 4: Push branch**

Branch is `feature/secrets-loader`. Push to origin:

```
git -C C:/dev/h2t-skills push -u origin feature/secrets-loader
```

- [ ] **Step 5: Open PR**

```
gh pr create --repo lichtpfad/h2t-skills --base main --head feature/secrets-loader \
  --title "feat(secrets): minimal h2t_secrets loader for issue #108" \
  --body "$(cat <<'EOF'
Closes #108. First child of umbrella #107.

## Summary

Ships `h2t_secrets` loader in `plugins/h2t-core/scripts/`. Single source of truth for secrets at `~/.dor/secrets/secrets.env`. Migrates only `h2t-ops:research` to use it; per-skill follow-ups #109/#110/#111/#112 are tracked separately.

## What changed

- `plugins/h2t-core/scripts/h2t_secrets.py` — new module: `bootstrap()`, `get_blob()`, ~80 LOC stdlib only.
- `plugins/h2t-core/scripts/tests/test_h2t_secrets.py` — 14 unit tests.
- `plugins/h2t-ops/skills/research/scripts/exa_search.py` — `_load_h2t_secrets()` cross-plugin importer; `bootstrap()` called in `main()` before arg parsing; `FileNotFoundError` → exit 4 + `EXA_ERROR:ENV`.
- `plugins/h2t-ops/skills/research/tests/conftest.py` — autouse fixture isolates tests from real `~/.dor/secrets/`.
- 2 new tests in `test_exa_search.py` verify bootstrap is invoked + missing-file behaviour.
- `plugins/h2t-core/scripts/secrets-readme-template.md` — rotation runbook template.
- `h2t-core` plugin patch bump.

## Why

A drift bug surfaced during PR #106 closeout: `EXA_API_KEY` lived in shell env on AUTOMATA but was missing from `~/.dor/secrets.env`. Sessions launched from a different shell had no key, agent hit `EXA_ERROR:ENV` on preflight, then dispatched the deprecated `h2t:research-agent` and silently fell back to `WebSearch`/`WebFetch`.

Single loader convention surfaces this drift fail-loud and gives every Python skill a predictable path to the canonical secrets file.

## Backward compatibility

- All other skills (`meetgeek`, `telegram`, `process-transcripts`, OAuth-based) untouched. They keep working via shell-export.
- Shell-exported env vars take precedence over `secrets.env`. Ad-hoc experimentation unbroken.
- Existing 88 research tests + 2 new = 90 passing.

## Test plan

- [x] `python -m pytest plugins/h2t-core/scripts/tests/ plugins/h2t-ops/skills/research/tests/ -v` → 104 passing
- [x] Cross-plugin import smoke test passes
- [ ] Live smoke after merge: a fresh shell with no `EXA_API_KEY` exported → research preflight succeeds via `secrets.env`

## Refs

- Issue: #108
- Umbrella: #107
- Spec: `docs/superpowers/specs/2026-05-07-secrets-loader.md`
- Plan: `docs/superpowers/plans/2026-05-07-secrets-loader.md`
EOF
)"
```

- [ ] **Step 6: Document manual user steps in PR comment**

After PR is open, post a comment with the user-side migration steps that this PR's code does NOT do automatically:

```
gh pr comment <PR_NUMBER> --repo lichtpfad/h2t-skills --body "$(cat <<'EOF'
## Manual user steps required after merge

This PR ships the loader but does NOT touch your home directory. After merge, perform these once:

1. Create `~/.dor/secrets/` directory.
2. Copy `plugins/h2t-core/scripts/secrets-readme-template.md` → `~/.dor/secrets/README.md`. Fill in actual key sources/test commands as needed.
3. Create `~/.dor/secrets/secrets.env` with all current keys:
   - `EXA_API_KEY` from current shell env (or `~/.h2t/config/secrets/exa-keys.md` registry)
   - `EXA_API_KEY_BACKUP` from `~/.h2t/config/secrets/exa-keys.md` (secondary)
   - `GEMINI_API_KEY` from old `~/.dor/secrets.env`
   - `MEETGEEK_API_KEY` from wherever it lives now
4. Verify: open a fresh shell with NO `EXA_API_KEY` exported. Run:
   ```
   ~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/research/scripts/exa_search.py preflight
   ```
   Expected: `OK`.
5. Delete the old `~/.dor/secrets.env` file (now superseded by `~/.dor/secrets/secrets.env`).
6. Update user-level `~/.claude/CLAUDE.md` `Config:` line:
   - Old: `Config:    ~/.h2t/config/  (domains.yaml, repo-mapping.yaml, secrets/)`
   - New: `Config:    ~/.h2t/config/ (domains.yaml, repo-mapping.yaml) | Secrets: ~/.dor/secrets/`
7. Update memory note `feedback_h2t_secrets_runtime` to reference the new layout.
8. Add `~/.h2t/config/secrets/README.md` redirect note pointing at `~/.dor/secrets/`.

Once steps 1–7 are done, claim live verification → bump `h2t-core` to next minor in a separate commit.
EOF
)"
```

---

## Self-Review Checklist (post-implementation)

After completing all tasks:

- [ ] `h2t_secrets.bootstrap()` follows shell-export-wins ordering (verified by `test_bootstrap_does_not_override_existing_environ`).
- [ ] Fail-loud is consistent: missing file → FileNotFoundError; malformed line → ValueError.
- [ ] No real key values appear in any commit. Run:
  ```
  git -C C:/dev/h2t-skills log -p main..HEAD | grep -iE "EXA_API_KEY=[a-z0-9-]{8,}" || echo "OK no leaked keys"
  ```
- [ ] `_load_h2t_secrets()` handles both relative-path and `H2T_PLUGIN_ROOT` fallback.
- [ ] All 104 tests pass.
- [ ] No drive-by changes in unrelated skills.
- [ ] Plan-task-to-commit ratio: 6 commits, 6 tasks (Task 7 is verify-only).
