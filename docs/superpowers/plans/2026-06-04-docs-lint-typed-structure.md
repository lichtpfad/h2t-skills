# docs-lint Type-Aware Structure Checks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `check_project_structure_typed(rp, template)` to `docs-lint`, wire it into `_collect_all_findings()` so that repos with an explicit `template:` in `docs-lint.yaml` are checked against their type-specific directory structure from `PROJECT_TYPES`.

**Architecture:** `lint.py` already imports `load_config(rp)` which reads `.claude/rules/docs-lint.yaml` and returns `{"template": str|None, ...}`. We import `PROJECT_TYPES` from `docs.project_types` (prerequisite), add one pure function `check_project_structure_typed()`, wire it into `_collect_all_findings()`, and extend `fix_structure()` with a matching scaffolding path. Each piece has its own task and commit.

**`PROJECT_TYPES` contract** (from prerequisite `project_types.py`):
```python
PROJECT_TYPES["code_repo"]      = {"root_dirs": ["src","tests","docs","scripts"], "docs_dirs": []}
PROJECT_TYPES["client_project"] = {"root_dirs": ["docs","data","deliverables","scripts"],
                                    "docs_dirs": ["docs/ops","docs/research","docs/deliverables"]}
PROJECT_TYPES["research_project"] = {"root_dirs": ["docs","data"], "docs_dirs": ["docs/research"]}
PROJECT_TYPES["creative_project"] = {"root_dirs": ["assets","scripts","exports","docs"],
                                      "docs_dirs": ["docs/assets","docs/briefs","docs/reviews"]}
PROJECT_TYPES["personal_os"]    = {"root_dirs": ["docs"], "docs_dirs": ["docs/notes","docs/sessions"]}
PROJECT_TYPES["ops_workflow"]   = {"root_dirs": ["docs","scripts"],
                                   "docs_dirs": ["docs/runbooks","docs/logs"]}
```

**`finding()` format** (from `docs.reporter`):
```python
finding(type_: str, severity: str, path: str, message: str, safe_fix: str | None = None) -> dict
# → {"type", "severity", "path", "message"[, "safe_fix"]}
```
Typed findings additionally get a `"template"` key set on the dict after creation (machine-readable, not only embedded in message text).

**Path assumption:** `root_dirs` / `docs_dirs` entries are trusted internal POSIX-style relative paths. No validation of `..`, absolute paths, or Windows separators is needed — inputs come only from `PROJECT_TYPES`, which is a controlled constant. This assumption must be violated explicitly in code review if `PROJECT_TYPES` ever accepts user input.

**Deduplication note:** `REQUIRED_CORE_DIRS = ['docs/superpowers/specs', 'docs/superpowers/plans', 'docs/adr', 'docs/reports']` — deep docs subdirs only. Typed `root_dirs` are top-level dirs (src, tests, etc.), typed `docs_dirs` are template-specific subdirs. No overlap with `REQUIRED_CORE_DIRS` by design. If a future template adds `docs/adr` to `docs_dirs`, `fix_structure()` will no-op (dir exists), and `check_project_structure_typed()` will report no finding. No dedup logic needed now; add a note in the function docstring.

**Tech Stack:** Python stdlib only, no new dependencies. All new code in `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` and `tests/docs/test_lint_checks.py`.

---

## Prerequisites

**Required:** Plan `2026-06-03-project-types-foundation.md` must be fully implemented.

Verify shape (all 6 keys + correct fields):
```
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'C:/dev/h2t-skills/plugins/h2t-dev/lib'); from docs.project_types import PROJECT_TYPES; spec = PROJECT_TYPES['code_repo']; assert 'root_dirs' in spec and 'docs_dirs' in spec; print('ok', list(PROJECT_TYPES))"
```
Expected: `ok ['code_repo', 'client_project', 'research_project', 'creative_project', 'personal_os', 'ops_workflow']`

**If this fails — stop. Do not proceed past this step.** Implement `2026-06-03-project-types-foundation.md` first.

Verify `template:` semantics in h2t-skills own config:
```
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'C:/dev/h2t-skills/plugins/h2t-dev/lib'); from docs.config import load_config; from pathlib import Path; cfg = load_config(Path('C:/dev/h2t-skills')); print('template =', repr(cfg.get('template')))"
```
Expected: prints `template = 'code_repo'` (confirms `template:` means project-structure type, not doc template).

Verify no import cycle — `docs.project_types` must NOT import from lint.py or docs.config:
```
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "import ast, pathlib; src = pathlib.Path('C:/dev/h2t-skills/plugins/h2t-dev/lib/docs/project_types.py').read_text(); tree = ast.parse(src); imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]; print('imports:', imports); assert 'docs.config' not in imports and 'lint' not in imports, 'CYCLE!'; print('no cycle')"
```
Expected: `no cycle`

---

## How chaos cleanup works (workflow, not code)

This plan adds the **detection** layer. Full cleanup flow for a chaotic repo:

```
1. docs-lint doctor --root <repo>    → surfaces all issues including typed structure gaps
2. docs-lint fix-safe --root <repo>  → creates MISSING EMPTY DIRS only (scaffolding)
                                       ⚠ files in wrong places are NOT moved automatically
                                       output includes: "NOTE: N files may need git mv — run docs-lint plan"
3. git mv <wrong-place> <right-place> → human moves files (preserves git history)
4. docs-lint doctor --root <repo>    → verify clean
```

`fix_structure()` scope is intentionally narrow — only creates missing directories. Moving files is a destructive decision requiring human judgment. Auto-move would silently break imports, links, and git history.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` | Import, `check_project_structure_typed()`, wire into `_collect_all_findings()`, extend `fix_structure()` |
| Modify | `tests/docs/test_lint_checks.py` | Unit + integration + fix_structure + CLI tests |

**Finding types after this plan:**

| Message prefix | `"template"` field | Meaning |
|----------------|-------------------|---------|
| `missing dir: X/` | absent | Generic — from `REQUIRED_CORE_DIRS` (type-agnostic) |
| `missing required dir: X/ (template: Y)` | `"Y"` | Typed root dir missing |
| `missing template dir: X/ (template: Y)` | `"Y"` | Typed docs/ subdir missing |
| `path exists but is not a dir: X/ (template: Y)` | `"Y"` | Collision: file at expected dir location |
| `legacy dir: X/` | absent | File in wrong location |
| `data in docs: X` | absent | Content boundary violation |

Typed findings (with `"template"` key) are filterable by `project-audit` and other consumers using `f.get("template")`.

---

## Task 1: `check_project_structure_typed()` — function + unit tests

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Verify prerequisite**

```
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'C:/dev/h2t-skills/plugins/h2t-dev/lib'); from docs.project_types import PROJECT_TYPES; spec = PROJECT_TYPES['code_repo']; assert 'root_dirs' in spec and 'docs_dirs' in spec; print('ok', list(PROJECT_TYPES))"
```

Expected: `ok ['code_repo', ...]` — if fail, stop here.

- [ ] **Step 2: Write failing tests**

Append to `tests/docs/test_lint_checks.py`:

```python
from lint import check_project_structure_typed


def test_check_typed_code_repo_missing_src(tmp_path):
    result = check_project_structure_typed(tmp_path, "code_repo")
    assert any("src" in m for m in result), result


def test_check_typed_code_repo_all_present(tmp_path):
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    assert check_project_structure_typed(tmp_path, "code_repo") == []


def test_check_typed_client_project_missing_deliverables(tmp_path):
    for d in ["docs", "data", "scripts"]:
        (tmp_path / d).mkdir()
    result = check_project_structure_typed(tmp_path, "client_project")
    assert any("deliverables" in m for m in result), result


def test_check_typed_unknown_template_returns_empty(tmp_path):
    assert check_project_structure_typed(tmp_path, "nonexistent_type") == []


def test_check_typed_research_project_missing_docs_subdir(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    result = check_project_structure_typed(tmp_path, "research_project")
    assert any("docs/research" in m for m in result), result


def test_check_typed_research_project_fully_present(tmp_path):
    for d in ["docs", "data", "docs/research"]:
        (tmp_path / d).mkdir(parents=True)
    assert check_project_structure_typed(tmp_path, "research_project") == []


def test_check_typed_creative_project_missing_assets(tmp_path):
    result = check_project_structure_typed(tmp_path, "creative_project")
    assert any("assets" in m for m in result), result


def test_check_typed_messages_include_template_name(tmp_path):
    result = check_project_structure_typed(tmp_path, "code_repo")
    assert all("code_repo" in m for m in result), result


def test_check_typed_file_at_dir_path_is_collision(tmp_path):
    """A file occupying a required dir path → 'not a dir' message, not 'missing'."""
    (tmp_path / "src").write_text("oops")  # file, not dir
    result = check_project_structure_typed(tmp_path, "code_repo")
    src_msgs = [m for m in result if "src" in m]
    assert any("not a dir" in m for m in src_msgs), src_msgs
```

- [ ] **Step 3: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "check_typed" -v
```

Expected: `ImportError` or `AttributeError: module 'lint' has no attribute 'check_project_structure_typed'`

- [ ] **Step 4: Add import and function to `lint.py`**

After `from docs.config import load_config`, add:

```python
try:
    from docs.project_types import PROJECT_TYPES as _PROJECT_TYPES
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    _PROJECT_TYPES = {}
    _PROJECT_TYPES_AVAILABLE = False
```

After `check_repo_root()` and before `check_data_docs_boundary()`, add:

```python
def check_project_structure_typed(rp: Path, template: str) -> list[str]:
    """Check type-specific root + docs dirs from PROJECT_TYPES.

    Only called when docs-lint.yaml has an explicit non-empty template field.
    Returns [] for unknown templates (graceful no-op).

    Findings include '(template: X)' suffix in message AND are tagged with
    a 'template' key on the finding dict — filterable by machine consumers.

    Note: root_dirs/docs_dirs don't overlap with REQUIRED_CORE_DIRS by design.
    If a future template entry adds a dir already in REQUIRED_CORE_DIRS,
    check_structure() will already report it and this function will produce
    a duplicate. Fix: dedup by message in _collect_all_findings() at that time.

    Assumes PROJECT_TYPES entries contain trusted internal POSIX relative paths.
    """
    spec = _PROJECT_TYPES.get(template)
    if spec is None:
        return []
    failures = []
    for d in spec.get("root_dirs", []):
        p = rp / d
        if p.is_dir():
            continue
        if p.exists():
            failures.append(f"path exists but is not a dir: {d}/ (template: {template})")
        else:
            failures.append(f"missing required dir: {d}/ (template: {template})")
    for d in spec.get("docs_dirs", []):
        p = rp / d
        if p.is_dir():
            continue
        if p.exists():
            failures.append(f"path exists but is not a dir: {d}/ (template: {template})")
        else:
            failures.append(f"missing template dir: {d}/ (template: {template})")
    return failures
```

- [ ] **Step 5: Run unit tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "check_typed" -v
```

Expected: all 9 PASSED.

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): add check_project_structure_typed — type-aware dir checks"
```

---

## Task 2: Wire into `_collect_all_findings()` + integration tests

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/docs/test_lint_checks.py`:

```python
import lint as _lint_module


def test_collect_findings_no_typed_check_without_template(tmp_path):
    """Without docs-lint.yaml, no typed findings appear."""
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed == []


def test_collect_findings_typed_check_fires_when_template_set(tmp_path):
    """template: code_repo in yaml → missing src/ appears as a typed structure finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template") == "code_repo"]
    assert any("src" in f["message"] for f in typed), [f["message"] for f in typed]


def test_collect_findings_typed_check_has_template_field(tmp_path):
    """Typed findings have 'template' key set — machine-readable, not just in message."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed, "expected at least one typed finding"
    for f in typed:
        assert f["template"] == "code_repo"


def test_collect_findings_typed_check_silent_when_all_present(tmp_path):
    """code_repo with all root_dirs present → no typed findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template") == "code_repo"]
    assert typed == []


def test_collect_findings_unknown_template_no_crash(tmp_path):
    """template: nonexistent_type in yaml → no typed findings, no exception."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: nonexistent_type\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed == []
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "collect_findings" -v
```

Expected: `test_collect_findings_typed_check_fires_when_template_set` and `test_collect_findings_typed_check_has_template_field` fail (typed check not yet wired).

- [ ] **Step 3: Wire into `_collect_all_findings()`**

Replace the `_collect_all_findings()` function in `lint.py`:

```python
def _collect_all_findings(rp: Path, no_pymarkdown: bool = False) -> list[dict]:
    """Run all checks and return findings list (navigation first, metadata last)."""
    all_findings = []
    all_findings.extend(find_orphan_files(rp))
    all_findings.extend(check_naming_all_docs(rp))
    extra = REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])
    cfg = load_config(rp)
    # template is set only when docs-lint.yaml has an explicit non-empty template field
    template = cfg.get("template") or None
    typed_msgs = check_project_structure_typed(rp, template) if template else []
    for msg in (
        check_structure(rp)
        + typed_msgs
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    ):
        f = finding("structure", "warn", "", msg)
        if template and "(template:" in msg:
            f["template"] = template
        all_findings.append(f)
    for msg in check_frontmatter(rp):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))
    return all_findings
```

- [ ] **Step 4: Run integration tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "check_typed or collect_findings" -v
```

Expected: all new tests PASSED.

- [ ] **Step 5: Run full docs test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v --ignore=tests/docs/test_execution_tracking.py
```

Expected: all PASSED (no regressions).

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): wire typed structure check into _collect_all_findings"
```

---

## Task 3: `fix_structure()` extension + CLI test + smoke test + bump

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Test: `tests/docs/test_lint_checks.py`

- [ ] **Step 1: Write failing fix_structure tests**

Append to `tests/docs/test_lint_checks.py`:

```python
from lint import fix_structure


def test_fix_structure_creates_typed_dirs_for_code_repo(tmp_path):
    """fix_structure creates root_dirs from PROJECT_TYPES when template is set."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    fixes = fix_structure(tmp_path)
    assert (tmp_path / "src").is_dir()
    assert (tmp_path / "tests").is_dir()
    assert any("src" in f for f in fixes), fixes


def test_fix_structure_noop_without_template(tmp_path):
    """fix_structure without template creates only REQUIRED_CORE_DIRS, no typed dirs."""
    fixes = fix_structure(tmp_path)
    assert not any("template:" in f for f in fixes), fixes


def test_fix_structure_noop_unknown_template(tmp_path):
    """fix_structure with unknown template doesn't crash, creates no typed dirs."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: nonexistent_type\n",
        encoding="utf-8",
    )
    fixes = fix_structure(tmp_path)
    assert not any("template:" in f for f in fixes), fixes


def test_fix_structure_does_not_move_existing_files(tmp_path):
    """fix_structure never moves or deletes files — even in wrong-location dirs."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    # Pre-create a file at an unexpected location
    old_dir = tmp_path / "old_scripts"
    old_dir.mkdir()
    sentinel = old_dir / "important.py"
    sentinel.write_text("# do not touch", encoding="utf-8")
    fix_structure(tmp_path)
    # File must still be exactly where it was
    assert sentinel.exists()
    assert sentinel.read_text(encoding="utf-8") == "# do not touch"
    assert (tmp_path / "old_scripts").is_dir()


def test_fix_structure_creates_parents_for_docs_dirs(tmp_path):
    """fix_structure creates parent dirs recursively for docs_dirs like docs/research."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: research_project\n",
        encoding="utf-8",
    )
    fix_structure(tmp_path)
    assert (tmp_path / "docs" / "research").is_dir()
```

- [ ] **Step 2: Run to confirm failure**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "fix_structure" -v
```

Expected: `test_fix_structure_creates_typed_dirs_for_code_repo` fails (typed dirs not yet created).

- [ ] **Step 3: Extend `fix_structure()` in `lint.py`**

Replace the existing `fix_structure()`:

```python
def fix_structure(rp: Path) -> list[str]:
    """Create missing dirs (scaffolding only). Does NOT move files — use git mv for that.

    Creates REQUIRED_CORE_DIRS always, plus PROJECT_TYPES[template] dirs when template: is set.
    Idempotent: existing dirs are left unchanged.
    Returns list of "created: <path>/" strings for newly created dirs only.
    """
    fixes = []
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if ensure_dir(d):
            fixes.append(f"created: {rel_dir}/")
    cfg = load_config(rp)
    template = cfg.get("template") or None
    if template:
        spec = _PROJECT_TYPES.get(template)
        if spec:
            for rel_dir in spec.get("root_dirs", []) + spec.get("docs_dirs", []):
                d = rp / rel_dir
                already_exists = d.exists()
                d.mkdir(parents=True, exist_ok=True)
                if not already_exists:
                    fixes.append(f"created: {rel_dir}/ (template: {template})")
    return fixes
```

- [ ] **Step 4: Run fix_structure tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "fix_structure" -v
```

Expected: all 5 PASSED.

- [ ] **Step 5: Add doctor JSON CLI test**

Append to `tests/docs/test_lint_checks.py`:

```python
import subprocess as _subprocess


def test_doctor_json_output_schema(tmp_path):
    """docs-lint doctor --json produces h2t_lifecycle_report/v0.1 with expected keys."""
    import sys as _sys
    lint_script = (
        _lint_module_path if (_lint_module_path := getattr(_lint_module, "__file__", None))
        else None
    )
    if lint_script is None:
        return  # skip if can't find script
    result = _subprocess.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["schema"] == "h2t_lifecycle_report/v0.1"
    assert "status" in data
    assert "total_findings" in data
    assert isinstance(data["findings"], list)


def test_doctor_json_typed_finding_has_template_field(tmp_path):
    """doctor --json findings with template: have 'template' key in JSON."""
    import sys as _sys
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return
    result = _subprocess.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    typed = [f for f in data["findings"] if f.get("template")]
    assert typed, "expected at least one typed finding in doctor JSON output"
    for f in typed:
        assert f["template"] == "code_repo"
```

**Note:** `test_doctor_json_output_schema` requires `import json` at top of test file. Verify it's already imported (it's in the existing test module — check before adding a duplicate).

- [ ] **Step 6: Run all new tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py -k "fix_structure or doctor_json" -v
```

Expected: all 7 PASSED.

- [ ] **Step 7: Run full docs test suite**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v --ignore=tests/docs/test_execution_tracking.py
```

Expected: all PASSED.

- [ ] **Step 8: Smoke test on real repo (no-crash + live detection)**

```
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/dev/h2t-skills --json --no-pymarkdown
```

Parse output manually and verify:
- `schema == "h2t_lifecycle_report/v0.1"` ✓
- `status` is `"ok"` or `"warning"` (not error, no exception)
- Any finding with `"template"` key → typed check is live
- Print: `"typed findings: N"` where N = count of findings with `"template"` field

If repo is missing typed dirs, typed findings prove detection works. If none → repo is compliant.

- [ ] **Step 9: Version bump**

```
python C:/dev/h2t-skills/scripts/bump_plugin.py h2t-dev patch
```

- [ ] **Step 10: Commit**

```
git -C C:/dev/h2t-skills add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py plugins/h2t-dev/.claude-plugin/plugin.json
git -C C:/dev/h2t-skills commit -m "feat(docs-lint): extend fix_structure for typed dirs + CLI JSON tests"
```

---

## Self-Review

**Spec coverage:**
- [x] `check_project_structure_typed(rp, template)` added — Task 1
- [x] Wired into `_collect_all_findings()` — Task 2 Step 3
- [x] Gated on explicit non-empty template (repos without docs-init unaffected) — Task 2 Step 3
- [x] `fix_structure()` extended to scaffold typed dirs — Task 3 Step 3
- [x] Unit tests: 9 tests including collision case and template name in messages — Task 1
- [x] Integration: no-template, template+missing, template+present, unknown template, template field in dict — Task 2
- [x] fix_structure() tests: creates dirs, no-op without template, no-op unknown, preserves files, creates parents — Task 3
- [x] CLI/doctor JSON tests: schema, template field in JSON output — Task 3 Step 5
- [x] Smoke test on real repo — Task 3 Step 8
- [x] Version bump — Task 3 Step 9

**Codex 20-issue checklist:**
- [x] #1 Task split: 3 separate tasks, each with own commit
- [x] #2 Wrong count framing: use `-k` selectors, not absolute counts
- [x] #3 Unknown template in wired path: `test_collect_findings_unknown_template_no_crash`
- [x] #4 Shape validation: `.get("root_dirs", [])` / `.get("docs_dirs", [])` in both check and fix
- [x] #5 Path normalization: assumption documented — internal trusted POSIX paths only
- [x] #6 Duplicate findings: documented in function docstring — no overlap with REQUIRED_CORE_DIRS by design
- [x] #7 "template is set" defined: `cfg.get("template") or None` — falsy (empty string, None, whitespace) treated as no-template
- [x] #8 fix_structure() spec: calls load_config(rp), no-op without template, no-op unknown, parents=True, returns list
- [x] #9 fix_structure() tests: 5 dedicated tests in Task 3 Step 1
- [x] #10 "never moves files" test: `test_fix_structure_does_not_move_existing_files` with file at unexpected path
- [x] #11 Smoke test: fixture-based CLI tests for behavior; h2t-skills for no-crash + live
- [x] #12 Commit timing: Task 1 commit after function+tests; Task 2 commit after wiring; Task 3 after everything
- [x] #13 Import cycle: verified in Prerequisites section
- [x] #14 Finding format: uses existing `finding()` dict, `"template"` key added post-creation
- [x] #15 is_dir() collision: "path exists but is not a dir" message for file-at-dir-path
- [x] #16 CLI/doctor JSON test: `test_doctor_json_output_schema` and `test_doctor_json_typed_finding_has_template_field`
- [x] #17 JSON template field: `f["template"] = template` on finding dict — machine-readable, not only in message
- [x] #18 Template semantics: verified in Prerequisites (load_config on h2t-skills confirms code_repo)
- [x] #19 Import fail = stop: Prerequisites section has explicit stop instruction
- [x] #20 chaos workflow output: `_run_fix_safe` message covers "Renames/moves require manual action" (existing) — typed check doesn't change this; smoke test output shows live findings
