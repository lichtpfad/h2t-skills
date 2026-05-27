# Research Maintenance Doctor Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local maintenance commands for `h2t-ops research` that can inspect research store health, rebuild navigation indexes from canonical JSON objects, and report safe cleanup candidates without deleting canonical research objects.

**Architecture:** Add a read-mostly `maintenance.py` module beside `store.py` and `navigation.py`. `doctor()` reports health findings, `rebuild_indexes()` regenerates cache indexes from canonical objects, and `cleanup()` returns a dry-run cleanup plan for non-canonical artifacts. `ResearchClient` and CLI commands expose these helpers without changing provider workflows.

**Tech Stack:** Python stdlib (`json`, `pathlib`, `datetime`), existing `h2t_ops.connectors.research.store` path helpers, existing `h2t_ops.core.errors`, pytest, `h2t-ops` argparse command surface.

---

## Issue And Boundary

GitHub issue: `#193 research: retention cleanup and index doctor`.

This plan is only for local research artifact maintenance.

In scope:

- `h2t-ops research doctor`
- `h2t-ops research rebuild-indexes`
- `h2t-ops research cleanup --dry-run`
- documented retention classes
- tests for broken refs, stale indexes, rebuild, dry-run cleanup

Out of scope:

- provider key routing (`#194`)
- POS ingestion
- link object model / `links.index.json`
- billing dashboards
- deleting canonical object JSON by default
- fixing malformed canonical objects automatically

## File Structure

- Create: `h2t_ops/connectors/research/maintenance.py`
  - Pure local maintenance helpers.
  - Reads canonical object JSON from `objects/documents`, `objects/threads`, `objects/runs`, `objects/syntheses`.
  - Reports doctor findings.
  - Rebuilds `indexes/documents.index.json`, `indexes/threads.index.json`, `indexes/syntheses.index.json`, `indexes/aliases.index.json`.
  - Produces cleanup dry-run plan for non-canonical files.
- Create: `tests/connectors/research/test_maintenance.py`
  - Unit tests for doctor/rebuild/cleanup.
- Modify: `h2t_ops/connectors/research/client.py`
  - Add thin `ResearchClient` wrappers.
- Modify: `h2t_ops/connectors/research/commands.py`
  - Add CLI parser/dispatch for `doctor`, `rebuild-indexes`, `cleanup`.
- Modify: `tests/connectors/research/test_client.py`
  - Client wrapper tests.
- Modify: `tests/connectors/research/test_commands.py`
  - Parser/dispatch and CLI fixture tests.
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
  - Document maintenance commands and retention policy.
- Create: `docs/reports/2026-05-27-research-maintenance-smoke.md`
  - Local smoke evidence.

## Contracts To Preserve

- Canonical object JSON under `objects/**` is source truth.
- Index files under `indexes/*.index.json` are rebuildable caches.
- Markdown mirrors are human review surfaces only.
- `doctor` is read-only.
- `rebuild-indexes` writes only index files.
- `cleanup` defaults to `--dry-run`; non-dry-run execution is not implemented in this v1 plan.
- CLI `cleanup` v1 requires an explicit `--dry-run` flag and has no execute flag.
- `cleanup` must never propose deleting canonical object JSON.
- Missing index files are not errors; they are rebuildable.
- Malformed canonical object JSON is an `error` finding, not auto-fixed.
- Stale index refs are `warning` findings because `rebuild-indexes` can repair them.
- Missing artifact refs are `warning` findings because canonical object JSON remains valid.
- Nullable artifact refs are ignored; non-empty string artifact refs are checked relative to the research root unless absolute.
- v1 alias rebuild only regenerates document URL aliases from `canonical_url` and `source_url`; non-URL/manual alias types are out of scope until aliases become canonical objects.

## Data Shapes

All public maintenance helpers return dict envelopes:

```python
{
    "kind": "research_doctor",
    "root": "C:/tmp/research",
    "status": "ok|warning|error",
    "counts": {"errors": 0, "warnings": 0, "info": 0},
    "findings": [
        {
            "severity": "warning",
            "code": "alias_target_missing",
            "message": "alias target object does not exist",
            "path": "C:/tmp/research/indexes/aliases.index.json",
            "object_type": "document",
            "object_id": "research-doc:missing",
        }
    ],
}
```

```python
{
    "kind": "research_rebuild_indexes",
    "root": "C:/tmp/research",
    "written": [
        "C:/tmp/research/indexes/documents.index.json",
        "C:/tmp/research/indexes/threads.index.json",
        "C:/tmp/research/indexes/syntheses.index.json",
        "C:/tmp/research/indexes/aliases.index.json",
    ],
    "counts": {
        "documents": 1,
        "threads": 1,
        "runs": 1,
        "syntheses": 1,
        "aliases": 1,
    },
}
```

```python
{
    "kind": "research_cleanup",
    "root": "C:/tmp/research",
    "dry_run": True,
    "policy": {
        "delete_canonical_objects": False,
        "delete_indexes": False,
        "delete_unreferenced_partial_md": True,
    },
    "count": 1,
    "candidates": [
        {
            "path": "C:/tmp/research/orphan.partial.md",
            "reason": "unreferenced_partial_markdown",
            "action": "would_delete",
        }
    ],
}
```

---

### Task 0: Branch And Worktree Hygiene

**Files:**
- No file edits.

- [ ] **Step 1: Check current branch and dirty state**

Run:

```powershell
git status -sb
```

Expected:

- current branch is `main`
- unrelated local dirty files may exist:
  - `docs/README.md`
  - `uv.lock`
  - `docs/handoffs/`
  - unrelated untracked plan files

Do not stage or modify unrelated files.

- [ ] **Step 2: Sync main**

Run:

```powershell
git pull --ff-only origin main
```

Expected:

- local `main` is current with `origin/main`
- no unrelated file content changes are staged

- [ ] **Step 3: Verify `main` is not ahead before branching**

Run:

```powershell
git log --oneline origin/main..HEAD
```

Expected:

- no output

If this prints commits, do not create the #193 branch from local `main`; those commits would leak into the #193 PR. Either stop and ask the operator, or create the feature branch directly from `origin/main` in Step 4.

- [ ] **Step 4: Create feature branch from the clean remote base**

Run:

```powershell
git switch --create codex-research-maintenance-doctor-cleanup origin/main
```

Expected:

- branch changes to `codex-research-maintenance-doctor-cleanup`
- branch base is `origin/main`, not a local ahead commit

---

### Task 1: Maintenance Module Skeleton And Object Loading

**Files:**
- Create: `h2t_ops/connectors/research/maintenance.py`
- Create: `tests/connectors/research/test_maintenance.py`

- [ ] **Step 1: Write failing tests for canonical object loading and malformed object findings**

Create `tests/connectors/research/test_maintenance.py` with:

```python
from __future__ import annotations

import json

from h2t_ops.connectors.research import maintenance, store


def test_doctor_reports_malformed_canonical_object_as_error(tmp_path):
    root = tmp_path / "research"
    path = store.object_path(root, "documents", "research-doc:bad")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json", encoding="utf-8")

    result = maintenance.doctor(root)

    assert result["kind"] == "research_doctor"
    assert result["status"] == "error"
    assert result["counts"]["errors"] == 1
    assert result["findings"][0]["severity"] == "error"
    assert result["findings"][0]["code"] == "object_json_invalid"
    assert result["findings"][0]["path"] == str(path)


def test_doctor_reports_schema_and_id_mismatch_as_errors(tmp_path):
    root = tmp_path / "research"
    store.write_json(
        store.object_path(root, "documents", "research-doc:bad"),
        {"schema": "research_thread/v0.1", "document_id": "research-doc:other"},
    )

    result = maintenance.doctor(root)

    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "error"
    assert "object_schema_mismatch" in codes
    assert "object_id_mismatch" in codes
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- FAIL with import error for `h2t_ops.connectors.research.maintenance`

- [ ] **Step 3: Create `maintenance.py` with object metadata, safe JSON reader, and doctor skeleton**

Create `h2t_ops/connectors/research/maintenance.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.connectors.research import store
from h2t_ops.core.errors import UsageError


OBJECTS = {
    "document": ("documents", "research_document/v0.1", "document_id"),
    "thread": ("threads", "research_thread/v0.1", "thread_id"),
    "run": ("runs", "research_run/v0.1", "run_id"),
    "synthesis": ("syntheses", "research_synthesis/v0.1", "synthesis_id"),
}


def _finding(
    severity: str,
    code: str,
    message: str,
    *,
    path: Path | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        item["path"] = str(path)
    if object_type is not None:
        item["object_type"] = object_type
    if object_id is not None:
        item["object_id"] = object_id
    if ref is not None:
        item["ref"] = ref
    return item


def _read_json_file(path: Path) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, _finding(
            "error",
            "object_json_invalid",
            "canonical research object is not valid JSON",
            path=path,
        )


def _iter_object_files(root: Path, directory: str) -> list[Path]:
    base = Path(root) / "objects" / directory
    if not base.is_dir():
        return []
    return sorted(base.glob("*.json"))


def _load_objects(root: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    objects: dict[str, dict[str, dict[str, Any]]] = {
        object_type: {} for object_type in OBJECTS
    }
    findings: list[dict[str, Any]] = []
    for object_type, (directory, expected_schema, id_key) in OBJECTS.items():
        for path in _iter_object_files(root, directory):
            data, error = _read_json_file(path)
            if error is not None:
                findings.append(error)
                continue
            if not isinstance(data, dict):
                findings.append(
                    _finding(
                        "error",
                        "object_not_mapping",
                        "canonical research object must be a JSON object",
                        path=path,
                        object_type=object_type,
                    )
                )
                continue
            expected_id = path.stem
            actual_schema = data.get("schema")
            actual_id = data.get(id_key)
            if actual_schema != expected_schema:
                findings.append(
                    _finding(
                        "error",
                        "object_schema_mismatch",
                        f"expected schema {expected_schema}, got {actual_schema}",
                        path=path,
                        object_type=object_type,
                        object_id=str(actual_id or expected_id),
                    )
                )
            if actual_id != expected_id:
                findings.append(
                    _finding(
                        "error",
                        "object_id_mismatch",
                        f"expected id {expected_id}, got {actual_id}",
                        path=path,
                        object_type=object_type,
                        object_id=str(actual_id or ""),
                    )
                )
            if actual_schema == expected_schema and actual_id == expected_id:
                objects[object_type][str(actual_id)] = data
    return objects, findings


def _status(findings: list[dict[str, Any]]) -> str:
    if any(item["severity"] == "error" for item in findings):
        return "error"
    if any(item["severity"] == "warning" for item in findings):
        return "warning"
    return "ok"


def _counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "errors": sum(1 for item in findings if item["severity"] == "error"),
        "warnings": sum(1 for item in findings if item["severity"] == "warning"),
        "info": sum(1 for item in findings if item["severity"] == "info"),
    }


def doctor(root: Path) -> dict[str, Any]:
    root = Path(root)
    _objects, findings = _load_objects(root)
    return {
        "kind": "research_doctor",
        "root": str(root),
        "status": _status(findings),
        "counts": _counts(findings),
        "findings": findings,
    }


def rebuild_indexes(root: Path) -> dict[str, Any]:
    raise UsageError("research rebuild-indexes is not implemented yet")


def cleanup(root: Path, *, dry_run: bool = True) -> dict[str, Any]:
    raise UsageError("research cleanup is not implemented yet")
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- `2 passed`

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/maintenance.py tests/connectors/research/test_maintenance.py
git commit -m "feat(research): add maintenance doctor skeleton"
```

---

### Task 2: Doctor Reference Checks

**Files:**
- Modify: `h2t_ops/connectors/research/maintenance.py`
- Modify: `tests/connectors/research/test_maintenance.py`

- [ ] **Step 1: Add tests for stale indexes, alias targets, and cross-object refs**

Append to `tests/connectors/research/test_maintenance.py`:

```python
def _demo_document(root):
    document = store.build_research_document(
        canonical_url="https://example.com/post",
        source_url="https://example.com/post",
        provider="jina",
        title="Example",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="abc",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "post.partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(root, "documents", document["document_id"], document)
    return document


def test_doctor_warns_for_stale_document_index_ref(tmp_path):
    root = tmp_path / "research"
    store.write_json(
        store.index_path(root, "documents"),
        [{"document_id": "research-doc:missing", "project_ids": ["project:demo"]}],
    )

    result = maintenance.doctor(root)

    assert result["status"] == "warning"
    assert result["findings"][0]["code"] == "index_object_missing"
    assert result["findings"][0]["object_id"] == "research-doc:missing"


def test_doctor_warns_for_alias_target_missing(tmp_path):
    root = tmp_path / "research"
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/missing",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    result = maintenance.doctor(root)

    assert result["status"] == "warning"
    assert result["findings"][0]["code"] == "alias_target_missing"


def test_doctor_warns_for_missing_artifact_refs(tmp_path):
    root = tmp_path / "research"
    document = _demo_document(root)

    result = maintenance.doctor(root)

    assert result["status"] == "warning"
    codes = {finding["code"] for finding in result["findings"]}
    assert "artifact_ref_missing" in codes
    assert document["document_id"] in {
        finding.get("object_id") for finding in result["findings"]
    }


def test_doctor_warns_for_missing_run_document_and_synthesis_refs(tmp_path):
    root = tmp_path / "research"
    thread = store.build_research_thread(
        question="What is Exa?",
        created_at="2026-05-27T10:00:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["answer"],
    )
    thread["latest_synthesis_id"] = "research-synthesis:missing"
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-27T10:00:00Z",
        query="What is Exa?",
        provider_set=["exa"],
        document_ids=["research-doc:missing"],
    )
    synthesis = store.build_research_synthesis(
        thread_id="research-thread:missing",
        run_ids=["research-run:missing"],
        summary="Summary",
        created_at="2026-05-27T10:00:00Z",
    )
    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)

    result = maintenance.doctor(root)

    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "warning"
    assert "thread_latest_synthesis_missing" in codes
    assert "run_document_missing" in codes
    assert "synthesis_thread_missing" in codes
    assert "synthesis_run_missing" in codes
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- FAIL because doctor does not yet inspect index rows or cross-object refs.

- [ ] **Step 3: Implement index row and reference checks**

In `h2t_ops/connectors/research/maintenance.py`, add helpers before `doctor()`:

```python
def _read_index(root: Path, index_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = store.index_path(root, index_name)
    if not path.is_file():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], [
            _finding(
                "error",
                "index_json_invalid",
                "research index is not valid JSON",
                path=path,
            )
        ]
    if not isinstance(data, list):
        return [], [
            _finding(
                "error",
                "index_not_list",
                "research index must be a JSON list",
                path=path,
            )
        ]
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, dict):
            rows.append(row)
        else:
            findings.append(
                _finding(
                    "error",
                    "index_row_not_mapping",
                    "research index row must be a JSON object",
                    path=path,
                )
            )
    return rows, findings


def _check_index_refs(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    checks = {
        "documents": ("document", "document_id"),
        "threads": ("thread", "thread_id"),
        "syntheses": ("synthesis", "synthesis_id"),
    }
    findings: list[dict[str, Any]] = []
    for index_name, (object_type, id_key) in checks.items():
        rows, errors = _read_index(root, index_name)
        findings.extend(errors)
        for row in rows:
            object_id = str(row.get(id_key) or "")
            if object_id and object_id not in objects[object_type]:
                findings.append(
                    _finding(
                        "warning",
                        "index_object_missing",
                        "index row points to a missing canonical object",
                        path=store.index_path(root, index_name),
                        object_type=object_type,
                        object_id=object_id,
                    )
                )
    return findings


def _check_alias_refs(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows, findings = _read_index(root, "aliases")
    for row in rows:
        target_type = str(row.get("target_object_type") or "")
        target_id = str(row.get("target_id") or "")
        if target_type not in OBJECTS:
            findings.append(
                _finding(
                    "error",
                    "alias_target_type_unknown",
                    "alias row has an unknown target object type",
                    path=store.index_path(root, "aliases"),
                    object_type=target_type,
                    object_id=target_id,
                )
            )
            continue
        if target_id not in objects[target_type]:
            findings.append(
                _finding(
                    "warning",
                    "alias_target_missing",
                    "alias target object does not exist",
                    path=store.index_path(root, "aliases"),
                    object_type=target_type,
                    object_id=target_id,
                )
            )
    return findings


def _artifact_ref_path(root: Path, raw_ref: Any) -> Path | None:
    if not isinstance(raw_ref, str) or not raw_ref.strip():
        return None
    candidate = Path(raw_ref)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _check_artifact_refs(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for object_type, rows in objects.items():
        for object_id, obj in rows.items():
            refs = obj.get("artifact_refs")
            if not isinstance(refs, dict):
                continue
            for key, value in refs.items():
                path = _artifact_ref_path(root, value)
                if path is not None and not path.is_file():
                    findings.append(
                        _finding(
                            "warning",
                            "artifact_ref_missing",
                            f"artifact ref {key} does not exist",
                            path=path,
                            object_type=object_type,
                            object_id=object_id,
                            ref=key,
                        )
                    )
    return findings


def _check_cross_object_refs(
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for thread_id, thread in objects["thread"].items():
        latest = thread.get("latest_synthesis_id")
        if isinstance(latest, str) and latest and latest not in objects["synthesis"]:
            findings.append(
                _finding(
                    "warning",
                    "thread_latest_synthesis_missing",
                    "thread latest_synthesis_id points to a missing synthesis",
                    object_type="thread",
                    object_id=thread_id,
                    ref=latest,
                )
            )
    for run_id, run in objects["run"].items():
        thread_id = str(run.get("thread_id") or "")
        if thread_id and thread_id not in objects["thread"]:
            findings.append(
                _finding(
                    "warning",
                    "run_thread_missing",
                    "run thread_id points to a missing thread",
                    object_type="run",
                    object_id=run_id,
                    ref=thread_id,
                )
            )
        for document_id in run.get("document_ids") or []:
            if document_id not in objects["document"]:
                findings.append(
                    _finding(
                        "warning",
                        "run_document_missing",
                        "run document_ids contains a missing document",
                        object_type="run",
                        object_id=run_id,
                        ref=str(document_id),
                    )
                )
    for synthesis_id, synthesis in objects["synthesis"].items():
        thread_id = str(synthesis.get("thread_id") or "")
        if thread_id and thread_id not in objects["thread"]:
            findings.append(
                _finding(
                    "warning",
                    "synthesis_thread_missing",
                    "synthesis thread_id points to a missing thread",
                    object_type="synthesis",
                    object_id=synthesis_id,
                    ref=thread_id,
                )
            )
        for run_id in synthesis.get("run_ids") or []:
            if run_id not in objects["run"]:
                findings.append(
                    _finding(
                        "warning",
                        "synthesis_run_missing",
                        "synthesis run_ids contains a missing run",
                        object_type="synthesis",
                        object_id=synthesis_id,
                        ref=str(run_id),
                    )
                )
    return findings
```

Replace `doctor()` with:

```python
def doctor(root: Path) -> dict[str, Any]:
    root = Path(root)
    objects, findings = _load_objects(root)
    findings.extend(_check_index_refs(root, objects))
    findings.extend(_check_alias_refs(root, objects))
    findings.extend(_check_artifact_refs(root, objects))
    findings.extend(_check_cross_object_refs(objects))
    return {
        "kind": "research_doctor",
        "root": str(root),
        "status": _status(findings),
        "counts": _counts(findings),
        "findings": findings,
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- all maintenance tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/maintenance.py tests/connectors/research/test_maintenance.py
git commit -m "feat(research): add doctor reference checks"
```

---

### Task 3: Rebuild Indexes From Canonical Objects

**Files:**
- Modify: `h2t_ops/connectors/research/maintenance.py`
- Modify: `tests/connectors/research/test_maintenance.py`

- [ ] **Step 1: Add rebuild tests**

Append to `tests/connectors/research/test_maintenance.py`:

```python
def test_rebuild_indexes_writes_deterministic_indexes_from_objects(tmp_path):
    root = tmp_path / "research"
    document = _demo_document(root)
    thread = store.build_research_thread(
        question="What is Exa?",
        created_at="2026-05-27T10:00:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["answer"],
    )
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-27T10:00:00Z",
        query="What is Exa?",
        provider_set=["exa"],
        document_ids=[document["document_id"]],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="Summary",
        created_at="2026-05-27T10:00:00Z",
    )
    thread["latest_synthesis_id"] = synthesis["synthesis_id"]
    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)

    result = maintenance.rebuild_indexes(root)

    assert result["kind"] == "research_rebuild_indexes"
    assert result["counts"] == {
        "documents": 1,
        "threads": 1,
        "runs": 1,
        "syntheses": 1,
        "aliases": 1,
    }
    documents = json.loads(store.index_path(root, "documents").read_text(encoding="utf-8"))
    threads = json.loads(store.index_path(root, "threads").read_text(encoding="utf-8"))
    syntheses = json.loads(store.index_path(root, "syntheses").read_text(encoding="utf-8"))
    aliases = json.loads(store.index_path(root, "aliases").read_text(encoding="utf-8"))
    assert documents[0]["document_id"] == document["document_id"]
    assert threads[0]["latest_synthesis_id"] == synthesis["synthesis_id"]
    assert syntheses[0]["synthesis_id"] == synthesis["synthesis_id"]
    assert aliases == [
        {
            "alias_type": "url",
            "alias_value": "https://example.com/post",
            "target_object_type": "document",
            "target_id": document["document_id"],
            "confidence": "high",
        }
    ]


def test_rebuild_indexes_replaces_stale_rows(tmp_path):
    root = tmp_path / "research"
    document = _demo_document(root)
    store.write_json(
        store.index_path(root, "documents"),
        [{"document_id": "research-doc:stale", "project_ids": ["project:old"]}],
    )

    maintenance.rebuild_indexes(root)

    documents = json.loads(store.index_path(root, "documents").read_text(encoding="utf-8"))
    assert [row["document_id"] for row in documents] == [document["document_id"]]


def test_rebuild_indexes_with_malformed_object_does_not_overwrite_existing_indexes(tmp_path):
    root = tmp_path / "research"
    index_path = store.index_path(root, "documents")
    existing_rows = [{"document_id": "research-doc:keep", "project_ids": ["project:demo"]}]
    store.write_json(index_path, existing_rows)
    bad_path = store.object_path(root, "documents", "research-doc:bad")
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{bad json", encoding="utf-8")

    result = maintenance.rebuild_indexes(root)

    assert result["status"] == "error"
    assert result["written"] == []
    assert json.loads(index_path.read_text(encoding="utf-8")) == existing_rows
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- FAIL because `rebuild_indexes()` raises `UsageError`.

- [ ] **Step 3: Implement index row builders and rebuild**

Add to `maintenance.py` before `rebuild_indexes()`:

```python
def _document_index_row(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "canonical_url": document.get("canonical_url") or None,
        "provider": document.get("provider"),
        "title": document.get("title") or None,
        "status": document.get("status"),
        "review_status": document.get("review_status"),
        "thread_ids": document.get("thread_ids") or [],
        "entity_ids": document.get("entity_ids") or [],
        "project_ids": document.get("project_ids") or [],
        "updated_at": document.get("fetched_at"),
    }


def _thread_index_row(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "thread_id": thread["thread_id"],
        "question": thread.get("question"),
        "status": thread.get("status"),
        "owner_context": thread.get("owner_context"),
        "topics": thread.get("topics") or [],
        "latest_synthesis_id": thread.get("latest_synthesis_id"),
        "updated_at": thread.get("created_at"),
    }


def _synthesis_project_ids(
    synthesis: dict[str, Any],
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    thread = objects["thread"].get(str(synthesis.get("thread_id") or ""))
    context = thread.get("owner_context") if isinstance(thread, dict) else None
    context_id = context.get("context_id") if isinstance(context, dict) else None
    return [context_id] if isinstance(context_id, str) and context_id.startswith("project:") else []


def _synthesis_index_row(
    synthesis: dict[str, Any],
    objects: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "synthesis_id": synthesis["synthesis_id"],
        "thread_id": synthesis.get("thread_id"),
        "status": synthesis.get("status"),
        "review_status": synthesis.get("review_status"),
        "confidence_summary": None,
        "has_open_questions": bool(synthesis.get("open_questions") or []),
        "project_ids": _synthesis_project_ids(synthesis, objects),
        "updated_at": synthesis.get("created_at"),
    }


def _alias_rows(objects: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for document_id, document in objects["document"].items():
        seen: set[str] = set()
        for raw in (document.get("canonical_url"), document.get("source_url")):
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            rows.append(
                {
                    "alias_type": "url",
                    "alias_value": value,
                    "target_object_type": "document",
                    "target_id": document_id,
                    "confidence": "high",
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["alias_type"],
            row["alias_value"],
            row["target_object_type"],
            row["target_id"],
        ),
    )
```

Replace `rebuild_indexes()` with:

```python
def rebuild_indexes(root: Path) -> dict[str, Any]:
    root = Path(root)
    objects, findings = _load_objects(root)
    if any(item["severity"] == "error" for item in findings):
        return {
            "kind": "research_rebuild_indexes",
            "root": str(root),
            "status": "error",
            "written": [],
            "counts": {
                "documents": 0,
                "threads": 0,
                "runs": 0,
                "syntheses": 0,
                "aliases": 0,
            },
            "findings": findings,
        }

    documents = sorted(
        (_document_index_row(item) for item in objects["document"].values()),
        key=lambda row: row["document_id"],
    )
    threads = sorted(
        (_thread_index_row(item) for item in objects["thread"].values()),
        key=lambda row: row["thread_id"],
    )
    syntheses = sorted(
        (_synthesis_index_row(item, objects) for item in objects["synthesis"].values()),
        key=lambda row: row["synthesis_id"],
    )
    aliases = _alias_rows(objects)

    payloads = {
        "documents": documents,
        "threads": threads,
        "syntheses": syntheses,
        "aliases": aliases,
    }
    written: list[str] = []
    for index_name, rows in payloads.items():
        path = store.index_path(root, index_name)
        store.write_json(path, rows)
        written.append(str(path))
    return {
        "kind": "research_rebuild_indexes",
        "root": str(root),
        "status": "ok",
        "written": written,
        "counts": {
            "documents": len(objects["document"]),
            "threads": len(objects["thread"]),
            "runs": len(objects["run"]),
            "syntheses": len(objects["synthesis"]),
            "aliases": len(aliases),
        },
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py tests/connectors/research/test_navigation.py -q
```

Expected:

- maintenance and navigation tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/maintenance.py tests/connectors/research/test_maintenance.py
git commit -m "feat(research): rebuild indexes from canonical objects"
```

---

### Task 4: Cleanup Dry-Run Policy

**Files:**
- Modify: `h2t_ops/connectors/research/maintenance.py`
- Modify: `tests/connectors/research/test_maintenance.py`

- [ ] **Step 1: Add cleanup dry-run tests**

Append to `tests/connectors/research/test_maintenance.py`:

```python
def test_cleanup_dry_run_reports_unreferenced_partial_markdown_without_deleting(tmp_path):
    root = tmp_path / "research"
    orphan = root / "orphan.partial.md"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("temporary", encoding="utf-8")

    result = maintenance.cleanup(root, dry_run=True)

    assert result["kind"] == "research_cleanup"
    assert result["dry_run"] is True
    assert result["count"] == 1
    assert result["candidates"][0]["path"] == str(orphan)
    assert result["candidates"][0]["reason"] == "unreferenced_partial_markdown"
    assert result["candidates"][0]["action"] == "would_delete"
    assert orphan.exists()


def test_cleanup_dry_run_does_not_propose_canonical_objects_or_indexes(tmp_path):
    root = tmp_path / "research"
    document = _demo_document(root)
    store.upsert_document_index(root, document)

    result = maintenance.cleanup(root, dry_run=True)

    candidate_paths = {item["path"] for item in result["candidates"]}
    assert str(store.object_path(root, "documents", document["document_id"])) not in candidate_paths
    assert str(store.index_path(root, "documents")) not in candidate_paths


def test_cleanup_execute_mode_is_rejected_in_v1(tmp_path):
    result = maintenance.cleanup(tmp_path / "research", dry_run=False)

    assert result["kind"] == "research_cleanup"
    assert result["dry_run"] is False
    assert result["status"] == "blocked"
    assert result["candidates"] == []
    assert result["message"] == "cleanup execution is intentionally disabled in v1; rerun with dry_run=True"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- FAIL because `cleanup()` raises `UsageError`.

- [ ] **Step 3: Implement cleanup dry-run**

Replace `cleanup()` in `maintenance.py` with:

```python
def _referenced_artifact_paths(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> set[Path]:
    refs: set[Path] = set()
    for rows in objects.values():
        for obj in rows.values():
            artifact_refs = obj.get("artifact_refs")
            if not isinstance(artifact_refs, dict):
                continue
            for value in artifact_refs.values():
                path = _artifact_ref_path(root, value)
                if path is not None:
                    refs.add(path.resolve())
    return refs


def _is_inside_canonical_area(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to((Path(root) / "objects").resolve())
        return True
    except ValueError:
        pass
    try:
        path.resolve().relative_to((Path(root) / "indexes").resolve())
        return True
    except ValueError:
        return False


def cleanup(root: Path, *, dry_run: bool = True) -> dict[str, Any]:
    root = Path(root)
    policy = {
        "delete_canonical_objects": False,
        "delete_indexes": False,
        "delete_unreferenced_partial_md": True,
    }
    if not dry_run:
        return {
            "kind": "research_cleanup",
            "root": str(root),
            "dry_run": False,
            "status": "blocked",
            "policy": policy,
            "count": 0,
            "candidates": [],
            "message": "cleanup execution is intentionally disabled in v1; rerun with dry_run=True",
        }

    objects, _findings = _load_objects(root)
    referenced = _referenced_artifact_paths(root, objects)
    candidates: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.rglob("*.partial.md")):
            if _is_inside_canonical_area(root, path):
                continue
            if path.resolve() in referenced:
                continue
            candidates.append(
                {
                    "path": str(path),
                    "reason": "unreferenced_partial_markdown",
                    "action": "would_delete",
                }
            )
    return {
        "kind": "research_cleanup",
        "root": str(root),
        "dry_run": True,
        "status": "ok",
        "policy": policy,
        "count": len(candidates),
        "candidates": candidates,
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_maintenance.py -q
```

Expected:

- all maintenance tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/maintenance.py tests/connectors/research/test_maintenance.py
git commit -m "feat(research): add cleanup dry-run policy"
```

---

### Task 5: ResearchClient Maintenance Methods

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add client wrapper tests**

Append to `tests/connectors/research/test_client.py`:

```python
def test_research_client_doctor_delegates_to_maintenance(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import maintenance

    calls = []

    def fake_doctor(root):
        calls.append(root)
        return {"kind": "research_doctor", "root": str(root), "status": "ok"}

    monkeypatch.setattr(maintenance, "doctor", fake_doctor)

    result = client.ResearchClient(output_dir=tmp_path).research_doctor()

    assert result["kind"] == "research_doctor"
    assert calls == [tmp_path]


def test_research_client_rebuild_indexes_delegates_to_maintenance(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import maintenance

    calls = []

    def fake_rebuild(root):
        calls.append(root)
        return {"kind": "research_rebuild_indexes", "root": str(root)}

    monkeypatch.setattr(maintenance, "rebuild_indexes", fake_rebuild)

    result = client.ResearchClient(output_dir=tmp_path).rebuild_research_indexes()

    assert result["kind"] == "research_rebuild_indexes"
    assert calls == [tmp_path]


def test_research_client_cleanup_delegates_to_maintenance(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import maintenance

    calls = []

    def fake_cleanup(root, *, dry_run=True):
        calls.append((root, dry_run))
        return {"kind": "research_cleanup", "dry_run": dry_run}

    monkeypatch.setattr(maintenance, "cleanup", fake_cleanup)

    result = client.ResearchClient(output_dir=tmp_path).cleanup_research(dry_run=True)

    assert result == {"kind": "research_cleanup", "dry_run": True}
    assert calls == [(tmp_path, True)]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -q
```

Expected:

- FAIL because the client methods do not exist.

- [ ] **Step 3: Import maintenance and add client methods**

In `h2t_ops/connectors/research/client.py`, change:

```python
from h2t_ops.connectors.research import navigation, store
```

to:

```python
from h2t_ops.connectors.research import maintenance, navigation, store
```

Add these methods after `resolve_research_alias()`:

```python
    def research_doctor(self) -> dict[str, Any]:
        """Inspect local research store health without writing files."""
        return maintenance.doctor(self.output_dir)

    def rebuild_research_indexes(self) -> dict[str, Any]:
        """Rebuild research navigation indexes from canonical object JSON."""
        return maintenance.rebuild_indexes(self.output_dir)

    def cleanup_research(self, *, dry_run: bool = True) -> dict[str, Any]:
        """Return a cleanup plan for non-canonical research artifacts."""
        return maintenance.cleanup(self.output_dir, dry_run=dry_run)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py tests/connectors/research/test_maintenance.py -q
```

Expected:

- client and maintenance tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): expose maintenance client methods"
```

---

### Task 6: CLI Parser And Dispatch

**Files:**
- Modify: `h2t_ops/connectors/research/commands.py`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add parser and fake-client dispatch tests**

In `tests/connectors/research/test_commands.py`, add methods to `FakeResearchClient`:

```python
    def research_doctor(self) -> dict:
        self.calls.append(("research_doctor", {}))
        return {"method": "research_doctor", "output_dir": str(self.output_dir)}

    def rebuild_research_indexes(self) -> dict:
        self.calls.append(("rebuild_research_indexes", {}))
        return {"method": "rebuild_research_indexes", "output_dir": str(self.output_dir)}

    def cleanup_research(self, *, dry_run: bool = True) -> dict:
        self.calls.append(("cleanup_research", {"dry_run": dry_run}))
        return {"method": "cleanup_research", "dry_run": dry_run, "output_dir": str(self.output_dir)}
```

Append parser tests:

```python
def test_parser_registration_for_research_maintenance_commands():
    parser = cli.build_parser()

    doctor = parser.parse_args(
        ["research", "doctor", "--output-dir", "/tmp/research", "--json"]
    )
    rebuild = parser.parse_args(
        ["research", "rebuild-indexes", "--output-dir", "/tmp/research", "--json"]
    )
    cleanup = parser.parse_args(
        ["research", "cleanup", "--dry-run", "--output-dir", "/tmp/research", "--json"]
    )

    assert doctor.research_cmd == "doctor"
    assert doctor.output_dir == "/tmp/research"
    assert doctor.as_json is True
    assert rebuild.research_cmd == "rebuild-indexes"
    assert cleanup.research_cmd == "cleanup"
    assert cleanup.dry_run is True

    with pytest.raises(SystemExit):
        parser.parse_args(["research", "cleanup", "--output-dir", "/tmp/research"])
```

Append dispatch tests near existing `commands.run` tests:

```python
def test_research_maintenance_dispatch(monkeypatch, tmp_path):
    FakeResearchClient.instances.clear()
    research_client_module = importlib.import_module("h2t_ops.connectors.research.client")
    monkeypatch.setattr(research_client_module, "ResearchClient", FakeResearchClient)

    doctor_args = argparse.Namespace(
        research_cmd="doctor",
        output_dir=str(tmp_path),
    )
    rebuild_args = argparse.Namespace(
        research_cmd="rebuild-indexes",
        output_dir=str(tmp_path),
    )
    cleanup_args = argparse.Namespace(
        research_cmd="cleanup",
        output_dir=str(tmp_path),
        dry_run=True,
    )

    assert commands.run(doctor_args)["method"] == "research_doctor"
    assert commands.run(rebuild_args)["method"] == "rebuild_research_indexes"
    assert commands.run(cleanup_args)["method"] == "cleanup_research"
    assert FakeResearchClient.instances[-1].calls[-1] == ("cleanup_research", {"dry_run": True})
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected:

- FAIL because parser/dispatch does not yet support maintenance commands.

- [ ] **Step 3: Add CLI subcommands**

In `h2t_ops/connectors/research/commands.py`, add near navigation commands:

```python
    doctor = cmds.add_parser("doctor", help="Inspect local research store health")
    doctor.add_argument("--output-dir", dest="output_dir")
    add_fmt(doctor)

    rebuild = cmds.add_parser(
        "rebuild-indexes",
        help="Rebuild research indexes from canonical object JSON",
    )
    rebuild.add_argument("--output-dir", dest="output_dir")
    add_fmt(rebuild)

    cleanup = cmds.add_parser(
        "cleanup",
        help="Report safe cleanup candidates for local research artifacts",
    )
    cleanup.add_argument("--output-dir", dest="output_dir")
    cleanup.add_argument("--dry-run", action="store_true", required=True, dest="dry_run")
    add_fmt(cleanup)
```

In `run(args)`, add before `answer`:

```python
    if cmd == "doctor":
        return client.research_doctor()
    if cmd == "rebuild-indexes":
        return client.rebuild_research_indexes()
    if cmd == "cleanup":
        return client.cleanup_research(dry_run=args.dry_run)
```

`commands.run()` imports `ResearchClient` inside the function, so command tests must monkeypatch `h2t_ops.connectors.research.client.ResearchClient`; monkeypatching `commands.ResearchClient` does not affect dispatch.

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py tests/connectors/research/test_client.py tests/connectors/research/test_maintenance.py -q
```

Expected:

- command, client, and maintenance tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/commands.py tests/connectors/research/test_commands.py
git commit -m "feat(research): add maintenance commands"
```

---

### Task 7: CLI Fixture Tests For Doctor, Rebuild, Cleanup

**Files:**
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add real command-path fixture tests**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_research_doctor_cli_reports_stale_alias(tmp_path, capsys):
    root = tmp_path / "research"
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/missing",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    cli.main(
        [
            "research",
            "doctor",
            "--output-dir",
            str(root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "research_doctor"
    assert payload["result"]["status"] == "warning"
    assert payload["result"]["findings"][0]["code"] == "alias_target_missing"


def test_research_rebuild_indexes_cli_writes_documents_index(tmp_path, capsys):
    root = tmp_path / "research"
    document = store.build_research_document(
        canonical_url="https://example.com/post",
        source_url="https://example.com/post",
        provider="jina",
        title="Example",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="abc",
        artifact_refs={
            "metadata": None,
            "normalized_text": None,
            "citation_bundle": None,
            "markdown_mirror": None,
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(root, "documents", document["document_id"], document)

    cli.main(
        [
            "research",
            "rebuild-indexes",
            "--output-dir",
            str(root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["counts"]["documents"] == 1
    rows = json.loads(store.index_path(root, "documents").read_text(encoding="utf-8"))
    assert rows[0]["document_id"] == document["document_id"]


def test_research_cleanup_cli_dry_run_reports_orphan_partial(tmp_path, capsys):
    root = tmp_path / "research"
    orphan = root / "orphan.partial.md"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("temporary", encoding="utf-8")

    cli.main(
        [
            "research",
            "cleanup",
            "--dry-run",
            "--output-dir",
            str(root),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "research_cleanup"
    assert payload["result"]["count"] == 1
    assert payload["result"]["candidates"][0]["path"] == str(orphan)
    assert orphan.exists()
```

- [ ] **Step 2: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected:

- command tests pass

- [ ] **Step 3: Commit**

Run:

```powershell
git add tests/connectors/research/test_commands.py
git commit -m "test(research): cover maintenance cli dispatch"
```

---

### Task 8: Skill Documentation And Retention Policy

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add docs assertion test**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_research_skill_documents_maintenance_commands_and_retention_policy():
    text = Path("plugins/h2t-ops/skills/research/SKILL.md").read_text(encoding="utf-8")

    assert "h2t-ops research doctor" in text
    assert "h2t-ops research rebuild-indexes" in text
    assert "h2t-ops research cleanup --dry-run" in text
    assert "Canonical object JSON is never deleted by default" in text
    assert "doctor is read-only" in text
    assert "indexes are rebuildable caches" in text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py::test_research_skill_documents_maintenance_commands_and_retention_policy -q
```

Expected:

- FAIL because `SKILL.md` does not yet document maintenance commands.

- [ ] **Step 3: Update skill docs**

In `plugins/h2t-ops/skills/research/SKILL.md`, add this section after `Navigation Commands`:

```markdown
## Maintenance Commands

Use maintenance commands when local research artifacts or indexes may be stale:

```bash
h2t-ops research doctor --output-dir <dir> --json
h2t-ops research rebuild-indexes --output-dir <dir> --json
h2t-ops research cleanup --dry-run --output-dir <dir> --json
```

Retention policy:

- Canonical object JSON is never deleted by default.
- `doctor` is read-only.
- `rebuild-indexes` writes only `indexes/*.index.json`.
- `cleanup --dry-run` reports non-canonical cleanup candidates and does not delete files.
- indexes are rebuildable caches; if an index and object disagree, object JSON wins.
- Markdown mirrors and `.partial.md` files are human/operator surfaces, not canonical knowledge.
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected:

- command tests pass

- [ ] **Step 5: Commit**

Run:

```powershell
git add plugins/h2t-ops/skills/research/SKILL.md tests/connectors/research/test_commands.py
git commit -m "docs(research): document maintenance commands"
```

---

### Task 9: Smoke Report

**Files:**
- Create: `docs/reports/2026-05-27-research-maintenance-smoke.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected:

- all research tests pass

- [ ] **Step 2: Run local smoke in temp root**

Run:

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Expected:

- `ok=true`
- output includes `research_refs.document_id`

Run:

```powershell
uv.exe run h2t-ops research doctor --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Expected:

- `ok=true`
- `result.kind=research_doctor`
- status may be `ok` or `warning`; warnings for missing artifact refs are acceptable if refs are intentionally absent

Run:

```powershell
uv.exe run h2t-ops research rebuild-indexes --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Expected:

- `ok=true`
- `result.kind=research_rebuild_indexes`
- `result.counts.documents >= 1`

Run:

```powershell
uv.exe run h2t-ops research cleanup --dry-run --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Expected:

- `ok=true`
- `result.kind=research_cleanup`
- `result.dry_run=true`

- [ ] **Step 3: Write smoke report**

Create `docs/reports/2026-05-27-research-maintenance-smoke.md`:

```markdown
---
title: Research Maintenance Smoke
date: 2026-05-27
status: done
---

# Research Maintenance Smoke

## Scope

Validate local maintenance commands for:

- `research doctor`
- `research rebuild-indexes`
- `research cleanup --dry-run`

## Commands

```powershell
uv.exe run pytest tests/connectors/research -q
```

Result:

- Record the exact pytest passed count from the command output.

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `ok=true`
- Record the emitted `research_refs.document_id`.

```powershell
uv.exe run h2t-ops research doctor --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_doctor`
- Record the emitted doctor status.

```powershell
uv.exe run h2t-ops research rebuild-indexes --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_rebuild_indexes`
- Record the emitted document count.

```powershell
uv.exe run h2t-ops research cleanup --dry-run --output-dir C:/tmp/h2t-research-maintenance-smoke --json
```

Result:

- `kind=research_cleanup`
- `dry_run=true`
- Record the emitted cleanup candidate count.

## Conclusion

Maintenance commands inspect and rebuild local research store state without deleting canonical object JSON.
```

Before committing, replace the example result bullets with the actual values from the smoke command output. Do not leave placeholder text in the report.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/reports/2026-05-27-research-maintenance-smoke.md
git commit -m "docs(research): record maintenance smoke"
```

---

### Task 10: Final Verification And PR

**Files:**
- No code edits expected.

- [ ] **Step 1: Run full focused research suite**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected:

- all tests pass

- [ ] **Step 2: Inspect branch diff**

Run:

```powershell
git status -sb
git diff --stat origin/main..HEAD
```

Expected:

- branch contains only #193 files:
  - `h2t_ops/connectors/research/maintenance.py`
  - research client/commands changes
  - research tests
  - `plugins/h2t-ops/skills/research/SKILL.md`
  - smoke report
  - this plan
- unrelated dirty files remain unstaged

- [ ] **Step 3: Push branch**

Run:

```powershell
git push -u origin codex-research-maintenance-doctor-cleanup
```

- [ ] **Step 4: Create PR**

Run:

```powershell
$body = @"
## Summary
- add research maintenance doctor for stale indexes, missing refs, malformed objects
- add rebuild-indexes from canonical object JSON
- add cleanup dry-run for non-canonical partial markdown candidates
- document retention boundaries and record smoke evidence

## Tests
- uv.exe run pytest tests/connectors/research -q
- smoke: fetch, doctor, rebuild-indexes, cleanup --dry-run under C:/tmp/h2t-research-maintenance-smoke

Closes #193
"@
gh pr create --title "feat(research): add maintenance doctor and cleanup dry-run" --body $body --base main --head codex-research-maintenance-doctor-cleanup
```

- [ ] **Step 5: Comment on issue #193**

Run:

```powershell
gh issue comment 193 --body "Implemented in PR <PR_NUMBER>: research maintenance doctor, rebuild-indexes, cleanup dry-run, docs, tests, and smoke evidence."
```

- [ ] **Step 6: Check CI**

Run:

```powershell
gh pr checks <PR_NUMBER> --watch=false
```

Expected:

- all required checks pass or are pending with no immediate failure

## Self-Review

Spec coverage:

- Retention policy documented: Task 8.
- Doctor detects missing objects, stale index refs, and missing artifact refs: Task 2.
- Rebuild indexes from canonical objects: Task 3.
- Cleanup has dry-run mode and tests: Task 4 and Task 7.
- Single-key workflow unchanged: no provider auth code touched; final tests include existing research suite.
- Canonical object JSON never deleted by default: Task 4 and Task 8.

Placeholder scan:

- Angle-bracket values remain only in reusable command examples such as `<dir>` and PR instructions such as `<PR_NUMBER>`.
- The smoke report task explicitly requires actual command values before commit and does not permit placeholder result text.
- There are no implementation placeholders in code tasks.

Type consistency:

- Module functions: `doctor(root)`, `rebuild_indexes(root)`, `cleanup(root, dry_run=True)`.
- Client methods: `research_doctor()`, `rebuild_research_indexes()`, `cleanup_research(dry_run=True)`.
- CLI commands: `doctor`, `rebuild-indexes`, `cleanup --dry-run`.
