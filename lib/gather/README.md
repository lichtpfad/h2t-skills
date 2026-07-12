# h2t gather — Context Assembly Framework

Parallel context collection for Claude Code skills. One Python call replaces 10+ sequential tool calls.

## Quick Start

```bash
# Run from any directory
$H2T_PYTHON gather.py --cwd . --memory-dir "<memory_dir>"
# → JSON to stdout with project identity, git state, GitHub issues, etc.
```

## Architecture

```
lib/gather/
  runner.py      run_parallel() — ThreadPoolExecutor, parallel subprocess
  project.py     identify_project() — resolve project from ANY directory
  user.py        gather_user_context() — about-me + domain-dependent context
  git.py         gather_git() — remote, branch, log, status
  github.py      gather_github() — issues, milestones, PRs via gh CLI
  stack.py       detect_stack() — project stack from marker files
  sessions.py    find_session_files() — handoff files across machines
```

Eval is not part of gather. Metrics are recorded at the skill/CLI layer via
`SkillEval` (`lib/eval/session.py`) — see [Eval](#eval) below.

### Progressive Disclosure — 4 Layers

| Layer | What | Speed | Modules |
|-------|------|-------|---------|
| 0 | Identity — who, what project, what machine | instant | `project`, `user` |
| 1 | State — git, stack detection | ~100ms | `git`, `stack` |
| 2 | Work Context — GitHub, session files | ~500ms | `github`, `sessions` |
| 3 | Deep Context — file contents, Notion, Calendar | varies | `sources/*` (future) |

Skills declare which layers they need. Gather loads only those.

## Writing a Skill Gatherer

Each skill gets a thin `gather.py` in its directory:

```python
#!/usr/bin/env python3
"""Context gatherer for my-skill."""

import argparse, sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, get_machine_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    # Layer 0
    project = identify_project(args.cwd)
    user = gather_user_context(domain=project.get("domain"))

    # Layer 1 (conditional)
    git = gather_git() if project["type"] == "git" else {}
    stack = detect_stack(args.cwd)

    # Layer 2 (conditional)
    github = {}
    remote = project.get("github") or git.get("owner_repo", "")
    if remote:
        github = gather_github(remote)

    result = {
        "project": project, "user": user,
        "git": git, "github": github, "stack": stack,
        "machine": get_machine_name(),
    }

    # Gatherers do not record eval themselves — the skill/CLI layer wraps the
    # invocation in SkillEval (see Eval below).
    output_json(result)

if __name__ == "__main__":
    main()
```

In SKILL.md, call it with one command:

```bash
$H2T_PYTHON "${CLAUDE_PLUGIN_ROOT}/skills/my-skill/gather.py" \
  --memory-dir "<memory_dir>" --cwd "$(pwd)"
```

## Adding a New Source Module

Create `lib/gather/my_source.py`:

```python
"""My new context source."""

from .runner import run_parallel  # if you need subprocess calls

def gather_my_source(some_param: str) -> dict:
    """Gather context from my source. Returns plain dict."""
    # Use run_parallel() for external commands
    # Or read files directly with pathlib
    return {"key": "value"}
```

Add export to `__init__.py`:

```python
from .my_source import gather_my_source
```

Use in any skill's `gather.py`:

```python
from gather.my_source import gather_my_source
result["my_source"] = gather_my_source(param)
```

## Core API

### `run_parallel(commands, max_workers=8, timeout=15)`

Run multiple subprocess commands in parallel.

```python
results = run_parallel({
    "branch": ["git", "branch", "--show-current"],
    "issues": ["gh", "issue", "list", "--json", "number,title"],
})
# results["branch"] = "main\n"
# results["issues"] = '[{"number":1,...}]'
# Failed commands return ""
```

### `identify_project(cwd)`

Resolve project identity from any directory.

```python
project = identify_project(".")
# {"id": "agent-skills", "domain": "personal-os", "type": "git",
#  "github": "lichtpfad/h2t-skills", "config_root": "~/.h2t/config"}
```

Resolution: git remote → repo-mapping.yaml → cwd_patterns → default.

## Eval

Eval is **not** a gather module. A skill (or its CLI entrypoint) wraps its run in
`SkillEval` (`lib/eval/session.py`), which writes metrics per the resolved
`H2T_EVALS_MODE` (`off` / `local` / `push`) on context exit:

```python
from lib.eval.session import SkillEval

with SkillEval("dev-session-start", domain="dev", project="agent-skills") as ev:
    ev.metric("skills.gather_source_success_rate", value_num=0.95)
    ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
```

The mandatory `core.*` metrics are emitted automatically; callers add custom
`skills.*` metrics. Gatherers stay eval-free.

## Testing

```bash
# All unit tests
for t in plugins/h2t/lib/gather/test_*.py; do python "$t"; done

# Integration — run gatherer
python plugins/h2t/skills/dev-session-start/gather.py --cwd .

# Cross-platform
python gather.py --cwd "E:/DROPBOX/..."  # non-git directory
python gather.py --cwd /tmp               # unknown project
```

## Design Decisions

See `docs/adr/001-gather-framework.md` for full architecture decision record.

Key choices:
- **Python stdlib only** — no external deps in core (PyYAML in project.py, already in venv)
- **subprocess, not import** — each module shells out to git/gh, no library coupling
- **Dict in, JSON out** — modules return plain dicts, gatherer serializes once
- **Fail gracefully** — missing sources return empty, never crash
- **Cross-platform** — Windows + macOS, tested on both
