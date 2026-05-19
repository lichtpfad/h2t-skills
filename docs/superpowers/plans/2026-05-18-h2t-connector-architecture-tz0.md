# ТЗ-0 H2T Connector Architecture — Core Foundation + Notion Walking Skeleton — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `h2t` import package + `core/` foundation + a fully-migrated Notion connector (walking skeleton) proving the connector standard from `docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md`.

**Architecture:** Monolithic `h2t` package, lazily auto-registered connectors. `client.py` = API logic (typed errors, no I/O side effects); `commands.py` = thin argparse adapter (lazy client import); `core/` = registry, errors, envelope, output, secrets. New entrypoint `h2t.cli:main` delegates non-migrated commands to legacy `lib.cli.main:main` unchanged.

**Tech Stack:** Python 3.11, stdlib `argparse`/`importlib`, `pytest`, `notion-client`, `httpx`, `uv` (toolchain).

---

## Execution Contract (read before any task)

**All implementation-plan commands use exactly one prefix:** `uv run h2t dev <tool|check> ...`

- ✅ `uv run h2t dev pytest tests/core -v`
- ✅ `uv run h2t dev python -c "import h2t; print(h2t.__version__)"`
- ✅ `uv run h2t dev check no-syspath`
- ✅ availability/health: `uv run h2t --version`, `uv run h2t doctor`, `uv run h2t notion --help`
- ❌ NO direct `.venv/Scripts/python` / `.venv/bin/python` / `$PY` / `$PIP` / `$PYTEST`
- ❌ NO `command -v`, `$(...)`, `>NUL`, `echo $?`, or shell-specific redirection
- ❌ NO `uv run h2t dev pip install -e .` — the project is auto-provisioned by `uv run`; `h2t dev pip` exists for ad-hoc deps only, never to install **this** project

`uv run` provisions the project (incl. `[project.dependencies]` **and the `dev` dependency-group → `pytest`**) into its managed env on first call — that is the single, documented bootstrap seam. No editable install in the TDD loop.

**Prereq:** `uv` on PATH (installed by `/h2t-core:setup`: `pip install uv`).

---

## Locked Design Decisions (resolve spec §14 + transition gap)

1. **Install source (dev/CI):** `uv run` auto-provisions from `pyproject`. No explicit editable install in the loop. External sharing (git-ref / PyPI / `uv tool install`) is a **separate rollout decision**, NOT in ТЗ-0.
2. **Transition compatibility (spec gap, decided here):** flipping `[project.scripts]` to `h2t.cli:main` must not regress `h2t gather` or `h2t ingest gmail/calendar`. `h2t/cli.py` recognizes migrated commands (`dev`, `doctor`, `connectors`, `notion`, `--version`) and **delegates everything else** to legacy `lib.cli.main:main`. `lib/` is NOT modified in ТЗ-0; its pre-existing `sys.path.insert` is knowingly retained until its commands migrate (ТЗ-1/ТЗ-2). The "no `sys.path.insert`" DoD applies to the **new `h2t` package**, which adds none.
3. **`ingest notion` shim:** `h2t ingest notion …` forwards to the **new** notion connector with a small explicit legacy-arg mapping (Task 9). Deprecation notice → stderr on human/`md`, silent on `--json`, forwarded exit code, stateless (spec §10).
4. **Notion deps are DECLARED project deps** (spec §4.1 general rule unchanged; the spec is NOT edited). `pyproject` `[project.dependencies]` gains `notion-client`, `httpx`, `python-dotenv` → `uv run` gives a working Notion out of the box. `client.py` STILL imports the SDK lazily and converts a missing import to `ConfigError` — defensive depth for a broken env (lazy is always §4.1-compliant, even for declared deps). **Note:** the re-wrapped client uses stdlib `h2t.core.secrets`; `python-dotenv` is unused by the ТЗ-0 Notion path — declared for forward-compat / other notion tooling only. Future heavy connector deps may become optional extras.
5. **Three distinct surfaces (spec §7):** `h2t --version` = availability contract; `h2t doctor` = installed CLI health (version, path, connectors, secrets presence — no network), for users/skills; `h2t dev …` = repo-local execution wrapper for agents/plans/tests.

---

## File Structure

**Create:**
- `h2t/__init__.py` — package marker, `__version__`
- `h2t/dev.py` — `h2t dev` wrapper: `python|pip|pytest` + named `check`s
- `h2t/cli.py` — entrypoint: dev/version routing + (Task 9) connector dispatch, legacy delegation, ingest shim, doctor
- `h2t/core/__init__.py`
- `h2t/core/errors.py`, `h2t/core/envelope.py`, `h2t/core/output.py`, `h2t/core/registry.py`, `h2t/core/secrets.py`
- `h2t/connectors/__init__.py`
- `h2t/connectors/notion/__init__.py`, `h2t/connectors/notion/client.py`, `h2t/connectors/notion/commands.py`
- `.h2t/agent-runtime.json`
- `tests/core/test_errors.py`, `test_envelope.py`, `test_output.py`, `test_registry.py`, `test_secrets.py`
- `tests/connectors/notion/test_client.py`, `test_commands.py`

**Modify:**
- `pyproject.toml` — entrypoint, packages, Notion deps, version
- `plugins/h2t-ops/skills/notion/SKILL.md` — spec §8 conformance

---

### Task 0: Bootstrap skeleton + dev wrapper + agent-runtime config

**Files:**
- Create: `h2t/__init__.py`, `h2t/core/__init__.py`, `h2t/connectors/__init__.py`, `h2t/dev.py`, `h2t/cli.py`, `.h2t/agent-runtime.json`
- Modify: `pyproject.toml`

- [ ] **Step 1: Package markers**

`h2t/__init__.py`:
```python
"""h2t — unified connector CLI + library. Spec: docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md"""
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

- [ ] **Step 2: Agent runtime config**

`.h2t/agent-runtime.json`:
```json
{
  "schema": 1,
  "repo": ".",
  "platform": "auto"
}
```

- [ ] **Step 3: dev wrapper**

`h2t/dev.py`:
```python
"""h2t dev — repo-local execution wrapper for agents/plans/tests.

Resolves the running interpreter (uv-managed under `uv run`) so plans never
hardcode a python path or shell idiom.
  dev python <args...>   -> [py, <args...>]
  dev pip <args...>      -> [py, -m pip, <args...>]   (NOT for installing this project)
  dev pytest <args...>   -> [py, -m pytest, <args...>]
  dev check <name>       -> named verification (no shell, cross-platform)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parent.parent / ".h2t" / "agent-runtime.json"


def _repo_root() -> Path:
    base = _RUNTIME.parent.parent
    try:
        cfg = json.loads(_RUNTIME.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    repo = cfg.get("repo", ".")
    return base.resolve() if repo == "." else Path(repo).resolve()


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=_repo_root()).returncode


def _check(name: str) -> int:
    root = _repo_root()
    if name == "no-syspath":
        import re
        pat = re.compile(r"sys\.path\.insert\s*\(")  # call syntax, not bare needle
        hits = [str(p) for p in (root / "h2t").rglob("*.py")
                if pat.search(p.read_text(encoding="utf-8"))]
        if hits:
            print("FAIL no-syspath: " + ", ".join(hits), file=sys.stderr)
            return 1
        print("OK no-syspath")
        return 0
    if name == "lazy-registry":
        import builtins
        real = builtins.__import__

        def guard(n, *a, **k):
            if n in ("notion_client", "httpx"):
                raise AssertionError(f"registry imported {n}")
            return real(n, *a, **k)

        builtins.__import__ = guard
        try:
            from h2t.core.registry import discover
            names = {s.name for s in discover()}
        except ImportError as e:
            print(f"FAIL lazy-registry (not yet installed: {e})", file=sys.stderr)
            return 1
        finally:
            builtins.__import__ = real
        ok = "notion" in names
        print(("OK" if ok else "FAIL") + " lazy-registry")
        return 0 if ok else 1
    if name == "gather-smoke":
        code = subprocess.run(
            [sys.executable, "-m", "h2t.cli", "gather", "session-start", "--cwd", str(root)],
            cwd=root, stdout=subprocess.DEVNULL).returncode
        print(("OK" if code == 0 else "FAIL") + f" gather-smoke (exit={code})")
        return 0 if code == 0 else 1
    if name == "skill-md-notion":
        f = root / "plugins" / "h2t-ops" / "skills" / "notion" / "SKILL.md"
        t = f.read_text(encoding="utf-8")
        ok = t.startswith("---") and "h2t notion get" in t
        print(("OK" if ok else "FAIL") + " skill-md-notion")
        return 0 if ok else 1
    print(f"unknown check: {name}", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: h2t dev {python|pip|pytest|check} ...", file=sys.stderr)
        return 2
    tool, rest, py = argv[0], argv[1:], sys.executable
    if tool == "python":
        return _run([py, *rest])
    if tool == "pip":
        return _run([py, "-m", "pip", *rest])
    if tool == "pytest":
        return _run([py, "-m", "pytest", *rest])
    if tool == "check":
        if not rest:
            print("usage: h2t dev check <name>", file=sys.stderr)
            return 2
        return _check(rest[0])
    print(f"unknown dev tool: {tool}", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Minimal cli.py (dev + version + legacy delegation; expanded in Task 9)**

`h2t/cli.py`:
```python
"""h2t CLI entrypoint. dev/version here; connector dispatch + doctor added in Task 9."""
from __future__ import annotations

import sys

import h2t
from h2t.dev import main as _dev_main


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "dev":
        return _dev_main(argv[1:])
    if argv and argv[0] in ("--version", "-V"):
        print(f"h2t {h2t.__version__}")
        return 0
    from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
    old = sys.argv
    sys.argv = ["h2t", *argv]
    try:
        legacy_main()
        return 0
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    finally:
        sys.argv = old


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: pyproject — entrypoint, packages, Notion deps, version**

In `pyproject.toml` set `[project]` `version = "0.2.0"`, replace `dependencies = []` with:
```toml
dependencies = [
  "notion-client>=2.0",
  "httpx>=0.27",
  "python-dotenv>=1.0",
]
```
replace `[project.scripts]` `h2t = "lib.cli.main:main"` with `h2t = "h2t.cli:main"`, and `[tool.setuptools.packages.find]` `include = ["lib*"]` with `include = ["h2t*", "lib*"]`.

Then add a **new top-level table** so `uv run` provisions pytest (uv installs the `dev` dependency-group by default):
```toml
[dependency-groups]
dev = [
  "pytest>=8",
]
```

- [ ] **Step 6: Provision + verify (first `uv run` = bootstrap seam)**

Run: `uv run h2t --version`
Expected: uv provisions the env (one-time), then prints `h2t 0.2.0`, exit 0.

Run: `uv run h2t dev python -c "import h2t, h2t.core, h2t.connectors; print(h2t.__version__)"`
Expected: prints `0.2.0`.

- [ ] **Step 7: Commit**

```
git add h2t/ .h2t/agent-runtime.json pyproject.toml
git commit -m "feat(h2t): bootstrap skeleton + dev wrapper + agent-runtime config"
```

---

### Task 1: core/errors.py — typed exceptions + exit-code map

**Files:** Create `h2t/core/errors.py`; Test `tests/core/test_errors.py`

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


def test_all_subclass_kinds_are_in_exit_codes():
    for cls in (UsageError, ConfigError, AuthError, ProviderError, NotFoundError, NetworkError):
        assert cls.kind in EXIT_CODES, f"{cls.__name__}.kind={cls.kind!r} missing from EXIT_CODES"


def test_hint_stored_and_defaults_none():
    e = UsageError("bad arg", hint="run h2t --help")
    assert e.hint == "run h2t --help"
    assert str(e) == "bad arg"
    assert UsageError("x").hint is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/core/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.errors`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/errors.py`:
```python
"""Typed error hierarchy + exit-code mapping (spec §5)."""
from __future__ import annotations


class H2TError(Exception):
    """Base. Carries an optional install/fix hint.
    Always raise a typed subclass; do not raise H2TError directly."""
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
        return EXIT_CODES.get(exc.kind, EXIT_CODES["provider"])
    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/core/test_errors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add h2t/core/errors.py tests/core/test_errors.py
git commit -m "feat(h2t-core): typed errors + exit-code map"
```

---

### Task 2: core/envelope.py — universal result/error shape

**Files:** Create `h2t/core/envelope.py`; Test `tests/core/test_envelope.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_envelope.py`:
```python
from h2t.core.envelope import success_envelope, error_envelope
from h2t.core.errors import AuthError


def test_success_shape():
    assert success_envelope("notion", {"id": "abc"}) == {
        "ok": True, "provider": "notion", "result": {"id": "abc"}}


def test_error_shape_with_hint():
    env = error_envelope("notion", AuthError("denied", hint="Set NOTION_API_TOKEN"))
    assert env == {"ok": False, "provider": "notion",
                   "error": {"type": "auth", "message": "denied",
                             "hint": "Set NOTION_API_TOKEN"}}


def test_error_shape_unknown_exception_is_provider():
    env = error_envelope("notion", ValueError("boom"))
    assert env["error"]["type"] == "provider" and env["error"]["hint"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/core/test_envelope.py -v`
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
    return {"ok": False, "provider": provider,
            "error": {"type": kind, "message": str(exc), "hint": hint}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/core/test_envelope.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add h2t/core/envelope.py tests/core/test_envelope.py
git commit -m "feat(h2t-core): universal result/error envelope"
```

---

### Task 3: core/output.py — json / md / human emitter

**Files:** Create `h2t/core/output.py`; Test `tests/core/test_output.py`

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


def test_emit_json_error_to_stderr_nonzero(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="json")
    out = capsys.readouterr()
    assert code == 4
    payload = json.loads(out.err)
    assert payload["ok"] is False and payload["error"]["type"] == "auth"
    assert out.out == ""


def test_emit_md_passthrough_string(capsys):
    code = emit("notion", result="# Title\n", fmt="md")
    out = capsys.readouterr()
    assert code == 0 and "# Title" in out.out


def test_emit_human_error_writes_stderr(capsys):
    code = emit("notion", exc=AuthError("denied", hint="Set NOTION_API_TOKEN"), fmt="human")
    out = capsys.readouterr()
    assert code == 4 and "denied" in out.err and "Set NOTION_API_TOKEN" in out.err
    assert out.out == ""


def test_emit_human_dict_result(capsys):
    code = emit("notion", result={"key": "val"}, fmt="human")
    out = capsys.readouterr()
    assert code == 0
    assert json.loads(out.out) == {"key": "val"}


def test_emit_human_error_no_hint(capsys):
    code = emit("notion", exc=AuthError("denied"), fmt="human")
    out = capsys.readouterr()
    assert code == 4
    assert "denied" in out.err and "hint:" not in out.err
    assert out.out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/core/test_output.py -v`
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
    """Render to stdout (success) or stderr (error). Return exit code."""
    if exc is not None:
        code = exit_code_for(exc)
        env_dict = error_envelope(provider, exc)
        if fmt == "json":
            print(json.dumps(env_dict, ensure_ascii=False), file=sys.stderr)
        else:
            env = env_dict["error"]
            line = f"error[{env['type']}]: {env['message']}"
            if env["hint"]:
                line += f"\nhint: {env['hint']}"
            print(line, file=sys.stderr)
        return code
    if fmt == "json":
        print(json.dumps(success_envelope(provider, result), ensure_ascii=False))
    elif fmt == "md":
        # NOTE: md and human are identical for now; they diverge in Task 9
        # (md → markdown tables, human → concise). Keep branches separate.
        print(result if isinstance(result, str)
              else json.dumps(result, ensure_ascii=False, indent=2))
    else:  # human
        print(result if isinstance(result, str)
              else json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/core/test_output.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add h2t/core/output.py tests/core/test_output.py
git commit -m "feat(h2t-core): output emitter (json/md/human)"
```

---

### Task 4: core/registry.py — ConnectorSpec + lazy discovery

**Files:** Create `h2t/core/registry.py`; Test `tests/core/test_registry.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_registry.py`:
```python
import sys
import builtins
from h2t.core.registry import ConnectorSpec, discover, resolve_client


def test_connectorspec_fields():
    spec = ConnectorSpec(name="x", help="h", client="pkg.mod:Cls", register=lambda s: None)
    assert spec.name == "x" and spec.client == "pkg.mod:Cls"


def test_discover_finds_notion():
    specs = {s.name: s for s in discover()}
    assert "notion" in specs
    assert specs["notion"].client == "h2t.connectors.notion.client:NotionClient"


def test_discover_does_not_import_notion_sdk(monkeypatch):
    real_import = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError(f"discovery must not import {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    sys.modules.pop("h2t.connectors.notion.client", None)
    assert "notion" in {s.name for s in discover()}


def test_resolve_client_lazy_returns_class():
    spec = next(s for s in discover() if s.name == "notion")
    assert resolve_client(spec).__name__ == "NotionClient"


def test_discover_skips_broken_connector(tmp_path, monkeypatch):
    import h2t.connectors as _pkg
    pkgdir = tmp_path / "broken_conn"
    pkgdir.mkdir()
    (pkgdir / "__init__.py").write_text("raise ImportError('missing dep')\n", encoding="utf-8")
    monkeypatch.setattr(_pkg, "__path__", list(_pkg.__path__) + [str(tmp_path)])
    names = {s.name for s in discover()}          # must NOT raise
    assert "broken_conn" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/core/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.core.registry`.

- [ ] **Step 3: Write minimal implementation**

`h2t/core/registry.py`:
```python
"""Connector registry: explicit ConnectorSpec, lazy discovery (spec §4)."""
from __future__ import annotations

import importlib
import pkgutil
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import h2t.connectors as _connectors_pkg


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    help: str
    client: str                      # lazy "module:attr" — resolved on demand only
    register: Callable[[Any], None]


def discover() -> Iterator[ConnectorSpec]:
    """Yield CONNECTOR from each h2t.connectors.<name> subpackage (cheap import).

    A connector whose __init__ raises is skipped with a stderr warning rather
    than killing discovery for every connector (plug-in registry convention).
    """
    for mod in pkgutil.iter_modules(_connectors_pkg.__path__):
        if not mod.ispkg:
            continue
        try:
            sub = importlib.import_module(f"h2t.connectors.{mod.name}")
        except Exception as e:  # noqa: BLE001 — one bad connector must not kill the registry
            print(f"h2t: warning: skipped connector {mod.name!r}: {e}", file=sys.stderr)
            continue
        spec = getattr(sub, "CONNECTOR", None)
        if isinstance(spec, ConnectorSpec):
            yield spec


def resolve_client(spec: ConnectorSpec) -> type:
    """Import and return the client class — only when actually needed."""
    module_path, sep, attr = spec.client.partition(":")
    if not sep or not attr:
        raise ValueError(f"malformed connector client spec: {spec.client!r} (expected 'module:attr')")
    return getattr(importlib.import_module(module_path), attr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/core/test_registry.py::test_connectorspec_fields -v`
Expected: PASS. (Remaining registry tests pass after Task 8 — re-run there.)

- [ ] **Step 5: Commit**

```
git add h2t/core/registry.py tests/core/test_registry.py
git commit -m "feat(h2t-core): ConnectorSpec + lazy discovery"
```

---

### Task 5: core/secrets.py — minimal secrets + Notion token

**Files:** Create `h2t/core/secrets.py`; Test `tests/core/test_secrets.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_secrets.py`:
```python
import os
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
    assert os.environ["FOO"] == "shell" and os.environ["BAR"] == "baz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/core/test_secrets.py -v`
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

Run: `uv run h2t dev pytest tests/core/test_secrets.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add h2t/core/secrets.py tests/core/test_secrets.py
git commit -m "feat(h2t-core): minimal secrets + notion token resolution"
```

---

### Task 6: connectors/notion/client.py — re-wrap with typed errors

**Files:** Create `h2t/connectors/notion/__init__.py` (marker), `h2t/connectors/notion/client.py`; Test `tests/connectors/notion/test_client.py`

Mechanical re-wrap of `lib/clients/notion.py` (spec §10 rule 1): same API logic, only side-effects and error types change.

- [ ] **Step 1: Subpackage marker**

`h2t/connectors/notion/__init__.py`:
```python
"""Notion connector. CONNECTOR + register added in Task 8."""
```

- [ ] **Step 2: Write the failing test**

`tests/connectors/notion/test_client.py`:
```python
import pytest
from h2t.connectors.notion.client import NotionClient
from h2t.core.errors import ConfigError


@pytest.fixture
def conv():
    c = object.__new__(NotionClient)  # bypass __init__ (no token / no SDK)
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
    import pathlib
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr("h2t.core.secrets.Path.home",
                        lambda: pathlib.Path("/nonexistent-xyz"))
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


from h2t.connectors.notion.client import _map_http_status, _map_sdk_exc
from h2t.core.errors import AuthError, NetworkError, NotFoundError, ProviderError


@pytest.mark.parametrize("status,expected", [
    (401, AuthError), (403, AuthError), (404, NotFoundError),
    (500, ProviderError), (503, ProviderError), (400, ProviderError),
])
def test_map_http_status(status, expected):
    assert isinstance(_map_http_status(status, "err"), expected)


@pytest.mark.parametrize("msg,expected", [
    ("insufficient permission to access", AuthError),
    ("could not find page with id", NotFoundError),
    ("connection refused", NetworkError),
    ("request to notion api has timed out", NetworkError),
    ("some other api error", ProviderError),
])
def test_map_sdk_exc_substring(msg, expected):
    assert isinstance(_map_sdk_exc(Exception(msg), op="op"), expected)


def test_map_sdk_exc_passthrough_typed():
    e = NotFoundError("already typed")
    assert _map_sdk_exc(e, op="op") is e


class _FakeAPIErr(Exception):
    def __init__(self, code, status):
        super().__init__("opaque message")
        self.code = code
        self.status = status


@pytest.mark.parametrize("code,status,expected", [
    ("unauthorized", 401, AuthError),
    ("restricted_resource", 403, AuthError),
    ("object_not_found", 404, NotFoundError),
    ("rate_limited", 429, ProviderError),
])
def test_map_sdk_exc_structured_code(code, status, expected):
    assert isinstance(_map_sdk_exc(_FakeAPIErr(code, status), op="op"), expected)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/connectors/notion/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.connectors.notion.client`.

- [ ] **Step 4: Create client.py from the legacy file with these exact transforms**

Copy `lib/clients/notion.py` → `h2t/connectors/notion/client.py`, then apply EXACTLY:

1. Replace lines 1–44 (docstring through `self.client = Client(auth=self.token)`) with:
```python
"""NotionClient — bidirectional Notion adapter (re-wrapped, typed errors).

API logic is identical to lib/clients/notion.py; only side effects and error
types changed per spec §10 (re-wrap not rewrite).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from h2t.core.errors import (
    AuthError, ConfigError, H2TError, NetworkError, NotFoundError, ProviderError,
)
from h2t.core.secrets import resolve_notion_token


def _map_http_status(status: int, msg: str):
    if status in (401, 403):
        return AuthError(f"Notion auth/permission denied (HTTP {status}): {msg}")
    if status == 404:
        return NotFoundError(f"Notion resource not found (HTTP {status}): {msg}")
    if status >= 500:
        return ProviderError(f"Notion server error (HTTP {status}): {msg}")
    return ProviderError(f"Notion API error (HTTP {status}): {msg}")


def _map_sdk_exc(e: Exception, *, op: str):
    if isinstance(e, H2TError):
        return e  # already typed (e.g. from _http_post / get_blocks) — don't re-classify
    code = getattr(e, "code", None)
    if hasattr(code, "value"):           # notion_client APIErrorCode enum → str
        code = code.value
    status = getattr(e, "status", 0)
    if code in ("unauthorized", "restricted_resource") or status in (401, 403):
        return AuthError(f"Failed to {op}: {e}")
    if code == "object_not_found" or status == 404:
        return NotFoundError(f"Failed to {op}: {e}")
    s = str(e).lower()
    if "unauthorized" in s or "restricted" in s or "permission" in s:
        return AuthError(f"Failed to {op}: {e}")
    if "could not find" in s:
        return NotFoundError(f"Failed to {op}: {e}")
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(f"Failed to {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")


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

2. Delete the now-removed old `_get_token` method (legacy lines ~46–53).

3. In `query_database`, replace the `httpx.post(...)` + `response.raise_for_status()` + `data = response.json()` block with `data = self._http_post(url, headers, body)`. Keep the pagination loop unchanged.

4. For every SDK-wrapping method (`get_page`, `get_blocks`, `get_database`, `find_databases_on_page`, `create_page`, `update_page`, `append_blocks`, `delete_block`, `replace_page_content`, and the outer `query_database` try), replace each:
```python
        except Exception as e:
            raise Exception(f"Failed to ...: {e}") from e
```
with (preserve the original message after `op=`):
```python
        except Exception as e:
            raise _map_sdk_exc(e, op="<original message, e.g. get page {page_id}>") from e
```

5. Leave ALL pure converters byte-identical: `blocks_to_markdown`, `_block_to_markdown`, `_rich_text_to_markdown`, `parse_inline`, `markdown_to_blocks`, `_extract_property_value`, `database_items_to_markdown`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/connectors/notion/test_client.py -v`
Expected: PASS (5).

- [ ] **Step 6: Commit**

```
git add h2t/connectors/notion/__init__.py h2t/connectors/notion/client.py tests/connectors/notion/test_client.py
git commit -m "feat(notion): re-wrapped client with typed errors"
```

---

### Task 7: connectors/notion/commands.py — argparse adapter (lazy client)

**Files:** Create `h2t/connectors/notion/commands.py`; Test `tests/connectors/notion/test_commands.py`

- [ ] **Step 1: Write the failing test**

`tests/connectors/notion/test_commands.py`:
```python
import argparse
import sys
import builtins
from h2t.connectors.notion.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_notion_subcommands():
    ns = _parser().parse_args(["notion", "get", "PAGEID"])
    assert ns.connector == "notion" and ns.notion_cmd == "get" and ns.page_id == "PAGEID"


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["notion", "get", "PID", "--json"]).as_json is True
    assert p.parse_args(["notion", "blocks", "PID", "--format", "md"]).fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
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


import types
import pytest
from h2t.connectors.notion import commands as notion_cmds
from h2t.core.errors import UsageError


class _FakeClient:
    def get_blocks(self, page_id, limit=None): return [{"type": "paragraph", "id": "b1"}]
    def blocks_to_markdown(self, blocks): return "MD"
    def update_page(self, *a, **k): return {"id": "p"}


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def test_get_json_returns_raw_blocks(monkeypatch):
    monkeypatch.setattr("h2t.connectors.notion.client.NotionClient", lambda *a, **k: _FakeClient())
    out = notion_cmds.run(_ns(notion_cmd="get", page_id="P", as_json=True, fmt="human"))
    assert out == [{"type": "paragraph", "id": "b1"}]


def test_get_human_returns_markdown(monkeypatch):
    monkeypatch.setattr("h2t.connectors.notion.client.NotionClient", lambda *a, **k: _FakeClient())
    out = notion_cmds.run(_ns(notion_cmd="get", page_id="P", as_json=False, fmt="human"))
    assert out == "MD"


def test_update_noop_raises_usageerror(monkeypatch):
    monkeypatch.setattr("h2t.connectors.notion.client.NotionClient", lambda *a, **k: _FakeClient())
    with pytest.raises(UsageError):
        notion_cmds.run(_ns(notion_cmd="update", page_id="P", title=None,
                            append=None, file=None, replace=False))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run h2t dev pytest tests/connectors/notion/test_commands.py -v`
Expected: FAIL — `ModuleNotFoundError: h2t.connectors.notion.commands`.

- [ ] **Step 3: Write minimal implementation**

`h2t/connectors/notion/commands.py` (NO module-level client import — spec §4.1):
```python
"""Notion CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

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

    g = cmds.add_parser("get", help="Get page blocks as markdown")
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
    """Dispatch a notion subcommand. Returns a result or raises core.errors."""
    from h2t.connectors.notion.client import NotionClient  # lazy (spec §4.1)
    from h2t.core.errors import UsageError

    def _read_file(path):
        from pathlib import Path as _P
        try:
            return _P(path).read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise UsageError(f"file not found: {path}") from e

    client = NotionClient()
    cmd = args.notion_cmd
    if cmd == "get":
        blocks = client.get_blocks(args.page_id)
        return blocks if _fmt(args) == "json" else client.blocks_to_markdown(blocks)
    if cmd == "blocks":
        blocks = client.get_blocks(args.page_id, limit=args.limit)
        return blocks if _fmt(args) == "json" else client.blocks_to_markdown(blocks)
    if cmd == "search":
        import json as _json
        fdict = None
        if args.filter_json:
            fdict = _json.loads(args.filter_json)
        elif args.filter and "=" in args.filter:
            k, _, v = args.filter.partition("=")
            fdict = {"property": k.strip(), "select": {"equals": v.strip()}}
        rows = client.query_database(args.database_id, filter_dict=fdict, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
    if cmd == "get-database":
        rows = client.query_database(args.database_id, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
    if cmd == "find-databases":
        return client.find_databases_on_page(args.page_id)
    if cmd == "create":
        content = _read_file(args.file) if args.file else args.content
        return client.create_page(args.parent_id, args.title,
                                  content=content, is_database=args.database)
    if cmd == "update":
        out: dict = {}
        if args.title:
            out["title"] = client.update_page(args.page_id, title=args.title)
        if args.append or args.file:
            text = _read_file(args.file) if args.file else args.append
            if args.replace:
                client.replace_page_content(args.page_id, text)
                out["content"] = "replaced"
            else:
                out["content"] = client.append_blocks(
                    args.page_id, client.markdown_to_blocks(text))
        if not out:
            raise UsageError("update: specify --title, --append, or --file")
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
    raise UsageError(f"unknown notion subcommand: {cmd}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run h2t dev pytest tests/connectors/notion/test_commands.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```
git add h2t/connectors/notion/commands.py tests/connectors/notion/test_commands.py
git commit -m "feat(notion): argparse adapter with lazy client import"
```

---

### Task 8: connectors/notion/__init__.py — CONNECTOR spec

**Files:** Modify `h2t/connectors/notion/__init__.py`

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

- [ ] **Step 2: Run registry + notion suites**

Run: `uv run h2t dev pytest tests/core/test_registry.py tests/connectors/notion -v`
Expected: PASS — incl. `test_discover_finds_notion`, `test_discover_does_not_import_notion_sdk`, `test_resolve_client_lazy_returns_class`.

- [ ] **Step 3: Commit**

```
git add h2t/connectors/notion/__init__.py
git commit -m "feat(notion): register CONNECTOR spec (lazy client)"
```

---

### Task 9: h2t/cli.py — dispatcher + legacy delegation + ingest shim + doctor

**Files:** Modify `h2t/cli.py` (replace Task 0 minimal version); extend `tests/connectors/notion/test_commands.py`

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/connectors/notion/test_commands.py`:
```python
from h2t.cli import build_parser, dispatch


def test_version_branch_exits_zero(capsys):
    assert dispatch(["--version"]) == 0
    assert "h2t " in capsys.readouterr().out


def test_connectors_list_no_heavy_import(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError("connectors list must not import SDK")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert dispatch(["connectors"]) == 0
    assert "notion" in capsys.readouterr().out


def test_doctor_reports_connectors(capsys):
    assert dispatch(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "notion" in out and "secrets" in out


def test_ingest_notion_shim_warns_on_human(monkeypatch, capsys):
    called = {}

    def fake_run(args):
        called["ran"] = True
        return "OK"

    monkeypatch.setattr("h2t.connectors.notion.commands.run", fake_run)
    code = dispatch(["ingest", "notion", "get", "PID"])
    err = capsys.readouterr().err
    assert called.get("ran") is True
    assert "deprecat" in err.lower()
    assert code == 0


def test_ingest_notion_shim_silent_on_json(monkeypatch, capsys):
    def fake_run_json(args):
        return {"id": "x"}

    monkeypatch.setattr("h2t.connectors.notion.commands.run", fake_run_json)
    code = dispatch(["ingest", "notion", "get", "PID", "--json"])
    cap = capsys.readouterr()
    assert "deprecat" not in cap.err.lower()
    assert code == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run h2t dev pytest tests/connectors/notion/test_commands.py -v -k "version_branch or connectors_list or doctor or shim"`
Expected: FAIL — `ImportError: cannot import name 'build_parser' from h2t.cli`.

- [ ] **Step 3: Replace cli.py with the full implementation**

`h2t/cli.py` (keeps Task 0's `dev`/`--version` routing byte-identical; adds connectors, doctor, shim, legacy delegation):
```python
"""h2t CLI: dev wrapper + registry dispatch + doctor + legacy delegation + ingest shim."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import h2t
from h2t.core.errors import UsageError
from h2t.core.output import emit
from h2t.core.registry import discover
from h2t.dev import main as _dev_main

_MIGRATED = {"notion"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h2t", description="h2t unified connector CLI")
    p.add_argument("--version", action="version", version=f"h2t {h2t.__version__}")
    sub = p.add_subparsers(dest="connector")
    sub.add_parser("connectors", help="List available connectors")
    sub.add_parser("doctor", help="Installed CLI health (version, path, connectors, secrets)")
    for spec in discover():
        spec.register(sub)
    return p


def _doctor() -> int:
    print(f"h2t {h2t.__version__}")
    print(f"executable: {shutil.which('h2t') or sys.executable}")
    print("connectors:")
    for spec in discover():
        print(f"  - {spec.name}: {spec.help}")
    notion = bool(os.getenv("NOTION_API_TOKEN")) or \
        (Path.home() / ".config" / "notion" / "token").is_file()
    print(f"secrets: NOTION_API_TOKEN={'present' if notion else 'MISSING'}")
    return 0


def _legacy(argv: list[str]) -> int:
    from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
    old = sys.argv
    sys.argv = ["h2t", *argv]
    try:
        legacy_main()
        return 0
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
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


def _run_connector(argv: list[str]) -> int:
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 2)
    handler = getattr(ns, "_handler", None)
    if handler is None:
        return emit(argv[0], exc=UsageError("no subcommand"), fmt="human")
    fmt = "json" if getattr(ns, "as_json", False) else getattr(ns, "fmt", "human")
    provider = argv[0]
    try:
        return emit(provider, result=handler(ns), fmt=fmt)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — central error→exit mapping
        return emit(provider, exc=exc, fmt=fmt)


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "dev":
        return _dev_main(argv[1:])
    if argv and argv[0] in ("--version", "-V"):
        print(f"h2t {h2t.__version__}")
        return 0
    if argv and argv[0] == "doctor":
        return _doctor()
    if argv and argv[0] == "connectors":
        for spec in discover():
            print(f"{spec.name:12} {spec.help}")
        return 0
    # ingest notion shim → new connector (spec §10)
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "notion":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest) and rest[j + 1] in ("json", "markdown"):
                norm += ["--json"] if rest[j + 1] == "json" else ["--format", "md"]
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            print("deprecated: `h2t ingest notion` → use `h2t notion` (spec §10)",
                  file=sys.stderr)
        return _run_connector(["notion", *norm])
    if argv and argv[0] in ("gather", "ingest"):
        return _legacy(argv)
    if argv and argv[0] in _MIGRATED:
        return _run_connector(argv)
    if not argv:
        build_parser().print_help()
        return 0
    return _legacy(argv)


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI tests + full suite**

Run: `uv run h2t dev pytest tests/connectors/notion tests/core -v`
Expected: PASS (all core + notion incl. version/connectors/doctor/shim).

- [ ] **Step 5: Manual smoke (no network)**

Run: `uv run h2t --version`
Run: `uv run h2t connectors`
Run: `uv run h2t notion --help`
Run: `uv run h2t doctor`
Expected: `h2t 0.2.0`; lists `notion`; notion help; doctor shows version/connectors/secrets. No `notion_client` import error (lazy).

- [ ] **Step 6: Commit**

```
git add h2t/cli.py tests/connectors/notion/test_commands.py
git commit -m "feat(h2t): cli dispatcher, doctor, legacy delegation, ingest shim"
```

---

### Task 10: Notion SKILL.md → spec §8 conformance

**Files:** Modify `plugins/h2t-ops/skills/notion/SKILL.md`

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
If it fails: run `/h2t-core:setup`. `h2t doctor` reports version, install path, connectors,
and secrets presence (no network).

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
| `h2t notion create <parent-id> "Title" [--content "md" \| --file f.md] [--database]` | create page |
| `h2t notion update <page-id> [--title T] [--append "md" \| --file f.md] [--replace]` | update page |
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

- [ ] **Step 2: Verify via named check**

Run: `uv run h2t dev check skill-md-notion`
Expected: prints `OK skill-md-notion`, exit 0.

- [ ] **Step 3: Commit**

```
git add plugins/h2t-ops/skills/notion/SKILL.md
git commit -m "docs(notion): SKILL.md to spec §8 contract (h2t notion)"
```

---

### Task 11: DoD verification (spec §12)

**Files:** none (verification only)

- [ ] **Step 1: Full ТЗ-0 suite**

Run: `uv run h2t dev pytest tests/core tests/connectors -v`
Expected: ALL PASS.

- [ ] **Step 2: DoD checklist (all via uv run — no shell idioms)**

```
uv run h2t --version
uv run h2t notion --help
uv run h2t doctor
uv run h2t ingest notion --help
uv run h2t dev python -c "from h2t.connectors.notion.client import NotionClient; print('import ok')"
uv run h2t dev check no-syspath
uv run h2t dev check lazy-registry
uv run h2t dev check gather-smoke
uv run h2t dev check skill-md-notion
```
Expected: `h2t 0.2.0` exit 0; notion help; doctor block; ingest-notion help (with deprecation on stderr); `import ok`; `OK no-syspath`; `OK lazy-registry`; `OK gather-smoke (exit=0)`; `OK skill-md-notion`.

- [ ] **Step 3: Final commit**

```
git add -A docs/superpowers/plans/2026-05-18-h2t-connector-architecture-tz0.md
git commit -m "chore(h2t): ТЗ-0 walking skeleton complete — DoD verified"
```

---

## Self-Review

**Spec coverage (spec §11 In-ТЗ-0 → task):**
- `h2t/` package + pyproject `h2t.cli:main` + no new `sys.path.insert` → Task 0; verified Task 11 (`check no-syspath`)
- `core/registry|errors|envelope|output|secrets` → Tasks 4,1,2,3,5
- Notion connector walking skeleton → Tasks 6,7,8
- Backward-compatible `ingest notion` route (spec §10 policy) → Task 9
- Tests `tests/core/` + `tests/connectors/notion/` → every task TDD; aggregate Task 11
- Notion SKILL.md §8 → Task 10
- Lazy-discovery "zero heavy imports" → Task 4 test + `check lazy-registry` (Task 0 wrapper, run Task 11)
- Transition non-regression (`gather`) → Task 9 `_legacy` + `check gather-smoke`
- §14 decisions + transition gap → Locked Design Decisions block
- spec §7 three surfaces (`--version` / `doctor` / `dev`) → Task 0 (dev/version) + Task 9 (doctor)

**Placeholder scan:** no TBD/TODO; every code step shows full content; Task 6 re-wrap uses exact copy-then-edit instructions against a named real file with each edit shown verbatim.

**Type consistency:** `ConnectorSpec(name,help,client,register)` consistent Tasks 4/8; `emit(provider,*,result,exc,fmt)` consistent Tasks 3/9; `discover()`/`resolve_client()` consistent Tasks 4/9/dev; `dispatch()` `dev`+`--version` branches byte-identical Task 0 ↔ Task 9; error `kind` ↔ `EXIT_CODES` ↔ envelope `error.type` consistent Tasks 1/2/3; `run(args)` handler + `_handler` default consistent Tasks 7/9; shim test uses named `def fake_run` (no lambda).

Out-of-scope confirmed deferred: gmail/calendar/drive/meetgeek/telegram (ТЗ-1); research/fetch + `core/http.py` + legacy exit-code remap + rich envelope (ТЗ-2). `python-dotenv` declared but unused by ТЗ-0 Notion path (decision #4 note).
