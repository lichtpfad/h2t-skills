---
title: "docs-lint Unified Contract Implementation Plan"
status: "draft"
date: "2026-05-28"
milestone: "lifecycle-os"
issue: ""
---

# docs-lint Unified Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign docs-lint to report documentation health in navigation → naming → structure → metadata order, with 5 operational modes, machine-readable envelope, and orphan detection.

**Architecture:** New checks extracted into focused `lib/docs/` modules (reporter.py, orphan.py, naming.py, config.py, index_builder.py). Existing `lint.py` becomes thin orchestrator with sub-command CLI. Legacy `--fix`/`--fix-frontmatter` flags preserved with deprecation warnings. `docs-index` role absorbed by `fix-index` mode.

**Tech Stack:** Python stdlib (pathlib, re, json, os, collections.deque, tempfile, argparse); existing `lib/docs/common.py`; pytest with `tmp_path` fixtures.

---

## File Structure

**New files:**
- `plugins/h2t-dev/lib/docs/reporter.py` — `h2t_lifecycle_report/v0.1` envelope builder
- `plugins/h2t-dev/lib/docs/fix_plan.py` — converts findings → `h2t_docs_fix_plan/v0.1` action list
- `plugins/h2t-dev/lib/docs/apply_report.py` — writes `h2t_docs_fix_apply_report/v0.1` after fix runs
- `plugins/h2t-dev/lib/docs/orphan.py` — BFS orphan detection from docs/README.md
- `plugins/h2t-dev/lib/docs/naming.py` — extended naming checks across all docs/
- `plugins/h2t-dev/lib/docs/config.py` — `.claude/rules/docs-lint.yaml` discovery
- `plugins/h2t-dev/lib/docs/index_builder.py` — marker-based index with bootstrap
- `tests/docs/test_reporter.py`
- `tests/docs/test_fix_plan.py`
- `tests/docs/test_orphan.py`
- `tests/docs/test_naming_extended.py`
- `tests/docs/test_config.py`
- `tests/docs/test_fix_index.py`

**Modified files:**
- `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` — new CLI sub-commands, `--root PATH`, backward compat
- `plugins/h2t-dev/skills/docs-lint/SKILL.md` — update to new contract

---

### Task 1: reporter.py — JSON envelope builder

**Files:**
- Create: `plugins/h2t-dev/lib/docs/reporter.py`
- Create: `tests/docs/test_reporter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_reporter.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.reporter import build_report, finding, status_from_findings, SCHEMA


def test_build_report_schema():
    r = build_report(
        command="docs-lint",
        repo_root="/tmp/repo",
        status="ok",
        summary="no issues",
        findings=[],
        safe_next_action="nothing",
    )
    assert r["schema"] == SCHEMA
    assert r["schema_version"] == "0.1"
    assert r["command"] == "docs-lint"


def test_build_report_evidence_has_checked_at():
    r = build_report(
        command="docs-lint",
        repo_root="/tmp/repo",
        status="ok",
        summary="",
        findings=[],
        safe_next_action="",
    )
    assert "checked_at" in r["evidence"]
    assert r["evidence"]["checked_at"].endswith("Z")


def test_finding_no_safe_fix():
    f = finding("orphan", "warn", "docs/old.md", "not reachable")
    assert "safe_fix" not in f
    assert f["type"] == "orphan"
    assert f["severity"] == "warn"
    assert f["path"] == "docs/old.md"


def test_finding_with_safe_fix():
    f = finding("frontmatter", "info", "docs/foo.md", "missing title",
                safe_fix="add frontmatter")
    assert f["safe_fix"] == "add frontmatter"


def test_status_from_findings_empty():
    assert status_from_findings([]) == "ok"


def test_status_from_findings_warn():
    assert status_from_findings([finding("orphan", "warn", "x.md", "msg")]) == "warn"


def test_status_from_findings_critical():
    assert status_from_findings(
        [finding("error", "critical", "x.md", "msg")]
    ) == "fail"


def test_status_from_findings_error():
    assert status_from_findings(
        [finding("broken", "error", "x.md", "msg")]
    ) == "fail"
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.reporter'`

- [ ] **Step 3: Implement reporter.py**

```python
# plugins/h2t-dev/lib/docs/reporter.py
"""h2t_lifecycle_report/v0.1 envelope builder."""
from __future__ import annotations
import datetime

SCHEMA = "h2t_lifecycle_report/v0.1"
SCHEMA_VERSION = "0.1"


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
    }
    if safe_fix is not None:
        result["safe_fix"] = safe_fix
    return result


def build_report(
    *,
    command: str,
    repo_root: str,
    status: str,
    summary: str,
    findings: list[dict],
    safe_next_action: str,
    git_head: str = "",
) -> dict:
    """Build a complete h2t_lifecycle_report/v0.1 envelope."""
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "repo_root": repo_root,
        "status": status,
        "summary": summary,
        "findings": findings,
        "safe_next_action": safe_next_action,
        "evidence": {
            "git_head": git_head,
            "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
    }


def status_from_findings(findings: list[dict]) -> str:
    """Derive status from severity of findings list."""
    if not findings:
        return "ok"
    severities = {f["severity"] for f in findings}
    if severities & {"error", "critical"}:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "ok"
```

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_reporter.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/reporter.py tests/docs/test_reporter.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add reporter.py — h2t_lifecycle_report/v0.1 envelope builder"
```

---

### Task 1.5: fix_plan.py + apply_report.py — execution tracking schemas

Converts findings into a deterministic, stable action list (`h2t_docs_fix_plan/v0.1`) and records
what was applied, skipped, failed, or waived (`h2t_docs_fix_apply_report/v0.1`).
This is the audit trail layer that makes fix runs reproducible and comparable across runs.

**Files:**
- Create: `plugins/h2t-dev/lib/docs/fix_plan.py`
- Create: `plugins/h2t-dev/lib/docs/apply_report.py`
- Create: `tests/docs/test_fix_plan.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_fix_plan.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.fix_plan import build_fix_plan, _action_id, SCHEMA
from docs.reporter import finding


def test_build_fix_plan_schema():
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[])
    assert plan["schema"] == SCHEMA
    assert plan["schema_version"] == "0.1"
    assert "plan_id" in plan
    assert "generated_at" in plan
    assert plan["generated_at"].endswith("Z")


def test_action_id_is_stable():
    """Same inputs → same action_id across calls."""
    id1 = _action_id("add_frontmatter", "docs/foo.md")
    id2 = _action_id("add_frontmatter", "docs/foo.md")
    assert id1 == id2
    assert id1.startswith("docs-action:")


def test_action_id_differs_by_type():
    id1 = _action_id("add_frontmatter", "docs/foo.md")
    id2 = _action_id("rename_file", "docs/foo.md")
    assert id1 != id2


def test_orphan_finding_maps_to_add_to_index():
    f = finding("orphan", "warn", "docs/old.md", "not reachable")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    assert len(plan["actions"]) == 1
    action = plan["actions"][0]
    assert action["type"] == "add_to_index"
    assert action["risk"] == "review"
    assert action["requires_confirmation"] is True
    assert action["path"] == "docs/old.md"


def test_naming_finding_maps_to_rename_file():
    f = finding("naming", "warn", "docs/MyDoc.md", "not kebab-case",
                safe_fix="rename to 'mydoc.md'")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    assert len(plan["actions"]) == 1
    action = plan["actions"][0]
    assert action["type"] == "rename_file"
    assert action["risk"] == "review"
    assert action["target_path"] == "mydoc.md"


def test_missing_dir_finding_maps_to_create_dir():
    f = finding("structure", "warn", "", "missing dir: docs/adr/")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    safe_actions = [a for a in plan["actions"] if a["type"] == "create_dir"]
    assert len(safe_actions) == 1
    assert safe_actions[0]["risk"] == "safe"
    assert safe_actions[0]["requires_confirmation"] is False


def test_frontmatter_finding_maps_to_add_frontmatter():
    f = finding("frontmatter", "info", "docs/foo.md", "missing title")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    action = plan["actions"][0]
    assert action["type"] == "add_frontmatter"
    assert action["risk"] == "safe"
    assert action["requires_confirmation"] is False


def test_plan_id_is_deterministic_for_same_findings():
    """Same findings → same plan_id (stable across runs)."""
    findings = [finding("orphan", "warn", "docs/x.md", "msg")]
    plan1 = build_fix_plan(repo_root="/tmp/repo", findings=findings)
    plan2 = build_fix_plan(repo_root="/tmp/repo", findings=findings)
    assert plan1["plan_id"] == plan2["plan_id"]


def test_empty_findings_empty_actions():
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[])
    assert plan["actions"] == []


# --- apply_report ---

from docs.apply_report import build_apply_report, action_result, file_hash, APPLY_SCHEMA


def test_apply_report_schema():
    report = build_apply_report(plan_id="p1", run_id="r1", actions=[])
    assert report["schema"] == APPLY_SCHEMA
    assert report["schema_version"] == "0.1"
    assert "applied_at" in report


def test_action_result_applied():
    r = action_result("docs-action:abc", "applied", "created dir")
    assert r["status"] == "applied"
    assert r["action_id"] == "docs-action:abc"


def test_action_result_waived():
    r = action_result("docs-action:abc", "waived", "user declined rename")
    assert r["status"] == "waived"


def test_file_hash_empty_string_for_missing_file(tmp_path):
    assert file_hash(tmp_path / "nonexistent.md") == ""


def test_file_hash_stable(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Hello")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2
    assert len(h1) == 16
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_plan.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.fix_plan'`

- [ ] **Step 3: Implement fix_plan.py**

```python
# plugins/h2t-dev/lib/docs/fix_plan.py
"""Converts doc findings into h2t_docs_fix_plan/v0.1 action list."""
from __future__ import annotations
import datetime
import hashlib

SCHEMA = "h2t_docs_fix_plan/v0.1"


def _action_id(action_type: str, path: str, target_path: str | None = None) -> str:
    """Deterministic stable id from (type, path, target_path)."""
    key = f"{action_type}:{path}:{target_path or ''}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"docs-action:{h}"


def _extract_rename_target(safe_fix: str) -> str | None:
    """Extract target filename from safe_fix string like \"rename to 'foo.md'\"."""
    import re
    m = re.search(r"rename to '([^']+)'", safe_fix or "")
    return m.group(1) if m else None


def _findings_to_actions(findings: list[dict]) -> list[dict]:
    actions = []
    for f in findings:
        t = f.get("type", "")
        path = f.get("path", "")
        msg = f.get("message", "")

        if t == "orphan":
            actions.append({
                "action_id": _action_id("add_to_index", path),
                "type": "add_to_index",
                "status": "proposed",
                "risk": "review",
                "path": path,
                "target_path": None,
                "reason": msg,
                "requires_confirmation": True,
            })

        elif t == "naming":
            target = _extract_rename_target(f.get("safe_fix", ""))
            actions.append({
                "action_id": _action_id("rename_file", path, target),
                "type": "rename_file",
                "status": "proposed",
                "risk": "review",
                "path": path,
                "target_path": target,
                "reason": msg,
                "requires_confirmation": True,
            })

        elif t == "structure":
            if "missing dir:" in msg:
                dir_name = msg.split("missing dir:")[-1].strip().rstrip("/")
                actions.append({
                    "action_id": _action_id("create_dir", dir_name),
                    "type": "create_dir",
                    "status": "proposed",
                    "risk": "safe",
                    "path": dir_name,
                    "target_path": None,
                    "reason": msg,
                    "requires_confirmation": False,
                })

        elif t == "frontmatter":
            actions.append({
                "action_id": _action_id("add_frontmatter", path),
                "type": "add_frontmatter",
                "status": "proposed",
                "risk": "safe",
                "path": path,
                "target_path": None,
                "reason": msg,
                "requires_confirmation": False,
            })

    return actions


def build_fix_plan(
    *,
    repo_root: str,
    findings: list[dict],
    source_report_id: str = "",
) -> dict:
    """Build h2t_docs_fix_plan/v0.1 from a findings list."""
    actions = _findings_to_actions(findings)
    # plan_id is deterministic: sha256 of (repo_root, sorted action_ids)
    id_key = repo_root + "|" + "|".join(
        sorted(a["action_id"] for a in actions)
    )
    plan_id = "docs-fix-plan:" + hashlib.sha256(id_key.encode()).hexdigest()[:16]
    return {
        "schema": SCHEMA,
        "schema_version": "0.1",
        "plan_id": plan_id,
        "repo_root": repo_root,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_report_id": source_report_id,
        "actions": actions,
    }
```

- [ ] **Step 4: Implement apply_report.py**

```python
# plugins/h2t-dev/lib/docs/apply_report.py
"""Builds h2t_docs_fix_apply_report/v0.1 — audit trail of a fix run."""
from __future__ import annotations
import datetime
import hashlib
from pathlib import Path

APPLY_SCHEMA = "h2t_docs_fix_apply_report/v0.1"


def action_result(
    action_id: str,
    status: str,      # applied | skipped | failed | waived
    message: str = "",
    before_hash: str = "",
    after_hash: str = "",
) -> dict:
    return {
        "action_id": action_id,
        "status": status,
        "message": message,
        "before_hash": before_hash,
        "after_hash": after_hash,
    }


def file_hash(path: Path | str) -> str:
    """SHA256 of file content (first 16 hex chars), empty string if absent."""
    p = Path(path)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build_apply_report(
    *,
    plan_id: str,
    run_id: str,
    actions: list[dict],
) -> dict:
    return {
        "schema": APPLY_SCHEMA,
        "schema_version": "0.1",
        "plan_id": plan_id,
        "run_id": run_id,
        "applied_at": datetime.datetime.utcnow().isoformat() + "Z",
        "actions": actions,
    }
```

- [ ] **Step 5: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_plan.py -v
```

Expected: `15 passed`

- [ ] **Step 6: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/fix_plan.py plugins/h2t-dev/lib/docs/apply_report.py tests/docs/test_fix_plan.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add fix_plan.py + apply_report.py — execution tracking schemas v0.1"
```

---

### Task 2: orphan.py — BFS orphan detection

**Files:**
- Create: `plugins/h2t-dev/lib/docs/orphan.py`
- Create: `tests/docs/test_orphan.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_orphan.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.orphan import find_orphan_files


def test_no_docs_dir_no_findings(tmp_path):
    """No docs/ dir → no findings."""
    assert find_orphan_files(tmp_path) == []


def test_readme_itself_not_orphan(tmp_path):
    """docs/README.md is the BFS root — never flagged as orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n")
    results = find_orphan_files(tmp_path)
    assert not any("README.md" in r["path"] for r in results)


def test_linked_file_not_orphan(tmp_path):
    """File linked from README.md → not an orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Guide](guide.md)\n")
    (docs / "guide.md").write_text("# Guide\n")
    results = find_orphan_files(tmp_path)
    assert not any("guide.md" in r["path"] for r in results)


def test_unlinked_file_is_orphan(tmp_path):
    """File not linked from README.md → orphan finding."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n")
    (docs / "stale.md").write_text("# Stale\n")
    results = find_orphan_files(tmp_path)
    assert len(results) == 1
    assert "stale.md" in results[0]["path"]
    assert results[0]["type"] == "orphan"
    assert results[0]["severity"] == "warn"


def test_transitive_link_not_orphan(tmp_path):
    """File reachable via chain README → section/README → deep → not orphan."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Section](section/README.md)\n")
    section = docs / "section"
    section.mkdir()
    (section / "README.md").write_text("# Section\n\n[Deep](deep.md)\n")
    (section / "deep.md").write_text("# Deep\n")
    results = find_orphan_files(tmp_path)
    assert not any("deep.md" in r["path"] for r in results)
    assert not any("section/README.md" in r["path"] for r in results)


def test_missing_readme_all_files_flagged(tmp_path):
    """No docs/README.md → all docs files are orphans (unreachable)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# Page\n")
    results = find_orphan_files(tmp_path)
    assert len(results) == 1
    assert "page.md" in results[0]["path"]


def test_http_links_not_followed(tmp_path):
    """External http links are skipped — no false positives."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Docs\n\n[External](https://example.com/page.md)\n"
    )
    (docs / "local.md").write_text("# Local\n")
    results = find_orphan_files(tmp_path)
    assert any("local.md" in r["path"] for r in results)


def test_fragment_links_resolved_correctly(tmp_path):
    """Links with #anchor are resolved to the file (anchor stripped)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        "# Docs\n\n[Guide](guide.md#section)\n"
    )
    (docs / "guide.md").write_text("# Guide\n")
    results = find_orphan_files(tmp_path)
    assert not any("guide.md" in r["path"] for r in results)


def test_traversal_outside_docs_blocked(tmp_path):
    """Links pointing to ../outside.md (outside docs/) are not followed."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[Outside](../outside.md)\n")
    (tmp_path / "outside.md").write_text("# Outside\n")
    results = find_orphan_files(tmp_path)
    # outside.md lives outside docs/ — must not appear in findings
    assert not any("outside.md" in r["path"] for r in results)


def test_links_within_docs_subdir_followed(tmp_path):
    """Links into docs subdirs are still followed correctly."""
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    (docs / "README.md").write_text("# Docs\n\n[Page](sub/page.md)\n")
    (docs / "sub" / "page.md").write_text("# Page\n")
    results = find_orphan_files(tmp_path)
    assert not any("page.md" in r["path"] for r in results)
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_orphan.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.orphan'`

- [ ] **Step 3: Implement orphan.py**

```python
# plugins/h2t-dev/lib/docs/orphan.py
"""BFS orphan detection: finds .md files unreachable from docs/README.md."""
from __future__ import annotations
import re
from collections import deque
from pathlib import Path

_LINK_RE = re.compile(r'\[(?:[^\]]*)\]\(([^)#?\s][^)]*?)(?:[#?][^)]*)?\)')


def _parse_md_links(text: str, base_dir: Path, docs_dir: Path) -> list[Path]:
    """Extract local .md link targets constrained to within docs_dir."""
    docs_resolved = docs_dir.resolve()
    links = []
    for m in _LINK_RE.finditer(text):
        href = m.group(1).strip()
        if href.startswith(("http://", "https://", "mailto:", "/")):
            continue
        target = (base_dir / href).resolve()
        if target.suffix != ".md" or not target.is_file():
            continue
        # Reject targets outside docs/ and symlinks
        try:
            target.relative_to(docs_resolved)
        except ValueError:
            continue
        if target.is_symlink():
            continue
        links.append(target)
    return links


def find_orphan_files(repo_root: Path) -> list[dict]:
    """
    BFS from docs/README.md. Returns finding dicts for unreachable .md files.
    Files reachable via any linked index chain are not orphans.
    """
    from docs.reporter import finding as make_finding

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    readme = docs_dir / "README.md"
    if not readme.exists():
        orphans = sorted(docs_dir.rglob("*.md"))
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

    all_docs = {f.resolve() for f in docs_dir.rglob("*.md")}
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

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_orphan.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/orphan.py tests/docs/test_orphan.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add orphan.py — BFS unreachable-doc detection from docs/README.md"
```

---

### Task 3: naming.py — extended naming checks across all docs/

**Files:**
- Create: `plugins/h2t-dev/lib/docs/naming.py`
- Create: `tests/docs/test_naming_extended.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_naming_extended.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.naming import check_naming_all_docs


def test_no_docs_dir_no_findings(tmp_path):
    assert check_naming_all_docs(tmp_path) == []


def test_clean_kebab_file_no_finding(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my-guide.md").write_text("# Guide")
    assert check_naming_all_docs(tmp_path) == []


def test_readme_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# README")
    assert check_naming_all_docs(tmp_path) == []


def test_changelog_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CHANGELOG.md").write_text("# Changes")
    assert check_naming_all_docs(tmp_path) == []


def test_uppercase_filename_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "MyDoc.md").write_text("# My Doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert results[0]["type"] == "naming"
    assert results[0]["severity"] == "warn"
    assert "MyDoc.md" in results[0]["message"]


def test_space_in_name_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my doc.md").write_text("# my doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert results[0]["safe_fix"] is not None


def test_underscore_flagged(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "my_doc.md").write_text("# my doc")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "my-doc.md" in results[0]["safe_fix"]


def test_spec_without_date_prefix_flagged(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "my-feature-design.md").write_text("# Spec")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "date prefix" in results[0]["message"]
    assert "YYYY-MM-DD-my-feature-design.md" in results[0]["safe_fix"]


def test_spec_with_date_prefix_ok(tmp_path):
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "2026-05-28-my-feature.md").write_text("# Spec")
    assert check_naming_all_docs(tmp_path) == []


def test_plan_without_date_flagged(tmp_path):
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "my-plan.md").write_text("# Plan")
    results = check_naming_all_docs(tmp_path)
    assert len(results) == 1
    assert "date prefix" in results[0]["message"]


def test_index_md_allowed(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Index")
    assert check_naming_all_docs(tmp_path) == []
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_naming_extended.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.naming'`

- [ ] **Step 3: Implement naming.py**

```python
# plugins/h2t-dev/lib/docs/naming.py
"""Extended naming convention checks for all docs/ markdown files."""
from __future__ import annotations
import re
from pathlib import Path

_ALLOWED_NAMES = frozenset({
    "README.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md",
    "GEMINI.md", "index.md", "LICENSE.md",
})
_KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$")
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_DATE_REQUIRED_SUBDIRS = frozenset({"superpowers/specs", "superpowers/plans"})


def _requires_date_prefix(rel_path: str) -> bool:
    """True if the path is inside a dir that requires YYYY-MM-DD- prefix."""
    return any(d in rel_path for d in _DATE_REQUIRED_SUBDIRS)


def check_naming_all_docs(repo_root: Path) -> list[dict]:
    """
    Check all .md files in docs/ for:
    1. lowercase kebab-case (spaces, uppercase, underscores → finding)
    2. date prefix where required (superpowers/specs/, superpowers/plans/)
    Returns list of finding dicts.
    """
    from docs.reporter import finding as make_finding

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    findings = []
    for md_file in docs_dir.rglob("*.md"):
        name = md_file.name
        if name in _ALLOWED_NAMES:
            continue
        rel = str(md_file.relative_to(repo_root)).replace("\\", "/")

        if not _KEBAB_RE.match(name):
            proposed = re.sub(r"[\s_]+", "-", name).lower()
            findings.append(
                make_finding(
                    "naming",
                    "warn",
                    rel,
                    f"Not lowercase kebab-case: '{name}'",
                    safe_fix=f"rename to '{proposed}'",
                )
            )
            continue  # skip date-prefix check on badly-named file

        if _requires_date_prefix(rel) and not _DATE_PREFIX_RE.match(name):
            findings.append(
                make_finding(
                    "naming",
                    "warn",
                    rel,
                    f"Missing date prefix in {rel.rsplit('/', 1)[0]}: '{name}'",
                    safe_fix=f"rename to 'YYYY-MM-DD-{name}'",
                )
            )

    return findings
```

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_naming_extended.py -v
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/naming.py tests/docs/test_naming_extended.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add naming.py — extended kebab-case and date-prefix checks for all docs/"
```

---

### Task 4: config.py — per-repo config discovery

**Files:**
- Create: `plugins/h2t-dev/lib/docs/config.py`
- Create: `tests/docs/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_config.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.config import load_config


def test_defaults_when_no_config_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"
    assert "docs/adr" in cfg["required_dirs"]
    assert cfg["exceptions"] == []
    assert cfg["template"] is None


def test_config_overrides_docs_root(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("docs_root: documentation\n")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "documentation"


def test_config_partial_override_keeps_defaults(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("template: client_project\n")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"
    assert cfg["template"] == "client_project"


def test_exceptions_list_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("exceptions:\n  - eval\n  - ops\n")
    cfg = load_config(tmp_path)
    assert "eval" in cfg["exceptions"]
    assert "ops" in cfg["exceptions"]


def test_empty_config_file_returns_defaults(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.config'`

- [ ] **Step 3: Implement config.py**

```python
# plugins/h2t-dev/lib/docs/config.py
"""Per-repo docs-lint configuration discovery from .claude/rules/docs-lint.yaml."""
from __future__ import annotations
from pathlib import Path
from typing import Any

CONFIG_PATH = ".claude/rules/docs-lint.yaml"

_DEFAULTS: dict[str, Any] = {
    "docs_root": "docs",
    "required_dirs": [
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        "docs/adr",
        "docs/reports",
    ],
    "exceptions": [],
    "template": None,
}


def load_config(repo_root: Path) -> dict[str, Any]:
    """Load config from .claude/rules/docs-lint.yaml; fall back to defaults."""
    cfg_path = repo_root / CONFIG_PATH
    if not cfg_path.exists():
        return dict(_DEFAULTS)
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
    return merged
```

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_config.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/config.py tests/docs/test_config.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add config.py — .claude/rules/docs-lint.yaml discovery with defaults"
```

---

### Task 5: index_builder.py — marker-based index with bootstrap

Absorbs the user-facing role of docs-index. Uses injectable generator for testability.

**Files:**
- Create: `plugins/h2t-dev/lib/docs/index_builder.py`
- Create: `tests/docs/test_fix_index.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/docs/test_fix_index.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.index_builder import (
    compute_index_update,
    write_index,
    INDEX_START,
    INDEX_END,
)

_FAKE_GENERATE = lambda rp, name: "# generated content\n"


def test_no_readme_operation_is_append(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "append"
    assert has_markers is False
    assert INDEX_START in content
    assert INDEX_END in content


def test_readme_with_markers_operation_is_replace(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text(f"# Manual\n\n{INDEX_START}\nold content\n{INDEX_END}\n")
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "replace"
    assert has_markers is True
    assert "old content" not in content
    assert "# Manual" in content
    assert "# generated content" in content


def test_readme_without_markers_operation_is_append(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text("# Manual Section\n\nsome content\n")
    content, operation, has_markers = compute_index_update(
        tmp_path, "test-repo", generate=_FAKE_GENERATE
    )
    assert operation == "append"
    assert "# Manual Section" in content
    assert "some content" in content
    assert INDEX_START in content


def test_dry_run_does_not_write(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=False,
                         generate=_FAKE_GENERATE)
    readme = tmp_path / "docs" / "README.md"
    assert not readme.exists()
    assert report["status"] == "dry_run"
    assert report["applied"] is False


def test_apply_creates_readme(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=True,
                         generate=_FAKE_GENERATE)
    readme = tmp_path / "docs" / "README.md"
    assert readme.exists()
    content = readme.read_text(encoding="utf-8")
    assert INDEX_START in content
    assert report["status"] == "applied"
    assert report["applied"] is True


def test_apply_is_atomic_no_tmp_leftovers(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    write_index(tmp_path, "test-repo", apply=True, generate=_FAKE_GENERATE)
    tmp_files = list(docs.glob("*.tmp"))
    assert tmp_files == []


def test_apply_replace_preserves_manual_content(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text(f"# Manual\n\n{INDEX_START}\nold\n{INDEX_END}\n")
    write_index(tmp_path, "test-repo", apply=True, generate=_FAKE_GENERATE)
    content = readme.read_text(encoding="utf-8")
    assert "# Manual" in content
    assert "old" not in content
    assert "# generated content" in content


def test_apply_over_existing_readme_no_markers_succeeds(tmp_path):
    """apply=True over existing README without markers appends and does not crash (Windows-safe os.replace)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = docs / "README.md"
    readme.write_text("# Existing Content\n")
    report = write_index(tmp_path, "test-repo", apply=True,
                         generate=_FAKE_GENERATE)
    assert report["status"] == "applied"
    content = readme.read_text(encoding="utf-8")
    assert "# Existing Content" in content
    assert INDEX_START in content
    assert not list(docs.glob("*.tmp"))


def test_report_has_required_fields(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    report = write_index(tmp_path, "test-repo", apply=False,
                         generate=_FAKE_GENERATE)
    assert "readme_path" in report
    assert "operation" in report
    assert "has_markers" in report
    assert "status" in report
    assert "applied" in report
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_index.py -v
```

Expected: `ModuleNotFoundError: No module named 'docs.index_builder'`

- [ ] **Step 3: Implement index_builder.py**

```python
# plugins/h2t-dev/lib/docs/index_builder.py
"""Marker-based docs/README.md index builder with bootstrap support."""
from __future__ import annotations
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

INDEX_START = "<!-- h2t-index-start -->"
INDEX_END = "<!-- h2t-index-end -->"

_MARKER_RE = re.compile(
    r"<!-- h2t-index-start -->.*?<!-- h2t-index-end -->",
    re.DOTALL,
)


def _default_generate(repo_root: Path, repo_name: str) -> str:
    """Import and call build_navigation_index from docs-index script."""
    import sys
    _index_dir = Path(__file__).parents[3] / "skills" / "docs-index" / "scripts"
    if str(_index_dir) not in sys.path:
        sys.path.insert(0, str(_index_dir))
    from index import build_navigation_index
    return build_navigation_index(repo_root, repo_name)


def compute_index_update(
    repo_root: Path,
    repo_name: str,
    readme_path: Path | None = None,
    *,
    generate: Callable[[Path, str], str] | None = None,
) -> tuple[str, str, bool]:
    """
    Compute new README content without writing.
    Returns (new_content, operation, has_markers).
    operation: 'replace' | 'append'
    has_markers: True if README already has index markers.
    """
    if generate is None:
        generate = _default_generate
    if readme_path is None:
        readme_path = repo_root / "docs" / "README.md"

    generated = generate(repo_root, repo_name)
    wrapped = f"{INDEX_START}\n{generated}\n{INDEX_END}"

    if not readme_path.exists():
        return wrapped + "\n", "append", False

    existing = readme_path.read_text(encoding="utf-8", errors="replace")

    if INDEX_START in existing:
        new_content = _MARKER_RE.sub(wrapped, existing)
        return new_content, "replace", True

    # Bootstrap: append section below existing content
    new_content = existing.rstrip() + "\n\n" + wrapped + "\n"
    return new_content, "append", False


def write_index(
    repo_root: Path,
    repo_name: str,
    *,
    apply: bool = False,
    readme_path: Path | None = None,
    generate: Callable[[Path, str], str] | None = None,
) -> dict:
    """
    Dry-run or apply index update. Returns operation report.
    On apply, uses atomic tmp-file + os.replace() (Windows-safe).
    """
    if readme_path is None:
        readme_path = repo_root / "docs" / "README.md"

    new_content, operation, has_markers = compute_index_update(
        repo_root, repo_name, readme_path, generate=generate
    )

    report: dict = {
        "readme_path": str(readme_path),
        "operation": operation,
        "has_markers": has_markers,
        "applied": False,
        "status": "dry_run",
    }

    if not apply:
        return report

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=readme_path.parent,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(new_content)
        tmp_path = tf.name

    try:
        os.replace(tmp_path, readme_path)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    report["applied"] = True
    report["status"] = "applied"
    return report
```

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_fix_index.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/lib/docs/index_builder.py tests/docs/test_fix_index.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): add index_builder.py — marker-based README index with bootstrap support"
```

---

### Task 6: lint.py rewrite — new CLI with sub-commands and backward compat

The new CLI replaces the old positional-repos-only interface. Mode detection:
- First arg in `{audit, plan, fix-safe, fix-index, doctor}` → new sub-command mode
- `--fix` or `--fix-frontmatter` present → legacy mode with deprecation warning to stderr
- No args and no sub-command → auto-detect from cwd in audit mode

New args:
- `--root PATH` — explicit repo root (bypasses DEV_ROOT, skips global-standards check)
- `--json` — machine-readable output (for `doctor` mode)
- `--apply` — write changes (for `fix-index` mode)
- `--only frontmatter` — scope for `fix-safe` mode

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Modify: `tests/docs/test_lint_checks.py` (add backward-compat tests)

- [ ] **Step 1: Add backward-compat tests to test_lint_checks.py**

Add at the end of `tests/docs/test_lint_checks.py`:

```python
# --- Backward compatibility ---

import subprocess as _sp
import sys as _sys

_LINT_SCRIPT = str(
    Path(__file__).parents[2]
    / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"
)


def test_legacy_fix_flag_emits_deprecation_warning(tmp_path):
    """--fix flag emits deprecation warning to stderr and exits 0."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "--root", str(tmp_path), "--fix"],
        capture_output=True, text=True,
    )
    assert "deprecated" in result.stderr.lower() or "fix-safe" in result.stderr.lower()
    assert result.returncode == 0


def test_legacy_fix_frontmatter_flag_emits_deprecation(tmp_path):
    """--fix-frontmatter emits deprecation warning to stderr and exits 0."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "--root", str(tmp_path), "--fix-frontmatter"],
        capture_output=True, text=True,
    )
    assert "deprecated" in result.stderr.lower() or "fix-safe" in result.stderr.lower()
    assert result.returncode == 0


def test_new_audit_subcommand_exits_cleanly(tmp_path):
    """audit subcommand with --root on empty repo exits without crash."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "audit", "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1)


def test_doctor_json_produces_schema(tmp_path):
    """doctor --json outputs valid h2t_lifecycle_report/v0.1 schema."""
    import json as _json
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "doctor", "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1)
    data = _json.loads(result.stdout)
    assert data["schema"] == "h2t_lifecycle_report/v0.1"


def test_fix_index_dry_run_no_file_created(tmp_path):
    """fix-index without --apply does not create README.md."""
    (tmp_path / "docs").mkdir()
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "fix-index", "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not (tmp_path / "docs" / "README.md").exists()


def test_fix_safe_preserves_existing_frontmatter_keys(tmp_path):
    """fix-safe does not drop custom/unknown frontmatter keys when adding missing required ones."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    md = specs / "2026-05-28-test-spec.md"
    md.write_text(
        '---\ntitle: "My Spec"\ncustom_tag: "keep-me"\n---\n# Content\n'
    )
    _sp.run(
        [_sys.executable, _LINT_SCRIPT, "fix-safe", "--root", str(tmp_path),
         "--only", "frontmatter"],
        capture_output=True, text=True,
    )
    result = md.read_text(encoding="utf-8")
    assert 'custom_tag: "keep-me"' in result
    assert "status:" in result


def test_legacy_fix_with_root_is_rejected(tmp_path):
    """--fix combined with --root is rejected (ambiguous target). Exits non-zero."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "--root", str(tmp_path), "--fix"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "--root" in result.stderr or "incompatible" in result.stderr.lower()
```

- [ ] **Step 2: Run new tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_lint_checks.py::test_legacy_fix_flag_emits_deprecation_warning -v
```

Expected: `FAILED` (assertion error — current lint.py has no deprecation warning)

- [ ] **Step 3: Rewrite lint.py with new CLI**

Replace `plugins/h2t-dev/skills/docs-lint/scripts/lint.py` with:

```python
#!/usr/bin/env python3
"""docs-lint: Documentation health check and fix tool.

Sub-commands:
  audit       Run all checks and show findings (default)
  plan        Show human-readable cleanup plan without writing
  fix-safe    Apply only safe mechanical fixes (dirs, frontmatter)
  fix-index   Rebuild docs/README.md navigation index
  doctor      Output machine-readable h2t_lifecycle_report/v0.1 JSON

Legacy flags (deprecated, use sub-commands instead):
  --fix                 → fix-safe (emits deprecation warning)
  --fix-frontmatter     → fix-safe --only=frontmatter (emits deprecation warning)
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, REPO_EXTRA_DIRS, STANDARDS_FILES,
    FRONTMATTER_RULES, ensure_dir, print_header, repo_path, parse_frontmatter,
)
from docs.orphan import find_orphan_files
from docs.naming import check_naming_all_docs
from docs.reporter import build_report, status_from_findings, finding
from docs.config import load_config
from docs.index_builder import write_index

_SUBCOMMANDS = frozenset({"audit", "plan", "fix-safe", "fix-index", "doctor"})

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

YAML_FLAG_CHECKS: dict[str, str] = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report": "docs/reports",
    "docs.marketing_docs": "docs/marketing",
}


def _load_projects_yaml() -> dict:
    if not PROJECTS_YAML_PATH.exists():
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return {}


def _get_flag(project_data: dict, dotted_key: str) -> bool:
    parts = dotted_key.split(".")
    node = project_data
    for p in parts:
        if not isinstance(node, dict):
            return False
        node = node.get(p, False)
    return bool(node)


def check_projects_yaml(rp: Path, name: str, projects: dict) -> list[str]:
    if not projects:
        return []
    project_data = projects.get(name, {})
    if not project_data:
        return []
    failures = []
    for flag, required_path in YAML_FLAG_CHECKS.items():
        if _get_flag(project_data, flag):
            target = rp / required_path
            if not target.exists():
                failures.append(f"projects.yaml {flag}=true but missing: {required_path}")
    return failures


def check_structure(rp: Path) -> list[str]:
    failures = []
    for rel_dir in REQUIRED_CORE_DIRS:
        if not (rp / rel_dir).exists():
            failures.append(f"missing dir: {rel_dir}/")
    for name, path in [
        ("docs/README.md", rp / "docs" / "README.md"),
        (".claude/rules/documentation.md", rp / ".claude" / "rules" / "documentation.md"),
        (".pymarkdown.yaml", rp / ".pymarkdown.yaml"),
        (".vale.ini", rp / ".vale.ini"),
    ]:
        if not path.exists():
            failures.append(f"missing: {name}")
    return failures


def check_adr_naming(rp: Path) -> list[str]:
    failures = []
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return failures
    for adr in adr_dir.glob("[0-9]*.md"):
        if not re.match(r"^\d{4}-", adr.name):
            failures.append(f"ADR naming: {adr.name} (expected 4-digit prefix)")
    return failures


LEGACY_DIRS = ["docs/plans", "docs/specs", "docs/handoff", "docs/handoffs", "docs/eval"]


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


def check_frontmatter(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return failures
    for md_file in docs_dir.rglob("*.md"):
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern not in rel or not required_fields:
                continue
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            if fm is None:
                failures.append(f"{rel}: missing frontmatter")
                break
            for field in required_fields:
                if field not in fm:
                    failures.append(f"{rel}: missing field '{field}'")
    return failures


def run_pymarkdownlnt(rp: Path) -> list[str]:
    pymdl = shutil.which("pymarkdownlnt") or shutil.which("pymarkdown")
    if not pymdl:
        return []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []
    result = subprocess.run(
        [pymdl, "scan", str(docs_dir)],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode != 0:
        out = result.stdout + result.stderr
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return [f"pymarkdownlnt: {ln}" for ln in lines[:20]]
    return []


def fix_structure(rp: Path) -> list[str]:
    fixes = []
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if ensure_dir(d):
            fixes.append(f"created: {rel_dir}/")
    return fixes


def _extract_title(text: str, filename: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", filename)
    return name.replace("-", " ").replace("_", " ").strip(".md")


def _extract_date(filename: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else "unknown"


def _extract_milestone(filename: str) -> str:
    m = re.search(r"-(m\d+)-", filename, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _git_author(rp: Path, filepath: Path) -> str:
    rel = str(filepath.relative_to(rp))
    result = subprocess.run(
        ["git", "-C", str(rp), "log", "--diff-filter=A", "--format=%an", "--", rel],
        capture_output=True, text=True,
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines[0] if lines else "lichtpfad"


def _frontmatter_value(field: str, md_file: Path, text: str, rp: Path) -> str:
    """Derive a default value for a single missing frontmatter field."""
    if field == "title":
        return f'"{_extract_title(text, md_file.stem)}"'
    if field == "status":
        return '"draft"'
    if field == "owner":
        return f'"{_git_author(rp, md_file)}"'
    if field == "date":
        return f'"{_extract_date(md_file.name)}"'
    if field == "milestone":
        return f'"{_extract_milestone(md_file.name)}"'
    return '""'


def fix_frontmatter_action(rp: Path) -> list[str]:
    """Add only missing required frontmatter fields. Preserves existing keys."""
    fixes = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return fixes
    for md_file in docs_dir.rglob("*.md"):
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        matched_pattern = None
        required_fields_for_pattern: list[str] = []
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern in rel and required_fields:
                matched_pattern = dir_pattern
                required_fields_for_pattern = required_fields
                break
        if not matched_pattern:
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm is not None and all(f in fm for f in required_fields_for_pattern):
            continue

        missing = [f for f in required_fields_for_pattern if not (fm and f in fm)]

        if fm is not None and text.startswith("---"):
            # Partial frontmatter: append only missing fields to existing block.
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_block = parts[1].rstrip("\n")
                body = parts[2]
                extra = "\n".join(
                    f"{f}: {_frontmatter_value(f, md_file, text, rp)}"
                    for f in missing
                )
                new_text = "---\n" + fm_block.lstrip("\n") + "\n" + extra + "\n---" + body
            else:
                continue  # can't parse safely; skip
        else:
            # No frontmatter at all: build complete header from scratch.
            lines = ["---"]
            for f in required_fields_for_pattern:
                lines.append(f"{f}: {_frontmatter_value(f, md_file, text, rp)}")
            lines += ["---", ""]
            body_text = text if not text.startswith("---") else text
            new_text = "\n".join(lines) + body_text

        # Atomic write via tmp + os.replace (Windows-safe)
        import tempfile as _tmpmod
        dir_ = md_file.parent
        with _tmpmod.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=dir_, delete=False, suffix=".tmp"
        ) as tf:
            tf.write(new_text)
            tmp = tf.name
        try:
            os.replace(tmp, md_file)
        except Exception:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        fixes.append(f"added frontmatter fields {missing}: {rel}")
    return fixes


_SYNC_LABELS_SCRIPT = Path(__file__).parents[2] / "docs-sync-labels" / "scripts" / "sync_labels.py"
_H2T_PYTHON = (
    Path.home() / ".h2t" / "venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else Path.home() / ".h2t" / "venv" / "bin" / "python"
)


def fix_labels(rp: Path, repo_name: str) -> str:
    python = str(_H2T_PYTHON) if _H2T_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(_SYNC_LABELS_SCRIPT), repo_name, "--apply"],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode == 0:
        return f"labels synced for {repo_name}"
    return f"label sync failed: {result.stderr.strip()[:120]}"


def _get_git_head(rp: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(rp), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _resolve_root(root_arg: str | None) -> Path:
    """Resolve --root arg to absolute Path."""
    if root_arg:
        return Path(root_arg).resolve()
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part
    return cwd


def _repo_name_from_root(rp: Path) -> str:
    return rp.name


def _collect_all_findings(rp: Path, no_pymarkdown: bool = False) -> list[dict]:
    """Run all checks and return findings list (navigation first, metadata last)."""
    findings = []
    # 1. Navigation / orphan
    findings.extend(find_orphan_files(rp))
    # 2. Naming
    for msg in check_naming_all_docs(rp):
        # naming.py already returns finding dicts
        findings.append(msg) if isinstance(msg, dict) else None
    # 3. Structure
    extra = REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])
    for msg in (
        check_structure(rp)
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + (check_repo_root(rp))
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    ):
        findings.append(finding("structure", "warn", "", msg))
    # 4. Metadata / frontmatter (secondary)
    for msg in check_frontmatter(rp):
        findings.append(finding("frontmatter", "info", "", msg))
    return findings


def _naming_findings_from_check(rp: Path) -> list[dict]:
    """check_naming_all_docs returns dicts already."""
    return check_naming_all_docs(rp)


def _run_audit(rp: Path, no_pymarkdown: bool = False) -> None:
    repo_name = _repo_name_from_root(rp)
    print_header(f"docs-lint audit: {rp}")

    orphans = find_orphan_files(rp)
    naming = check_naming_all_docs(rp)
    extra = REPO_EXTRA_DIRS.get(repo_name, [])
    structure_msgs = (
        check_structure(rp)
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    )
    frontmatter_msgs = check_frontmatter(rp)

    sections = [
        ("Navigation / Orphans", orphans, lambda f: f"  WARN: [{f['type']}] {f['path']} — {f['message']}"),
        ("Naming", naming, lambda f: f"  WARN: [{f['type']}] {f['path']} — {f['message']}"),
        ("Structure", [finding("structure", "warn", "", m) for m in structure_msgs],
         lambda f: f"  WARN: {f['message']}"),
        ("Metadata / Frontmatter", [finding("frontmatter", "info", "", m) for m in frontmatter_msgs],
         lambda f: f"  INFO: {f['message']}"),
    ]

    total = 0
    for section_name, items, fmt in sections:
        if items:
            print(f"\n--- {section_name} ({len(items)}) ---")
            for item in items:
                print(fmt(item))
            total += len(items)

    print(f"\n{'=' * 60}")
    if total:
        print(f"  RESULT: {total} finding(s) — run 'docs-lint plan' for cleanup steps")
        sys.exit(1)
    else:
        print("  RESULT: all checks passed")


def _run_plan(rp: Path) -> None:
    print_header(f"docs-lint plan: {rp}")
    orphans = find_orphan_files(rp)
    naming = check_naming_all_docs(rp)

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

    extra = REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])
    structure_msgs = (
        check_structure(rp)
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
    )
    if structure_msgs:
        print("\n## Structure Issues\n")
        for msg in structure_msgs:
            print(f"  - {msg}")

    if not orphans and not naming and not structure_msgs:
        print("\n  No cleanup needed.")
    else:
        print(f"\n  Run 'docs-lint fix-safe' for auto-fixable items.")
        print(f"  Run 'docs-lint fix-index' for README/index rebuild.")


def _run_fix_safe(rp: Path, only: str = "all") -> None:
    print_header(f"docs-lint fix-safe [{only}]: {rp}")
    if only in ("all", "dirs"):
        fixes = fix_structure(rp)
        for f in fixes:
            print(f"  FIX: {f}")
    if only in ("all", "frontmatter"):
        fixes = fix_frontmatter_action(rp)
        for f in fixes:
            print(f"  FIX: {f}")
    print("  Done. Renames/moves require 'docs-lint plan' review and manual action.")


def _run_fix_index(rp: Path, apply: bool = False) -> None:
    repo_name = _repo_name_from_root(rp)
    mode = "APPLY" if apply else "DRY-RUN"
    print_header(f"docs-lint fix-index [{mode}]: {rp}")
    report = write_index(rp, repo_name, apply=apply)
    print(f"  operation: {report['operation']}")
    print(f"  has_markers: {report['has_markers']}")
    print(f"  readme_path: {report['readme_path']}")
    print(f"  status: {report['status']}")
    if not apply and not report["has_markers"]:
        print("  Note: README has no markers — run with --apply to append index section.")


def _run_doctor(rp: Path, json_output: bool = False, no_pymarkdown: bool = False) -> None:
    orphans = find_orphan_files(rp)
    naming = check_naming_all_docs(rp)
    extra = REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])
    structure_msgs = (
        check_structure(rp)
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    )
    frontmatter_msgs = check_frontmatter(rp)

    all_findings = (
        orphans
        + naming
        + [finding("structure", "warn", "", m) for m in structure_msgs]
        + [finding("frontmatter", "info", "", m) for m in frontmatter_msgs]
    )
    status = status_from_findings(all_findings)
    total = len(all_findings)
    summary = (
        f"{len(orphans)} orphan(s), {len(naming)} naming issue(s), "
        f"{len(structure_msgs)} structure issue(s), {len(frontmatter_msgs)} metadata issue(s)"
    )
    safe_next = (
        "Run 'docs-lint plan' for cleanup plan"
        if total else "No issues found"
    )
    report = build_report(
        command="docs-lint doctor",
        repo_root=str(rp),
        status=status,
        summary=summary,
        findings=all_findings,
        safe_next_action=safe_next,
        git_head=_get_git_head(rp),
    )

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print_header(f"docs-lint doctor: {rp}")
        print(f"  status: {status}")
        print(f"  {summary}")
        if total:
            sys.exit(1)


def _detect_current_repo() -> str | None:
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part.name
    return None


# ---- Legacy mode (repos by name) ----

def _legacy_main(args: argparse.Namespace) -> None:
    if args.repos:
        targets = args.repos
    elif args.all:
        targets = REPO_MANIFEST
    else:
        detected = _detect_current_repo()
        targets = [detected] if detected else REPO_MANIFEST

    print_header(f"docs-lint: checking {len(targets)} repos")
    projects = _load_projects_yaml()

    # Global standards check only in DEV_ROOT-based mode
    print("\n--- Global Standards ---")
    std_dir = DEV_ROOT / "docs" / "standards"
    std_fails = [f for f in STANDARDS_FILES if not (std_dir / f).exists()]
    if std_fails:
        for f in std_fails:
            print(f"  FAIL: missing {f}")
    else:
        print(f"  OK: all {len(STANDARDS_FILES)} standards files present")

    total_failures = len(std_fails)

    for name in targets:
        rp = repo_path(name)
        if not rp.exists():
            print(f"\n--- {name} ---\n  SKIP: repo not found at {rp}")
            continue
        print(f"\n--- {name} ---")

        if args.fix:
            fixes = fix_structure(rp)
            for f in fixes:
                print(f"  FIX: {f}")
        if args.fix_frontmatter:
            fixes = fix_frontmatter_action(rp)
            for f in fixes:
                print(f"  FIX: {f}")

        extra = REPO_EXTRA_DIRS.get(name, [])
        failures = (
            check_structure(rp)
            + check_adr_naming(rp)
            + check_legacy_dirs(rp, extra_dirs=extra)
            # use old naming check for multi-repo legacy mode
            + _legacy_check_naming(rp)
            + check_frontmatter(rp)
            + check_data_docs_boundary(rp)
            + check_projects_yaml(rp, name, projects)
            + (check_repo_root(rp) if args.repo_root else [])
            + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
        )
        if failures:
            for f in failures:
                print(f"  FAIL: {f}")
            total_failures += len(failures)
        else:
            print("  OK: all checks passed")

        if args.fix_labels:
            msg = fix_labels(rp, name)
            print(f"  FIX-LABELS: {msg}")

    print(f"\n{'=' * 60}")
    if total_failures:
        print(f"  RESULT: {total_failures} issue(s) found")
        sys.exit(1)
    else:
        print(f"  RESULT: all {len(targets)} repos compliant")


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_NAMING_DIRS = ["docs/superpowers/specs", "docs/superpowers/plans"]
_NAMING_SKIP = {"README.md", "index.md"}


def _legacy_check_naming(rp: Path) -> list[str]:
    """Legacy naming check for multi-repo mode (specs/plans date prefix only)."""
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


# ---- Entry point ----

def main() -> None:
    # Detect legacy vs new mode
    raw = sys.argv[1:]

    # Legacy mode detection: --fix or --fix-frontmatter present
    legacy_flags = {"--fix", "--fix-frontmatter"}
    is_legacy_flags = bool(set(raw) & legacy_flags)

    # Sub-command mode: first non-flag arg is a known sub-command
    first_pos = next((a for a in raw if not a.startswith("-")), None)
    is_subcommand = first_pos in _SUBCOMMANDS

    if is_legacy_flags:
        # Reject ambiguous combination: --root + legacy fix flags target different repos.
        if "--root" in raw:
            print(
                "ERROR: '--root' is incompatible with deprecated '--fix'/'--fix-frontmatter'. "
                "Use 'docs-lint fix-safe --root PATH' instead.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Emit deprecation warning to stderr
        for flag in legacy_flags & set(raw):
            if flag == "--fix":
                print(
                    "DEPRECATED: '--fix' is deprecated. Use 'docs-lint fix-safe' instead. "
                    "Will be removed in v2.",
                    file=sys.stderr,
                )
            if flag == "--fix-frontmatter":
                print(
                    "DEPRECATED: '--fix-frontmatter' is deprecated. "
                    "Use 'docs-lint fix-safe --only=frontmatter' instead. Will be removed in v2.",
                    file=sys.stderr,
                )
        # Build legacy parser and dispatch
        parser = argparse.ArgumentParser()
        parser.add_argument("repos", nargs="*")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--fix-frontmatter", dest="fix_frontmatter", action="store_true")
        parser.add_argument("--fix-labels", dest="fix_labels", action="store_true")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--repo-root", dest="repo_root", action="store_true")
        args = parser.parse_args(raw)
        _legacy_main(args)
        return

    if is_subcommand or (first_pos is None and "--root" in raw):
        # New sub-command mode
        parser = argparse.ArgumentParser(prog="docs-lint")
        parser.add_argument("command", nargs="?", default="audit",
                            choices=list(_SUBCOMMANDS))
        parser.add_argument("--root", default=None,
                            help="Explicit repo root path (bypasses DEV_ROOT)")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="all",
                            choices=["all", "frontmatter", "dirs"])
        parser.add_argument("--json", dest="json_output", action="store_true")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        args = parser.parse_args(raw)
        rp = _resolve_root(args.root)

        cmd = args.command or "audit"
        if cmd == "audit":
            _run_audit(rp, no_pymarkdown=args.no_pymarkdown)
        elif cmd == "plan":
            _run_plan(rp)
        elif cmd == "fix-safe":
            _run_fix_safe(rp, only=args.only)
        elif cmd == "fix-index":
            _run_fix_index(rp, apply=args.apply)
        elif cmd == "doctor":
            _run_doctor(rp, json_output=args.json_output,
                        no_pymarkdown=args.no_pymarkdown)
        return

    # Default: legacy multi-repo mode (no sub-command, no --fix flags)
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--fix-frontmatter", dest="fix_frontmatter", action="store_true")
    parser.add_argument("--fix-labels", dest="fix_labels", action="store_true")
    parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
    parser.add_argument("--repo-root", dest="repo_root", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(raw)
    _legacy_main(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full docs test suite — verify all pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all existing tests pass + new backward-compat tests pass

- [ ] **Step 5: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/skills/docs-lint/scripts/lint.py tests/docs/test_lint_checks.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): new CLI sub-commands (audit/plan/fix-safe/fix-index/doctor) + backward compat --fix deprecation"
```

---

### Task 6b: lint.py execution tracking — plan --json, fix-safe --plan, fix-index --plan

Adds the execution tracking layer: `plan --json` outputs a deterministic action list, `fix-safe --plan FILE` applies it and writes an apply report, `fix-index --plan FILE --apply` does the same for index actions.

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/scripts/lint.py`
- Create: `tests/docs/test_execution_tracking.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/docs/test_execution_tracking.py
import json, sys
from pathlib import Path
import subprocess

_LINT = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"
_PYTHON = Path(__file__).parents[2] / ".venv/Scripts/python.exe"


def _run(args, cwd=None):
    r = subprocess.run(
        [str(_PYTHON), str(_LINT)] + args,
        capture_output=True, text=True, cwd=cwd,
    )
    return r


def test_plan_json_schema(tmp_path):
    """plan --json emits h2t_docs_fix_plan/v0.1 envelope."""
    docs = tmp_path / "docs" / "superpowers" / "specs"
    docs.mkdir(parents=True)
    (docs / "no-date-spec.md").write_text("---\ntitle: x\n---\n# x")
    r = _run(["plan", "--root", str(tmp_path), "--json"])
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["schema"] == "h2t_docs_fix_plan/v0.1"
    assert isinstance(obj["actions"], list)
    assert "plan_id" in obj


def test_plan_json_action_ids_stable(tmp_path):
    """Identical repo → same plan_id on repeated runs."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "stray.md").write_text("# orphan")
    r1 = _run(["plan", "--root", str(tmp_path), "--json"])
    r2 = _run(["plan", "--root", str(tmp_path), "--json"])
    assert json.loads(r1.stdout)["plan_id"] == json.loads(r2.stdout)["plan_id"]


def test_fix_safe_plan_writes_apply_report(tmp_path):
    """fix-safe --plan FILE writes h2t_docs_fix_apply_report/v0.1 to .h2t/."""
    # Create a file with missing frontmatter — safe fix
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    f = tmp_path / "docs" / "superpowers" / "specs" / "2026-05-28-my-spec.md"
    f.write_text("# No frontmatter here\n")

    # Generate plan
    plan_r = _run(["plan", "--root", str(tmp_path), "--json"])
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan_r.stdout)

    # Apply safe actions
    r = _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    assert r.returncode == 0, r.stderr

    # Apply report must exist
    reports = list((tmp_path / ".h2t").glob("lint-apply-*.json"))
    assert len(reports) == 1
    obj = json.loads(reports[0].read_text())
    assert obj["schema"] == "h2t_docs_fix_apply_report/v0.1"
    assert "plan_id" in obj
    assert isinstance(obj["actions"], list)


def test_fix_safe_plan_action_status_fields(tmp_path):
    """Every action in apply report has status, action_id, message."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs" / "2026-05-28-x.md").write_text("# x")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)
    _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    report = json.loads(list((tmp_path / ".h2t").glob("lint-apply-*.json"))[0].read_text())
    for action in report["actions"]:
        assert "action_id" in action
        assert action["status"] in {"applied", "skipped", "failed", "waived"}
        assert "message" in action


def test_fix_index_plan_apply_writes_report(tmp_path):
    """fix-index --plan FILE --apply writes apply report."""
    readme = tmp_path / "docs" / "README.md"
    (tmp_path / "docs").mkdir()
    readme.write_text("# Docs\n")
    (tmp_path / "docs" / "superpowers").mkdir()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)

    r = _run(["fix-index", "--root", str(tmp_path), "--plan", str(plan_path), "--apply"])
    assert r.returncode == 0, r.stderr
    reports = list((tmp_path / ".h2t").glob("lint-apply-*.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text())["schema"] == "h2t_docs_fix_apply_report/v0.1"


def test_waived_actions_appear_in_report(tmp_path):
    """Actions skipped due to requires_confirmation appear as waived, not missing."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "orphan.md").write_text("# Orphan\n")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)
    _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    report = json.loads(list((tmp_path / ".h2t").glob("lint-apply-*.json"))[0].read_text())
    statuses = {a["status"] for a in report["actions"]}
    # Orphan action is review-risk → waived by fix-safe
    assert "waived" in statuses
```

- [ ] **Step 2: Run tests to confirm they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_execution_tracking.py -v
```

Expected: ImportError or AttributeError (plan/fix-safe/fix-index sub-commands not yet wired).

- [ ] **Step 3: Wire `plan --json` into lint.py**

In `cmd_plan(args)` (or a new `cmd_plan` function), after collecting all findings:

```python
from docs.fix_plan import build_fix_plan

def cmd_plan(args):
    repo_root = _resolve_root(args)
    findings = _collect_all_findings(repo_root)
    if args.json:
        plan = build_fix_plan(repo_root=repo_root, findings=findings)
        print(json.dumps(plan, indent=2))
        return
    # ... existing human-readable plan output ...
```

Add `--json` flag to `plan` sub-parser:

```python
p_plan = sub.add_parser("plan", help="Show prioritised fix plan")
p_plan.add_argument("--root", default=None)
p_plan.add_argument("--json", action="store_true")
```

- [ ] **Step 4: Wire `fix-safe --plan FILE` into lint.py**

```python
from docs.apply_report import build_apply_report, action_result, file_hash
import time, os

def cmd_fix_safe(args):
    repo_root = _resolve_root(args)

    if args.plan:
        plan = json.loads(Path(args.plan).read_text())
        results = []
        for act in plan["actions"]:
            if act["risk"] in {"review", "destructive"} or act.get("requires_confirmation"):
                results.append(action_result(act["action_id"], "waived",
                                             "skipped: requires_confirmation or risk > safe"))
                continue
            bh = file_hash(act.get("path", ""))
            try:
                _apply_safe_action(repo_root, act)
                ah = file_hash(act.get("path", ""))
                results.append(action_result(act["action_id"], "applied",
                                             before_hash=bh, after_hash=ah))
            except Exception as exc:
                results.append(action_result(act["action_id"], "failed", str(exc),
                                             before_hash=bh))
        report = build_apply_report(plan_id=plan["plan_id"],
                                    run_id=f"fix-safe-{int(time.time())}",
                                    actions=results)
        report_dir = repo_root / ".h2t"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"lint-apply-{int(time.time())}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Apply report: {report_path}")
        return
    # ... existing fix-safe logic (no plan) ...
```

Add `--plan` flag to `fix-safe` sub-parser:

```python
p_fix_safe = sub.add_parser("fix-safe", help="Apply safe fixes (frontmatter, dirs)")
p_fix_safe.add_argument("--root", default=None)
p_fix_safe.add_argument("--plan", default=None, metavar="FILE")
```

- [ ] **Step 5: Wire `fix-index --plan FILE --apply` into lint.py**

```python
def cmd_fix_index(args):
    repo_root = _resolve_root(args)
    if args.plan and args.apply:
        plan = json.loads(Path(args.plan).read_text())
        index_actions = [a for a in plan["actions"] if a["action_type"] == "add_to_index"]
        results = []
        for act in index_actions:
            try:
                _apply_index_action(repo_root, act)
                results.append(action_result(act["action_id"], "applied"))
            except Exception as exc:
                results.append(action_result(act["action_id"], "failed", str(exc)))
        report = build_apply_report(plan_id=plan["plan_id"],
                                    run_id=f"fix-index-{int(time.time())}",
                                    actions=results)
        report_dir = repo_root / ".h2t"
        report_dir.mkdir(exist_ok=True)
        (report_dir / f"lint-apply-{int(time.time())}.json").write_text(
            json.dumps(report, indent=2))
        return
    # ... existing dry-run / --apply without --plan logic ...
```

Add `--plan` flag to `fix-index` sub-parser:

```python
p_fix_index = sub.add_parser("fix-index", help="Rebuild docs/README.md index")
p_fix_index.add_argument("--root", default=None)
p_fix_index.add_argument("--apply", action="store_true")
p_fix_index.add_argument("--plan", default=None, metavar="FILE")
```

- [ ] **Step 6: Run tests — all must pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_execution_tracking.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 7: Run full docs test suite — no regressions**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/skills/docs-lint/scripts/lint.py plugins/h2t-dev/lib/docs/fix_plan.py plugins/h2t-dev/lib/docs/apply_report.py tests/docs/test_execution_tracking.py
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "feat(docs-lint): execution tracking — plan --json, fix-safe --plan, fix-index --plan + apply reports"
```

---

### Task 7: Update SKILL.md to new contract

**Files:**
- Modify: `plugins/h2t-dev/skills/docs-lint/SKILL.md`

- [ ] **Step 1: Replace SKILL.md content**

Write `plugins/h2t-dev/skills/docs-lint/SKILL.md`:

```markdown
---
name: h2t-dev:docs-lint
description: >-
  Use when checking docs compliance, linting documentation, verifying standards,
  or auditing documentation structure and navigation across h2t repos.
  Modes: audit (default), plan, fix-safe, fix-index, doctor --json.
  Use --root PATH for repos outside C:/dev (e.g. C:/work/rejuve).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# docs-lint

Run documentation health check across h2t repos.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
```

## Modes

Check is ordered: navigation → naming → structure → metadata.
**Do not stop after frontmatter issues** if navigation or naming findings exist.

### audit (default): show all findings

```bash
# Current repo (auto-detect from cwd):
$H2T_PYTHON "$LINT" audit

# Explicit path (for repos outside C:/dev):
$H2T_PYTHON "$LINT" audit --root C:/work/rejuve

# Named repo:
$H2T_PYTHON "$LINT" audit --root C:/dev/h2t-skills
```

### plan: human-readable cleanup plan

```bash
$H2T_PYTHON "$LINT" plan --root C:/work/rejuve
```

No writes. Shows orphans, naming fixes, structure issues in priority order.

### fix-safe: apply only safe mechanical fixes

```bash
# All safe fixes (create missing dirs, add missing frontmatter):
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve

# Frontmatter only:
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve --only frontmatter

# Dirs only:
$H2T_PYTHON "$LINT" fix-safe --root C:/work/rejuve --only dirs
```

**Safe = create dirs, add frontmatter. NOT safe = rename, move, delete, rewrite README.**

### fix-index: rebuild docs/README.md navigation

```bash
# Dry run (always run first):
$H2T_PYTHON "$LINT" fix-index --root C:/work/rejuve

# Apply (writes README.md atomically):
$H2T_PYTHON "$LINT" fix-index --root C:/work/rejuve --apply
```

Uses `<!-- h2t-index-start -->` / `<!-- h2t-index-end -->` markers.
First run on README without markers appends section (dry-run) — requires `--apply` to write.
Manual content outside markers is preserved.

### doctor --json: machine-readable report

```bash
$H2T_PYTHON "$LINT" doctor --root C:/work/rejuve --json
```

Outputs `h2t_lifecycle_report/v0.1` JSON to stdout.
Use for hooks, CI, and agent pipelines.

## Legacy Multi-Repo Mode (still works)

```bash
# Check specific repos:
$H2T_PYTHON "$LINT" h2t-graphs h2t-skills

# Check all repos:
$H2T_PYTHON "$LINT" --all

# Fix missing dirs (deprecated → use fix-safe):
$H2T_PYTHON "$LINT" --fix h2t-graphs   # emits deprecation warning
```

## Hook Usage

```bash
# In hooks — must complete within H2T_LINT_HOOK_TIMEOUT (default 8s):
H2T_LINT_HOOK_TIMEOUT=8 $H2T_PYTHON "$LINT" doctor --root . --json > .h2t-lint-cache.json
```

## Output

Show full output to user. If findings > 0:
1. Report navigation/orphan findings first
2. Then naming issues with proposed renames
3. Then structure issues
4. Frontmatter issues last
5. Suggest `fix-safe` for auto-fixable items

**Do not suggest renaming or moving files in `fix-safe` — those require plan + user confirmation.**

## References

Load on demand when needed:

- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/naming-conventions.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md`
```

- [ ] **Step 2: Verify the SKILL.md frontmatter is valid**

```
C:/dev/h2t-skills/.venv/Scripts/python -c "
import sys; sys.path.insert(0, 'plugins/h2t-dev/lib')
from docs.common import parse_frontmatter
text = open('plugins/h2t-dev/skills/docs-lint/SKILL.md').read()
fm = parse_frontmatter(text)
assert fm['name'] == 'h2t-dev:docs-lint'
assert fm['metadata']['version'] == '2.0.0'
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup add plugins/h2t-dev/skills/docs-lint/SKILL.md
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit -m "docs(docs-lint): update SKILL.md to new contract — 5 modes, navigation-first order, --root PATH"
```

---

### Task 8: Dogfood acceptance on h2t-skills and rejuve

Verify the full execution tracking cycle works on real repos: doctor → plan → fix-safe → doctor (confirm resolution).

**Files:** None created. Apply reports land in `<repo>/.h2t/lint-apply-*.json`.

- [ ] **Step 1: Run full test suite — all tests must pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

Expected: all tests pass. Fix any regressions before proceeding.

- [ ] **Step 2: doctor --json baseline on h2t-skills worktree**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup --json
```

Expected: valid JSON with `"schema": "h2t_lifecycle_report/v0.1"`. Note the `"report_id"` and count of findings. Save baseline findings count.

- [ ] **Step 3: plan --json → save to file**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py plan --root C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup --json > /tmp/h2t-lint-plan.json
```

Expected: JSON file with `"schema": "h2t_docs_fix_plan/v0.1"`, `"plan_id"` field, and `"actions"` list. Verify plan_id is non-empty. Actions should have `action_id`, `risk`, `requires_confirmation` fields.

- [ ] **Step 4: fix-safe --plan → apply safe actions**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py fix-safe --root C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup --plan /tmp/h2t-lint-plan.json
```

Expected:
- Exits 0
- Prints apply report path (e.g. `.h2t/lint-apply-1234567890.json`)
- Apply report has `"schema": "h2t_docs_fix_apply_report/v0.1"`
- `"actions"` list has entries with status `applied`, `skipped`, or `waived`
- Waived entries (requires_confirmation or risk > safe) must appear in the list — NOT silently dropped

- [ ] **Step 5: doctor --json after fix — verify resolution**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup --json
```

Expected: findings count is equal to or less than baseline from Step 2. Specifically:
- Findings that were addressed by `applied` actions should no longer appear
- Findings for `waived` actions may still appear (by design — they need manual review)
- No new finding types introduced by the fix run

If findings count did not decrease despite applied actions: investigate — a fix may have been applied but the check logic doesn't re-read from disk. Fix the check function, not the test.

- [ ] **Step 6: Run doctor --json on rejuve (outside C:/dev)**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/work/rejuve --json
```

Expected:
- No false `missing standards files` noise (global standards check skipped for `--root` mode)
- `status` reflects actual rejuve doc state

If `C:/work/rejuve` does not exist, run against a sibling repo at a non-DEV_ROOT path instead.

- [ ] **Step 7: Run plan on rejuve (human-readable output)**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py plan --root C:/work/rejuve
```

Expected: shows orphan and naming sections first (not frontmatter first).

- [ ] **Step 8: Run fix-index dry-run on h2t-skills worktree**

```
C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py fix-index --root C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup
```

Expected: shows operation (append or replace), does NOT write README.md.

- [ ] **Step 9: Commit acceptance evidence note**

```
git -C C:/dev/h2t-skills/.claude/worktrees/lifecycle-skill-cleanup commit --allow-empty -m "test(docs-lint): dogfood acceptance complete on h2t-skills + rejuve — closes #240"
```

---

## Checklist Summary

- [ ] Task 1: reporter.py + tests (7 tests pass)
- [ ] Task 1.5: fix_plan.py + apply_report.py + tests (15 tests pass)
- [ ] Task 2: orphan.py + tests (8 tests pass)
- [ ] Task 3: naming.py + tests (11 tests pass)
- [ ] Task 4: config.py + tests (5 tests pass)
- [ ] Task 5: index_builder.py + tests (9 tests pass)
- [ ] Task 6: lint.py rewrite + backward-compat tests (all docs/ tests pass)
- [ ] Task 6b: execution tracking — plan --json, fix-safe --plan, fix-index --plan + apply reports (6 tests pass)
- [ ] Task 7: SKILL.md updated to v2.0.0
- [ ] Task 8: Dogfood — doctor→plan→fix-safe→doctor cycle on h2t-skills (resolution verified) + rejuve audit

## Deferred (not in #240 scope)

- Hook timeout/cache enforcement (`H2T_LINT_HOOK_TIMEOUT` env var is documented but not enforced in lint.py; hook wrapper handles the timeout)
- Concurrency: both index_builder.py and fix_frontmatter_action use atomic os.replace(). Multiple parallel runs on the same file remain last-writer-wins, acceptable for v1.
- Structure.py as separate module (structure checks remain inline in lint.py for now — extract if lint.py exceeds 400 LOC in a follow-up)
