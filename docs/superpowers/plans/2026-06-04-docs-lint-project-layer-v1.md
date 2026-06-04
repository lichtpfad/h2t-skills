# docs-lint Project-Layer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend docs-lint with a deterministic project-layer check suite (root structure, gitignore hygiene, agent instructions structural audit) gated by `project_checks: true` in docs-lint.yaml.

**Architecture:** Three new `lib/docs/` modules (`root_structure`, `gitignore_hygiene`, `agent_instructions`) each exporting pure functions; `lint.py` imports them lazily and routes into the existing `_collect_all_findings`/`_run_audit`/`_run_fix_safe` pipeline behind a `project_checks` config flag. No LLM, no file mutations beyond .gitignore fix-safe, no CLI changes.

**Tech Stack:** Python 3.11, stdlib only (`re`, `fnmatch`, `pathlib`); pytest + tmp_path for tests; existing `docs.reporter.finding()` for finding dicts; `docs.config.load_config()` for config; `docs.project_types.PROJECT_TYPES` for template specs.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `plugins/h2t-dev/lib/docs/root_structure.py` | STANDARD_ALLOWLIST, check_root_structure, check_root_readmes |
| Create | `plugins/h2t-dev/lib/docs/gitignore_hygiene.py` | check_gitignore_hygiene, fix_gitignore_hygiene |
| Create | `plugins/h2t-dev/lib/docs/agent_instructions.py` | Deterministic .claude/* structural checks |
| Create | `tests/docs/test_root_structure.py` | Unit tests for root_structure module |
| Create | `tests/docs/test_gitignore_hygiene.py` | Unit tests for gitignore_hygiene module |
| Create | `tests/docs/test_agent_instructions.py` | Unit tests for agent_instructions module |
| Modify | `plugins/h2t-dev/lib/docs/config.py` | Add `custom_root_dirs` and `project_checks` defaults |
| Modify | `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | Wire project layer into pipeline |
| Modify | `tests/docs/test_config.py` | Tests for new config defaults |
| Modify | `tests/docs/test_lint_checks.py` | Integration tests for project_checks gate |

---

## Task 1: Config Extension — `custom_root_dirs` and `project_checks`

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Modify: `tests/docs/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/docs/test_config.py`:

```python
def test_custom_root_dirs_default_empty(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["custom_root_dirs"] == []


def test_project_checks_default_false(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["project_checks"] is False


def test_custom_root_dirs_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text(
        "custom_root_dirs:\n  - nimbalyst-local\n  - client-tools\n"
    )
    cfg = load_config(tmp_path)
    assert "nimbalyst-local" in cfg["custom_root_dirs"]
    assert "client-tools" in cfg["custom_root_dirs"]


def test_project_checks_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("project_checks: true\n")
    cfg = load_config(tmp_path)
    assert cfg["project_checks"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v -k "custom_root_dirs or project_checks"
```

Expected: FAIL with `KeyError: 'custom_root_dirs'` or `AssertionError`.

- [ ] **Step 3: Add defaults to config.py**

In `plugins/h2t-dev/lib/docs/config.py`, the `_DEFAULTS` dict currently ends with `"template": None`. Add two new keys:

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
    "custom_root_dirs": [],
    "project_checks": False,
}
```

- [ ] **Step 4: Run tests to verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py tests/docs/test_config.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add custom_root_dirs and project_checks config defaults"
```

---

## Task 2: `lib/docs/root_structure.py` — Allowlist-Based Root Checks

**Files:**
- Create: `plugins/h2t-dev/lib/docs/root_structure.py`
- Create: `tests/docs/test_root_structure.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/docs/test_root_structure.py`:

```python
"""Unit tests for docs.root_structure module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.root_structure import check_root_structure, check_root_readmes, STANDARD_ALLOWLIST


# --- check_root_structure ---

def test_allowlist_items_not_flagged(tmp_path):
    """Standard items (README.md, pyproject.toml, .gitignore, docs/) are not flagged."""
    (tmp_path / "README.md").write_text("")
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / ".gitignore").write_text("")
    (tmp_path / "docs").mkdir()
    result = check_root_structure(tmp_path)
    assert result == [], f"Standard items should not produce findings: {result}"


def test_template_root_dirs_not_flagged(tmp_path):
    """Dirs from template spec (code_repo: src, tests) are not flagged."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    result = check_root_structure(tmp_path, template="code_repo")
    paths = [f["path"] for f in result]
    assert "src/" not in paths
    assert "tests/" not in paths


def test_custom_root_dirs_not_flagged(tmp_path):
    """custom_root_dirs items are not flagged."""
    (tmp_path / "nimbalyst-local").mkdir()
    result = check_root_structure(tmp_path, custom_root_dirs=["nimbalyst-local"])
    paths = [f["path"] for f in result]
    assert "nimbalyst-local/" not in paths


def test_temp_file_at_root_flagged_as_warn(tmp_path):
    """Files matching TEMP_PATTERNS get severity=warn finding."""
    (tmp_path / "session_analysis.txt").write_text("")
    result = check_root_structure(tmp_path)
    assert len(result) == 1
    assert result[0]["severity"] == "warn"
    assert "temp file" in result[0]["message"]
    assert result[0]["path"] == "session_analysis.txt"


def test_tmp_file_flagged_as_warn(tmp_path):
    """*.tmp file at root → warn finding."""
    (tmp_path / "scratch.tmp").write_text("")
    result = check_root_structure(tmp_path)
    assert any(f["severity"] == "warn" and "scratch.tmp" in f["path"] for f in result)


def test_unknown_item_flagged_as_info(tmp_path):
    """Unknown item not matching any pattern → severity=info finding."""
    (tmp_path / "my-weird-dir").mkdir()
    result = check_root_structure(tmp_path)
    assert len(result) == 1
    assert result[0]["severity"] == "info"
    assert "unknown root item" in result[0]["message"]
    assert "custom_root_dirs" in result[0]["message"]


def test_git_dir_skipped(tmp_path):
    """.git dir is silently skipped."""
    (tmp_path / ".git").mkdir()
    result = check_root_structure(tmp_path)
    assert result == []


def test_venv_dir_skipped(tmp_path):
    """.venv dir is silently skipped."""
    (tmp_path / ".venv").mkdir()
    result = check_root_structure(tmp_path)
    assert result == []


def test_empty_root_no_findings(tmp_path):
    """Completely empty root → no findings."""
    result = check_root_structure(tmp_path)
    assert result == []


def test_finding_type_is_root_structure(tmp_path):
    """Unknown item findings have type='root_structure'."""
    (tmp_path / "mystery-folder").mkdir()
    result = check_root_structure(tmp_path)
    assert all(f["type"] == "root_structure" for f in result)


# --- check_root_readmes ---

def test_root_readmes_present_no_findings(tmp_path):
    """All template root dirs have README.md → no findings."""
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
        (tmp_path / d / "README.md").write_text("")
    result = check_root_readmes(tmp_path, "code_repo")
    assert result == []


def test_root_readmes_missing_flagged(tmp_path):
    """Template root dir missing README.md → info finding."""
    (tmp_path / "src").mkdir()
    # No README.md in src/
    result = check_root_readmes(tmp_path, "code_repo")
    src_findings = [f for f in result if "src" in f["path"]]
    assert src_findings, "Missing README.md in src/ should produce a finding"
    assert src_findings[0]["severity"] == "info"


def test_root_readmes_missing_dir_not_flagged(tmp_path):
    """Dirs that don't exist are not flagged by check_root_readmes (already handled by check_project_structure_typed)."""
    # src/ doesn't exist at all — check_project_structure_typed handles this
    result = check_root_readmes(tmp_path, "code_repo")
    # Finding should not mention src because the dir itself doesn't exist
    src_findings = [f for f in result if "src/" in f["path"]]
    assert src_findings == []


def test_root_readmes_unknown_template_returns_empty(tmp_path):
    """Unknown template → no findings, no crash."""
    result = check_root_readmes(tmp_path, "nonexistent_type")
    assert result == []


def test_root_readmes_finding_type(tmp_path):
    """check_root_readmes findings have type='root_readmes'."""
    (tmp_path / "src").mkdir()
    result = check_root_readmes(tmp_path, "code_repo")
    assert all(f["type"] == "root_readmes" for f in result)
```

- [ ] **Step 2: Run tests to verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_root_structure.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docs.root_structure'`.

- [ ] **Step 3: Create `plugins/h2t-dev/lib/docs/root_structure.py`**

```python
"""Root structure validation for docs-lint project-layer (v1 — deterministic, no LLM)."""
from __future__ import annotations
import fnmatch
from pathlib import Path

STANDARD_ALLOWLIST: frozenset[str] = frozenset({
    # VCS
    ".git", ".gitignore", ".gitattributes", ".github",
    # Agent/tool config
    ".claude", ".editorconfig", ".h2t",
    # Standard project dirs (required or near-universal)
    "docs", "data", "src", "tests", "test", "scripts", "assets",
    "dist", "build",
    # Tool config files required by check_structure / docs-lint itself
    ".pymarkdown.yaml", ".vale.ini",
    # Project docs
    "README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE",
    "docs-lint-plan.yaml",
    # Python
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "uv.lock", ".pytest_cache", "__pycache__",
    # Node
    "package.json", "package-lock.json", "pnpm-lock.yaml", "node_modules",
    ".prettierrc", ".prettierrc.json", ".eslintrc.json",
    "tsconfig.json", "tsconfig.base.json",
    # Rust / Go
    "Cargo.toml", "go.mod",
    # Build
    "Makefile", "Dockerfile", "docker-compose.yml",
    # Misc
    ".env.example",
})

TEMP_PATTERNS: tuple[str, ...] = (
    "*.tmp", "*.log", "session_*.txt", "full_messages.txt",
    "cryo_*.txt", "*_analysis.txt", "*_summary.txt",
)

# Items with their own dedicated check in check_repo_root — skip to avoid duplicate findings.
_LEGACY_BANNED: frozenset[str] = frozenset({"temp", "old", "backup", "tmp", "archive_old"})

_ALWAYS_SKIP: frozenset[str] = frozenset({
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "node_modules", ".ruff_cache", ".vscode", ".idea",
})


def check_root_structure(
    rp: Path,
    template: str | None = None,
    custom_root_dirs: list[str] | None = None,
) -> list[dict]:
    """Return findings for root items not in allowlist.

    Severity:
    - warn  → matches a TEMP_PATTERNS glob (temp file, should be gitignored)
    - info  → unknown item (may be intentional — add to custom_root_dirs)

    Items already handled by check_repo_root (_LEGACY_BANNED) are skipped to avoid
    duplicate findings. Items in _ALWAYS_SKIP are silently ignored.
    """
    from docs.reporter import finding as make_finding
    from docs.project_types import PROJECT_TYPES

    allowed: set[str] = set(STANDARD_ALLOWLIST)
    if template:
        spec = PROJECT_TYPES.get(template)
        if spec:
            allowed.update(spec.get("root_dirs", []))
    allowed.update(custom_root_dirs or [])

    findings: list[dict] = []
    for item in sorted(rp.iterdir()):
        name = item.name
        if name in _ALWAYS_SKIP:
            continue
        if name.lower() in _LEGACY_BANNED:
            continue  # check_repo_root already reports these
        if name in allowed:
            continue

        rel = name + ("/" if item.is_dir() else "")
        is_temp = any(fnmatch.fnmatch(name, pat) for pat in TEMP_PATTERNS)
        if is_temp:
            findings.append(make_finding(
                "root_structure", "warn", rel,
                f"temp file at root: {name} — add pattern to .gitignore",
            ))
        else:
            findings.append(make_finding(
                "root_structure", "info", rel,
                f"unknown root item: {name} — add to custom_root_dirs in docs-lint.yaml if intentional",
            ))
    return findings


def check_root_readmes(rp: Path, template: str) -> list[dict]:
    """Return info findings for template root_dirs missing a README.md.

    Only checks dirs that actually exist on disk — missing dirs are
    already reported by check_project_structure_typed.
    """
    from docs.reporter import finding as make_finding
    from docs.project_types import PROJECT_TYPES

    spec = PROJECT_TYPES.get(template)
    if spec is None:
        return []

    findings: list[dict] = []
    for d in spec.get("root_dirs", []):
        dir_path = rp / d
        if not dir_path.is_dir():
            continue
        if not (dir_path / "README.md").exists():
            findings.append(make_finding(
                "root_readmes", "info", f"{d}/README.md",
                f"missing README.md in root dir: {d}/",
            ))
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_root_structure.py -v
```

Expected: all 15 tests PASS.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/root_structure.py tests/docs/test_root_structure.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add root_structure module — allowlist-based root item validation"
```

---

## Task 3: `lib/docs/gitignore_hygiene.py` — Check and Fix

**Files:**
- Create: `plugins/h2t-dev/lib/docs/gitignore_hygiene.py`
- Create: `tests/docs/test_gitignore_hygiene.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/docs/test_gitignore_hygiene.py`:

```python
"""Unit tests for docs.gitignore_hygiene module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene


def test_no_temp_files_no_findings(tmp_path):
    """No temp files at root → no findings."""
    result = check_gitignore_hygiene(tmp_path)
    assert result == []


def test_temp_file_in_gitignore_no_finding(tmp_path):
    """Temp file exists but pattern is already in .gitignore → no finding."""
    (tmp_path / "session_analysis.txt").write_text("")
    (tmp_path / ".gitignore").write_text("*_analysis.txt\n")
    result = check_gitignore_hygiene(tmp_path)
    assert result == []


def test_temp_file_not_in_gitignore_produces_finding(tmp_path):
    """Temp file at root, pattern not in .gitignore → single finding."""
    (tmp_path / "cryo_items.txt").write_text("")
    (tmp_path / ".gitignore").write_text("*.py\n")
    result = check_gitignore_hygiene(tmp_path)
    assert len(result) == 1
    assert result[0]["type"] == "gitignore_hygiene"
    assert result[0]["severity"] == "info"
    assert "cryo_*.txt" in result[0]["message"]


def test_multiple_missing_patterns_one_finding(tmp_path):
    """Multiple unignored temp files → single consolidated finding."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / "session_x.txt").write_text("")
    result = check_gitignore_hygiene(tmp_path)
    assert len(result) == 1
    assert "2" in result[0]["message"] or "*.tmp" in result[0]["message"]


def test_no_gitignore_file_temp_files_flagged(tmp_path):
    """No .gitignore at all but temp files present → finding."""
    (tmp_path / "scratch.tmp").write_text("")
    result = check_gitignore_hygiene(tmp_path)
    assert len(result) == 1


def test_fix_appends_missing_patterns(tmp_path):
    """fix_gitignore_hygiene appends unignored patterns to .gitignore."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / ".gitignore").write_text("*.py\n")
    changes = fix_gitignore_hygiene(tmp_path)
    assert len(changes) >= 1
    content = (tmp_path / ".gitignore").read_text()
    assert "*.tmp" in content


def test_fix_no_op_when_already_ignored(tmp_path):
    """fix_gitignore_hygiene does nothing if pattern already in .gitignore."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / ".gitignore").write_text("*.tmp\n")
    changes = fix_gitignore_hygiene(tmp_path)
    assert changes == []


def test_fix_creates_gitignore_if_missing(tmp_path):
    """fix_gitignore_hygiene creates .gitignore if it doesn't exist."""
    (tmp_path / "scratch.tmp").write_text("")
    fix_gitignore_hygiene(tmp_path)
    assert (tmp_path / ".gitignore").exists()
    content = (tmp_path / ".gitignore").read_text()
    assert "*.tmp" in content


def test_fix_preserves_existing_content(tmp_path):
    """fix_gitignore_hygiene preserves pre-existing .gitignore content."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    fix_gitignore_hygiene(tmp_path)
    content = (tmp_path / ".gitignore").read_text()
    assert "*.pyc" in content
    assert "__pycache__/" in content
    assert "*.tmp" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_gitignore_hygiene.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docs.gitignore_hygiene'`.

- [ ] **Step 3: Create `plugins/h2t-dev/lib/docs/gitignore_hygiene.py`**

```python
"""Gitignore hygiene checks: temp files at repo root not covered by .gitignore."""
from __future__ import annotations
import fnmatch
from pathlib import Path

from docs.root_structure import TEMP_PATTERNS


def _read_gitignore_patterns(rp: Path) -> list[str]:
    gi = rp / ".gitignore"
    if not gi.exists():
        return []
    return [
        line.strip()
        for line in gi.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def check_gitignore_hygiene(rp: Path) -> list[dict]:
    """Return a single consolidated finding if temp-pattern files exist at root
    but their pattern is absent from .gitignore."""
    from docs.reporter import finding as make_finding

    existing = set(_read_gitignore_patterns(rp))
    missing: list[str] = []
    for pat in TEMP_PATTERNS:
        if pat in existing:
            continue
        if list(rp.glob(pat)):
            missing.append(pat)

    if not missing:
        return []

    pattern_list = ", ".join(f'"{p}"' for p in missing)
    return [make_finding(
        "gitignore_hygiene", "info", ".gitignore",
        f"{len(missing)} temp pattern(s) not in .gitignore: {pattern_list} — run fix-safe to add",
    )]


def fix_gitignore_hygiene(rp: Path) -> list[str]:
    """Append missing temp patterns to .gitignore. Returns list of 'added: <pat>' strings."""
    existing = set(_read_gitignore_patterns(rp))
    missing: list[str] = []
    for pat in TEMP_PATTERNS:
        if pat in existing:
            continue
        if list(rp.glob(pat)):
            missing.append(pat)

    if not missing:
        return []

    gi = rp / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n# docs-lint: temp files\n" + "\n".join(missing) + "\n"
    gi.write_text(text, encoding="utf-8")
    return [f"added to .gitignore: {p}" for p in missing]
```

- [ ] **Step 4: Run tests to verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_gitignore_hygiene.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/gitignore_hygiene.py tests/docs/test_gitignore_hygiene.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add gitignore_hygiene module — temp pattern coverage check and fix"
```

---

## Task 4: `lib/docs/agent_instructions.py` — Deterministic `.claude/*` Audit

**Files:**
- Create: `plugins/h2t-dev/lib/docs/agent_instructions.py`
- Create: `tests/docs/test_agent_instructions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/docs/test_agent_instructions.py`:

```python
"""Unit tests for docs.agent_instructions module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.agent_instructions import check_agent_instructions


def test_no_claude_dir_returns_empty(tmp_path):
    """.claude/ dir absent → no findings, no crash."""
    result = check_agent_instructions(tmp_path)
    assert result == []


def test_required_rules_files_missing_flagged(tmp_path):
    """documentation.md and linting.md missing from .claude/rules/ → findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    result = check_agent_instructions(tmp_path)
    types = [f["message"] for f in result]
    assert any("documentation.md" in m for m in types)
    assert any("linting.md" in m for m in types)


def test_required_rules_files_present_not_flagged(tmp_path):
    """documentation.md and linting.md present → no 'missing required' finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text("# Docs rules")
    (rules / "linting.md").write_text("# Lint rules")
    result = check_agent_instructions(tmp_path)
    missing = [f for f in result if "missing required" in f["message"]]
    assert missing == []


def test_non_kebab_rules_file_flagged(tmp_path):
    """Rules file with uppercase → naming finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "MyRules.md").write_text("# bad name")
    result = check_agent_instructions(tmp_path)
    naming = [f for f in result if "not kebab-case" in f["message"]]
    assert naming, f"Expected kebab-case finding, got: {result}"
    assert naming[0]["severity"] == "warn"


def test_kebab_rules_file_not_flagged(tmp_path):
    """my-rules.md is valid kebab-case → no naming finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text("")
    (rules / "linting.md").write_text("")
    (rules / "my-custom-rules.md").write_text("")
    result = check_agent_instructions(tmp_path)
    naming = [f for f in result if "not kebab-case" in f["message"]]
    assert naming == []


def test_stale_absolute_path_in_rules_flagged(tmp_path):
    """Absolute path in backtick code span that doesn't exist → stale path finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text(
        "# Docs\n\nRun `C:/dev/nonexistent-repo/scripts/check.py` to verify.\n"
    )
    (rules / "linting.md").write_text("")
    result = check_agent_instructions(tmp_path)
    stale = [f for f in result if "stale path" in f["message"]]
    assert stale, f"Expected stale path finding, got: {result}"


def test_existing_absolute_path_not_flagged(tmp_path):
    """Absolute path in backtick that DOES exist → no stale path finding."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "documentation.md").write_text(
        f"# Docs\n\nConfig at `{str(tmp_path).replace(chr(92), '/')}`.\n"
    )
    (rules / "linting.md").write_text("")
    result = check_agent_instructions(tmp_path)
    stale = [f for f in result if "stale path" in f["message"]]
    assert stale == []


def test_claude_md_missing_commands_section_flagged(tmp_path):
    """CLAUDE.md without 'Key Commands' or 'Commands' heading → info finding."""
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Overview\n\nSome content.\n")
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "missing" in f["message"] and "Commands" in f["message"]]
    assert section_findings, f"Expected commands section finding, got: {result}"
    assert section_findings[0]["severity"] == "info"


def test_claude_md_with_key_commands_not_flagged(tmp_path):
    """CLAUDE.md with '## Key Commands' heading → no section finding."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Key Commands\n\n```bash\npython run.py\n```\n"
    )
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "Commands" in f.get("message", "")]
    assert section_findings == []


def test_claude_md_with_commands_heading_not_flagged(tmp_path):
    """CLAUDE.md with '## Commands' heading → no section finding."""
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n## Commands\n\n```bash\nnpm start\n```\n"
    )
    result = check_agent_instructions(tmp_path)
    section_findings = [f for f in result if "Commands" in f.get("message", "")]
    assert section_findings == []


def test_finding_type_is_agent_instructions(tmp_path):
    """All findings have type='agent_instructions'."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    result = check_agent_instructions(tmp_path)
    for f in result:
        assert f["type"] == "agent_instructions", f"Wrong type: {f}"
```

- [ ] **Step 2: Run tests to verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_agent_instructions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docs.agent_instructions'`.

- [ ] **Step 3: Create `plugins/h2t-dev/lib/docs/agent_instructions.py`**

```python
"""Deterministic audit of .claude/* agent instructions structure (v1 — no LLM)."""
from __future__ import annotations
import re
from pathlib import Path

_REQUIRED_RULES: frozenset[str] = frozenset({"documentation.md", "linting.md"})
_KEBAB_RE = re.compile(r'^[a-z0-9][a-z0-9-]*\.md$')
# Match backtick code spans that contain path-like strings.
# Only flags absolute paths (C:/... or /home/...) to minimize false positives.
# Relative paths are skipped — they can't be reliably resolved without knowing
# the working directory context. See issue #258 for v4 enhancement.
_CODE_SPAN_RE = re.compile(r'`([^`\n]{4,200})`')
_ABS_PATH_RE = re.compile(r'^[A-Za-z]:[\\/]|^/[a-z]')
_SECTION_RE = re.compile(r'^#{1,3}\s+(Key\s+Commands?|Commands?)\b', re.MULTILINE)


def _extract_absolute_code_span_paths(text: str) -> list[str]:
    """Extract absolute-path strings from backtick code spans."""
    results = []
    for m in _CODE_SPAN_RE.finditer(text):
        s = m.group(1).strip()
        if _ABS_PATH_RE.match(s) and ('/' in s or '\\' in s):
            # Strip trailing punctuation that might have been captured
            s = s.rstrip('.,;:)')
            results.append(s)
    return results


def _path_exists(candidate: str) -> bool:
    """Check if an absolute path candidate exists on the filesystem."""
    from pathlib import Path as _Path
    # Normalize backslashes
    norm = candidate.replace('\\', '/')
    try:
        return _Path(candidate).exists() or _Path(norm).exists()
    except (OSError, ValueError):
        return True  # Treat unparseable paths as non-stale


def check_agent_instructions(rp: Path) -> list[dict]:
    """Deterministic structural checks for .claude/* (v1 — no LLM clarity scoring).

    Checks:
    1. .claude/rules/documentation.md and linting.md present
    2. All .claude/rules/*.md filenames are kebab-case
    3. Absolute paths in backtick spans of rules/*.md exist on fs
    4. CLAUDE.md has a 'Key Commands' or 'Commands' section
    5. Absolute paths in backtick spans of CLAUDE.md exist on fs
    """
    from docs.reporter import finding as make_finding

    findings: list[dict] = []
    claude_dir = rp / ".claude"
    if not claude_dir.exists():
        return []

    rules_dir = claude_dir / "rules"
    if rules_dir.exists():
        # Required files
        for req in sorted(_REQUIRED_RULES):
            if not (rules_dir / req).exists():
                findings.append(make_finding(
                    "agent_instructions", "warn", f".claude/rules/{req}",
                    f"missing required rules file: .claude/rules/{req}",
                ))
        # Naming convention
        for f in sorted(rules_dir.glob("*.md")):
            if not _KEBAB_RE.match(f.name):
                findings.append(make_finding(
                    "agent_instructions", "warn", f".claude/rules/{f.name}",
                    f"rules file not kebab-case: {f.name}",
                ))
        # Stale absolute paths
        for f in sorted(rules_dir.glob("*.md")):
            text = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(rp)).replace("\\", "/")
            for candidate in _extract_absolute_code_span_paths(text):
                if not _path_exists(candidate):
                    findings.append(make_finding(
                        "agent_instructions", "info", rel,
                        f"stale path in {rel}: '{candidate}'",
                    ))

    # CLAUDE.md checks
    claude_md = rp / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8", errors="replace")
        if not _SECTION_RE.search(text):
            findings.append(make_finding(
                "agent_instructions", "info", "CLAUDE.md",
                "CLAUDE.md missing 'Key Commands' or 'Commands' section",
            ))
        for candidate in _extract_absolute_code_span_paths(text):
            if not _path_exists(candidate):
                findings.append(make_finding(
                    "agent_instructions", "info", "CLAUDE.md",
                    f"stale path in CLAUDE.md: '{candidate}'",
                ))

    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_agent_instructions.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/agent_instructions.py tests/docs/test_agent_instructions.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add agent_instructions module — deterministic .claude/* structural audit"
```

---

## Task 5: Wire Project Layer into `lint.py`

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Modify: `tests/docs/test_lint_checks.py`

### What to change in `lint.py`

**Imports** (add after existing `from docs.config import load_config` import, at top of file):

```python
try:
    from docs.root_structure import check_root_structure, check_root_readmes
    from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene
    from docs.agent_instructions import check_agent_instructions
    _PROJECT_LAYER_AVAILABLE = True
except ImportError:
    _PROJECT_LAYER_AVAILABLE = False
```

**`_collect_all_findings`** — add project layer calls at the end of the function, before `return all_findings`.

The function currently ends with:
```python
    for msg in check_frontmatter(rp):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))
    return all_findings
```

Change to:
```python
    for msg in check_frontmatter(rp):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))

    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        all_findings.extend(check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs))
        if template:
            all_findings.extend(check_root_readmes(rp, template))
        all_findings.extend(check_gitignore_hygiene(rp))
        all_findings.extend(check_agent_instructions(rp))

    return all_findings
```

**`_run_audit`** — add "Project Layer" section to the output. The sections list currently ends with:

```python
    sections = [
        ("Navigation / Orphans", orphans, ...),
        ("Naming", naming, ...),
        ("Structure", [...], ...),
        ("Metadata / Frontmatter", [...], ...),
    ]
```

Add a fifth section after the frontmatter section:

```python
        ("Project Layer", [f for f in all_findings if f["type"] in {
            "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
        }], lambda f: f"  {f['severity'].upper()}: [{f['type']}] {f['path']} — {f['message']}"),
```

To do this correctly, `_run_audit` must call `_collect_all_findings` instead of duplicating the logic. Currently `_run_audit` re-runs checks manually. Add project layer findings by collecting them separately:

After the existing section list definition, add:

```python
    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        project_findings = (
            check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs)
            + (check_root_readmes(rp, template) if template else [])
            + check_gitignore_hygiene(rp)
            + check_agent_instructions(rp)
        )
    else:
        project_findings = []
    sections.append(
        ("Project Layer", project_findings,
         lambda f: f"  {f['severity'].upper()}: [{f['type']}] {f['path']} — {f['message']}")
    )
```

**`_run_fix_safe`** — add gitignore hygiene fix when project_checks enabled. At the end of `_run_fix_safe`, before the final print, add:

```python
    if _PROJECT_LAYER_AVAILABLE:
        cfg = load_config(rp)
        if cfg.get("project_checks") and only in ("all",):
            gi_fixes = fix_gitignore_hygiene(rp)
            for f in gi_fixes:
                print(f"  FIX: {f}")
```

(This block goes after the `if only in ("all", "frontmatter"):` block and before `print("  Done. ...")`)

- [ ] **Step 1: Write failing integration tests**

Add to `tests/docs/test_lint_checks.py`:

```python
# --- Project layer integration ---

def test_project_layer_disabled_by_default(tmp_path):
    """Without project_checks: true, no project-layer findings appear."""
    # Set up a dir that would trigger root_structure finding
    (tmp_path / "mystery-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    assert project == [], f"Project layer should be off by default: {project}"


def test_project_layer_enabled_when_config_set(tmp_path):
    """project_checks: true in docs-lint.yaml enables project-layer findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    (tmp_path / "mystery-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] == "root_structure"]
    assert project, "Expected root_structure finding for unknown dir"


def test_custom_root_dirs_respected_in_collect(tmp_path):
    """custom_root_dirs in config suppress root_structure findings for listed items."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\ncustom_root_dirs:\n  - my-tool\n"
    )
    (tmp_path / "my-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] == "root_structure"]
    assert project == [], f"my-tool should be allowed via custom_root_dirs: {project}"


def test_gitignore_hygiene_finding_in_collect(tmp_path):
    """Temp file at root with project_checks: true → gitignore_hygiene finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    (tmp_path / "scratch.tmp").write_text("")
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    gi = [f for f in findings if f["type"] == "gitignore_hygiene"]
    assert gi, "Expected gitignore_hygiene finding for unignored .tmp file"


def test_agent_instructions_finding_in_collect(tmp_path):
    """Missing .claude/rules/documentation.md with project_checks: true → agent_instructions finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    ai = [f for f in findings if f["type"] == "agent_instructions"]
    assert ai, "Expected agent_instructions finding for missing required rules files"


def test_doctor_json_summary_includes_project_count(tmp_path):
    """doctor --json summary string includes project issue count when project_checks enabled."""
    import json as _json
    import sys as _sys
    import subprocess as _sp2
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return
    result = _sp2.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = _json.loads(result.stdout)
    assert "project issue" in data["summary"], (
        f"doctor summary should include project count: {data['summary']}"
    )
    # total must equal len(findings) — no silent drop
    assert data["status"] != "ok" or len(data["findings"]) == 0
    project_findings = [f for f in data["findings"] if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    # If project layer fired, there must be at least documentation.md missing
    assert project_findings, "Expected project layer findings with project_checks: true"
```

- [ ] **Step 2: Run tests to verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v -k "project_layer or gitignore_hygiene or agent_instructions"
```

Expected: FAIL — `test_project_layer_enabled_when_config_set` and others fail because lint.py doesn't call project layer yet.

- [ ] **Step 3: Apply the three edits to `lint.py`**

**Edit 1 — add imports** (after the existing `from docs.config import load_config` line):

```python
try:
    from docs.root_structure import check_root_structure, check_root_readmes
    from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene
    from docs.agent_instructions import check_agent_instructions
    _PROJECT_LAYER_AVAILABLE = True
except ImportError:
    _PROJECT_LAYER_AVAILABLE = False
```

**Edit 2 — `_collect_all_findings`**: find the block at the end of the function:

```python
    for msg in check_frontmatter(rp):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))
    return all_findings
```

Replace with:

```python
    for msg in check_frontmatter(rp):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))

    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        all_findings.extend(check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs))
        if template:
            all_findings.extend(check_root_readmes(rp, template))
        all_findings.extend(check_gitignore_hygiene(rp))
        all_findings.extend(check_agent_instructions(rp))

    return all_findings
```

**Edit 3 — `_run_audit`**: find the sections list definition. It currently defines 4 sections (Navigation/Orphans, Naming, Structure, Metadata/Frontmatter). After the list definition and before the `total = 0` line, add:

```python
    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        project_findings = (
            check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs)
            + (check_root_readmes(rp, template) if template else [])
            + check_gitignore_hygiene(rp)
            + check_agent_instructions(rp)
        )
    else:
        project_findings = []
    sections.append(
        ("Project Layer", project_findings,
         lambda f: f"  {f['severity'].upper()}: [{f['type']}] {f['path']} — {f['message']}"),
    )
```

Note: `_run_audit` already resolves `cfg`, `template`, and `extra` at its top. The `project_findings` block uses those same variables. Read the full `_run_audit` function before editing to confirm variable names match.

**Edit 4 — `_run_plan` human output**: find the block in `_run_plan` that filters findings into orphans/naming/structure (around line 571). After the `structure` variable is defined, add a `project` variable and section. Find:

```python
    print_header(f"docs-lint plan: {rp}")
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
```

Add `project` after `structure`:

```python
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
```

Then find the existing `if orphans:` / `if naming:` / `if structure:` blocks and add after them:

```python
    if project:
        print("\n## Project Layer\n")
        for f in project:
            print(f"  - [{f['type']}] {f['path']}: {f['message']}")
```

And update the final condition from:

```python
    if not orphans and not naming and not structure:
```

to:

```python
    if not orphans and not naming and not structure and not project:
```

**Edit 5 — `_run_doctor` summary**: find in `_run_doctor`:

```python
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    frontmatter = [f for f in all_findings if f["type"] == "frontmatter"]
    total = len(all_findings)
    summary = (
        f"{len(orphans)} orphan(s), {len(naming)} naming issue(s), "
        f"{len(structure)} structure issue(s), {len(frontmatter)} metadata issue(s)"
    )
```

Replace with:

```python
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    frontmatter = [f for f in all_findings if f["type"] == "frontmatter"]
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    total = len(all_findings)
    summary = (
        f"{len(orphans)} orphan(s), {len(naming)} naming issue(s), "
        f"{len(structure)} structure issue(s), {len(frontmatter)} metadata issue(s), "
        f"{len(project)} project issue(s)"
    )
```

**Edit 6 — `_run_fix_safe`**: find the `print("  Done. Renames/moves require ...")` line at the end of `_run_fix_safe` (the non-plan-file branch). Before that print, add:

```python
    if _PROJECT_LAYER_AVAILABLE:
        _cfg = load_config(rp)
        if _cfg.get("project_checks") and only in ("all",):
            gi_fixes = fix_gitignore_hygiene(rp)
            for fx in gi_fixes:
                print(f"  FIX: {fx}")
```

- [ ] **Step 4: Run all integration tests to verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v -k "project_layer or gitignore_hygiene or agent_instructions"
```

Expected: 6 new tests PASS.

- [ ] **Step 5: Run the full test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v --no-header -q
```

Expected: all previously passing tests still PASS, total count increased by ~35.

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): wire project-layer checks into lint.py pipeline behind project_checks flag"
```

---

## Task 6: Version Bump h2t-dev → 1.0.14

**Files:**
- Modify: `plugins/h2t-dev/.claude-plugin/plugin.json` (via bump script)
- Modify: `plugins/h2t-dev/CHANGELOG.md` (via bump script)

- [ ] **Step 1: Run bump script**

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev 1.0.14
```

Expected output: `h2t-dev bumped to 1.0.14`.

- [ ] **Step 2: Verify version in plugin.json**

```
python -c "import json; d=json.load(open('C:/dev/h2t-skills/plugins/h2t-dev/.claude-plugin/plugin.json')); print(d['version'])"
```

Expected: `1.0.14`

- [ ] **Step 3: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/.claude-plugin/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "chore(h2t-dev): bump to v1.0.14 — project-layer v1"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|------------------|------|
| `project_checks: false` default | Task 1 |
| `custom_root_dirs: []` default | Task 1 |
| STANDARD_ALLOWLIST (extended) | Task 2 |
| check_root_structure — temp_file finding (warn) | Task 2 |
| check_root_structure — unknown finding (info) | Task 2 |
| check_root_readmes — missing README.md in template dirs | Task 2 |
| check_gitignore_hygiene — temp patterns not in .gitignore | Task 3 |
| fix_gitignore_hygiene — fix-safe appends patterns | Task 3 |
| check_agent_instructions — required rules files present | Task 4 |
| check_agent_instructions — kebab-case naming | Task 4 |
| check_agent_instructions — stale paths in rules/*.md | Task 4 |
| check_agent_instructions — CLAUDE.md Commands section | Task 4 |
| check_agent_instructions — stale paths in CLAUDE.md | Task 4 |
| Wire into _collect_all_findings | Task 5 |
| Wire into _run_audit output | Task 5 |
| Wire into _run_plan human output | Task 5 |
| Wire into _run_doctor summary | Task 5 |
| Wire fix_gitignore_hygiene into fix-safe | Task 5 |
| project_checks gate (off by default) | Task 5 |

### What Is NOT in this plan (intentionally deferred)

- LLM judge for root items — #258 (v4)
- Agent instructions clarity scoring — #258 (v4)
- `plan --save` / `plan --apply` — #256/#257 (v2/v3)
- Harvest loop — #259 (v5)
- Cross-project audit (`--tier product`) — h2t-core:project-audit scope

### Known limitations (v1 design decisions)

- **Stale path detection** is conservative: only absolute paths in backtick code spans are checked. Relative paths are not checked (working directory ambiguity). This is intentional for v1 to avoid false positives. See #258 for v4 enhancement.
- **`_LEGACY_BANNED` skip**: items like `temp/`, `old/` are already caught by `check_repo_root` and skipped in `check_root_structure` to avoid duplicate findings.
- **`_run_audit` refactor not done**: `_run_audit` currently duplicates some logic from `_collect_all_findings`. A full refactor to make `_run_audit` call `_collect_all_findings` is a separate cleanup — not included here to minimize blast radius.
