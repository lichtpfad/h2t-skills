---
title: "docs-lint Enhancement — legacy dirs, repo root, data/docs boundary, label fix"
status: "draft"
date: "2026-05-27"
milestone: "skills-release"
---

# docs-lint Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `lint.py` with four new checks (legacy dirs, naming conventions, repo root, data/docs boundary) and a `--fix-labels` flag that calls `sync_labels.py`.

**Architecture:** All new logic added as pure functions in `lint.py` that take a `Path` and return `list[str]`. Each function is independently testable. Tests use `pytest` `tmp_path` fixture — no real repos needed. New CLI flags: `--repo-root` (enables root check), `--fix-labels` (runs sync_labels for diverged repos).

**Tech Stack:** Python 3.11, pytest, pathlib. No new dependencies.

> **Naming note:** `--fix` already exists in `lint.py` (creates missing dirs, fixes frontmatter). `--fix-labels` is a separate flag specifically for label sync to avoid collision.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `plugins/h2t-dev/lib/docs/common.py` | Modify | Add `REPO_EXTRA_DIRS` constant |
| `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | Modify | Add 4 check functions + `--repo-root` + `--fix-labels` flags |
| `tests/docs/__init__.py` | Create | Package marker |
| `tests/docs/test_lint_checks.py` | Create | Unit tests for all new check functions |

---

### Task 0: Add `REPO_EXTRA_DIRS` whitelist to `common.py`

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/common.py`

Per-repo allowed extra dirs — lint skips them when checking structure.

- [ ] **Step 1: Add constant to `common.py`**

After `REQUIRED_CORE_DIRS` in `plugins/h2t-dev/lib/docs/common.py`:

```python
# Extra dirs allowed per repo — not flagged by check_legacy_dirs or structure checks
REPO_EXTRA_DIRS: dict[str, list[str]] = {
    "h2t-evals":         ["ops", "contracts"],
    "h2t-transcription": ["methodology", "diagrams"],
    "h2t-vision":        ["presentation"],
}
```

- [ ] **Step 2: Import in `lint.py`**

Update the import line in `lint.py`:

```python
from docs.common import (
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, REPO_EXTRA_DIRS,
    STANDARDS_FILES, FRONTMATTER_RULES, ensure_dir, print_header,
    repo_path, parse_frontmatter,
)
```

- [ ] **Step 3: Use whitelist in `check_legacy_dirs`**

`check_legacy_dirs` accepts optional `extra_dirs` to skip:

```python
def check_legacy_dirs(rp: Path, extra_dirs: list[str] | None = None) -> list[str]:
    skip = set(extra_dirs or [])
    failures = []
    for rel in LEGACY_DIRS:
        dir_name = rel.split("/")[-1]
        if dir_name in skip:
            continue
        if (rp / rel).exists():
            failures.append(f"legacy dir: {rel}/ — migrate to docs/superpowers/ or docs/archive/")
    return failures
```

In `main()`, pass the whitelist:

```python
extra = REPO_EXTRA_DIRS.get(name, [])
failures = (
    check_structure(rp)
    + check_adr_naming(rp)
    + check_legacy_dirs(rp, extra_dirs=extra)
    ...
)
```

- [ ] **Step 3b: Add whitelist skip test**

Append to `tests/docs/test_lint_checks.py`:

```python
def test_check_legacy_dirs_skips_whitelisted(tmp_path):
    """Dir in extra_dirs whitelist is not flagged."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path, extra_dirs=["eval"])
    assert result == []
```

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "whitelisted" -v
```

Expected: 1 test PASS

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/common.py plugins/h2t-dev/skills/docs-lint/scripts/lint.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add REPO_EXTRA_DIRS whitelist — skip allowed dirs per repo"
```

---

### Task 1: Test infrastructure — `tests/docs/` package

**Files:**
- Create: `tests/docs/__init__.py`

- [ ] **Step 1: Create package marker**

```python
# tests/docs/__init__.py
# (empty)
```

- [ ] **Step 2: Verify pytest discovers the package**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ --collect-only
```

Expected: `no tests ran` (package exists, no tests yet)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add tests/docs/__init__.py
git -C C:/dev/h2t-skills commit -m "test(docs-lint): add tests/docs package"
```

---

### Task 2: `check_legacy_dirs` — warns about banned legacy directories

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing test**

Create `tests/docs/test_lint_checks.py`:

```python
"""Unit tests for docs-lint check functions."""
import sys
from pathlib import Path

# Make lint.py importable
_LINT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"
sys.path.insert(0, str(_LINT_DIR))
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from lint import check_legacy_dirs


def test_check_legacy_dirs_clean(tmp_path):
    """No legacy dirs → no failures."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    assert check_legacy_dirs(tmp_path) == []


def test_check_legacy_dirs_plans(tmp_path):
    """docs/plans/ present → failure."""
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/plans" in f for f in result)


def test_check_legacy_dirs_specs(tmp_path):
    """docs/specs/ present → failure."""
    (tmp_path / "docs" / "specs").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/specs" in f for f in result)


def test_check_legacy_dirs_handoff(tmp_path):
    """docs/handoff/ present → failure."""
    (tmp_path / "docs" / "handoff").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("handoff" in f for f in result)


def test_check_legacy_dirs_eval(tmp_path):
    """docs/eval/ present → failure."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("eval" in f for f in result)
```

- [ ] **Step 2: Run test — expect FAIL (ImportError)**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v
```

Expected: `ImportError: cannot import name 'check_legacy_dirs'`

- [ ] **Step 3: Implement `check_legacy_dirs` in lint.py**

Add after `check_adr_naming()` in `lint.py`:

```python
LEGACY_DIRS = [
    "docs/plans",
    "docs/specs",
    "docs/handoff",
    "docs/handoffs",
    "docs/eval",
]


def check_legacy_dirs(rp: Path) -> list[str]:
    failures = []
    for rel in LEGACY_DIRS:
        if (rp / rel).exists():
            failures.append(f"legacy dir: {rel}/ — migrate to docs/superpowers/ or docs/archive/")
    return failures
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Wire into `main()` — add to failures list**

In `main()`, extend the `failures = (...)` expression:

```python
failures = (
    check_structure(rp)
    + check_adr_naming(rp)
    + check_legacy_dirs(rp)          # NEW
    + check_frontmatter(rp)
    + check_projects_yaml(rp, name, projects)
    + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
)
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add check_legacy_dirs — warn on docs/plans, docs/specs, docs/handoff, docs/eval"
```

---

### Task 3: `check_naming_conventions` — YYYY-MM-DD prefix required in specs/plans

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/docs/test_lint_checks.py`:

```python
from lint import check_naming_conventions


def test_naming_clean(tmp_path):
    """Dated specs and plans → no failures."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "2026-05-27-my-feature-design.md").write_text("# x")
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-05-27-my-feature-plan.md").write_text("# x")
    assert check_naming_conventions(tmp_path) == []


def test_naming_spec_missing_date(tmp_path):
    """Spec without date prefix → failure."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "my-feature-design.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-design.md" in f for f in result)


def test_naming_plan_missing_date(tmp_path):
    """Plan without date prefix → failure."""
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "my-feature-plan.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-plan.md" in f for f in result)


def test_naming_readme_ignored(tmp_path):
    """README.md in specs dir → not flagged."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# index")
    assert check_naming_conventions(tmp_path) == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py::test_naming_spec_missing_date -v
```

Expected: `ImportError: cannot import name 'check_naming_conventions'`

- [ ] **Step 3: Implement `check_naming_conventions`**

Add after `check_legacy_dirs()` in `lint.py`:

```python
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_NAMING_DIRS = ["docs/superpowers/specs", "docs/superpowers/plans"]
_NAMING_SKIP = {"README.md", "index.md"}


def check_naming_conventions(rp: Path) -> list[str]:
    failures = []
    for rel_dir in _NAMING_DIRS:
        d = rp / rel_dir
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            if md.name in _NAMING_SKIP:
                continue
            if not _DATE_PREFIX.match(md.name):
                failures.append(
                    f"naming: {rel_dir}/{md.name} — expected YYYY-MM-DD- prefix"
                )
    return failures
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v -k "naming"
```

Expected: 4 tests PASS

- [ ] **Step 5: Wire into `main()`**

```python
failures = (
    check_structure(rp)
    + check_adr_naming(rp)
    + check_legacy_dirs(rp)
    + check_naming_conventions(rp)   # NEW
    + check_frontmatter(rp)
    + check_projects_yaml(rp, name, projects)
    + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
)
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add check_naming_conventions — YYYY-MM-DD prefix required in specs/plans"
```

---

### Task 4: `check_repo_root` — no temp dirs, root element count

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/docs/test_lint_checks.py`:

```python
from lint import check_repo_root


def test_repo_root_clean(tmp_path):
    """Minimal clean root → no failures."""
    for name in ["README.md", "pyproject.toml", ".gitignore", "CLAUDE.md"]:
        (tmp_path / name).write_text("")
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    assert check_repo_root(tmp_path) == []


def test_repo_root_temp_dir(tmp_path):
    """temp/ in root → failure."""
    (tmp_path / "temp").mkdir()
    result = check_repo_root(tmp_path)
    assert any("temp" in f for f in result)


def test_repo_root_old_dir(tmp_path):
    """old/ in root → failure."""
    (tmp_path / "old").mkdir()
    result = check_repo_root(tmp_path)
    assert any("old" in f for f in result)


def test_repo_root_backup_dir(tmp_path):
    """backup/ in root → failure."""
    (tmp_path / "backup").mkdir()
    result = check_repo_root(tmp_path)
    assert any("backup" in f for f in result)


def test_repo_root_too_many_items(tmp_path):
    """More than 12 items in root → failure."""
    for i in range(13):
        (tmp_path / f"item_{i}.txt").write_text("")
    result = check_repo_root(tmp_path)
    assert any("root has" in f for f in result)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "repo_root" -v
```

Expected: `ImportError: cannot import name 'check_repo_root'`

- [ ] **Step 3: Implement `check_repo_root`**

Add after `check_naming_conventions()` in `lint.py`:

```python
_BANNED_ROOT_DIRS = {"temp", "old", "backup", "tmp", "archive_old"}
_ROOT_MAX_ITEMS = 12
_ROOT_SKIP = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
              "node_modules", ".ruff_cache", ".vscode", ".idea"}


def check_repo_root(rp: Path) -> list[str]:
    failures = []
    items = [p for p in rp.iterdir() if p.name not in _ROOT_SKIP]
    for item in items:
        if item.is_dir() and item.name.lower() in _BANNED_ROOT_DIRS:
            failures.append(f"repo root: banned dir '{item.name}/' — remove or archive via git mv")
    visible = [p for p in items if not p.name.startswith(".")]
    if len(visible) > _ROOT_MAX_ITEMS:
        failures.append(
            f"repo root has {len(visible)} items (max {_ROOT_MAX_ITEMS}) — consider consolidating"
        )
    return failures
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "repo_root" -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Add `--repo-root` flag and wire into `main()`**

In `main()`, add argument:

```python
parser.add_argument("--repo-root", action="store_true",
                    help="Check repo root for banned dirs and item count")
```

Add to failures:

```python
failures = (
    check_structure(rp)
    + check_adr_naming(rp)
    + check_legacy_dirs(rp)
    + check_naming_conventions(rp)
    + check_frontmatter(rp)
    + check_projects_yaml(rp, name, projects)
    + (check_repo_root(rp) if args.repo_root else [])   # NEW
    + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
)
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add check_repo_root — ban temp/old/backup, root item count limit"
```

---

### Task 5: `check_data_docs_boundary` — JSON/YAML in docs/, Markdown in data/

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/docs/test_lint_checks.py`:

```python
from lint import check_data_docs_boundary


def test_data_docs_boundary_clean(tmp_path):
    """Markdown in docs/, JSON in data/ → no failures."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# x")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "registry.json").write_text("{}")
    assert check_data_docs_boundary(tmp_path) == []


def test_json_in_docs(tmp_path):
    """JSON file in docs/ → failure."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_text("{}")
    result = check_data_docs_boundary(tmp_path)
    assert any("data.json" in f for f in result)


def test_yaml_in_docs(tmp_path):
    """YAML file in docs/ → failure."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "config.yaml").write_text("key: value")
    result = check_data_docs_boundary(tmp_path)
    assert any("config.yaml" in f for f in result)


def test_markdown_in_data(tmp_path):
    """Markdown file in data/ → failure."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "notes.md").write_text("# notes")
    result = check_data_docs_boundary(tmp_path)
    assert any("notes.md" in f for f in result)


def test_data_docs_boundary_no_dirs(tmp_path):
    """No docs/ or data/ dirs → no failures."""
    assert check_data_docs_boundary(tmp_path) == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "data_docs" -v
```

Expected: `ImportError: cannot import name 'check_data_docs_boundary'`

- [ ] **Step 3: Implement `check_data_docs_boundary`**

Add after `check_repo_root()` in `lint.py`:

```python
_DATA_EXTS_IN_DOCS = {".json", ".yaml", ".yml", ".csv"}
_DOC_EXTS_IN_DATA = {".md"}
_DATA_DOCS_SKIP = {".pymarkdown.yaml", ".vale.ini"}


def check_data_docs_boundary(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*"):
            if f.is_file() and f.suffix in _DATA_EXTS_IN_DOCS and f.name not in _DATA_DOCS_SKIP:
                rel = str(f.relative_to(rp)).replace("\\", "/")
                failures.append(f"data in docs: {rel} — move to data/")
    data_dir = rp / "data"
    if data_dir.exists():
        for f in data_dir.rglob("*"):
            if f.is_file() and f.suffix in _DOC_EXTS_IN_DATA:
                rel = str(f.relative_to(rp)).replace("\\", "/")
                failures.append(f"doc in data: {rel} — move to docs/")
    return failures
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "data_docs" -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Wire into `main()`**

```python
failures = (
    check_structure(rp)
    + check_adr_naming(rp)
    + check_legacy_dirs(rp)
    + check_naming_conventions(rp)
    + check_frontmatter(rp)
    + check_data_docs_boundary(rp)    # NEW
    + check_projects_yaml(rp, name, projects)
    + (check_repo_root(rp) if args.repo_root else [])
    + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
)
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add check_data_docs_boundary — JSON/YAML in docs/, Markdown in data/"
```

---

### Task 6: `--fix-labels` flag — call sync_labels.py for repos with label drift

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing test**

Append to `tests/docs/test_lint_checks.py`:

```python
import subprocess
from unittest.mock import patch, MagicMock
from lint import fix_labels


def test_fix_labels_calls_sync(tmp_path):
    """fix_labels runs sync_labels.py for the given repo."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced 3", stderr="")
        result = fix_labels(tmp_path, "h2t-skills")
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "sync_labels.py" in " ".join(str(c) for c in cmd)


def test_fix_labels_returns_message(tmp_path):
    """fix_labels returns a non-empty message on success."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced 3", stderr="")
        result = fix_labels(tmp_path, "h2t-skills")
    assert result != ""
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "fix_labels" -v
```

Expected: `ImportError: cannot import name 'fix_labels'`

- [ ] **Step 3: Implement `fix_labels`**

Add after `fix_frontmatter()` in `lint.py`:

```python
_SYNC_LABELS_SCRIPT = Path(__file__).parents[2] / "docs-sync-labels" / "scripts" / "sync_labels.py"
_H2T_PYTHON = (
    Path.home() / ".h2t" / "venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else Path.home() / ".h2t" / "venv" / "bin" / "python"
)


def fix_labels(rp: Path, repo_name: str) -> str:
    python = str(_H2T_PYTHON) if _H2T_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(_SYNC_LABELS_SCRIPT), repo_name],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode == 0:
        return f"labels synced for {repo_name}"
    return f"label sync failed: {result.stderr.strip()[:120]}"
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "fix_labels" -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Add `--fix-labels` flag and wire into `main()`**

In `main()`, add argument:

```python
parser.add_argument("--fix-labels", action="store_true",
                    help="Sync canonical GitHub labels (requires gh CLI)")
```

In the per-repo loop, after failures are printed, add:

```python
if args.fix_labels:
    msg = fix_labels(rp, name)
    print(f"  FIX-LABELS: {msg}")
```

- [ ] **Step 6: Run full test suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add --fix-labels flag — calls sync_labels.py for repos with label drift"
```

---

### Task 7: Update SKILL.md trigger descriptions

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/SKILL.md`

- [ ] **Step 1: Update description to mention new flags**

In `SKILL.md`, update the `description:` field:

```yaml
description: >-
  Use when checking docs compliance, linting documentation, verifying standards,
  or auditing documentation structure and frontmatter across h2t repos.
  Flags: --repo-root (root dir audit), --fix-labels (sync GitHub labels),
  --fix (create missing dirs), --fix-frontmatter (auto-add frontmatter).
```

- [ ] **Step 2: Bump patch version**

> **NOTE: Version ordering** — Plan 3 (milestone-closure) bumps h2t-dev to `1.0.7`. This plan (docs-lint) must be applied and merged **before** Plan 3. Apply in order: docs-lint (1.0.6) → milestone-closure (1.0.7).

```bash
C:/dev/h2t-skills/.venv/Scripts/python scripts/bump_plugin.py h2t-dev 1.0.6
```

- [ ] **Step 3: Final test run**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/SKILL.md plugins/h2t-dev/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "docs(docs-lint): update SKILL.md with new flags; bump version"
```

- [ ] **Step 5: Mark `gh-memory` deprecated in plugin.json**

In `plugins/h2t-dev/plugin.json`, find the `gh-memory` skill entry and add `"deprecated": true` to its metadata, or add a `"status": "deprecated"` field.

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/plugin.json
git -C C:/dev/h2t-skills commit -m "chore(gh-memory): mark skill deprecated in plugin.json"
```
