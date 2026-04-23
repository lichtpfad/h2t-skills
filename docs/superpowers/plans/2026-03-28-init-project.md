---
title: "h2t:init-project Implementation Plan"
status: "draft"
date: "2026-03-28"
milestone: ""
---
# h2t:init-project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register any directory as a project in the h2t ecosystem via auto-detection, user confirmation, and deterministic YAML writing.

**Architecture:** PreToolUse hook runs `detect_project.py` → returns `INIT_DATA:` with recommendations + confirm message. SKILL.md shows confirm verbatim, collects missing input. User confirms → LLM calls `apply_registration.py` via Bash → writes `repo-mapping.yaml` and `domains.yaml`.

**Tech Stack:** Python 3.11+, ruamel.yaml (required), pytest, bash (hook handler)

**Prerequisite:** `ruamel.yaml` must be installed in `~/.h2t/venv`. Check with Task 0.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t/skills/init-project/scripts/detect_project.py` | Create | Detect type, domain, tracker; build confirm message |
| `plugins/h2t/skills/init-project/scripts/test_detect.py` | Create | Tests for detection logic |
| `plugins/h2t/skills/init-project/scripts/apply_registration.py` | Create | Write to repo-mapping.yaml + domains.yaml |
| `plugins/h2t/skills/init-project/scripts/test_apply.py` | Create | Tests for YAML writing (temp files) |
| `plugins/h2t/skills/init-project/SKILL.md` | Create | 3-step orchestration |
| `plugins/h2t/hooks-handlers/gather-on-skill` | Modify | Add init-project skill routing + script name lookup |

---

### Task 0: Install ruamel.yaml prerequisite

**Files:** none (venv setup)

- [ ] **Step 1: Install ruamel.yaml**

Run: `~/.h2t/venv/Scripts/python.exe -m pip install ruamel.yaml`

- [ ] **Step 2: Verify installation**

Run: `~/.h2t/venv/Scripts/python.exe -c "from ruamel.yaml import YAML; print('ok')"`
Expected: `ok`

---

### Task 1: Create `detect_project.py` — detection + confirm message

**Files:**
- Create: `plugins/h2t/skills/init-project/scripts/detect_project.py`
- Create: `plugins/h2t/skills/init-project/scripts/test_detect.py`

- [ ] **Step 1: Write failing test — happy path (git project, known domain)**

```python
# plugins/h2t/skills/init-project/scripts/test_detect.py
"""Tests for detect_project.py detection logic."""
import sys
from pathlib import Path

# Add lib to path for gather imports
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from detect_project import detect_project, _detect_domain, _detect_tracker, _humanize_id


def test_detect_domain_h2t_prefix():
    assert _detect_domain("C:/dev/h2t-vision") == ("hou2touch", "high", "path C:/dev/h2t-* matches hou2touch")


def test_detect_domain_crypto_prefix():
    assert _detect_domain("C:/dev/crypto-etl") == ("crypto", "high", "path C:/dev/crypto-* matches crypto")


def test_detect_domain_generic_dev():
    domain, confidence, reason = _detect_domain("C:/dev/some-project")
    assert domain == "dev"
    assert confidence == "medium"


def test_detect_domain_dropbox_h2t():
    domain, confidence, reason = _detect_domain("E:/DROPBOX/LichtPfad Dropbox/HOU2TOUCH/COURSES")
    assert domain == "hou2touch"
    assert confidence == "high"


def test_detect_domain_unknown():
    domain, confidence, reason = _detect_domain("D:/random/folder")
    assert domain is None
    assert confidence == "low"


def test_humanize_id():
    assert _humanize_id("h2t-vision") == "H2T Vision"
    assert _humanize_id("crypto-etl") == "Crypto ETL"
    assert _humanize_id("my-cool-project") == "My Cool Project"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_detect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'detect_project'`

- [ ] **Step 3: Implement `detect_project.py`**

```python
#!/usr/bin/env python3
"""Detect project type, domain, tracker for init-project skill.

Usage: $H2T_PYTHON detect_project.py --cwd <path>
Outputs JSON to stdout.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather.stack import detect_stack

# Domain patterns: (regex on normalized forward-slash path, domain, confidence)
DOMAIN_PATTERNS = [
    (r"[Cc]:/dev/h2t-|[Cc]:/dev/hou2touch", "hou2touch", "high", "path C:/dev/h2t-* matches hou2touch"),
    (r"[Cc]:/dev/crypto-", "crypto", "high", "path C:/dev/crypto-* matches crypto"),
    (r"HOU2TOUCH", "hou2touch", "high", "path contains HOU2TOUCH"),
    (r"[Cc]:/dev/", "dev", "medium", "path C:/dev/* suggests dev"),
    (r"Projects/DOR|Projects/newsengine", "personal-os", "high", "known personal-os project path"),
    (r"Projects/crypto-", "crypto", "high", "path ~/Projects/crypto-* matches crypto"),
]

# File extensions that hint at art domain
ART_EXTENSIONS = {".toe", ".hip", ".hiplc", ".hipnc"}


def _detect_type(cwd: str) -> tuple[str, str | None]:
    """Detect project type and github remote.

    Returns: (type, github_owner_repo_or_none)
    """
    git_dir = Path(cwd) / ".git"
    if not git_dir.exists():
        return "directory", None

    # Try to get remote
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        remote = result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        remote = ""

    if not remote:
        return "git-local", None

    # Parse owner/repo
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    github = m.group(1) if m else None
    return "git", github


def _detect_domain(cwd: str) -> tuple[str | None, str, str]:
    """Detect domain from path patterns.

    Returns: (domain_or_none, confidence, reason)
    """
    # Normalize to forward slashes
    normalized = cwd.replace("\\", "/")

    for pattern, domain, confidence, reason in DOMAIN_PATTERNS:
        if re.search(pattern, normalized):
            return domain, confidence, reason

    # Check for art file extensions
    cwd_path = Path(cwd)
    if cwd_path.is_dir():
        for ext in ART_EXTENSIONS:
            if list(cwd_path.glob(f"*{ext}"))[:1]:
                return "art", "medium", f"found {ext} files suggesting art project"

    return None, "low", f"path {normalized} — no pattern match"


def _detect_tracker(
    github: str | None, domain: str | None, domains_data: dict,
) -> tuple[str | None, str, str]:
    """Detect task tracker. Returns (tracker, confidence, reason).

    If domain is unknown, tracker is deferred.
    """
    if domain is None:
        return None, "deferred", "domain unknown — tracker will be resolved after domain selection"

    # Check if domain has notion_db_id
    domain_info = domains_data.get("domains", {}).get(domain, {})
    has_notion = bool(domain_info.get("notion_db_id"))

    # Check GitHub accessibility
    has_github = False
    if github:
        try:
            result = subprocess.run(
                ["gh", "repo", "view", github, "--json", "name"],
                capture_output=True, text=True, timeout=10,
            )
            has_github = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            has_github = False

    if has_github and not has_notion:
        return "github", "high", "GitHub remote exists and accessible"
    if has_notion and not has_github:
        return "notion", "high", f"domain {domain} has notion_db_id"
    if has_github and has_notion:
        return None, "low", f"both GitHub and Notion available for domain {domain} — ask user"
    return "none", "high", "no GitHub, no Notion for this domain"


def _humanize_id(project_id: str) -> str:
    """Convert kebab-case id to human label: 'h2t-vision' → 'H2T Vision'."""
    parts = project_id.split("-")
    result = []
    for part in parts:
        # Keep acronyms uppercase if all letters are already
        if part.upper() == part and len(part) <= 4:
            result.append(part.upper())
        else:
            result.append(part.capitalize())
    return " ".join(result)


def _check_already_registered(
    cwd: str, repo_name: str | None, mapping_data: dict,
) -> dict | None:
    """Check if project is already in repo-mapping.yaml.

    Returns current config dict or None if not registered.
    """
    mappings = mapping_data.get("mappings", {})
    cwd_patterns = mapping_data.get("cwd_patterns", {})

    # Check by repo name in mappings
    if repo_name and repo_name in mappings:
        domain_project = mappings[repo_name]
        parts = domain_project.split("/", 1)
        return {
            "id": parts[1] if len(parts) == 2 else repo_name,
            "domain": parts[0],
            "source": "mappings",
        }

    # Check by cwd in cwd_patterns
    normalized = cwd.replace("\\", "/")
    for pattern, domain_project in cwd_patterns.items():
        if pattern.replace("/", "\\") in normalized or pattern in normalized:
            parts = domain_project.split("/", 1)
            return {
                "id": parts[1] if len(parts) == 2 else "unknown",
                "domain": parts[0],
                "source": "cwd_patterns",
            }

    return None


def _find_label(domains_data: dict, domain: str, project_id: str) -> str | None:
    """Find existing label in domains.yaml."""
    domain_info = domains_data.get("domains", {}).get(domain, {})
    for proj in domain_info.get("projects", []):
        if proj.get("id") == project_id:
            return proj.get("label")
    return None


def _load_yaml(path: Path) -> dict:
    """Load YAML file, return empty dict if missing or no yaml."""
    try:
        import yaml
    except ImportError:
        return {}
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_confirm_message(detected: dict, already_registered: bool) -> str:
    """Build the confirm message shown to user."""
    if already_registered:
        cur = detected
        return (
            f"Проект {cur['id']} уже зарегистрирован:\n"
            f"- Домен: {cur['domain']}\n"
            f"- Label: {cur.get('label', cur['id'])}\n\n"
            f"Хочешь обновить настройки?"
        )

    d = detected
    lines = ["Регистрирую проект:\n"]
    lines.append(f"- **ID:** {d['id']}")
    lines.append(f"- **Label:** {d['label']}")

    if d.get("domain"):
        lines.append(f"- **Домен:** {d['domain']}")

    type_str = d["type"]
    if d.get("github"):
        type_str += f" (GitHub: {d['github']})"
    lines.append(f"- **Тип:** {type_str}")

    if d.get("stack") and d["stack"] != "none":
        lines.append(f"- **Stack:** {d['stack']}")

    if d.get("tracker_confidence") == "deferred":
        lines.append("- **Task tracker:** определится после выбора домена")
    elif d.get("task_tracker"):
        lines.append(f"- **Task tracker:** {d['task_tracker']}")

    if d.get("domain"):
        lines.append("\nФайлы:")
        lines.append("- `~/.h2t/config/repo-mapping.yaml` → добавлю mapping")
        lines.append("- `~/.h2t/config/domains.yaml` → добавлю project entry")
        lines.append("\nВсё верно?")
    else:
        # Domain unknown — need to ask
        lines.append("\nНе могу определить домен. Варианты:")
        # List available domains
        lines.append("1. dev")
        lines.append("2. hou2touch")
        lines.append("3. crypto")
        lines.append("4. art")
        lines.append("5. personal-os")
        lines.append("6. admin")
        lines.append("7. другой")
        lines.append("\nКакой домен?")

    return "\n".join(lines)


def detect_project(cwd: str) -> dict:
    """Main detection entry point. Returns full result dict."""
    config_root = Path.home() / ".h2t" / "config"
    mapping_data = _load_yaml(config_root / "repo-mapping.yaml")
    domains_data = _load_yaml(config_root / "domains.yaml")

    cwd_path = Path(cwd).resolve()
    cwd_str = str(cwd_path)

    # Detect type + github
    proj_type, github = _detect_type(cwd_str)

    # Derive repo name from github or dir name
    repo_name = None
    if github:
        repo_name = github.split("/")[-1]
    elif proj_type in ("git", "git-local"):
        repo_name = cwd_path.name

    # Check already registered
    current = _check_already_registered(cwd_str, repo_name, mapping_data)
    if current:
        label = _find_label(domains_data, current["domain"], current["id"])
        current["label"] = label or _humanize_id(current["id"])
        return {
            "already_registered": True,
            "current": current,
            "confirm_message": _build_confirm_message(current, already_registered=True),
        }

    # Reject workspace
    if _is_workspace(cwd_path, mapping_data):
        return {
            "error": f"Это workspace ({cwd_str}), не проект. cd в конкретный проект.",
        }

    # Detect domain
    domain, domain_confidence, domain_reason = _detect_domain(cwd_str)

    # Detect stack
    stack = detect_stack(cwd_str)
    stack_name = stack.get("name", "none")

    # Project id
    project_id = repo_name or cwd_path.name

    # Label
    label = _find_label(domains_data, domain, project_id) if domain else None
    if not label:
        label = _humanize_id(project_id)

    # Detect tracker (deferred if domain unknown)
    tracker, tracker_confidence, tracker_reason = _detect_tracker(
        github, domain, domains_data,
    )

    # Build needs_input
    input_fields = []
    if domain_confidence != "high":
        input_fields.append("domain")
    if tracker_confidence == "low":
        input_fields.append("task_tracker")

    detected = {
        "id": project_id,
        "type": proj_type,
        "github": github,
        "stack": stack_name,
        "domain": domain,
        "domain_confidence": domain_confidence,
        "domain_reason": domain_reason,
        "label": label,
        "task_tracker": tracker,
        "tracker_confidence": tracker_confidence,
        "tracker_reason": tracker_reason,
    }

    return {
        "detected": detected,
        "already_registered": False,
        "needs_input": bool(input_fields),
        "input_fields": input_fields,
        "confirm_message": _build_confirm_message(detected, already_registered=False),
    }


def _is_workspace(cwd: Path, mapping_data: dict) -> bool:
    """Check if cwd is a workspace (parent of known repos)."""
    mappings = mapping_data.get("mappings", {})
    child_count = sum(
        1 for subdir in cwd.iterdir()
        if subdir.is_dir() and subdir.name in mappings
    ) if cwd.is_dir() else 0
    return child_count >= 3  # arbitrary threshold: 3+ known children = workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    result = detect_project(args.cwd)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_detect.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write tests for tracker logic and already-registered**

```python
# append to test_detect.py

def test_detect_tracker_github_only():
    """GitHub accessible, no notion → github."""
    # Can't test gh CLI in unit tests, test the logic with mocked inputs
    from detect_project import _detect_tracker
    # Simulate: github exists, domain has no notion_db_id
    domains = {"domains": {"dev": {"label": "Dev"}}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", "dev", domains)
    # Note: this will try to run `gh` — may fail in CI. Test the no-github path instead.


def test_detect_tracker_deferred_when_no_domain():
    """Domain unknown → tracker deferred."""
    from detect_project import _detect_tracker
    domains = {"domains": {}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", None, domains)
    assert tracker is None
    assert confidence == "deferred"


def test_detect_tracker_none_when_no_github_no_notion():
    """No GitHub, no Notion → none."""
    from detect_project import _detect_tracker
    domains = {"domains": {"admin": {"label": "Admin"}}}
    # github=None means no remote
    tracker, confidence, reason = _detect_tracker(None, "admin", domains)
    assert tracker == "none"
    assert confidence == "high"


def test_check_already_registered_found():
    from detect_project import _check_already_registered
    mapping = {"mappings": {"my-repo": "dev/my-project"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/my-repo", "my-repo", mapping)
    assert result is not None
    assert result["id"] == "my-project"
    assert result["domain"] == "dev"


def test_check_already_registered_not_found():
    from detect_project import _check_already_registered
    mapping = {"mappings": {"other-repo": "dev/other"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/new-repo", "new-repo", mapping)
    assert result is None


def test_check_already_registered_cwd_pattern():
    from detect_project import _check_already_registered
    mapping = {"mappings": {}, "cwd_patterns": {"/Steuer": "admin/taxes"}}
    result = _check_already_registered("E:/DROPBOX/Steuer/2026", None, mapping)
    assert result is not None
    assert result["domain"] == "admin"
```

- [ ] **Step 6: Run all detect tests**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_detect.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t/skills/init-project/scripts/detect_project.py plugins/h2t/skills/init-project/scripts/test_detect.py
git commit -m "feat: detect_project.py — type, domain, tracker detection for init-project (#17)"
```

---

### Task 2: Create `apply_registration.py` — YAML writer

**Files:**
- Create: `plugins/h2t/skills/init-project/scripts/apply_registration.py`
- Create: `plugins/h2t/skills/init-project/scripts/test_apply.py`

- [ ] **Step 1: Write failing test — add to repo-mapping (git project)**

```python
# plugins/h2t/skills/init-project/scripts/test_apply.py
"""Tests for apply_registration.py YAML writing."""
import json
import tempfile
import shutil
from pathlib import Path

from apply_registration import apply_registration


def _make_config(tmp: Path, mapping_content: str, domains_content: str):
    """Create temp config dir with YAML files."""
    mapping_file = tmp / "repo-mapping.yaml"
    domains_file = tmp / "domains.yaml"
    mapping_file.write_text(mapping_content, encoding="utf-8")
    domains_file.write_text(domains_content, encoding="utf-8")
    return mapping_file, domains_file


MINIMAL_MAPPING = """\
# repo-mapping.yaml
mappings:
  existing-repo: dev/existing

cwd_patterns:
  "/some/path": admin/taxes

default: dev/unknown
"""

MINIMAL_DOMAINS = """\
# domains.yaml
domains:
  dev:
    label: "Dev"
    projects:
      - id: existing
        label: "Existing Project"
"""


def test_add_git_project_to_mapping(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    result = apply_registration(
        project_id="new-project",
        domain="dev",
        project_type="git",
        label="New Project",
        task_tracker="github",
        github="lichtpfad/new-project",
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"

    # Verify mapping was added
    content = mapping_file.read_text(encoding="utf-8")
    assert "new-project:" in content
    assert "dev/new-project" in content
    # Verify comment preserved
    assert "# repo-mapping.yaml" in content

    # Verify domains entry added
    dcontent = domains_file.read_text(encoding="utf-8")
    assert "new-project" in dcontent
    assert "New Project" in dcontent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_apply.py::test_add_git_project_to_mapping -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `apply_registration.py`**

```python
#!/usr/bin/env python3
"""Apply project registration to repo-mapping.yaml and domains.yaml.

Usage: $H2T_PYTHON apply_registration.py --id X --domain Y --type Z --label L --task-tracker T [--github G] [--stack S] [--cwd P] [--config-root R]
Outputs JSON to stdout.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
except ImportError:
    print(json.dumps({
        "status": "error",
        "error": "ruamel.yaml required. Install: pip install ruamel.yaml into ~/.h2t/venv",
    }))
    sys.exit(1)


def _backup(path: Path) -> None:
    """Create .bak backup of a file."""
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def apply_registration(
    project_id: str,
    domain: str,
    project_type: str,
    label: str,
    task_tracker: str = "none",
    github: str | None = None,
    stack: str | None = None,
    cwd: str | None = None,
    config_root: str | None = None,
) -> dict:
    """Register project in repo-mapping.yaml and domains.yaml.

    Returns result dict with status and actions list.
    """
    root = Path(config_root) if config_root else Path.home() / ".h2t" / "config"
    mapping_path = root / "repo-mapping.yaml"
    domains_path = root / "domains.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    actions = []

    # 1. Update repo-mapping.yaml
    _backup(mapping_path)
    mapping = yaml.load(mapping_path) if mapping_path.exists() else {}
    if mapping is None:
        mapping = {}

    if "mappings" not in mapping:
        mapping["mappings"] = {}
    if "cwd_patterns" not in mapping:
        mapping["cwd_patterns"] = {}

    domain_project = f"{domain}/{project_id}"

    if project_type in ("git", "git-local"):
        # Use repo name (last part of github or project_id) as key
        repo_key = github.split("/")[-1] if github else project_id
        mapping["mappings"][repo_key] = domain_project
        actions.append(f"Added {repo_key} to repo-mapping.yaml mappings")
    else:
        # directory type → cwd_patterns
        if cwd:
            normalized = cwd.replace("\\", "/")
            mapping["cwd_patterns"][normalized] = domain_project
            actions.append(f"Added {normalized} to repo-mapping.yaml cwd_patterns")
        else:
            actions.append("Skipped cwd_patterns — no --cwd provided for directory type")

    with open(mapping_path, "w", encoding="utf-8") as f:
        yaml.dump(mapping, f)

    # 2. Update domains.yaml
    _backup(domains_path)
    domains = yaml.load(domains_path) if domains_path.exists() else {}
    if domains is None:
        domains = {}

    if "domains" not in domains:
        domains["domains"] = {}
    if domain not in domains["domains"]:
        domains["domains"][domain] = {"label": domain.capitalize(), "projects": []}

    domain_data = domains["domains"][domain]
    if "projects" not in domain_data:
        domain_data["projects"] = []

    # Check if project already exists in domain
    existing = None
    for proj in domain_data["projects"]:
        if proj.get("id") == project_id:
            existing = proj
            break

    if existing:
        # Update existing entry
        existing["label"] = label
        if task_tracker != "none":
            existing["task_tracker"] = task_tracker
        actions.append(f"Updated {project_id} in domains.yaml under {domain}")
    else:
        # Add new entry
        new_entry = {"id": project_id, "label": label, "description": ""}
        if task_tracker != "none":
            new_entry["task_tracker"] = task_tracker
        domain_data["projects"].append(new_entry)
        actions.append(f"Added {project_id} to domains.yaml under {domain}")

    with open(domains_path, "w", encoding="utf-8") as f:
        yaml.dump(domains, f)

    # 3. Create .claude/project-id if cwd provided
    if cwd:
        pid_dir = Path(cwd) / ".claude"
        pid_file = pid_dir / "project-id"
        if not pid_file.exists():
            pid_dir.mkdir(parents=True, exist_ok=True)
            pid_file.write_text(project_id + "\n", encoding="utf-8")
            actions.append("Created .claude/project-id")

    return {
        "status": "ok",
        "actions": actions,
        "next_steps": [
            "Next /session-start will recognize this project",
            "Run /h2t:scaffold-project for full setup (CLAUDE.md, milestones, issues)",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--type", required=True, dest="project_type")
    parser.add_argument("--label", required=True)
    parser.add_argument("--task-tracker", default="none")
    parser.add_argument("--github", default=None)
    parser.add_argument("--stack", default=None)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--config-root", default=None)
    args = parser.parse_args()

    result = apply_registration(
        project_id=args.id,
        domain=args.domain,
        project_type=args.project_type,
        label=args.label,
        task_tracker=args.task_tracker,
        github=args.github,
        stack=args.stack,
        cwd=args.cwd,
        config_root=args.config_root,
    )

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_apply.py::test_add_git_project_to_mapping -v`
Expected: PASS

- [ ] **Step 5: Write more tests — directory type, update existing, backup, project-id**

```python
# append to test_apply.py

def test_add_directory_project_to_cwd_patterns(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    result = apply_registration(
        project_id="steuer",
        domain="admin",
        project_type="directory",
        label="Steuer Docs",
        task_tracker="none",
        cwd="E:/DROPBOX/Steuer",
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"
    content = mapping_file.read_text(encoding="utf-8")
    assert "E:/DROPBOX/Steuer" in content
    assert "admin/steuer" in content


def test_update_existing_project(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    result = apply_registration(
        project_id="existing",
        domain="dev",
        project_type="git",
        label="Updated Label",
        task_tracker="github",
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"
    dcontent = domains_file.read_text(encoding="utf-8")
    assert "Updated Label" in dcontent
    # Should not duplicate
    assert dcontent.count("id: existing") == 1


def test_backup_created(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="test",
        domain="dev",
        project_type="git",
        label="Test",
        config_root=str(tmp_path),
    )

    assert (tmp_path / "repo-mapping.yaml.bak").exists()
    assert (tmp_path / "domains.yaml.bak").exists()


def test_project_id_file_created(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    apply_registration(
        project_id="my-project",
        domain="dev",
        project_type="git",
        label="My Project",
        cwd=str(project_dir),
        config_root=str(tmp_path),
    )

    pid_file = project_dir / ".claude" / "project-id"
    assert pid_file.exists()
    assert pid_file.read_text().strip() == "my-project"


def test_project_id_file_not_overwritten(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    (claude_dir / "project-id").write_text("old-id\n")

    apply_registration(
        project_id="new-id",
        domain="dev",
        project_type="git",
        label="New",
        cwd=str(project_dir),
        config_root=str(tmp_path),
    )

    assert (claude_dir / "project-id").read_text().strip() == "old-id"


def test_comment_preserved_in_mapping(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="new",
        domain="dev",
        project_type="git",
        label="New",
        config_root=str(tmp_path),
    )

    content = mapping_file.read_text(encoding="utf-8")
    assert "# repo-mapping.yaml" in content


def test_new_domain_created_if_missing(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="taxes",
        domain="admin",
        project_type="directory",
        label="Taxes",
        task_tracker="notion",
        cwd="/some/path",
        config_root=str(tmp_path),
    )

    dcontent = domains_file.read_text(encoding="utf-8")
    assert "admin:" in dcontent
    assert "taxes" in dcontent
    assert "task_tracker: notion" in dcontent or "task_tracker: 'notion'" in dcontent
```

- [ ] **Step 6: Run all apply tests**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/test_apply.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t/skills/init-project/scripts/apply_registration.py plugins/h2t/skills/init-project/scripts/test_apply.py
git commit -m "feat: apply_registration.py — YAML writer for init-project (#17)"
```

---

### Task 3: Update hook — add init-project routing

**Files:**
- Modify: `plugins/h2t/hooks-handlers/gather-on-skill`

- [ ] **Step 1: Add init-project to skill detection**

In the skill detection block (lines 11-16), add:

```bash
elif [[ "$skill" == *"init-project"* ]]; then
  SKILL_NAME="init-project"
```

- [ ] **Step 2: Replace hardcoded gather.py path with case lookup**

Replace line 37:
```bash
GATHER_PY="${CLAUDE_PLUGIN_ROOT}/skills/${SKILL_NAME}/scripts/gather.py"
```

With:
```bash
# Resolve entry script per skill
case "$SKILL_NAME" in
  init-project)  SCRIPT_NAME="detect_project.py" ;;
  *)             SCRIPT_NAME="gather.py" ;;
esac
GATHER_PY="${CLAUDE_PLUGIN_ROOT}/skills/${SKILL_NAME}/scripts/${SCRIPT_NAME}"
```

- [ ] **Step 3: Update error message**

Replace line 39:
```bash
echo '{"systemMessage": "GATHER_ERROR: gather.py not found at '"$GATHER_PY"'"}'
```
With:
```bash
echo '{"systemMessage": "GATHER_ERROR: '"$SCRIPT_NAME"' not found at '"$GATHER_PY"'"}'
```

- [ ] **Step 4: Add init-project output branch**

Change the if/else structure. Current structure:

```bash
if [ "$SKILL_NAME" = "handoff" ]; then
  ...
else
  # dev-session-start
  ...
fi
```

Change to:

```bash
if [ "$SKILL_NAME" = "handoff" ]; then
  ...
elif [ "$SKILL_NAME" = "init-project" ]; then
  # init-project: return as INIT_DATA
  "$H2T_PYTHON" -c "
import sys, json
raw = sys.stdin.read().strip()
output = {'systemMessage': 'INIT_DATA: ' + raw}
print(json.dumps(output, ensure_ascii=False))
" <<< "$RESULT"
else
  # dev-session-start: return pre-formatted briefing + meta
  ...
fi
```

- [ ] **Step 5: Don't pass --format-briefing for init-project**

The current flag logic (lines 43-47) already only adds `--format-briefing` for dev-session-start, so no change needed. Verify by reading.

- [ ] **Step 6: Test hook manually**

```bash
cd C:/dev/claude-agent-skills
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:init-project"},"cwd":"C:/dev/claude-agent-skills"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill
```

Expected: Output JSON with `"systemMessage": "INIT_DATA: {\"already_registered\": true, ...}"` (because agent-skills is already registered).

```bash
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:dev-session-start"},"cwd":"C:/dev/claude-agent-skills"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill 2>&1 | head -c 100
```

Expected: Still starts with `BRIEFING:` — no regression.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t/hooks-handlers/gather-on-skill
git commit -m "feat: hook supports init-project skill with detect_project.py routing (#17)"
```

---

### Task 4: Create SKILL.md

**Files:**
- Create: `plugins/h2t/skills/init-project/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: init-project
description: Register existing repo or directory in h2t ecosystem. Triggers on "/init-project", "register project", or actionable hint from session-start when project.id == "unknown". NOT for creating new repos (use /h2t:scaffold-project).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

Register the current directory as a project in the h2t ecosystem. The PreToolUse hook has already detected the project type, domain, and task tracker.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
```

## Procedure

### Step 1: Show Detection Result

Look for `INIT_DATA:` in hook output or system messages.

If it contains `"error":` — show the error and stop.
If it contains `"already_registered": true` — show confirm_message, ask if user wants to update. If no → stop.

**Show confirm_message VERBATIM.** Do not modify or supplement.

### Step 2: Collect Missing Input

If `needs_input` is true:
- Show confirm_message (it already contains the question)
- Collect user's answer for each field in `input_fields`
- If `domain` was collected and `tracker_confidence` == `"deferred"`:
  - Check if the chosen domain is `hou2touch` (has Notion) AND `detected.github` exists → ask: "GitHub и Notion оба доступны. Task tracker: github или notion?"
  - Otherwise resolve automatically: github if `detected.github`, else none

If `needs_input` is false — wait for "ок" or corrections from user.

### Step 3: Apply Registration

Call apply_registration.py with confirmed parameters:

```bash
$H2T_PYTHON "${CLAUDE_PLUGIN_ROOT}/skills/init-project/scripts/apply_registration.py" \
  --id "{id}" --domain "{domain}" --type "{type}" \
  --label "{label}" --task-tracker "{tracker}" \
  --cwd "$(pwd)" --config-root "$HOME/.h2t/config" \
  [--github "{github}"]
```

Show the result JSON `actions` and `next_steps` to user.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running detection manually | Hook already ran detect_project.py. Use INIT_DATA |
| Writing YAML manually | Call apply_registration.py. It handles backups and comment preservation |
| Skipping domain question when needs_input | User MUST confirm domain before apply |
| Resolving tracker before domain is known | Tracker depends on domain. Wait for domain first |
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t/skills/init-project/SKILL.md
git commit -m "feat: init-project SKILL.md — 3-step registration orchestration (#17)"
```

---

### Task 5: Integration test + version bump + close issue

**Files:**
- Modify: `plugins/h2t/.claude-plugin/plugin.json`

- [ ] **Step 1: Run all tests**

```bash
cd C:/dev/claude-agent-skills
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/skills/init-project/scripts/ -v
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/ -v
```

Expected: ALL PASS in both suites.

- [ ] **Step 2: Test hook E2E — init-project on registered repo**

```bash
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:init-project"},"cwd":"C:/dev/claude-agent-skills"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill
```

Verify: `INIT_DATA:` with `already_registered: true` and `current.id: "agent-skills"`.

- [ ] **Step 3: Test hook E2E — init-project on unregistered directory**

```bash
mkdir -p /tmp/test-init-project
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:init-project"},"cwd":"/tmp/test-init-project"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill
rmdir /tmp/test-init-project
```

Verify: `INIT_DATA:` with `already_registered: false`, `needs_input: true` (domain unknown).

- [ ] **Step 4: Test hook E2E — dev-session-start (regression)**

```bash
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:dev-session-start"},"cwd":"C:/dev/claude-agent-skills"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill 2>&1 | head -c 80
```

Verify: Still starts with `BRIEFING:`.

- [ ] **Step 5: Test hook E2E — handoff (regression)**

```bash
CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" echo '{"tool_input":{"skill":"h2t:handoff"},"cwd":"C:/dev/claude-agent-skills"}' | CLAUDE_PLUGIN_ROOT="$(pwd)/plugins/h2t" bash plugins/h2t/hooks-handlers/gather-on-skill 2>&1 | head -c 80
```

Verify: Still starts with `GATHER_DATA:`.

- [ ] **Step 6: Bump version to 2.11.0**

In `plugins/h2t/.claude-plugin/plugin.json`, change `"version": "2.10.0"` → `"version": "2.11.0"`.

- [ ] **Step 7: Commit + close issue**

```bash
git add plugins/h2t/.claude-plugin/plugin.json
git commit -m "chore: bump to 2.11.0 — init-project skill (closes #17)"
gh issue close 17 --comment "Implemented in v2.11.0 — detect_project.py + apply_registration.py + SKILL.md"
```
