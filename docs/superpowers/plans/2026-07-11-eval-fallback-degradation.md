---
title: "Eval fallback degradation"
status: "draft"
date: "2026-07-11"
milestone: ""
---

# Eval fallback degradation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the eval subsystem degrade cleanly (and configurably) when h2t-evals is absent, via a tri-state `H2T_EVALS_MODE` (default `auto`), a centralized never-crash `SkillEval`, and a read-only `h2t-ops evals status`.

**Architecture:** Add mode resolution to the canonical `lib/eval/session.py`; gate all eval writes (`_write_local`/`_send_central`) on the resolved mode; keep the `skill_graph` lesson hook mode-independent. Sync the byte-identical vendored copy (`plugins/h2t-core/lib/eval/session.py`) that runtime actually loads, guarded by a parity test. Expose status via a new `evals` connector.

**Tech Stack:** Python stdlib (no new deps), pytest, argparse (h2t_ops connector registry).

**Spec:** `docs/superpowers/specs/2026-07-11-eval-fallback-degradation.md`

Run tests with: `C:/dev/h2t-skills/.venv/Scripts/pytest` (no venv activation).

---

## File Structure

- Modify: `lib/eval/session.py` — add `resolve_mode()` + `_sdk_available()`; store `self._mode` in `__init__`; gate `__exit__`/`metric` by mode.
- Modify: `lib/eval/test_session.py` — migrate 3 local-write tests to explicit `H2T_EVALS_MODE=local`; add mode/auto/stdlib tests.
- Create: `lib/eval/status.py` — `get_status()` read-only dict.
- Create: `lib/eval/test_status.py` — status tests.
- Sync:   `plugins/h2t-core/lib/eval/session.py` — byte-identical copy of root.
- Create: `tests/test_eval_vendored_parity.py` — parity guard.
- Create: `h2t_ops/connectors/evals/__init__.py` + `commands.py` — status connector.
- Create: `tests/connectors/evals/__init__.py` + `test_commands.py` — connector tests.
- Modify: `plugins/h2t-core/CHANGELOG.md` + patch bump.

---

## Task 1: Mode resolution helpers

**Files:**
- Modify: `lib/eval/session.py` (add module-level helpers after the imports, before `class SkillEval`)
- Test: `lib/eval/test_session.py`

- [ ] **Step 1: Write failing unit tests**

Append to `lib/eval/test_session.py`:

```python
from lib.eval import session as sess


def test_resolve_mode_explicit_wins(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({"H2T_EVALS_MODE": "off"}) == "off"
    assert sess.resolve_mode({"H2T_EVALS_MODE": "local"}) == "local"
    assert sess.resolve_mode({"H2T_EVALS_MODE": "push"}) == "push"


def test_resolve_mode_auto_push_when_sdk_and_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({"H2T_EVALS_TOKEN": "t"}) == "push"


def test_resolve_mode_auto_off_without_sdk(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_TOKEN": "t"}) == "off"


def test_resolve_mode_auto_off_without_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({}) == "off"


def test_resolve_mode_legacy_enabled_maps_push(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_ENABLED": "1"}) == "push"


def test_resolve_mode_invalid_behaves_as_auto(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_MODE": "garbage"}) == "off"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_resolve_mode_explicit_wins -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'resolve_mode'`

- [ ] **Step 3: Add the helpers**

In `lib/eval/session.py`, immediately after the import block (after `from typing import Optional`) and before `class SkillEval:`, insert:

```python
_VALID_MODES = ("auto", "off", "local", "push")


def _sdk_available() -> bool:
    """True if the h2t_evals SDK client is importable (cheap, no network)."""
    try:
        import h2t_evals.sdk  # noqa: F401
        return True
    except Exception:
        return False


def resolve_mode(env=None) -> str:
    """Resolve H2T_EVALS_MODE to a terminal mode: 'off' | 'local' | 'push'.

    Priority: explicit off/local/push > explicit 'auto' (resolved) >
    legacy H2T_EVALS_ENABLED=1 (push) > auto. 'auto' resolves to 'push' when
    the SDK is importable AND H2T_EVALS_TOKEN is set, else 'off'. An unset or
    invalid H2T_EVALS_MODE behaves as auto (with the legacy flag honored).
    """
    env = env if env is not None else os.environ
    raw = (env.get("H2T_EVALS_MODE") or "").strip().lower()
    if raw in ("off", "local", "push"):
        return raw
    if raw != "auto" and env.get("H2T_EVALS_ENABLED") == "1":
        return "push"
    if _sdk_available() and env.get("H2T_EVALS_TOKEN"):
        return "push"
    return "off"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py -k resolve_mode -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(eval): add H2T_EVALS_MODE resolution (auto/off/local/push)"
```

---

## Task 2: Gate eval writes by mode

**Files:**
- Modify: `lib/eval/session.py` (`__init__`, `__exit__`, `metric`)
- Test: `lib/eval/test_session.py`

- [ ] **Step 1: Migrate existing local-write tests + add behavior tests**

In `lib/eval/test_session.py`, add `monkeypatch` to the three local-write tests and force local mode. Change their signatures and first line:

```python
def test_skill_eval_local_write_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    # ... rest unchanged ...


def test_skill_eval_local_write_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    # ... rest unchanged ...


def test_skill_eval_metrics_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    # ... rest unchanged ...
```

Then append the new behavior tests:

```python
def test_off_mode_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    for var in ("H2T_EVALS_MODE", "H2T_EVALS_TOKEN", "H2T_EVALS_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    evals_root = tmp_path / "evals"
    with sess.SkillEval("session-start", domain="d", project="p",
                        evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    assert not evals_root.exists()


def test_push_with_absent_sdk_degrades_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "push")

    def _boom(self, status):
        raise ImportError("no sdk")

    monkeypatch.setattr(sess.SkillEval, "_send_central", _boom)
    evals_root = tmp_path / "evals"
    with sess.SkillEval("handoff", domain="d", project="p",
                        evals_root=str(evals_root)):
        pass
    files = list((evals_root / "handoff" / "sessions").glob("*.json"))
    assert len(files) == 1


def test_session_imports_only_stdlib():
    import ast
    import sys
    import pathlib
    tree = ast.parse(pathlib.Path(sess.__file__).read_text(encoding="utf-8"))
    roots = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    non_stdlib = roots - set(sys.stdlib_module_names)
    assert non_stdlib == set(), f"non-stdlib top-level imports: {non_stdlib}"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py::test_off_mode_writes_nothing -v`
Expected: FAIL (off mode still writes because `__init__` has no `_mode` and `__exit__` always writes)

- [ ] **Step 3: Store `_mode` in `__init__`**

In `lib/eval/session.py`, at the end of `__init__` (after `self._started_at: Optional[str] = None`), add:

```python
        self._mode = resolve_mode()
```

- [ ] **Step 4: Gate `__exit__` by mode**

Replace the body of `__exit__` (the block that computes `status`, calls `_write_local`, and the `H2T_EVALS_ENABLED` check) with:

```python
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if self._mode in ("local", "push"):
                status = "failure" if exc_type else "success"
                ended_at = datetime.now(timezone.utc).isoformat()
                self._write_local(status, ended_at)
                if self._mode == "push":
                    self._send_central(status)
        except Exception:
            pass  # never crash a skill for eval failure
        if exc_type is not None and self._skill_graph is not None:
            try:
                self._skill_graph.add_lesson(
                    skill_name=self.skill,
                    trigger=str(exc_val) if exc_val else "skill execution failure",
                    resolution="",
                    lesson_type="eval-finding",
                )
            except Exception:
                pass  # never crash a skill for graph failure
        return False  # do not suppress exceptions
```

- [ ] **Step 5: Make `metric` a no-op when off**

In `lib/eval/session.py`, at the start of `metric()` (before `entry: dict = {"key": key}`), add:

```python
        if self._mode == "off":
            return
```

- [ ] **Step 6: Run the full eval test module**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_session.py -v`
Expected: all pass (migrated + new + existing skill_graph tests)

- [ ] **Step 7: Commit**

```bash
git add lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(eval): gate local/central writes on resolved mode; off is a no-op"
```

---

## Task 3: Sync vendored copy + parity guard

**Files:**
- Sync: `plugins/h2t-core/lib/eval/session.py` (overwrite with root copy)
- Create: `tests/test_eval_vendored_parity.py`

- [ ] **Step 1: Write the parity test**

Create `tests/test_eval_vendored_parity.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eval_session_vendored_parity():
    """The vendored plugin copy (the runtime path) must match canonical root."""
    root = (ROOT / "lib" / "eval" / "session.py").read_text(encoding="utf-8")
    vendored = (
        ROOT / "plugins" / "h2t-core" / "lib" / "eval" / "session.py"
    ).read_text(encoding="utf-8")
    assert root == vendored, "lib/eval/session.py drifted from vendored copy; re-sync"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_eval_vendored_parity.py -v`
Expected: FAIL (vendored is stale — lacks skill_graph + new mode logic)

- [ ] **Step 3: Sync the vendored copy**

Run: `cp lib/eval/session.py plugins/h2t-core/lib/eval/session.py`

- [ ] **Step 4: Run parity test + confirm vendored still imports**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/test_eval_vendored_parity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/lib/eval/session.py tests/test_eval_vendored_parity.py
git commit -m "fix(eval): sync vendored session.py to canonical + parity guard"
```

---

## Task 4: Read-only status module

**Files:**
- Create: `lib/eval/status.py`
- Create: `lib/eval/test_status.py`

- [ ] **Step 1: Write failing tests**

Create `lib/eval/test_status.py`:

```python
from lib.eval import session as sess
from lib.eval.status import get_status


def test_status_off_when_no_sdk_or_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    st = get_status(env={}, evals_root="/nonexistent")
    assert st["mode"] == "off"
    assert st["sdk_available"] is False
    assert st["token_present"] is False
    assert "H2T_EVALS_MODE=local" in st["hint"]


def test_status_push_when_sdk_and_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    st = get_status(env={"H2T_EVALS_TOKEN": "t"}, evals_root="/nonexistent")
    assert st["mode"] == "push"
    assert st["token_present"] is True


def test_status_source_legacy(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    st = get_status(env={"H2T_EVALS_ENABLED": "1"}, evals_root="/nonexistent")
    assert st["source"] == "legacy"
    assert st["mode"] == "push"


def test_status_counts_local_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    d = tmp_path / "session-start" / "sessions"
    d.mkdir(parents=True)
    (d / "se-2026-07-11-001.json").write_text("{}", encoding="utf-8")
    st = get_status(env={}, evals_root=str(tmp_path))
    assert st["session_count"] == 1
    assert st["local_dir"] == str(tmp_path)
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.eval.status'`

- [ ] **Step 3: Implement `status.py`**

Create `lib/eval/status.py`:

```python
"""Read-only eval status — offline-safe, no writes, no network."""
import os
from pathlib import Path

from .session import _sdk_available, resolve_mode


def _mode_source(env) -> str:
    raw = (env.get("H2T_EVALS_MODE") or "").strip().lower()
    if raw in ("off", "local", "push", "auto"):
        return "env"
    if env.get("H2T_EVALS_ENABLED") == "1":
        return "legacy"
    return "default"


def _hint(mode: str, sdk: bool, token: bool) -> str:
    if mode == "push":
        return "push active"
    if mode == "local":
        return "local-only (H2T_EVALS_MODE=local)"
    missing = []
    if not sdk:
        missing.append("SDK not importable (see h2t-evals#99)")
    if not token:
        missing.append("H2T_EVALS_TOKEN unset")
    if missing:
        return (
            "auto→off: "
            + "; ".join(missing)
            + ". Provide both to auto-activate push, or set H2T_EVALS_MODE=local."
        )
    return "off (explicit)"


def get_status(env=None, evals_root=None) -> dict:
    env = env if env is not None else os.environ
    mode = resolve_mode(env)
    sdk = _sdk_available()
    token = bool(env.get("H2T_EVALS_TOKEN"))
    root = Path(evals_root) if evals_root else Path.home() / ".h2t" / "evals"
    try:
        count = sum(1 for _ in root.rglob("*.json")) if root.exists() else 0
    except OSError:
        count = 0
    return {
        "mode": mode,
        "source": _mode_source(env),
        "sdk_available": sdk,
        "token_present": token,
        "service_url": env.get("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088"),
        "local_dir": str(root),
        "session_count": count,
        "hint": _hint(mode, sdk, token),
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_status.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add lib/eval/status.py lib/eval/test_status.py
git commit -m "feat(eval): add read-only get_status()"
```

---

## Task 5: `h2t-ops evals status` connector

**Files:**
- Create: `h2t_ops/connectors/evals/__init__.py`
- Create: `h2t_ops/connectors/evals/commands.py`
- Create: `tests/connectors/evals/__init__.py`
- Create: `tests/connectors/evals/test_commands.py`

- [ ] **Step 1: Write failing tests**

Create `tests/connectors/evals/__init__.py` (empty file), then `tests/connectors/evals/test_commands.py`:

```python
import argparse

from h2t_ops.core.registry import discover


def test_evals_connector_registered():
    names = {spec.name for spec in discover()}
    assert "evals" in names


def test_evals_status_handler_returns_status(monkeypatch):
    from lib.eval import session as sess
    from h2t_ops.connectors.evals.commands import _cmd_status

    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    result = _cmd_status(argparse.Namespace())
    expected_keys = {
        "mode", "source", "sdk_available", "token_present",
        "service_url", "local_dir", "session_count", "hint",
    }
    assert expected_keys <= set(result)
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/evals/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'h2t_ops.connectors.evals'`

- [ ] **Step 3: Implement the connector**

Create `h2t_ops/connectors/evals/__init__.py`:

```python
"""Evals connector - registry entry (read-only status)."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register

CONNECTOR = ConnectorSpec(
    name="evals",
    help="Eval telemetry mode/status (read-only)",
    client="lib.eval.status:get_status",
    register=register,
)
```

Create `h2t_ops/connectors/evals/commands.py`:

```python
from __future__ import annotations

from typing import Any


def _cmd_status(ns: Any) -> dict:
    from lib.eval.status import get_status

    return get_status()


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("evals", help="Eval telemetry mode/status (read-only)")
    cmds = p.add_subparsers(dest="command")
    status = cmds.add_parser("status", help="Show resolved eval mode and availability")
    status.add_argument("--json", action="store_true", dest="as_json")
    status.set_defaults(_handler=_cmd_status)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/evals/test_commands.py -v`
Expected: 2 passed

- [ ] **Step 5: Smoke-test the CLI**

Run: `C:/dev/h2t-skills/.venv/Scripts/python -m h2t_ops.cli evals status --json`
Expected: JSON dict with `mode`, `source`, `hint` keys (no crash)

- [ ] **Step 6: Commit**

```bash
git add h2t_ops/connectors/evals tests/connectors/evals
git commit -m "feat(h2t-ops): add read-only 'evals status' connector"
```

---

## Task 6: CHANGELOG + version bump

**Files:**
- Modify: `plugins/h2t-core/CHANGELOG.md` (via bump script)

- [ ] **Step 1: Bump h2t-core patch (vendored lib changed)**

`bump_plugin.py` takes an explicit version (`<plugin_name> <new_version>`). Current
h2t-core is `3.2.12`, so bump to `3.2.13` (verify current first with
`grep -m1 version plugins/h2t-core/.claude-plugin/plugin.json` in case another commit bumped it):

Run: `C:/dev/h2t-skills/.venv/Scripts/python scripts/bump_plugin.py h2t-core 3.2.13`
Expected: `plugin.json` + `marketplace.json` + `CHANGELOG.md` updated to 3.2.13.

- [ ] **Step 2: Add a CHANGELOG entry line**

In `plugins/h2t-core/CHANGELOG.md`, under the new version heading, add:

```markdown
- eval fallback: `H2T_EVALS_MODE` (auto/off/local/push, default auto); off-by-default
  for adopters without h2t-evals; `h2t-ops evals status`. BREAKING: default is no longer
  implicit local-write — set `H2T_EVALS_MODE=local` to keep local-only telemetry.
```

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-core/plugin.json plugins/h2t-core/CHANGELOG.md
git commit -m "chore(h2t-core): bump patch for eval fallback mode"
```

---

## Task 7: Full suite + lint green

- [ ] **Step 1: Run the whole test suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest`
Expected: all green (no regressions in the ~1559-test suite)

- [ ] **Step 2: Run ruff**

Run: `C:/dev/h2t-skills/.venv/Scripts/ruff check lib/ h2t_ops/ tests/`
Expected: no errors

- [ ] **Step 3: Final commit if ruff auto-fixed anything**

```bash
git add -A
git commit -m "chore(eval): ruff clean"
```

---

## Notes for the implementer

- **Do not** add `import h2t_evals` at module top of `session.py` — it must stay stdlib-only (Task 2 test locks this). The SDK import lives inside `_sdk_available()` and `_send_central()`.
- The vendored copy in Task 3 is the **live runtime path** (`h2t-gather`/`h2t-handoff` load it); the parity test keeps it honest. Always edit root then re-run `cp`.
- `skill_graph` behavior is intentionally mode-independent — do not gate it on `self._mode`.
- Mode is resolved once per `SkillEval` construction; that is by design.

