# h2t gather CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-skill `gather.py` scripts with a single `h2t gather <skill>` CLI command, installed via `uv pip install -e .` in `~/.h2t/venv`.

**Architecture:** Add `pyproject.toml` to repo root making `lib/` an installable package with a `h2t` entry point. Create `lib/cli/main.py` as the CLI router that calls existing `lib/gather/*` modules. Rewrite `gather-on-skill` hook to use `h2t gather $skill --cwd $cwd` — hook shrinks from ~60 lines to ~25. Per-skill `gather.py` script is kept but thinned to a one-liner fallback for backward compat.

**Tech Stack:** Python 3.11, setuptools (already in venv), uv (cross-platform), existing `lib/gather/*` modules.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Create | Package definition, `h2t` entry point |
| `lib/cli/__init__.py` | Create | Package marker |
| `lib/cli/main.py` | Create | `h2t gather <skill>` CLI router |
| `lib/cli/test_main.py` | Create | CLI unit tests |
| `plugins/h2t-core/hooks-handlers/gather-on-skill` | Modify | Use `h2t gather` instead of per-skill script |
| `plugins/h2t-core/skills/setup/SKILL.md` | Modify | Add `uv pip install -e .` step after pip install |
| `plugins/h2t-core/scripts/update-plugin.sh` | Modify | Copy `pyproject.toml` into cache root |

---

## Task 1: pyproject.toml — make lib/ installable

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1.1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=70"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "h2t"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
h2t = "lib.cli.main:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["lib*"]
```

- [ ] **Step 1.2: Verify package structure looks correct**

```bash
cd C:/dev/claude-agent-skills
python -c "import setuptools; print(setuptools.find_packages())"
```

Expected output includes: `['lib', 'lib.activity', 'lib.cli', 'lib.eval', 'lib.gather']`

(lib.cli doesn't exist yet — that's fine, it will be created in Task 2)

- [ ] **Step 1.3: Install in editable mode**

```bash
~/.h2t/venv/Scripts/python.exe -m pip install -e . --quiet
# On Mac/Linux:
# ~/.h2t/venv/bin/python -m pip install -e . --quiet
```

Expected: installs without errors, no package conflicts.

- [ ] **Step 1.4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pyproject.toml — make lib/ installable as h2t package"
```

---

## Task 2: lib/cli/main.py — CLI router

**Files:**
- Create: `lib/cli/__init__.py`
- Create: `lib/cli/main.py`

- [ ] **Step 2.1: Create package marker**

```python
# lib/cli/__init__.py
"""h2t CLI package."""
```

- [ ] **Step 2.2: Write failing test first**

```python
# lib/cli/test_main.py
"""Tests for h2t gather CLI."""
import json
import subprocess
import sys
from pathlib import Path

VENV_PYTHON = Path.home() / ".h2t" / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path.home() / ".h2t" / "venv" / "bin" / "python"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_h2t(*args):
    """Run h2t CLI and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", "lib.cli.main", *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    return result.returncode, result.stdout, result.stderr


def test_gather_session_start_returns_json():
    code, out, err = run_h2t("gather", "session-start", "--cwd", str(REPO_ROOT))
    assert code == 0, f"Expected exit 0, got {code}. stderr: {err}"
    data = json.loads(out)
    assert "project" in data
    assert "git" in data


def test_gather_with_format_briefing_includes_briefing():
    code, out, err = run_h2t("gather", "session-start", "--cwd", str(REPO_ROOT), "--format-briefing")
    assert code == 0, f"Expected exit 0. stderr: {err}"
    data = json.loads(out)
    assert "_briefing" in data
    assert len(data["_briefing"]) > 0


def test_gather_handoff_returns_json():
    code, out, err = run_h2t("gather", "handoff", "--cwd", str(REPO_ROOT))
    assert code == 0, f"Expected exit 0. stderr: {err}"
    data = json.loads(out)
    assert "project" in data
    assert "git" in data


def test_unknown_subcommand_exits_nonzero():
    code, out, err = run_h2t("unknowncommand")
    assert code != 0


def test_gather_missing_skill_exits_nonzero():
    code, out, err = run_h2t("gather")
    assert code != 0
```

- [ ] **Step 2.3: Run tests — expect FAIL**

```bash
cd C:/dev/claude-agent-skills
~/.h2t/venv/Scripts/python.exe -m pytest lib/cli/test_main.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `lib.cli.main` doesn't exist yet.

- [ ] **Step 2.4: Create lib/cli/main.py**

```python
#!/usr/bin/env python3
"""h2t CLI — unified entry point.

Usage:
    h2t gather session-start [--cwd PATH] [--format-briefing]
    h2t gather handoff [--cwd PATH]
    h2t gather init-project [--cwd PATH]
"""
import argparse
import sys
import time
from pathlib import Path

# Ensure lib/ is importable when run as -m lib.cli.main (dev mode)
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _run_gather(skill: str, cwd: str, format_briefing: bool) -> None:
    """Execute gather for the given skill, print JSON to stdout."""
    from lib.gather import output_json
    from lib.gather.project import identify_project
    from lib.gather.user import gather_user_context
    from lib.gather.git import gather_git
    from lib.gather.github import gather_github
    from lib.gather.stack import detect_stack
    from lib.gather.sessions import find_session_files, get_machine_name
    from lib.gather.briefing import format_briefing as make_briefing
    from lib.eval.session import SkillEval

    start = time.monotonic()
    sources_used: list[str] = []
    sources_failed: list[str] = []

    project = identify_project(cwd)
    sources_used.append("project")

    user = gather_user_context(domain=project.get("domain"))

    git_data = {}
    try:
        git_data = gather_git(cwd)
        sources_used.append("git")
    except Exception:
        sources_failed.append("git")

    github_data = {}
    try:
        owner_repo = git_data.get("owner_repo") or project.get("github")
        if owner_repo:
            github_data = gather_github(owner_repo)
            sources_used.append("github")
    except Exception:
        sources_failed.append("github")

    stack = {}
    try:
        stack = detect_stack(cwd)
    except Exception:
        pass

    machine = get_machine_name()
    sessions = []
    try:
        sessions = find_session_files(project.get("id", ""), machine)
    except Exception:
        pass

    elapsed_ms = int((time.monotonic() - start) * 1000)

    slug_template = (
        f"{project.get('id', 'unknown')}-gather-frame-{{task}}"
        f"-{time.strftime('%Y-%m-%d-%H%M')}"
    )

    result: dict = {
        "project": project,
        "git": git_data,
        "github": github_data,
        "stack": stack,
        "sessions": sessions,
        "machine": machine,
        "user": user,
        "session_id": "",
        "_meta": {
            "sources_used": sources_used,
            "sources_failed": sources_failed,
            "gather_ms": elapsed_ms,
            "slug_template": slug_template,
            "project": project,
            "user": user,
            "sessions": sessions,
            "machine": machine,
            "session_id": "",
        },
    }

    if format_briefing:
        try:
            result["_briefing"] = make_briefing(result)
        except Exception as e:
            result["_briefing"] = f"BRIEFING_ERROR: {e}"

    output_json(result)


def main() -> None:
    parser = argparse.ArgumentParser(prog="h2t", description="h2t CLI tools")
    sub = parser.add_subparsers(dest="command")

    gather_p = sub.add_parser("gather", help="Collect context for a skill")
    gather_p.add_argument("skill", nargs="?", help="Skill name: session-start, handoff, ...")
    gather_p.add_argument("--cwd", default=".", help="Working directory (default: .)")
    gather_p.add_argument("--format-briefing", action="store_true",
                          help="Include _briefing field in output")

    args = parser.parse_args()

    if args.command == "gather":
        if not args.skill:
            gather_p.print_help()
            sys.exit(1)
        _run_gather(skill=args.skill, cwd=args.cwd, format_briefing=args.format_briefing)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.5: Run tests — expect PASS**

```bash
cd C:/dev/claude-agent-skills
~/.h2t/venv/Scripts/python.exe -m pytest lib/cli/test_main.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 2.6: Verify h2t CLI works end-to-end**

```bash
~/.h2t/venv/Scripts/python.exe -m lib.cli.main gather session-start --cwd . --format-briefing 2>&1 | python -c "import json,sys; d=json.load(sys.stdin); print('project:', d['project']['id']); print('briefing:', bool(d.get('_briefing')))"
```

Expected:
```
project: agent-skills
briefing: True
```

- [ ] **Step 2.7: Commit**

```bash
git add lib/cli/__init__.py lib/cli/main.py lib/cli/test_main.py
git commit -m "feat(cli): add h2t gather CLI router (Task 2)"
```

---

## Task 3: Rewrite gather-on-skill hook

**Files:**
- Modify: `plugins/h2t-core/hooks-handlers/gather-on-skill`

- [ ] **Step 3.1: Verify h2t binary is available after install**

```bash
~/.h2t/venv/Scripts/python.exe -c "import lib.cli.main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3.2: Rewrite the hook**

Replace the entire content of `plugins/h2t-core/hooks-handlers/gather-on-skill`:

```bash
#!/usr/bin/env bash
# PreToolUse: gather context when h2t-core session skills are invoked.
set -euo pipefail

input=$(cat)
skill=$(echo "$input" | jq -r '.tool_input.skill // ""')
cwd=$(echo "$input" | jq -r '.cwd // "."')

# Only fire for h2t-core session skills
case "$skill" in
  *session-start*|*handoff*|*init-project*) ;;
  *) exit 0 ;;
esac

# Deduplicate: skip if same skill was gathered in the last 30s
LOCK_KEY=$(echo "$skill" | tr '/:' '__')
LOCK_FILE="${TMPDIR:-/tmp}/h2t_gather_${LOCK_KEY}.lock"
NOW=$(date +%s)
if [ -f "$LOCK_FILE" ]; then
  LOCK_TIME=$(cat "$LOCK_FILE" 2>/dev/null || echo 0)
  AGE=$(( NOW - LOCK_TIME )) || AGE=99
  if [ "$AGE" -lt 30 ]; then
    exit 0
  fi
fi
echo "$NOW" > "$LOCK_FILE"

# Find Python
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"

if [ -z "$H2T_PYTHON" ]; then
  echo '{"systemMessage": "GATHER_ERROR: h2t venv not found. Run /h2t-core:setup"}'
  exit 0
fi

# Build args
ARGS="$skill --cwd $cwd"
[[ "$skill" == *session-start* ]] && ARGS="$ARGS --format-briefing"

# Run gather CLI
RESULT=$("$H2T_PYTHON" -m lib.cli.main gather $ARGS 2>/dev/null) || true

if [ -z "$RESULT" ]; then
  echo '{"systemMessage": "GATHER_ERROR: h2t gather returned no output. Run /h2t-core:setup to reinstall."}'
  exit 0
fi

# Format output for Claude systemMessage injection
BRIEFING=$("$H2T_PYTHON" -c "
import json, sys
data = json.load(sys.stdin)
b = data.get('_briefing', '')
m = json.dumps(data.get('_meta', {}))
print(f'BRIEFING:\n{b}\n\nGATHER_META: {m}')
" <<< "$RESULT" 2>/dev/null) || BRIEFING="GATHER_DATA: $RESULT"

printf '{"systemMessage": "%s"}' "$("$H2T_PYTHON" -c "
import sys
print(sys.stdin.read()
  .replace('\\\\', '\\\\\\\\')
  .replace('\"', '\\\\\"')
  .replace(chr(10), '\\\\n')
)" <<< "$BRIEFING")"
```

- [ ] **Step 3.3: Test hook manually**

```bash
echo '{"tool_name":"Skill","tool_input":{"skill":"h2t-core:session-start"},"cwd":"C:/dev/claude-agent-skills"}' \
  | bash plugins/h2t-core/hooks-handlers/gather-on-skill \
  | python -c "import json,sys; d=json.load(sys.stdin); msg=d['systemMessage']; print(msg[:100])"
```

Expected: first 100 chars of systemMessage start with `BRIEFING:` or `GATHER_DATA:`.

- [ ] **Step 3.4: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/gather-on-skill
git commit -m "feat(hook): rewrite gather-on-skill to use h2t gather CLI"
```

---

## Task 4: Update setup SKILL.md — add uv pip install -e .

**Files:**
- Modify: `plugins/h2t-core/skills/setup/SKILL.md`

- [ ] **Step 4.1: Read the current Step 4 in SKILL.md**

Read `plugins/h2t-core/skills/setup/SKILL.md` and find Step 4 (Install dependencies).

- [ ] **Step 4.2: Replace Step 4 with updated version**

Change the existing Step 4 block from:

```bash
"$VENV_PIP" install --upgrade pip
"$VENV_PIP" install -r "$REQ"
```

To:

```bash
"$VENV_PIP" install --upgrade pip uv
"$VENV_PIP" install -r "$REQ"

# Install h2t CLI in editable mode (enables `h2t gather` command)
H2T_SKILLS_REPO=$(ls -d "$HOME/.claude/plugins/cache/lichtpfad/h2t-core"/*/  2>/dev/null | sort -V | tail -1 | xargs dirname 2>/dev/null || echo "")
[ -n "$H2T_SKILLS_REPO" ] && "$VENV_PIP" install -e "$H2T_SKILLS_REPO" --quiet && echo "h2t CLI installed" || echo "WARN: h2t-skills repo not found, skipping editable install"
```

Also bump version in frontmatter: `1.1.0` → `1.2.0`.

- [ ] **Step 4.3: Commit**

```bash
git add plugins/h2t-core/skills/setup/SKILL.md
git commit -m "feat(setup): install h2t CLI in editable mode during setup (v1.2.0)"
```

---

## Task 5: Update update-plugin.sh — copy pyproject.toml to cache

**Files:**
- Modify: `plugins/h2t-core/scripts/update-plugin.sh`

- [ ] **Step 5.1: Read update-plugin.sh and find the lib/ copy section**

Read `plugins/h2t-core/scripts/update-plugin.sh`. Find where `lib/` is copied into cache.

- [ ] **Step 5.2: Add pyproject.toml copy after lib/ copy**

Find the line that copies lib/ (something like `cp -r "$REPO_DIR/lib/" "$CACHE_TARGET/lib/"`).

Add directly after it:

```bash
# Copy pyproject.toml so editable install works from cache root
cp "$REPO_DIR/pyproject.toml" "$CACHE_TARGET/pyproject.toml"
```

- [ ] **Step 5.3: Run update-plugin.sh and verify**

```bash
bash plugins/h2t-core/scripts/update-plugin.sh
ls ~/.claude/plugins/cache/lichtpfad/h2t-core/*/pyproject.toml
```

Expected: file exists in cache.

- [ ] **Step 5.4: Commit**

```bash
git add plugins/h2t-core/scripts/update-plugin.sh
git commit -m "feat(update-plugin): copy pyproject.toml to cache for editable install"
```

---

## Task 6: Integration test end-to-end

- [ ] **Step 6.1: Run full test suite**

```bash
cd C:/dev/claude-agent-skills
~/.h2t/venv/Scripts/python.exe -m pytest lib/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass (no regressions in existing lib/gather tests).

- [ ] **Step 6.2: Test h2t binary from venv**

```bash
~/.h2t/venv/Scripts/python.exe -m lib.cli.main gather session-start --cwd C:/dev/claude-agent-skills --format-briefing | python -c "import json,sys; d=json.load(sys.stdin); print('✓ project:', d['project']['id']); print('✓ briefing:', d['_briefing'][:50])"
```

Expected:
```
✓ project: agent-skills
✓ briefing: ## Сессия: agent-skills ...
```

- [ ] **Step 6.3: Test hook fires correctly (simulate Skill tool call)**

```bash
echo '{"tool_name":"Skill","tool_input":{"skill":"h2t-core:session-start"},"cwd":"C:/dev/claude-agent-skills"}' \
  | bash plugins/h2t-core/hooks-handlers/gather-on-skill \
  | python -c "
import json, sys
d = json.load(sys.stdin)
msg = d['systemMessage']
assert 'BRIEFING:' in msg, f'Expected BRIEFING in output, got: {msg[:100]}'
print('✓ Hook output contains BRIEFING')
print('✓ First 80 chars:', msg[:80])
"
```

Expected:
```
✓ Hook output contains BRIEFING
✓ First 80 chars: BRIEFING:
## Сессия: agent-skills ...
```

- [ ] **Step 6.4: Close GitHub issue #24**

```bash
gh issue close 24 --repo lichtpfad/h2t-skills --comment "Implemented: h2t gather CLI via lib/cli/main.py, hook rewritten, editable install in setup."
```

- [ ] **Step 6.5: Final commit + push**

```bash
git push
```

---

## Self-Review

**Spec coverage check:**
- ✅ `h2t gather session-start --cwd .` → Task 2
- ✅ `h2t gather handoff --cwd .` → Task 2 (same code path, different skill arg)
- ✅ Hook rewrite < 25 lines (was ~60) → Task 3
- ✅ `uv pip install -e .` in setup → Task 4
- ✅ Works on Windows + Mac (python path detection cross-platform) → Task 1, 3
- ✅ Per-skill `gather.py` not deleted — backward compat preserved (not in scope)

**Not in scope (future issues):**
- `h2t gather daily-brief` (needs h2t-ops calendar/gmail adapters)
- `h2t gather overview` (multi-repo, needs Phase 2)
- Moving `detect_project.py` (init-project) into lib/gather
- Removing old `skills/session-start/scripts/gather.py`
