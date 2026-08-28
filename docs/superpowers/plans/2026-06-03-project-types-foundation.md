---
title: "project_types Foundation — Implementation Plan"
status: "draft"
date: "2026-06-03"
milestone: ""
issue: ""
---
# project_types Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `plugins/h2t-dev/lib/docs/project_types.py` as single source of truth for per-project-type directory structures, and refactor `scaffold_project.py` + `init.py` to read from it instead of maintaining separate local dicts.

**Architecture:** A new shared module in `plugins/h2t-dev/lib/docs/project_types.py` defines `PROJECT_TYPES` (root dirs + docs dirs per template), `SCAFFOLD_TYPE_TO_TEMPLATE` (CLI type → template name), and `detect_template()` (type discovery from `.claude/rules/docs-lint.yaml` or file presence). Both `init.py` and `scaffold_project.py` drop their local dicts and import from this module. **Intentional behaviour changes:** `code_repo` gains `scripts/` root dir; `research_project` drops `research/` from root (moves to `docs/research`); `creative_project` retains `docs/assets` in docs_dirs. `.gitignore` template selection via `type_base` is preserved independently of the PROJECT_TYPES import path.

**Tech Stack:** Python stdlib only. No new dependencies.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `plugins/h2t-dev/lib/docs/project_types.py` | Per-type structure definitions |
| Modify | `plugins/h2t-dev/skills/docs-init/scripts/init.py` | Remove `TEMPLATE_EXTRA_DIRS`, import lib |
| Modify | `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | Remove `DIR_STRUCTURE` + `TYPE_TO_TEMPLATE`, add lib path, import lib |
| Create | `tests/docs/test_project_types.py` | Tests for the new module |

---

## Task 1: Create `lib/docs/project_types.py`

**Files:**
- Create: `plugins/h2t-dev/lib/docs/project_types.py`
- Test: `tests/docs/test_project_types.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_project_types.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.project_types import (
    PROJECT_TYPES,
    SCAFFOLD_TYPE_TO_TEMPLATE,
    detect_template,
)


def test_all_templates_have_required_keys():
    for name, spec in PROJECT_TYPES.items():
        assert "root_dirs" in spec, f"{name} missing root_dirs"
        assert "docs_dirs" in spec, f"{name} missing docs_dirs"
        assert "root_files_required" in spec, f"{name} missing root_files_required"
        assert isinstance(spec["root_dirs"], list), f"{name}.root_dirs must be list"
        assert isinstance(spec["docs_dirs"], list), f"{name}.docs_dirs must be list"


def test_scaffold_type_to_template_covers_all_scaffold_types():
    expected = {"code-github", "code-local", "docs", "dcc", "directory"}
    assert set(SCAFFOLD_TYPE_TO_TEMPLATE.keys()) == expected


def test_scaffold_type_to_template_maps_to_known_templates():
    for t, tmpl in SCAFFOLD_TYPE_TO_TEMPLATE.items():
        assert tmpl in PROJECT_TYPES, f"{t} maps to unknown template {tmpl}"


def test_detect_template_reads_docs_lint_yaml(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: creative_project\n"
    )
    assert detect_template(tmp_path) == "creative_project"


def test_detect_template_ignores_unknown_template_in_yaml(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "template: nonexistent_type\n"
    )
    result = detect_template(tmp_path)
    assert result in PROJECT_TYPES


def test_detect_template_fallback_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert detect_template(tmp_path) == "code_repo"


def test_detect_template_fallback_deliverables(tmp_path):
    (tmp_path / "deliverables").mkdir()
    assert detect_template(tmp_path) == "client_project"


def test_detect_template_default(tmp_path):
    assert detect_template(tmp_path) == "code_repo"


def test_no_docs_dir_duplicates_required_core():
    """docs_dirs must not repeat REQUIRED_CORE_DIRS entries."""
    required = {
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        "docs/adr",
        "docs/reports",
    }
    for name, spec in PROJECT_TYPES.items():
        for d in spec["docs_dirs"]:
            assert d not in required, (
                f"{name}.docs_dirs contains {d} which is already in REQUIRED_CORE_DIRS"
            )
```

- [ ] **Step 2: Run to confirm tests fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.project_types'`

- [ ] **Step 3: Write `project_types.py`**

```python
# plugins/h2t-dev/lib/docs/project_types.py
"""Per-project-type directory structure definitions.

Single source of truth consumed by:
  - docs-init (docs/ subdirs to scaffold per template)
  - scaffold-project (root dirs to create per type)
  - docs-lint (structure compliance checks, future)
"""
from __future__ import annotations
from pathlib import Path
from typing import TypedDict


class ProjectTypeSpec(TypedDict):
    root_dirs: list[str]        # dirs to create at project root
    docs_dirs: list[str]        # dirs inside docs/ beyond REQUIRED_CORE_DIRS
    root_files_required: list[str]


PROJECT_TYPES: dict[str, ProjectTypeSpec] = {
    "code_repo": {
        "root_dirs": ["src", "tests", "docs", "scripts"],
        "docs_dirs": [],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "client_project": {
        "root_dirs": ["docs", "data", "deliverables", "scripts"],
        "docs_dirs": ["docs/ops", "docs/research", "docs/deliverables"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "research_project": {
        "root_dirs": ["docs", "data"],
        "docs_dirs": ["docs/research"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "creative_project": {
        "root_dirs": ["assets", "scripts", "exports", "docs"],
        "docs_dirs": ["docs/assets", "docs/briefs", "docs/reviews"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "personal_os": {
        "root_dirs": ["docs"],
        "docs_dirs": ["docs/notes", "docs/sessions"],
        "root_files_required": [],
    },
    "ops_workflow": {
        "root_dirs": ["docs", "scripts"],
        "docs_dirs": ["docs/runbooks", "docs/logs"],
        "root_files_required": ["README.md"],
    },
}

# Maps scaffold --type arg to template name
SCAFFOLD_TYPE_TO_TEMPLATE: dict[str, str] = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}


def detect_template(repo_root: Path) -> str:
    """Detect project template name for an existing repo.

    Priority:
    1. .claude/rules/docs-lint.yaml template field (written by docs-init)
    2. File-presence heuristics
    3. Default: code_repo
    """
    cfg = repo_root / ".claude" / "rules" / "docs-lint.yaml"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("template:"):
                name = line.split(":", 1)[1].strip()
                if name in PROJECT_TYPES:
                    return name

    if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.py").exists():
        return "code_repo"
    if (repo_root / "package.json").exists():
        return "code_repo"
    if (repo_root / "deliverables").exists():
        return "client_project"
    if (repo_root / "assets").exists() and (repo_root / "scripts").exists():
        return "creative_project"

    return "code_repo"
```

- [ ] **Step 4: Run tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py -v
```

Expected: all 9 PASSED.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/project_types.py tests/docs/test_project_types.py
git -C C:/dev/h2t-skills commit -m "feat(docs): add project_types lib — single source of truth for per-type structure"
```

---

## Task 2: Refactor `init.py` — use `project_types.py`

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-init/scripts/init.py`
- Test: `tests/docs/test_docs_init_repo_root.py` (existing, must still pass)

- [ ] **Step 1: Verify existing tests pass before touching anything**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py -v
```

Expected: all PASSED. If not — stop and investigate before proceeding.

- [ ] **Step 2: Edit `init.py`**

Remove `TEMPLATE_EXTRA_DIRS` dict and replace its one usage in `init_repo()`.

In the import block (after the existing `sys.path` setup for lib):
```python
# add after the existing lib path setup at top of file
from docs.project_types import PROJECT_TYPES
```

Replace the `TEMPLATE_EXTRA_DIRS` dict definition (delete it entirely).

Replace the usage in `init_repo()`:
```python
# OLD:
    for rel_dir in TEMPLATE_EXTRA_DIRS.get(template, []):

# NEW:
    for rel_dir in PROJECT_TYPES.get(template, {}).get("docs_dirs", []):
```

The `--template` choices in `main()` must stay in sync with `PROJECT_TYPES` keys. Update to:
```python
    parser.add_argument("--template", default="code_repo", choices=list(PROJECT_TYPES))
```

- [ ] **Step 3: Run existing tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py -v
```

Expected: all PASSED.

- [ ] **Step 4: Run full docs test suite to check for regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-init/scripts/init.py
git -C C:/dev/h2t-skills commit -m "refactor(docs-init): replace TEMPLATE_EXTRA_DIRS with PROJECT_TYPES from lib"
```

> Note: h2t-dev version bump happens in Task 3 Step 8 alongside h2t-core — single bump covers both init.py and scaffold changes.

---

## Task 3: Refactor `scaffold_project.py` — use `project_types.py`

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Test: `tests/scaffold/test_scaffold_steps.py` (existing, must still pass)

- [ ] **Step 1: Verify existing tests pass before touching anything**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v
```

Expected: all PASSED. If not — stop.

- [ ] **Step 2: Add lib path setup and import to `scaffold_project.py`**

After the existing imports, add before the constants block:

```python
# lib path: plugins/h2t-core → plugins → h2t-dev/lib (sibling plugin lib)
_SCAFFOLD_SCRIPT = Path(__file__).resolve()
_H2T_DEV_LIB = _SCAFFOLD_SCRIPT.parents[3].parent / "h2t-dev" / "lib"
if _H2T_DEV_LIB.exists() and str(_H2T_DEV_LIB) not in sys.path:
    sys.path.insert(0, str(_H2T_DEV_LIB))

try:
    from docs.project_types import PROJECT_TYPES, SCAFFOLD_TYPE_TO_TEMPLATE
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    _PROJECT_TYPES_AVAILABLE = False
    PROJECT_TYPES = {}
    SCAFFOLD_TYPE_TO_TEMPLATE = {}
```

The `try/except` is a safety net: scaffold must still work if the lib is missing (e.g. running from cache before the plugin is updated). Fallback preserves **exactly** the current `DIR_STRUCTURE` values so cache-runs produce no unexpected changes.

- [ ] **Step 3: Replace `DIR_STRUCTURE` and `TYPE_TO_TEMPLATE`**

Keep the local dicts as fallbacks but gate them:

```python
# Local fallbacks — exact copy of old DIR_STRUCTURE/TYPE_TO_TEMPLATE
# Used only when project_types lib is unavailable (stale cache run)
_DIR_STRUCTURE_FALLBACK: dict[str, list[str]] = {
    "code": ["src", "tests", "docs"],
    "docs": ["docs", "research"],
    "dcc": ["assets", "scripts", "exports"],
    "directory": [],
}

_TYPE_TO_TEMPLATE_FALLBACK: dict[str, str] = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}
```

Delete the old `DIR_STRUCTURE` and `TYPE_TO_TEMPLATE` dicts (they are replaced by the fallbacks above and the lib import above).

- [ ] **Step 4: Update `template_for_type()` and `cmd_create()`**

`template_for_type()` currently reads from `TYPE_TO_TEMPLATE`. Update:

```python
def template_for_type(project_type: str) -> str:
    mapping = SCAFFOLD_TYPE_TO_TEMPLATE if _PROJECT_TYPES_AVAILABLE else _TYPE_TO_TEMPLATE_FALLBACK
    return mapping.get(project_type, "code_repo")
```

In `cmd_create()`, replace `DIR_STRUCTURE` usage:

```python
# OLD:
    type_base = args.type.split("-")[0]  # "code-github" -> "code"
    dirs = DIR_STRUCTURE.get(type_base, [])

# NEW:
    template = template_for_type(args.type)
    if _PROJECT_TYPES_AVAILABLE:
        dirs = PROJECT_TYPES.get(template, {}).get("root_dirs", [])
    else:
        type_base = args.type.split("-")[0]
        dirs = _DIR_STRUCTURE_FALLBACK.get(type_base, [])
```

Note: `template` is already computed later in `cmd_create()` — move the `template = template_for_type(args.type)` line up to replace the `type_base` computation.

The full updated `cmd_create()` beginning (replace through `is_git =`):

```python
def cmd_create(args: argparse.Namespace) -> dict:
    base = Path(args.dir).expanduser().resolve()
    project_dir = base / args.id
    type_base = args.type.split("-")[0]   # keep for .gitignore selection (DCC_GITIGNORE)
    template = template_for_type(args.type)
    if _PROJECT_TYPES_AVAILABLE:
        dirs = PROJECT_TYPES.get(template, {}).get("root_dirs", [])
    else:
        dirs = _DIR_STRUCTURE_FALLBACK.get(type_base, [])
    is_git = args.type in ("code-github", "code-local")
```

Remove the old `template = template_for_type(args.type)` line that follows (it is now above). Keep `type_base` — it is still used for `.gitignore` template selection later in `cmd_create()`.

- [ ] **Step 5: Add `cmd_create()` tests**

Add to `tests/scaffold/test_scaffold_steps.py`:

```python
from unittest.mock import patch, MagicMock
import scaffold_project


def test_cmd_create_code_repo_root_dirs(tmp_path, monkeypatch):
    """code-github creates src, tests, docs, scripts at root."""
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "skip"}):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                import argparse
                args = argparse.Namespace(
                    id="test-proj", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False,
                )
                result = scaffold_project.cmd_create(args)
    assert result["status"] == "ok"
    proj = tmp_path / "test-proj"
    assert (proj / "src").exists()
    assert (proj / "tests").exists()
    assert (proj / "scripts").exists()


def test_cmd_create_dcc_uses_dcc_gitignore(tmp_path, monkeypatch):
    """dcc type uses DCC_GITIGNORE (*.cache, *.bak), not python gitignore."""
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "creative_project": {"root_dirs": ["assets", "scripts", "exports", "docs"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"dcc": "creative_project"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "skip"}):
        import argparse
        args = argparse.Namespace(
            id="my-dcc", type="dcc", stack="none",
            dir=str(tmp_path), description="dcc project", dry_run=False,
        )
        result = scaffold_project.cmd_create(args)
    assert result["status"] == "ok"
    gitignore = (tmp_path / "my-dcc" / ".gitignore").read_text(encoding="utf-8")
    assert "*.cache" in gitignore
    assert "*.pyc" not in gitignore


def test_cmd_create_dry_run_lists_would_create(tmp_path):
    """dry-run returns would_create list without touching disk."""
    import argparse
    args = argparse.Namespace(
        id="dry-proj", type="code-local", stack="python",
        dir=str(tmp_path), description="", dry_run=True,
    )
    result = scaffold_project.cmd_create(args)
    assert result["status"] == "dry-run"
    assert any("dry-proj" in item for item in result["would_create"])
    assert not (tmp_path / "dry-proj").exists()
```

- [ ] **Step 6: Run scaffold tests including new ones**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v
```

Expected: all PASSED, including the 3 new tests.

- [ ] **Step 7: Run full test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/ -x -q
```

Expected: no failures introduced by this change.

- [ ] **Step 8: Version bump**

```
python scripts/bump_plugin.py h2t-core patch
python scripts/bump_plugin.py h2t-dev patch
```

Both plugins changed public structure behaviour. Patch bump per project versioning rules.

- [ ] **Step 9: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py plugins/h2t-core/.claude-plugin/plugin.json plugins/h2t-dev/.claude-plugin/plugin.json
git -C C:/dev/h2t-skills commit -m "refactor(scaffold): replace DIR_STRUCTURE/TYPE_TO_TEMPLATE with project_types lib"
```

---

## Self-Review

**Spec coverage:**
- [x] `lib/docs/project_types.py` created — Task 1
- [x] `init.py` refactored — Task 2
- [x] `scaffold_project.py` refactored — Task 3
- [x] `client_project` type exists with correct root + docs dirs
- [x] `research_project.docs_dirs` no longer duplicates `docs/reports` (REQUIRED_CORE_DIRS)
- [x] `docs` scaffold type no longer creates `research/` at root level (was a bug)
- [x] `detect_template()` exported for future use by project-audit

**Gaps / notes:**
- `docs-lint` type-aware checks are intentionally **not** in this plan — that's Step 2 of the roadmap
- `project-audit` → `docs-lint doctor` integration is Step 3
- The `scripts` dir is added to `code_repo.root_dirs` — previously scaffold didn't create it. Existing repos won't be affected; new scaffolds will get it.

**Placeholder scan:** none found.

**Type consistency:** `PROJECT_TYPES`, `SCAFFOLD_TYPE_TO_TEMPLATE`, `detect_template` — names are consistent across all tasks.

**Codex review issues resolved:**
- [x] Fallback dict matches old `DIR_STRUCTURE` exactly (cache-safe)
- [x] `cmd_create()` tests added: root dirs, DCC .gitignore, dry-run
- [x] Version bump step added (Task 3 Step 8) for both h2t-core and h2t-dev
