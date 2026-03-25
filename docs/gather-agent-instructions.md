# Agent Instructions: Using the Gather Framework

> For Claude Code agents creating or modifying h2t skills that need project context.

## When to Use Gather

If your skill needs **any** of this information, use gather instead of separate tool calls:
- What project are we in? (git remote, domain, project ID)
- What's the current state? (branch, uncommitted work, stack)
- What work is open? (GitHub issues, milestones, PRs)
- What happened in previous sessions? (handoff files)
- Who is the user? (about-me context, language, communication style)

## How to Add Gather to a Skill

### Step 1: Create `gather.py` in your skill directory

```
plugins/h2t/skills/YOUR-SKILL/
  SKILL.md       ← skill definition
  gather.py      ← NEW: context gatherer
```

Import only the modules you need from `lib/gather/`:

```python
#!/usr/bin/env python3
import argparse, sys, time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
# Import only what you need:
# from gather.git import gather_git
# from gather.github import gather_github
# from gather.user import gather_user_context
# from gather.stack import detect_stack
# from gather.sessions import find_session_files
from gather.eval import record_eval, estimate_tokens
```

### Step 2: Declare your layers

Choose which layers your skill needs:

| Your skill needs... | Import | Layer |
|---------------------|--------|-------|
| Project identity | `identify_project` | 0 |
| User context / about-me | `gather_user_context` | 0 |
| Git state | `gather_git` | 1 |
| Stack detection | `detect_stack` | 1 |
| GitHub issues/PRs | `gather_github` | 2 |
| Session history | `find_session_files` | 2 |

**Rule:** import only what you need. Don't load GitHub data if you don't use it.

### Step 3: Update SKILL.md

Replace individual bash commands with single gather call:

```markdown
### Step N: Gather Context

\```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && H2T_PYTHON="python3"

$H2T_PYTHON "${CLAUDE_PLUGIN_ROOT}/skills/YOUR-SKILL/gather.py" \
  --memory-dir "<memory_dir>" \
  --cwd "$(pwd)"
\```

Parse the returned JSON and use for subsequent steps.
```

### Step 4: Add eval tracking

Always record eval metrics — it's free and helps measure skill performance:

```python
record_eval("your-skill-name", {
    "duration_ms": duration_ms,
    "sources_used": sources_used,
    "sources_failed": sources_failed,
    "context_tokens_estimate": estimate_tokens(result),
    # Add skill-specific metrics:
    "your_custom_metric": value,
})
```

## Adding a New Context Source

When you need data from a source that doesn't exist yet (Notion, Calendar, Obsidian, etc.):

1. Create `plugins/h2t/lib/gather/my_source.py`
2. Function signature: `def gather_my_source(param) -> dict`
3. Use `run_parallel()` for external commands, `pathlib` for file reads
4. Return plain dict — never JSON strings
5. Add export to `__init__.py`
6. Write `test_my_source.py` with at least 2 tests
7. Failed/unavailable sources return empty dict, never raise

## Conventions

- **Modules return dicts.** Never JSON strings, never print to stdout.
- **Gatherers call `output_json()` once.** At the end, after all modules complete.
- **Fail silently.** If `gh` isn't installed, `gather_github()` returns empty. No crashes.
- **No external deps in core.** Only stdlib. PyYAML is the exception (already in h2t venv).
- **Eval is mandatory.** Every gatherer must call `record_eval()`.
- **Cross-platform.** Test on Windows and macOS. Use `pathlib`, not string paths.

## Project Identity Resolution

`identify_project(cwd)` resolves project from ANY directory:

1. **Git remote** → lookup in `~/.h2t/config/repo-mapping.yaml` mappings
2. **cwd path** → match against `cwd_patterns` in repo-mapping.yaml
3. **Default** → `dev/unknown`

This means gather works in Dropbox folders, Obsidian vaults, and any directory — not just git repos.

## Domain-Aware Context

`gather_user_context(domain=...)` loads different context based on project domain:

| Domain | Additional context |
|--------|--------------------|
| `personal`, `personal-os` | `psychology.md` |
| `hou2touch` | (courses context, future) |
| `crypto` | (strategy context, future) |
| default | `core.md` only |

## Example: Minimal Skill Gatherer

For a skill that only needs project identity and GitHub issues:

```python
#!/usr/bin/env python3
import sys, time
from pathlib import Path
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.github import gather_github
from gather.eval import record_eval, estimate_tokens

start = time.monotonic()
project = identify_project(".")
github = gather_github(project["github"]) if project.get("github") else {}
result = {"project": project, "github": github}

record_eval("my-skill", {
    "duration_ms": int((time.monotonic() - start) * 1000),
    "context_tokens_estimate": estimate_tokens(result),
})
output_json(result)
```
