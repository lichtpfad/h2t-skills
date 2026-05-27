---
title: "milestone-closure Enhancement — absorb docs-cleanup, docs-index + navigation template rewrite"
status: "draft"
date: "2026-05-27"
milestone: "skills-release"
---

# milestone-closure Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) Rewrite `index.py` to produce a navigation-first `docs/README.md` (Quick Links table + ADR table with links) instead of a file inventory. (2) Extend `milestone-closure` SKILL.md to invoke `docs-cleanup` and `docs-index` as mandatory checklist steps with dry-run preview gate before archival.

**Architecture:** `index.py` gains `build_navigation_index()` alongside existing `build_index()`; `main()` is wired to call the new function. `milestone-closure` SKILL.md adds Steps 3a/3b using the real CLI contracts. No new Python files; `milestone-closure` has no scripts — it stays a pure skill orchestrator. Tests cover navigation output, ADR links, and field names.

**Tech Stack:** Python 3.11, pytest, pathlib. No new dependencies.

---

## CLI Contracts (read before implementing)

| Script | Dry-run (preview) | Apply (write/execute) | Notes |
|--------|------------------|----------------------|-------|
| `docs-cleanup/scripts/cleanup.py` | `cleanup.py <repo>` | `cleanup.py <repo> --apply --milestone <tag>` | No `--repo`/`--dry-run` flags; default = dry-run |
| `docs-index/scripts/index.py` | `index.py <repo>` | `index.py <repo> --apply` | Prints to stdout without `--apply`; writes `docs/README.md` with `--apply` |

**`_collect_adrs()` schema:** `{"num": str, "file": str, "title": str, "status": str, "date": str}`
Key is `num`, not `number`. Link target: `adr/{file}`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `plugins/h2t-dev/skills/docs-index/scripts/index.py` | Modify | Add `build_navigation_index()` + wire into `main()` |
| `plugins/h2t-dev/skills/milestone-closure/SKILL.md` | Modify | Add Steps 3a/3b: docs-cleanup (preview then apply) + docs-index |
| `tests/docs/test_index_navigation.py` | Create | Unit tests for navigation template, ADR links, field schema |

---

### Task 0: Test infrastructure — `tests/docs/test_index_navigation.py`

**Files:**
- Create: `tests/docs/test_index_navigation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/docs/test_index_navigation.py`:

```python
"""Tests for docs-index navigation template output."""
import sys
from pathlib import Path

_INDEX_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-index/scripts"
sys.path.insert(0, str(_INDEX_DIR))
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from index import build_navigation_index


def test_build_navigation_index_has_repo_title(tmp_path):
    """Output starts with # {repo} Documentation."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "h2t-skills")
    assert "# h2t-skills Documentation" in result


def test_build_navigation_index_has_quick_links(tmp_path):
    """Quick Links section present when superpowers/ exists."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Quick Links" in result


def test_build_navigation_index_adr_section_has_link(tmp_path):
    """ADR table row contains markdown link to the file."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-use-python.md").write_text(
        "---\nstatus: accepted\ndate: 2026-01-01\n---\n# Use Python\n"
    )
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Architecture Decisions" in result
    # Must contain a markdown link: [title](adr/filename)
    assert "[Use Python](adr/0001-use-python.md)" in result


def test_build_navigation_index_adr_number_from_num_field(tmp_path):
    """ADR row uses 'num' field (not 'number') — correct schema from _collect_adrs."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0042-some-decision.md").write_text(
        "---\nstatus: proposed\ndate: 2026-03-01\n---\n# Some Decision\n"
    )
    result = build_navigation_index(tmp_path, "my-repo")
    assert "42" in result  # num strips leading zeros: "0042" → "42"


def test_build_navigation_index_no_adr_section_when_absent(tmp_path):
    """No ADR section when docs/adr/ does not exist."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Architecture Decisions" not in result


def test_build_navigation_index_no_quick_links_when_no_sections(tmp_path):
    """No Quick Links table when no standard subdirs exist."""
    (tmp_path / "docs").mkdir()
    result = build_navigation_index(tmp_path, "my-repo")
    assert "## Quick Links" not in result
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_index_navigation.py -v
```

Expected: `ImportError: cannot import name 'build_navigation_index'`

- [ ] **Step 3: Commit test file**

```bash
git -C C:/dev/h2t-skills add tests/docs/test_index_navigation.py
git -C C:/dev/h2t-skills commit -m "test(docs-index): add failing tests for navigation template"
```

---

### Task 1: Implement `build_navigation_index` in index.py

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-index/scripts/index.py`

Uses the real `_collect_adrs()` schema: `row["num"]` and `row["file"]`.

- [ ] **Step 1: Add `build_navigation_index` function**

Add after `build_index()`, before `_extract_custom_sections()`:

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

    # ADR table — uses _collect_adrs() schema: num, file, title, status, date
    adrs = _collect_adrs(rp)
    if adrs:
        lines += ["## Architecture Decisions", ""]
        lines += ["| # | Title | Status | Date |", "|---|-------|--------|------|"]
        for adr in adrs:
            num = adr["num"]
            link = f"[{adr['title']}](adr/{adr['file']})"
            badge = _status_badge(adr["status"])
            lines.append(f"| {num} | {link} | {badge} | {adr['date']} |")
        lines.append("")

    # Preserve Specs, Plans, Reports tables (keep parity with build_index)
    specs = _collect_dir(rp, "superpowers/specs")
    if specs:
        lines += ["## Specs", ""]
        lines += ["| Title | Status | Date |", "|-------|--------|------|"]
        for r in specs:
            badge = _status_badge(r["status"])
            lines.append(f"| [{r['title']}](superpowers/specs/{r['file']}) | {badge} | {r['date']} |")
        lines.append("")

    plans = _collect_dir(rp, "superpowers/plans")
    if plans:
        lines += ["## Plans", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in plans:
            lines.append(f"| [{r['title']}](superpowers/plans/{r['file']}) | {r['date']} |")
        lines.append("")

    reports = _collect_dir(rp, "reports")
    if reports:
        lines += ["## Reports", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in reports:
            lines.append(f"| [{r['title']}](reports/{r['file']}) | {r['date']} |")
        lines.append("")

    # Preserve custom sections from existing README (## Notes, ## Team, ## Links)
    readme = rp / "docs" / "README.md"
    if readme.exists():
        existing = readme.read_text(encoding="utf-8")
        preserved = _extract_custom_sections(existing)
        if preserved:
            lines += ["", preserved]

    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Wire into `main()` — replace `build_index` call**

In `main()`, replace:

```python
content = build_index(rp, name)
```

with:

```python
content = build_navigation_index(rp, name)
```

- [ ] **Step 3: Run tests — expect PASS**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_index_navigation.py -v
```

Expected: 6 tests PASS

- [ ] **Step 4: Run full docs test suite (non-regression)**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests PASS

- [ ] **Step 4b: Remove dead `build_index()` from index.py**

After wiring `main()` to call `build_navigation_index()`, the old `build_index()` function becomes unreachable dead code. Remove it from `index.py` unless external callers are known.

Check for callers first:
```bash
C:/dev/h2t-skills/.venv/Scripts/python -c "import subprocess; r = subprocess.run(['grep', '-r', 'build_index', 'plugins/', 'tests/'], capture_output=True, text=True); print(r.stdout)"
```

If no external callers: delete `build_index()` and `_extract_custom_sections()` from `index.py` (note: `_extract_custom_sections` is now used by `build_navigation_index`, so keep it).

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-index/scripts/index.py
git -C C:/dev/h2t-skills commit -m "feat(docs-index): add build_navigation_index — Quick Links + ADR/Specs/Plans/Reports; remove dead build_index"
```

---

### Task 2: Extend milestone-closure SKILL.md with docs-cleanup + docs-index steps

**Files:**
- Modify: `plugins/h2t-dev/skills/milestone-closure/SKILL.md`

No scripts needed. Uses real CLI contracts:
- dry-run preview: `cleanup.py <repo>` (no flags)
- apply: `cleanup.py <repo> --apply --milestone <tag>`
- index rebuild: `index.py <repo> --apply`

- [ ] **Step 1: Insert Step 3a (docs-cleanup preview gate) after existing Step 3**

Add after the "Write Phase Report" step:

```markdown
### Step 3a: Archive Stale Plans — docs-cleanup

First run in dry-run mode (default) to preview what will be archived:

```bash
~/.h2t/venv/Scripts/python plugins/h2t-dev/skills/docs-cleanup/scripts/cleanup.py <repo-name>
```

**STOP if unexpected files are listed.** Confirm with user before proceeding.

If the preview is acceptable, run with `--apply` to execute git mv + commit.
Replace `<M>` with the milestone number (e.g. `M6`):

```bash
~/.h2t/venv/Scripts/python plugins/h2t-dev/skills/docs-cleanup/scripts/cleanup.py <repo-name> --apply --milestone <M>
```
```

- [ ] **Step 2: Insert Step 3b (docs-index rebuild) after Step 3a**

```markdown
### Step 3b: Rebuild docs/README.md — docs-index

Regenerate the navigation index after archival:

```bash
~/.h2t/venv/Scripts/python plugins/h2t-dev/skills/docs-index/scripts/index.py <repo-name> --apply
```

Commit the updated `docs/README.md` separately if not already committed by cleanup step.
```

- [ ] **Step 3: Update Checklist Summary**

Add two items after the Phase Report item:

```markdown
- [ ] Stale plans archived (`cleanup.py <repo>` previewed, then `--apply` executed)
- [ ] `docs/README.md` rebuilt via `index.py <repo> --apply`
```

- [ ] **Step 4: Bump patch version**

> **NOTE: Version ordering** — This plan bumps h2t-dev to `1.0.7`. Plan 1 (docs-lint) bumps to `1.0.6`. Apply in order: docs-lint first (→ 1.0.6), then this plan (→ 1.0.7).

```bash
C:/dev/h2t-skills/.venv/Scripts/python scripts/bump_plugin.py h2t-dev 1.0.7
```

- [ ] **Step 5: Final test run**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/milestone-closure/SKILL.md plugins/h2t-dev/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "feat(milestone-closure): add docs-cleanup preview gate + docs-index rebuild steps"
```
