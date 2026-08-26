# docs-lint v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade docs-lint from a minimal mechanical checker to a full multi-angle audit pipeline with stable finding IDs, severity normalization, exception config, vendor filtering, and a rewritten SKILL.md.

**Architecture:** Extend `reporter.py` (finding IDs) → `config.py` (.h2t/docs-lint.yaml + exceptions) → `lint.py` (severity norm, vendor filter, cap, exception filter, _run_audit refactor) → rewrite `SKILL.md`.

**Tech Stack:** Python 3.11, PyYAML, jq (external CLI), gh CLI

---

## File Map

| File | Change |
|---|---|
| `plugins/h2t-dev/lib/docs/reporter.py` | Add `id` field to `finding()` |
| `plugins/h2t-dev/lib/docs/config.py` | `.h2t/docs-lint.yaml` primary path, `project_type` alias, exception schema, stale/orphan warnings |
| `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | Backward-compat exceptions, severity norm, vendor filter, cap, exception filter, `_run_audit` refactor |
| `plugins/h2t-dev/skills/docs-lint/SKILL.md` | Full rewrite |
| `plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md` | New |
| `tests/docs/test_reporter.py` | Extend — finding ID |
| `tests/docs/test_config.py` | Extend — .h2t/docs-lint.yaml, project_type, exceptions |
| `tests/docs/test_lint_v2.py` | New — all lint.py extensions |
| `plugins/h2t-dev/plugin.json` | Version bump to 1.0.17 |
| `plugins/h2t-dev/CHANGELOG.md` | Entry |

---

## Task 1: Add stable `id` field to `finding()`

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/reporter.py`
- Test: `tests/docs/test_reporter.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/docs/test_reporter.py`:

```python
def test_finding_has_id_with_path():
    f = finding("orphan", "warn", "docs/plans/foo.md", "orphan file")
    assert f["id"] == "orphan:docs/plans/foo.md"

def test_finding_has_id_without_path():
    f = finding("structure", "warn", "", "missing dir: docs/adr/")
    assert f["id"] == "structure"

def test_finding_id_stable_across_calls():
    f1 = finding("naming", "warn", "docs/adr/_foo.md", "underscore")
    f2 = finding("naming", "warn", "docs/adr/_foo.md", "underscore")
    assert f1["id"] == f2["id"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -k "test_finding_has_id" -v
```

Expected: FAIL — `KeyError: 'id'`

- [ ] **Step 3: Add `id` to `finding()` in `reporter.py`**

```python
def finding(
    type_: str,
    severity: str,
    path: str,
    message: str,
    safe_fix: str | None = None,
) -> dict:
    """Build a single finding dict. safe_fix omitted when None."""
    result: dict = {
        "type": type_,
        "severity": severity,
        "path": path,
        "message": message,
        "id": f"{type_}:{path}" if path else type_,
    }
    if safe_fix is not None:
        result["safe_fix"] = safe_fix
    return result
```

- [ ] **Step 4: Run all reporter tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/reporter.py tests/docs/test_reporter.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add stable id field to finding() — {type}:{path}"
```

---

## Task 2: Extend `config.py` — `.h2t/docs-lint.yaml`, `project_type`, exception schema

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Test: `tests/docs/test_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/docs/test_config.py`:

```python
import datetime
from pathlib import Path


def test_h2t_config_takes_priority_over_claude_rules(tmp_path):
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("project_type: td-tool\n")
    claude_cfg = tmp_path / ".claude" / "rules" / "docs-lint.yaml"
    claude_cfg.parent.mkdir(parents=True)
    claude_cfg.write_text("template: plugin-pack\n")
    from docs.config import load_config
    cfg = load_config(tmp_path)
    assert cfg["template"] == "td-tool"
    assert cfg["_config_source"] == ".h2t/docs-lint.yaml"


def test_project_type_normalizes_to_template(tmp_path):
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("project_type: standalone-tool\n")
    from docs.config import load_config
    cfg = load_config(tmp_path)
    assert cfg["template"] == "standalone-tool"


def test_exception_stale_flag(tmp_path):
    old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(
        f"exceptions:\n  - path: old_dir/\n    reason: test\n    type: archive\n    reviewed: {old_date}\n"
    )
    (tmp_path / "old_dir").mkdir()
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("stale" in w["message"] for w in warnings)


def test_exception_orphan_flag(tmp_path):
    today = datetime.date.today().isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(
        f"exceptions:\n  - path: nonexistent_dir/\n    reason: test\n    type: archive\n    reviewed: {today}\n"
    )
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("orphan exception" in w["message"] for w in warnings)


def test_exception_string_format_no_crash(tmp_path):
    """Legacy string exceptions (e.g. 'eval') must not crash get_exception_warnings."""
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("exceptions:\n  - eval\n  - ops\n")
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert isinstance(warnings, list)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -k "test_h2t_config or test_project_type or test_exception" -v
```

Expected: FAIL

- [ ] **Step 3: Rewrite `config.py`**

Replace `plugins/h2t-dev/lib/docs/config.py` entirely:

```python
"""Per-repo docs-lint configuration discovery.

Search order:
  1. .h2t/docs-lint.yaml   — project-level (new)
  2. .claude/rules/docs-lint.yaml  — legacy location
"""
from __future__ import annotations
import datetime
from pathlib import Path
from typing import Any

CONFIG_PATHS = [".h2t/docs-lint.yaml", ".claude/rules/docs-lint.yaml"]
_STALE_DAYS = 90

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
    "template": None,       # internal key; set from 'project_type' or 'template'
    "custom_root_dirs": [],
    "project_checks": False,
    "deliverables_dir": "deliverables",
    "_config_source": None,
}


def load_config(repo_root: Path) -> dict[str, Any]:
    """Load config from first found path; fall back to defaults."""
    for config_path in CONFIG_PATHS:
        cfg_path = repo_root / config_path
        if not cfg_path.exists():
            continue
        text = cfg_path.read_text(encoding="utf-8", errors="replace")
        try:
            import yaml
            data = yaml.safe_load(text) or {}
        except ImportError:
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        for k, v in data.items():
            if v is not None:
                merged[k] = v
        # Normalize: 'project_type' (new) takes precedence over 'template' (legacy)
        if data.get("project_type"):
            merged["template"] = data["project_type"]
        elif data.get("template"):
            merged["template"] = data["template"]
        merged["_config_source"] = config_path
        return merged
    return dict(_DEFAULTS)


def get_exception_warnings(exceptions: list, repo_root: Path) -> list[dict]:
    """Return warning findings for stale or orphan dict-exceptions.

    String exceptions (legacy format like 'eval') are silently skipped.
    """
    from docs.reporter import finding
    warnings = []
    today = datetime.date.today()
    for exc in exceptions:
        if not isinstance(exc, dict):
            continue  # legacy string format — no warnings
        path = exc.get("path", "")
        reviewed_str = exc.get("reviewed")
        full_path = repo_root / path.rstrip("/")
        if not full_path.exists():
            warnings.append(finding(
                "structure", "important", path,
                f"orphan exception in docs-lint config: '{path}' no longer exists — remove from config",
            ))
            continue
        if reviewed_str:
            try:
                reviewed = datetime.date.fromisoformat(str(reviewed_str))
                age = (today - reviewed).days
                if age > _STALE_DAYS:
                    warnings.append(finding(
                        "structure", "low", path,
                        f"stale exception: '{path}' last reviewed {age}d ago (>{_STALE_DAYS}d) — re-confirm or remove",
                    ))
            except (ValueError, TypeError):
                pass
    return warnings
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py tests/docs/test_config.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): .h2t/docs-lint.yaml + project_type alias + exception warnings"
```

---

## Task 3: Extend `lint.py` — severity norm, vendor filter, cap, exception filter

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_v2.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/docs/test_lint_v2.py`:

```python
"""Tests for docs-lint v2 extensions: severity, vendor filter, cap, exceptions."""
from pathlib import Path
import datetime
import pytest


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "documentation.md").write_text("# rules\n")
    return tmp_path


def test_all_findings_have_id_field(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    for f in _collect_all_findings(repo):
        assert "id" in f and f["id"], f"missing id: {f}"


def test_all_findings_have_normalized_severity(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    valid = {"critical", "important", "low"}
    for f in _collect_all_findings(repo):
        assert f["severity"] in valid, f"bad severity '{f['severity']}': {f}"


def test_vendor_paths_excluded(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "README.md").write_text("vendor\n")
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "README.md").write_text("vendor\n")
    paths = [f["path"] for f in _collect_all_findings(repo)]
    assert not any(".venv" in p for p in paths)
    assert not any("node_modules" in p for p in paths)


def test_per_dimension_cap(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings, _DIM_LIMIT
    from collections import Counter
    repo = _make_repo(tmp_path)
    # Create 60 files without date prefix to trigger naming findings
    for i in range(60):
        (repo / "docs" / "superpowers" / "plans" / f"plan-no-date-{i}.md").write_text("---\ntitle: x\n---\n")
    counts = Counter(f["type"] for f in _collect_all_findings(repo))
    for t, n in counts.items():
        assert n <= _DIM_LIMIT, f"dimension '{t}' has {n} > {_DIM_LIMIT}"


def test_exception_dict_paths_filtered(tmp_path):
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    (repo / "benchmark_results").mkdir()
    (repo / "benchmark_results" / "run.json").write_text("{}")
    today = datetime.date.today().isoformat()
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    (h2t / "docs-lint.yaml").write_text(
        f"exceptions:\n  - path: benchmark_results/\n    reason: live\n    type: operational_data\n    reviewed: {today}\n"
    )
    paths = [f["path"] for f in _collect_all_findings(repo)]
    assert not any("benchmark_results" in p for p in paths)


def test_exception_string_format_no_crash(tmp_path):
    """Legacy string exceptions must not crash _collect_all_findings."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    (h2t / "docs-lint.yaml").write_text("exceptions:\n  - eval\n  - ops\n")
    findings = _collect_all_findings(repo)
    assert isinstance(findings, list)


def test_exception_warnings_not_capped(tmp_path):
    """Stale exception warnings must survive the dimension cap."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _collect_all_findings
    repo = _make_repo(tmp_path)
    old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    h2t = repo / ".h2t"
    h2t.mkdir(exist_ok=True)
    existing = repo / "stale_dir"
    existing.mkdir()
    (h2t / "docs-lint.yaml").write_text(
        f"exceptions:\n  - path: stale_dir/\n    reason: old\n    type: archive\n    reviewed: {old_date}\n"
    )
    msgs = [f["message"] for f in _collect_all_findings(repo)]
    assert any("stale" in m for m in msgs), "stale exception warning was capped away"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py -v
```

Expected: FAIL

- [ ] **Step 3: Add constants and helpers to `lint.py`**

Add after the import block, before `_SUBCOMMANDS` (after line ~68):

```python
_VENDOR_EXCLUDE = {
    ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_DIM_LIMIT = 50

_SEVERITY_MAP = {
    "error": "critical",
    "warn": "important",
    "info": "low",
    "critical": "critical",
    "important": "important",
    "low": "low",
}


def _is_vendor_path(path: str) -> bool:
    if not path:
        return False
    return any(part in _VENDOR_EXCLUDE for part in Path(path).parts)


def _is_vendor_message(message: str) -> bool:
    """Catch vendor paths embedded in message when path field is empty."""
    return any(f"/{v}/" in message or message.startswith(v + "/")
               for v in _VENDOR_EXCLUDE)


def _apply_exceptions(findings: list[dict], exceptions: list) -> list[dict]:
    """Remove findings whose path matches a documented exception.

    Handles both dict exceptions (new) and string exceptions (legacy).
    """
    exception_paths: set[str] = set()
    for exc in exceptions:
        if isinstance(exc, str):
            exception_paths.add(exc.rstrip("/"))
        elif isinstance(exc, dict):
            p = exc.get("path", "").rstrip("/")
            if p:
                exception_paths.add(p)
    if not exception_paths:
        return findings
    result = []
    for f in findings:
        fp = f.get("path", "").rstrip("/")
        covered = any(
            fp == ep or fp.startswith(ep + "/") or fp.startswith(ep)
            for ep in exception_paths if ep
        )
        if not covered:
            result.append(f)
    return result


def _cap_by_dimension(findings: list[dict], limit: int = _DIM_LIMIT) -> list[dict]:
    """Keep at most `limit` findings per type, preserving order."""
    counts: dict[str, int] = {}
    result = []
    for f in findings:
        t = f["type"]
        if counts.get(t, 0) < limit:
            result.append(f)
            counts[t] = counts.get(t, 0) + 1
    return result


def _normalize_severities(findings: list[dict]) -> list[dict]:
    """Map legacy severity values (warn/info/error) to spec values (critical/important/low)."""
    for f in findings:
        f["severity"] = _SEVERITY_MAP.get(f.get("severity", "info"), "low")
    return findings
```

- [ ] **Step 4: Update `_collect_all_findings` post-processing**

Find the end of `_collect_all_findings` (around line 540 — just before `return all_findings`).
Replace the final `return all_findings` with:

```python
    # Post-processing pipeline
    # 1. Severity normalization (warn/info → important/low)
    _normalize_severities(all_findings)
    # 2. Vendor path filter — by path field AND by message content
    all_findings = [
        f for f in all_findings
        if not _is_vendor_path(f.get("path", ""))
        and not (not f.get("path") and _is_vendor_message(f.get("message", "")))
    ]
    # 3. Exception filter (dict and string exceptions)
    cfg_exceptions = cfg.get("exceptions") or []
    all_findings = _apply_exceptions(all_findings, cfg_exceptions)
    # 4. Dimension cap (exception warnings appended after cap so they survive)
    all_findings = _cap_by_dimension(all_findings)
    # 5. Exception warnings — appended AFTER cap so they are never dropped
    from docs.config import get_exception_warnings
    all_findings.extend(get_exception_warnings(cfg_exceptions, rp))
    return all_findings
```

- [ ] **Step 5: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py -v
```

Expected: all PASS

- [ ] **Step 6: Run full test suite — no regressions**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ --ignore=tests/docs/test_execution_tracking.py -q
```

Expected: same pass count as before Task 3

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_v2.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): severity norm, vendor filter, dim cap, exception filter"
```

---

## Task 4: Refactor `_run_audit()` to use `_collect_all_findings()`

Without this, maintenance mode (`lint.py audit`) bypasses all Task 3 extensions.

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_v2.py`

- [ ] **Step 1: Write failing test**

Add to `tests/docs/test_lint_v2.py`:

```python
def test_audit_applies_vendor_filter(tmp_path, capsys):
    """_run_audit must not output vendor paths."""
    import sys
    sys.path.insert(0, str(Path("plugins/h2t-dev/skills/docs-lint/scripts")))
    from lint import _run_audit
    repo = _make_repo(tmp_path)
    (repo / ".venv" / "lib").mkdir(parents=True)
    (repo / ".venv" / "lib" / "README.md").write_text("vendor\n")
    try:
        _run_audit(repo)
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert ".venv" not in captured.out, ".venv path leaked into audit output"
```

- [ ] **Step 2: Run test to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py::test_audit_applies_vendor_filter -v
```

Expected: FAIL — `.venv` appears in output

- [ ] **Step 3: Refactor `_run_audit()` to use `_collect_all_findings()`**

Find `_run_audit` in `lint.py` (around line 545). Replace its body with:

```python
def _run_audit(rp: Path, no_pymarkdown: bool = False) -> None:
    print_header(f"docs-lint audit: {rp}")
    all_findings = _collect_all_findings(rp, no_pymarkdown=no_pymarkdown)

    orphans   = [f for f in all_findings if f["type"] == "orphan"]
    naming    = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    frontmatter = [f for f in all_findings if f["type"] == "frontmatter"]
    project   = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene",
        "agent_instructions", "misplaced_deliverable",
    }]

    def _fmt(f: dict) -> str:
        sev = f.get("severity", "low").upper()[:4]
        path = f.get("path", "")
        msg = f.get("message", "")
        return f"  [{sev}] {path}: {msg}" if path else f"  [{sev}] {msg}"

    sections = [
        ("Navigation / Orphans", orphans),
        ("Naming", naming),
        ("Structure", structure),
        ("Metadata / Frontmatter", frontmatter),
        ("Project Layer", project),
    ]
    total = 0
    for title, items in sections:
        if items:
            print(f"\n--- {title} ({len(items)}) ---")
            for item in items:
                print(_fmt(item))
            total += len(items)

    print(f"\n{'=' * 60}")
    if total:
        print(f"  RESULT: {total} finding(s) — run 'docs-lint plan' for cleanup steps")
        sys.exit(1)
    else:
        print("  RESULT: all checks passed")
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ --ignore=tests/docs/test_execution_tracking.py -q
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_v2.py
git -C C:/dev/h2t-skills commit -m "refactor(docs-lint): _run_audit uses _collect_all_findings — extensions apply everywhere"
```

---

## Task 5: Write `references/non-standard-resolution.md`

**Files:**
- Create: `plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md`

- [ ] **Step 1: Create the file**

```markdown
# Non-Standard Path Resolution Reference

Use when evaluating dirs/files not in the standard project template (Dimension 8).

---

## Decision Tree

```
Found non-standard path
        │
        ▼
   Needed? (git activity last 30d + content size)
   git log --oneline --since="30 days ago" -- <path>
       / \
     Yes   No → DELETE (confirm; skip for archived stage)
     │
     ▼
  Covered by standard template for detected project_type?
      / \
    Yes   No
    │          │
    ▼          ▼
 Misplaced   Project-specific?
 → MOVE          / \
   (pre-checks) Yes   No → ADD PROJECT TYPE (PR proposal)
                │
                ▼
           EXCEPTION → .h2t/docs-lint.yaml
```

---

## MOVE pre-checks

Before confirming any `git mv`:

```bash
# 1. Reference search
grep -r "<path>" . --include="*.py" --include="*.md" -l 2>/dev/null | head -20

# 2. Generated file check
git check-ignore -v "<path>" 2>/dev/null

# 3. Symlink check
test -L "<path>" && echo "SYMLINK — do not git mv"

# 4. Submodule check
git submodule status 2>/dev/null | grep "<path>"
```

Only proceed after user confirms and all checks pass.

---

## EXCEPTION format

Write to `.h2t/docs-lint.yaml`:

```yaml
exceptions:
  - path: benchmark_results/
    reason: "TD perf data, updated live"
    type: operational_data   # operational_data|archive|generated|tool_output|external
    reviewed: 2026-06-06     # today's date — re-confirm every 90 days
```

---

## ADD PROJECT TYPE

1. Document the pattern in the conversation
2. Propose extension to `plugins/h2t-dev/lib/docs/project_types.py`
3. Open GitHub issue: `skills: add project type <name>` with label `type:feature`
4. Do NOT edit `project_types.py` directly — requires PR + review

---

## Project type autodetect precedence

1. `.h2t/docs-lint.yaml` `project_type` field
2. `CLAUDE.md` first 50 lines — keyword scan
3. `pyproject.toml` + `plugins/` dir → `plugin-pack`
4. `pyproject.toml` without `plugins/` → `standalone-tool`
5. `package.json` → `frontend-tool`
6. Default → `unknown`
```

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/h2t-skills add "plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md"
git -C C:/dev/h2t-skills commit -m "docs(docs-lint): add non-standard path resolution reference"
```

---

## Task 6: Rewrite `SKILL.md`

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/SKILL.md`

- [ ] **Step 1: Write the new SKILL.md**

Replace `plugins/h2t-dev/skills/docs-lint/SKILL.md` entirely:

````markdown
---
name: h2t-dev:docs-lint
description: >-
  Audit and maintain documentation/structure health in h2t-stack repos.
  Full pipeline: sniff → gate → analyze → plan → issues → fixes → validate.
  Scoped to repos using Claude Code + h2t standards.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# docs-lint v2

Scope: h2t-stack repos (Claude Code, `.claude/rules/`, `docs/superpowers/`, h2t standards).

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
ROOT="${1:-.}"
DRY_RUN="${2:-}"   # pass "--dry-run" to skip issue creation and commits
```

## Phase 1: Sniff (automatic)

Run in parallel:

```bash
git -C "$ROOT" ls-files --cached --others --exclude-standard 2>/dev/null | head -500
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" 2>/dev/null
cat "$ROOT/CLAUDE.md" 2>/dev/null | head -80
cat "$ROOT/.h2t/docs-lint.yaml" 2>/dev/null
ls "$ROOT/.claude/rules/" 2>/dev/null
```

Also read first 30 lines of `pyproject.toml` or `package.json` if present.

If a reference is missing from `references/`, skip that dimension and log:
`[dim-N] reference missing — skipped`.

**Autodetect project_type** (first match):
1. `.h2t/docs-lint.yaml` → `project_type`
2. `CLAUDE.md` first 50 lines — keyword scan
3. `pyproject.toml` + `plugins/` → `plugin-pack`
4. `pyproject.toml` only → `standalone-tool`
5. `package.json` → `frontend-tool`
6. Default → `unknown`

Output exactly 3 lines:
```
Тип: <project_type>, <organic-grow|structured|greenfield>
Состояние: <1-line summary>
Сигнал: <порядок|хаос|зрелый> → рекомендую (<stage>)
```

## Phase 2: Gate — ONE question

```
Стадия проекта:
(1) cleanup   — organic-grow, нужен полный аудит
(2) mature    — стабильная структура, maintenance lint
(3) greenfield — новый репо, setup-ориентированный аудит
(4) archived  — read-only, только анализ
```

---

## Branch: Maintenance (stage 2)

```bash
# Read last valid state (schema=1, handle corrupt lines)
LAST_STATE=$("$H2T_PYTHON" - <<'PYEOF'
import sys, json
from pathlib import Path
state_file = Path("$ROOT/.h2t/lint-state.jsonl")
if not state_file.exists():
    sys.exit(0)
for line in reversed(state_file.read_text().splitlines()):
    try:
        obj = json.loads(line)
        if obj.get("schema") == 1:
            print(json.dumps(obj))
            sys.exit(0)
    except Exception:
        pass
PYEOF
)

# If no valid state → fall back to full audit
if [ -z "$LAST_STATE" ]; then
  echo "No previous state — running full audit instead."
  # → continue as stage (1) cleanup
fi

# Capture current finding IDs via doctor --json
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > /tmp/lint-current.json 2>/dev/null
CURRENT_IDS=$(jq '[.findings[].id]' /tmp/lint-current.json 2>/dev/null || echo "[]")
LAST_IDS=$(echo "$LAST_STATE" | jq '.finding_ids // []' 2>/dev/null || echo "[]")

# Delta = IDs in current but not in last
NEW_IDS=$(jq -n --argjson cur "$CURRENT_IDS" --argjson last "$LAST_IDS" '$cur - $last')

# Apply safe fixes automatically
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"

# Show only delta
jq -r '.[]' <<< "$NEW_IDS" | while read id; do echo "  [NEW] $id"; done
```

Append state:
```bash
mkdir -p "$ROOT/.h2t"
AFTER_IDS=$(jq '[.findings[].id]' /tmp/lint-current.json 2>/dev/null || echo "[]")
AFTER_COUNT=$(jq '.findings | length' /tmp/lint-current.json 2>/dev/null || echo 0)
jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson after_count "$AFTER_COUNT" \
  --argjson new_ids "$NEW_IDS" \
  --argjson after_ids "$AFTER_IDS" \
  '{schema:1,ts:$ts,mode:"maintenance",findings_after:$after_count,new:$new_ids,finding_ids:$after_ids}' \
  >> "$ROOT/.h2t/lint-state.jsonl"
rm -f /tmp/lint-current.json
```

---

## Branch: Full Audit (stages 1, 3, 4)

### Step A: Pre-flight

```bash
# Dirty worktree — warn on ANY uncommitted changes
DIRTY=$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -v '^??' | head -1)
if [ -n "$DIRTY" ]; then
  BRANCH=$(git -C "$ROOT" branch --show-current 2>/dev/null)
  echo "WARNING: uncommitted changes on branch '$BRANCH'. Continue? (y/n)"
  # Wait for user input — do not proceed if 'n'
fi

# gh auth (skip issue creation if fails)
GH_AUTH_OK=0
gh auth status 2>/dev/null && GH_AUTH_OK=1 || echo "gh auth failed — issues will be skipped"

# Duplicate issue check
[ "$GH_AUTH_OK" = "1" ] && \
  gh issue list --label "type:docs-lint" --json number,title --limit 20 2>/dev/null || true
```

Dry-run mode (`$DRY_RUN` = `--dry-run`): skip commits and issue creation throughout.

### Step B: Capture before-state

```bash
mkdir -p "$ROOT/.h2t"
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-before.json" 2>/dev/null
BEFORE_COUNT=$(jq '.findings | length' "$ROOT/.h2t/lint-before.json" 2>/dev/null || echo 0)
```

### Step C: Multi-angle analysis

Load references on demand (skip with log if missing):
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md` — dims 1,2,6
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md` — dims 3,4
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md` — dim 8

| # | Dimension | Source |
|---|---|---|
| 1 | Docs structure | doctor --json type=orphan,structure + documentation-structure.md |
| 2 | Naming | type=naming + naming-conventions.md |
| 3 | Code organization | git ls-files + code-organization.md |
| 4 | Data storage | git ls-files root dirs |
| 5 | Agent accessibility | CLAUDE.md + .claude/rules/ |
| 6 | Frontmatter | type=frontmatter |
| 7 | Root hygiene | type=structure (root count) |
| 8 | Non-standard dirs | git ls-files vs template + non-standard-resolution.md |

Stage 4 (archived): collect findings, mark all destructive suggestions `[ANALYSIS ONLY]`.

### Step D: Report

```
## docs-lint audit — {project} — {date}

### Critical
- [dim-N] <path>: <message>

### Important
- [dim-N] <path>: <message>

### Low
- [dim-N] <path>: <message>

### Config warnings
- [stale-exception] ...
- [orphan-exception] ...
```

### Step E: Write plan file + commit

```bash
PLAN_FILE="$ROOT/docs/superpowers/plans/$(date +%Y-%m-%d)-docs-audit.md"
# Write findings to $PLAN_FILE

if [ "$DRY_RUN" != "--dry-run" ]; then
  git -C "$ROOT" add "$PLAN_FILE"
  git -C "$ROOT" commit -m "docs: docs-lint audit $(date +%Y-%m-%d)"
fi
```

### Step F: Create GitHub issues

Only if GH_AUTH_OK=1 AND stage ≠ 4 AND DRY_RUN is empty.

```bash
# Check for existing issue first
EXISTING=$(gh issue list --label "type:docs-lint" \
  --search "$ISSUE_TITLE" --json number,title 2>/dev/null | jq '.[0].number // empty')

if [ -n "$EXISTING" ]; then
  echo "Existing issue #$EXISTING. Update or create new? (u/n)"
else
  # Create labels if missing
  gh label create "type:docs-lint" --color "0075ca" \
    --description "docs-lint audit finding" 2>/dev/null || true
  gh label create "priority:p0" --color "b60205" 2>/dev/null || true
  gh label create "priority:p1" --color "d93f0b" 2>/dev/null || true

  # One issue per dimension with findings
  gh issue create \
    --title "$ISSUE_TITLE" \
    --body "$ISSUE_BODY" \
    --label "type:docs-lint" \
    --label "$PRIORITY_LABEL"
fi
```

Dry-run: print issue titles/bodies to stdout instead.

### Step G: Apply fixes

Safe (automatic):
```bash
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"
"$H2T_PYTHON" "$LINT" fix-index --root "$ROOT" --apply
```

Destructive (confirm each before running):
- rename: show `git mv <old> <new>` and wait for "y"
- move: run MOVE pre-checks from non-standard-resolution.md, then confirm
- delete: show `git rm <path>` and wait for "y"

Stage 4: skip all fixes.

### Step H: Validation gate

```bash
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-after.json" 2>/dev/null

DELTA=$(jq -n \
  --slurpfile before "$ROOT/.h2t/lint-before.json" \
  --slurpfile after "$ROOT/.h2t/lint-after.json" \
  '($before[0].findings | map(.id)) as $b_ids |
   ($after[0].findings | map(.id)) as $a_ids |
   {
     fixed:     ($b_ids - $a_ids | length),
     remaining: ($after[0].findings | length),
     new:       ($a_ids - $b_ids),
     pass:      (($a_ids - $b_ids | length) == 0)
   }')

FIXED=$(echo "$DELTA" | jq '.fixed')
AFTER_COUNT=$(jq '.findings | length' "$ROOT/.h2t/lint-after.json")
NEW_IDS=$(echo "$DELTA" | jq '.new')
PASS=$(echo "$DELTA" | jq '.pass')
AFTER_IDS=$(jq '[.findings[].id]' "$ROOT/.h2t/lint-after.json")
PROJECT_TYPE=$(jq -r '(.project_type // .template // "unknown")' \
  "$ROOT/.h2t/docs-lint.yaml" 2>/dev/null || echo "unknown")

echo "findings_before: $BEFORE_COUNT  findings_after: $AFTER_COUNT  fixed: $FIXED  new: $NEW_IDS  $([ "$PASS" = "true" ] && echo PASS || echo FAIL)"

rm -f "$ROOT/.h2t/lint-before.json" "$ROOT/.h2t/lint-after.json"
```

### Step I: Append state

```bash
jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg pt "$PROJECT_TYPE" \
  --argjson before_count "$BEFORE_COUNT" \
  --argjson after_count "$AFTER_COUNT" \
  --argjson fixed "$FIXED" \
  --argjson new_ids "$NEW_IDS" \
  --argjson pass_val "$PASS" \
  --argjson after_ids "$AFTER_IDS" \
  '{schema:1,ts:$ts,mode:"full",project_type:$pt,
    findings_before:$before_count,findings_after:$after_count,
    fixed:$fixed,new:$new_ids,pass:$pass_val,finding_ids:$after_ids}' \
  >> "$ROOT/.h2t/lint-state.jsonl"
```

---

## Legacy sub-commands (still work)

```bash
"$H2T_PYTHON" "$LINT" audit --root .
"$H2T_PYTHON" "$LINT" plan --root .
"$H2T_PYTHON" "$LINT" fix-safe --root .
"$H2T_PYTHON" "$LINT" fix-index --root .
"$H2T_PYTHON" "$LINT" doctor --json --root .
```

## References

Load on demand:
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/naming-conventions.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md`
````

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): rewrite SKILL.md v2 — full pipeline with fixed maintenance/gate/dry-run"
```

---

## Task 7: Plugin version bump

- [ ] **Step 1: Bump to v1.0.17**

```bash
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev 1.0.17
```

- [ ] **Step 2: Verify**

```bash
grep '"version"' C:/dev/h2t-skills/plugins/h2t-dev/plugin.json
```

Expected: `"version": "1.0.17"`

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/plugin.json plugins/h2t-dev/CHANGELOG.md
git -C C:/dev/h2t-skills commit -m "chore: bump h2t-dev to 1.0.17 — docs-lint v2 full audit pipeline"
```

---

## Self-Review

**All Codex P1 addressed:**

| P1 | Fix |
|---|---|
| project_type vs template | Task 2: `project_type` normalizes to `template` internally |
| _run_audit bypasses extensions | Task 4: refactored to use `_collect_all_findings()` |
| Maintenance delta broken | Task 6: uses `doctor --json` for IDs, LAST_STATE from jsonl |
| State append variables undeclared | Task 6 Step I: all vars derived from jq delta + doctor output |
| severity warn/info ≠ spec | Task 3: `_normalize_severities()` maps to critical/important/low |
| String exceptions crash | Task 2 + Task 3: `isinstance(exc, dict)` guard everywhere |
| Pre-flight only on main/master | Task 6 Step A: warns on ANY dirty worktree |
| --dry-run missing | Task 6: `$DRY_RUN` variable, skips commits + issues |
| fix-safe/fix-index behavior | Task 6 Step G: safe=auto, destructive=confirm, stage4=skip |

**All Codex P2 addressed:**

| P2 | Fix |
|---|---|
| Cap by type not dimension | Task 3: `_cap_by_dimension` by `type`; acceptable given type≈dimension |
| Exception warnings capped | Task 3: warnings appended AFTER cap |
| Vendor filter misses empty-path | Task 3: `_is_vendor_message()` for empty-path findings |
| Standard h2t labels | Task 6: creates labels from spec if missing |
| Missing reference behavior | Task 6 Phase 1: `[dim-N] reference missing — skipped` |
| python3 → $H2T_PYTHON | Task 6: `$H2T_PYTHON` used throughout SKILL.md |
