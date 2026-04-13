# Documentation Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 documentation skills в h2t-dev для автоматизации поддержания docs-стандартов в 16 h2t-* репо.

**Architecture:** Shared lib (`plugins/h2t-dev/lib/docs/`) + 4 skills с инкапсулированными скриптами. Паттерн import — как gather.py (sys.path + PLUGIN_ROOT). labels.json bundled в skill data/.

**Tech Stack:** Python 3.11+ stdlib, pyyaml (optional fallback to regex), gh CLI (subprocess), git (subprocess).

**Shell:** bash (Claude Code на Windows).

**ТЗ:** `C:/dev/docs/superpowers/specs/2026-04-13-documentation-skills-tz.md`

**Source scripts:** `C:/dev/docs/standards/scripts/` (портируем, не ссылаемся)

---

## File Structure

```
plugins/h2t-dev/
  lib/
    docs/
      __init__.py
      common.py            # REPO_MANIFEST, tiers, dirs, git/fs helpers (~70 lines)
  skills/
    docs-lint/
      SKILL.md
      scripts/
        lint.py            # verify_standards + validate_frontmatter merged (~150 lines)
    docs-init/
      SKILL.md
      scripts/
        init.py            # scaffold_docs + setup_rules + deploy_linting merged (~120 lines)
    docs-cleanup/
      SKILL.md
      scripts/
        cleanup.py         # новый скрипт (~80 lines)
    docs-sync-labels/
      SKILL.md
      scripts/
        sync_labels.py     # портирование sync_labels.py (~60 lines)
      data/
        labels.json        # копия из C:/dev/docs/standards/labels.json
  commands/
    docs-lint.md
    docs-init.md
    docs-cleanup.md
    docs-sync-labels.md
```

**Import pattern (каждый script):**
```python
import sys
from pathlib import Path

# PLUGIN_ROOT = plugins/h2t-dev/ (4 levels up from scripts/)
_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
# Fallback: repo-level lib for dev/smoke mode (before update-plugin.sh runs)
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import REPO_MANIFEST, repo_path, ...
```

---

## Task 1: Shared lib — `lib/docs/common.py`

**Files:**
- Create: `plugins/h2t-dev/lib/docs/__init__.py`
- Create: `plugins/h2t-dev/lib/docs/common.py`

**Port from:** `C:/dev/docs/standards/scripts/common.py` (68 lines)

- [ ] **Step 1: Create `__init__.py`**

```python
# plugins/h2t-dev/lib/docs/__init__.py
```
Empty file.

- [ ] **Step 2: Create `common.py`**

Port `common.py` with these changes:
- `DEV_ROOT` — read from env `H2T_DEV_ROOT` with fallback to `C:/dev`
- `REPO_MANIFEST` — as-is (16 repos)
- `TIER_A/B/C` — as-is
- `REQUIRED_CORE_DIRS` — as-is
- `STANDARDS_FILES` — move from verify_standards.py here (shared)
- `repo_path()` — as-is
- `git_add_commit()` — as-is
- `ensure_dir()` — as-is
- `print_header()` — replace unicode with ASCII (cp1252 constraint)
- Add `GH` constant: `shutil.which("gh") or "C:/Program Files/GitHub CLI/gh.exe"`
- Add `FRONTMATTER_RULES` dict (from validate_frontmatter.py)

```python
"""Shared utilities for h2t-dev documentation skills."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))

REPO_MANIFEST = [
    "h2t-ai", "h2t-business", "h2t-client", "h2t-content", "h2t-dcc",
    "h2t-evals", "h2t-factory", "h2t-graphs", "h2t-landings", "h2t-skills",
    "h2t-snap", "h2t-staging", "h2t-tools", "h2t-transcription",
    "h2t-vision", "h2t-voice",
]

TIER_A = ["h2t-evals", "h2t-transcription", "h2t-graphs", "h2t-ai", "h2t-vision", "h2t-skills"]
TIER_B = ["h2t-factory", "h2t-snap", "h2t-staging", "h2t-landings", "h2t-dcc", "h2t-voice"]
TIER_C = ["h2t-business", "h2t-client", "h2t-content", "h2t-tools"]

REQUIRED_CORE_DIRS = [
    "docs/superpowers/specs",
    "docs/superpowers/plans",
    "docs/adr",
    "docs/reports",
]

STANDARDS_FILES = [
    "naming-conventions.md", "git-naming-conventions.md",
    "documentation-structure.md", "code-organization.md",
    "api-contracts.md", "adr-process.md", "linting.md", "labels.json",
]

FRONTMATTER_RULES = {
    "superpowers/specs": ["title", "status", "owner", "date"],
    "adr": ["title", "status", "date"],
}

GH = shutil.which("gh") or "C:/Program Files/GitHub CLI/gh.exe"


def repo_path(name: str) -> Path:
    return DEV_ROOT / name


def git_add_commit(repo: Path, paths: list[str], message: str) -> bool:
    for p in paths:
        subprocess.run(["git", "-C", str(repo), "add", "-f", p], check=True)
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if result.returncode == 0:
        return False
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True)
    return True


def ensure_dir(path: Path, gitkeep: bool = True) -> bool:
    if path.exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    if gitkeep:
        (path / ".gitkeep").touch()
    return True


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        import yaml
        return yaml.safe_load(parts[1]) or {}
    except ImportError:
        pass
    fm = {}
    for line in parts[1].strip().splitlines():
        m = re.match(r"(\w+):\s*(.+)", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm
```

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/
git -C C:/dev/h2t-skills commit -m "feat(h2t-dev): add lib/docs/common.py — shared utilities for docs skills"
```

---

## Task 2: docs-lint skill (#65)

**Files:**
- Create: `plugins/h2t-dev/skills/docs-lint/SKILL.md`
- Create: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Create: `plugins/h2t-dev/commands/docs-lint.md`

**Port from:** `verify_standards.py` (114 lines) + `validate_frontmatter.py` (100 lines) -> merged `lint.py`

- [ ] **Step 1: Create `lint.py`**

Merge verify_standards + validate_frontmatter into one script. Also adds:
- `projects.yaml` cross-check (conditional docs flags vs actual files)
- `pymarkdownlnt` runner (if installed in PATH)

Output format:
```
--- h2t-graphs ---
  OK: dirs (4/4)
  OK: docs/README.md
  FAIL: .pymarkdown.yaml missing
  OK: frontmatter (12 files checked)
  FAIL: docs/superpowers/specs/foo.md: missing field 'status'
  OK: pymarkdownlnt (42 files clean)
```

Exit code 0 = all pass, 1 = failures found.

`projects.yaml` flag → required file mapping (from design spec):
```python
PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

YAML_FLAG_CHECKS = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report":  "docs/reports",        # dir must be non-empty
    "docs.marketing_docs": "docs/marketing",
}
```

```python
#!/usr/bin/env python3
"""Documentation standards linter for h2t repos."""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, STANDARDS_FILES,
    FRONTMATTER_RULES, ensure_dir, print_header, repo_path, parse_frontmatter,
)

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

YAML_FLAG_CHECKS: dict[str, str] = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report": "docs/reports",
    "docs.marketing_docs": "docs/marketing",
}


def _load_projects_yaml() -> dict:
    if not PROJECTS_YAML_PATH.exists():
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return {}  # skip cross-check if no yaml


def _get_flag(project_data: dict, dotted_key: str) -> bool:
    """Walk nested dict by dot-separated key."""
    parts = dotted_key.split(".")
    node = project_data
    for p in parts:
        if not isinstance(node, dict):
            return False
        node = node.get(p, False)
    return bool(node)


def check_projects_yaml(rp: Path, name: str, projects: dict) -> list[str]:
    """Cross-check projects.yaml flags vs actual files."""
    if not projects:
        return []
    project_data = projects.get(name, {})
    if not project_data:
        return []
    failures = []
    for flag, required_path in YAML_FLAG_CHECKS.items():
        if _get_flag(project_data, flag):
            target = rp / required_path
            if not target.exists():
                failures.append(f"projects.yaml {flag}=true but missing: {required_path}")
    return failures


def check_structure(rp: Path) -> list[str]:
    failures = []
    for rel_dir in REQUIRED_CORE_DIRS:
        if not (rp / rel_dir).exists():
            failures.append(f"missing dir: {rel_dir}/")
    for name, path in [
        ("docs/README.md", rp / "docs" / "README.md"),
        (".claude/rules/documentation.md", rp / ".claude" / "rules" / "documentation.md"),
        (".pymarkdown.yaml", rp / ".pymarkdown.yaml"),
        (".vale.ini", rp / ".vale.ini"),
    ]:
        if not path.exists():
            failures.append(f"missing: {name}")
    return failures


def check_adr_naming(rp: Path) -> list[str]:
    failures = []
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return failures
    for adr in adr_dir.glob("[0-9]*.md"):
        if not re.match(r"^\d{4}-", adr.name):
            failures.append(f"ADR naming: {adr.name} (expected 4-digit prefix)")
    return failures


def check_frontmatter(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return failures
    for md_file in docs_dir.rglob("*.md"):
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern not in rel or not required_fields:
                continue
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            if fm is None:
                failures.append(f"{rel}: missing frontmatter")
                break
            for field in required_fields:
                if field not in fm:
                    failures.append(f"{rel}: missing field '{field}'")
    return failures


def run_pymarkdownlnt(rp: Path) -> list[str]:
    """Run pymarkdownlnt if available. Returns list of failure lines."""
    pymdl = shutil.which("pymarkdownlnt") or shutil.which("pymarkdown")
    if not pymdl:
        return []  # not installed — skip silently
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []
    result = subprocess.run(
        [pymdl, "scan", str(docs_dir)],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode != 0:
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        return [f"pymarkdownlnt: {ln}" for ln in lines[:20]]  # cap output
    return []


def fix_structure(rp: Path) -> list[str]:
    fixes = []
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if ensure_dir(d):
            fixes.append(f"created: {rel_dir}/")
    return fixes


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint documentation standards")
    parser.add_argument("repos", nargs="*", help="Repos to check (default: all 16)")
    parser.add_argument("--fix", action="store_true", help="Create missing dirs")
    parser.add_argument("--no-pymarkdown", action="store_true", help="Skip pymarkdownlnt")
    args = parser.parse_args()

    targets = args.repos or REPO_MANIFEST
    print_header(f"docs-lint: checking {len(targets)} repos")

    # Load projects.yaml for cross-check
    projects = _load_projects_yaml()

    # Global standards check
    print("\n--- Global Standards ---")
    std_dir = DEV_ROOT / "docs" / "standards"
    std_fails = [f for f in STANDARDS_FILES if not (std_dir / f).exists()]
    if std_fails:
        for f in std_fails:
            print(f"  FAIL: missing {f}")
    else:
        print(f"  OK: all {len(STANDARDS_FILES)} standards files present")

    total_failures = len(std_fails)

    for name in targets:
        rp = repo_path(name)
        if not rp.exists():
            print(f"\n--- {name} ---\n  SKIP: repo not found at {rp}")
            continue

        print(f"\n--- {name} ---")

        if args.fix:
            fixes = fix_structure(rp)
            for f in fixes:
                print(f"  FIX: {f}")

        failures = (
            check_structure(rp)
            + check_adr_naming(rp)
            + check_frontmatter(rp)
            + check_projects_yaml(rp, name, projects)
            + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
        )
        if failures:
            for f in failures:
                print(f"  FAIL: {f}")
            total_failures += len(failures)
        else:
            print("  OK: all checks passed")

    print(f"\n{'=' * 60}")
    if total_failures:
        print(f"  RESULT: {total_failures} issue(s) found")
        sys.exit(1)
    else:
        print(f"  RESULT: all {len(targets)} repos compliant")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create SKILL.md**

```markdown
---
name: docs-lint
description: This skill should be used when the user asks to "check docs", "lint documentation", "verify standards", "docs compliance", "are docs up to standard", or wants to audit documentation structure and frontmatter across h2t repos.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

Run documentation standards compliance check across h2t repos.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
```

## Usage

Check all 16 repos:
```bash
$H2T_PYTHON "$LINT"
```

Check specific repo:
```bash
$H2T_PYTHON "$LINT" h2t-graphs
```

Fix missing dirs:
```bash
$H2T_PYTHON "$LINT" --fix h2t-graphs
```

## Output

Show the full lint output to the user. If there are failures, suggest specific fixes.
```

- [ ] **Step 3: Create command**

Format matches existing `plugins/h2t-dev/commands/*.md`:
```markdown
---
description: "Docs lint: check documentation standards compliance across h2t repos. Triggers: 'check docs', 'lint docs', 'verify standards'."
---

Use the h2t-dev:docs-lint skill.
```

- [ ] **Step 4: Test**

```bash
$HOME/.h2t/venv/Scripts/python.exe plugins/h2t-dev/skills/docs-lint/scripts/lint.py h2t-graphs
```

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/ plugins/h2t-dev/commands/docs-lint.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-dev): docs-lint skill — compliance checker (#65)"
```

---

## Task 3: docs-init skill (#66)

**Files:**
- Create: `plugins/h2t-dev/skills/docs-init/SKILL.md`
- Create: `plugins/h2t-dev/skills/docs-init/scripts/init.py`
- Create: `plugins/h2t-dev/commands/docs-init.md`

**Port from:** `scaffold_docs.py` + `setup_rules.py` + `deploy_linting.py` -> merged `init.py`

- [ ] **Step 1: Create `init.py`**

Merge 3 scripts. Operations:
1. Read `projects.yaml` for repo metadata and conditional dir flags
2. Create required core dirs + .gitkeep
3. Create conditional dirs based on `projects.yaml` flags (product/, client/, marketing/, etc.)
4. Create `docs/README.md` from template
5. Create `.claude/rules/documentation.md`
6. Create `.pymarkdown.yaml` + `.vale.ini`
7. Add `docs/.artifacts/` to `.gitignore` (create file if missing)

All operations idempotent (skip if exists). Default `--dry-run`. Explicit `--apply` to write.

`projects.yaml` flag → conditional dir mapping:
```python
CONDITIONAL_DIRS: dict[str, str] = {
    "docs.positioning": "docs/product",
    "docs.marketing_docs": "docs/marketing",
    "docs.architecture": "docs/architecture",
    "docs.client_api": "docs/client",
    "docs.guides": "docs/guides",
    "docs.research": "docs/research",
    "docs.artifacts": "docs/.artifacts",
}
```

```python
#!/usr/bin/env python3
"""Scaffold standard docs/ structure for h2t repos."""

import argparse
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT, REQUIRED_CORE_DIRS, ensure_dir, git_add_commit, print_header, repo_path,
)

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

CONDITIONAL_DIRS: dict[str, str] = {
    "docs.positioning": "docs/product",
    "docs.marketing_docs": "docs/marketing",
    "docs.architecture": "docs/architecture",
    "docs.client_api": "docs/client",
    "docs.guides": "docs/guides",
    "docs.research": "docs/research",
    "docs.artifacts": "docs/.artifacts",
}


def _load_project(name: str) -> dict:
    if not PROJECTS_YAML_PATH.exists():
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        data = yaml.safe_load(text) or {}
        return data.get(name, {})
    except ImportError:
        return {}

MINIMAL_README = """\
# {name} Documentation

## Quick Links

| Section | Description |
|---------|-------------|
| [Specs & Plans](superpowers/) | Design specs and implementation plans |
| [ADRs](adr/) | Architectural decisions |
| [Reports](reports/) | Milestone reports |
"""

RULES_TEMPLATE = """\
# Documentation Rules

Follow standards defined in C:/dev/docs/standards/:
- Directory structure: documentation-structure.md
- Naming: naming-conventions.md
- Git conventions: git-naming-conventions.md
- ADR process: adr-process.md
- Linting: linting.md

All documentation goes in docs/ with the standard subdirectory layout.
"""

PYMARKDOWN_YAML = """\
plugins:
  md013:
    enabled: false
  md033:
    enabled: false
  md041:
    enabled: false
"""

VALE_INI = """\
StylesPath = .vale/styles
MinAlertLevel = warning

[docs/**/*.md]
BasedOnStyles = Vale
"""


def init_repo(name: str, *, dry_run: bool = True, commit: bool = False) -> list[str]:
    rp = repo_path(name)
    if not rp.exists():
        print(f"  ERROR: {rp} not found")
        return []

    project_data = _load_project(name)
    changes = []
    action = "would create" if dry_run else "created"

    # Required core dirs
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if not d.exists():
            if not dry_run:
                ensure_dir(d)
            print(f"  {action}: {rel_dir}/")
            changes.append(rel_dir)

    # Conditional dirs from projects.yaml
    for flag, rel_dir in CONDITIONAL_DIRS.items():
        parts = flag.split(".")
        node = project_data
        for p in parts:
            node = node.get(p, False) if isinstance(node, dict) else False
        if node:
            d = rp / rel_dir
            if not d.exists():
                if not dry_run:
                    ensure_dir(d)
                print(f"  {action}: {rel_dir}/ (from projects.yaml {flag}=true)")
                changes.append(rel_dir)

    # docs/README.md
    readme = rp / "docs" / "README.md"
    if not readme.exists():
        if not dry_run:
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(MINIMAL_README.format(name=name), encoding="utf-8")
        print(f"  {action}: docs/README.md")
        changes.append("docs/README.md")

    # .claude/rules/documentation.md
    rules_file = rp / ".claude" / "rules" / "documentation.md"
    if not rules_file.exists():
        if not dry_run:
            rules_file.parent.mkdir(parents=True, exist_ok=True)
            rules_file.write_text(RULES_TEMPLATE, encoding="utf-8")
        print(f"  {action}: .claude/rules/documentation.md")
        changes.append(".claude/rules/documentation.md")

    # .pymarkdown.yaml
    pm = rp / ".pymarkdown.yaml"
    if not pm.exists():
        if not dry_run:
            pm.write_text(PYMARKDOWN_YAML, encoding="utf-8")
        print(f"  {action}: .pymarkdown.yaml")
        changes.append(".pymarkdown.yaml")

    # .vale.ini
    vale = rp / ".vale.ini"
    if not vale.exists():
        if not dry_run:
            vale.write_text(VALE_INI, encoding="utf-8")
        print(f"  {action}: .vale.ini")
        changes.append(".vale.ini")

    # .gitignore — create if missing, append entry if needed
    gi = rp / ".gitignore"
    gi_entry = "docs/.artifacts/"
    gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if gi_entry not in gi_content:
        if not dry_run:
            with open(gi, "a", encoding="utf-8") as f:
                f.write(f"\n# Documentation artifacts\n{gi_entry}\n")
        print(f"  {action}: .gitignore entry for {gi_entry}")
        changes.append(".gitignore")

    if changes and not dry_run and commit:
        git_add_commit(rp, ["docs/", ".claude/", ".pymarkdown.yaml", ".vale.ini", ".gitignore"],
                       "docs: scaffold standard documentation structure")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold docs/ structure")
    parser.add_argument("repo", help="Repo name (e.g. h2t-graphs)")
    parser.add_argument("--apply", action="store_true", help="Actually create files (default: dry-run)")
    parser.add_argument("--commit", action="store_true", help="Git commit after apply")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-init [{mode}]: {args.repo}")
    changes = init_repo(args.repo, dry_run=not args.apply, commit=args.commit)

    if not changes:
        print("\n  Nothing to do -- all files already exist")
    elif not args.apply:
        print(f"\n  {len(changes)} changes pending. Run with --apply to create.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create SKILL.md**

Pipeline skill:
1. Run `init.py <repo>` (dry-run)
2. Show changes to user
3. GATE: ask user to confirm
4. Run `init.py <repo> --apply --commit`

- [ ] **Step 3: Create command**

```markdown
---
description: "Docs init: scaffold standard docs/ structure for h2t repo. Triggers: 'init docs', 'setup docs structure', 'scaffold documentation'."
---

Use the h2t-dev:docs-init skill.
```

- [ ] **Step 4: Test, commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-init/ plugins/h2t-dev/commands/docs-init.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-dev): docs-init skill — scaffold docs structure (#66)"
```

---

## Task 4: docs-cleanup skill (#67)

**Files:**
- Create: `plugins/h2t-dev/skills/docs-cleanup/SKILL.md`
- Create: `plugins/h2t-dev/skills/docs-cleanup/scripts/cleanup.py`
- Create: `plugins/h2t-dev/commands/docs-cleanup.md`

**New script** (no existing source to port).

- [ ] **Step 1: Create `cleanup.py`**

Operations:
1. Find plans older than `--days` in `docs/superpowers/plans/`
2. Find specs with `status: implemented` in frontmatter
3. Show `docs/.artifacts/` size (with `--clean-artifacts` flag to wipe)
4. Default: dry-run (show what would move). `--apply` to execute `git mv` + commit.
5. After archiving: update `docs/README.md` (append archive note)
6. Commit message: `docs: archive M{milestone} documents` (milestone from `--milestone` arg, default "N")

Notes vs plan v1:
- `repo` is positional (default: current repo from `git rev-parse`)
- `--apply` executes moves; default is show-only (dry-run implied, no explicit flag needed)
- Commit message format matches ТЗ: `docs: archive M{N} documents`

```python
#!/usr/bin/env python3
"""Find and archive stale documentation."""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import parse_frontmatter, print_header, repo_path


def _current_repo_name() -> str | None:
    """Detect repo name from cwd via git remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip().rstrip("/").split("/")[-1].removesuffix(".git")
    return None


def find_stale_plans(rp: Path, max_age_days: int = 30) -> list[Path]:
    stale = []
    plans_dir = rp / "docs" / "superpowers" / "plans"
    if not plans_dir.exists():
        return stale
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for f in plans_dir.glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m:
            try:
                if datetime.strptime(m.group(1), "%Y-%m-%d") < cutoff:
                    stale.append(f)
            except ValueError:
                pass
    return sorted(stale)


def find_implemented_specs(rp: Path) -> list[Path]:
    specs_dir = rp / "docs" / "superpowers" / "specs"
    if not specs_dir.exists():
        return []
    implemented = []
    for f in specs_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm and fm.get("status") in ("implemented", "done", "completed"):
            implemented.append(f)
    return sorted(implemented)


def artifacts_size(rp: Path) -> int:
    art = rp / "docs" / ".artifacts"
    if not art.exists():
        return 0
    return sum(f.stat().st_size for f in art.rglob("*") if f.is_file())


def update_readme(rp: Path, archived: list[tuple[Path, Path]], milestone: str) -> None:
    """Append archive section to docs/README.md if it exists."""
    readme = rp / "docs" / "README.md"
    if not readme.exists():
        return
    note = f"\n\n## Archived (M{milestone})\n\n"
    for src, dest in archived:
        note += f"- {src.name} -> {dest.relative_to(rp)}\n"
    with open(readme, "a", encoding="utf-8") as f:
        f.write(note)


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive stale docs")
    parser.add_argument("repo", nargs="?", help="Repo name (default: current repo)")
    parser.add_argument("--apply", action="store_true", help="Execute git mv + commit")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--milestone", default="N", help="Milestone label for commit message")
    parser.add_argument("--clean-artifacts", action="store_true",
                        help="Delete docs/.artifacts/ contents (requires --apply)")
    args = parser.parse_args()

    name = args.repo or _current_repo_name()
    if not name:
        print("ERROR: cannot determine repo name. Pass repo as argument.")
        sys.exit(1)

    rp = repo_path(name)
    if not rp.exists():
        print(f"ERROR: {rp} not found")
        sys.exit(1)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-cleanup [{mode}]: {name}")

    archive_dir = rp / "docs" / "archive"
    candidates: list[tuple[Path, Path]] = []

    stale = find_stale_plans(rp, args.days)
    if stale:
        print(f"\n  Stale plans (>{args.days} days): {len(stale)}")
        for f in stale:
            rel = f.relative_to(rp)
            dest = archive_dir / rel.relative_to("docs")
            candidates.append((f, dest))
            print(f"    {rel}")

    implemented = find_implemented_specs(rp)
    if implemented:
        print(f"\n  Implemented specs: {len(implemented)}")
        for f in implemented:
            rel = f.relative_to(rp)
            dest = archive_dir / rel.relative_to("docs")
            candidates.append((f, dest))
            print(f"    {rel}")

    art_bytes = artifacts_size(rp)
    if art_bytes > 0:
        print(f"\n  docs/.artifacts/: {art_bytes / 1024:.1f} KB")
        if args.clean_artifacts and not args.apply:
            print("  (use --clean-artifacts --apply to delete)")

    if not candidates and not (args.clean_artifacts and art_bytes > 0):
        print("\n  Nothing to do.")
        return

    if not args.apply:
        if candidates:
            print(f"\n  {len(candidates)} files to archive. Run with --apply to execute.")
        return

    # Execute moves
    if candidates:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for src, dest in candidates:
            dest.parent.mkdir(parents=True, exist_ok=True)
            rel_src = src.relative_to(rp)
            rel_dest = dest.relative_to(rp)
            subprocess.run(["git", "-C", str(rp), "mv", str(rel_src), str(rel_dest)], check=True)
            print(f"    moved: {rel_src} -> {rel_dest}")

        update_readme(rp, candidates, args.milestone)

        subprocess.run(
            ["git", "-C", str(rp), "commit", "-m",
             f"docs: archive M{args.milestone} documents"],
            check=True,
        )
        print(f"\n  Archived {len(candidates)} files.")

    # Clean artifacts
    if args.clean_artifacts and art_bytes > 0:
        art_dir = rp / "docs" / ".artifacts"
        shutil.rmtree(art_dir)
        art_dir.mkdir()
        (art_dir / ".gitkeep").touch()
        print(f"  Cleared docs/.artifacts/ ({art_bytes / 1024:.1f} KB freed)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create SKILL.md** (pipeline: dry-run -> show -> GATE -> apply)
- [ ] **Step 3: Create command** (same format as github-issues.md):

```markdown
---
description: "Docs cleanup: find and archive stale plans and implemented specs. Triggers: 'archive docs', 'cleanup docs', 'close milestone docs'."
---

Use the h2t-dev:docs-cleanup skill.
```

- [ ] **Step 4: Test, commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-cleanup/ plugins/h2t-dev/commands/docs-cleanup.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-dev): docs-cleanup skill — archive stale docs (#67)"
```

---

## Task 5: docs-sync-labels skill (#68)

**Files:**
- Create: `plugins/h2t-dev/skills/docs-sync-labels/SKILL.md`
- Create: `plugins/h2t-dev/skills/docs-sync-labels/scripts/sync_labels.py`
- Create: `plugins/h2t-dev/skills/docs-sync-labels/data/labels.json`
- Create: `plugins/h2t-dev/commands/docs-sync-labels.md`

**Port from:** `sync_labels.py` (76 lines) + bundle `labels.json`

- [ ] **Step 1: Copy `labels.json`** from `C:/dev/docs/standards/labels.json`

- [ ] **Step 2: Create `sync_labels.py`**

Changes from original:
- Import common via PLUGIN_ROOT pattern
- Load `labels.json` from `data/` dir relative to script (not DEV_ROOT)
- Default dry-run, `--apply` to execute

```python
#!/usr/bin/env python3
"""Sync canonical labels to GitHub repos via gh CLI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import GH, REPO_MANIFEST, print_header

LABELS_FILE = Path(__file__).resolve().parent.parent / "data" / "labels.json"
ORG = "lichtpfad"


def sync_repo(repo_name: str, labels: dict, *, dry_run: bool = True) -> int:
    errors = 0
    for category, label_list in labels.items():
        for label in label_list:
            cmd = [
                GH, "label", "create", label["name"],
                "--color", label["color"],
                "--description", label["description"],
                "--repo", f"{ORG}/{repo_name}",
                "--force",
            ]
            if dry_run:
                print(f"  {label['name']} ({category})")
                continue
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  FAIL: {label['name']} -- {result.stderr.strip()}", file=sys.stderr)
                errors += 1
            else:
                print(f"  OK: {label['name']}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync labels to GitHub repos")
    parser.add_argument("repos", nargs="*", help="Repos (default: all 16)")
    parser.add_argument("--apply", action="store_true", help="Actually sync (default: dry-run)")
    args = parser.parse_args()

    targets = args.repos or REPO_MANIFEST
    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-sync-labels [{mode}]: {len(targets)} repos")

    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    total = sum(len(v) for v in labels.values())
    print(f"  {total} labels from {LABELS_FILE.name}\n")

    total_errors = 0
    for name in targets:
        print(f"--- {name} ---")
        errors = sync_repo(name, labels, dry_run=not args.apply)
        total_errors += errors

    if not args.apply:
        print(f"\n  Dry-run complete. Run with --apply to sync.")
    elif total_errors:
        print(f"\n  FAILED: {total_errors} label(s) failed")
        sys.exit(1)
    else:
        print(f"\n  All repos synced.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create SKILL.md**

- [ ] **Step 4: Create command**

```markdown
---
description: "Docs sync-labels: sync canonical GitHub labels from labels.json to h2t repos. Triggers: 'sync labels', 'update github labels', 'add missing labels'."
---

Use the h2t-dev:docs-sync-labels skill.
```

- [ ] **Step 5: Test, commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-sync-labels/ plugins/h2t-dev/commands/docs-sync-labels.md
git -C C:/dev/h2t-skills commit -m "feat(h2t-dev): docs-sync-labels skill — sync canonical labels (#68)"
```

---

## Task 6: Integration test

- [ ] **Step 1: Run docs-lint on all repos**

```bash
$HOME/.h2t/venv/Scripts/python.exe plugins/h2t-dev/skills/docs-lint/scripts/lint.py
```

- [ ] **Step 2: Run docs-init dry-run on one repo**

```bash
$HOME/.h2t/venv/Scripts/python.exe plugins/h2t-dev/skills/docs-init/scripts/init.py h2t-tools
```

- [ ] **Step 3: Run docs-sync-labels dry-run**

```bash
$HOME/.h2t/venv/Scripts/python.exe plugins/h2t-dev/skills/docs-sync-labels/scripts/sync_labels.py h2t-graphs
```

- [ ] **Step 4: Run docs-cleanup dry-run**

```bash
$HOME/.h2t/venv/Scripts/python.exe plugins/h2t-dev/skills/docs-cleanup/scripts/cleanup.py h2t-skills
```

---

## Task 7: Update h2t-dev README

After all skills are implemented, update `plugins/h2t-dev/README.md` (or `docs/README.md`) to document the 4 new skills.

- [ ] Add entries for docs-lint, docs-init, docs-cleanup, docs-sync-labels
- [ ] Include: purpose, key args, example invocation
- [ ] Commit: `docs(h2t-dev): document docs-* skills in README`

---

## Execution Order

```
Task 1 (shared lib)        -- блокирует все остальные
  |
  +-- Task 2 (docs-lint)   -- параллельно с 3, 4, 5
  +-- Task 3 (docs-init)
  +-- Task 4 (docs-cleanup)
  +-- Task 5 (docs-sync-labels)
  |
Task 6 (integration test)  -- после всех
  |
Task 7 (README update)     -- финальный шаг
```

Task 1 один субагент. Tasks 2-5 параллельно после Task 1. Task 6 финальная проверка. Task 7 — документация.
