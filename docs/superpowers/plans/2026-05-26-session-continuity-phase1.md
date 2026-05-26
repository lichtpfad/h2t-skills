# Session Continuity Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `session-start` and `handoff` use bounded machine-readable continuity as the default runtime path, keep the existing confirmation-gated UX, and demote markdown handoff to a secondary mirror without breaking Claude-compatible gather/injection.

**Architecture:** This phase is intentionally local-first. It keeps the current gather/hook contract, keeps `latest.json` as the canonical local continuity file, and changes the runtime so repo sessions read only bounded state instead of scanning archival markdown by default. `handoff` still writes markdown, but bounded state becomes primary and markdown failure becomes a surfaced degraded-success case instead of a hard dependency.

**Tech Stack:** Python 3.11+, existing `plugins/h2t-core` skill runtime, `pytest`, local JSON files under `~/.h2t/sessions`, no POS network sync in this phase

---

## Scope Check

The redesign spec includes two distinct tracks:

1. local continuity/runtime behavior;
2. POS session sync and future authoritative registry migration.

This plan covers only **track 1**. POS event emission schema alignment remains documented in:

- `docs/superpowers/specs/2026-05-26-session-continuity-redesign.md`
- `docs/superpowers/specs/2026-05-26-session-continuity-pos-alignment-note.md`

Do **not** expand this implementation wave into POS ingestion, non-repo persistence, or network sync.

## File Structure

### Files to modify

- `plugins/h2t-core/lib/gather/sessions.py`
  - Keep repo-session lookup on `latest.json`
  - Bound and normalize the continuity payload
  - Stop making archival markdown enumeration a default runtime dependency

- `plugins/h2t-core/lib/gather/test_sessions.py`
  - Add tests for repo-only lookup guarantees
  - Add tests proving missing markdown does not break continuity lookup
  - Add tests proving non-repo/generalized lookup is intentionally absent in v1

- `plugins/h2t-core/skills/handoff/scripts/writer.py`
  - Keep confirmation-gated write flow
  - Make `latest.json` the primary artifact
  - Make markdown write failure return degraded-success
  - De-duplicate generated artifacts/next-actions before persistence

- `plugins/h2t-core/skills/handoff/scripts/test_writer.py`
  - Add degraded-success tests
  - Add dedupe tests
  - Keep bounded `latest.json` tests

- `plugins/h2t-core/skills/session-start/SKILL.md`
  - Remove default reliance on archival handoff file lists
  - Preserve injected `BRIEFING + GATHER_META` flow
  - Fix the current Graph Integration regression by restoring a valid Python execution path

- `plugins/h2t-core/skills/handoff/SKILL.md`
  - Keep confirmation gate
  - Update wording so markdown is treated as mirror, not canonical continuity memory
  - Surface degraded mirror behavior in confirmation/output wording

- `tests/core/test_skill_entrypoints.py`
  - Extend the existing entrypoint/skill wiring tests
  - Add assertions for the updated skill instructions if this repo remains the source of truth for those skill texts

### Files to create

- `h2t_ops/handoff_entry.py`
  - Thin installable wrapper around `plugins/h2t-core/skills/handoff/scripts/writer.py`

### Files to modify for packaging

- `pyproject.toml`
  - Add `h2t-handoff` entrypoint

## Task 1: Tighten Repo-Only Continuity Lookup

**Files:**
- Modify: `plugins/h2t-core/lib/gather/sessions.py`
- Test: `plugins/h2t-core/lib/gather/test_sessions.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `plugins/h2t-core/lib/gather/test_sessions.py`:

```python
def test_find_latest_session_index_returns_none_when_only_markdown_exists(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    md = root / "machine-a" / "repo" / "old.md"
    md.parent.mkdir(parents=True)
    md.write_text("legacy handoff", encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    result = find_latest_session_index("repo")

    assert result is None


def test_find_latest_session_index_uses_newest_latest_json_only(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    older = root / "machine-a" / "repo" / "latest.json"
    newer = root / "machine-b" / "repo" / "latest.json"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_text(json.dumps({"version": 1, "session_id": "older"}), encoding="utf-8")
    newer.write_text(json.dumps({"version": 1, "session_id": "newer"}), encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    newer.touch()

    result = find_latest_session_index("repo")

    assert result is not None
    assert result["session_id"] == "newer"


def test_find_latest_session_index_repo_lookup_is_v1_boundary(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    latest = root / "machine-a" / "project-only" / "latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps({"version": 1, "session_id": "s1"}), encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    result = find_latest_session_index("non-repo-context")

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest plugins/h2t-core/lib/gather/test_sessions.py -q
```

Expected: at least one new test fails because the current implementation still treats the older session layout too loosely for the intended v1 boundary.

- [ ] **Step 3: Write minimal implementation**

Update `plugins/h2t-core/lib/gather/sessions.py` so repo continuity lookup stays strict and bounded. The implementation should preserve the existing public function name, but make the v1 boundary obvious:

```python
def find_latest_session_index(repo_name: str) -> dict | None:
    """Find newest bounded latest.json for a repo-scoped session."""
    if not repo_name or "/" in repo_name and repo_name.startswith("project:"):
        return None

    root = _session_root()
    if not root.exists():
        return None

    candidates: list[Path] = []
    for machine_dir in root.iterdir():
        if not machine_dir.is_dir():
            continue
        latest = machine_dir / repo_name / "latest.json"
        if latest.is_file():
            candidates.append(latest)

    if not candidates:
        return None

    path = max(candidates, key=os.path.getmtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return _bound_latest_index(data, path)
```

Also add a short module-level comment above `find_session_files()` clarifying it is archival discovery and not the default runtime continuity path.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest plugins/h2t-core/lib/gather/test_sessions.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/lib/gather/sessions.py plugins/h2t-core/lib/gather/test_sessions.py
git commit -m "fix(session): tighten repo continuity lookup"
```

## Task 2: Make Handoff State Primary and Markdown Mirror Secondary

**Files:**
- Modify: `plugins/h2t-core/skills/handoff/scripts/writer.py`
- Test: `plugins/h2t-core/skills/handoff/scripts/test_writer.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `plugins/h2t-core/skills/handoff/scripts/test_writer.py`:

```python
def test_write_handoff_deduplicates_artifacts(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    result = writer.write_handoff(
        session_id="dev-repo-dedupe-2026-05-26",
        domain="dev",
        project="repo",
        what_done="- added deploy\n- added deploy",
        what_remains="- [ ] ship release\n- [ ] ship release",
        artifacts=["commit:abc123", "commit:abc123", "issue:185"],
    )

    latest = json.loads(Path(result["latest"]).read_text(encoding="utf-8"))
    refs = [(item["type"], item["ref"]) for item in latest["artifacts"]]

    assert refs == [("commit", "abc123"), ("issue", "185")]
    assert latest["next_actions"] == ["ship release"]


def test_write_handoff_returns_degraded_when_markdown_write_fails(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    original_write_text = Path.write_text

    def fail_only_markdown(self, content, encoding="utf-8"):
        if self.name.endswith(".md"):
            raise OSError("mirror write failed")
        return original_write_text(self, content, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", fail_only_markdown)

    result = writer.write_handoff(
        session_id="dev-repo-degraded-2026-05-26",
        domain="dev",
        project="repo",
        what_done="- finished task",
        what_remains="- [ ] next task",
        artifacts=["commit:abc123"],
    )

    assert result["status"] == "degraded"
    assert result["mirror_write_failed"] is True
    assert Path(result["latest"]).is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest plugins/h2t-core/skills/handoff/scripts/test_writer.py -q
```

Expected: FAIL because dedupe and degraded-success are not implemented.

- [ ] **Step 3: Write minimal implementation**

Update `plugins/h2t-core/skills/handoff/scripts/writer.py` with three small helpers and a degraded path.

Add helper functions near `_extract_items()`:

```python
def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_artifacts(values: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for value in values:
        key = (value.get("type", "artifact"), value.get("ref", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append({"type": key[0], "ref": key[1]})
    return result
```

Update `_build_latest_index()`:

```python
def _build_latest_index(
    *,
    session_id: str,
    domain: str,
    project: str,
    what_done: str,
    what_remains: str,
    artifacts: list[dict],
    markdown_path: Path | None,
    updated_at: datetime,
) -> dict:
    summary_short, summary_truncated = _truncate(what_done, SUMMARY_LIMIT)
    next_actions, actions_truncated = _extract_items(what_remains)
    next_actions = _dedupe_preserving_order(next_actions)
    artifact_rows = _dedupe_artifacts(artifacts)[:MAX_ARTIFACTS]
    truncated = summary_truncated or actions_truncated or len(artifacts) > MAX_ARTIFACTS
    return {
        "version": 1,
        "session_id": session_id,
        "project": project,
        "domain": domain,
        "updated_at": updated_at.isoformat(),
        "summary_short": summary_short,
        "next_actions": next_actions,
        "blockers": [],
        "artifacts": artifact_rows,
        "markdown_path": str(markdown_path) if markdown_path else "",
        "truncated": truncated,
    }
```

Update `write_handoff()` so it writes `latest.json` even if markdown fails:

```python
    md_dir = Path(markdown_dir) if markdown_dir else default_markdown_dir(project)
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{session_id}.md"

    now = datetime.now(timezone.utc)
    markdown_failed = False
    try:
        md_path.write_text(md_content, encoding="utf-8")
        persisted_md_path: Path | None = md_path
    except OSError:
        markdown_failed = True
        persisted_md_path = None

    latest = _build_latest_index(
        session_id=session_id,
        domain=domain,
        project=project,
        what_done=what_done,
        what_remains=what_remains,
        artifacts=parsed_artifacts,
        markdown_path=persisted_md_path,
        updated_at=now,
    )
    latest_path = md_dir / "latest.json"
    _write_json_atomic(latest_path, latest)

    return {
        "status": "degraded" if markdown_failed else "ok",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": str(md_path) if not markdown_failed else "",
        "latest": str(latest_path),
        "artifacts": len(latest["artifacts"]),
        "mirror_write_failed": markdown_failed,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest plugins/h2t-core/skills/handoff/scripts/test_writer.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/handoff/scripts/writer.py plugins/h2t-core/skills/handoff/scripts/test_writer.py
git commit -m "fix(handoff): make latest state primary over markdown mirror"
```

## Task 3: Package Handoff Writer and Repair Skill Contracts

**Files:**
- Create: `h2t_ops/handoff_entry.py`
- Modify: `pyproject.toml`
- Modify: `plugins/h2t-core/skills/handoff/SKILL.md`
- Modify: `plugins/h2t-core/skills/session-start/SKILL.md`
- Test: `tests/core/test_skill_entrypoints.py`

- [ ] **Step 1: Write the failing tests**

Extend `tests/core/test_skill_entrypoints.py` with:

```python
from h2t_ops import handoff_entry


def test_handoff_entry_delegates_to_handoff_writer(monkeypatch):
    calls: list[str] = []

    def fake_run(relative_path: str) -> int:
        calls.append(relative_path)
        return 0

    monkeypatch.setattr(handoff_entry, "run_plugin_main", fake_run)
    assert handoff_entry.main() == 0
    assert calls == ["skills/handoff/scripts/writer.py"]


def test_handoff_skill_uses_installable_entrypoint():
    skill_path = Path("plugins/h2t-core/skills/handoff/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert "command -v h2t-handoff" in text
    assert "h2t-handoff write \\" in text
    assert '${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py' not in text


def test_session_start_skill_keeps_graph_python_resolution():
    skill_path = Path("plugins/h2t-core/skills/session-start/SKILL.md")
    text = skill_path.read_text(encoding="utf-8")
    assert 'source "${CLAUDE_PLUGIN_ROOT}/scripts/resolve-h2t-python.sh"' in text
    assert "resolve_h2t_python" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest tests/core/test_skill_entrypoints.py -q
```

Expected: FAIL because `h2t-handoff` entrypoint and updated skill wiring do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `h2t_ops/handoff_entry.py`:

```python
"""Installable entrypoint for handoff writer."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/handoff/scripts/writer.py")
```

Update `pyproject.toml`:

```toml
[project.scripts]
h2t-ops = "h2t_ops.cli:main"
h2t-gather = "h2t_ops.gather_entry:main"
h2t-activity-log = "h2t_ops.activity_log_entry:main"
h2t-handoff = "h2t_ops.handoff_entry:main"
```

Update `plugins/h2t-core/skills/handoff/SKILL.md` setup and write step:

```bash
command -v h2t-handoff >/dev/null 2>&1 || {
  echo "ERROR: h2t-handoff not found. Run: uv tool install --editable C:/dev/h2t-skills"
  exit 1
}
```

and:

```bash
h2t-handoff write \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>" \
  --what-done "<WHAT_DONE>" \
  --what-remains "<WHAT_REMAINS>" \
  --artifacts <ARTIFACT_LIST>
```

Update `plugins/h2t-core/skills/session-start/SKILL.md` setup so it keeps the working graph integration contract:

```bash
command -v h2t-gather >/dev/null 2>&1 || {
  echo "ERROR: h2t-gather not found. Run: uv tool install --editable C:/dev/h2t-skills"
  exit 1
}
command -v h2t-activity-log >/dev/null 2>&1 || {
  echo "ERROR: h2t-activity-log not found. Run: uv tool install --editable C:/dev/h2t-skills"
  exit 1
}
source "${CLAUDE_PLUGIN_ROOT}/scripts/resolve-h2t-python.sh"
resolve_h2t_python || { echo "ERROR: no working Python found for h2t graph integration"; exit 1; }
```

Also tighten the “Previous-session context” section so it no longer encourages archival file thinking:

```markdown
If `GATHER_RESULT.latest_session` is missing: skip this step silently.
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest tests/core/test_skill_entrypoints.py -q
uv.exe run h2t-handoff --help
```

Expected:
- pytest PASS
- `h2t-handoff --help` prints the handoff writer CLI help

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml h2t_ops/handoff_entry.py plugins/h2t-core/skills/handoff/SKILL.md plugins/h2t-core/skills/session-start/SKILL.md tests/core/test_skill_entrypoints.py
git commit -m "feat(skills): package handoff writer entrypoint"
```

## Task 4: Verify End-to-End Local Runtime Behavior

**Files:**
- Modify: `docs/superpowers/specs/2026-05-26-session-continuity-redesign.md`
- Modify: `docs/superpowers/specs/2026-05-26-session-continuity-pos-alignment-note.md`

- [ ] **Step 1: Run focused runtime verification**

Run:

```bash
uv.exe run pytest plugins/h2t-core/lib/gather/test_sessions.py plugins/h2t-core/skills/handoff/scripts/test_writer.py tests/core/test_skill_entrypoints.py -q
```

Expected: PASS

- [ ] **Step 2: Run local continuity smoke**

Run:

```bash
uv.exe run h2t-gather --cwd . --format-briefing
```

Expected:
- JSON output
- `_briefing` present
- no requirement to inspect archival markdown for default continuity

- [ ] **Step 3: Run local handoff smoke**

Run:

```bash
$env:H2T_SESSION_ROOT="C:/tmp/h2t-session-smoke"
$env:H2T_ACTIVITY_SPOOL="C:/tmp/h2t-session-smoke/spool.jsonl"
uv.exe run h2t-handoff write --session-id "dev-h2t-skills-smoke-2026-05-26" --domain "dev" --project "h2t-skills" --what-done "- shipped continuity phase 1" --what-remains "- [ ] write POS sync plan" --artifacts commit:abc123
Get-Content C:/tmp/h2t-session-smoke/*/h2t-skills/latest.json
```

Expected:
- writer returns JSON with `status: "ok"` or `status: "degraded"`
- `latest.json` exists
- `summary_short` and bounded `next_actions` are present

- [ ] **Step 4: Record implementation notes**

Append a short “Implementation Status” note to both spec files:

```markdown
## Implementation Status

- Phase 1 local continuity landed
- repo-session lookup is the only guaranteed continuity lookup in v1
- markdown is still written by default but no longer treated as canonical runtime memory
- POS sync remains deferred to a later implementation wave
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-26-session-continuity-redesign.md docs/superpowers/specs/2026-05-26-session-continuity-pos-alignment-note.md
git commit -m "docs(session): record phase 1 continuity implementation status"
```

## Self-Review

### Spec coverage

- Preserve gather/injection pipeline: covered in Task 3 skill/runtime contract
- Runtime continuity machine-readable first: covered in Tasks 1-2
- Markdown demoted to mirror: covered in Task 2
- Preserve handoff confirmation workflow: preserved by not changing the write gate; documented in Task 3 skill contract
- Repo-only v1 lookup: covered in Task 1
- Degraded mirror behavior: covered in Task 2
- POS sync boundary only, no implementation: preserved by keeping Task 4 docs-only

No spec gaps remain for **Phase 1 local continuity**. POS event emission and generalized non-code persistence are intentionally deferred.

### Placeholder scan

Checked for:
- `TBD`
- `TODO`
- “appropriate error handling”
- “similar to task”
- undefined files/functions

No placeholders remain.

### Type consistency

- `latest.json` stays on `summary_short`, `next_actions`, `artifacts`, `blockers`, `truncated`
- degraded result shape consistently uses:
  - `status`
  - `mirror_write_failed`
- entrypoint function names consistently use:
  - `main()`
  - `run_plugin_main(...)`

No naming drift remains across tasks.
