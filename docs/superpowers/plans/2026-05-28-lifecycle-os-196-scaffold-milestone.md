---
title: "Lifecycle OS #196 — scaffold/init + milestone-closure consolidation"
status: "draft"
date: "2026-05-28"
milestone: "lifecycle-os"
related:
  - "#196"
  - "docs/superpowers/specs/2026-05-28-lifecycle-os-harness-contract.md"
  - "docs/superpowers/plans/2026-05-27-scaffold-project-enhancement.md"
---

# Lifecycle OS #196 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Lifecycle OS #196 by making project scaffold/init work outside `C:/dev`, replacing stale milestone closure instructions with `gh api` + unified `docs-lint`, and writing structured reports for project init and milestone closure.

**Architecture:** This is a repair/continuation plan, not a greenfield rewrite. #240 already shipped unified `docs-lint`; #211 already shipped handoff GitHub state. Existing partial #196 code in `main` is kept where correct (`setup_h2t.py` latest link, sync-label helper, hook install), but fixed where it contradicts the harness contract: `docs-init` must accept explicit repo roots, `on-stop` must not use `gh milestone`, and `milestone-closure` must orchestrate `docs-lint plan/fix-index` instead of standalone `docs-index`.

**Tech Stack:** Python stdlib (`argparse`, `json`, `pathlib`, `subprocess`, `tempfile`, `datetime`), existing h2t-dev docs modules, pytest, GitHub CLI via `gh api`.

---

## Scope

In scope:

- `docs-init` script accepts `--repo-root` and optional project template.
- `scaffold-project` calls `docs-init --repo-root <project_dir>` for projects outside `DEV_ROOT`.
- `scaffold-project` writes a small machine-readable setup report.
- `on-stop` handler uses `gh api repos/{owner}/{repo}/milestones`, not `gh milestone list`.
- `milestone-closure` gains a deterministic script with dry-run, structured report, docs-lint integration, and explicit close confirmation.
- `milestone-closure` SKILL.md is updated to use the script and remove `docs-cleanup` / `docs-index` as mandatory steps.
- Dogfood verifies a temp repo outside `C:/dev` and a real dry-run milestone closure path.

Out of scope:

- #197 hooks rollout beyond repairing the existing `on-stop` handler.
- Scheduled `project-audit`.
- POS event emission. Reports must be POS-ingestable later, but no POS write is implemented in #196.
- Actual destructive milestone closing during dogfood.
- Automatic archive/move/delete of docs.

## Current State

Already implemented in `main`:

- `plugins/h2t-core/skills/setup/scripts/setup_h2t.py`
  - `_semver_key`
  - `create_latest_link`
  - `plugin-versions.json` fallback after `install-h2t-ops`
- `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
  - `run_docs_init`
  - `run_sync_labels`
  - `install_hooks`
- `plugins/h2t-core/hooks-handlers/on-stop`
- `tests/scaffold/test_scaffold_latest.py`
- `tests/scaffold/test_scaffold_steps.py`

Known defects to fix:

- `run_docs_init` skips all repos outside `DEV_ROOT`, directly contradicting #196.
- `docs-init/scripts/init.py` can only resolve `DEV_ROOT / repo_name`.
- `on-stop` uses `gh milestone list`, which is not a valid GitHub CLI command.
- `milestone-closure/SKILL.md` still calls `docs-cleanup` and standalone `docs-index`.
- There is no deterministic milestone closure report script.
- There is no machine-readable setup report from scaffold-project.

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t-dev/skills/docs-init/scripts/init.py` | Modify | Add `--repo-root`, template-aware config, keep old repo-name mode |
| `tests/docs/test_docs_init_repo_root.py` | Create | Verify docs-init works outside `DEV_ROOT` |
| `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py` | Modify | Call docs-init by repo root, add template mapping, write setup report |
| `tests/scaffold/test_scaffold_steps.py` | Modify | Replace DEV_ROOT skip tests with repo-root tests |
| `plugins/h2t-core/hooks-handlers/on-stop` | Modify | Replace invalid `gh milestone list` with `gh api` |
| `tests/scaffold/test_on_stop.py` | Create | Unit-test on-stop parsing and non-blocking behavior |
| `plugins/h2t-dev/skills/milestone-closure/scripts/closure.py` | Create | Deterministic dry-run/apply milestone closure backend |
| `tests/milestone/test_closure.py` | Create | Unit-test closure backend without live GitHub writes |
| `plugins/h2t-dev/skills/milestone-closure/SKILL.md` | Modify | Use closure.py + docs-lint plan/fix-index, remove docs-index/docs-cleanup mandatory flow |
| `plugins/h2t-dev/README.md` | Modify | Update lifecycle docs commands for docs-lint unified and milestone closure |
| `plugins/h2t-dev/CHANGELOG.md` | Modify | Record #196 behavior |
| `plugins/h2t-core/skills/scaffold-project/SKILL.md` | Modify | Remove DEV_ROOT-only warning; document templates and setup report |
| `plugins/h2t-core/.claude-plugin/plugin.json` | Modify | Patch bump after scaffold changes |

---

### Task 1: Add `--repo-root` and templates to docs-init

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-init/scripts/init.py`
- Create: `tests/docs/test_docs_init_repo_root.py`

- [ ] **Step 1: Write failing tests**

Create `tests/docs/test_docs_init_repo_root.py`:

```python
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-init/scripts"
sys.path.insert(0, str(_SCRIPT_DIR))

from init import init_repo


def test_init_repo_accepts_explicit_repo_root_outside_dev(tmp_path):
    repo = tmp_path / "client-project"
    repo.mkdir()

    changes = init_repo(
        "client-project",
        repo_root=repo,
        dry_run=False,
        commit=False,
        template="client_project",
    )

    assert changes is not None
    assert (repo / "docs" / "README.md").exists()
    assert (repo / ".claude" / "rules" / "documentation.md").exists()
    assert (repo / ".claude" / "rules" / "docs-lint.yaml").exists()


def test_init_repo_writes_docs_lint_template_config(tmp_path):
    repo = tmp_path / "research-project"
    repo.mkdir()

    init_repo(
        "research-project",
        repo_root=repo,
        dry_run=False,
        commit=False,
        template="research_project",
    )

    cfg = (repo / ".claude" / "rules" / "docs-lint.yaml").read_text(encoding="utf-8")
    assert "template: research_project" in cfg
    assert "docs_root: docs" in cfg


def test_init_repo_preserves_old_name_mode(monkeypatch, tmp_path):
    import init as init_mod

    repo = tmp_path / "h2t-example"
    repo.mkdir()
    monkeypatch.setattr(init_mod, "repo_path", lambda name: repo)

    changes = init_repo("h2t-example", dry_run=False, commit=False)

    assert changes is not None
    assert (repo / "docs" / "README.md").exists()


def test_init_repo_returns_none_when_explicit_root_missing(tmp_path):
    missing = tmp_path / "missing"
    assert init_repo("missing", repo_root=missing, dry_run=True) is None
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py -v
```

Expected: failure because `init_repo()` does not accept `repo_root` / `template`.

- [ ] **Step 3: Update docs-init constants**

In `plugins/h2t-dev/skills/docs-init/scripts/init.py`, add after `VALE_INI`:

```python
DOCS_LINT_CONFIG = """\
schema: h2t_docs_lint_config/v0.1
docs_root: docs
template: {template}
exceptions: []
"""

TEMPLATE_EXTRA_DIRS: dict[str, list[str]] = {
    "code_repo": [],
    "client_project": ["docs/ops", "docs/research", "docs/deliverables"],
    "research_project": ["docs/research", "docs/reports"],
    "creative_project": ["docs/briefs", "docs/assets", "docs/reviews"],
    "personal_os": ["docs/notes", "docs/sessions"],
    "ops_workflow": ["docs/runbooks", "docs/logs"],
}
```

- [ ] **Step 4: Change `init_repo` signature and root resolution**

Replace the function signature and first root block:

```python
def init_repo(
    name: str,
    *,
    repo_root: Path | None = None,
    dry_run: bool = True,
    commit: bool = False,
    template: str = "code_repo",
) -> list[str] | None:
    rp = repo_root.expanduser().resolve() if repo_root else repo_path(name)
    if not rp.exists():
        print(f"  ERROR: {rp} not found")
        return None
```

- [ ] **Step 5: Add template directories**

After required core dirs loop, add:

```python
    for rel_dir in TEMPLATE_EXTRA_DIRS.get(template, []):
        d = rp / rel_dir
        if not d.exists():
            if not dry_run:
                ensure_dir(d)
            print(f"  {action}: {rel_dir}/ (from template {template})")
            changes.append(rel_dir)
```

- [ ] **Step 6: Write docs-lint.yaml**

After `.claude/rules/documentation.md` handling, add:

```python
    docs_lint_cfg = rp / ".claude" / "rules" / "docs-lint.yaml"
    if not docs_lint_cfg.exists():
        if not dry_run:
            docs_lint_cfg.parent.mkdir(parents=True, exist_ok=True)
            docs_lint_cfg.write_text(
                DOCS_LINT_CONFIG.format(template=template),
                encoding="utf-8",
            )
        print(f"  {action}: .claude/rules/docs-lint.yaml")
        changes.append(".claude/rules/docs-lint.yaml")
```

- [ ] **Step 7: Add CLI flags**

In `main()`, add:

```python
    parser.add_argument("--repo-root", default=None, help="Explicit repo root path; bypasses DEV_ROOT/repo resolution")
    parser.add_argument("--template", default="code_repo", choices=[
        "code_repo", "client_project", "research_project",
        "creative_project", "personal_os", "ops_workflow",
    ])
```

Change the call:

```python
    changes = init_repo(
        args.repo,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        dry_run=not args.apply,
        commit=args.commit,
        template=args.template,
    )
```

- [ ] **Step 8: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py tests/docs/test_lint_checks.py -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add plugins/h2t-dev/skills/docs-init/scripts/init.py tests/docs/test_docs_init_repo_root.py
git commit -m "feat(docs-init): support explicit repo-root and lifecycle templates"
```

---

### Task 2: Make scaffold-project use repo-root docs-init and setup reports

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Modify: `tests/scaffold/test_scaffold_steps.py`

- [ ] **Step 1: Replace the obsolete skip test**

In `tests/scaffold/test_scaffold_steps.py`, replace `test_run_docs_init_skips_non_dev_root` with:

```python
def test_run_docs_init_passes_repo_root_for_non_dev_project(tmp_path, monkeypatch):
    """run_docs_init supports repos outside DEV_ROOT via --repo-root."""
    import scaffold_project

    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path / "dev")
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "work" / "my-repo"
    project_dir.mkdir(parents=True)

    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_docs_init("my-repo", project_dir, template="client_project")

    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert result["status"] == "ok"
    assert "--repo-root" in cmd
    assert str(project_dir) in cmd
    assert "--template" in cmd
    assert "client_project" in cmd
```

- [ ] **Step 2: Add setup report tests**

Append to `tests/scaffold/test_scaffold_steps.py`:

```python
from scaffold_project import write_setup_report, template_for_type


def test_template_for_type_maps_client_docs():
    assert template_for_type("docs") == "research_project"
    assert template_for_type("code-github") == "code_repo"


def test_write_setup_report_creates_machine_readable_file(tmp_path):
    report = write_setup_report(
        project_dir=tmp_path,
        project_id="example",
        template="client_project",
        status="ok",
        actions=["created docs"],
    )

    assert report["schema"] == "h2t_project_setup_report/v0.1"
    report_path = tmp_path / ".h2t" / "project-setup-report.json"
    assert report_path.exists()
    assert "client_project" in report_path.read_text(encoding="utf-8")
```

- [ ] **Step 3: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_scaffold_steps.py -v
```

Expected: failures for `template` arg and missing report helpers.

- [ ] **Step 4: Add template mapping and setup report helper**

In `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`, add after `DIR_STRUCTURE`:

```python
TYPE_TO_TEMPLATE = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}


def template_for_type(project_type: str) -> str:
    return TYPE_TO_TEMPLATE.get(project_type, "code_repo")


def write_setup_report(
    *,
    project_dir: Path,
    project_id: str,
    template: str,
    status: str,
    actions: list[str],
) -> dict:
    import datetime

    report = {
        "schema": "h2t_project_setup_report/v0.1",
        "schema_version": "0.1",
        "producer": "h2t-core/scaffold-project",
        "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
        "project_id": project_id,
        "template": template,
        "repo_root": str(project_dir),
        "status": status,
        "actions": actions,
        "safe_next_action": "Run h2t-core:session-start in the project directory",
        "evidence": {
            "project_dir_exists": project_dir.exists(),
        },
    }
    out = project_dir / ".h2t" / "project-setup-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return report
```

- [ ] **Step 5: Replace `run_docs_init` implementation**

Replace `run_docs_init` with:

```python
def run_docs_init(repo_name: str, project_dir: Path, *, template: str = "code_repo") -> dict:
    init_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-init" / "scripts" / "init.py"
    if not init_script.exists():
        return {"status": "skip", "reason": "docs-init script not found"}
    r = subprocess.run(
        [
            sys.executable,
            str(init_script),
            repo_name,
            "--repo-root",
            str(project_dir),
            "--template",
            template,
            "--apply",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()[:400]}
    return {"status": "error", "error": r.stderr.strip()[:400] or r.stdout.strip()[:400]}
```

- [ ] **Step 6: Wire template and setup report in `cmd_create`**

Inside `cmd_create`, after `type_base`:

```python
    template = template_for_type(args.type)
```

Change docs-init call:

```python
        di = run_docs_init(args.id, project_dir, template=template)
```

Before returning `ok`, write setup report:

```python
    if not args.dry_run:
        report = write_setup_report(
            project_dir=project_dir,
            project_id=args.id,
            template=template,
            status="ok",
            actions=actions,
        )
        actions.append(f"setup-report: {project_dir / '.h2t' / 'project-setup-report.json'}")

    return {"status": "ok", "path": str(project_dir), "actions": actions}
```

- [ ] **Step 7: Run scaffold tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/ -v
```

Expected: all scaffold tests pass.

- [ ] **Step 8: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py tests/scaffold/test_scaffold_steps.py
git commit -m "feat(scaffold-project): run docs-init by repo-root and write setup report"
```

---

### Task 3: Replace on-stop `gh milestone` with `gh api`

**Files:**
- Modify: `plugins/h2t-core/hooks-handlers/on-stop`
- Create: `tests/scaffold/test_on_stop.py`

- [ ] **Step 1: Write tests**

Create `tests/scaffold/test_on_stop.py`:

```python
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_on_stop():
    path = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers/on-stop"
    spec = importlib.util.spec_from_file_location("h2t_on_stop", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_slug_uses_gh_repo_view():
    mod = _load_on_stop()
    with patch.object(mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="lichtpfad/h2t-skills\n", stderr="")
        assert mod._resolve_repo_slug() == "lichtpfad/h2t-skills"
    assert mock_run.call_args[0][0][:3] == ["gh", "repo", "view"]


def test_closed_milestones_uses_gh_api():
    mod = _load_on_stop()
    payload = '[{"title":"M1","open_issues":0},{"title":"M2","open_issues":2}]'
    with patch.object(mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        assert mod._closed_ready_milestones("lichtpfad/h2t-skills") == ["M1"]
    cmd = mock_run.call_args[0][0]
    assert cmd[:2] == ["gh", "api"]
    assert "repos/lichtpfad/h2t-skills/milestones" in cmd


def test_check_milestones_never_raises_on_gh_error(capsys):
    mod = _load_on_stop()
    with patch.object(mod, "_resolve_repo_slug", side_effect=RuntimeError("boom")):
        mod._check_milestones()
    assert capsys.readouterr().out == ""
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_on_stop.py -v
```

Expected: failure because helper functions do not exist.

- [ ] **Step 3: Replace on-stop content**

Replace `plugins/h2t-core/hooks-handlers/on-stop` with:

```python
#!/usr/bin/env python3
"""Stop hook: suggest milestone-closure when an open milestone has no open issues."""
import json
import subprocess
import sys


def _resolve_repo_slug() -> str:
    r = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def _closed_ready_milestones(repo_slug: str) -> list[str]:
    if not repo_slug:
        return []
    r = subprocess.run(
        ["gh", "api", f"repos/{repo_slug}/milestones", "-f", "state=open"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        milestones = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    return [
        str(m["title"])
        for m in milestones
        if int(m.get("open_issues", 0)) == 0
    ]


def _check_milestones() -> None:
    try:
        repo_slug = _resolve_repo_slug()
        for title in _closed_ready_milestones(repo_slug):
            print(
                f"[h2t] Milestone '{title}' has no open issues -- "
                "consider /h2t-dev:milestone-closure"
            )
    except Exception:
        return


if __name__ == "__main__":
    _check_milestones()
    sys.exit(0)
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/scaffold/test_on_stop.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/on-stop tests/scaffold/test_on_stop.py
git commit -m "fix(h2t-core): use gh api in on-stop milestone suggestion"
```

---

### Task 4: Add milestone-closure deterministic backend

**Files:**
- Create: `plugins/h2t-dev/skills/milestone-closure/scripts/closure.py`
- Create: `tests/milestone/test_closure.py`

- [ ] **Step 1: Write tests**

Create `tests/milestone/test_closure.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/milestone-closure/scripts"
sys.path.insert(0, str(_SCRIPT_DIR))

from closure import (
    build_report,
    fetch_next_open_items,
    find_milestone,
    milestone_status,
    run_docs_lint_plan,
)


def test_find_milestone_by_title():
    milestones = [
        {"number": 1, "title": "M1", "open_issues": 0, "closed_issues": 3},
        {"number": 2, "title": "M2", "open_issues": 1, "closed_issues": 4},
    ]
    assert find_milestone(milestones, "M2")["number"] == 2


def test_find_milestone_by_number_string():
    milestones = [{"number": 7, "title": "skills-release", "open_issues": 0}]
    assert find_milestone(milestones, "7")["title"] == "skills-release"


def test_milestone_status_blocked_when_open_issues():
    milestone = {"title": "M2", "open_issues": 2, "closed_issues": 5}
    assert milestone_status(milestone) == "blocked"


def test_milestone_status_ready_when_zero_open_issues():
    milestone = {"title": "M2", "open_issues": 0, "closed_issues": 5}
    assert milestone_status(milestone) == "ready"


def test_run_docs_lint_plan_uses_unified_docs_lint(tmp_path):
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="plan ok", stderr="")
        result = run_docs_lint_plan(tmp_path, python="python")
    assert result["status"] == "ok"
    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert "docs-lint" in " ".join(cmd)
    assert "plan" in cmd
    assert "--root" in cmd
    assert str(tmp_path) in cmd


def test_build_report_has_contract_fields(tmp_path):
    report = build_report(
        repo="lichtpfad/h2t-skills",
        repo_root=tmp_path,
        milestone={"number": 1, "title": "M1", "open_issues": 0, "closed_issues": 3},
        status="ready",
        docs_lint={"status": "ok"},
        safe_next_action="Review docs-lint plan",
    )
    assert report["schema"] == "h2t_milestone_closure_report/v0.1"
    assert report["producer"] == "h2t-dev/milestone-closure"
    assert report["milestone"]["title"] == "M1"


def test_fetch_next_open_items_uses_real_github_issues():
    payload = '[{"number":196,"title":"Project Lifecycle OS","labels":[{"name":"priority:p1"}]}]'
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        items = fetch_next_open_items("lichtpfad/h2t-skills", limit=3)
    assert items[0]["number"] == 196
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["gh", "issue", "list"]
    assert "--state" in cmd
    assert "open" in cmd
```

- [ ] **Step 2: Run tests and verify failure**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/milestone/test_closure.py -v
```

Expected: import failure because `closure.py` does not exist.

- [ ] **Step 3: Create closure.py**

Create `plugins/h2t-dev/skills/milestone-closure/scripts/closure.py`:

```python
#!/usr/bin/env python3
"""Deterministic milestone closure backend for h2t-dev."""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "h2t_milestone_closure_report/v0.1"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def resolve_repo(repo_arg: str | None) -> str:
    if repo_arg:
        return repo_arg
    r = _run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh repo view failed")
    return r.stdout.strip()


def fetch_milestones(repo: str) -> list[dict]:
    r = _run(["gh", "api", f"repos/{repo}/milestones", "-f", "state=all"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh api milestones failed")
    return json.loads(r.stdout or "[]")


def find_milestone(milestones: list[dict], selector: str) -> dict:
    for milestone in milestones:
        if str(milestone.get("number")) == selector or milestone.get("title") == selector:
            return milestone
    raise ValueError(f"milestone not found: {selector}")


def milestone_status(milestone: dict) -> str:
    return "blocked" if int(milestone.get("open_issues", 0)) > 0 else "ready"


def run_docs_lint_plan(repo_root: Path, *, python: str = sys.executable) -> dict:
    lint = Path(__file__).resolve().parents[2] / "docs-lint" / "scripts" / "lint.py"
    r = _run([python, str(lint), "plan", "--root", str(repo_root)])
    return {
        "status": "ok" if r.returncode == 0 else "error",
        "exit_code": r.returncode,
        "stdout": r.stdout[-4000:],
        "stderr": r.stderr[-2000:],
    }


def fetch_next_open_items(repo: str, *, limit: int = 5) -> list[dict]:
    r = _run([
        "gh", "issue", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", str(limit),
        "--json", "number,title,labels,milestone",
    ])
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def close_milestone(repo: str, milestone: dict, *, confirm_title: str) -> dict:
    title = str(milestone.get("title", ""))
    if confirm_title.strip() != title:
        return {
            "status": "error",
            "error": f"confirmation mismatch: expected {title!r}, got {confirm_title!r}",
        }
    r = _run([
        "gh", "api", f"repos/{repo}/milestones/{milestone['number']}",
        "-X", "PATCH", "-f", "state=closed",
    ])
    return {
        "status": "ok" if r.returncode == 0 else "error",
        "exit_code": r.returncode,
        "stdout": r.stdout[-1000:],
        "stderr": r.stderr[-1000:],
    }


def build_report(
    *,
    repo: str,
    repo_root: Path,
    milestone: dict,
    status: str,
    docs_lint: dict,
    safe_next_action: str,
    next_open_items: list[dict] | None = None,
    close_result: dict | None = None,
) -> dict:
    return {
        "schema": SCHEMA,
        "schema_version": "0.1",
        "producer": "h2t-dev/milestone-closure",
        "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
        "repo": repo,
        "repo_root": str(repo_root),
        "status": status,
        "milestone": {
            "number": milestone.get("number"),
            "title": milestone.get("title"),
            "open_issues": milestone.get("open_issues", 0),
            "closed_issues": milestone.get("closed_issues", 0),
            "state": milestone.get("state"),
        },
        "docs_lint": docs_lint,
        "next_open_items": next_open_items or [],
        "safe_next_action": safe_next_action,
        "close_result": close_result,
    }


def write_report(repo_root: Path, report: dict) -> Path:
    out_dir = repo_root / ".h2t" / "lifecycle"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = str(report["milestone"]["title"]).lower().replace(" ", "-")
    out = out_dir / f"milestone-closure-{safe_title}.json"
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None, help="owner/repo; defaults to gh repo view")
    parser.add_argument("--repo-root", default=".", help="local repo root")
    parser.add_argument("--milestone", required=True, help="milestone title or API number")
    parser.add_argument("--close", action="store_true", help="close GitHub milestone after checks")
    parser.add_argument("--confirm-title", default="", help="required with --close")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve()
    try:
        repo = resolve_repo(args.repo)
        milestone = find_milestone(fetch_milestones(repo), args.milestone)
        status = milestone_status(milestone)
        docs_lint = run_docs_lint_plan(repo_root)
        next_open_items = fetch_next_open_items(repo)
        close_result = None
        safe_next = "Review docs-lint plan before any archive/move; run docs-lint fix-index after approved cleanup"
        if status == "blocked":
            safe_next = "Resolve or move open milestone issues before closure"
        elif args.close:
            close_result = close_milestone(repo, milestone, confirm_title=args.confirm_title)
            status = "closed" if close_result["status"] == "ok" else "partial"
            safe_next = "Write handoff / release report"
        report = build_report(
            repo=repo,
            repo_root=repo_root,
            milestone=milestone,
            status=status,
            docs_lint=docs_lint,
            next_open_items=next_open_items,
            safe_next_action=safe_next,
            close_result=close_result,
        )
        report_path = write_report(repo_root, report)
        report["refs"] = [{"type": "report_json", "uri": str(report_path)}]
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "schema_version": "0.1",
            "producer": "h2t-dev/milestone-closure",
            "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(exc),
            "safe_next_action": "Fix milestone closure error and rerun dry-run",
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") not in {"error", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/milestone/test_closure.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-dev/skills/milestone-closure/scripts/closure.py tests/milestone/test_closure.py
git commit -m "feat(milestone-closure): add gh-api dry-run backend with docs-lint plan"
```

---

### Task 5: Update milestone-closure SKILL.md to current contract

**Files:**
- Modify: `plugins/h2t-dev/skills/milestone-closure/SKILL.md`

- [ ] **Step 1: Replace procedure with closure.py workflow**

Rewrite `plugins/h2t-dev/skills/milestone-closure/SKILL.md` body after frontmatter:

```markdown
# Milestone Closure

Close a GitHub milestone as a Lifecycle OS phase boundary.

This skill is a thin orchestrator. Deterministic state is gathered by
`skills/milestone-closure/scripts/closure.py`.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
CLOSURE="$CLAUDE_PLUGIN_ROOT/skills/milestone-closure/scripts/closure.py"
```

## Procedure

### Step 1: Identify milestone

Ask the user for the milestone title or GitHub milestone API number if it is not
already explicit.

### Step 2: Dry-run closure report

```bash
$H2T_PYTHON "$CLOSURE" --repo-root "$(pwd)" --milestone "{milestone}" --json
```

Read the JSON:

- If `status == "blocked"`: show open-issue count and stop.
- If `status == "error"`: show error and stop.
- If `docs_lint.status != "ok"`: summarize docs-lint plan and ask what to do.

### Step 3: Documentation gate

Run docs cleanup manually through unified docs-lint:

```bash
$H2T_PYTHON "$CLAUDE_PLUGIN_ROOT/skills/docs-lint/scripts/lint.py" plan --root "$(pwd)"
$H2T_PYTHON "$CLAUDE_PLUGIN_ROOT/skills/docs-lint/scripts/lint.py" fix-index --root "$(pwd)"
```

`fix-index` without `--apply` is dry-run. Ask before using `--apply`.

Do not call standalone `docs-index`. It is no longer user-facing.
Do not archive, move, delete, or rename files without explicit user approval.

### Step 4: Close milestone only with confirmation

Ask the user to confirm the exact milestone title.

```bash
$H2T_PYTHON "$CLOSURE" --repo-root "$(pwd)" --milestone "{milestone}" --close --confirm-title "{exact title}" --json
```

### Step 5: Report outcome

Show:

- report JSON path from `refs`;
- milestone status;
- docs-lint summary;
- `next_open_items` from real GitHub state if available.

## Checklist

- [ ] Dry-run closure report generated
- [ ] Open issue count is zero or explicitly handled
- [ ] docs-lint plan reviewed
- [ ] docs-lint fix-index dry-run reviewed
- [ ] Any write/destructive step explicitly confirmed
- [ ] GitHub milestone closed only after exact-title confirmation
- [ ] Next open items reviewed from closure report
```

- [ ] **Step 2: Verify old forbidden references are gone**

```bash
rg -n "docs-index|docs-cleanup|gh milestone" plugins/h2t-dev/skills/milestone-closure/SKILL.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-dev/skills/milestone-closure/SKILL.md
git commit -m "docs(milestone-closure): use closure backend and unified docs-lint flow"
```

---

### Task 6: Update scaffold-project skill documentation

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/SKILL.md`
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`

- [ ] **Step 1: Update description**

In `plugins/h2t-core/skills/scaffold-project/SKILL.md`, replace the description block with:

```yaml
description: >
  Create and register a new project in h2t ecosystem via interactive wizard.
  Triggers on "/scaffold-project", "scaffold", "новый проект", "new project".
  After creation: calls docs-init with explicit --repo-root, writes docs-lint
  template config, writes a machine-readable setup report, installs on-stop
  hook into .claude/settings.json. After GitHub creation: syncs labels via
  docs-sync-labels. NOT for registering existing repos (use
  /h2t-core:init-project for that).
```

- [ ] **Step 2: Remove DEV_ROOT-only wording**

Find the current line:

```text
After creation: calls docs-init to scaffold docs/ structure (DEV_ROOT projects only),
```

Ensure no remaining `DEV_ROOT projects only` wording exists:

```bash
rg -n "DEV_ROOT projects only|C:/dev only|project not under DEV_ROOT" plugins/h2t-core/skills/scaffold-project plugins/h2t-core/skills/scaffold-project/scripts
```

Expected: no matches except tests that assert the old behavior has been removed.

- [ ] **Step 3: Bump h2t-core patch version**

Update `plugins/h2t-core/.claude-plugin/plugin.json`:

```json
"version": "3.2.2"
```

Do not bump minor; this still needs live confirmation.

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/SKILL.md plugins/h2t-core/.claude-plugin/plugin.json
git commit -m "docs(scaffold-project): document repo-root lifecycle setup flow"
```

---

### Task 7: Update h2t-dev docs and version metadata

**Files:**
- Modify: `plugins/h2t-dev/README.md`
- Modify: `plugins/h2t-dev/CHANGELOG.md`
- Modify: `plugins/h2t-dev/.claude-plugin/plugin.json` if present

- [ ] **Step 1: Update README docs-lint examples**

In `plugins/h2t-dev/README.md`, replace legacy docs-lint examples:

```text
docs-lint                    # Check all repos
docs-lint h2t-graphs h2t-ai # Check specific repos
docs-lint --fix              # Create missing dirs
```

with:

```text
docs-lint audit --root .           # Show docs health findings
docs-lint plan --root .            # Show cleanup plan
docs-lint fix-safe --root .        # Apply safe mechanical fixes only
docs-lint fix-index --root .       # Dry-run README/navigation rebuild
docs-lint doctor --root . --json   # Machine-readable report
```

- [ ] **Step 2: Update milestone closure README section**

Replace any instruction that says `docs-index` or `docs-cleanup` is mandatory with:

```text
milestone-closure uses closure.py for GitHub state and calls unified docs-lint:
docs-lint plan before cleanup decisions, docs-lint fix-index after approved cleanup.
Standalone docs-index is deprecated as a user-facing flow.
```

- [ ] **Step 3: Add CHANGELOG entry**

At top of `plugins/h2t-dev/CHANGELOG.md`, add:

```markdown
## Unreleased

- feat(milestone-closure): add gh-api dry-run backend and structured closure report
- docs(milestone-closure): replace standalone docs-index/docs-cleanup flow with unified docs-lint
```

- [ ] **Step 4: Patch bump h2t-dev metadata if plugin file exists**

If `plugins/h2t-dev/.claude-plugin/plugin.json` exists, bump patch only.

Command:

```bash
if [ -f plugins/h2t-dev/.claude-plugin/plugin.json ]; then git diff -- plugins/h2t-dev/.claude-plugin/plugin.json; fi
```

On Windows PowerShell equivalent:

```powershell
if (Test-Path plugins/h2t-dev/.claude-plugin/plugin.json) { git diff -- plugins/h2t-dev/.claude-plugin/plugin.json }
```

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-dev/README.md plugins/h2t-dev/CHANGELOG.md plugins/h2t-dev/.claude-plugin/plugin.json
git commit -m "docs(h2t-dev): document milestone closure over unified docs-lint"
```

If `plugins/h2t-dev/.claude-plugin/plugin.json` does not exist, omit it from `git add`.

---

### Task 8: Dogfood acceptance

**Files:**
- No source files unless fixes are needed.

- [ ] **Step 1: Run targeted tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_docs_init_repo_root.py tests/scaffold/ tests/milestone/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Run full docs tests**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Dogfood docs-init outside C:/dev**

Use a temp path, not a real client repo:

```powershell
$root = "C:/tmp/h2t-lifecycle-dogfood-repo"
Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $root | Out-Null
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-dev/skills/docs-init/scripts/init.py lifecycle-dogfood --repo-root $root --template client_project --apply
Test-Path "$root/docs/README.md"
Test-Path "$root/.claude/rules/docs-lint.yaml"
```

Expected: both `Test-Path` commands return `True`.

- [ ] **Step 4: Dogfood scaffold dry-run outside C:/dev**

```powershell
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py create --id lifecycle-dogfood --type docs --stack none --dir C:/tmp --description "Lifecycle dogfood" --dry-run
```

Expected: JSON status `dry-run`, no writes.

- [ ] **Step 5: Dogfood milestone closure dry-run**

Run against h2t-skills with a known milestone title or API number. Do not pass `--close`.

```powershell
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-dev/skills/milestone-closure/scripts/closure.py --repo lichtpfad/h2t-skills --repo-root C:/dev/h2t-skills --milestone "lifecycle-os" --json
```

If no `lifecycle-os` milestone exists, rerun with an existing open milestone and record the output. Expected:

- JSON parses;
- `schema` is `h2t_milestone_closure_report/v0.1`;
- no GitHub state is changed;
- `docs_lint` field exists.
- `next_open_items` exists, even if empty.

- [ ] **Step 6: Verify forbidden strings**

```bash
rg -n "gh milestone list|docs-index/scripts/index.py|docs-cleanup/scripts/cleanup.py" plugins/h2t-core plugins/h2t-dev/skills/milestone-closure
```

Expected: no matches in active milestone/scaffold flow.

- [ ] **Step 7: Commit acceptance evidence**

```bash
git commit --allow-empty -m "test(lifecycle): dogfood #196 scaffold and milestone closure flow"
```

---

## Checklist Summary

- [ ] Task 1: `docs-init --repo-root` and template config
- [ ] Task 2: `scaffold-project` repo-root docs-init and setup report
- [ ] Task 3: `on-stop` uses `gh api`, not `gh milestone`
- [ ] Task 4: milestone closure deterministic backend
- [ ] Task 5: milestone-closure SKILL.md updated to unified docs-lint flow
- [ ] Task 6: scaffold-project skill docs updated
- [ ] Task 7: h2t-dev README/CHANGELOG updated
- [ ] Task 8: dogfood acceptance on temp repo + h2t-skills dry-run

## Self-Review

Spec coverage:

- Project Init outside `DEV_ROOT`: Tasks 1-2.
- docs-init/docs-sync-labels absorption: Task 2 preserves sync-labels and fixes docs-init root handling.
- Project registry entry: existing `scaffold-project` skill still calls `apply_registration.py`; this plan does not duplicate registration logic in the scaffold script. The setup report records scaffold state; registry remains owned by `init-project/apply_registration.py`.
- `setup_h2t.py latest/`: already implemented in `main`; not repeated.
- Milestone closure with `gh api`: Tasks 3-5.
- `docs-lint plan` before cleanup and `fix-index` after approved cleanup: Tasks 4-5.
- Structured closure report: Task 4.
- Select next real open item: Task 4 adds `next_open_items` from live `gh issue list`.

Known deliberate deferrals:

- POS event emission.
- Automatic docs archive/move/delete.
- Scheduled project-audit.
- Full lifecycle-native plan registry.

---

## Plan Review Amendments (from /plan-eng-review 2026-05-28)

The following amendments were accepted during engineering review and MUST be applied by the agentic executor:

### Amendment A1 (D1): Extend docs-init to all project types

**Task 2 Step 6 update — replace is_git guard:**

The original plan shows `run_docs_init` inside `if is_git and not args.dry_run:`. This is incorrect after D1 decision. The executor MUST change this to:

```python
if not args.dry_run:
    di = run_docs_init(args.id, project_dir, template=template)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di['error']}"}

if is_git and not args.dry_run:
    ih = install_hooks(project_dir)
    actions.append(f"install-hooks: {ih['status']}")
```

`install_hooks` remains under `is_git` guard (deferred to #197).

**Task 2 Step 1 test update — add non-git type test:**

Add to `test_scaffold_steps.py`:
```python
def test_run_docs_init_passes_repo_root_for_docs_type(tmp_path, monkeypatch):
    """docs-type project (not is_git) also gets docs-init via --repo-root."""
    import scaffold_project
    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "my-docs"
    project_dir.mkdir()
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_docs_init("my-docs", project_dir, template="research_project")
    assert result["status"] == "ok"
    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert "--repo-root" in cmd
    assert "--template" in cmd
    assert "research_project" in cmd
```

**Task 8 Step 4 update — test without --dry-run for docs type:**

Replace dogfood Step 4 with:
```powershell
# Test type=docs WITHOUT --dry-run to verify docs-init runs for non-git types
C:/dev/h2t-skills/.venv/Scripts/python.exe plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py create --id lifecycle-dogfood-docs --type docs --stack none --dir C:/tmp --description "Lifecycle dogfood docs type"
Test-Path "C:/tmp/lifecycle-dogfood-docs/docs/README.md"
Test-Path "C:/tmp/lifecycle-dogfood-docs/.claude/rules/docs-lint.yaml"
```
Expected: both `Test-Path` return `True`.

### Amendment A2 (D5): Add safety guard in docs-init

**Task 1 Step 4 update — add repo_root safety check:**

In `init_repo`, immediately after resolving `rp`, add:
```python
# Guard against accidental writes to system paths
_HOME = Path.home().resolve()
_DANGER = (
    rp == _HOME
    or rp == _HOME.parent
    or len(rp.parts) <= 1
    or (len(rp.parts) == 2 and rp.drive and rp.parts[1] == "\\")  # Windows root C:\
)
if _DANGER:
    print(f"  ERROR: {rp} is a system path — pass a project subdirectory")
    return None
```

**Add test for safety guard to `tests/docs/test_docs_init_repo_root.py`:**
```python
def test_init_repo_rejects_home_directory(monkeypatch, tmp_path):
    from pathlib import Path
    import init as init_mod
    # Temporarily treat tmp_path as "home" for testing purposes
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    result = init_repo("home", repo_root=tmp_path, dry_run=True)
    assert result is None
```

### Amendment A3 (D3): Add close_milestone tests

**Task 4 Step 1 update — add to `tests/milestone/test_closure.py`:**
```python
def test_close_milestone_refuses_on_title_mismatch():
    from closure import close_milestone
    milestone = {"number": 7, "title": "lifecycle-os", "open_issues": 0}
    with patch("closure.subprocess.run") as mock_run:
        result = close_milestone("owner/repo", milestone, confirm_title="wrong-title")
    assert result["status"] == "error"
    mock_run.assert_not_called()


def test_close_milestone_calls_gh_api_patch():
    from closure import close_milestone
    milestone = {"number": 7, "title": "lifecycle-os", "open_issues": 0}
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = close_milestone("owner/repo", milestone, confirm_title="lifecycle-os")
    assert result["status"] == "ok"
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "gh"
    assert cmd[1] == "api"
    assert "PATCH" in cmd
```

### Amendment A4 (D4): Create tests/milestone/__init__.py

**Task 4 Step 3 update — add step:**

Before creating `test_closure.py`, create an empty `tests/milestone/__init__.py`:
```bash
mkdir -p tests/milestone
touch tests/milestone/__init__.py
```
Add to `git add`:
```bash
git add tests/milestone/__init__.py
```

---

## Implementation Tasks (from /plan-eng-review)

Synthesized from review findings. Each task derives from a specific finding.

- [ ] **T1 (P1, human: ~30min / CC: ~5min)** — docs-init — Add safety guard for repo_root
  - Surfaced by: Outside Voice D5 — init_repo can write to C:/ or ~ with no guard
  - Files: `plugins/h2t-dev/skills/docs-init/scripts/init.py`, `tests/docs/test_docs_init_repo_root.py`
  - Verify: new test `test_init_repo_rejects_home_directory` passes; safety guard blocks `~` / `C:\`

- [ ] **T2 (P1, human: ~20min / CC: ~5min)** — scaffold-project — Remove is_git guard before run_docs_init
  - Surfaced by: Code Quality D2 — D1 decision requires extending docs-init to all non-dry-run types
  - Files: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`, `tests/scaffold/test_scaffold_steps.py`
  - Verify: `pytest tests/scaffold/` — docs-type projects now call docs-init

- [ ] **T3 (P2, human: ~15min / CC: ~3min)** — milestone-closure — Add close_milestone confirmation tests
  - Surfaced by: Test Review D3 — GitHub-writing function has no unit test for confirmation mechanism
  - Files: `tests/milestone/test_closure.py`
  - Verify: `test_close_milestone_refuses_on_title_mismatch` + `test_close_milestone_calls_gh_api_patch` pass

- [ ] **T4 (P2, human: ~1min / CC: ~1min)** — test-infra — Create tests/milestone/__init__.py
  - Surfaced by: Test Review D4 — missing pytest module boundary breaks CI in some configs
  - Files: `tests/milestone/__init__.py`
  - Verify: `pytest tests/milestone/ -v` runs without import errors

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 4 cross-model findings, 2 acted on (D5: guard, T1), 2 deferred to TODO |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 5 issues (D1-D5), 4 P1-P2 amendments added to plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** Safety guard for `--repo-root` (D5/T1 added), template validation → TODOS.md, pagination → TODOS.md
- **CROSS-MODEL:** D5 — Codex found safety gap I missed; user accepted adding guard in #196
- **UNRESOLVED:** 0
- **VERDICT:** ENG REVIEW — 4 amendments in plan (A1-A4). Implement T1-T4 before dogfood acceptance.
