---
title: "lifecycle OS fixes — scaffold + docs-init + fix-index"
status: "draft"
date: "2026-06-08"
milestone: ""
---

# Lifecycle OS Fixes — scaffold + docs-init + fix-index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 systemic gaps that cause newly scaffolded projects to accumulate docs-lint findings within days: missing .gitignore entries, missing .h2t/lint-state.jsonl init, silent docs-init skip not caught, and fix-index blind to non-standard docs/ sections.

**Architecture:** All fixes are isolated to 3 Python scripts and their existing test files. No new abstractions. Tasks are independent — each can be verified by running `pytest tests/docs/ tests/scaffold/ -v`.

**Tech Stack:** Python 3.11+, pytest, pathlib. No new dependencies.

**Issues closed:** #262, #263, #266, #268.

> **Codex review applied 2026-06-09.** 4 blocking fixes incorporated:
> (1) `d.rglob("*.md")` instead of `d.glob("*.md")` to include superpowers/ — otherwise existing test breaks.
> (2) T4 adds individual file links per discovered section (not just dir links) — otherwise orphan findings remain.
> (3) All new `argparse.Namespace` in tests include `merge=False` — without it `cmd_create()` raises AttributeError.
> (4) T3 validates `docs/superpowers/specs`, `docs/superpowers/plans` with `.is_dir()` — not shallow `docs/superpowers`.

---

## File Map

| File | Change |
|------|--------|
| `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | T1: gitignore entries; T3: docs-init validation |
| `plugins/h2t-dev/skills/docs-init/scripts/init.py` | T1: gitignore entries; T2: lint-state.jsonl init |
| `plugins/h2t-dev/skills/docs-index/scripts/index.py` | T4: dynamic section discovery |
| `tests/scaffold/test_scaffold_steps.py` | T1+T3: new tests |
| `tests/docs/test_docs_init_repo_root.py` | T1+T2: new tests |
| `tests/docs/test_index_navigation.py` | T4: new tests |

---

## Task 1: Fix .gitignore — add lint temp files to scaffold templates and docs-init

**Closes:** #268

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py:40-88`
- Modify: `plugins/h2t-dev/skills/docs-init/scripts/init.py:200-209`
- Test: `tests/scaffold/test_scaffold_steps.py`
- Test: `tests/docs/test_docs_init_repo_root.py`

### Step 1.1: Write failing tests

In `tests/scaffold/test_scaffold_steps.py`, add after the last test:

```python
def test_gitignore_python_includes_lint_temp_files():
    """scaffold .gitignore must exclude docs-lint temp files from day 0."""
    from scaffold_project import GITIGNORE_TEMPLATES
    gi = GITIGNORE_TEMPLATES["python"]
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi


def test_gitignore_none_includes_lint_temp_files():
    from scaffold_project import GITIGNORE_TEMPLATES
    gi = GITIGNORE_TEMPLATES["none"]
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi


def test_gitignore_dcc_includes_lint_temp_files():
    from scaffold_project import DCC_GITIGNORE
    assert ".h2t/lint-before.json" in DCC_GITIGNORE
    assert ".h2t/lint-after.json" in DCC_GITIGNORE
```

In `tests/docs/test_docs_init_repo_root.py`, add:

```python
def test_init_repo_adds_lint_temp_files_to_gitignore(tmp_path):
    """docs-init appends .h2t/lint-before.json and lint-after.json to .gitignore."""
    repo = tmp_path / "my-repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")

    init_repo("my-repo", repo_root=repo, dry_run=False, commit=False)

    gi = (repo / ".gitignore").read_text(encoding="utf-8")
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi
```

### Step 1.2: Run tests to verify they fail

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py::test_gitignore_python_includes_lint_temp_files tests/scaffold/test_scaffold_steps.py::test_gitignore_none_includes_lint_temp_files tests/scaffold/test_scaffold_steps.py::test_gitignore_dcc_includes_lint_temp_files tests/docs/test_docs_init_repo_root.py::test_init_repo_adds_lint_temp_files_to_gitignore -v
```

Expected: 4 FAILED (AssertionError).

### Step 1.3: Fix scaffold_project.py — add entries to all GITIGNORE_TEMPLATES

In `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`, the `GITIGNORE_TEMPLATES` dict at lines 40-80 and `DCC_GITIGNORE` at lines 82-88.

Replace the entire `GITIGNORE_TEMPLATES` and `DCC_GITIGNORE` block (lines 40-88):

```python
_H2T_LINT_ENTRIES = """\
# docs-lint temp files
.h2t/lint-before.json
.h2t/lint-after.json
"""

GITIGNORE_TEMPLATES: dict[str, str] = {
    "python": """\
.venv/
__pycache__/
*.pyc
*.pyo
*.pyd
dist/
build/
*.egg-info/
.env
.env.*
""" + _H2T_LINT_ENTRIES,
    "js": """\
node_modules/
dist/
.env
.env.*
*.log
.DS_Store
""" + _H2T_LINT_ENTRIES,
    "ts": """\
node_modules/
dist/
.env
.env.*
*.log
*.js.map
.DS_Store
""" + _H2T_LINT_ENTRIES,
    "rust": """\
target/
.env
.env.*
""" + _H2T_LINT_ENTRIES,
    "none": """\
.env
.env.*
*.log
""" + _H2T_LINT_ENTRIES,
}

DCC_GITIGNORE = """\
*.cache
*.bak
Backup/
.env
.env.*
""" + _H2T_LINT_ENTRIES
```

### Step 1.4: Fix docs-init — add lint temp files to .gitignore append section

In `plugins/h2t-dev/skills/docs-init/scripts/init.py`, lines 200-209:

Replace:

```python
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
```

With:

```python
    # .gitignore — create if missing, append missing entries
    gi = rp / ".gitignore"
    gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    _gi_entries = [
        ("docs/.artifacts/", "# Documentation artifacts"),
        (".h2t/lint-before.json", "# docs-lint temp files"),
        (".h2t/lint-after.json", None),
    ]
    for gi_entry, gi_comment in _gi_entries:
        if gi_entry not in gi_content:
            if not dry_run:
                with open(gi, "a", encoding="utf-8") as f:
                    if gi_comment:
                        f.write(f"\n{gi_comment}\n")
                    f.write(f"{gi_entry}\n")
                gi_content += f"\n{gi_entry}\n"
            print(f"  {action}: .gitignore entry for {gi_entry}")
            if ".gitignore" not in changes:
                changes.append(".gitignore")
```

### Step 1.5: Run tests to verify they pass

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py::test_gitignore_python_includes_lint_temp_files tests/scaffold/test_scaffold_steps.py::test_gitignore_none_includes_lint_temp_files tests/scaffold/test_scaffold_steps.py::test_gitignore_dcc_includes_lint_temp_files tests/docs/test_docs_init_repo_root.py::test_init_repo_adds_lint_temp_files_to_gitignore -v
```

Expected: 4 PASSED.

### Step 1.6: Run full test suite (smoke)

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ tests/docs/ -v --tb=short
```

Expected: all existing tests PASS, 4 new PASS.

### Step 1.7: Commit

```
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-init/scripts/init.py
git -C C:/dev/h2t-skills add tests/scaffold/test_scaffold_steps.py
git -C C:/dev/h2t-skills add tests/docs/test_docs_init_repo_root.py
```

```
git -C C:/dev/h2t-skills commit -m "fix(scaffold+docs-init): add lint temp files to .gitignore templates closes #268"
```

---

## Task 2: docs-init initializes .h2t/lint-state.jsonl

**Closes:** #266

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-init/scripts/init.py`
- Test: `tests/docs/test_docs_init_repo_root.py`

### Step 2.1: Write failing test

In `tests/docs/test_docs_init_repo_root.py`, add:

```python
def test_init_repo_creates_h2t_lint_state(tmp_path):
    """docs-init creates .h2t/lint-state.jsonl so it's tracked from day 0."""
    repo = tmp_path / "my-repo"
    repo.mkdir()

    init_repo("my-repo", repo_root=repo, dry_run=False, commit=False)

    lint_state = repo / ".h2t" / "lint-state.jsonl"
    assert lint_state.exists(), ".h2t/lint-state.jsonl must be created by docs-init"
```

### Step 2.2: Run test to verify it fails

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py::test_init_repo_creates_h2t_lint_state -v
```

Expected: FAILED (FileNotFoundError or AssertionError).

### Step 2.3: Add lint-state.jsonl init to docs-init

In `plugins/h2t-dev/skills/docs-init/scripts/init.py`, make two changes:

**Change A:** In `init_repo()`, update the final `git_add_commit()` call (line 212) to include `.h2t/`:

Before:
```python
        git_add_commit(rp, ["docs/", ".claude/", ".pymarkdown.yaml", ".vale.ini", ".gitignore"],
                       "docs: scaffold standard documentation structure")
```

After:
```python
        git_add_commit(rp, ["docs/", ".claude/", ".h2t/", ".pymarkdown.yaml", ".vale.ini", ".gitignore"],
                       "docs: scaffold standard documentation structure")
```

**Change B:** Add a new block after the `.vale.ini` block (after line 198) and before the `.gitignore` block:

```python
    # .h2t/lint-state.jsonl — initialize empty so it's trackable from day 0
    lint_state = rp / ".h2t" / "lint-state.jsonl"
    if not lint_state.exists():
        if not dry_run:
            lint_state.parent.mkdir(parents=True, exist_ok=True)
            lint_state.write_text("", encoding="utf-8")
        print(f"  {action}: .h2t/lint-state.jsonl")
        changes.append(".h2t/lint-state.jsonl")
```

### Step 2.4: Run test to verify it passes

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py::test_init_repo_creates_h2t_lint_state -v
```

Expected: PASSED.

### Step 2.5: Run full docs-init tests

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py -v
```

Expected: all PASSED.

### Step 2.6: Commit

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-init/scripts/init.py
git -C C:/dev/h2t-skills add tests/docs/test_docs_init_repo_root.py
```

```
git -C C:/dev/h2t-skills commit -m "fix(docs-init): create .h2t/lint-state.jsonl on init closes #266"
```

---

## Task 3: scaffold validates docs-init critical paths

**Closes:** #262

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py:279-282`
- Test: `tests/scaffold/test_scaffold_steps.py`

### Step 3.1: Write failing test

In `tests/scaffold/test_scaffold_steps.py`, add after the last test:

```python
def test_cmd_create_fails_when_docs_init_ok_but_paths_missing(tmp_path, monkeypatch):
    """scaffold returns error if docs-init reports ok but critical docs paths are absent.

    This catches the silent-skip case where docs-init returns status='ok' but
    didn't actually write any files (e.g. script path mismatch).
    """
    import scaffold_project
    import argparse
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "ok", "output": ""}):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                args = argparse.Namespace(
                    id="test-proj", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False, merge=False,
                )
                result = scaffold_project.cmd_create(args)

    # docs-init reported ok but docs/README.md was never created
    assert result["status"] == "error"
    assert "docs-init" in result["error"].lower() or "missing" in result["error"].lower()


def test_cmd_create_succeeds_when_docs_init_ok_and_paths_present(tmp_path, monkeypatch):
    """scaffold succeeds when docs-init ok AND critical paths exist."""
    import scaffold_project
    import argparse
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})

    def fake_docs_init(repo_name, project_dir, *, template="code_repo"):
        # Simulate real docs-init: create critical paths matching REQUIRED_CORE_DIRS
        (project_dir / "docs" / "README.md").parent.mkdir(parents=True, exist_ok=True)
        (project_dir / "docs" / "README.md").write_text("# docs\n")
        (project_dir / "docs" / "adr").mkdir(exist_ok=True)
        (project_dir / "docs" / "reports").mkdir(exist_ok=True)
        (project_dir / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
        (project_dir / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "output": ""}

    with patch("scaffold_project.run_docs_init", side_effect=fake_docs_init):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                args = argparse.Namespace(
                    id="test-proj2", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False, merge=False,
                )
                result = scaffold_project.cmd_create(args)

    assert result["status"] == "ok"
```

### Step 3.2: Run tests to verify they fail

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py::test_cmd_create_fails_when_docs_init_ok_but_paths_missing tests/scaffold/test_scaffold_steps.py::test_cmd_create_succeeds_when_docs_init_ok_and_paths_present -v
```

Expected: first test FAILED (got status='ok' instead of 'error'), second test MAY pass.

### Step 3.3: Add validation to cmd_create in scaffold_project.py

In `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`, replace lines 279-282:

**Before:**
```python
    di = run_docs_init(args.id, project_dir, template=template)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di['error']}"}
```

**After:**
```python
    di = run_docs_init(args.id, project_dir, template=template)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di.get('error', '')}"}
    if di["status"] == "ok":
        _critical_files = ["docs/README.md"]
        _critical_dirs = [
            "docs/adr", "docs/reports",
            "docs/superpowers/specs", "docs/superpowers/plans",
        ]
        _missing = [
            p for p in _critical_files if not (project_dir / p).is_file()
        ] + [
            p for p in _critical_dirs if not (project_dir / p).is_dir()
        ]
        if _missing:
            return {
                "status": "error",
                "error": f"docs-init reported ok but critical paths missing: {_missing}",
            }
    if di["status"] == "skip":
        actions.append("WARNING: docs-init skipped — docs structure may be incomplete")
```

### Step 3.4: Run tests to verify they pass

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py::test_cmd_create_fails_when_docs_init_ok_but_paths_missing tests/scaffold/test_scaffold_steps.py::test_cmd_create_succeeds_when_docs_init_ok_and_paths_present -v
```

Expected: 2 PASSED.

### Step 3.5: Fix existing test that mocks docs-init with skip

The test `test_cmd_create_code_repo_root_dirs` (line 268) patches `run_docs_init` to return `{"status": "skip"}`. With the new validation, `skip` is NOT checked for critical paths (only `ok` triggers validation). Also check it has `merge=False` in `argparse.Namespace` — if not, add it. Verify this test still passes:

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py::test_cmd_create_code_repo_root_dirs -v
```

Expected: PASSED (skip bypasses path validation — acceptable since skip means h2t-dev not installed).

### Step 3.6: Run full scaffold tests

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v --tb=short
```

Expected: all PASSED.

### Step 3.7: Commit

```
git -C C:/dev/h2t-skills add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py
git -C C:/dev/h2t-skills add tests/scaffold/test_scaffold_steps.py
```

```
git -C C:/dev/h2t-skills commit -m "fix(scaffold): validate docs-init critical paths after ok status closes #262"
```

---

## Task 4: fix-index dynamic section discovery

**Closes:** #263

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-index/scripts/index.py:89-113`
- Test: `tests/docs/test_index_navigation.py`

The current `_SECTION_MAP` hardcodes 4 sections for Quick Links. Files in `docs/research/`, `docs/product/`, `docs/architecture/` etc. are created by docs-init but never appear in Quick Links → marked orphan by docs-lint.

Fix: replace hardcoded `_SECTION_MAP` lookup in `build_navigation_index()` with dynamic scan of `docs/` subdirs.

### Step 4.1: Write failing tests

In `tests/docs/test_index_navigation.py`, add:

```python
def test_build_navigation_index_includes_research_dir_in_quick_links(tmp_path):
    """docs/research/ dir with content must appear in Quick Links."""
    research_dir = tmp_path / "docs" / "research"
    research_dir.mkdir(parents=True)
    (research_dir / "2026-06-01-analysis.md").write_text("# Analysis\n")

    result = build_navigation_index(tmp_path, "my-repo")

    assert "## Quick Links" in result
    assert "research" in result.lower()


def test_build_navigation_index_includes_unknown_dir_in_quick_links(tmp_path):
    """Any docs/ subdir with .md files appears in Quick Links, even if not in known list."""
    custom_dir = tmp_path / "docs" / "custom-section"
    custom_dir.mkdir(parents=True)
    (custom_dir / "notes.md").write_text("# Notes\n")

    result = build_navigation_index(tmp_path, "my-repo")

    assert "custom-section" in result


def test_build_navigation_index_excludes_empty_dirs_from_quick_links(tmp_path):
    """Dirs with no .md files do not appear in Quick Links."""
    empty_dir = tmp_path / "docs" / "empty-section"
    empty_dir.mkdir(parents=True)

    result = build_navigation_index(tmp_path, "my-repo")

    assert "empty-section" not in result


def test_build_navigation_index_excludes_adr_from_quick_links(tmp_path):
    """adr/ has its own table — must not also appear in Quick Links."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-test.md").write_text("# Test\n")

    result = build_navigation_index(tmp_path, "my-repo")

    # ADR appears in Architecture Decisions table, not Quick Links
    assert "## Architecture Decisions" in result
    # Quick Links should not list adr as a section
    lines = [l for l in result.splitlines() if "## Quick Links" in l or ("[adr]" in l.lower())]
    # No Quick Links row pointing to adr/
    assert not any("[adr]" in l.lower() for l in result.splitlines())
```

### Step 4.2: Run tests to verify they fail

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_index_navigation.py::test_build_navigation_index_includes_research_dir_in_quick_links tests/docs/test_index_navigation.py::test_build_navigation_index_includes_unknown_dir_in_quick_links tests/docs/test_index_navigation.py::test_build_navigation_index_excludes_empty_dirs_from_quick_links -v
```

Expected: first 2 FAILED, third may pass.

### Step 4.3: Refactor build_navigation_index for dynamic section discovery

In `plugins/h2t-dev/skills/docs-index/scripts/index.py`, replace lines 89-113:

**Before:**
```python
_SECTION_MAP = [
    ("superpowers", "Specs & Plans", "Design specs and implementation plans"),
    ("reports",     "Reports",       "Milestone reports"),
    ("guides",      "Guides",        "How-to documentation"),
    ("api",         "API",           "API reference"),
]


def build_navigation_index(rp: Path, repo_name: str) -> str:
    docs_dir = rp / "docs"
    lines = [f"# {repo_name} Documentation", ""]

    # Quick Links — only when at least one section dir exists (adr excluded: has own table)
    present = [
        (anchor, title, desc)
        for anchor, title, desc in _SECTION_MAP
        if (docs_dir / anchor).exists()
    ]
    if present:
        lines += ["## Quick Links", ""]
        lines += ["| Section | Description |", "|---------|-------------|"]
        for anchor, title, desc in present:
            lines.append(f"| [{title}]({anchor}/) | {desc} |")
        lines.append("")
```

**After:**
```python
# Known section metadata — anchor → (title, description)
_KNOWN_SECTIONS: dict[str, tuple[str, str]] = {
    "superpowers": ("Specs & Plans", "Design specs and implementation plans"),
    "reports":     ("Reports",       "Milestone reports"),
    "guides":      ("Guides",        "How-to documentation"),
    "api":         ("API",           "API reference"),
    "research":    ("Research",      "Research documents"),
    "product":     ("Product",       "Product documentation"),
    "marketing":   ("Marketing",     "Marketing documentation"),
    "architecture":("Architecture",  "Architecture documentation"),
    "client":      ("Client",        "Client documentation"),
}

# These dirs have dedicated sections in the index — exclude from Quick Links
_QUICK_LINKS_EXCLUDE = {"adr", ".artifacts"}


def _discover_sections(docs_dir: Path) -> list[tuple[str, str, str]]:
    """Return (anchor, title, description) for all docs/ subdirs that have .md files."""
    if not docs_dir.exists():
        return []
    result = []
    for d in sorted(docs_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name in _QUICK_LINKS_EXCLUDE or d.name.startswith("."):
            continue
        if not any(d.rglob("*.md")):
            continue
        anchor = d.name
        title, desc = _KNOWN_SECTIONS.get(anchor, (anchor.replace("-", " ").title(), f"{anchor.title()} documents"))
        result.append((anchor, title, desc))
    return result


def build_navigation_index(rp: Path, repo_name: str) -> str:
    docs_dir = rp / "docs"
    lines = [f"# {repo_name} Documentation", ""]

    # Quick Links — dynamic: scan all docs/ subdirs with .md content
    present = _discover_sections(docs_dir)
    if present:
        lines += ["## Quick Links", ""]
        lines += ["| Section | Description |", "|---------|-------------|"]
        for anchor, title, desc in present:
            lines.append(f"| [{title}]({anchor}/) | {desc} |")
        lines.append("")
```

**Also add** after the existing `reports` collection block (after line ~150), individual file tables for any discovered section NOT already handled by the explicit blocks (superpowers/specs, superpowers/plans, reports):

```python
    # Dynamic sections — generate individual file links so orphan detector can follow them
    _HANDLED_SECTIONS = {"superpowers", "adr", "reports"}
    for anchor, title, _desc in present:
        if anchor in _HANDLED_SECTIONS:
            continue
        section_files = _collect_dir(rp, anchor)
        if section_files:
            lines += [f"## {title}", ""]
            lines += ["| Title | Date |", "|-------|------|"]
            for r in section_files:
                lines.append(f"| [{r['title']}]({anchor}/{r['file']}) | {r['date']} |")
            lines.append("")
```

This must be inserted **after** the `reports` block and **before** the custom-sections extraction. The orphan detector follows `.md` file links — directory links do not resolve. Without individual file links, `docs/research/foo.md` remains orphan regardless of Quick Links.

### Step 4.4: Run tests to verify they pass

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_index_navigation.py -v
```

Expected: all PASSED including 4 new tests.

### Step 4.5: Run full docs test suite

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v --tb=short
```

Expected: all PASSED.

### Step 4.6: Commit

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-index/scripts/index.py
git -C C:/dev/h2t-skills add tests/docs/test_index_navigation.py
```

```
git -C C:/dev/h2t-skills commit -m "fix(docs-index): dynamic section discovery — Quick Links scans all docs/ subdirs closes #263"
```

---

## Task 5: Version bump and deploy

**Files:**
- `plugins/h2t-core/plugin.json` — bump patch
- `plugins/h2t-dev/plugin.json` — bump patch

### Step 5.1: Run full test suite (final gate)

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ tests/docs/ -v --tb=short
```

Expected: all PASSED.

### Step 5.2: Bump h2t-core version

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-core patch
```

Expected: `h2t-core X.Y.Z → X.Y.Z+1` printed.

### Step 5.3: Bump h2t-dev version

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev patch
```

Expected: `h2t-dev X.Y.Z → X.Y.Z+1` printed.

### Step 5.4: Commit version bumps

```
git -C C:/dev/h2t-skills add plugins/h2t-core/plugin.json plugins/h2t-dev/plugin.json
git -C C:/dev/h2t-skills add plugins/h2t-core/CHANGELOG.md plugins/h2t-dev/CHANGELOG.md
```

```
git -C C:/dev/h2t-skills commit -m "chore: bump h2t-core and h2t-dev patch — lifecycle OS fixes"
```

### Step 5.5: Push and deploy

```
git -C C:/dev/h2t-skills push origin main
```

After push, in Claude Code session:
```
/plugin marketplace update lichtpfad
/reload-plugins
```

---

## Out of Scope (separate plans)

- **#264** — frontmatter templates: `fix-safe` already handles missing frontmatter; create separate plan for adding frontmatter block to `writing-plans` SKILL.md header template
- **#265** — config unification (`.h2t/docs-lint.yaml` vs `.claude/rules/`): risky refactor, needs migration path
- **#267** — `docs-init --finalize` flag to auto-run fix-index: nice-to-have, separate plan
