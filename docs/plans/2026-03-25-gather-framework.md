# Gather Framework + Fix dev-session-start Step 6 Bug

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create Context Assembly Framework — pluggable Python gather system for h2t skills with progressive disclosure, parallel execution, eval tracking. Fix Step 6 skip bug (#6).

**Architecture:** Shared `lib/gather/` Python package with 4 layers of progressive disclosure. Layer 0 (Identity) works from any directory via registry resolve. Each skill gets a thin `gather.py` that composes needed modules and outputs JSON to stdout. Automatic eval tracking built into gather() call.

**Tech Stack:** Python 3.10+ (stdlib only — subprocess, concurrent.futures, json, pathlib). No external dependencies. PyYAML used only in project.py (already in h2t venv).

**ADR:** `docs/adr/001-gather-framework.md`
**Issues:** #7, #8, #9, #10, #11 (milestone: Gather Framework v0.1)

---

## File Structure

```
plugins/h2t/
  lib/
    gather/
      __init__.py          ← public API: gather(layers=, deep=, skill_name=)
      runner.py            ← ThreadPoolExecutor parallel command runner
      project.py           ← Layer 0: identify_project(cwd) via registry resolve
      user.py              ← Layer 0: user context (about-me/, domain-specific)
      git.py               ← Layer 1: git info: remote, branch, log, status
      github.py            ← Layer 2: gh CLI: issues, milestones, PRs
      stack.py             ← Layer 1: stack detection from project files
      sessions.py          ← Layer 2: session files discovery, session ID extraction
      eval.py              ← eval tracking: duration, sources, errors → ~/.h2t/evals/
  skills/
    dev-session-start/
      gather.py            ← skill-specific gatherer (composes lib modules)
      SKILL.md             ← updated: single gather call + Step 6 fix
```

**Design decisions:**
- `lib/gather/` is a package — each source is a module, easy to add new ones
- No external dependencies in core (PyYAML only in project.py, already in venv)
- Each module returns plain dicts — `output_json()` serializes at the end
- `runner.py` is the core — everything else builds on `run_parallel()`
- Progressive disclosure: skills declare `layers=[0,1,2]` + `deep=[...]`
- Eval tracking is automatic — `gather()` records metrics transparently

---

### Task 1: Core runner — `lib/gather/runner.py` (#7)

**Files:**
- Create: `plugins/h2t/lib/gather/runner.py`
- Create: `plugins/h2t/lib/gather/__init__.py`
- Test: `plugins/h2t/lib/gather/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# test_runner.py
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gather.runner import run_parallel, output_json

def test_run_parallel_basic():
    """Two independent commands run and return stdout."""
    results = run_parallel({
        "echo_a": ["echo", "hello"],
        "echo_b": ["echo", "world"],
    })
    assert results["echo_a"].strip() == "hello"
    assert results["echo_b"].strip() == "world"

def test_run_parallel_failing_command():
    """Failing command returns empty string, doesn't crash others."""
    results = run_parallel({
        "good": ["echo", "ok"],
        "bad": ["false"],
    })
    assert results["good"].strip() == "ok"
    assert results["bad"] == ""

def test_output_json(capsys):
    """output_json writes compact JSON to stdout."""
    output_json({"key": "value", "num": 42})
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed == {"key": "value", "num": 42}

if __name__ == "__main__":
    test_run_parallel_basic()
    test_run_parallel_failing_command()
    print("All runner tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_runner.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'gather'`

- [ ] **Step 3: Write minimal implementation**

```python
# runner.py
"""Core parallel command runner for h2t gather framework."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def _run_one(cmd: list[str], timeout: int = 15) -> str:
    """Run a single command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def run_parallel(
    commands: dict[str, list[str]],
    max_workers: int = 8,
    timeout: int = 15,
) -> dict[str, str]:
    """Run multiple commands in parallel, return {name: stdout}.

    Failed or timed-out commands return empty string.
    """
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_one, cmd, timeout): name
            for name, cmd in commands.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
    return results


def output_json(data: Any) -> None:
    """Write data as JSON to stdout."""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
```

```python
# __init__.py
"""h2t gather framework — parallel context collection for skills."""

from .runner import run_parallel, output_json

__all__ = ["run_parallel", "output_json"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_runner.py`
Expected: `All runner tests passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/__init__.py plugins/h2t/lib/gather/runner.py plugins/h2t/lib/gather/test_runner.py
git commit -m "feat(gather): core parallel runner with run_parallel() and output_json() (#7)"
```

---

### Task 2: Git module — `lib/gather/git.py` (#8)

**Files:**
- Create: `plugins/h2t/lib/gather/git.py`
- Test: `plugins/h2t/lib/gather/test_git.py`

- [ ] **Step 1: Write the failing test**

```python
# test_git.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.git import gather_git

def test_gather_git_returns_expected_keys():
    result = gather_git()
    for key in ("remote", "branch", "log", "status", "owner_repo"):
        assert key in result

def test_gather_git_branch_is_string():
    result = gather_git()
    assert isinstance(result["branch"], str)
    assert len(result["branch"]) > 0

if __name__ == "__main__":
    test_gather_git_returns_expected_keys()
    test_gather_git_branch_is_string()
    print("All git tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_git.py`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# git.py
"""Git context gathering."""

import re
from .runner import run_parallel


def gather_git() -> dict:
    """Gather git repo info: remote, branch, log, status, owner/repo."""
    raw = run_parallel({
        "remote": ["git", "remote", "get-url", "origin"],
        "branch": ["git", "branch", "--show-current"],
        "log":    ["git", "log", "--oneline", "-5"],
        "status": ["git", "status", "--short"],
        "stash":  ["git", "stash", "list"],
    })
    remote = raw["remote"].strip()
    return {
        "remote": remote,
        "branch": raw["branch"].strip(),
        "log": raw["log"].strip().splitlines(),
        "status": raw["status"].strip(),
        "stash": raw["stash"].strip(),
        "owner_repo": _parse_owner_repo(remote),
    }


def _parse_owner_repo(remote_url: str) -> str:
    """Extract 'owner/repo' from git remote URL."""
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote_url)
    return m.group(1) if m else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_git.py`
Expected: `All git tests passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/git.py plugins/h2t/lib/gather/test_git.py
git commit -m "feat(gather): git module — remote, branch, log, status, owner/repo (#8)"
```

---

### Task 3: GitHub module — `lib/gather/github.py` (#8)

**Files:**
- Create: `plugins/h2t/lib/gather/github.py`
- Test: `plugins/h2t/lib/gather/test_github.py`

- [ ] **Step 1: Write the failing test**

```python
# test_github.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.github import gather_github

def test_gather_github_returns_expected_keys():
    result = gather_github("lichtpfad/claude-agent-skills")
    for key in ("issues", "milestones", "prs", "bugs"):
        assert key in result
    assert isinstance(result["issues"], list)

def test_gather_github_with_project_filter():
    result = gather_github("lichtpfad/claude-agent-skills", project_label="nonexistent")
    assert "issues" in result

if __name__ == "__main__":
    test_gather_github_returns_expected_keys()
    test_gather_github_with_project_filter()
    print("All github tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_github.py`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# github.py
"""GitHub context gathering via gh CLI."""

import json as _json
from .runner import run_parallel


def gather_github(
    owner_repo: str,
    project_label: str | None = None,
    issue_limit: int = 20,
) -> dict:
    """Gather GitHub state: milestones, issues, bugs, PRs."""
    label_args = ["--label", f"project:{project_label}"] if project_label else []

    raw = run_parallel({
        "milestones": [
            "gh", "api", f"repos/{owner_repo}/milestones",
            "--jq", '.[] | select(.state=="open") | {title, open: .open_issues, closed: .closed_issues}',
        ],
        "issues": [
            "gh", "issue", "list", "--repo", owner_repo, "--state", "open",
            *label_args, "--json", "number,title,labels", "--limit", str(issue_limit),
        ],
        "bugs": [
            "gh", "issue", "list", "--repo", owner_repo, "--state", "open",
            "--label", "bug", *label_args, "--json", "number,title", "--limit", "10",
        ],
        "prs": [
            "gh", "pr", "list", "--repo", owner_repo, "--state", "open",
            "--json", "number,title,headRefName",
        ],
    })

    milestones = _parse_jsonl_or_json(raw["milestones"])
    issues = _parse_json(raw["issues"])
    bugs = _parse_json(raw["bugs"])
    prs = _parse_json(raw["prs"])

    current_milestone = max(milestones, key=lambda m: m.get("open", 0)) if milestones else None

    milestone_issues = []
    if current_milestone:
        raw_mi = run_parallel({
            "mi": [
                "gh", "issue", "list", "--repo", owner_repo,
                "--milestone", current_milestone["title"], "--state", "open",
                *label_args, "--json", "number,title,labels",
            ],
        })
        milestone_issues = _parse_json(raw_mi["mi"])

    return {
        "milestones": milestones, "current_milestone": current_milestone,
        "milestone_issues": milestone_issues,
        "issues": issues, "bugs": bugs, "prs": prs,
    }


def _parse_json(raw: str) -> list:
    if not raw.strip():
        return []
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return []


def _parse_jsonl_or_json(raw: str) -> list:
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        result = _json.loads(stripped)
        return result if isinstance(result, list) else [result]
    except _json.JSONDecodeError:
        pass
    items = []
    for line in stripped.splitlines():
        line = line.strip()
        if line:
            try:
                items.append(_json.loads(line))
            except _json.JSONDecodeError:
                continue
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$H2T_PYTHON plugins/h2t/lib/gather/test_github.py`
Expected: `All github tests passed`

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/github.py plugins/h2t/lib/gather/test_github.py
git commit -m "feat(gather): github module — issues, milestones, PRs via gh CLI (#8)"
```

---

### Task 4: Stack + Sessions modules (#8)

**Files:**
- Create: `plugins/h2t/lib/gather/stack.py`
- Create: `plugins/h2t/lib/gather/sessions.py`
- Test: `plugins/h2t/lib/gather/test_stack.py`
- Test: `plugins/h2t/lib/gather/test_sessions.py`

- [ ] **Step 1: Write failing tests**

```python
# test_stack.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.stack import detect_stack

def test_detect_stack_returns_dict():
    result = detect_stack(".")
    assert isinstance(result, dict)
    assert "name" in result and "commands" in result

if __name__ == "__main__":
    test_detect_stack_returns_dict()
    print("All stack tests passed")
```

```python
# test_sessions.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.sessions import find_session_files, extract_session_id

def test_find_session_files_returns_list():
    assert isinstance(find_session_files("claude-agent-skills"), list)

def test_extract_session_id_returns_string():
    assert isinstance(extract_session_id(), str)

if __name__ == "__main__":
    test_find_session_files_returns_list()
    test_extract_session_id_returns_string()
    print("All sessions tests passed")
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Write implementations**

```python
# stack.py
"""Project stack detection."""
from pathlib import Path

STACK_MAP = {
    "package.json":   {"name": "js",     "commands": {"test": "npm test", "audit": "npm audit", "build": "npm run build"}},
    "pyproject.toml": {"name": "python", "commands": {"test": "pytest", "audit": "pip-audit", "lint": "ruff check"}},
    "Cargo.toml":     {"name": "rust",   "commands": {"test": "cargo test", "audit": "cargo audit", "lint": "cargo clippy"}},
    "go.mod":         {"name": "go",     "commands": {"test": "go test ./...", "audit": "govulncheck ./...", "lint": "go vet ./..."}},
}

def detect_stack(cwd: str = ".") -> dict:
    root = Path(cwd)
    for marker, stack in STACK_MAP.items():
        if (root / marker).exists():
            return stack
    return {"name": "none", "commands": {}}
```

```python
# sessions.py
"""Session file discovery and session ID extraction."""
import os, platform
from pathlib import Path

def find_session_files(repo_name: str) -> list[str]:
    """Find session handoff files across all machines: ~/.dor/sessions/*/{repo}/*.md"""
    sessions_root = Path.home() / ".dor" / "sessions"
    if not sessions_root.exists():
        return []
    files = []
    for machine_dir in sessions_root.iterdir():
        if not machine_dir.is_dir():
            continue
        repo_dir = machine_dir / repo_name
        if repo_dir.is_dir():
            files.extend(str(f) for f in sorted(repo_dir.glob("*.md"), key=os.path.getmtime, reverse=True))
    return files

def extract_session_id(memory_dir: str | None = None) -> str:
    """Extract Claude session ID from newest .jsonl file in memory_dir parent."""
    if not memory_dir:
        return ""
    project_dir = Path(memory_dir).parent
    if not project_dir.exists():
        return ""
    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    return jsonl_files[0].stem if jsonl_files else ""

def get_machine_name() -> str:
    name = os.environ.get("DOR_MACHINE_NAME", "")
    if not name:
        name = platform.node().lower().split(".")[0]
    return name
```

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/stack.py plugins/h2t/lib/gather/sessions.py plugins/h2t/lib/gather/test_stack.py plugins/h2t/lib/gather/test_sessions.py
git commit -m "feat(gather): stack detection + session file discovery (#8)"
```

---

### Task 5: Project identity — `lib/gather/project.py` (#9)

**Files:**
- Create: `plugins/h2t/lib/gather/project.py`
- Test: `plugins/h2t/lib/gather/test_project.py`

**Context:** Project identity must work from ANY directory — git repos, Dropbox folders, Obsidian vaults.
Uses `~/.h2t/config/repo-mapping.yaml` (mappings + cwd_patterns) and `domains.yaml` for resolve.
Does NOT duplicate registry.py logic — calls it as subprocess for resolve, or reads YAML directly.

- [ ] **Step 1: Write the failing test**

```python
# test_project.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.project import identify_project

def test_identify_project_returns_expected_keys():
    result = identify_project(".")
    for key in ("id", "domain", "type", "github"):
        assert key in result, f"Missing key: {key}"

def test_identify_project_git_repo():
    """In a git repo, type should be 'git' and github should be populated."""
    result = identify_project(".")
    # We're in claude-agent-skills — a git repo
    assert result["type"] == "git"
    assert result["domain"] == "personal-os"
    assert result["id"] == "agent-skills"

def test_identify_project_nonexistent_dir():
    """Non-git directory falls back gracefully."""
    result = identify_project("/tmp")
    assert result["type"] == "directory"
    assert result["domain"]  # should have some default

if __name__ == "__main__":
    test_identify_project_returns_expected_keys()
    test_identify_project_git_repo()
    test_identify_project_nonexistent_dir()
    print("All project tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write implementation**

```python
# project.py
"""Project identity — resolve project from any directory.

Uses ~/.h2t/config/repo-mapping.yaml for git repos and cwd pattern matching.
Uses ~/.h2t/config/domains.yaml for domain metadata.
"""

from pathlib import Path
from .runner import run_parallel

# Optional: PyYAML (already in h2t venv)
try:
    import yaml
except ImportError:
    yaml = None


def _get_config_root() -> Path:
    """Find h2t config root."""
    import os
    env = os.environ.get("H2T_CONFIG_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".h2t" / "config"


def _load_yaml(path: Path) -> dict:
    """Load YAML file, return empty dict on failure."""
    if yaml is None or not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def identify_project(cwd: str = ".") -> dict:
    """Identify project from any directory.

    Resolution order:
    1. git remote → repo-mapping.yaml mappings
    2. cwd path → repo-mapping.yaml cwd_patterns
    3. default from repo-mapping.yaml

    Returns: {id, domain, label, type, github, config_root}
    """
    cwd_abs = str(Path(cwd).resolve())
    config_root = _get_config_root()
    mapping = _load_yaml(config_root / "repo-mapping.yaml")
    domains = _load_yaml(config_root / "domains.yaml")

    mappings = mapping.get("mappings", {})
    cwd_patterns = mapping.get("cwd_patterns", {})
    default = mapping.get("default", "dev/unknown")

    # 1. Try git remote
    raw = run_parallel({"remote": ["git", "-C", cwd, "remote", "get-url", "origin"]})
    remote = raw["remote"].strip()
    repo_name = ""
    github_remote = ""

    if remote:
        # Extract repo name from remote URL
        import re
        m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if m:
            github_remote = m.group(1)
            repo_name = github_remote.split("/")[-1]

        # Lookup in mappings
        if repo_name in mappings:
            domain, project_id = _split_domain_project(mappings[repo_name])
            label = _find_label(domains, domain, project_id)
            return {
                "id": project_id, "domain": domain, "label": label,
                "type": "git", "github": github_remote,
                "config_root": str(config_root),
            }

    # 2. Try cwd_patterns
    for pattern, domain_project in cwd_patterns.items():
        # Normalize path separators for cross-platform matching
        if pattern.replace("/", "\\") in cwd_abs.replace("/", "\\"):
            domain, project_id = _split_domain_project(domain_project)
            label = _find_label(domains, domain, project_id)
            return {
                "id": project_id, "domain": domain, "label": label,
                "type": "directory", "github": github_remote or None,
                "config_root": str(config_root),
            }

    # 3. Default
    domain, project_id = _split_domain_project(default)
    return {
        "id": project_id, "domain": domain, "label": project_id,
        "type": "git" if remote else "directory",
        "github": github_remote or None,
        "config_root": str(config_root),
    }


def _split_domain_project(value: str) -> tuple[str, str]:
    """Split 'domain/project' into (domain, project)."""
    parts = value.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "unknown")


def _find_label(domains: dict, domain: str, project_id: str) -> str:
    """Find project label from domains.yaml."""
    domain_data = domains.get("domains", {}).get(domain, {})
    for proj in domain_data.get("projects", []):
        if proj.get("id") == project_id:
            return proj.get("label", project_id)
    return project_id
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/project.py plugins/h2t/lib/gather/test_project.py
git commit -m "feat(gather): project identity — resolve from any directory (#9)"
```

---

### Task 6: User context — `lib/gather/user.py` (#9)

**Files:**
- Create: `plugins/h2t/lib/gather/user.py`
- Test: `plugins/h2t/lib/gather/test_user.py`

**Context:** User context is domain-dependent. `core.md` always loads. `psychology.md` loads for personal domain. `strategy.md` loads for strategic sessions. This is the foundation for progressive disclosure Layer 3.

- [ ] **Step 1: Write the failing test**

```python
# test_user.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.user import gather_user_context

def test_gather_user_context_returns_expected_keys():
    result = gather_user_context()
    assert "core_path" in result
    assert "language" in result
    assert "available_contexts" in result

def test_gather_user_context_core_exists():
    result = gather_user_context()
    assert os.path.exists(result["core_path"]) or result["core_path"] == ""

def test_gather_user_context_with_domain():
    result = gather_user_context(domain="personal")
    assert "deep_paths" in result
    # personal domain should include psychology.md if it exists

if __name__ == "__main__":
    test_gather_user_context_returns_expected_keys()
    test_gather_user_context_core_exists()
    test_gather_user_context_with_domain()
    print("All user tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write implementation**

```python
# user.py
"""User context gathering — about-me files, domain-dependent deep context."""

from pathlib import Path

# Domain → additional context files to load
DOMAIN_CONTEXT_MAP = {
    "personal": ["psychology.md"],
    "personal-os": ["psychology.md"],
    "hou2touch": [],
    "crypto": ["strategy.md"],
    "art": [],
}


def gather_user_context(
    domain: str | None = None,
    config_root: str | None = None,
) -> dict:
    """Gather user context files.

    Always includes core.md path.
    Domain-specific files added based on DOMAIN_CONTEXT_MAP.

    Returns paths only — caller reads content if needed (progressive disclosure).
    """
    root = Path(config_root) if config_root else Path.home() / ".h2t" / "config"
    about_me = root / "about-me"

    core_path = about_me / "core.md"
    available = [str(f) for f in about_me.glob("*.md")] if about_me.exists() else []

    result = {
        "core_path": str(core_path) if core_path.exists() else "",
        "language": "ru",
        "available_contexts": available,
        "deep_paths": [],
    }

    if domain:
        extra_files = DOMAIN_CONTEXT_MAP.get(domain, [])
        for filename in extra_files:
            path = about_me / filename
            if path.exists():
                result["deep_paths"].append(str(path))

    # Strategy is available for any domain if explicitly in deep sources
    strategy_path = root / "docs" / "strategy-summary.md"
    if strategy_path.exists():
        result["strategy_path"] = str(strategy_path)

    return result
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/user.py plugins/h2t/lib/gather/test_user.py
git commit -m "feat(gather): user context — about-me + domain-dependent deep paths (#9)"
```

---

### Task 7: Eval tracking — `lib/gather/eval.py` (#10)

**Files:**
- Create: `plugins/h2t/lib/gather/eval.py`
- Test: `plugins/h2t/lib/gather/test_eval.py`

**Context:** Automatic metrics recording per gather() call. Compatible with creative-thinking eval format. Stores to `~/.h2t/evals/{skill_name}/sessions/`.

- [ ] **Step 1: Write the failing test**

```python
# test_eval.py
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gather.eval import record_eval

def test_record_eval_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        record_eval(
            skill_name="test-skill",
            metrics={"duration_ms": 150, "sources_used": ["git", "github"]},
            evals_root=tmpdir,
        )
        sessions_dir = os.path.join(tmpdir, "test-skill", "sessions")
        assert os.path.isdir(sessions_dir)
        files = os.listdir(sessions_dir)
        assert len(files) == 1
        with open(os.path.join(sessions_dir, files[0])) as f:
            data = json.load(f)
        assert data["skill"] == "test-skill"
        assert data["metrics"]["duration_ms"] == 150

def test_record_eval_increments_counter():
    with tempfile.TemporaryDirectory() as tmpdir:
        record_eval("s", {"a": 1}, evals_root=tmpdir)
        record_eval("s", {"a": 2}, evals_root=tmpdir)
        sessions_dir = os.path.join(tmpdir, "s", "sessions")
        assert len(os.listdir(sessions_dir)) == 2

if __name__ == "__main__":
    test_record_eval_creates_file()
    test_record_eval_increments_counter()
    print("All eval tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Write implementation**

```python
# eval.py
"""Eval tracking for gather framework.

Records metrics per skill invocation to ~/.h2t/evals/{skill}/sessions/.
Compatible with creative-thinking eval format.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def record_eval(
    skill_name: str,
    metrics: dict,
    evals_root: str | None = None,
) -> str | None:
    """Record eval metrics for a skill invocation.

    Args:
        skill_name: Skill identifier (e.g., "dev-session-start")
        metrics: Dict of metrics to record
        evals_root: Override eval storage root (default: ~/.h2t/evals)

    Returns:
        Path to created eval file, or None on failure.
    """
    root = Path(evals_root) if evals_root else Path.home() / ".h2t" / "evals"
    sessions_dir = root / skill_name / "sessions"

    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Find next sequence number for today
    existing = list(sessions_dir.glob(f"{skill_name[:2]}-{date_str}-*.json"))
    seq = len(existing) + 1

    prefix = skill_name[:2]  # ss for session-start, ct for creative-thinking
    filename = f"{prefix}-{date_str}-{seq:03d}.json"
    filepath = sessions_dir / filename

    record = {
        "session_id": f"{prefix}-{date_str}-{seq:03d}",
        "skill": skill_name,
        "timestamp": now.isoformat(),
        "metrics": metrics,
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return str(filepath)
    except OSError:
        return None


def estimate_tokens(data: dict) -> int:
    """Rough token estimate for a dict (JSON serialized length / 4)."""
    return len(json.dumps(data, ensure_ascii=False)) // 4
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/lib/gather/eval.py plugins/h2t/lib/gather/test_eval.py
git commit -m "feat(gather): eval tracking — automatic metrics per skill (#10)"
```

---

### Task 8: Skill-specific gatherer — `dev-session-start/gather.py` (#11)

**Files:**
- Create: `plugins/h2t/skills/dev-session-start/gather.py`

**Context:** Composes all lib/gather modules. Uses project identity (Layer 0), conditionally loads git/github (Layer 1-2), records eval metrics automatically.

- [ ] **Step 1: Write the gatherer script**

```python
#!/usr/bin/env python3
"""Context gatherer for dev-session-start skill.

Usage: $H2T_PYTHON gather.py [--memory-dir <path>] [--cwd <path>]
Outputs JSON to stdout.
"""

import argparse
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, extract_session_id, get_machine_name
from gather.eval import record_eval, estimate_tokens


def read_project_filter(cwd: str = ".") -> str | None:
    pid_file = Path(cwd) / ".claude" / "project-id"
    if pid_file.exists():
        return pid_file.read_text().strip() or None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    start = time.monotonic()
    sources_used = []
    sources_failed = []

    # Layer 0 — Identity
    project = identify_project(args.cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )
    sources_used.append("user")

    # Layer 1 — State (conditional on project type)
    git = {}
    if project["type"] == "git":
        git = gather_git()
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")

    stack = detect_stack(args.cwd)
    sources_used.append("stack")

    # Layer 2 — Work Context (conditional on github)
    github = {}
    github_remote = project.get("github") or git.get("owner_repo", "")
    if github_remote:
        project_label = read_project_filter(args.cwd)
        github = gather_github(github_remote, project_label=project_label)
        sources_used.append("github")
        if not github.get("issues") and not github.get("milestones"):
            sources_failed.append("github")

    # Layer 2 — Sessions
    repo_name = github_remote.split("/")[-1] if github_remote else Path(args.cwd).resolve().name
    session_files = find_session_files(repo_name)
    sources_used.append("sessions")

    # Metadata
    session_id = extract_session_id(args.memory_dir) if args.memory_dir else ""
    machine = get_machine_name()

    result = {
        "project": project,
        "user": user,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": session_files,
        "session_id": session_id,
        "machine": machine,
    }

    duration_ms = int((time.monotonic() - start) * 1000)

    # Eval — record gather metrics
    record_eval("dev-session-start", {
        "duration_ms": duration_ms,
        "layers": [0, 1, 2],
        "sources_used": sources_used,
        "sources_failed": sources_failed,
        "context_tokens_estimate": estimate_tokens(result),
        "project_type": project["type"],
        "project_domain": project.get("domain", ""),
    })

    output_json(result)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `$H2T_PYTHON plugins/h2t/skills/dev-session-start/gather.py --cwd .`
Verify JSON contains: project.id, project.domain, git.branch, github.issues, user.core_path

- [ ] **Step 3: Verify eval was recorded**

Run: `ls ~/.h2t/evals/dev-session-start/sessions/`
Expected: one `de-YYYY-MM-DD-001.json` file

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/gather.py
git commit -m "feat(gather): dev-session-start gatherer with project identity + eval (#11)"
```

---

### Task 9: Update SKILL.md — gather integration + Step 6 fix (#11, closes #6)

**Files:**
- Modify: `plugins/h2t/skills/dev-session-start/SKILL.md`

- [ ] **Step 1: Replace Steps 1-4 with single gather call**

Replace individual Steps 1-4 with consolidated gather call using `$PLUGIN_ROOT` and `$H2T_PYTHON`.
See ADR-001 for gather call format.

- [ ] **Step 2: Fix Step 5 — remove user interaction**

Remove: `Ask: **"Продолжить с задачей X, или другое направление?"**`
Step 5 = pure data presentation, NO question.

- [ ] **Step 3: Fix Step 6 — add GATE + merge naming and direction**

Add `⛔ MANDATORY GATE` marker. Combine session naming + work direction question in one interaction point.

- [ ] **Step 4: Update graphviz procedure diagram**

Steps 1-4 → "1-4. Gather context". Step 6 gets `⛔GATE` label.

- [ ] **Step 5: Update Common Mistakes table**

Add: `| Ask "what to work on?" in Step 5 | Step 5 is data only. Naming + direction go in Step 6 GATE |`

- [ ] **Step 6: Review full SKILL.md for consistency**

Verify no references to old individual bash commands, Step 5 has no interaction, Step 6 has GATE.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/SKILL.md
git commit -m "fix(dev-session-start): Step 6 GATE + gather.py integration

Closes #6"
```

---

### Task 10: Final — update __init__.py + integration test

**Files:**
- Modify: `plugins/h2t/lib/gather/__init__.py`

- [ ] **Step 1: Update __init__.py with all exports**

```python
"""h2t gather framework — parallel context collection for skills."""

from .runner import run_parallel, output_json
from .git import gather_git
from .github import gather_github
from .stack import detect_stack
from .sessions import find_session_files, extract_session_id, get_machine_name
from .project import identify_project
from .user import gather_user_context
from .eval import record_eval, estimate_tokens

__all__ = [
    "run_parallel", "output_json",
    "gather_git", "gather_github",
    "detect_stack",
    "find_session_files", "extract_session_id", "get_machine_name",
    "identify_project", "gather_user_context",
    "record_eval", "estimate_tokens",
]
```

- [ ] **Step 2: Full integration test**

Run: `$H2T_PYTHON plugins/h2t/skills/dev-session-start/gather.py --cwd .`
Verify: project.domain = "personal-os", git.branch = "main", github.issues non-empty

- [ ] **Step 3: Run all unit tests**

Run: `for t in plugins/h2t/lib/gather/test_*.py; do echo "=== $t ==="; $H2T_PYTHON "$t"; done`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t/lib/gather/__init__.py
git commit -m "feat(gather): complete v0.1 — all modules + public API (#7 #8 #9 #10 #11)"
```
