---
title: "docs-lint v2: Misplaced Deliverable Files Detection + git mv Apply"
status: "draft"
date: "2026-06-05"
milestone: ""
---
# docs-lint v2: Misplaced Deliverable Files Detection + git mv Apply

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** docs-lint detects non-markdown deliverable files (html, pdf, pptx) in `docs/**` and automatically moves them via `git mv` to a configurable `deliverables/` directory.

**Architecture:** New `misplaced_files.py` module provides detection + git-tracked check. `config.py` gains a `deliverables_dir` default. `fix_plan.py` gets a `move_file` action type. `lint.py` integrates detection into all commands and adds a direct `_apply_misplaced_moves()` helper that calls `git mv` from `fix-safe`. `plan --save FILE` saves the JSON fix plan to disk.

**Tech Stack:** Python stdlib (`subprocess`, `pathlib`), existing `docs.*` module pattern, `git mv` for tracked moves.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t-dev/lib/docs/misplaced_files.py` | CREATE | `check_misplaced_deliverables()` + `_is_tracked()` |
| `plugins/h2t-dev/lib/docs/config.py` | MODIFY | Add `deliverables_dir: "deliverables"` default |
| `plugins/h2t-dev/lib/docs/fix_plan.py` | MODIFY | Add `move_file` action branch for `misplaced_deliverable` |
| `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | MODIFY | 6 integration points (import, collect, audit, plan, fix-safe, doctor) |
| `tests/docs/test_misplaced_files.py` | CREATE | Unit tests for `misplaced_files.py` |
| `tests/docs/test_lint_checks.py` | MODIFY | Integration tests for plan --save + fix-safe moves |
| `plugins/h2t-dev/.claude-plugin/plugin.json` | MODIFY | Bump version 1.0.15 → 1.0.16 |

---

### Task 1: `misplaced_files.py` — detection module

**Files:**
- Create: `plugins/h2t-dev/lib/docs/misplaced_files.py`
- Create: `tests/docs/test_misplaced_files.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_misplaced_files.py
"""Unit tests for docs.misplaced_files module."""
import sys
from pathlib import Path
from unittest.mock import patch

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.misplaced_files import check_misplaced_deliverables


def test_no_docs_dir_returns_empty(tmp_path):
    result = check_misplaced_deliverables(tmp_path)
    assert result == []


def test_only_md_files_no_findings(tmp_path):
    docs = tmp_path / "docs" / "research"
    docs.mkdir(parents=True)
    (docs / "2026-01-01-analysis.md").write_text("# Analysis")
    result = check_misplaced_deliverables(tmp_path)
    assert result == []


def test_html_in_docs_produces_finding(tmp_path):
    docs = tmp_path / "docs" / "research"
    docs.mkdir(parents=True)
    (docs / "report.html").write_text("<html></html>")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1
    assert result[0]["type"] == "misplaced_deliverable"
    assert result[0]["severity"] == "warn"
    assert "docs/research/report.html" in result[0]["path"]
    assert result[0]["target_path"] == "deliverables/report.html"
    assert result[0]["is_tracked"] is True


def test_pdf_in_docs_produces_finding(tmp_path):
    docs = tmp_path / "docs" / "client"
    docs.mkdir(parents=True)
    (docs / "proposal.pdf").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=False):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1
    assert result[0]["is_tracked"] is False


def test_custom_deliverables_dir_in_target_path(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "deck.pptx").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path, deliverables_dir="outputs")
    assert result[0]["target_path"] == "outputs/deck.pptx"


def test_multiple_deliverable_exts_detected(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("a.html", "b.pdf", "c.pptx", "d.docx"):
        (docs / name).write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 4


def test_htm_extension_detected(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.htm").write_text("")
    with patch("docs.misplaced_files._is_tracked", return_value=True):
        result = check_misplaced_deliverables(tmp_path)
    assert len(result) == 1


def test_readme_md_not_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs")
    result = check_misplaced_deliverables(tmp_path)
    assert result == []
```

- [ ] **Step 2: Run to verify tests fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_misplaced_files.py -v
```
Expected: FAIL with `ImportError: cannot import name 'check_misplaced_deliverables'`

- [ ] **Step 3: Write `misplaced_files.py`**

```python
# plugins/h2t-dev/lib/docs/misplaced_files.py
"""Detect misplaced deliverable files (html/pdf/pptx) inside docs/."""
from __future__ import annotations
import subprocess
from pathlib import Path

_DELIVERABLE_EXTS: frozenset[str] = frozenset({
    ".html", ".htm", ".pdf", ".pptx", ".docx", ".xlsx",
})


def _is_tracked(rp: Path, filepath: Path) -> bool:
    """Return True if filepath is tracked by git (relative to rp)."""
    try:
        rel = str(filepath.relative_to(rp))
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=str(rp),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_misplaced_deliverables(
    rp: Path,
    deliverables_dir: str = "deliverables",
) -> list[dict]:
    """Find non-markdown deliverable files inside docs/ and propose moving them.

    Returns findings with extra fields: target_path, is_tracked.
    """
    from docs.reporter import finding as make_finding

    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []

    findings: list[dict] = []
    for f in sorted(docs_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in _DELIVERABLE_EXTS:
            continue
        rel = str(f.relative_to(rp)).replace("\\", "/")
        target = f"{deliverables_dir}/{f.name}"
        tracked = _is_tracked(rp, f)
        fd = make_finding(
            "misplaced_deliverable", "warn", rel,
            f"deliverable file in docs/: {rel} — move to {target}",
        )
        fd["target_path"] = target
        fd["is_tracked"] = tracked
        findings.append(fd)
    return findings
```

- [ ] **Step 4: Run tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_misplaced_files.py -v
```
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/misplaced_files.py tests/docs/test_misplaced_files.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add misplaced_files check module"
```

---

### Task 2: `config.py` — `deliverables_dir` default

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Modify: `tests/docs/test_config.py`

- [ ] **Step 1: Write the failing test**

Open `tests/docs/test_config.py` and add at the end:

```python
def test_deliverables_dir_default(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["deliverables_dir"] == "deliverables"


def test_deliverables_dir_override_from_yaml(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\ndeliverables_dir: outputs\n"
    )
    cfg = load_config(tmp_path)
    assert cfg["deliverables_dir"] == "outputs"
```

- [ ] **Step 2: Run to verify fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v -k "deliverables"
```
Expected: FAIL with `KeyError: 'deliverables_dir'`

- [ ] **Step 3: Add `deliverables_dir` to `_DEFAULTS`**

In `plugins/h2t-dev/lib/docs/config.py`, in the `_DEFAULTS` dict (after `"project_checks": False`):

```python
    "deliverables_dir": "deliverables",
```

Full `_DEFAULTS` after edit:
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
    "deliverables_dir": "deliverables",
}
```

- [ ] **Step 4: Run tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```
Expected: all PASSED (including 2 new)

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py tests/docs/test_config.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add deliverables_dir config key"
```

---

### Task 3: `fix_plan.py` — `move_file` action type

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/fix_plan.py`
- Modify: `tests/docs/test_fix_plan.py` (create if absent — check first)

The file `tests/docs/test_fix_plan.py` may not exist. If absent, create it; if present, add to it.

- [ ] **Step 1: Write the failing tests**

Check if `tests/docs/test_fix_plan.py` exists. If not, create:

```python
# tests/docs/test_fix_plan.py
"""Unit tests for docs.fix_plan module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.fix_plan import build_fix_plan, _findings_to_actions


def test_misplaced_deliverable_tracked_produces_safe_move_action():
    findings = [{
        "type": "misplaced_deliverable",
        "severity": "warn",
        "path": "docs/research/report.html",
        "message": "deliverable file in docs/: docs/research/report.html — move to deliverables/report.html",
        "target_path": "deliverables/report.html",
        "is_tracked": True,
    }]
    actions = _findings_to_actions(findings)
    assert len(actions) == 1
    a = actions[0]
    assert a["type"] == "move_file"
    assert a["path"] == "docs/research/report.html"
    assert a["target_path"] == "deliverables/report.html"
    assert a["risk"] == "safe"
    assert a["requires_confirmation"] is False


def test_misplaced_deliverable_untracked_produces_review_action():
    findings = [{
        "type": "misplaced_deliverable",
        "severity": "warn",
        "path": "docs/foo.pdf",
        "message": "deliverable file in docs/: docs/foo.pdf — move to deliverables/foo.pdf",
        "target_path": "deliverables/foo.pdf",
        "is_tracked": False,
    }]
    actions = _findings_to_actions(findings)
    assert len(actions) == 1
    a = actions[0]
    assert a["risk"] == "review"
    assert a["requires_confirmation"] is True


def test_build_fix_plan_includes_move_file_action():
    findings = [{
        "type": "misplaced_deliverable",
        "severity": "warn",
        "path": "docs/deck.html",
        "message": "deliverable file in docs/: docs/deck.html — move to deliverables/deck.html",
        "target_path": "deliverables/deck.html",
        "is_tracked": True,
    }]
    plan = build_fix_plan(repo_root="/tmp/myrepo", findings=findings)
    assert plan["schema"] == "h2t_docs_fix_plan/v0.1"
    assert any(a["type"] == "move_file" for a in plan["actions"])
```

If `tests/docs/test_fix_plan.py` already exists, append the following to it (the file exists — add the import line and then the three test functions):

```python
from docs.fix_plan import _findings_to_actions  # extend existing import
```

Then append the three test functions.

- [ ] **Step 2: Run to verify fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_plan.py -v
```
Expected: FAIL (no `misplaced_deliverable` branch in `_findings_to_actions`)

- [ ] **Step 3: Add `move_file` branch to `_findings_to_actions` in `fix_plan.py`**

In `plugins/h2t-dev/lib/docs/fix_plan.py`, add after the `elif t == "frontmatter":` block (before `return actions`):

```python
        elif t == "misplaced_deliverable":
            target = f.get("target_path")
            is_tracked = f.get("is_tracked", False)
            actions.append({
                "action_id": _action_id("move_file", path, target),
                "type": "move_file",
                "status": "proposed",
                "risk": "safe" if is_tracked else "review",
                "path": path,
                "target_path": target,
                "reason": msg,
                "requires_confirmation": not is_tracked,
            })
```

- [ ] **Step 4: Run tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_plan.py -v
```
Expected: all PASSED (including 3 new)

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/fix_plan.py tests/docs/test_fix_plan.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add move_file action for misplaced deliverables"
```

---

### Task 4: `lint.py` — detection integration (import + collect + audit)

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`

This task wires the new check into the import block, `_collect_all_findings`, and `_run_audit`.

- [ ] **Step 1: Write the failing integration test**

Add to `tests/docs/test_lint_checks.py`:

```python
def test_collect_all_findings_detects_html_in_docs(tmp_path, monkeypatch):
    """_collect_all_findings returns misplaced_deliverable finding for HTML in docs/."""
    import lint
    from unittest.mock import patch

    # Minimal repo structure
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    yaml_content = "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(yaml_content)
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "report.html").write_text("<html/>")

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        findings = lint._collect_all_findings(tmp_path, no_pymarkdown=True)

    types = [f["type"] for f in findings]
    assert "misplaced_deliverable" in types
```

- [ ] **Step 2: Run to verify fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py::test_collect_all_findings_detects_html_in_docs -v
```
Expected: FAIL (`misplaced_deliverable` not in types)

- [ ] **Step 3: Edit the import try/except block in `lint.py`**

**IMPORTANT (Codex review issue #7):** Add `misplaced_files` as a SEPARATE try/except block with its own flag, NOT inside the existing project-layer try. This prevents one broken import from disabling all project-layer checks.

Find the existing try/except (lines ~49-60):
```python
try:
    from docs.root_structure import check_root_structure, check_root_readmes
    from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene
    from docs.agent_instructions import check_agent_instructions
    _PROJECT_LAYER_AVAILABLE = True
except ImportError as _e:
    ...
    _PROJECT_LAYER_AVAILABLE = False
```

Add a SECOND try/except block immediately after it:
```python
try:
    from docs.misplaced_files import check_misplaced_deliverables
    _MISPLACED_FILES_AVAILABLE = True
except ImportError:
    _MISPLACED_FILES_AVAILABLE = False
```

Then in `_collect_all_findings`, guard misplaced check with `_MISPLACED_FILES_AVAILABLE`:
```python
    if _MISPLACED_FILES_AVAILABLE and cfg.get("project_checks"):
        deliverables_dir = cfg.get("deliverables_dir", "deliverables")
        all_findings.extend(check_misplaced_deliverables(rp, deliverables_dir))
```

And similarly in `_run_audit` add to project_findings:
```python
        + (check_misplaced_deliverables(rp, _deliverables_dir) if _MISPLACED_FILES_AVAILABLE else [])
```

- [ ] **Step 4: Edit `_collect_all_findings` in `lint.py`**

Find the project_checks block (~lines 524-530):
```python
    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        all_findings.extend(check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs))
        if template:
            all_findings.extend(check_root_readmes(rp, template))
        all_findings.extend(check_gitignore_hygiene(rp))
        all_findings.extend(check_agent_instructions(rp))
```

Add one line at the end of that block:
```python
    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        all_findings.extend(check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs))
        if template:
            all_findings.extend(check_root_readmes(rp, template))
        all_findings.extend(check_gitignore_hygiene(rp))
        all_findings.extend(check_agent_instructions(rp))
        deliverables_dir = cfg.get("deliverables_dir", "deliverables")
        all_findings.extend(check_misplaced_deliverables(rp, deliverables_dir))
```

- [ ] **Step 5: Edit `_run_audit` project_findings block (~line 568-576)**

Find:
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
```

Replace with:
```python
    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        _deliverables_dir = cfg.get("deliverables_dir", "deliverables")
        project_findings = (
            check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs)
            + (check_root_readmes(rp, template) if template else [])
            + check_gitignore_hygiene(rp)
            + check_agent_instructions(rp)
            + check_misplaced_deliverables(rp, _deliverables_dir)
        )
    else:
        project_findings = []
```

- [ ] **Step 6: Run tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v
```
Expected: all PASSED including the new test

- [ ] **Step 7: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): wire misplaced_deliverables into collect + audit"
```

---

### Task 5: `lint.py` — apply integration (`_apply_safe_action` + `_apply_misplaced_moves` + `fix-safe`)

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`

This task adds the actual `git mv` execution path.

- [ ] **Step 1: Write the failing integration test**

Add to `tests/docs/test_lint_checks.py`:

```python
def test_fix_safe_moves_tracked_html(tmp_path, monkeypatch):
    """fix-safe with project_checks=true moves tracked HTML via git mv."""
    import subprocess
    import lint
    from unittest.mock import patch, MagicMock

    # Setup
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    )
    (tmp_path / "docs" / "research").mkdir(parents=True)
    html = tmp_path / "docs" / "research" / "deck.html"
    html.write_text("<html/>")
    (tmp_path / "deliverables").mkdir()
    dst = tmp_path / "deliverables" / "deck.html"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        # Simulate git mv: move the file
        if cmd[0] == "git" and cmd[1] == "mv":
            src = Path(cmd[2])
            dst_p = Path(cmd[3])
            dst_p.write_bytes(src.read_bytes())
            src.unlink()
        m = MagicMock()
        m.returncode = 0
        m.stderr = ""
        return m

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        with patch("subprocess.run", side_effect=fake_run):
            lint._run_fix_safe(tmp_path, only="all")

    assert dst.exists()
    assert not html.exists()
```

- [ ] **Step 2: Run to verify fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py::test_fix_safe_moves_tracked_html -v
```
Expected: FAIL (HTML file still at original location)

- [ ] **Step 3: Fix `_run_fix_safe --plan FILE` hash reporting for move_file (Codex issue #5)**

In `_run_fix_safe` (~line 660), find:
```python
                _apply_safe_action(rp, act)
                ah = file_hash(rp / act.get("path", "")) if act.get("path") else ""
```

Replace with:
```python
                _apply_safe_action(rp, act)
                # move_file: after-hash is at target_path (src is gone after git mv)
                _hash_path = act.get("target_path") if act.get("type") == "move_file" else act.get("path", "")
                ah = file_hash(rp / _hash_path) if _hash_path else ""
```

- [ ] **Step 5: Add `move_file` branch to `_apply_safe_action` in `lint.py`**

Find `_apply_safe_action` (~line 698):
```python
def _apply_safe_action(rp: Path, act: dict) -> None:
    """Apply a single safe action from a fix plan."""
    action_type = act.get("type", "")
    path = act.get("path", "")
    if action_type == "create_dir":
        (rp / path).mkdir(parents=True, exist_ok=True)
    elif action_type == "add_frontmatter":
        target = rp / path
        if target.exists():
            fix_frontmatter_action_single(rp, target)
```

Replace with:
```python
def _apply_safe_action(rp: Path, act: dict) -> None:
    """Apply a single safe action from a fix plan."""
    action_type = act.get("type", "")
    path = act.get("path", "")
    if action_type == "create_dir":
        (rp / path).mkdir(parents=True, exist_ok=True)
    elif action_type == "add_frontmatter":
        target = rp / path
        if target.exists():
            fix_frontmatter_action_single(rp, target)
    elif action_type == "move_file":
        src = rp / path
        dst = rp / (act.get("target_path") or "")
        if src.exists() and dst.parent.exists() and not dst.exists():
            subprocess.run(
                ["git", "mv", str(src), str(dst)],
                cwd=str(rp), check=True, capture_output=True,
            )
```

- [ ] **Step 6: Add `_apply_misplaced_moves()` helper function in `lint.py`**

Add this function immediately before `_run_fix_safe` (~line 647):

```python
def _apply_misplaced_moves(rp: Path, cfg: dict) -> list[str]:
    """Detect misplaced deliverable files and git mv tracked ones.

    Returns list of human-readable fix messages (FIX or SKIP).
    """
    if not _PROJECT_LAYER_AVAILABLE:
        return []
    deliverables_dir = cfg.get("deliverables_dir", "deliverables")
    findings = check_misplaced_deliverables(rp, deliverables_dir)
    fixes: list[str] = []
    for f in findings:
        if not f.get("is_tracked"):
            fixes.append(f"SKIP: {f['path']} is untracked — move manually with: git mv")
            continue
        tgt_path = f.get("target_path", "")
        dst = rp / tgt_path
        if not dst.parent.exists():
            fixes.append(f"SKIP: {f['path']} — target dir missing: {tgt_path.split('/')[0]}/")
            continue
        src = rp / f["path"]
        if dst.exists():
            fixes.append(f"SKIP: {f['path']} — destination already exists: {tgt_path}")
            continue
        result = subprocess.run(
            ["git", "mv", str(src), str(dst)],
            cwd=str(rp), capture_output=True, text=True,
        )
        if result.returncode == 0:
            fixes.append(f"git mv {f['path']} → {tgt_path}")
        else:
            fixes.append(f"FAILED: git mv {f['path']}: {result.stderr.strip()[:80]}")
    return fixes
```

- [ ] **Step 7: Wire `_apply_misplaced_moves` into `_run_fix_safe`**

In `_run_fix_safe` (~line 689-695), find:
```python
    if _PROJECT_LAYER_AVAILABLE:
        _cfg = load_config(rp)
        if _cfg.get("project_checks") and only in ("all",):
            gi_fixes = fix_gitignore_hygiene(rp)
            for fx in gi_fixes:
                print(f"  FIX: {fx}")
    print("  Done. Renames/moves require 'docs-lint plan' review and manual action.")
```

Replace with:
```python
    if _PROJECT_LAYER_AVAILABLE:
        _cfg = load_config(rp)
        if _cfg.get("project_checks") and only in ("all", "moves"):
            gi_fixes = fix_gitignore_hygiene(rp)
            for fx in gi_fixes:
                print(f"  FIX: {fx}")
            move_fixes = _apply_misplaced_moves(rp, _cfg)
            for fx in move_fixes:
                print(f"  FIX: {fx}")
    print("  Done.")
```

- [ ] **Step 8: Run tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v
```
Expected: all PASSED including the new test

- [ ] **Step 9: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add git mv apply path for misplaced deliverables"
```

---

### Task 6: `lint.py` — `plan --save`, `_run_plan` misplaced section, `_run_doctor` update

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/docs/test_lint_checks.py`:

```python
def test_plan_save_writes_json_file(tmp_path):
    """plan --save writes fix plan JSON to disk."""
    import lint
    from unittest.mock import patch

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    )
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "deck.html").write_text("<html/>")

    plan_file = tmp_path / "plan.json"

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        lint._run_plan(tmp_path, save_file=str(plan_file))

    assert plan_file.exists()
    import json
    plan = json.loads(plan_file.read_text())
    assert plan["schema"] == "h2t_docs_fix_plan/v0.1"
    assert any(a["type"] == "move_file" for a in plan["actions"])


def test_run_plan_human_readable_shows_misplaced(tmp_path, capsys):
    """_run_plan human output shows Misplaced Deliverable Files section."""
    import lint
    from unittest.mock import patch

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    )
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "report.html").write_text("<html/>")

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        lint._run_plan(tmp_path)

    captured = capsys.readouterr()
    assert "Misplaced" in captured.out
    assert "report.html" in captured.out


def test_doctor_counts_misplaced_deliverable(tmp_path, capsys):
    """doctor JSON output counts misplaced_deliverable in project issues."""
    import lint
    import json
    from unittest.mock import patch

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    )
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "report.html").write_text("<html/>")

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        lint._run_doctor(tmp_path, json_output=True, no_pymarkdown=True)

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    project_findings = [
        f for f in report["findings"]
        if f["type"] == "misplaced_deliverable"
    ]
    assert len(project_findings) == 1
    assert "1 project issue" in report["summary"]
```

- [ ] **Step 2: Run to verify fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -v -k "save or misplaced or doctor_counts"
```
Expected: 3 FAIL (functions don't accept `save_file` yet, plan section missing, doctor not counting)

- [ ] **Step 3: Update `_run_plan` signature + human-readable section + save_file**

Find `_run_plan` (~line 599):
```python
def _run_plan(rp: Path, json_output: bool = False) -> None:
    all_findings = _collect_all_findings(rp, no_pymarkdown=True)

    if json_output:
        from docs.fix_plan import build_fix_plan
        plan = build_fix_plan(repo_root=str(rp), findings=all_findings)
        print(json.dumps(plan, indent=2))
        return
```

Replace entire `_run_plan` function with:

```python
def _run_plan(
    rp: Path,
    json_output: bool = False,
    save_file: str | None = None,
) -> None:
    all_findings = _collect_all_findings(rp, no_pymarkdown=True)

    if json_output or save_file:
        from docs.fix_plan import build_fix_plan
        plan = build_fix_plan(repo_root=str(rp), findings=all_findings)
        output = json.dumps(plan, indent=2)
        if save_file:
            Path(save_file).write_text(output, encoding="utf-8")
            print(f"Plan saved: {save_file}")
            return
        print(output)
        return

    print_header(f"docs-lint plan: {rp}")
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    misplaced = [f for f in all_findings if f["type"] == "misplaced_deliverable"]
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]

    if orphans:
        print("\n## Orphan Files (not linked from any README/index)\n")
        for f in orphans:
            print(f"  - {f['path']}")
        print("\n  Action: link from a relevant README, move to archive/, or delete after review.")

    if naming:
        print("\n## Naming Convention Fixes\n")
        for f in naming:
            fix = f.get("safe_fix", "")
            print(f"  - {f['path']}: {f['message']}")
            if fix:
                print(f"    → {fix}")

    if structure:
        print("\n## Structure Issues\n")
        for f in structure:
            print(f"  - {f['message']}")

    if misplaced:
        print("\n## Misplaced Deliverable Files\n")
        for f in misplaced:
            tracked_note = "" if f.get("is_tracked") else " (untracked — move manually)"
            print(f"  - {f['path']} → {f['target_path']}{tracked_note}")
        print("\n  Action: run 'docs-lint fix-safe' to git mv tracked files.")

    if project:
        print("\n## Project Layer\n")
        for f in project:
            print(f"  - [{f['type']}] {f['path']}: {f['message']}")

    if not orphans and not naming and not structure and not misplaced and not project:
        print("\n  No cleanup needed.")
    else:
        print(f"\n  Run 'docs-lint fix-safe' for auto-fixable items.")
        print(f"  Run 'docs-lint fix-index' for README/index rebuild.")
```

- [ ] **Step 4: Update `_run_doctor` project filter to include `misplaced_deliverable`**

Find in `_run_doctor` (~line 819):
```python
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
```

Replace with:
```python
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions",
        "misplaced_deliverable",
    }]
```

- [ ] **Step 5: Add `--save` flag to the `plan` command in `main()`**

Find in `main()` the subcommand parser block (~line 973):
```python
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="all", choices=["all", "frontmatter", "dirs"])
        parser.add_argument("--json", dest="json_output", action="store_true")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--plan", default=None, metavar="FILE")
```

Add one line after `--json`:
```python
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="all", choices=["all", "frontmatter", "dirs", "moves"])
        parser.add_argument("--json", dest="json_output", action="store_true")
        parser.add_argument("--save", default=None, metavar="FILE",
                            help="Save fix plan JSON to FILE (plan command only)")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--plan", default=None, metavar="FILE")
```

Note: also extended `--only` choices to include `"moves"` so `fix-safe --only=moves` works.

- [ ] **Step 6: Wire `--save` into plan dispatch in `main()`**

Find (~line 989):
```python
        elif cmd == "plan":
            _run_plan(rp, json_output=args.json_output)
```

Replace with:
```python
        elif cmd == "plan":
            _run_plan(rp, json_output=args.json_output, save_file=args.save)
```

- [ ] **Step 7: Run all tests — verify pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```
Expected: all PASSED

- [ ] **Step 8: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): plan --save, misplaced section in plan output, doctor counts"
```

---

### Task 7: version bump + dogfood on rejuve

**Files:**
- Modify: `plugins/h2t-dev/.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version to 1.0.16**

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev 1.0.16
```

- [ ] **Step 2: Run full test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/ -v
```
Expected: all PASSED (187+ tests)

- [ ] **Step 3: Verify audit finds HTML in rejuve**

```
~/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py audit --root C:/work/rejuve --no-pymarkdown
```
Expected: output includes `misplaced_deliverable` warnings for `docs/research/2026-05-23-european-reference-deck.html` and `docs/research/2026-05-25-research-hub.html`

- [ ] **Step 4: Verify plan shows proposed moves**

```
~/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py plan --root C:/work/rejuve
```
Expected: output includes `## Misplaced Deliverable Files` section with both HTML files → `deliverables/`

- [ ] **Step 5: Apply the moves on rejuve**

```
~/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py fix-safe --root C:/work/rejuve
```
Expected: output includes `FIX: git mv docs/research/2026-05-23-european-reference-deck.html → deliverables/2026-05-23-european-reference-deck.html` (and the same for the second file)

- [ ] **Step 6: Verify rejuve has 0 findings**

```
~/.h2t/venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py audit --root C:/work/rejuve --no-pymarkdown
```
Expected: `RESULT: all checks passed`

- [ ] **Step 7: Commit rejuve changes**

```
git -C C:/work/rejuve add deliverables/ docs/research/
git -C C:/work/rejuve commit -m "chore: move HTML deliverables from docs/research to deliverables (docs-lint fix-safe)"
```

- [ ] **Step 8: Commit h2t-skills version bump**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/.claude-plugin/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "chore: bump h2t-dev to 1.0.16 — misplaced deliverables detection + git mv apply"
```
