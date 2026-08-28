---
title: "docs-lint Harvest Fixes — Implementation Plan"
status: "draft"
date: "2026-06-04"
milestone: ""
---
# docs-lint Harvest Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 false-positive sources found in rejuve real-world audit: `exclude_dirs` support, `client_project` template correction, root item count ignoring gitignored files, and naming exceptions for living log files.

**Architecture:** Four independent tasks, each producing a working commit. Tasks 1 and 4 are one-liners. Tasks 2 and 3 touch `config.py` (adds new fields to `_DEFAULTS`) + one lib file each + callers in `lint.py`. Naming exceptions (#251) reuses the same config extension pattern as exclude_dirs (#248) — read Task 2 first.

**Tech Stack:** Python stdlib only. Files: `plugins/h2t-dev/lib/docs/project_types.py`, `plugins/h2t-dev/lib/docs/config.py`, `plugins/h2t-dev/lib/docs/orphan.py`, `plugins/h2t-dev/lib/docs/naming.py`, `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`, `tests/docs/test_lint_checks.py`, `tests/docs/test_project_types.py`.

**Python executable:** `C:/dev/h2t-skills/.venv/Scripts/python.exe`
**Pytest:** `C:/dev/h2t-skills/.venv/Scripts/pytest`
**One command per Bash call — no `&&` chaining.**

---

## Prerequisites

Verify current test suite is green:
```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -q --ignore=tests/docs/test_execution_tracking.py
```
Expected: 129 passed.

---

## File Map

| Action | Path | What changes |
|--------|------|-------------|
| Modify | `plugins/h2t-dev/lib/docs/project_types.py` | Remove `"docs/deliverables"` from client_project |
| Modify | `plugins/h2t-dev/lib/docs/config.py` | Add `exclude_dirs: []` and `naming_exceptions: []` to `_DEFAULTS` |
| Modify | `plugins/h2t-dev/lib/docs/orphan.py` | Accept `exclude_dirs` param, skip excluded paths |
| Modify | `plugins/h2t-dev/lib/docs/naming.py` | Accept `exclude_dirs` + `naming_exceptions` params |
| Modify | `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | `check_repo_root` uses git; callers pass exclude_dirs + naming_exceptions |
| Modify | `tests/docs/test_lint_checks.py` | New tests for all 4 fixes |
| Modify | `tests/docs/test_project_types.py` | Update client_project assertion |

---

## Task 1: Fix `client_project` template — remove `docs/deliverables/` (#249)

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/project_types.py`
- Test: `tests/docs/test_project_types.py`

- [ ] **Step 1: Write failing test**

Read `tests/docs/test_project_types.py` first to understand existing test style. Append:

```python
def test_client_project_does_not_require_docs_deliverables():
    """docs/deliverables/ was a false positive on projects with root-level deliverables/."""
    spec = PROJECT_TYPES["client_project"]
    assert "docs/deliverables" not in spec["docs_dirs"], (
        "docs/deliverables should not be required — projects use root-level deliverables/ instead"
    )
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py -k "does_not_require_docs_deliverables" -v
```

Expected: FAILED (currently `"docs/deliverables"` is in `client_project["docs_dirs"]`).

- [ ] **Step 3: Remove from project_types.py**

In `plugins/h2t-dev/lib/docs/project_types.py`, find `client_project` entry and remove `"docs/deliverables"` from `docs_dirs`. Result:

```python
"client_project": {
    "root_dirs": ["docs", "data", "deliverables", "scripts"],
    "docs_dirs": ["docs/ops", "docs/research"],
    "root_files_required": ["README.md", "CLAUDE.md"],
},
```

- [ ] **Step 4: Run test**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/project_types.py tests/docs/test_project_types.py
git -C C:/dev/h2t-skills commit -m "fix(docs-lint): remove docs/deliverables from client_project template (#249)"
```

---

## Task 2: `exclude_dirs` in docs-lint.yaml — suppress false positives for agent dirs (#248)

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Modify: `plugins/h2t-dev/lib/docs/orphan.py`
- Modify: `plugins/h2t-dev/lib/docs/naming.py`
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

### What it does

When `docs-lint.yaml` contains:
```yaml
exclude_dirs:
  - docs/superpowers
```

All orphan and naming findings for files under `docs/superpowers/` are suppressed. Typed structure checks (`check_project_structure_typed`) are NOT affected — they check dir existence, not file reachability.

- [ ] **Step 1: Write failing tests**

Append to `tests/docs/test_lint_checks.py`:

```python
def test_exclude_dirs_suppresses_orphan_findings(tmp_path):
    """Files under excluded dirs don't appear as orphans."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers").mkdir()
    (tmp_path / "docs" / "superpowers" / "plan.md").write_text(
        "# Plan\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\nexclude_dirs:\n  - docs/superpowers\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    orphan_paths = [f["path"] for f in findings if f["type"] == "orphan"]
    assert not any("superpowers" in p for p in orphan_paths), orphan_paths


def test_exclude_dirs_suppresses_naming_findings(tmp_path):
    """Files under excluded dirs don't get naming-convention findings."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    # Filename without date prefix — would normally trigger naming finding
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\nexclude_dirs:\n  - docs/superpowers\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming_paths = [f["path"] for f in findings if f["type"] == "naming"]
    assert not any("superpowers" in p for p in naming_paths), naming_paths


def test_exclude_dirs_empty_list_changes_nothing(tmp_path):
    """exclude_dirs: [] (default) does not suppress any findings."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    # No docs-lint.yaml → exclude_dirs defaults to []
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming_paths = [f["path"] for f in findings if f["type"] == "naming"]
    assert any("superpowers" in p for p in naming_paths), "expected naming finding without exclusion"
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "exclude_dirs" -v
```

Expected: `test_exclude_dirs_suppresses_orphan_findings` and `test_exclude_dirs_suppresses_naming_findings` FAIL.

- [ ] **Step 3: Add `exclude_dirs` to config.py defaults**

In `plugins/h2t-dev/lib/docs/config.py`, add `"exclude_dirs": []` to `_DEFAULTS`:

```python
_DEFAULTS: dict[str, Any] = {
    "docs_root": "docs",
    "required_dirs": [
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        "docs/adr",
        "docs/reports",
    ],
    "exceptions": [],
    "exclude_dirs": [],
    "template": None,
}
```

- [ ] **Step 4: Update `find_orphan_files` in orphan.py**

Add `exclude_dirs` parameter. Filter out any resolved path that falls under an excluded dir:

```python
def find_orphan_files(repo_root: Path, exclude_dirs: list[str] | None = None) -> list[dict]:
    """
    BFS from docs/README.md. Returns finding dicts for unreachable .md files.
    exclude_dirs: list of repo-root-relative paths to skip (e.g. ["docs/superpowers"]).
    """
    from docs.reporter import finding as make_finding

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    _excluded = {(repo_root / d).resolve() for d in (exclude_dirs or [])}

    def _is_excluded(p: Path) -> bool:
        rp = p.resolve()
        return any(rp == ex or ex in rp.parents for ex in _excluded)

    readme = docs_dir / "README.md"
    if not readme.exists():
        orphans = [f for f in sorted(docs_dir.rglob("*.md")) if not _is_excluded(f)]
        return [
            make_finding(
                "orphan",
                "warn",
                str(f.relative_to(repo_root)).replace("\\", "/"),
                "docs/README.md missing — cannot determine reachability",
            )
            for f in orphans
        ]

    visited: set[Path] = set()
    queue: deque[Path] = deque([readme.resolve()])
    visited.add(readme.resolve())

    while queue:
        current = queue.popleft()
        if not current.is_file():
            continue
        try:
            text = current.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linked in _parse_md_links(text, current.parent, docs_dir):
            resolved = linked.resolve()
            if resolved not in visited:
                visited.add(resolved)
                queue.append(resolved)

    all_docs = {
        f.resolve()
        for f in docs_dir.rglob("*.md")
        if not _is_excluded(f)
    }
    orphans_abs = all_docs - visited

    findings = []
    repo_resolved = repo_root.resolve()
    for abs_path in sorted(orphans_abs):
        try:
            rel = str(abs_path.relative_to(repo_resolved)).replace("\\", "/")
        except ValueError:
            rel = str(abs_path)
        findings.append(
            make_finding(
                "orphan",
                "warn",
                rel,
                "Not reachable from docs/README.md or any linked index",
            )
        )
    return findings
```

- [ ] **Step 5: Update `check_naming_all_docs` in naming.py**

Add `exclude_dirs` parameter. Skip files under excluded paths:

```python
def check_naming_all_docs(
    repo_root: Path, exclude_dirs: list[str] | None = None
) -> list[dict]:
```

At the start of the function body, before the loop over `.md` files, add:

```python
    _excluded = {(repo_root / d).resolve() for d in (exclude_dirs or [])}

    def _is_excluded(p: Path) -> bool:
        rp = p.resolve()
        return any(rp == ex or ex in rp.parents for ex in _excluded)
```

Then in the inner loop where each `.md` file is processed, add an early skip:

```python
        if _is_excluded(md_file):
            continue
```

Place it before any other check on `md_file`. Read the current function body (`check_naming_all_docs` starts at line 20 of naming.py) and insert accordingly.

- [ ] **Step 6: Update callers in lint.py**

In `_collect_all_findings()`, the `cfg` dict is already loaded. Pass `exclude_dirs` to both functions:

```python
    exclude_dirs = cfg.get("exclude_dirs") or []
    all_findings.extend(find_orphan_files(rp, exclude_dirs=exclude_dirs))
    all_findings.extend(check_naming_all_docs(rp, exclude_dirs=exclude_dirs))
```

In `_run_audit()`, find where `find_orphan_files(rp)` and `check_naming_all_docs(rp)` are called (around lines 493–494) and update:

```python
    exclude_dirs = cfg.get("exclude_dirs") or []
    orphans = find_orphan_files(rp, exclude_dirs=exclude_dirs)
    naming = check_naming_all_docs(rp, exclude_dirs=exclude_dirs)
```

Note: `cfg` is already loaded in `_run_audit()` after Task 2 of the previous plan. If it's not, add `cfg = load_config(rp)` before these lines.

- [ ] **Step 7: Run tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "exclude_dirs" -v
```

Expected: all 3 PASSED.

- [ ] **Step 8: Run full suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -q --ignore=tests/docs/test_execution_tracking.py
```

Expected: all PASSED.

- [ ] **Step 9: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py plugins/h2t-dev/lib/docs/orphan.py plugins/h2t-dev/lib/docs/naming.py plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add exclude_dirs support — suppress orphan/naming findings for agent dirs (#248)"
```

---

## Task 3: Naming exceptions for living log files (#251)

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Modify: `plugins/h2t-dev/lib/docs/naming.py`
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

### What it does

When `docs-lint.yaml` contains:
```yaml
naming_exceptions:
  - docs/superpowers/plans/docs-lint-skill-log.md
  - docs/superpowers/plans/*-harvest.jsonl
```

Files matching these patterns (fnmatch, relative to repo root) are skipped by the date-prefix naming check. Any file in the exception list won't trigger `"Missing date prefix"` warnings.

- [ ] **Step 1: Write failing test**

Append to `tests/docs/test_lint_checks.py`:

```python
import fnmatch as _fnmatch


def test_naming_exceptions_suppresses_date_prefix_finding(tmp_path):
    """Files listed in naming_exceptions skip the date-prefix check."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    living_log = tmp_path / "docs" / "superpowers" / "plans" / "my-log.md"
    living_log.write_text("# Living log\n", encoding="utf-8")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\n"
        "naming_exceptions:\n"
        "  - docs/superpowers/plans/my-log.md\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "my-log" in f["path"]]
    assert naming == [], f"expected no naming finding for excepted file, got: {naming}"


def test_naming_exceptions_glob_pattern(tmp_path):
    """naming_exceptions supports fnmatch glob patterns."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans" / "skill-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\n"
        "naming_exceptions:\n"
        "  - docs/superpowers/plans/*-log.md\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "skill-log" in f["path"]]
    assert naming == [], f"expected glob pattern to suppress finding, got: {naming}"


def test_naming_exceptions_empty_list_changes_nothing(tmp_path):
    """naming_exceptions: [] (default) still enforces date prefix."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    # No docs-lint.yaml → no exceptions
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "my-log" in f["path"]]
    assert naming, "expected naming finding without exception config"
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "naming_exception" -v
```

Expected: FAILED.

- [ ] **Step 3: Add `naming_exceptions` to config.py defaults**

In `plugins/h2t-dev/lib/docs/config.py`, add `"naming_exceptions": []` to `_DEFAULTS`:

```python
_DEFAULTS: dict[str, Any] = {
    "docs_root": "docs",
    "required_dirs": [
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        "docs/adr",
        "docs/reports",
    ],
    "exceptions": [],
    "exclude_dirs": [],
    "naming_exceptions": [],
    "template": None,
}
```

- [ ] **Step 4: Update `check_naming_all_docs` in naming.py**

Add `naming_exceptions` parameter. Before the date-prefix check, test if the file's relative path matches any exception pattern (using `fnmatch`):

```python
import fnmatch

def check_naming_all_docs(
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    naming_exceptions: list[str] | None = None,
) -> list[dict]:
```

Inside the loop, after the `_is_excluded` check and before the date-prefix check, add:

```python
            rel_posix = str(md_file.relative_to(repo_root)).replace("\\", "/")
            if any(fnmatch.fnmatch(rel_posix, pat) for pat in (naming_exceptions or [])):
                continue
```

Place this before the `if _requires_date_prefix(rel) and not _DATE_PREFIX_RE.match(name):` block.

- [ ] **Step 5: Update callers in lint.py**

In `_collect_all_findings()`, pass `naming_exceptions`:

```python
    exclude_dirs = cfg.get("exclude_dirs") or []
    naming_exceptions = cfg.get("naming_exceptions") or []
    all_findings.extend(find_orphan_files(rp, exclude_dirs=exclude_dirs))
    all_findings.extend(check_naming_all_docs(rp, exclude_dirs=exclude_dirs, naming_exceptions=naming_exceptions))
```

In `_run_audit()`, same update:

```python
    exclude_dirs = cfg.get("exclude_dirs") or []
    naming_exceptions = cfg.get("naming_exceptions") or []
    orphans = find_orphan_files(rp, exclude_dirs=exclude_dirs)
    naming = check_naming_all_docs(rp, exclude_dirs=exclude_dirs, naming_exceptions=naming_exceptions)
```

- [ ] **Step 6: Run tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "naming_exception" -v
```

Expected: all 3 PASSED.

- [ ] **Step 7: Run full suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -q --ignore=tests/docs/test_execution_tracking.py
```

Expected: all PASSED.

- [ ] **Step 8: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py plugins/h2t-dev/lib/docs/naming.py plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add naming_exceptions config — skip date-prefix check for living logs (#251)"
```

---

## Task 4: Root item count — exclude gitignored files (#250)

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

### What it does

`check_repo_root()` currently counts all visible items at repo root including gitignored temp files and untracked build artifacts. Fix: use `git ls-files` to count only git-tracked items, with fallback to current behavior if not in a git repo.

- [ ] **Step 1: Write failing test**

Append to `tests/docs/test_lint_checks.py`:

```python
def test_check_repo_root_excludes_gitignored_files(tmp_path):
    """Root item count uses git-tracked files, not raw filesystem count."""
    import subprocess as _sp
    # Init a git repo
    _sp.run(["git", "init", str(tmp_path)], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)
    # Create 8 tracked files
    for name in ["README.md", "CLAUDE.md", "a.md", "b.md", "c.md", "d.md", "e.md", "f.md"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
        _sp.run(["git", "-C", str(tmp_path), "add", name], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)
    # Create 10 gitignored/untracked temp files that would push count above limit
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\n", encoding="utf-8")
    for i in range(10):
        (tmp_path / f"temp_{i}.tmp").write_text("x", encoding="utf-8")
    # Should not trigger "root has N items" since tracked count is 8 (< 12)
    from lint import check_repo_root
    result = check_repo_root(tmp_path)
    count_msgs = [m for m in result if "items (max" in m]
    assert count_msgs == [], f"expected no count warning, got: {count_msgs}"


def test_check_repo_root_fallback_without_git(tmp_path):
    """Outside a git repo, check_repo_root falls back to filesystem count (no crash)."""
    from lint import check_repo_root
    # tmp_path is not a git repo — should not raise
    result = check_repo_root(tmp_path)
    # Result is a list (possibly empty), no exception
    assert isinstance(result, list)
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "repo_root_excludes_gitignored" -v
```

Expected: FAILED (current count includes untracked files).

- [ ] **Step 3: Update `check_repo_root` in lint.py**

Replace the current `check_repo_root` function:

```python
def check_repo_root(rp: Path) -> list[str]:
    import subprocess as _sp
    failures = []
    items = [p for p in rp.iterdir() if p.name not in _ROOT_SKIP]
    for item in items:
        if item.is_dir() and item.name.lower() in _BANNED_ROOT_DIRS:
            failures.append(f"repo root: banned dir '{item.name}/' — remove or archive via git mv")
    # Count only git-tracked items; fall back to filesystem if not a git repo
    try:
        result = _sp.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--directory",
             "--cached", "--", "."],
            cwd=str(rp),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tracked = {
                line.split("/")[0].rstrip("/")
                for line in result.stdout.splitlines()
                if line and not line.startswith(".")
            }
            visible_count = len(tracked)
        else:
            raise RuntimeError("git failed")
    except Exception:
        # Not a git repo or git unavailable — fall back to filesystem count
        visible_count = len([p for p in items if not p.name.startswith(".")])
    if visible_count > _ROOT_MAX_ITEMS:
        failures.append(
            f"repo root has {visible_count} items (max {_ROOT_MAX_ITEMS}) — consider consolidating"
        )
    return failures
```

**Note:** `git ls-files --others --exclude-standard --directory --cached` lists both tracked files and untracked-but-not-ignored files. We only want tracked. Change to:

```python
        result = _sp.run(
            ["git", "ls-files", "--cached", "--", "."],
            cwd=str(rp),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Count unique top-level names (first path component) of tracked files
            tracked = {
                line.split("/")[0]
                for line in result.stdout.splitlines()
                if line and not line.startswith(".")
            }
            visible_count = len(tracked)
        else:
            raise RuntimeError("git failed")
```

- [ ] **Step 4: Run tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "repo_root" -v
```

Expected: all PASSED.

- [ ] **Step 5: Run full suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -q --ignore=tests/docs/test_execution_tracking.py
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "fix(docs-lint): root item count uses git-tracked files only, excludes gitignored (#250)"
```

---

## Task 5: Version bump + push

- [ ] **Step 1: Bump h2t-dev patch**

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev patch
```

- [ ] **Step 2: Commit bump**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/.claude-plugin/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "chore(h2t-dev): bump patch — harvest fixes #248 #249 #250 #251"
```

- [ ] **Step 3: Verify and report**

Run tests, confirm pass, then report to user for push approval:

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/
```

Do NOT push automatically. User approves push separately.

---

## Self-Review

**Spec coverage:**
- [x] #249 — `docs/deliverables` removed from client_project template (Task 1)
- [x] #248 — `exclude_dirs` parsed from config, applied to orphan + naming checks (Task 2)
- [x] #251 — `naming_exceptions` parsed from config, fnmatch patterns, applied before date-prefix check (Task 3)
- [x] #250 — `check_repo_root` uses `git ls-files --cached` with fallback (Task 4)
- [x] All tasks: TDD (failing test → implement → pass → commit)
- [x] No `&&` chaining in commands

**Placeholder scan:** None — all steps have actual code.

**Type consistency:**
- `exclude_dirs: list[str] | None` — consistent across orphan.py, naming.py, lint.py callers
- `naming_exceptions: list[str] | None` — consistent across naming.py, lint.py callers
- `cfg.get("exclude_dirs") or []` — consistent in both `_collect_all_findings` and `_run_audit`
