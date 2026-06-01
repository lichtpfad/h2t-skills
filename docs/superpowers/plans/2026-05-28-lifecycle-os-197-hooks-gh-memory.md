---
title: "Lifecycle OS #197 — lifecycle hooks + gh-memory deprecation"
status: "draft"
date: "2026-05-28"
milestone: "lifecycle-os"
related:
  - "#197"
  - "#196"
  - "docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md"
---

# Lifecycle OS #197 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Lifecycle OS hooks a safe byproduct of work and deprecate `gh-memory` as agent memory without breaking old users.

**Architecture:** #197 runs after #196. #196 owns scaffold/init and repairs the Stop milestone hook; #197 adds the missing `PostToolUse(git commit)` docs health hook, ensures scaffold installs both lifecycle hooks idempotently, and turns `gh-memory` into an explicit compatibility shim that points users to `session-start` / `handoff`. Hooks are thin wrappers around deterministic scripts, non-blocking, timeout-bounded, and never perform destructive actions.

**Tech Stack:** Python stdlib (`json`, `os`, `pathlib`, `subprocess`, `sys`, `time`), Claude Code hook JSON via stdin, existing `docs-lint doctor --json`, pytest.

---

## Dependencies

This plan assumes #196 has landed, or at least these files exist and are current:

- `plugins/h2t-core/hooks-handlers/on-stop`
- `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`

If `plugins/h2t-core/hooks-handlers/on-stop` still contains `gh milestone list`,
stop and finish #196 first. #197 should not reimplement milestone closure.

## Scope

In scope:

- Add a non-blocking `PostToolUse` hook handler for `git commit`.
- Run `docs-lint doctor --json` only when the latest commit changed tracked docs markdown files.
- Write hook reports under `.h2t/lifecycle/` and ensure scaffold ignores that cache path locally so hooks do not make repos dirty.
- Install both `Stop` and `PostToolUse` hooks through `scaffold-project`.
- Deprecate `gh-memory` in SKILL.md and h2t-dev docs as a compatibility shim.
- Add tests for hook behavior and deprecation text.

Out of scope:

- POS event publishing.
- Scheduled `project-audit`.
- Changing `docs-lint` internals.
- Closing milestones.
- Running hooks globally for existing repos.

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t-core/hooks-handlers/post_git_commit_docs_lint.py` | Create | Testable backend for PostToolUse git commit docs-lint hook |
| `plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint` | Create | Thin executable wrapper |
| `tests/hooks/test_post_git_commit_docs_lint.py` | Create | Unit tests for hook backend |
| `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | Modify | Install PostToolUse hook alongside Stop hook; ignore hook report cache via `.git/info/exclude` |
| `tests/scaffold/test_scaffold_steps.py` | Modify | Assert hook install includes both hooks and remains idempotent |
| `plugins/h2t-dev/skills/gh-memory/SKILL.md` | Modify | Turn into explicit deprecated compatibility shim |
| `plugins/h2t-dev/README.md` | Modify | Mark `gh-memory` deprecated and point to `session-start` / `handoff` |
| `tests/lifecycle/test_gh_memory_deprecated.py` | Create | Guard against re-promoting gh-memory |
| `plugins/h2t-core/.claude-plugin/plugin.json` | Modify | Patch bump h2t-core |
| `plugins/h2t-dev/.claude-plugin/plugin.json` | Modify | Patch bump h2t-dev |
| `docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md` | Modify | Mark #197 implemented after merge |

---

### Task 1: Add PostToolUse git commit docs-lint hook backend

**Files:**
- Create: `plugins/h2t-core/hooks-handlers/post_git_commit_docs_lint.py`
- Create: `tests/hooks/test_post_git_commit_docs_lint.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hooks/test_post_git_commit_docs_lint.py`:

```python
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_HOOK_DIR = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers"
sys.path.insert(0, str(_HOOK_DIR))

import post_git_commit_docs_lint as hook


def test_is_git_commit_payload_accepts_bash_git_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_accepts_git_c_repo_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git -C C:/work/rejuve commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_accepts_git_config_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git -c user.name=test commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_rejects_other_commands():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
    assert hook.is_git_commit_payload(payload) is False


def test_is_git_commit_payload_rejects_echo_false_positive():
    payload = {"tool_name": "Bash", "tool_input": {"command": 'echo "git commit -m test"'}}
    assert hook.is_git_commit_payload(payload) is False


def test_changed_docs_from_head_filters_docs_markdown(tmp_path):
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="docs/a.md\nsrc/app.py\ndocs/data.json\nREADME.md\n",
            stderr="",
        )
        changed = hook.changed_docs_from_head(tmp_path)

    assert changed == ["docs/a.md"]
    cmd = mock_run.call_args[0][0]
    assert cmd[:4] == ["git", "-C", str(tmp_path), "diff-tree"]


def test_changed_docs_returns_empty_on_git_error(tmp_path):
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad revision")
        assert hook.changed_docs_from_head(tmp_path) == []


def test_find_docs_lint_script_prefers_env(tmp_path, monkeypatch):
    script = tmp_path / "lint.py"
    script.write_text("# lint", encoding="utf-8")
    monkeypatch.setenv("H2T_DOCS_LINT_SCRIPT", str(script))
    assert hook.find_docs_lint_script() == script


def test_build_report_records_skipped_state(tmp_path):
    report = hook.build_hook_report(
        repo_root=tmp_path,
        status="skipped",
        changed_docs=[],
        docs_lint=None,
        message="no docs changed",
    )
    assert report["schema"] == "h2t_lifecycle_report/v0.1"
    assert report["command"] == "post-git-commit-docs-lint"
    assert report["status"] == "skipped"
    assert report["evidence"]["hook"] == "PostToolUse:git-commit:docs-lint"


def test_write_report_uses_h2t_lifecycle_dir(tmp_path):
    report = hook.build_hook_report(
        repo_root=tmp_path,
        status="ok",
        changed_docs=["docs/a.md"],
        docs_lint={"status": "ok"},
        message="done",
    )
    path = hook.write_report(tmp_path, report)
    assert path == tmp_path / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "ok"


def test_run_docs_lint_doctor_uses_timeout(tmp_path):
    lint = tmp_path / "lint.py"
    lint.write_text("# lint", encoding="utf-8")
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"status":"ok"}', stderr="")
        result = hook.run_docs_lint_doctor(tmp_path, lint, timeout=3)
    assert result["status"] == "ok"
    assert mock_run.call_args.kwargs["timeout"] == 3


def test_hook_timeout_seconds_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("H2T_LINT_HOOK_TIMEOUT", "bad")
    assert hook.hook_timeout_seconds() == 8
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_post_git_commit_docs_lint.py -v
```

Expected: import failure because `post_git_commit_docs_lint.py` does not exist.

- [ ] **Step 3: Create hook backend**

Create `plugins/h2t-core/hooks-handlers/post_git_commit_docs_lint.py`:

```python
#!/usr/bin/env python3
"""PostToolUse git commit hook: run docs-lint doctor when docs markdown changed."""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "h2t_lifecycle_report/v0.1"
SCHEMA_VERSION = "0.1"
HOOK_NAME = "PostToolUse:git-commit:docs-lint"
COMMAND = "post-git-commit-docs-lint"


def is_git_commit_payload(payload: dict[str, Any]) -> bool:
    if payload.get("tool_name") not in {"Bash", "shell_command"}:
        return False
    tool_input = payload.get("tool_input") or payload.get("parameters") or {}
    command = str(tool_input.get("command", ""))
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts or parts[0].lower() != "git":
        return False
    i = 1
    while i < len(parts):
        token = parts[i].lower()
        if token == "commit":
            return True
        if token in {"-c", "-C", "--git-dir", "--work-tree"}:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return False
    return False


def changed_docs_from_head(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    changed = []
    for raw in result.stdout.splitlines():
        path = raw.strip().replace("\\", "/")
        if path.startswith("docs/") and path.endswith(".md"):
            changed.append(path)
    return changed


def find_docs_lint_script() -> Path | None:
    env = os.environ.get("H2T_DOCS_LINT_SCRIPT")
    if env and Path(env).is_file():
        return Path(env)

    candidates = [
        Path.cwd() / "plugins" / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py",
        Path("C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py"),
        Path.home() / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-dev" / "latest" / "skills" / "docs-lint" / "scripts" / "lint.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def run_docs_lint_doctor(repo_root: Path, lint_script: Path, *, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, str(lint_script), "doctor", "--root", str(repo_root), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "message": "hook timeout",
            "stdout": (exc.stdout or "")[-1000:],
            "stderr": (exc.stderr or "")[-1000:],
        }
    if result.returncode != 0:
        return {
            "status": "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "docs-lint produced invalid JSON",
            "stdout": result.stdout[-2000:],
        }


def build_hook_report(
    *,
    repo_root: Path,
    status: str,
    changed_docs: list[str],
    docs_lint: dict[str, Any] | None,
    message: str,
) -> dict[str, Any]:
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "producer": "h2t-core/post-git-commit-docs-lint",
        "produced_at": now,
        "repo_root": str(repo_root),
        "status": status,
        "summary": message,
        "findings": [],
        "safe_next_action": "Run docs-lint plan --root . if docs health warnings matter before merge",
        "evidence": {
            "hook": HOOK_NAME,
            "changed_docs": changed_docs,
            "docs_lint": docs_lint,
            "checked_at": now,
        },
    }


def write_report(repo_root: Path, report: dict[str, Any]) -> Path:
    out = repo_root / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


def hook_timeout_seconds() -> int:
    raw = os.environ.get("H2T_LINT_HOOK_TIMEOUT", "8")
    try:
        timeout = int(raw)
    except ValueError:
        return 8
    return max(1, min(timeout, 30))


def _load_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    repo_root = Path.cwd().resolve()
    payload = _load_payload()
    if payload and not is_git_commit_payload(payload):
        return 0

    changed_docs = changed_docs_from_head(repo_root)
    if not changed_docs:
        write_report(
            repo_root,
            build_hook_report(
                repo_root=repo_root,
                status="skipped",
                changed_docs=[],
                docs_lint=None,
                message="no docs markdown changed in latest commit",
            ),
        )
        return 0

    lint_script = find_docs_lint_script()
    if lint_script is None:
        write_report(
            repo_root,
            build_hook_report(
                repo_root=repo_root,
                status="error",
                changed_docs=changed_docs,
                docs_lint=None,
                message="docs-lint script not found",
            ),
        )
        return 0

    timeout = hook_timeout_seconds()
    docs_lint = run_docs_lint_doctor(repo_root, lint_script, timeout=timeout)
    status = "ok" if docs_lint.get("status") in {"ok", "warn"} else "error"
    write_report(
        repo_root,
        build_hook_report(
            repo_root=repo_root,
            status=status,
            changed_docs=changed_docs,
            docs_lint=docs_lint,
            message="docs-lint doctor completed",
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_post_git_commit_docs_lint.py -v
```

Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/post_git_commit_docs_lint.py tests/hooks/test_post_git_commit_docs_lint.py
git commit -m "feat(hooks): add post-git-commit docs-lint backend"
```

---

### Task 2: Add executable hook wrapper

**Files:**
- Create: `plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint`
- Modify: `tests/hooks/test_post_git_commit_docs_lint.py`

- [ ] **Step 1: Add wrapper existence test**

Append to `tests/hooks/test_post_git_commit_docs_lint.py`:

```python
def test_wrapper_exists_and_references_backend():
    wrapper = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint"
    text = wrapper.read_text(encoding="utf-8")
    assert "post_git_commit_docs_lint" in text
    assert "raise SystemExit" in text
```

- [ ] **Step 2: Run test and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_post_git_commit_docs_lint.py::test_wrapper_exists_and_references_backend -v
```

Expected: failure because wrapper does not exist.

- [ ] **Step 3: Create wrapper**

Create `plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint`:

```python
#!/usr/bin/env python3
"""Thin wrapper for post_git_commit_docs_lint.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import post_git_commit_docs_lint

if __name__ == "__main__":
    raise SystemExit(post_git_commit_docs_lint.main())
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_post_git_commit_docs_lint.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint tests/hooks/test_post_git_commit_docs_lint.py
git commit -m "feat(hooks): add post-git-commit docs-lint wrapper"
```

---

### Task 3: Install PostToolUse hook through scaffold-project

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Modify: `tests/scaffold/test_scaffold_steps.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/scaffold/test_scaffold_steps.py`:

```python
def _hook_commands(entries):
    return [
        command["command"]
        for entry in entries
        for command in entry.get("hooks", [])
        if command.get("type") == "command"
    ]


def test_install_hooks_has_posttooluse_git_commit_hook(tmp_path):
    """PostToolUse hook runs docs-lint after git commit."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    commands = _hook_commands(hooks)
    assert any("post-git-commit-docs-lint" in command for command in commands)


def test_install_hooks_posttooluse_matcher_targets_bash_git_commit(tmp_path):
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    matching = [
        entry for entry in hooks
        if any("post-git-commit-docs-lint" in command for command in _hook_commands([entry]))
    ]
    assert matching
    assert "Bash" in matching[0].get("matcher", "")
    assert "git commit" in matching[0].get("matcher", "")


def test_install_hooks_posttooluse_idempotent(tmp_path):
    install_hooks(tmp_path)
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    matching = [
        entry for entry in hooks
        if any("post-git-commit-docs-lint" in command for command in _hook_commands([entry]))
    ]
    assert len(matching) == 1


def test_install_hooks_ignores_lifecycle_report_cache(tmp_path):
    git_info = tmp_path / ".git" / "info"
    git_info.mkdir(parents=True)
    install_hooks(tmp_path)
    exclude = git_info / "exclude"
    assert ".h2t/lifecycle/*.json" in exclude.read_text(encoding="utf-8")
```

Also update the existing Stop hook tests in the same file to use `_hook_commands(...)`
instead of reading `h.get("command")` directly. The installed hook shape must match
Claude's real nested hook contract:

```python
stop_hooks = data.get("hooks", {}).get("Stop", [])
commands = _hook_commands(stop_hooks)
assert any("on-stop" in command for command in commands)
cmd = commands[0]
assert cmd.startswith("~")
assert "latest" in cmd
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -k "posttooluse" -v
```

Expected: failures because `install_hooks` only installs Stop hook.

- [ ] **Step 3: Update hook entries**

In `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`, replace `_HOOK_ENTRIES` with:

```python
_HOOK_ENTRIES = {
    "Stop": [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f"{_HOOK_BASE}/hooks-handlers/on-stop",
                }
            ],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Bash(git commit*)",
            "hooks": [
                {
                    "type": "command",
                    "command": f"{_HOOK_BASE}/hooks-handlers/post-git-commit-docs-lint",
                }
            ],
        }
    ],
}
```

Add this helper near `install_hooks`:

```python
def ensure_hook_report_cache_ignored(project_dir: Path) -> None:
    exclude = project_dir / ".git" / "info" / "exclude"
    if not exclude.parent.exists():
        return
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    line = ".h2t/lifecycle/*.json"
    if line not in existing.splitlines():
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        exclude.write_text(existing + suffix + line + "\n", encoding="utf-8")
```

Then call it at the end of `install_hooks`, before returning:

```python
    ensure_hook_report_cache_ignored(project_dir)
```

Replace the body of `install_hooks` with a nested-shape idempotent implementation:

```python
def _entry_commands(entry: dict) -> list[str]:
    return [
        command.get("command", "")
        for command in entry.get("hooks", [])
        if command.get("type") == "command"
    ]


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
            desired_commands = set(_entry_commands(entry))
            already_present = any(
                desired_commands.intersection(_entry_commands(existing_entry))
                for existing_entry in existing
            )
            if not already_present:
                existing.append(entry)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    ensure_hook_report_cache_ignored(project_dir)
    return {"status": "ok", "path": str(settings_path)}
```

- [ ] **Step 4: Run scaffold tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -v
```

Expected: all scaffold hook tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py
git commit -m "feat(scaffold-project): install post-git-commit docs-lint hook"
```

---

### Task 4: Deprecate gh-memory as a compatibility shim

**Files:**
- Modify: `plugins/h2t-dev/skills/gh-memory/SKILL.md`
- Modify: `plugins/h2t-dev/README.md`
- Create: `tests/lifecycle/test_gh_memory_deprecated.py`

- [ ] **Step 1: Write deprecation guard tests**

Create `tests/lifecycle/test_gh_memory_deprecated.py`:

```python
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_gh_memory_skill_is_explicitly_deprecated():
    text = (ROOT / "plugins/h2t-dev/skills/gh-memory/SKILL.md").read_text(encoding="utf-8")
    assert "status: deprecated" in text
    assert "compatibility shim" in text.lower()
    assert "h2t-core:session-start" in text
    assert "h2t-core:handoff" in text


def test_gh_memory_no_longer_promotes_persistent_agent_memory():
    text = (ROOT / "plugins/h2t-dev/skills/gh-memory/SKILL.md").read_text(encoding="utf-8")
    forbidden = [
        "This skill should be used when GitHub Issues are needed as persistent agent memory",
        "Purpose: Persistent cross-session memory",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_h2t_dev_readme_marks_gh_memory_deprecated():
    text = (ROOT / "plugins/h2t-dev/README.md").read_text(encoding="utf-8")
    assert "gh-memory" in text
    assert "deprecated" in text.lower()
    assert "session-start" in text
    assert "handoff" in text
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/lifecycle/test_gh_memory_deprecated.py -v
```

Expected: failures because SKILL/README still promote old memory behavior.

- [ ] **Step 3: Rewrite gh-memory frontmatter and intro**

In `plugins/h2t-dev/skills/gh-memory/SKILL.md`, replace the frontmatter and first body section with:

```markdown
---
name: h2t-dev:gh-memory
description: "Deprecated compatibility shim for old GitHub-Issues-as-memory workflows. Prefer h2t-core:session-start and h2t-core:handoff for session continuity; prefer project GitHub issues for real task state."
compatibility: "Claude Code. Requires: gh CLI authenticated to the target GitHub account."
status: deprecated
metadata:
  author: lichtpfad
  version: 1.0.1
---

# gh-memory — Deprecated Compatibility Shim

`gh-memory` is deprecated as agent memory.

Use instead:

- `h2t-core:session-start` for bounded session context.
- `h2t-core:handoff` for confirmed session summary and live GitHub what-remains.
- Project-local GitHub issues for task truth.
- POS later for accepted long-term session/project memory.

This skill remains only as a compatibility shim for old workflows that stored
agent tasks in `lichtpfad/DOR` issues. Do not use it for new Lifecycle OS work.
```

Keep the old command reference below this section under a heading:

```markdown
## Legacy Commands
```

- [ ] **Step 4: Update h2t-dev README**

In `plugins/h2t-dev/README.md`, replace:

```markdown
- **gh-memory** — GitHub Issues persistent memory
```

with:

```markdown
- **gh-memory** — deprecated compatibility shim; use `h2t-core:session-start` / `h2t-core:handoff` for continuity and project GitHub issues for task truth
```

- [ ] **Step 5: Run deprecation tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/lifecycle/test_gh_memory_deprecated.py -v
```

Expected: 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t-dev/skills/gh-memory/SKILL.md plugins/h2t-dev/README.md tests/lifecycle/test_gh_memory_deprecated.py
git commit -m "docs(gh-memory): mark as deprecated compatibility shim"
```

---

### Task 5: Version bumps and lifecycle status sync

**Files:**
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`
- Modify: `plugins/h2t-dev/.claude-plugin/plugin.json`
- Modify: `docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md`

- [ ] **Step 1: Bump h2t-core patch version**

In `plugins/h2t-core/.claude-plugin/plugin.json`, change:

```json
"version": "3.2.1"
```

to:

```json
"version": "3.2.2"
```

- [ ] **Step 2: Bump h2t-dev patch version**

In `plugins/h2t-dev/.claude-plugin/plugin.json`, change:

```json
"version": "1.0.8"
```

to:

```json
"version": "1.0.9"
```

- [ ] **Step 3: Update lifecycle spec issue mapping**

In `docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md`, change the #197 row from:

```markdown
| #197 | lifecycle hooks and `gh-memory` deprecation | open |
```

to:

```markdown
| #197 | lifecycle hooks and `gh-memory` deprecation | implemented by PR for this plan |
```

Do not mark #196 here unless #196 is already merged.

- [ ] **Step 4: Run metadata/deprecation tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_post_git_commit_docs_lint.py tests/scaffold/test_scaffold_steps.py tests/lifecycle/test_gh_memory_deprecated.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/.claude-plugin/plugin.json plugins/h2t-dev/.claude-plugin/plugin.json docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md
git commit -m "docs(lifecycle): sync #197 hook and gh-memory status"
```

---

### Task 6: Dogfood acceptance

**Files:**
- No source files unless fixes are needed.

- [ ] **Step 1: Run targeted tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/ tests/scaffold/test_scaffold_steps.py tests/lifecycle/test_gh_memory_deprecated.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run docs-lint on changed docs**

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/dev/h2t-skills --json
```

Expected: valid JSON; warnings are acceptable, crashes are not.

- [ ] **Step 3: Manual hook backend smoke without changing repo state**

First ensure the local hook cache path is ignored in this repo:

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "import sys; from pathlib import Path; sys.path.insert(0, 'plugins/h2t-core/skills/scaffold-project/scripts'); import scaffold_project as s; s.ensure_hook_report_cache_ignored(Path.cwd())"
```

Run the hook backend directly. It should write a non-blocking report based on the current HEAD:

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-core/hooks-handlers/post_git_commit_docs_lint.py
```

Expected:

- exits 0;
- writes `.h2t/lifecycle/post-git-commit-docs-lint.json`;
- report `status` is `ok`, `skipped`, or `error`; hook must not fail the session.
- the hook report must not make the repo dirty after scaffold installed the local exclude.

Then verify the report is ignored:

```bash
git status --short .h2t/lifecycle/post-git-commit-docs-lint.json
```

Expected: no output.

- [ ] **Step 4: Verify no active docs-index/gh-memory promotion**

```bash
rg -n "GitHub Issues persistent memory|Purpose: Persistent cross-session memory|docs-index as user-facing|docs-index/scripts/index.py" plugins/h2t-dev plugins/h2t-core
```

Expected: no matches that promote deprecated flows.

- [ ] **Step 5: Commit acceptance evidence**

```bash
git commit --allow-empty -m "test(lifecycle): dogfood #197 hooks and gh-memory deprecation"
```

---

## Checklist Summary

- [ ] Task 1: PostToolUse git commit docs-lint hook backend
- [ ] Task 2: executable hook wrapper
- [ ] Task 3: scaffold-project installs PostToolUse hook
- [ ] Task 4: gh-memory deprecated as compatibility shim
- [ ] Task 5: patch versions + lifecycle spec status sync
- [ ] Task 6: dogfood acceptance

## Self-Review

Spec coverage:

- Hook `PostToolUse(git commit)` docs-lint quick check: Tasks 1-3.
- Non-blocking, timeout-bounded hook behavior: Task 1.
- Hook reports instead of long hook output: Task 1.
- Hook report uses the shared `h2t_lifecycle_report/v0.1` family instead of inventing a hook-only schema: Task 1.
- Hook report cache does not make repositories dirty after scaffold installation: Task 3 and Task 6.
- Stop hook: owned by #196; #197 depends on that repair and does not duplicate it.
- `gh-memory` deprecated in metadata/routing/docs: Task 4.
- `docs-index` rewrite excluded: no task touches docs-index.

Known deliberate deferrals:

- POS event emission.
- Global hook rollout to existing repos.
- Scheduled project-audit.
- Automated migration of old `gh-memory` issues.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | Not required for hook/deprecation maintenance plan |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not run | Not requested |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | patched | 4 findings applied: nested Claude hook shape, lifecycle report schema, dirty-state guard, extra payload tests |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not applicable | No UI changes |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | Not required before implementation |

- **UNRESOLVED:** 0 for this review pass.
- **VERDICT:** ENG PATCHED — ready for #196 merge, then implementation.
