# docs-lint v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade docs-lint from a minimal mechanical checker to a full multi-angle audit pipeline with stable finding IDs, exception config, vendor filtering, and a rewritten SKILL.md that drives the model through sniff → gate → audit → plan → issues → fixes → validation.

**Architecture:** Extend `reporter.py` (add finding IDs), `config.py` (add `.h2t/docs-lint.yaml` primary path + exception schema), `lint.py` (vendor filtering, per-dimension limits, exception filtering), then rewrite `SKILL.md` to orchestrate the full pipeline using the new capabilities.

**Tech Stack:** Python 3.11, PyYAML (already a dependency), jq (external CLI used in SKILL.md), gh CLI (for GitHub issues in SKILL.md)

---

## File Map

| File | Change |
|---|---|
| `plugins/h2t-dev/lib/docs/reporter.py` | Add `id` field to `finding()` |
| `plugins/h2t-dev/lib/docs/config.py` | Add `.h2t/docs-lint.yaml` primary path, exception schema, stale/orphan warnings |
| `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | Vendor filtering, per-dimension cap, exception-aware filtering |
| `plugins/h2t-dev/skills/docs-lint/SKILL.md` | Full rewrite — sniff → gate → audit → plan → issues → fixes → validation |
| `plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md` | New — decision tree reference for model |
| `tests/docs/test_reporter.py` | Extend — test `id` field |
| `tests/docs/test_config.py` | Extend — test `.h2t/docs-lint.yaml`, exceptions, stale/orphan |
| `tests/docs/test_lint_v2.py` | New — vendor filtering, per-dimension cap, exception filtering |
| `plugins/h2t-dev/plugin.json` | Version bump |
| `plugins/h2t-dev/CHANGELOG.md` | Entry for v1.0.17 |

---

## Task 1: Add stable `id` field to `finding()`

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/reporter.py`
- Test: `tests/docs/test_reporter.py`

- [ ] **Step 1: Read current test_reporter.py to understand existing tests**

```bash
cat tests/docs/test_reporter.py
```

- [ ] **Step 2: Write failing test for finding ID**

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

- [ ] **Step 3: Run test to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -k "test_finding_has_id" -v
```

Expected: FAIL — `KeyError: 'id'`

- [ ] **Step 4: Add `id` field to `finding()` in reporter.py**

Replace the `finding()` function body:

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

- [ ] **Step 5: Run tests to verify pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/reporter.py tests/docs/test_reporter.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add stable id field to finding() — {type}:{path}"
```

---

## Task 2: Add `.h2t/docs-lint.yaml` support and exception schema to `config.py`

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/config.py`
- Test: `tests/docs/test_config.py`

- [ ] **Step 1: Read test_config.py to understand existing tests**

```bash
cat tests/docs/test_config.py
```

- [ ] **Step 2: Write failing tests**

Add to `tests/docs/test_config.py`:

```python
import datetime
from pathlib import Path
import pytest


def test_h2t_config_takes_priority_over_claude_rules(tmp_path):
    """`.h2t/docs-lint.yaml` is read before `.claude/rules/docs-lint.yaml`."""
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("template: td-tool\n")

    claude_cfg = tmp_path / ".claude" / "rules" / "docs-lint.yaml"
    claude_cfg.parent.mkdir(parents=True)
    claude_cfg.write_text("template: plugin-pack\n")

    from docs.config import load_config
    cfg = load_config(tmp_path)
    assert cfg["template"] == "td-tool"
    assert cfg["_config_source"] == ".h2t/docs-lint.yaml"


def test_exception_stale_flag(tmp_path):
    """Exception older than 90 days is marked stale."""
    old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(f"exceptions:\n  - path: old_dir/\n    reason: test\n    type: archive\n    reviewed: {old_date}\n")

    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("stale" in w["message"] for w in warnings)


def test_exception_orphan_flag(tmp_path):
    """Exception whose path doesn't exist is marked orphan."""
    today = datetime.date.today().isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(f"exceptions:\n  - path: nonexistent_dir/\n    reason: test\n    type: archive\n    reviewed: {today}\n")

    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("orphan exception" in w["message"] for w in warnings)


def test_exception_no_warning_when_current(tmp_path):
    """Fresh exception with existing path produces no warnings."""
    today = datetime.date.today().isoformat()
    target = tmp_path / "benchmark_results"
    target.mkdir()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(f"exceptions:\n  - path: benchmark_results/\n    reason: live data\n    type: operational_data\n    reviewed: {today}\n")

    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert warnings == []
```

- [ ] **Step 3: Run tests to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -k "test_h2t_config or test_exception" -v
```

Expected: FAIL — `_config_source` key missing, `get_exception_warnings` not found

- [ ] **Step 4: Rewrite `config.py`**

Replace `plugins/h2t-dev/lib/docs/config.py` entirely:

```python
"""Per-repo docs-lint configuration discovery.

Search order:
  1. .h2t/docs-lint.yaml  (project-level, machine-readable)
  2. .claude/rules/docs-lint.yaml  (legacy location)
"""
from __future__ import annotations
import datetime
from pathlib import Path
from typing import Any

CONFIG_PATHS = [".h2t/docs-lint.yaml", ".claude/rules/docs-lint.yaml"]

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
    "_config_source": None,
}

_STALE_DAYS = 90


def load_config(repo_root: Path) -> dict[str, Any]:
    """Load config from first found config path; fall back to defaults."""
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
        merged["_config_source"] = config_path
        return merged
    return dict(_DEFAULTS)


def get_exception_warnings(exceptions: list[dict], repo_root: Path) -> list[dict]:
    """Return warning findings for stale or orphan exceptions.

    Stale: `reviewed` date older than _STALE_DAYS days.
    Orphan: `path` no longer exists in repo.
    """
    from docs.reporter import finding  # avoid circular at module level
    warnings = []
    today = datetime.date.today()
    for exc in exceptions:
        path = exc.get("path", "")
        reviewed_str = exc.get("reviewed")

        # Orphan check: path doesn't exist
        full_path = repo_root / path.rstrip("/")
        if not full_path.exists():
            warnings.append(finding(
                "structure", "warn", path,
                f"orphan exception in docs-lint config: '{path}' no longer exists — remove from config",
            ))
            continue

        # Stale check: reviewed date
        if reviewed_str:
            try:
                reviewed = datetime.date.fromisoformat(str(reviewed_str))
                age = (today - reviewed).days
                if age > _STALE_DAYS:
                    warnings.append(finding(
                        "structure", "warn", path,
                        f"stale exception: '{path}' last reviewed {age}d ago (>{_STALE_DAYS}d) — re-confirm or remove",
                    ))
            except (ValueError, TypeError):
                pass

    return warnings
```

- [ ] **Step 5: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/lib/docs/config.py tests/docs/test_config.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): .h2t/docs-lint.yaml primary config + exception stale/orphan warnings"
```

---

## Task 3: Add vendor filtering, per-dimension cap, exception filtering to `lint.py`

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_v2.py` (new)

- [ ] **Step 1: Write failing tests in new file**

Create `tests/docs/test_lint_v2.py`:

```python
"""Tests for docs-lint v2: vendor filtering, dimension cap, exception filtering."""
from pathlib import Path
import pytest


def _make_repo(tmp_path: Path, files: list[str]) -> Path:
    """Create a minimal git-like repo structure with given file paths."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "documentation.md").write_text("# rules\n")
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("content\n")
    return tmp_path


def test_vendor_paths_excluded_from_findings(tmp_path):
    """Findings from .venv/ and node_modules/ should not appear."""
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"))
    from lint import _collect_all_findings

    repo = _make_repo(tmp_path, [
        ".venv/lib/site-packages/docs/README.md",
        "node_modules/pkg/docs/README.md",
    ])
    findings = _collect_all_findings(repo)
    paths = [f["path"] for f in findings]
    assert not any(".venv" in p for p in paths), f"vendor path in findings: {paths}"
    assert not any("node_modules" in p for p in paths)


def test_per_dimension_cap(tmp_path):
    """No dimension should produce more than 50 findings."""
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"))
    from lint import _collect_all_findings, _DIM_LIMIT

    # Create 60 orphan-eligible files in docs/superpowers/plans/
    repo = _make_repo(tmp_path, [
        f"docs/superpowers/plans/2026-01-{i:02d}-plan.md" for i in range(1, 61)
    ])
    findings = _collect_all_findings(repo)
    from collections import Counter
    counts = Counter(f["type"] for f in findings)
    for type_, count in counts.items():
        assert count <= _DIM_LIMIT, f"dimension '{type_}' has {count} findings (cap={_DIM_LIMIT})"


def test_exception_paths_filtered_from_findings(tmp_path):
    """Findings matching documented exceptions should be excluded."""
    import datetime
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"))
    from lint import _collect_all_findings

    # Create a non-standard dir
    repo = _make_repo(tmp_path, ["benchmark_results/run_001.json"])

    # Document it as exception
    today = datetime.date.today().isoformat()
    h2t = tmp_path / ".h2t"
    h2t.mkdir(exist_ok=True)
    (h2t / "docs-lint.yaml").write_text(
        f"exceptions:\n  - path: benchmark_results/\n    reason: live data\n    type: operational_data\n    reviewed: {today}\n"
    )

    findings = _collect_all_findings(tmp_path)
    paths = [f["path"] for f in findings]
    assert not any("benchmark_results" in p for p in paths), \
        f"exception path leaked into findings: {paths}"


def test_all_findings_have_id_field(tmp_path):
    """Every finding returned by _collect_all_findings must have an 'id' field."""
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"))
    from lint import _collect_all_findings

    repo = _make_repo(tmp_path, [])
    findings = _collect_all_findings(repo)
    for f in findings:
        assert "id" in f, f"finding missing 'id': {f}"
        assert f["id"], f"finding has empty 'id': {f}"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py -v
```

Expected: FAIL — `_DIM_LIMIT` not found, vendor paths not filtered

- [ ] **Step 3: Add vendor filtering, dimension cap, exception filtering to `lint.py`**

Add after the imports block (after line ~68, before `_SUBCOMMANDS`):

```python
_VENDOR_EXCLUDE = {
    ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_DIM_LIMIT = 50


def _is_vendor_path(path: str) -> bool:
    """Return True if path passes through a vendor/generated directory."""
    return any(part in _VENDOR_EXCLUDE for part in Path(path).parts)


def _apply_exceptions(findings: list[dict], exceptions: list[dict]) -> list[dict]:
    """Remove findings whose path is covered by a documented exception."""
    if not exceptions:
        return findings
    exception_paths = {exc.get("path", "").rstrip("/") for exc in exceptions}
    result = []
    for f in findings:
        fp = f.get("path", "").rstrip("/")
        # Match exact path or prefix (e.g. exception "benchmark_results/" covers
        # "benchmark_results/run_001.json")
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
```

Then modify `_collect_all_findings` — add these three lines at the end, just before `return all_findings`:

```python
    # Post-processing: vendor filter → exception filter → dimension cap
    all_findings = [f for f in all_findings if not _is_vendor_path(f.get("path", ""))]
    cfg_exceptions = cfg.get("exceptions") or []
    all_findings = _apply_exceptions(all_findings, cfg_exceptions)
    # Append exception warnings (stale/orphan) — these bypass the cap
    from docs.config import get_exception_warnings
    all_findings.extend(get_exception_warnings(cfg_exceptions, rp))
    all_findings = _cap_by_dimension(all_findings)
    return all_findings
```

Note: remove the existing `return all_findings` at line 542 since we replace it.

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_v2.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ --ignore=tests/docs/test_execution_tracking.py -q
```

Expected: all existing tests PASS

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_v2.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): vendor filtering, per-dimension cap, exception filtering"
```

---

## Task 4: Write `references/non-standard-resolution.md`

**Files:**
- Create: `plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md`

- [ ] **Step 1: Create the reference file**

```markdown
# Non-Standard Path Resolution Reference

Use this decision tree when evaluating directories or files not present in the
standard project template. Applies to Dimension 8 of the full audit.

---

## Decision Tree

```
Found non-standard path
        │
        ▼
   Is it needed?
   Check: git log --oneline --since="30 days ago" -- <path>
   Check: wc -l <path> or ls <dir>/ — is it empty/stale?
       / \
     Yes   No → Outcome: DELETE
     │         Confirm with user before git rm
     ▼
  Covered by standard template for this project type?
  Check: project_type in .h2t/docs-lint.yaml or autodetected type
      / \
    Yes   No
    │          │
    ▼          ▼
 Misplaced   Is this specific to this project?
 → Outcome:  (not a pattern across h2t repos)
   MOVE          / \
   (see MOVE   Yes   No → Outcome: ADD PROJECT TYPE
   pre-checks) │         (PR proposal to h2t-skills/standards/)
               ▼
          Outcome: EXCEPTION
          Write to .h2t/docs-lint.yaml
```

---

## Outcome: DELETE

Present to user:
```
[non-standard] <path> — no git activity in 30 days, appears unused
Recommendation: DELETE
Command: git rm -r <path>
Confirm before running.
```

Skip DELETE suggestion for `archived` lifecycle stage.

---

## Outcome: MOVE

Present to user:
```
[non-standard] <path> — should be at <target>
Recommendation: MOVE
```

**Pre-checks before confirming move:**

```bash
# 1. Import/reference search (skip if > 1000 results)
grep -r "<path>" . --include="*.py" --include="*.md" -l | head -20

# 2. Generated file check (is it in .gitignore?)
git check-ignore -v <path>

# 3. Symlink check
test -L <path> && echo "SYMLINK — do not git mv"

# 4. Submodule check
git submodule status | grep "<path>"
```

Only proceed with `git mv <path> <target>` after user confirms and pre-checks pass.

---

## Outcome: EXCEPTION

Write to `.h2t/docs-lint.yaml`:

```yaml
exceptions:
  - path: <path>/        # trailing slash for dirs
    reason: "<one-line description of why it's here>"
    type: <operational_data|archive|generated|tool_output|external>
    reviewed: <YYYY-MM-DD>  # today's date
```

Valid types:
- `operational_data` — live data updated by the project (benchmark_results/, setlists/)
- `archive` — historical records, read-only
- `generated` — auto-generated output, not source
- `tool_output` — output from external tools (renders/, exports/)
- `external` — vendored or copied from outside

Exception is re-evaluated if `reviewed` date is older than 90 days.

---

## Outcome: ADD PROJECT TYPE

When a non-standard path pattern appears across multiple h2t repos:

1. Document the pattern in this conversation
2. Propose adding it to `plugins/h2t-dev/lib/docs/project_types.py`
   as a new template entry or extension of an existing one
3. Open a GitHub issue in lichtpfad/h2t-skills with label `type:feature`
4. Do NOT modify project_types.py directly — it requires a PR with review

---

## Project Type Templates (current)

Check `plugins/h2t-dev/lib/docs/project_types.py` for current template list.
Common types: `h2t-platform`, `client-project`, `standalone-tool`, `plugin-pack`, `research`.

---

## Autodetect Precedence

1. `.h2t/docs-lint.yaml` `project_type` field — explicit override
2. `CLAUDE.md` — look for type keywords in first 50 lines
3. `pyproject.toml` presence + `plugins/` dir → `plugin-pack`
4. `pyproject.toml` presence without `plugins/` → `standalone-tool`
5. `package.json` presence → `frontend-tool`
6. Default: `unknown`
```

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/references/non-standard-resolution.md
git -C C:/dev/h2t-skills commit -m "docs(docs-lint): add non-standard path resolution reference"
```

---

## Task 5: Rewrite `SKILL.md`

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/SKILL.md`

- [ ] **Step 1: Write the new SKILL.md**

Replace `plugins/h2t-dev/skills/docs-lint/SKILL.md` entirely:

```markdown
---
name: h2t-dev:docs-lint
description: >-
  Audit and maintain documentation/structure health in h2t-stack repos.
  Runs a full multi-angle audit (sniff → gate → analyze → plan → issues → fixes → validate)
  or maintenance lint depending on project lifecycle stage.
  Scoped to repos using Claude Code + h2t standards.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# docs-lint v2

Documentation and structure health pipeline for h2t-stack repos.

**Scope:** repos using Claude Code, `.claude/rules/`, `docs/superpowers/`, and h2t standards.
Not a general-purpose docs linter.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
ROOT="${1:-.}"   # explicit path or current dir
```

## Pipeline

### Phase 1: Sniff (automatic, no questions)

Run these in parallel:

```bash
# File tree
git ls-files --cached --others --exclude-standard 2>/dev/null | head -500

# Mechanical findings
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" 2>/dev/null

# Key files
cat "$ROOT/CLAUDE.md" 2>/dev/null | head -80
cat "$ROOT/.h2t/docs-lint.yaml" 2>/dev/null
ls "$ROOT/.claude/rules/" 2>/dev/null
```

Also read: `pyproject.toml` or `package.json` if present (first 30 lines).

**Project type autodetect** (first match wins):
1. `.h2t/docs-lint.yaml` → `project_type` field
2. `CLAUDE.md` first 50 lines → look for type keywords
3. `pyproject.toml` + `plugins/` dir → `plugin-pack`
4. `pyproject.toml` without `plugins/` → `standalone-tool`
5. Default → `unknown`

**Output exactly 3 lines:**
```
Тип: <detected type>, <organic-grow|structured|greenfield>
Состояние: <1-line summary of docs/code/agent health>
Сигнал: <порядок|хаос|зрелый> → рекомендую (<stage number>)
```

### Phase 2: Gate — ONE question

Ask exactly:

```
Стадия проекта:
(1) cleanup — organic-grow, нужен полный аудит
(2) mature — стабильная структура, нужен maintenance lint
(3) greenfield — новый репо, setup-ориентированный аудит
(4) archived — read-only, только анализ без деструктивных предложений
```

Wait for answer. Proceed to the matching branch.

---

## Branch: Maintenance (stage 2)

```bash
# Read last valid state
LAST_STATE=$(tail -100 "$ROOT/.h2t/lint-state.jsonl" 2>/dev/null | \
  python3 -c "
import sys, json
for line in reversed(sys.stdin.readlines()):
    try:
        obj = json.loads(line)
        if obj.get('schema') == 1:
            print(json.dumps(obj))
            break
    except: pass
" 2>/dev/null)

# Run audit
"$H2T_PYTHON" "$LINT" audit --root "$ROOT"

# Apply safe fixes automatically
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"
```

Compare current finding IDs with IDs from `$LAST_STATE.finding_ids`. Show only delta
(new finding IDs not present in last state).

If `$LAST_STATE` is empty (first run): switch to cleanup branch with note
`No previous state — running full audit instead`.

Append to `.h2t/lint-state.jsonl`:
```json
{"schema":1,"ts":"<ISO8601>","mode":"maintenance","project_type":"<type>","findings_before":<N>,"findings_after":<N>,"fixed":<N>,"new":[],"pass":<bool>,"finding_ids":[<ids>]}
```

---

## Branch: Full Audit (stages 1, 3, 4)

### Step A: Pre-flight checks

```bash
# 1. Dirty worktree
DIRTY=$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -v '^??' | head -1)
[ -n "$DIRTY" ] && echo "WARNING: uncommitted changes detected"

# 2. gh auth (only if issues will be created)
gh auth status 2>/dev/null || echo "GH_AUTH_FAILED"

# 3. Current branch
git -C "$ROOT" branch --show-current 2>/dev/null

# 4. Duplicate issue check (if GH auth ok)
gh issue list --label "type:docs-lint" --json number,title --limit 20 2>/dev/null
```

If dirty worktree on main/master: ask "Continue? (y/n)" before proceeding.
If GH_AUTH_FAILED: note in report, skip issue creation step.

### Step B: Multi-angle analysis

Read references on demand:
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md` — dims 1, 2, 6
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md` — dim 3, 4
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md` — dim 8

```bash
# Capture before-state for validation gate
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-before.json" 2>/dev/null
```

Run all 8 dimensions:

| # | Dimension | How |
|---|---|---|
| 1 | Docs structure | `lint.py doctor --json` findings type=orphan,structure + documentation-structure.md |
| 2 | Naming | findings type=naming + naming-conventions.md |
| 3 | Code organization | git ls-files + code-organization.md — src/ layout, test location, scripts |
| 4 | Data storage | git ls-files — operational data dirs in root |
| 5 | Agent accessibility | Read CLAUDE.md + .claude/rules/ — env, commands, invariants, secrets, forbidden |
| 6 | Frontmatter | findings type=frontmatter |
| 7 | Root hygiene | findings type=structure (root count) + git ls-files root level |
| 8 | Non-standard dirs | git ls-files vs standard template — use non-standard-resolution.md decision tree |

**Skip vendor paths** in all dimensions: `.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `build/`, `.git/`.

**Stage 4 (archived):** collect findings but mark all destructive recommendations as `[ANALYSIS ONLY — archived repo]`.

### Step C: Report

Present findings grouped by severity. Format:

```
## docs-lint audit — {project} — {date}

### Critical (must fix)
- [dim-N] <path>: <message>

### Important
- [dim-N] <path>: <message>

### Low
- [dim-N] <path>: <message>

### Config warnings
- [stale-exception] <path>: last reviewed N days ago
- [orphan-exception] <path>: no longer exists
```

### Step D: Write plan file

Save findings as `docs/superpowers/plans/YYYY-MM-DD-docs-audit.md`. Commit:

```bash
git -C "$ROOT" add docs/superpowers/plans/YYYY-MM-DD-docs-audit.md
git -C "$ROOT" commit -m "docs: docs-lint audit plan $(date +%Y-%m-%d)"
```

### Step E: Create GitHub issues

Only if GH auth succeeded and stage ≠ 4.

For each `critical` and `important` dimension with findings, create one issue:

```bash
gh issue create \
  --title "{repo-short}: [docs-lint] {dimension} — {N} findings" \
  --body "$(cat <<'EOF'
## Findings

{findings list}

## Source

Generated by /h2t-dev:docs-lint audit on {date}.
EOF
)" \
  --label "type:docs-lint" \
  --label "{priority-label}"
```

Label creation if missing:
```bash
gh label create "type:docs-lint" --color "0075ca" --description "docs-lint audit finding" 2>/dev/null || true
```

Priority labels: `priority:p0` for critical, `priority:p1` for important.

Check for existing issue with same title before creating:
```bash
gh issue list --label "type:docs-lint" --search "{title}" --json number,title | jq '.[0]'
```
If found: show existing issue number, ask "Update existing #N or create new?"

### Step F: Apply fixes

**Safe fixes — automatic, no confirmation:**
```bash
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"
"$H2T_PYTHON" "$LINT" fix-index --root "$ROOT" --apply
```

**Destructive fixes — confirm each before running:**
- rename: `git mv <old> <new>`
- move: `git mv <src> <dst>` (after pre-checks from non-standard-resolution.md)
- delete: `git rm <path>`

For stage 4 (archived): skip all fixes, show analysis only.

### Step G: Validation gate

```bash
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-after.json" 2>/dev/null

jq -n \
  --slurpfile before "$ROOT/.h2t/lint-before.json" \
  --slurpfile after "$ROOT/.h2t/lint-after.json" \
  '($before[0].findings | map(.id)) as $b_ids |
   ($after[0].findings | map(.id)) as $a_ids |
   {
     fixed:     ($b_ids - $a_ids | length),
     remaining: ($after[0].findings | length),
     new:       ($a_ids - $b_ids),
     pass:      (($a_ids - $b_ids | length) == 0)
   }'
```

`pass: true` = zero new finding IDs. If any `critical` ID appears in `new`: FAIL.

Show:
```
### Validation gate
findings_before: N  findings_after: M  fixed: K  new: [...]  PASS/FAIL
```

```bash
# Clean up temp files
rm -f "$ROOT/.h2t/lint-before.json" "$ROOT/.h2t/lint-after.json"
```

### Step H: Append state

```bash
mkdir -p "$ROOT/.h2t"
AFTER_IDS=$("$H2T_PYTHON" -c "
import json, sys
data = json.load(open('$ROOT/.h2t/lint-state-tmp.json'))
ids = [f['id'] for f in data.get('findings', [])]
print(json.dumps(ids))
" 2>/dev/null || echo "[]")

echo "{\"schema\":1,\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"mode\":\"full\",\"project_type\":\"$PROJECT_TYPE\",\"findings_before\":$BEFORE_COUNT,\"findings_after\":$AFTER_COUNT,\"fixed\":$FIXED,\"new\":$NEW_IDS,\"pass\":$PASS,\"finding_ids\":$AFTER_IDS}" >> "$ROOT/.h2t/lint-state.jsonl"
```

---

## References

Load on demand:

- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/naming-conventions.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md`

## Legacy sub-commands (still work)

```bash
"$H2T_PYTHON" "$LINT" audit --root .
"$H2T_PYTHON" "$LINT" plan --root .
"$H2T_PYTHON" "$LINT" fix-safe --root .
"$H2T_PYTHON" "$LINT" fix-index --root .
"$H2T_PYTHON" "$LINT" doctor --json --root .
```
```

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): rewrite SKILL.md — sniff→gate→audit→plan→issues→fixes→validate"
```

---

## Task 6: Plugin version bump

**Files:**
- Modify: `plugins/h2t-dev/plugin.json`
- Modify: `plugins/h2t-dev/CHANGELOG.md`

- [ ] **Step 1: Bump to v1.0.17**

```bash
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev 1.0.17
```

- [ ] **Step 2: Verify bump**

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

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Sniff phase (git ls-files + key files + lint.py doctor) | Task 5, Phase 1 |
| Gate — 4 lifecycle stages | Task 5, Phase 2 |
| Full audit — 8 dimensions | Task 5, Step B |
| Maintenance — delta from .h2t/lint-state.jsonl | Task 5, Maintenance branch |
| First-run fallback to full audit | Task 5, Maintenance branch |
| Pre-flight checks (dirty worktree, gh auth, branch, dup issues) | Task 5, Step A |
| Stable finding IDs | Task 1 |
| `.h2t/docs-lint.yaml` primary config | Task 2 |
| Exception filtering | Task 3 |
| Stale/orphan exception warnings | Task 2 |
| Vendor path filtering | Task 3 |
| Per-dimension cap (50) | Task 3 |
| Non-standard resolution decision tree | Task 4 |
| Plan file + commit | Task 5, Step D |
| GitHub issues immediately | Task 5, Step E |
| Safe fixes auto, destructive with confirm | Task 5, Step F |
| Validation gate (jq set subtraction, correct IDs) | Task 5, Step G |
| State JSONL append | Task 5, Step H |
| Schema versioning + corruption handling | Task 5, Maintenance branch |
| Stage 4 (archived) — analysis only | Task 5, Steps B, F |

**Type consistency check:** `_DIM_LIMIT` defined in Task 3 and referenced in Task 3 tests — consistent. `finding()` returns `id` field defined in Task 1 and tested in Task 3 — consistent. `get_exception_warnings()` defined in Task 2 and called in Task 3 — consistent.

**Placeholder scan:** None found.
