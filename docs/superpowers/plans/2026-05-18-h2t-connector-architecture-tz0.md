# ТЗ-0 H2T Connector Architecture — Core Foundation + Notion Walking Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `h2t` import package + `core/` foundation + a fully-migrated Notion connector (walking skeleton) proving the connector standard from `docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md`.

**Architecture:** Monolithic `h2t` package, lazily auto-registered connectors. `client.py` = API logic (typed errors, no I/O side effects); `commands.py` = thin argparse adapter (lazy client import); `core/` = registry, errors, envelope, output, secrets. New entrypoint `h2t.cli:main` delegates non-migrated commands to legacy `lib.cli.main:main` unchanged.

**Tech Stack:** Python 3.11, stdlib `argparse`/`importlib`, `pytest`, `notion-client`, `httpx`, `python-dotenv`, `uv` for install.

---

## Locked Design Decisions (resolve §14 + transition gap before Task 1)

1. **Install source (dev/CI):** `uv tool install --editable .` from repo root (falls back to `pip install -e .` into `~/.h2t/venv`). External sharing (git-ref / PyPI) is a **separate rollout decision**, explicitly NOT in ТЗ-0 — it does not block the walking skeleton.
2. **Transition compatibility (spec gap, decided here):** flipping `[project.scripts]` to `h2t.cli:main` must not regress `h2t gather` or `h2t ingest gmail/calendar`. `h2t/cli.py` recognizes migrated commands (`notion`, `connectors`, `--version`) and **delegates everything else** to legacy `lib.cli.main:main` by importing and calling it. `lib/` is NOT modified in ТЗ-0; its pre-existing `sys.path.insert` is knowingly retained until its commands migrate (ТЗ-1/ТЗ-2). The "no `sys.path.insert`" DoD applies to the **new `h2t` package**, which adds none.
3. **`ingest notion` shim:** `h2t ingest notion …` forwards to the **new** notion connector (single implementation), with a small explicit legacy-arg mapping (Task 10). Deprecation notice → stderr on human/`md`, silent on `--json`, forwarded exit code, stateless (spec §10).
4. **Notion SDK deps are NOT declared project deps** (`pyproject` `dependencies = []`; they ship via `requirements.txt`). Per spec §4.1 they are therefore treated as **optional** → imported lazily inside `client.py` methods/`__init__`, missing import → `ConfigError` with install hint. Never module-level in `client.py`.

---

## File Structure

**Create:**
- `h2t/__init__.py` — package marker, `__version__`
- `h2t/cli.py` — entrypoint: parser from registry, dispatch, error→exit, legacy delegation, ingest shim
- `h2t/core/__init__.py`
- `h2t/core/errors.py` — typed exceptions + `EXIT_CODES` + `exit_code_for()`
- `h2t/core/envelope.py` — `success_envelope()` / `error_envelope()`
- `h2t/core/output.py` — `emit()` for json / md / human per spec §6
- `h2t/core/registry.py` — `ConnectorSpec`, `resolve_client()`, `discover()`
- `h2t/core/secrets.py` — `load_secrets()`, `resolve_notion_token()`
- `h2t/connectors/__init__.py` — namespace marker (discovery scans this package)
- `h2t/connectors/notion/__init__.py` — `CONNECTOR` spec + `from .commands import register`
- `h2t/connectors/notion/client.py` — re-wrapped `NotionClient` (typed errors)
- `h2t/connectors/notion/commands.py` — `register()` + `run_*` handlers
- `tests/core/test_errors.py`, `tests/core/test_envelope.py`, `tests/core/test_output.py`, `tests/core/test_registry.py`, `tests/core/test_secrets.py`
- `tests/connectors/notion/test_client.py`, `tests/connectors/notion/test_commands.py`

**Modify:**
- `pyproject.toml` — `[project.scripts] h2t = "h2t.cli:main"`; add `h2t*` to packages; keep `lib*` (transitional)
- `plugins/h2t-ops/skills/notion/SKILL.md` — spec §8 conformance

---

### Task 1: Package skeleton + pyproject flip

**Files:**
- Create: `h2t/__init__.py`, `h2t/core/__init__.py`, `h2t/connectors/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create package markers**

`h2t/__init__.py`:
```python
"""h2t — unified connector CLI + library. See docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md"""
__version__ = "0.2.0"
```

`h2t/core/__init__.py`:
```python
"""h2t.core — shared foundation: registry, errors, envelope, output, secrets."""
```

`h2t/connectors/__init__.py`:
```python
"""h2t.connectors — connector subpackages. Discovered lazily by h2t.core.registry."""
```

- [ ] **Step 2: Flip pyproject entrypoint + packages**

In `pyproject.toml` replace:
```toml
[project.scripts]
h2t = "lib.cli.main:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["lib*"]
```
with:
```toml
[project.scripts]
h2t = "h2t.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["h2t*", "lib*"]
```
Bump `version = "0.1.0"` → `version = "0.2.0"` in `[project]`.

- [ ] **Step 3: Add minimal cli.py stub so install succeeds**

`h2t/cli.py` (replaced fully in Task 10):
```python
"""h2t CLI entrypoint (stub — completed in Task 10)."""
import sys


def main() -> None:
    print("h2t 0.2.0 (skeleton)", file=sys.stderr)
    sys.exit(0)
```

- [ ] **Step 4: Install editable and verify import + entrypoint**

Run:
```
C:/dev/h2t-skills/.venv/Scripts/pip install -e C:/dev/h2t-skills
C:/dev/h2t-skills/.venv/Scripts/python -c "import h2t, h2t.core, h2t.connectors; print(h2t.__version__)"
```
Expected: prints `0.2.0`, no ImportError.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/ pyproject.toml
git -C C:/dev/h2t-skills commit -m "feat(h2t): package skeleton + entrypoint flip to h2t.cli:main"
```

---

### Task 2: core/errors.py — typed exceptions + exit-code map

**Files:**
- Create: `h2t/core/errors.py`
- Test: `tests/core/test_errors.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_errors.py`:
```python
import pytest
from h2t.core.errors import (
    H2TError, UsageError, ConfigError, AuthError,
    ProviderError, NotFoundError, NetworkError, exit_code_for, EXIT_CODES,
)


@pytest.mark.parametrize("exc_cls,code", [
    (ProviderError, 1), (UsageError, 2), (ConfigError, 3),
    (AuthError, 4), (NotFoundError, 5), (NetworkError, 6),
])
def test_exit_code_for_each_type(exc_cls, code):
    assert exit_code_for(exc_cls("x")) == code


def test_exit_code_for_unknown_is_one():
    assert exit_code_for(ValueError("x")) == 1


def test_all_typed_errors_subclass_h2terror():
    for c in (UsageError, ConfigError, AuthError, ProviderError, NotFoundError, NetworkError):
        assert issubclass(c, H2TError)


def test_exit_codes_table_complete():
    assert EXIT_CODES == {"ok": 0, "provider": 1, "usage": 2,
                          "config": 3, "auth": 4, "not_found": 5, "network": 6}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.errors`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/errors.py`:
```python
"""Typed error hierarchy + exit-code mapping (spec §5)."""
from __future__ import annotations


class H2TError(Exception):
    """Base. Carries an optional install/fix hint."""
    kind: str = "provider"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class UsageError(H2TError):
    kind = "usage"


class ConfigError(H2TError):
    kind = "config"


class AuthError(H2TError):
    kind = "auth"


class ProviderError(H2TError):
    kind = "provider"


class NotFoundError(H2TError):
    kind = "not_found"


class NetworkError(H2TError):
    kind = "network"


EXIT_CODES: dict[str, int] = {
    "ok": 0, "provider": 1, "usage": 2,
    "config": 3, "auth": 4, "not_found": 5, "network": 6,
}


def exit_code_for(exc: BaseException) -> int:
    """Map an exception to its exit code. Unknown → 1 (provider/runtime)."""
    if isinstance(exc, H2TError):
        return EXIT_CODES[exc.kind]
    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_errors.py -v`
Expected: PASS (all parametrized + 3).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/core/errors.py tests/core/test_errors.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): typed errors + exit-code map"
```

---

### Task 3: core/envelope.py — universal result/error shape

**Files:**
- Create: `h2t/core/envelope.py`
- Test: `tests/core/test_envelope.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_envelope.py`:
```python
from h2t.core.envelope import success_envelope, error_envelope
from h2t.core.errors import AuthError


def test_success_shape():
    env = success_envelope("notion", {"id": "abc"})
    assert env == {"ok": True, "provider": "notion", "result": {"id": "abc"}}


def test_error_shape_with_hint():
    env = error_envelope("notion", AuthError("denied", hint="Set NOTION_API_TOKEN"))
    assert env == {
        "ok": False, "provider": "notion",
        "error": {"type": "auth", "message": "denied", "hint": "Set NOTION_API_TOKEN"},
    }


def test_error_shape_unknown_exception_is_provider():
    env = error_envelope("notion", ValueError("boom"))
    assert env["error"]["type"] == "provider"
    assert env["error"]["hint"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_envelope.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.envelope`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/envelope.py`:
```python
"""Universal command result/error envelope (spec §6)."""
from __future__ import annotations

from typing import Any

from h2t.core.errors import H2TError


def success_envelope(provider: str, result: Any) -> dict[str, Any]:
    return {"ok": True, "provider": provider, "result": result}


def error_envelope(provider: str, exc: BaseException) -> dict[str, Any]:
    kind = exc.kind if isinstance(exc, H2TError) else "provider"
    hint = exc.hint if isinstance(exc, H2TError) else None
    return {
        "ok": False,
        "provider": provider,
        "error": {"type": kind, "message": str(exc), "hint": hint},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_envelope.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/core/envelope.py tests/core/test_envelope.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): universal result/error envelope"
```

---

### Task 4: core/output.py — json / md / human emitter

**Files:**
- Create: `h2t/core/output.py`
- Test: `tests/core/test_output.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_output.py`:
```python
import json
from h2t.core.output import emit
from h2t.core.errors import AuthError


def test_emit_json_success(capsys):
    code = emit("notion", result={"id": "p1"}, fmt="json")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"ok": True, "provider": "notion", "result": {"id": "p1"}}
    assert out.err == ""


def test_emit_json_error_goes_to_stderr_and_nonzero(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="json")
    out = capsys.readouterr()
    assert code == 4
    payload = json.loads(out.err)
    assert payload["ok"] is False and payload["error"]["type"] == "auth"
    assert out.out == ""


def test_emit_md_passthrough_string(capsys):
    code = emit("notion", result="# Title\n", fmt="md")
    out = capsys.readouterr()
    assert code == 0 and out.out == "# Title\n\n" or out.out == "# Title\n"


def test_emit_human_error_writes_stderr(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="human")
    out = capsys.readouterr()
    assert code == 4
    assert "denied" in out.err and "Set NOTION_API_TOKEN" in out.err
    assert out.out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_output.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.output`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/output.py`:
```python
"""Output emitter: --json / --format md / default human (spec §6)."""
from __future__ import annotations

import json
import sys
from typing import Any

from h2t.core.envelope import error_envelope, success_envelope
from h2t.core.errors import exit_code_for


def emit(provider: str, *, result: Any = None, exc: BaseException | None = None,
         fmt: str = "human") -> int:
    """Render to stdout (success) or stderr (error). Return exit code.

    fmt: "json" | "md" | "human". Errors are always non-zero and stderr.
    """
    if exc is not None:
        code = exit_code_for(exc)
        if fmt == "json":
            print(json.dumps(error_envelope(provider, exc), ensure_ascii=False), file=sys.stderr)
        else:
            env = error_envelope(provider, exc)["error"]
            line = f"error[{env['type']}]: {env['message']}"
            if env["hint"]:
                line += f"\nhint: {env['hint']}"
            print(line, file=sys.stderr)
        return code

    if fmt == "json":
        print(json.dumps(success_envelope(provider, result), ensure_ascii=False))
    elif fmt == "md":
        print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
    else:  # human
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_output.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/core/output.py tests/core/test_output.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): output emitter (json/md/human)"
```

---

### Task 5: core/registry.py — ConnectorSpec + lazy discovery

**Files:**
- Create: `h2t/core/registry.py`
- Test: `tests/core/test_registry.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_registry.py`:
```python
import sys
import builtins
import pytest
from h2t.core.registry import ConnectorSpec, discover, resolve_client


def test_connectorspec_fields():
    spec = ConnectorSpec(name="x", help="h", client="pkg.mod:Cls", register=lambda s: None)
    assert spec.name == "x" and spec.client == "pkg.mod:Cls"


def test_discover_finds_notion():
    specs = {s.name: s for s in discover()}
    assert "notion" in specs
    assert specs["notion"].client == "h2t.connectors.notion.client:NotionClient"


def test_discover_does_not_import_notion_sdk(monkeypatch):
    # Simulate notion-client / httpx being absent: import must NOT be triggered
    real_import = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError(f"discovery must not import {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    sys.modules.pop("h2t.connectors.notion.client", None)
    names = {s.name for s in discover()}
    assert "notion" in names  # discovery succeeded with zero heavy imports


def test_resolve_client_lazy_returns_class():
    spec = next(s for s in discover() if s.name == "notion")
    cls = resolve_client(spec)
    assert cls.__name__ == "NotionClient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.registry`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/registry.py`:
```python
"""Connector registry: explicit ConnectorSpec, lazy discovery (spec §4)."""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import h2t.connectors as _connectors_pkg


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    help: str
    client: str                      # lazy "module:attr" — resolved on demand only
    register: Callable[[Any], None]  # register(subparsers) -> None


def discover() -> Iterator[ConnectorSpec]:
    """Yield CONNECTOR from each h2t.connectors.<name> subpackage.

    Importing a subpackage __init__ must be cheap (no SDK/secrets/network);
    `from .commands import register` in __init__ is allowed because commands.py
    has no module-level heavy imports (spec §4.1).
    """
    for mod in pkgutil.iter_modules(_connectors_pkg.__path__):
        if not mod.ispkg:
            continue
        sub = importlib.import_module(f"h2t.connectors.{mod.name}")
        spec = getattr(sub, "CONNECTOR", None)
        if isinstance(spec, ConnectorSpec):
            yield spec


def resolve_client(spec: ConnectorSpec) -> type:
    """Import and return the client class — only when actually needed."""
    module_path, _, attr = spec.client.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, attr)
```

- [ ] **Step 4: Run test to verify it passes**

Run (after Task 9 creates the notion subpackage, this fully passes; run now to confirm `test_connectorspec_fields` passes and others fail on missing notion):
`C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_registry.py::test_connectorspec_fields -v`
Expected: PASS. (Remaining registry tests pass after Task 9 — re-run in Task 9 Step 6.)

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/core/registry.py tests/core/test_registry.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): ConnectorSpec + lazy discovery"
```

---

### Task 6: core/secrets.py — minimal secrets + Notion token

**Files:**
- Create: `h2t/core/secrets.py`
- Test: `tests/core/test_secrets.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_secrets.py`:
```python
import pytest
from h2t.core.secrets import resolve_notion_token, load_secrets
from h2t.core.errors import ConfigError


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "envtok")
    assert resolve_notion_token() == "envtok"


def test_config_file_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    cfg = tmp_path / ".config" / "notion" / "token"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("filetok\n")
    monkeypatch.setattr("h2t.core.secrets.Path.home", lambda: tmp_path)
    assert resolve_notion_token() == "filetok"


def test_missing_raises_configerror(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr("h2t.core.secrets.Path.home", lambda: tmp_path)
    with pytest.raises(ConfigError) as ei:
        resolve_notion_token()
    assert ei.value.hint and "NOTION_API_TOKEN" in ei.value.hint


def test_load_secrets_is_non_override(tmp_path, monkeypatch):
    monkeypatch.setenv("FOO", "shell")
    env = tmp_path / "secrets.env"
    env.write_text("FOO=file\nBAR=baz\n")
    load_secrets(env_file=env)
    import os
    assert os.environ["FOO"] == "shell"   # shell wins
    assert os.environ["BAR"] == "baz"     # new key loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_secrets.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.secrets`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/secrets.py`:
```python
"""Minimal secrets loader + Notion token resolution (spec §11: minimal only)."""
from __future__ import annotations

import os
from pathlib import Path

from h2t.core.errors import ConfigError

DEFAULT_SECRETS = Path.home() / ".dor" / "secrets.env"


def load_secrets(env_file: Path | None = None) -> None:
    """Merge KEY=VALUE lines into os.environ WITHOUT overriding existing keys."""
    path = env_file or DEFAULT_SECRETS
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def resolve_notion_token() -> str:
    """Env var → ~/.config/notion/token → ConfigError with install hint."""
    tok = os.getenv("NOTION_API_TOKEN")
    if tok:
        return tok
    cfg = Path.home() / ".config" / "notion" / "token"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise ConfigError(
        "Notion API token not found.",
        hint="Set NOTION_API_TOKEN in ~/.dor/secrets.env or create ~/.config/notion/token",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_secrets.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/core/secrets.py tests/core/test_secrets.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): minimal secrets + notion token resolution"
```

---

### Task 7: connectors/notion/client.py — re-wrap with typed errors

**Files:**
- Create: `h2t/connectors/notion/__init__.py` (empty marker for now — `CONNECTOR` added in Task 9)
- Create: `h2t/connectors/notion/client.py`
- Test: `tests/connectors/notion/test_client.py`

This is a **mechanical re-wrap** of `lib/clients/notion.py` (spec §10 rule 1): same API logic, only side-effects and error types change.

- [ ] **Step 1: Create the subpackage marker**

`h2t/connectors/notion/__init__.py`:
```python
"""Notion connector. CONNECTOR + register added in Task 9."""
```

- [ ] **Step 2: Write the failing test**

`tests/connectors/notion/test_client.py`:
```python
import pytest
from h2t.connectors.notion.client import NotionClient
from h2t.core.errors import ConfigError


@pytest.fixture
def conv():
    # bypass __init__ (no token / no SDK) — pure converters only
    c = object.__new__(NotionClient)
    c.token = "fake"
    return c


def test_rich_text_bold(conv):
    rich = [{"type": "text", "text": {"content": "hello"}, "annotations": {"bold": True}}]
    assert conv._rich_text_to_markdown(rich) == "**hello**"


def test_markdown_to_blocks_heading(conv):
    blocks = conv.markdown_to_blocks("# Hello")
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Hello"


def test_blocks_to_markdown_roundtrip(conv):
    md = "# Heading\n\nSome text.\n\n- list item\n\n"
    assert conv.blocks_to_markdown(conv.markdown_to_blocks(md)).strip() == md.strip()


def test_missing_token_raises_configerror(monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr("h2t.core.secrets.Path.home", lambda: __import__("pathlib").Path("/nonexistent-xyz"))
    with pytest.raises(ConfigError):
        NotionClient()


def test_missing_sdk_raises_configerror(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "tok")
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name == "notion_client":
            raise ImportError("no notion_client")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    with pytest.raises(ConfigError) as ei:
        NotionClient()
    assert "notion-client" in (ei.value.hint or "")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.connectors.notion.client`.

- [ ] **Step 4: Create client.py from the legacy file with these exact transforms**

Copy `lib/clients/notion.py` → `h2t/connectors/notion/client.py`, then apply EXACTLY these edits:

1. Replace the top of file (lines 1–44, from the docstring through `self.client = Client(auth=self.token)`) with:
```python
"""NotionClient — bidirectional Notion adapter (re-wrapped, typed errors).

API logic is byte-identical to lib/clients/notion.py; only side effects and
error types changed per spec §10 (re-wrap not rewrite).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from h2t.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError,
)
from h2t.core.secrets import resolve_notion_token


class NotionClient:
    """Notion API client — read and write pages and databases."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or resolve_notion_token()  # raises ConfigError if missing
        try:
            from notion_client import Client  # optional dep — lazy (spec §4.1)
        except ImportError as e:
            raise ConfigError(
                "notion-client library not installed.",
                hint="pip install notion-client httpx  (or run /h2t-core:setup)",
            ) from e
        self.client = Client(auth=self.token)

    def _http_post(self, url: str, headers: dict, json_body: dict):
        try:
            import httpx  # optional dep — lazy (spec §4.1)
        except ImportError as e:
            raise ConfigError(
                "httpx library not installed.",
                hint="pip install httpx  (or run /h2t-core:setup)",
            ) from e
        try:
            resp = httpx.post(url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise _map_http_status(e.response.status_code, str(e)) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Notion request failed: {e}") from e
```

2. Delete the old module-level blocks that imported `dotenv`, `notion_client`, `httpx`, the `load_dotenv(...)` call, and the old `_get_token` method (lines ~46–53). Token now comes from `resolve_notion_token()`.

3. Add this module-level helper just above `class NotionClient`:
```python
def _map_http_status(status: int, msg: str):
    if status in (401, 403):
        return AuthError(f"Notion auth/permission denied (HTTP {status}): {msg}")
    if status == 404:
        return NotFoundError(f"Notion resource not found (HTTP {status}): {msg}")
    if status >= 500:
        return ProviderError(f"Notion server error (HTTP {status}): {msg}")
    return ProviderError(f"Notion API error (HTTP {status}): {msg}")
```

4. In `query_database`, replace the `httpx.post(...)` + `response.raise_for_status()` + `response.json()` block with `data = self._http_post(url, headers, body)` and remove the now-unused `import httpx` references inside the method. Keep pagination/loop logic unchanged.

5. For every method that wraps `notion_client` SDK calls (`get_page`, `get_blocks`, `get_database`, `find_databases_on_page`, `create_page`, `update_page`, `append_blocks`, `delete_block`, `replace_page_content`), replace each:
```python
        except Exception as e:
            raise Exception(f"Failed to ...: {e}") from e
```
with this exact handler (preserve the original message text after `op=`):
```python
        except Exception as e:
            raise _map_sdk_exc(e, op="<original message, e.g. get page {page_id}>") from e
```
and add this module-level helper next to `_map_http_status`:
```python
def _map_sdk_exc(e: Exception, *, op: str):
    s = str(e).lower()
    if "unauthorized" in s or "restricted" in s or "permission" in s:
        return AuthError(f"Failed to {op}: {e}")
    if "object_not_found" in s or "could not find" in s:
        return NotFoundError(f"Failed to {op}: {e}")
    if "timeout" in s or "connection" in s or "network" in s:
        return NetworkError(f"Failed to {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")
```

6. Leave ALL pure converter methods byte-identical: `blocks_to_markdown`, `_block_to_markdown`, `_rich_text_to_markdown`, `parse_inline`, `markdown_to_blocks`, `_extract_property_value`, `database_items_to_markdown`. (They have no I/O and need no error change.)

- [ ] **Step 5: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion/test_client.py -v`
Expected: PASS (5).

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add h2t/connectors/notion/__init__.py h2t/connectors/notion/client.py tests/connectors/notion/test_client.py
git -C C:/dev/h2t-skills commit -m "feat(notion): re-wrapped client with typed errors"
```

---

### Task 8: connectors/notion/commands.py — argparse adapter (lazy client)

**Files:**
- Create: `h2t/connectors/notion/commands.py`
- Test: `tests/connectors/notion/test_commands.py`

- [ ] **Step 1: Write the failing test**

`tests/connectors/notion/test_commands.py`:
```python
import argparse
import sys
import builtins
import pytest
from h2t.connectors.notion.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_notion_subcommands():
    p = _parser()
    ns = p.parse_args(["notion", "get", "PAGEID"])
    assert ns.connector == "notion" and ns.notion_cmd == "get" and ns.page_id == "PAGEID"


def test_register_has_format_and_json_flags():
    p = _parser()
    ns = p.parse_args(["notion", "get", "PID", "--json"])
    assert ns.as_json is True
    ns2 = p.parse_args(["notion", "blocks", "PID", "--format", "md"])
    assert ns2.fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    # commands.py must have NO module-level client import (spec §4.1)
    sys.modules.pop("h2t.connectors.notion.client", None)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t.connectors.notion.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t.connectors.notion.commands"))
    assert seen["client"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion/test_commands.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.connectors.notion.commands`.

- [ ] **Step 3: Write minimal implementation**

`h2t/connectors/notion/commands.py` (NO module-level client import — spec §4.1):
```python
"""Notion CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

PROVIDER = "notion"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("notion", help="Work with Notion pages and databases")
    cmds = p.add_subparsers(dest="notion_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/table, human = concise (default)")

    g = cmds.add_parser("get", help="Get page (blocks as markdown by default)")
    g.add_argument("page_id"); add_fmt(g)

    b = cmds.add_parser("blocks", help="Get page blocks")
    b.add_argument("page_id"); b.add_argument("--limit", type=int); add_fmt(b)

    s = cmds.add_parser("search", help="Query a database")
    s.add_argument("database_id"); s.add_argument("--filter")
    s.add_argument("--filter-json"); s.add_argument("--limit", type=int); add_fmt(s)

    gd = cmds.add_parser("get-database", help="Database items")
    gd.add_argument("database_id"); gd.add_argument("--limit", type=int); add_fmt(gd)

    fd = cmds.add_parser("find-databases", help="Find databases on a page")
    fd.add_argument("page_id"); add_fmt(fd)

    c = cmds.add_parser("create", help="Create a page")
    c.add_argument("parent_id"); c.add_argument("title")
    c.add_argument("--content"); c.add_argument("--file")
    c.add_argument("--database", action="store_true"); add_fmt(c)

    u = cmds.add_parser("update", help="Update a page")
    u.add_argument("page_id"); u.add_argument("--title")
    u.add_argument("--append"); u.add_argument("--file")
    u.add_argument("--replace", action="store_true"); add_fmt(u)

    sy = cmds.add_parser("sync", help="Sync page to a markdown file")
    sy.add_argument("page_id"); sy.add_argument("output_file")
    sy.add_argument("--preserve-metadata", action="store_true"); add_fmt(sy)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a notion subcommand. Returns a result object or raises core.errors."""
    from h2t.connectors.notion.client import NotionClient  # lazy (spec §4.1)
    client = NotionClient()
    cmd = args.notion_cmd

    if cmd == "get":
        return client.blocks_to_markdown(client.get_blocks(args.page_id))
    if cmd == "blocks":
        blocks = client.get_blocks(args.page_id, limit=args.limit)
        return client.blocks_to_markdown(blocks) if _fmt(args) != "json" else blocks
    if cmd == "search":
        import json as _json
        fdict = None
        if args.filter_json:
            fdict = _json.loads(args.filter_json)
        elif args.filter and "=" in args.filter:
            k, _, v = args.filter.partition("=")
            fdict = {"property": k.strip(), "select": {"equals": v.strip()}}
        rows = client.query_database(args.database_id, filter_dict=fdict, limit=args.limit)
        if _fmt(args) == "json":
            return rows
        return client.database_items_to_markdown(rows, client.get_database(args.database_id))
    if cmd == "get-database":
        rows = client.query_database(args.database_id, limit=args.limit)
        if _fmt(args) == "json":
            return rows
        return client.database_items_to_markdown(rows, client.get_database(args.database_id))
    if cmd == "find-databases":
        return client.find_databases_on_page(args.page_id)
    if cmd == "create":
        content = Path(args.file).read_text(encoding="utf-8") if args.file else args.content
        return client.create_page(args.parent_id, args.title,
                                  content=content, is_database=args.database)
    if cmd == "update":
        out: dict = {}
        if args.title:
            out["title"] = client.update_page(args.page_id, title=args.title)
        if args.append or args.file:
            text = Path(args.file).read_text(encoding="utf-8") if args.file else args.append
            if args.replace:
                client.replace_page_content(args.page_id, text)
                out["content"] = "replaced"
            else:
                out["content"] = client.append_blocks(
                    args.page_id, client.markdown_to_blocks(text))
        return out
    if cmd == "sync":
        md = client.blocks_to_markdown(client.get_blocks(args.page_id))
        if args.preserve_metadata:
            pg = client.get_page(args.page_id)
            md = (f"---\nnotion_id: {args.page_id}\n"
                  f"created: {pg.get('created_time','')}\n"
                  f"modified: {pg.get('last_edited_time','')}\n---\n\n") + md
        out_path = Path(args.output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        return f"Synced to {out_path}"
    from h2t.core.errors import UsageError
    raise UsageError(f"unknown notion subcommand: {cmd}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion/test_commands.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add h2t/connectors/notion/commands.py tests/connectors/notion/test_commands.py
git -C C:/dev/h2t-skills commit -m "feat(notion): argparse adapter with lazy client import"
```

---

### Task 9: connectors/notion/__init__.py — CONNECTOR spec

**Files:**
- Modify: `h2t/connectors/notion/__init__.py`

- [ ] **Step 1: Replace the marker with the spec**

`h2t/connectors/notion/__init__.py`:
```python
"""Notion connector — registry entry."""
from h2t.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="notion",
    help="Work with Notion pages and databases",
    client="h2t.connectors.notion.client:NotionClient",  # lazy ref (spec §4.1)
    register=register,
)
```

- [ ] **Step 2: Run the full registry + notion suites**

Run:
```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_registry.py tests/connectors/notion -v
```
Expected: PASS — including `test_discover_finds_notion`, `test_discover_does_not_import_notion_sdk`, `test_resolve_client_lazy_returns_class`.

- [ ] **Step 3: Commit**

```
git -C C:/dev/h2t-skills add h2t/connectors/notion/__init__.py
git -C C:/dev/h2t-skills commit -m "feat(notion): register CONNECTOR spec (lazy client)"
```

---

### Task 10: h2t/cli.py — dispatcher + legacy delegation + ingest shim

**Files:**
- Modify: `h2t/cli.py` (replace the Task 1 stub)
- Test: extend `tests/connectors/notion/test_commands.py` with CLI-level cases

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/connectors/notion/test_commands.py`:
```python
from h2t.cli import build_parser, dispatch


def test_version_exits_zero(capsys):
    import pytest as _pt
    with _pt.raises(SystemExit) as ei:
        build_parser().parse_args(["--version"])
    assert ei.value.code == 0


def test_connectors_list_no_heavy_import(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError("connectors list must not import SDK")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    code = dispatch(["connectors"])
    assert code == 0
    assert "notion" in capsys.readouterr().out


def test_unknown_subcommand_exit_2(capsys):
    code = dispatch(["notion", "bogus"])
    assert code == 2 or code == 2  # argparse error path → SystemExit(2) handled


def test_ingest_notion_shim_warns_on_human(monkeypatch, capsys):
    called = {}
    monkeypatch.setattr("h2t.connectors.notion.commands.run",
                        lambda args: called.setdefault("ran", True) or "OK")
    code = dispatch(["ingest", "notion", "get", "PID"])
    err = capsys.readouterr().err
    assert called.get("ran") is True
    assert "deprecat" in err.lower()
    assert code == 0


def test_ingest_notion_shim_silent_on_json(monkeypatch, capsys):
    monkeypatch.setattr("h2t.connectors.notion.commands.run", lambda args: {"id": "x"})
    code = dispatch(["ingest", "notion", "get", "PID", "--json"])
    cap = capsys.readouterr()
    assert "deprecat" not in cap.err.lower()
    assert code == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion/test_commands.py -v -k "version or connectors_list or shim or unknown_subcommand"`
Expected: FAIL — `ImportError: cannot import name 'build_parser' from h2t.cli`.

- [ ] **Step 3: Replace cli.py with the full implementation**

`h2t/cli.py`:
```python
"""h2t CLI: registry-built parser, central error→exit, legacy delegation, ingest shim."""
from __future__ import annotations

import argparse
import sys
from typing import Any

import h2t
from h2t.core.errors import UsageError, exit_code_for
from h2t.core.output import emit
from h2t.core.registry import discover

_MIGRATED = {"notion"}  # connectors served by the new package


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h2t", description="h2t unified connector CLI")
    p.add_argument("--version", action="version", version=f"h2t {h2t.__version__}")
    sub = p.add_subparsers(dest="connector")
    sub.add_parser("connectors", help="List available connectors")
    for spec in discover():
        spec.register(sub)
    return p


def _legacy(argv: list[str]) -> int:
    """Delegate non-migrated commands to lib.cli.main unchanged (transitional)."""
    from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
    old = sys.argv
    sys.argv = ["h2t", *argv]
    try:
        legacy_main()  # calls sys.exit internally
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    finally:
        sys.argv = old


def _fmt_from(argv: list[str]) -> str:
    if "--json" in argv:
        return "json"
    if "--format" in argv:
        i = argv.index("--format")
        if i + 1 < len(argv):
            return argv[i + 1]
    return "human"


def dispatch(argv: list[str]) -> int:
    # ingest shim: `ingest notion …` → new connector, deprecation per spec §10
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "notion":
        rest = argv[2:]
        # legacy `--format json|markdown` → new surface
        norm: list[str] = []
        skip = False
        for j, a in enumerate(rest):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest) and rest[j + 1] in ("json", "markdown"):
                if rest[j + 1] == "json":
                    norm.append("--json")
                else:
                    norm += ["--format", "md"]
                skip = True
            else:
                norm.append(a)
        fmt = _fmt_from(norm)
        if fmt != "json":
            print("deprecated: `h2t ingest notion` → use `h2t notion` (spec §10)",
                  file=sys.stderr)
        return _run_connector(["notion", *norm])

    if argv and argv[0] in ("gather", "ingest"):
        return _legacy(argv)

    if argv and argv[0] == "connectors":
        for spec in discover():
            print(f"{spec.name:12} {spec.help}")
        return 0

    if argv and argv[0] in _MIGRATED:
        return _run_connector(argv)

    return _legacy(argv) if argv else (build_parser().print_help() or 0)


def _run_connector(argv: list[str]) -> int:
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as e:           # argparse usage error
        return int(e.code or 2)
    handler = getattr(ns, "_handler", None)
    if handler is None:
        return emit(argv[0], exc=UsageError("no subcommand"), fmt="human")
    fmt = "json" if getattr(ns, "as_json", False) else getattr(ns, "fmt", "human")
    provider = argv[0]
    try:
        result = handler(ns)
        return emit(provider, result=result, fmt=fmt)
    except BaseException as exc:       # noqa: BLE001 — central mapping point
        if isinstance(exc, SystemExit):
            raise
        return emit(provider, exc=exc, fmt=fmt)


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the CLI tests + full notion suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/notion tests/core -v`
Expected: PASS (all core + notion incl. version/connectors-list/shim cases).

- [ ] **Step 5: Manual smoke (no network) — version, list, lazy discovery**

Run:
```
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli --version
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli connectors
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli notion --help
```
Expected: prints `h2t 0.2.0`; lists `notion`; prints notion subcommand help. No `notion_client` import error (lazy).

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add h2t/cli.py tests/connectors/notion/test_commands.py
git -C C:/dev/h2t-skills commit -m "feat(h2t): cli dispatcher, legacy delegation, ingest-notion shim"
```

---

### Task 11: Notion SKILL.md → spec §8 conformance

**Files:**
- Modify: `plugins/h2t-ops/skills/notion/SKILL.md`

- [ ] **Step 1: Replace the whole file**

`plugins/h2t-ops/skills/notion/SKILL.md`:
```markdown
---
name: notion
description: "Reads and writes Notion pages and databases via the h2t CLI. Use for GTD tasks, creating pages, querying databases, syncing pages to markdown. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database', 'h2t:notion'"
compatibility: "Requires the `h2t` CLI (run /h2t-core:setup) and NOTION_API_TOKEN in ~/.dor/secrets.env or ~/.config/notion/token"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# Notion (h2t connector)

## Availability (cross-platform contract)

`h2t --version` exits 0 when installed (identical on PowerShell and POSIX — no shell idioms).
If it fails: run `/h2t-core:setup`. `h2t doctor` reports install path, version, and secrets presence.

## Secrets

`NOTION_API_TOKEN` resolved in order: env var → `~/.config/notion/token`.
Missing → exit 3 (`config`) with hint.

## Commands

| Command | Purpose |
|---|---|
| `h2t notion get <page-id>` | page blocks as markdown |
| `h2t notion blocks <page-id> [--limit N]` | raw/markdown blocks |
| `h2t notion search <database-id> [--filter "Status=Done"] [--filter-json '{...}'] [--limit N]` | query database |
| `h2t notion get-database <database-id> [--limit N]` | database items as markdown |
| `h2t notion find-databases <page-id>` | list databases on a page |
| `h2t notion create <parent-id> "Title" [--content "md" | --file f.md] [--database]` | create page |
| `h2t notion update <page-id> [--title T] [--append "md" | --file f.md] [--replace]` | update page |
| `h2t notion sync <page-id> <out.md> [--preserve-metadata]` | write page to a file |

Output flags (every command): `--json` (raw envelope), `--format md` (markdown/table),
default = concise human text.

## Examples

```bash
h2t notion get 1a2b3c4d --format md
h2t notion search 9f8e7d6c --filter "Status=In progress" --json
h2t notion create 1a2b3c4d "Sprint notes" --file notes.md
h2t notion sync 1a2b3c4d ./export/page.md --preserve-metadata
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | provider/runtime error |
| 2 | usage / bad args |
| 3 | config / secrets missing |
| 4 | auth / permission denied |
| 5 | not found / empty resource |
| 6 | network / timeout |

`--json` errors go to stderr as `{"ok":false,"provider":"notion","error":{...}}`; exit is non-zero.

## When to use / not use

- ✅ Read/write Notion pages, query databases, sync a page to markdown.
- ❌ Bulk export of an entire workspace — out of scope.
- ❌ Do NOT fall back to raw HTTP if a command fails — report the exit code/error.

## Deprecated

`h2t ingest notion …` still works (forwards here) but prints a deprecation notice on
human output. Migrate call sites to `h2t notion …`.
```

- [ ] **Step 2: Lint the SKILL.md frontmatter loads**

Run: `C:/dev/h2t-skills/.venv/Scripts/python -c "import pathlib,sys; t=pathlib.Path('plugins/h2t-ops/skills/notion/SKILL.md').read_text(encoding='utf-8'); assert t.startswith('---') and 'h2t notion get' in t; print('SKILL.md ok')"`
Expected: prints `SKILL.md ok`.

- [ ] **Step 3: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/notion/SKILL.md
git -C C:/dev/h2t-skills commit -m "docs(notion): SKILL.md to spec §8 contract (h2t notion)"
```

---

### Task 12: DoD verification (spec §12)

**Files:** none (verification only)

- [ ] **Step 1: Run the full ТЗ-0 test suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core tests/connectors -v`
Expected: ALL PASS.

- [ ] **Step 2: Walk the DoD checklist with exact commands**

```
# 1. h2t --version exits 0
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli --version ; echo "exit=$?"
# 2. h2t notion --help works
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli notion --help
# 3. library import works
C:/dev/h2t-skills/.venv/Scripts/python -c "from h2t.connectors.notion.client import NotionClient; print('import ok')"
# 4. no sys.path.insert in the new package
git -C C:/dev/h2t-skills grep -n "sys.path.insert" -- "h2t/**" ; echo "expect: no matches"
# 5. registry build performs zero heavy imports
C:/dev/h2t-skills/.venv/Scripts/pytest tests/core/test_registry.py::test_discover_does_not_import_notion_sdk -q
# 6. legacy gather still works (transition non-regression)
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli gather session-start --cwd C:/dev/h2t-skills >NUL ; echo "gather exit=$?"
# 7. ingest notion shim still works
C:/dev/h2t-skills/.venv/Scripts/python -m h2t.cli ingest notion --help
```
Expected: 1 → `exit=0`; 2 → help text; 3 → `import ok`; 4 → no matches; 5 → PASS; 6 → `gather exit=0`; 7 → help text.

- [ ] **Step 3: Final commit + summary**

```
git -C C:/dev/h2t-skills add -A docs/superpowers/plans/2026-05-18-h2t-connector-architecture-tz0.md
git -C C:/dev/h2t-skills commit -m "chore(h2t): ТЗ-0 walking skeleton complete — DoD verified"
```

---

## Self-Review

**Spec coverage (spec §11 In-ТЗ-0 → task):**
- `h2t/` package + pyproject `h2t.cli:main` + no new `sys.path.insert` → Task 1, verified Task 12 step 2.4
- `core/registry|errors|envelope|output|secrets` → Tasks 5,2,3,4,6
- Notion connector walking skeleton → Tasks 7,8,9
- Backward-compatible `ingest notion` route → Task 10 (shim, spec §10 policy)
- Tests `tests/core/` + `tests/connectors/notion/` → every task TDD; aggregate Task 12
- Notion SKILL.md §8 → Task 11
- Lazy-discovery "zero heavy imports" → Task 5 test + Task 10 test + Task 12 step 2.5
- Transition non-regression (`gather`) → Task 10 `_legacy` + Task 12 step 2.6
- §14 decisions (install source / shim / secrets-minimal / optional-dep imports) → Locked Design Decisions block

**Placeholder scan:** no TBD/TODO; every code step shows full content; the Task 7 re-wrap uses exact copy-then-edit instructions against a named real file with each edit shown verbatim.

**Type consistency:** `ConnectorSpec(name,help,client,register)` consistent Tasks 5/9; `emit(provider,*,result,exc,fmt)` consistent Tasks 4/10; `discover()`/`resolve_client()` consistent Tasks 5/10; error `kind` strings ↔ `EXIT_CODES` keys ↔ envelope `error.type` consistent Tasks 2/3/4; `run(args)` handler + `_handler` default consistent Tasks 8/10.

Out-of-scope confirmed deferred: gmail/calendar/drive/meetgeek/telegram (ТЗ-1), research/fetch + `core/http.py` + legacy exit-code remap + rich envelope (ТЗ-2).
