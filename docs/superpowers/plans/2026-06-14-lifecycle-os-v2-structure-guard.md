---
title: "Lifecycle OS v2 — Structure Guard Implementation Plan"
status: "draft"
date: "2026-06-14"
milestone: ""
issue: ""
---
# Lifecycle OS v2 — Structure Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `structure_guard.py` — PreToolUse hook that blocks agents from creating files with forbidden names or in unregistered directories, distributed via h2t-core plugin.

**Architecture:** Python hook script reads `.h2t/structure.yaml` from CWD (per-repo config), checks the file path from the hook payload, and exits 2 (block), 1 (warn), or 0 (allow). Distributed via `plugins/h2t-core/hooks/hooks.json` — active in all sessions after `/plugin marketplace update lichtpfad` + `/reload-plugins`. scaffold_project.py updated to generate `.h2t/structure.yaml` for new repos.

**Tech Stack:** Python 3.11+ stdlib only (no external deps — hook runs outside venv). YAML parsed with a minimal custom parser. Tests via pytest + importlib.

**Spec:** `docs/superpowers/specs/2026-06-14-lifecycle-os-v2-design.md`

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `plugins/h2t-core/hooks-handlers/structure_guard.py` | Core hook logic — parse payload, read config, check rules, exit |
| Create | `plugins/h2t-core/hooks-handlers/structure-guard` | Bash wrapper — called from hooks.json, delegates to .py |
| Modify | `plugins/h2t-core/hooks/hooks.json` | Register PreToolUse hook for Write/Edit/MultiEdit |
| Create | `.h2t/structure.yaml` | Per-repo config for h2t-skills (allowlist + forbidden patterns) |
| Create | `tests/hooks/__init__.py` | Package marker |
| Create | `tests/hooks/test_structure_guard.py` | Unit tests for hook logic |
| Modify | `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | Generate `.h2t/structure.yaml` for new repos |
| Modify | `plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py` | Test structure.yaml generation |

---

### Task 1: structure_guard.py — core hook logic (TDD)

**Files:**
- Create: `tests/hooks/__init__.py`
- Create: `tests/hooks/test_structure_guard.py`
- Create: `plugins/h2t-core/hooks-handlers/structure_guard.py`

- [ ] **Step 1.1: Create tests/hooks/__init__.py**

```python
```
(empty file)

- [ ] **Step 1.2: Write failing tests**

Create `tests/hooks/test_structure_guard.py`:

```python
"""Tests for structure_guard.py PreToolUse hook."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_guard():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "structure_guard.py"
    spec = importlib.util.spec_from_file_location("structure_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ── config fixture ──────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "allowed_root_dirs": ["plugins/", "docs/", "h2t_ops/", "lib/", "scripts/", "tests/"],
    "forbidden_patterns": ["tmp_*", "*_tmp.*", "*_v2.*", "*_copy.*", "*_backup.*"],
    "plan_dirs": [
        {"path": "docs/superpowers/plans/", "pattern": r"^\d{4}-\d{2}-\d{2}-.+\.md$"},
    ],
}


# ── _parse_yaml ──────────────────────────────────────────────────────────────

def test_parse_yaml_allowed_root_dirs():
    guard = _load_guard()
    yaml_text = (
        "allowed_root_dirs:\n"
        "  - plugins/\n"
        "  - docs/\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert result["allowed_root_dirs"] == ["plugins/", "docs/"]


def test_parse_yaml_forbidden_patterns():
    guard = _load_guard()
    yaml_text = (
        "forbidden_patterns:\n"
        '  - "tmp_*"\n'
        '  - "*_v2.*"\n'
    )
    result = guard._parse_yaml(yaml_text)
    assert result["forbidden_patterns"] == ["tmp_*", "*_v2.*"]


def test_parse_yaml_plan_dirs():
    guard = _load_guard()
    yaml_text = (
        "plan_dirs:\n"
        "  - path: docs/superpowers/plans/\n"
        r'    pattern: "^\d{4}-\d{2}-\d{2}-.+\.md$"' + "\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert len(result["plan_dirs"]) == 1
    assert result["plan_dirs"][0]["path"] == "docs/superpowers/plans/"
    assert r"\d{4}" in result["plan_dirs"][0]["pattern"]


# ── check_file ───────────────────────────────────────────────────────────────

def test_forbidden_tmp_prefix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("tmp_foo.txt", SAMPLE_CONFIG)
    assert code == 2
    assert "tmp_*" in msg


def test_forbidden_v2_suffix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/something_v2.py", SAMPLE_CONFIG)
    assert code == 2


def test_plan_dir_bad_name_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/foo.md", SAMPLE_CONFIG)
    assert code == 2
    assert "YYYY-MM-DD" in msg or "pattern" in msg.lower()


def test_plan_dir_good_name_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/2026-06-14-foo.md", SAMPLE_CONFIG)
    assert code == 0


def test_known_root_dir_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/foo.py", SAMPLE_CONFIG)
    assert code == 0


def test_unknown_root_dir_warns():
    guard = _load_guard()
    code, msg = guard.check_file("random_new_dir/foo.py", SAMPLE_CONFIG)
    assert code == 1
    assert "random_new_dir" in msg or "allowlist" in msg.lower()


def test_no_config_returns_zero(tmp_path):
    guard = _load_guard()
    config = guard.load_config(tmp_path)
    assert config is None


def test_unknown_tool_name_returns_zero():
    guard = _load_guard()
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    # check_file not even called — main() returns 0 for non-Write tools
    # Test via the filter logic directly
    assert guard._is_write_tool(payload["tool_name"]) is False


def test_write_tool_recognized():
    guard = _load_guard()
    for name in ("Write", "Edit", "MultiEdit"):
        assert guard._is_write_tool(name) is True
```

- [ ] **Step 1.3: Run tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py -v
```

Expected: `ModuleNotFoundError` or import errors — structure_guard.py doesn't exist yet.

- [ ] **Step 1.4: Implement structure_guard.py**

Create `plugins/h2t-core/hooks-handlers/structure_guard.py`:

```python
#!/usr/bin/env python3
"""PreToolUse hook: enforce file naming conventions from .h2t/structure.yaml.

Exit codes (process):
  0 — allow (includes warn cases — Claude Code exit 1 behavior is undefined)
  2 — block (prevents Write/Edit/MultiEdit)

check_file() internal codes:
  0 — allow silently
  1 — warn (main() prints to stderr, exits 0)
  2 — block (main() prints to stderr, exits 2)

Fail-open: if .h2t/structure.yaml is missing or unreadable → EXIT 0.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

_STRUCTURE_FILE = ".h2t/structure.yaml"
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def _is_write_tool(tool_name: str) -> bool:
    return tool_name in _WRITE_TOOLS


def _parse_yaml(text: str) -> dict:
    """Minimal YAML parser for structure.yaml format (stdlib only, no PyYAML)."""
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None
    current_dict: dict | None = None

    for line in text.splitlines():
        raw = line.rstrip()
        if not raw or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())

        if indent == 0 and ":" in raw:
            key = raw.split(":", 1)[0].strip()
            current_key = key
            result[key] = []
            current_list = result[key]
            current_dict = None

        elif indent == 2 and raw.lstrip().startswith("- ") and current_list is not None:
            content = raw.lstrip()[2:].strip()
            if ":" in content:
                k, v = content.split(":", 1)
                current_dict = {k.strip(): v.strip().strip('"').strip("'")}
                current_list.append(current_dict)
            else:
                current_dict = None
                current_list.append(content.strip('"').strip("'"))

        elif indent == 4 and current_dict is not None and ":" in raw:
            k, v = raw.strip().split(":", 1)
            current_dict[k.strip()] = v.strip().strip('"').strip("'")

    return result


def load_config(repo_root: Path) -> dict | None:
    config_path = repo_root / _STRUCTURE_FILE
    if not config_path.exists():
        return None
    try:
        text = config_path.read_text(encoding="utf-8")
        return _parse_yaml(text)
    except Exception:
        return None


def check_file(file_path: str, config: dict) -> tuple[int, str]:
    """Return (exit_code, message). 0=allow, 1=warn, 2=block."""
    norm = file_path.replace("\\", "/")
    name = Path(norm).name

    # 1. Forbidden name patterns
    for pattern in config.get("forbidden_patterns", []):
        if fnmatch.fnmatch(name, pattern):
            return 2, (
                f"BLOCKED: запрещённый паттерн имени {pattern!r}. "
                f"Переименуйте файл. Файл: {norm!r}"
            )

    # 2. Plan directory naming rules
    for plan_dir in config.get("plan_dirs", []):
        dir_path = plan_dir.get("path", "")
        pattern = plan_dir.get("pattern", "")
        if norm.startswith(dir_path):
            if not re.match(pattern, name):
                return 2, (
                    f"BLOCKED: файл в {dir_path!r} должен соответствовать паттерну "
                    f"YYYY-MM-DD-<name>.md. Получено: {name!r}"
                )
            return 0, ""

    # 3. Unknown root directory
    allowed = config.get("allowed_root_dirs", [])
    if allowed and "/" in norm:
        root = norm.split("/")[0]
        allowed_roots = {a.rstrip("/") for a in allowed}
        if root not in allowed_roots:
            allowed_list = ", ".join(sorted(allowed_roots))
            return 1, (
                f"WARNING: директория {root!r} не в allowlist. "
                f"Допустимые: {allowed_list}. "
                f"Создаёте новую директорию? Добавьте в .h2t/structure.yaml."
            )

    return 0, ""


def _load_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def main() -> int:
    payload = _load_payload()

    tool_name = payload.get("tool_name", "")
    if not _is_write_tool(tool_name):
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    repo_root = Path.cwd().resolve()
    config = load_config(repo_root)
    if config is None:
        return 0  # fail open — no .h2t/structure.yaml

    # Normalise to repo-relative path
    try:
        rel = Path(file_path).resolve().relative_to(repo_root)
        norm = str(rel).replace("\\", "/")
    except ValueError:
        return 0  # outside repo — not our concern

    exit_code, message = check_file(norm, config)

    if message:
        print(message, file=sys.stderr)

    # check_file code 1 = warn intent: print to stderr but EXIT 0
    # (Claude Code exit 1 semantics in PreToolUse are undefined — safer to exit 0)
    return 2 if exit_code == 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 1.5: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 1.6: Commit**

```
git add plugins/h2t-core/hooks-handlers/structure_guard.py tests/hooks/__init__.py tests/hooks/test_structure_guard.py
git commit -m "feat(h2t-core): add structure_guard.py PreToolUse hook — enforce naming conventions"
```

---

### Task 2: Bash wrapper + hooks.json registration

**Files:**
- Create: `plugins/h2t-core/hooks-handlers/structure-guard`
- Modify: `plugins/h2t-core/hooks/hooks.json`

- [ ] **Step 2.1: Write failing test for hooks.json registration**

Add to `tests/hooks/test_structure_guard.py`:

```python
def test_hooks_json_has_structure_guard_entry():
    import json as _json
    hooks_path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks" / "hooks.json"
    data = _json.loads(hooks_path.read_text(encoding="utf-8"))
    pre_tool = data.get("hooks", {}).get("PreToolUse", [])
    commands = [
        hook["command"]
        for entry in pre_tool
        for hook in entry.get("hooks", [])
        if hook.get("type") == "command"
    ]
    assert any("structure-guard" in cmd for cmd in commands), (
        f"structure-guard not found in PreToolUse hooks. Commands: {commands}"
    )
```

- [ ] **Step 2.2: Run new test to confirm it fails**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py::test_hooks_json_has_structure_guard_entry -v
```

Expected: FAIL — structure-guard not in hooks.json yet.

- [ ] **Step 2.3: Create bash wrapper**

Create `plugins/h2t-core/hooks-handlers/structure-guard` (no extension, executable):

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$SCRIPT_DIR/structure_guard.py"
```

- [ ] **Step 2.4: Make wrapper executable (bash)**

```bash
chmod +x plugins/h2t-core/hooks-handlers/structure-guard
```

On Windows this is a no-op but ensures the script is marked executable in git:
```
git update-index --chmod=+x plugins/h2t-core/hooks-handlers/structure-guard
```

- [ ] **Step 2.5: Add PreToolUse entry to hooks.json**

Current `plugins/h2t-core/hooks/hooks.json`:
```json
{
  "hooks": {
    "SessionStart": [...],
    "PreToolUse": [
      {
        "matcher": "Skill",
        "hooks": [...]
      }
    ]
  }
}
```

Add the structure-guard entry to `PreToolUse`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/inject-h2t-context\""
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/gather-on-skill\""
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/structure-guard\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2.6: Run test to confirm it passes**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py -v
```

Expected: all tests PASS (including the new hooks.json test).

- [ ] **Step 2.7: Commit**

```
git add plugins/h2t-core/hooks-handlers/structure-guard plugins/h2t-core/hooks/hooks.json
git commit -m "feat(h2t-core): register structure-guard as PreToolUse hook in hooks.json"
```

---

### Task 3: .h2t/structure.yaml for h2t-skills repo

**Files:**
- Create: `.h2t/structure.yaml`

- [ ] **Step 3.1: Write failing integration test**

Add to `tests/hooks/test_structure_guard.py`:

```python
def test_h2t_structure_yaml_exists():
    repo_root = Path(__file__).parents[2]
    structure_yaml = repo_root / ".h2t" / "structure.yaml"
    assert structure_yaml.exists(), ".h2t/structure.yaml not found in repo root"


def test_h2t_structure_yaml_is_valid():
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    assert config is not None
    assert "allowed_root_dirs" in config
    assert "forbidden_patterns" in config
    assert len(config["allowed_root_dirs"]) >= 4
    assert "tmp_*" in config["forbidden_patterns"]


def test_h2t_structure_yaml_blocks_tmp(tmp_path):
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("tmp_foo.txt", config)
    assert code == 2


def test_h2t_structure_yaml_blocks_bad_plan_name(tmp_path):
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("docs/superpowers/plans/my-plan.md", config)
    assert code == 2


def test_h2t_structure_yaml_allows_dated_plan():
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("docs/superpowers/plans/2026-06-14-my-plan.md", config)
    assert code == 0
```

- [ ] **Step 3.2: Run new tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py -k "h2t_structure" -v
```

Expected: FAIL — `.h2t/structure.yaml` doesn't exist.

- [ ] **Step 3.3: Create .h2t/structure.yaml**

Create `.h2t/structure.yaml` in the h2t-skills repo root:

```yaml
# Structure guard configuration for h2t-skills
# Used by plugins/h2t-core/hooks-handlers/structure_guard.py

allowed_root_dirs:
  - plugins/
  - docs/
  - h2t_ops/
  - lib/
  - scripts/
  - tests/
  - .h2t/
  - .claude/

forbidden_patterns:
  - "tmp_*"
  - "*_tmp.*"
  - "*_v2.*"
  - "*_copy.*"
  - "*_backup.*"

plan_dirs:
  - path: "docs/superpowers/plans/"
    pattern: "^\d{4}-\d{2}-\d{2}-.+\.md$"
```

- [ ] **Step 3.4: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/hooks/test_structure_guard.py -v
```

Expected: all tests PASS.

- [ ] **Step 3.5: Commit**

```
git add .h2t/structure.yaml tests/hooks/test_structure_guard.py
git commit -m "feat(h2t-skills): add .h2t/structure.yaml — per-repo structure guard config"
```

---

### Task 4: scaffold_project.py — auto-generate .h2t/structure.yaml

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py`

- [ ] **Step 4.1: Write failing test**

Add to `plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py`:

```python
def test_create_generates_structure_yaml(tmp_path):
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    structure_yaml = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    assert structure_yaml.exists(), f"Expected .h2t/structure.yaml at {structure_yaml}"
    content = structure_yaml.read_text(encoding="utf-8")
    assert "allowed_root_dirs" in content
    assert "forbidden_patterns" in content
    assert "tmp_*" in content


def test_merge_generates_structure_yaml_if_missing(tmp_path):
    (tmp_path / "myproj").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    structure_yaml = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    assert structure_yaml.exists()


def test_structure_yaml_idempotent_on_merge(tmp_path):
    # First scaffold
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path))
    # Write custom content
    yaml_path = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    original = yaml_path.read_text(encoding="utf-8")
    # Second merge — should not overwrite
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert yaml_path.read_text(encoding="utf-8") == original
```

- [ ] **Step 4.2: Run new tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py -k "structure_yaml" -v
```

Expected: FAIL — scaffold doesn't generate `.h2t/structure.yaml` yet.

- [ ] **Step 4.3: Add generate_structure_yaml function to scaffold_project.py**

Find the section just before `def cmd_create` (around line 176 in the original). Add:

```python
_STRUCTURE_YAML_TEMPLATE = """\
# Structure guard configuration — managed by h2t-core:scaffold-project
# Used by plugins/h2t-core/hooks-handlers/structure_guard.py

allowed_root_dirs:
  - src/
  - tests/
  - docs/
  - scripts/
  - .h2t/
  - .claude/

forbidden_patterns:
  - "tmp_*"
  - "*_tmp.*"
  - "*_v2.*"
  - "*_copy.*"
  - "*_backup.*"

plan_dirs:
  - path: "docs/superpowers/plans/"
    pattern: "^\\d{4}-\\d{2}-\\d{2}-.+\\.md$"
"""


def write_structure_yaml(project_dir: Path) -> bool:
    """Write .h2t/structure.yaml if it doesn't exist. Returns True if written."""
    yaml_path = project_dir / ".h2t" / "structure.yaml"
    if yaml_path.exists():
        return False
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(_STRUCTURE_YAML_TEMPLATE, encoding="utf-8")
    return True
```

- [ ] **Step 4.4: Call write_structure_yaml in cmd_create**

Find the section in `cmd_create` after directories are created (around line 220, after the `.gitignore` block). Add the call right before `if is_git:`:

```python
    # Generate .h2t/structure.yaml (idempotent — skip if exists)
    if write_structure_yaml(project_dir):
        actions.append("Created .h2t/structure.yaml")
        if is_git:
            created_files.append(".h2t/structure.yaml")
```

Place this BEFORE the existing `if is_git:` block that handles the initial commit.

- [ ] **Step 4.5: Run tests to confirm they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py -v
```

Expected: all tests PASS (including old and new ones).

- [ ] **Step 4.6: Run full test suite to confirm no regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/ plugins/h2t-core/ -x -q
```

Expected: all tests PASS.

- [ ] **Step 4.7: Commit**

```
git add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py
git commit -m "feat(scaffold): auto-generate .h2t/structure.yaml in new repos"
```

---

### Task 5: Deploy + smoke test

- [ ] **Step 5.1: Push to main**

```
git push origin main
```

- [ ] **Step 5.2: Update plugin in Claude Code session**

In Claude Code terminal:
```
/plugin marketplace update lichtpfad
```
Then:
```
/reload-plugins
```

- [ ] **Step 5.3: Manual smoke test — verify hook fires**

In a Claude Code session with h2t-skills as working dir, ask Claude to:
> "Write a file called `tmp_test.txt` with content 'hello'"

Expected: Claude Code blocks the Write tool call. Claude sees:
```
BLOCKED: запрещённый паттерн имени 'tmp_*'. Переименуйте файл. Файл: 'tmp_test.txt'
```

- [ ] **Step 5.4: Verify fail-open works**

In a repo WITHOUT `.h2t/structure.yaml`, verify Write tool is not blocked (hook exits 0).

- [ ] **Step 5.5: Bump plugin version**

```
python scripts/bump_plugin.py h2t-core patch
```

Then push:
```
git push origin main
```

---

## What this plan does NOT cover

- QMD bootstrap (`qmd collection add`, `qmd embed`) — one-time manual setup, no TDD
- Graphify bootstrap (`graphify install`, `graphify .`) — one-time manual setup, no TDD
- Session-start integration (querying QMD/Graphify) — separate plan after bootstrap
- Monthly review automation — separate plan
- Exit code 1 undefined in PreToolUse — resolved: warn cases use exit 0 + stderr (see D1)

---

## GSTACK REVIEW REPORT

| Runs | Status | Findings |
|---|---|---|
| Architecture | ✅ | D1 resolved: exit code 1 → exit 0 + stderr для warn cases |
| Code Quality | ✅ | `main()` updated: `return 2 if exit_code == 2 else 0` |
| Tests | ✅ | 12 unit tests + 5 integration tests покрывают все 6 сценариев из спека |
| Performance | ✅ | load_config: disk read ~0.1ms per hook call, acceptable |
| Prior Learnings | ✅ | is_git-guard-dead-code applied: write_structure_yaml() вне if is_git guard |

**VERDICT:** план готов к реализации. Единственный риск снят: exit code 1 заменён на exit 0 + stderr для warn-случаев. Все 5 tasks реализуемы в одном PR.

NO UNRESOLVED DECISIONS
