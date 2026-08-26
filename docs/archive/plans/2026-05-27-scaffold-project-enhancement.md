---
title: "scaffold-project Enhancement — absorb docs-init, docs-sync-labels, hook install + setup latest/ junction"
status: "draft"
date: "2026-05-27"
milestone: "skills-release"
---

# scaffold-project Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Extend `setup_h2t.py` to create a `latest/` junction/symlink pointing to the current plugin version. (2) Extend `scaffold_project.py` to call `docs-init` and `docs-sync-labels` scripts as steps, and write thin-wrapper hooks into `.claude/settings.json`. (3) Create the `on-stop` hook handler script.

**Architecture:** All new helpers in `scaffold_project.py` shell out to existing CLI scripts using their real contracts. `setup_h2t.py` gets `create_latest_link()` with semver-aware version selection. `on-stop` is a new Python handler in `plugins/h2t-core/hooks-handlers/`. Tests assert real CLI flags, not just that subprocess was called.

**Tech Stack:** Python 3.11, pytest, pathlib, subprocess. No new dependencies.

---

## CLI Contracts (read before implementing)

| Script | Real invocation | Notes |
|--------|----------------|-------|
| `docs-init/scripts/init.py` | `init.py <repo_name> --apply` | Positional repo name; resolves path as `DEV_ROOT/name`; dry-run without `--apply` |
| `docs-sync-labels/scripts/sync_labels.py` | `sync_labels.py <repo_name> --apply` | Dry-run without `--apply`; exits 0 in both modes |
| `hooks-handlers/on-stop` (new) | Called by Claude Code Stop hook; exits 0 always | Non-blocking |

**Constraint:** `docs-init` resolves the project path as `DEV_ROOT / repo_name` (`C:/dev/{name}`). The helper must skip when the project is not under `DEV_ROOT`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `plugins/h2t-core/skills/setup/scripts/setup_h2t.py` | Modify | Add `create_latest_link()` with semver sort + `--latest-only` flag |
| `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | Modify | Add `run_docs_init()`, `run_sync_labels()`, `install_hooks()` helpers; wire into `cmd_create()` / `cmd_github()` |
| `plugins/h2t-core/hooks-handlers/on-stop` | **Create** | Non-blocking Stop hook: check milestone completeness → suggest milestone-closure |
| `tests/scaffold/__init__.py` | Create | Package marker |
| `tests/scaffold/test_scaffold_latest.py` | Create | Unit tests for `create_latest_link` |
| `tests/scaffold/test_scaffold_steps.py` | Create | Unit tests for `run_docs_init`, `run_sync_labels`, `install_hooks` |

---

### Task 0: `create_latest_link` in setup_h2t.py

**Files:**
- Modify: `plugins/h2t-core/skills/setup/scripts/setup_h2t.py`

Creates `~/.claude/plugins/cache/lichtpfad/h2t-core/latest/` → current installed version.
Used by thin-wrapper hooks so `settings.json` never needs updating after a plugin upgrade.
Uses **semver-aware sorting** to avoid `3.10.0 < 3.2.0` lexicographic trap.

- [ ] **Step 1: Write failing tests**

Create `tests/scaffold/__init__.py` (empty) and `tests/scaffold/test_scaffold_latest.py`:

```python
"""Tests for create_latest_link in setup_h2t."""
import sys
from pathlib import Path

_SETUP_DIR = Path(__file__).parents[2] / "plugins/h2t-core/skills/setup/scripts"
sys.path.insert(0, str(_SETUP_DIR))

from setup_h2t import create_latest_link, _semver_key


def test_semver_key_orders_correctly():
    """3.2.0 sorts after 3.10.0 lexicographically but semver puts 3.10.0 higher."""
    assert _semver_key("3.10.0") > _semver_key("3.2.0")


def test_semver_key_ignores_non_version_dirs():
    """Non-version strings return a zero tuple instead of raising."""
    assert _semver_key("latest") == (0, 0, 0)
    assert _semver_key("something-else") == (0, 0, 0)


def test_create_latest_link_creates_junction(tmp_path):
    """Creates latest/ pointing to versioned dir."""
    versioned = tmp_path / "1.2.3"
    versioned.mkdir()
    latest = tmp_path / "latest"
    create_latest_link(versioned, latest)
    assert latest.exists()


def test_create_latest_link_updates_existing(tmp_path):
    """Updates latest/ when called again with a new version."""
    old = tmp_path / "1.0.0"
    old.mkdir()
    new = tmp_path / "2.0.0"
    new.mkdir()
    latest = tmp_path / "latest"
    create_latest_link(old, latest)
    create_latest_link(new, latest)
    assert latest.exists()


def test_create_latest_link_returns_path(tmp_path):
    """Returns the resolved latest path."""
    versioned = tmp_path / "1.0.0"
    versioned.mkdir()
    latest = tmp_path / "latest"
    result = create_latest_link(versioned, latest)
    assert result == latest
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_latest.py -v
```

Expected: `ImportError: cannot import name 'create_latest_link'`

- [ ] **Step 3: Implement `_semver_key` and `create_latest_link`**

Add near the top of `setup_h2t.py`, after imports:

```python
def _semver_key(name: str) -> tuple[int, int, int]:
    parts = name.split(".")
    try:
        return tuple(int(p) for p in parts[:3]) + (0,) * (3 - len(parts[:3]))
    except ValueError:
        return (0, 0, 0)


def create_latest_link(versioned_dir: Path, latest_path: Path) -> Path:
    if latest_path.exists() or latest_path.is_symlink():
        if sys.platform == "win32":
            import subprocess as _sp
            _sp.run(["cmd", "/c", "rmdir", str(latest_path)], capture_output=True)
        else:
            if latest_path.is_symlink():
                latest_path.unlink()
            else:
                latest_path.rmdir()
    if sys.platform == "win32":
        import subprocess as _sp
        r = _sp.run(
            ["cmd", "/c", "mklink", "/J", str(latest_path), str(versioned_dir)],
            capture_output=True,
        )
        if r.returncode != 0:
            latest_path.symlink_to(versioned_dir, target_is_directory=True)
    else:
        latest_path.symlink_to(versioned_dir, target_is_directory=True)
    return latest_path
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_latest.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Wire into setup_h2t.py main flow**

After h2t-core plugin install step, detect installed version dir using semver sort and call:

```python
plugin_cache = Path.home() / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-core"
if plugin_cache.exists():
    versions = sorted(
        [d for d in plugin_cache.iterdir()
         if d.is_dir() and d.name != "latest" and _semver_key(d.name) != (0, 0, 0)],
        key=lambda p: _semver_key(p.name),
    )
    if versions:
        current = versions[-1]
        create_latest_link(current, plugin_cache / "latest")
        # Write plugin-versions.json fallback for hooks that can't resolve latest/
        versions_file = Path.home() / ".h2t" / "config" / "plugin-versions.json"
        versions_file.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        _data = {}
        if versions_file.exists():
            try:
                _data = _json.loads(versions_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        _data["h2t-core"] = str(current)
        versions_file.write_text(_json.dumps(_data, indent=2), encoding="utf-8")
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/setup/scripts/setup_h2t.py tests/scaffold/__init__.py tests/scaffold/test_scaffold_latest.py
git -C C:/dev/h2t-skills commit -m "feat(setup): create latest/ junction/symlink after plugin install (semver sort)"
```

---

### Task 1: `run_docs_init` helper in scaffold_project.py

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Test: `tests/scaffold/test_scaffold_steps.py`

**Contract:** `init.py <repo_name> --apply` — positional repo name, resolves path as `DEV_ROOT/name`.
Skip silently when project dir is not under `DEV_ROOT` (non-standard location).

- [ ] **Step 1: Write failing tests**

Create `tests/scaffold/test_scaffold_steps.py`:

```python
"""Tests for scaffold-project step helpers."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_SCAFFOLD_DIR = Path(__file__).parents[2] / "plugins/h2t-core/skills/scaffold-project/scripts"
sys.path.insert(0, str(_SCAFFOLD_DIR))

from scaffold_project import run_docs_init


def test_run_docs_init_passes_repo_name_not_path(tmp_path):
    """run_docs_init passes repo name (positional), not --cwd."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", tmp_path)
    cmd = mock_run.call_args[0][0]
    assert "my-repo" in cmd
    assert "--cwd" not in " ".join(str(c) for c in cmd)


def test_run_docs_init_passes_apply_flag(tmp_path):
    """run_docs_init always passes --apply so files are actually created."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", tmp_path)
    cmd = mock_run.call_args[0][0]
    assert "--apply" in cmd


def test_run_docs_init_skips_non_dev_root(tmp_path):
    """Skips gracefully when project is not under DEV_ROOT."""
    result = run_docs_init("my-repo", tmp_path / "elsewhere" / "my-repo")
    assert result["status"] == "skip"


def test_run_docs_init_returns_error_on_failure(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        result = run_docs_init("my-repo", tmp_path)
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "docs_init" -v
```

Expected: `ImportError: cannot import name 'run_docs_init'`

- [ ] **Step 3: Implement `run_docs_init`**

Add after `cmd_github()` in `scaffold_project.py`:

```python
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))

def run_docs_init(repo_name: str, project_dir: Path) -> dict:
    # init.py resolves path as DEV_ROOT/repo_name; skip for non-standard locations
    if project_dir.resolve() != (_DEV_ROOT / repo_name).resolve():
        return {"status": "skip", "reason": "project not under DEV_ROOT — run docs-init manually"}
    init_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-init" / "scripts" / "init.py"
    if not init_script.exists():
        return {"status": "skip", "reason": "docs-init script not found"}
    r = subprocess.run(
        [sys.executable, str(init_script), repo_name, "--apply"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()}
    return {"status": "error", "error": r.stderr.strip()[:200]}
```

Add `import os` at top of file if not already present.

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "docs_init" -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Wire into `cmd_create()` for code-github / code-local types**

In `cmd_create()`, after initial commit:

```python
if is_git and not args.dry_run:
    di = run_docs_init(args.id, project_dir)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di['error']}"}
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py
git -C C:/dev/h2t-skills commit -m "feat(scaffold-project): call docs-init after scaffold (repo_name --apply contract)"
```

---

### Task 2: `run_sync_labels` helper in scaffold_project.py

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Test: `tests/scaffold/test_scaffold_steps.py`

**Contract:** `sync_labels.py <repo_name> --apply` — without `--apply` it's a no-op dry-run that exits 0.
Must pass `--apply` to actually create labels. Skip when no GitHub remote.

- [ ] **Step 1: Write failing tests**

Append to `tests/scaffold/test_scaffold_steps.py`:

```python
from scaffold_project import run_sync_labels


def test_run_sync_labels_passes_apply_flag(tmp_path):
    """--apply is required to actually sync labels; must be present."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced", stderr="")
        run_sync_labels("h2t-skills")
    cmd = mock_run.call_args[0][0]
    assert "--apply" in cmd


def test_run_sync_labels_passes_repo_name(tmp_path):
    """repo name is passed as a positional argument."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_sync_labels("h2t-skills")
    cmd = mock_run.call_args[0][0]
    assert "h2t-skills" in cmd


def test_run_sync_labels_skip_if_no_repo_name():
    """Returns skip status when repo name is empty."""
    result = run_sync_labels("")
    assert result["status"] == "skip"


def test_run_sync_labels_error_on_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="gh not found")
        result = run_sync_labels("h2t-skills")
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "sync_labels" -v
```

Expected: `ImportError: cannot import name 'run_sync_labels'`

- [ ] **Step 3: Implement `run_sync_labels`**

```python
def run_sync_labels(repo_name: str) -> dict:
    if not repo_name:
        return {"status": "skip", "reason": "no repo name"}
    sync_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-sync-labels" / "scripts" / "sync_labels.py"
    if not sync_script.exists():
        return {"status": "skip", "reason": "sync_labels script not found"}
    r = subprocess.run(
        [sys.executable, str(sync_script), repo_name, "--apply"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()[:200]}
    return {"status": "error", "error": r.stderr.strip()[:200]}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "sync_labels" -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Wire into `cmd_github()`**

After GitHub repo creation succeeds:

```python
repo_name = args.github.split("/")[-1] if "/" in args.github else args.github
sl = run_sync_labels(repo_name)
actions.append(f"sync-labels: {sl['status']}")
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py
git -C C:/dev/h2t-skills commit -m "feat(scaffold-project): call sync_labels --apply after github scaffold"
```

---

### Task 3: Create `on-stop` hook handler

**Files:**
- **Create:** `plugins/h2t-core/hooks-handlers/on-stop`

The Stop hook script does not yet exist. It must be created before `install_hooks` can reference it.
Non-blocking: always exits 0. Prints a suggestion if a milestone has all issues closed.

- [ ] **Step 1: Create `plugins/h2t-core/hooks-handlers/on-stop`**

```python
#!/usr/bin/env python3
"""Stop hook: suggest milestone-closure when all milestone issues are closed."""
import subprocess
import sys


def _check_milestones() -> None:
    # gh milestone list auto-resolves owner/repo from current git remote
    r = subprocess.run(
        ["gh", "milestone", "list", "--json", "title,openIssues",
         "--jq", ".[] | select(.openIssues == 0) | .title"],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return
    for title in r.stdout.strip().splitlines():
        print(f"[h2t] Milestone '{title}' has no open issues — consider /h2t-dev:milestone-closure")


if __name__ == "__main__":
    try:
        _check_milestones()
    except Exception:
        pass  # non-blocking: never fail the session
    sys.exit(0)
```

- [ ] **Step 2: Verify script exits 0 unconditionally**

```bash
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-core/hooks-handlers/on-stop
```

Expected: exits 0 (may print nothing if gh CLI returns an error — that's fine)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/hooks-handlers/on-stop
git -C C:/dev/h2t-skills commit -m "feat(h2t-core): add on-stop hook handler — suggest milestone-closure when milestone done"
```

---

### Task 4: `install_hooks` — write thin-wrapper hooks into .claude/settings.json

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Test: `tests/scaffold/test_scaffold_steps.py`

References `on-stop` via the `latest/` junction created by Task 0.
Path: `~/.claude/plugins/cache/lichtpfad/h2t-core/latest/hooks-handlers/on-stop`.

- [ ] **Step 1: Write failing tests**

Append to `tests/scaffold/test_scaffold_steps.py`:

```python
import json
from scaffold_project import install_hooks


def test_install_hooks_creates_settings(tmp_path):
    """Creates .claude/settings.json with Stop hook."""
    install_hooks(tmp_path)
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()


def test_install_hooks_has_stop_hook(tmp_path):
    """Stop hook entry references on-stop handler."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    assert any("on-stop" in h.get("command", "") for h in stop_hooks)


def test_install_hooks_stop_hook_points_to_latest(tmp_path):
    """Stop hook path starts with ~ (portable) and references latest/ junction."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    cmd = stop_hooks[0]["command"]
    assert cmd.startswith("~")
    assert "latest" in cmd


def test_install_hooks_idempotent(tmp_path):
    """Calling twice does not duplicate hooks."""
    install_hooks(tmp_path)
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    on_stop = [h for h in stop_hooks if "on-stop" in h.get("command", "")]
    assert len(on_stop) == 1
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "install_hooks" -v
```

Expected: `ImportError: cannot import name 'install_hooks'`

- [ ] **Step 3: Implement `install_hooks`**

```python
# Use ~ so settings.json works on any machine, not just the one that ran scaffold
_HOOK_BASE = "~/.claude/plugins/cache/lichtpfad/h2t-core/latest"

_HOOK_ENTRIES = {
    "Stop": [
        {
            "matcher": "",
            "command": f"{_HOOK_BASE}/hooks-handlers/on-stop",
        }
    ],
}


def install_hooks(project_dir: Path) -> dict:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    else:
        data = {}
    hooks = data.setdefault("hooks", {})
    for event, entries in _HOOK_ENTRIES.items():
        existing = hooks.setdefault(event, [])
        for entry in entries:
            if not any(entry["command"] in h.get("command", "") for h in existing):
                existing.append(entry)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(settings_path)}
```

Add `import json` at top of file if not present.

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "install_hooks" -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Wire into `cmd_create()` after git init**

```python
if is_git and not args.dry_run:
    ih = install_hooks(project_dir)
    actions.append(f"install-hooks: {ih['status']}")
```

- [ ] **Step 6: Run full scaffold test suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py
git -C C:/dev/h2t-skills commit -m "feat(scaffold-project): install on-stop thin-wrapper hook into .claude/settings.json"
```

---

### Task 5: Update SKILL.md + bump version

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/SKILL.md`

- [ ] **Step 1: Update description to mention new steps**

In `SKILL.md`, update the `description:` field to mention docs-init, sync-labels, and hook install.
Note the constraint: docs-init only runs for projects created under `DEV_ROOT` (`C:/dev`).

- [ ] **Step 2: Bump patch version**

```bash
C:/dev/h2t-skills/.venv/Scripts/python scripts/bump_plugin.py h2t-core 3.2.0
```

- [ ] **Step 3: Final test run**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/SKILL.md plugins/h2t-core/plugin.json plugins/h2t-core/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "docs(scaffold-project): update SKILL.md with new steps; bump version"
```
