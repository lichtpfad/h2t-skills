# Research Navigation Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `h2t-ops research` navigation commands for listing indexes, showing canonical research objects, and resolving aliases over the Phase 1 local research artifact contract.

**Architecture:** Add a small read-only navigation module over `h2t_ops.connectors.research.store` path helpers, then expose it through `ResearchClient` and argparse commands. JSON output stays stable via existing connector envelopes; human output can remain compact pretty JSON because `h2t_ops.core.output.emit()` currently renders dicts as pretty JSON for human/md.

**Tech Stack:** Python stdlib (`argparse`, `json`, `pathlib`), existing `h2t_ops` connector patterns, pytest, GitHub issue `#192`.

---

## File Structure

- Create: `h2t_ops/connectors/research/navigation.py`
  - Read-only helper layer for indexes, canonical objects, alias resolution, project filtering, and schema validation.
  - Does not write files. Does not parse Markdown.
- Modify: `h2t_ops/connectors/research/client.py`
  - Add thin `ResearchClient` methods that delegate to `navigation.py`.
- Modify: `h2t_ops/connectors/research/commands.py`
  - Add `index`, `show`, and `resolve` subcommands.
  - Add `--output-dir` to all navigation commands.
- Create: `tests/connectors/research/test_navigation.py`
  - Unit tests for navigation helpers and error behavior.
- Modify: `tests/connectors/research/test_commands.py`
  - Parser/dispatch coverage for new commands.
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
  - Document lookup order and command surface.
- Create: `docs/reports/2026-05-27-research-navigation-smoke.md`
  - Record live/local smoke evidence after implementation.

## Contracts To Preserve

- Object JSON wins over indexes.
- Missing index returns empty list.
- Missing object is a `NotFoundError`.
- Malformed index/object/schema/id mismatch is a `ConfigError`.
- Unknown object/index type is a `UsageError`.
- Stale alias is surfaced in `resolve`; it does not fail.
- `--output-dir` is supported on every navigation command.
- `--json` works on every navigation command through the existing top-level emitter.
- Markdown mirrors are not read by navigation code.
- Do not touch `uv.lock`.

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
- unrelated dirty files may exist:
  - `docs/README.md`
  - `docs/handoffs/`
  - `uv.lock`
  - unrelated specs

Do not stage or modify unrelated files.

- [ ] **Step 2: Sync main**

Run:

```powershell
git pull --ff-only origin main
```

Expected: local `main` is up to date.

- [ ] **Step 3: Create the feature branch**

Run:

```powershell
git switch -c codex-research-navigation-surface
```

Expected: branch created.

- [ ] **Step 4: Re-check status**

Run:

```powershell
git status -sb
```

Expected:

- branch is `codex-research-navigation-surface`
- unrelated dirty files are still present but unstaged

---

### Task 1: Add Read-Only Navigation Helpers

**Files:**
- Create: `h2t_ops/connectors/research/navigation.py`
- Test: `tests/connectors/research/test_navigation.py`

- [ ] **Step 1: Write failing tests for missing indexes and project filtering**

Add this new file:

```python
from __future__ import annotations

import json

import pytest

from h2t_ops.connectors.research import navigation, store
from h2t_ops.core.errors import ConfigError, NotFoundError, UsageError


def test_list_index_missing_file_returns_empty_envelope(tmp_path):
    result = navigation.list_index(tmp_path / "research", "documents")

    assert result == {
        "kind": "research_index",
        "index": "documents",
        "root": str(tmp_path / "research"),
        "count": 0,
        "items": [],
    }


def test_list_index_rejects_unknown_index(tmp_path):
    with pytest.raises(UsageError, match="unknown research index"):
        navigation.list_index(tmp_path / "research", "unknown")


def test_list_documents_index_filters_by_project(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "document_id": "research-doc:a",
            "canonical_url": "https://a.example",
            "provider": "jina",
            "title": "A",
            "status": "indexed",
            "review_status": "unreviewed",
            "thread_ids": [],
            "entity_ids": [],
            "project_ids": ["project:demo"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "document_id": "research-doc:b",
            "canonical_url": "https://b.example",
            "provider": "jina",
            "title": "B",
            "status": "indexed",
            "review_status": "unreviewed",
            "thread_ids": [],
            "entity_ids": [],
            "project_ids": ["project:other"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
    ]
    store.write_json(store.index_path(root, "documents"), rows)

    result = navigation.list_index(root, "documents", project="demo")

    assert result["count"] == 1
    assert result["items"][0]["document_id"] == "research-doc:a"


def test_list_threads_index_filters_project_by_owner_context(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "thread_id": "research-thread:a",
            "question": "A?",
            "status": "open",
            "owner_context": {"context_type": "project", "context_id": "project:demo"},
            "topics": ["a"],
            "latest_synthesis_id": None,
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "thread_id": "research-thread:b",
            "question": "B?",
            "status": "open",
            "owner_context": {"context_type": "project", "context_id": "project:other"},
            "topics": ["b"],
            "latest_synthesis_id": None,
            "updated_at": "2026-05-27T10:00:00Z",
        },
    ]
    store.write_json(store.index_path(root, "threads"), rows)

    result = navigation.list_index(root, "threads", project="project:demo")

    assert result["count"] == 1
    assert result["items"][0]["thread_id"] == "research-thread:a"


def test_list_syntheses_index_filters_by_project(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "synthesis_id": "research-synthesis:a",
            "thread_id": "research-thread:a",
            "status": "draft",
            "review_status": "unreviewed",
            "confidence_summary": None,
            "has_open_questions": False,
            "project_ids": ["project:demo"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "synthesis_id": "research-synthesis:b",
            "thread_id": "research-thread:b",
            "status": "draft",
            "review_status": "unreviewed",
            "confidence_summary": None,
            "has_open_questions": False,
            "project_ids": ["project:other"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
    ]
    store.write_json(store.index_path(root, "syntheses"), rows)

    result = navigation.list_index(root, "syntheses", project="demo")

    assert result["count"] == 1
    assert result["items"][0]["synthesis_id"] == "research-synthesis:a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_navigation.py -q
```

Expected: FAIL with import/module errors because `navigation.py` does not exist.

- [ ] **Step 3: Implement index helpers**

Create `h2t_ops/connectors/research/navigation.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.connectors.research import store
from h2t_ops.core.errors import UsageError

INDEX_NAMES = {"documents", "threads", "syntheses", "aliases"}

OBJECTS = {
    "document": ("documents", "research_document/v0.1", "document_id"),
    "thread": ("threads", "research_thread/v0.1", "thread_id"),
    "run": ("runs", "research_run/v0.1", "run_id"),
    "synthesis": ("syntheses", "research_synthesis/v0.1", "synthesis_id"),
}


def normalize_project(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return value if value.startswith("project:") else f"project:{value}"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_index(root: Path, index_name: str) -> list[dict[str, Any]]:
    if index_name not in INDEX_NAMES:
        raise UsageError(f"unknown research index: {index_name}")
    path = store.index_path(root, index_name)
    if not path.is_file():
        return []
    data = _read_json(path)
    if not isinstance(data, list):
        raise ConfigError(f"research index is not a list: {path}")
    return [row for row in data if isinstance(row, dict)]


def _matches_project(index_name: str, row: dict[str, Any], project: str | None) -> bool:
    normalized = normalize_project(project)
    if normalized is None:
        return True
    if index_name == "threads":
        owner = row.get("owner_context")
        return isinstance(owner, dict) and owner.get("context_id") == normalized
    ids = row.get("project_ids")
    return isinstance(ids, list) and normalized in ids


def list_index(root: Path, index_name: str, *, project: str | None = None) -> dict[str, Any]:
    root = Path(root)
    rows = [
        row
        for row in _read_index(root, index_name)
        if _matches_project(index_name, row, project)
    ]
    return {
        "kind": "research_index",
        "index": index_name,
        "root": str(root),
        "count": len(rows),
        "items": rows,
    }
```

- [ ] **Step 4: Run helper tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_navigation.py -q
```

Expected: PASS for the first five tests.

- [ ] **Step 5: Commit**

```powershell
git add h2t_ops/connectors/research/navigation.py tests/connectors/research/test_navigation.py
git commit -m "feat(research): add navigation index helpers"
```

---

### Task 2: Add Show Object And Resolve Alias Helpers

**Files:**
- Modify: `h2t_ops/connectors/research/navigation.py`
- Modify: `tests/connectors/research/test_navigation.py`

- [ ] **Step 1: Add failing tests for show object, schema mismatch, missing object, and stale alias**

Append to `tests/connectors/research/test_navigation.py`:

```python
def test_show_object_loads_canonical_document(tmp_path):
    root = tmp_path / "research"
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
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(root, "documents", document["document_id"], document)

    result = navigation.show_object(root, "document", document["document_id"])

    assert result["kind"] == "research_object"
    assert result["object_type"] == "document"
    assert result["object_id"] == document["document_id"]
    assert result["object"] == document


def test_show_object_missing_file_raises_usage_error(tmp_path):
    with pytest.raises(NotFoundError, match="research object not found"):
        navigation.show_object(tmp_path / "research", "document", "research-doc:missing")


def test_show_object_schema_mismatch_raises_usage_error(tmp_path):
    root = tmp_path / "research"
    bad = {
        "schema": "research_thread/v0.1",
        "document_id": "research-doc:bad",
    }
    store.write_json(store.object_path(root, "documents", "research-doc:bad"), bad)

    with pytest.raises(ConfigError, match="research object schema mismatch"):
        navigation.show_object(root, "document", "research-doc:bad")


def test_show_object_loads_thread_run_and_synthesis(tmp_path):
    root = tmp_path / "research"
    thread = store.build_research_thread(
        question="What is Exa answer?",
        created_at="2026-05-27T10:00:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["exa"],
    )
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-27T10:01:00Z",
        query="exa answer",
        provider_set=["exa"],
        document_ids=[],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="Exa answer returns grounded answers.",
        created_at="2026-05-27T10:02:00Z",
    )
    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)

    loaded_thread = navigation.show_object(root, "thread", thread["thread_id"])
    loaded_run = navigation.show_object(root, "run", run["run_id"])
    loaded_synthesis = navigation.show_object(root, "synthesis", synthesis["synthesis_id"])

    assert loaded_thread["object"]["schema"] == "research_thread/v0.1"
    assert loaded_run["object"]["schema"] == "research_run/v0.1"
    assert loaded_synthesis["object"]["schema"] == "research_synthesis/v0.1"


def test_resolve_alias_returns_object_path_and_stale_state(tmp_path):
    root = tmp_path / "research"
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    result = navigation.resolve_alias(
        root,
        alias_value="https://example.com/post",
        alias_type="url",
    )

    assert result["kind"] == "research_resolution"
    assert result["count"] == 1
    assert result["matches"][0]["object_exists"] is False
    assert result["matches"][0]["object_path"].endswith("research-doc:missing.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_navigation.py -q
```

Expected: FAIL because `show_object()` and `resolve_alias()` are not implemented.

- [ ] **Step 3: Implement object and alias helpers**

Append to `h2t_ops/connectors/research/navigation.py`:

```python
def _object_path_for_type(root: Path, object_type: str, object_id: str) -> Path:
    if object_type not in OBJECTS:
        raise UsageError(f"unknown research object type: {object_type}")
    directory, _schema, _id_key = OBJECTS[object_type]
    return store.object_path(root, directory, object_id)


def show_object(root: Path, object_type: str, object_id: str) -> dict[str, Any]:
    root = Path(root)
    path = _object_path_for_type(root, object_type, object_id)
    if not path.is_file():
        raise NotFoundError(
            f"research object not found: {object_type} {object_id} at {path}"
        )
    obj = _read_json(path)
    if not isinstance(obj, dict):
        raise ConfigError(f"research object is not a JSON object: {path}")
    _directory, expected_schema, id_key = OBJECTS[object_type]
    if obj.get("schema") != expected_schema:
        raise ConfigError(
            f"research object schema mismatch: expected {expected_schema}, got {obj.get('schema')}"
        )
    if obj.get(id_key) != object_id:
        raise ConfigError(
            f"research object id mismatch: expected {object_id}, got {obj.get(id_key)}"
        )
    return {
        "kind": "research_object",
        "object_type": object_type,
        "object_id": object_id,
        "root": str(root),
        "object": obj,
    }


def _target_object_path(root: Path, target_type: str, target_id: str) -> Path:
    if target_type not in OBJECTS:
        return Path(root) / "objects" / target_type / f"{target_id}.json"
    directory, _schema, _id_key = OBJECTS[target_type]
    return store.object_path(root, directory, target_id)


def resolve_alias(
    root: Path,
    *,
    alias_value: str,
    alias_type: str = "url",
) -> dict[str, Any]:
    root = Path(root)
    value = str(alias_value).strip()
    kind = str(alias_type).strip() or "url"
    if not value:
        raise UsageError("research resolve requires a non-empty alias value")
    rows = [
        row
        for row in _read_index(root, "aliases")
        if row.get("alias_type") == kind and row.get("alias_value") == value
    ]
    matches: list[dict[str, Any]] = []
    for row in rows:
        target_type = str(row.get("target_object_type") or "")
        target_id = str(row.get("target_id") or "")
        path = _target_object_path(root, target_type, target_id)
        enriched = dict(row)
        enriched["object_path"] = str(path)
        enriched["object_exists"] = path.is_file()
        matches.append(enriched)
    return {
        "kind": "research_resolution",
        "root": str(root),
        "query": {"alias_type": kind, "alias_value": value},
        "count": len(matches),
        "matches": matches,
    }
```

- [ ] **Step 4: Run navigation tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_navigation.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add h2t_ops/connectors/research/navigation.py tests/connectors/research/test_navigation.py
git commit -m "feat(research): add navigation object lookup"
```

---

### Task 3: Wire ResearchClient Navigation Methods

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add failing client tests**

Append to `tests/connectors/research/test_client.py`:

```python
def test_research_client_lists_navigation_index(tmp_path):
    from h2t_ops.connectors.research import store

    root = tmp_path
    store.write_json(
        root / "indexes" / "documents.index.json",
        [
            {
                "document_id": "research-doc:a",
                "canonical_url": "https://a.example",
                "provider": "jina",
                "title": "A",
                "status": "indexed",
                "review_status": "unreviewed",
                "thread_ids": [],
                "entity_ids": [],
                "project_ids": ["project:demo"],
                "updated_at": "2026-05-27T10:00:00Z",
            }
        ],
    )

    result = client.ResearchClient(output_dir=root).list_research_index(
        "documents",
        project="demo",
    )

    assert result["index"] == "documents"
    assert result["count"] == 1


def test_research_client_shows_navigation_object(tmp_path):
    from h2t_ops.connectors.research import store

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
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(tmp_path, "documents", document["document_id"], document)

    result = client.ResearchClient(output_dir=tmp_path).show_research_object(
        "document",
        document["document_id"],
    )

    assert result["object_id"] == document["document_id"]
    assert result["object"]["title"] == "Example"


def test_research_client_resolves_url_alias(tmp_path):
    from h2t_ops.connectors.research import store

    store.upsert_alias_index(
        tmp_path,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    result = client.ResearchClient(output_dir=tmp_path).resolve_research_alias(
        alias_value="https://example.com/post",
        alias_type="url",
    )

    assert result["count"] == 1
    assert result["matches"][0]["target_id"] == "research-doc:missing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -q
```

Expected: FAIL because `ResearchClient` has no navigation methods.

- [ ] **Step 3: Add client methods**

In `h2t_ops/connectors/research/client.py`, add this import near other research imports:

```python
from h2t_ops.connectors.research import navigation, store
```

If `store` is already imported, change it to:

```python
from h2t_ops.connectors.research import navigation, store
```

Add these methods inside `ResearchClient`:

```python
    def list_research_index(
        self,
        index_name: str,
        *,
        project: str | None = None,
    ) -> dict[str, Any]:
        return navigation.list_index(
            self._research_root(),
            index_name,
            project=project,
        )

    def show_research_object(
        self,
        object_type: str,
        object_id: str,
    ) -> dict[str, Any]:
        return navigation.show_object(
            self._research_root(),
            object_type,
            object_id,
        )

    def resolve_research_alias(
        self,
        *,
        alias_value: str,
        alias_type: str = "url",
    ) -> dict[str, Any]:
        return navigation.resolve_alias(
            self._research_root(),
            alias_value=alias_value,
            alias_type=alias_type,
        )
```

- [ ] **Step 4: Run client tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): expose navigation client methods"
```

---

### Task 4: Add Argparse Surface And Dispatch

**Files:**
- Modify: `h2t_ops/connectors/research/commands.py`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add failing parser and dispatch tests**

Update `FakeResearchClient` in `tests/connectors/research/test_commands.py` with these methods:

```python
    def list_research_index(self, index_name: str, **kwargs) -> dict:
        self.calls.append(("list_research_index", {"index_name": index_name, **kwargs}))
        return {"method": "list_research_index", "index_name": index_name, "kwargs": kwargs}

    def show_research_object(self, object_type: str, object_id: str) -> dict:
        self.calls.append(("show_research_object", {"object_type": object_type, "object_id": object_id}))
        return {"method": "show_research_object", "object_type": object_type, "object_id": object_id}

    def resolve_research_alias(self, **kwargs) -> dict:
        self.calls.append(("resolve_research_alias", kwargs))
        return {"method": "resolve_research_alias", "kwargs": kwargs}
```

Append these tests:

```python
def test_parser_registration_for_research_index_show_resolve():
    parser = cli.build_parser()

    index = parser.parse_args(
        [
            "research",
            "index",
            "documents",
            "--project",
            "demo",
            "--output-dir",
            "C:/tmp/research",
            "--json",
        ]
    )
    show = parser.parse_args(
        [
            "research",
            "show",
            "document",
            "research-doc:abc",
            "--output-dir",
            "C:/tmp/research",
            "--json",
        ]
    )
    resolve = parser.parse_args(
        [
            "research",
            "resolve",
            "--alias",
            "https://example.com/post",
            "--alias-type",
            "url",
            "--output-dir",
            "C:/tmp/research",
            "--json",
        ]
    )

    assert index.research_cmd == "index"
    assert index.index_name == "documents"
    assert index.project == "demo"
    assert show.research_cmd == "show"
    assert show.object_type == "document"
    assert show.object_id == "research-doc:abc"
    assert resolve.research_cmd == "resolve"
    assert resolve.alias_value == "https://example.com/post"
    assert resolve.alias_type == "url"


def test_run_dispatches_navigation_commands(monkeypatch, tmp_path):
    _patch_fake_client(monkeypatch)

    index_result = commands.run(
        argparse.Namespace(
            research_cmd="index",
            output_dir=str(tmp_path),
            index_name="threads",
            project="demo",
        )
    )
    show_result = commands.run(
        argparse.Namespace(
            research_cmd="show",
            output_dir=str(tmp_path),
            object_type="thread",
            object_id="research-thread:abc",
        )
    )
    resolve_result = commands.run(
        argparse.Namespace(
            research_cmd="resolve",
            output_dir=str(tmp_path),
            url="https://example.com/post",
            alias_value=None,
            alias_type="url",
        )
    )

    assert FakeResearchClient.instances[0].output_dir == tmp_path
    assert index_result["method"] == "list_research_index"
    assert index_result["kwargs"] == {"project": "demo"}
    assert show_result["method"] == "show_research_object"
    assert show_result["object_type"] == "thread"
    assert resolve_result["method"] == "resolve_research_alias"
    assert resolve_result["kwargs"] == {
        "alias_value": "https://example.com/post",
        "alias_type": "url",
    }
```

- [ ] **Step 2: Run command tests to verify they fail**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected: FAIL because parser/dispatch do not know `index`, `show`, or `resolve`.

- [ ] **Step 3: Add parser subcommands**

In `h2t_ops/connectors/research/commands.py`, after `answer_p` and before `resolve_author`, add:

```python
    index_p = cmds.add_parser("index", help="List local research navigation indexes")
    index_p.add_argument("index_name", choices=["documents", "threads", "syntheses"])
    index_p.add_argument("--project", dest="project")
    index_p.add_argument("--output-dir", dest="output_dir")
    add_fmt(index_p)

    show_p = cmds.add_parser("show", help="Show a canonical local research object")
    show_p.add_argument("object_type", choices=["document", "thread", "run", "synthesis"])
    show_p.add_argument("object_id")
    show_p.add_argument("--output-dir", dest="output_dir")
    add_fmt(show_p)

    resolve_p = cmds.add_parser("resolve", help="Resolve a local research alias")
    resolve_group = resolve_p.add_mutually_exclusive_group(required=True)
    resolve_group.add_argument("--url", dest="url")
    resolve_group.add_argument("--alias", dest="alias_value")
    resolve_p.add_argument("--alias-type", default="url", dest="alias_type")
    resolve_p.add_argument("--output-dir", dest="output_dir")
    add_fmt(resolve_p)
```

- [ ] **Step 4: Add dispatch branches**

In `run(args)`, before `resolve-author`, add:

```python
    if cmd == "index":
        return client.list_research_index(
            args.index_name,
            project=args.project,
        )
    if cmd == "show":
        return client.show_research_object(
            args.object_type,
            args.object_id,
        )
    if cmd == "resolve":
        alias_value = args.url if args.url else args.alias_value
        return client.resolve_research_alias(
            alias_value=alias_value,
            alias_type=args.alias_type,
        )
```

- [ ] **Step 5: Run command tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add h2t_ops/connectors/research/commands.py tests/connectors/research/test_commands.py
git commit -m "feat(research): add navigation commands"
```

---

### Task 5: Add End-To-End CLI Tests

**Files:**
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Add failing CLI dispatch tests using real client/storage**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_research_navigation_cli_lists_and_shows_objects(tmp_path, capsys):
    from h2t_ops.connectors.research import store

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
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(tmp_path, "documents", document["document_id"], document)
    store.upsert_document_index(tmp_path, document)

    code = cli.dispatch(
        [
            "research",
            "index",
            "documents",
            "--project",
            "demo",
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )
    out = json.loads(capsys.readouterr().out)

    assert code == 0
    assert out["ok"] is True
    assert out["result"]["count"] == 1
    assert out["result"]["items"][0]["document_id"] == document["document_id"]

    code = cli.dispatch(
        [
            "research",
            "show",
            "document",
            document["document_id"],
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )
    out = json.loads(capsys.readouterr().out)

    assert code == 0
    assert out["result"]["object"]["document_id"] == document["document_id"]


def test_research_navigation_cli_shows_thread_run_and_synthesis(tmp_path, capsys):
    from h2t_ops.connectors.research import store

    thread = store.build_research_thread(
        question="What is Exa answer?",
        created_at="2026-05-27T10:00:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["exa"],
    )
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-27T10:01:00Z",
        query="exa answer",
        provider_set=["exa"],
        document_ids=[],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="Exa answer returns grounded answers.",
        created_at="2026-05-27T10:02:00Z",
    )
    store.write_object(tmp_path, "threads", thread["thread_id"], thread)
    store.write_object(tmp_path, "runs", run["run_id"], run)
    store.write_object(tmp_path, "syntheses", synthesis["synthesis_id"], synthesis)

    for object_type, object_id, id_key in [
        ("thread", thread["thread_id"], "thread_id"),
        ("run", run["run_id"], "run_id"),
        ("synthesis", synthesis["synthesis_id"], "synthesis_id"),
    ]:
        code = cli.dispatch(
            [
                "research",
                "show",
                object_type,
                object_id,
                "--output-dir",
                str(tmp_path),
                "--json",
            ]
        )
        out = json.loads(capsys.readouterr().out)

        assert code == 0
        assert out["result"]["object"][id_key] == object_id


def test_research_navigation_cli_resolves_stale_alias(tmp_path, capsys):
    from h2t_ops.connectors.research import store

    store.upsert_alias_index(
        tmp_path,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    code = cli.dispatch(
        [
            "research",
            "resolve",
            "--url",
            "https://example.com/post",
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )
    out = json.loads(capsys.readouterr().out)

    assert code == 0
    assert out["result"]["count"] == 1
    assert out["result"]["matches"][0]["object_exists"] is False
```

- [ ] **Step 2: Run the CLI tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected: PASS after Task 4.

- [ ] **Step 3: Commit**

```powershell
git add tests/connectors/research/test_commands.py
git commit -m "test(research): cover navigation cli dispatch"
```

---

### Task 6: Update Skill Documentation

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
- Modify: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Extend the documentation assertion**

Update `test_research_skill_documents_json_first_local_truth()` in `tests/connectors/research/test_commands.py`:

```python
def test_research_skill_documents_json_first_local_truth():
    text = Path("plugins/h2t-ops/skills/research/SKILL.md").read_text(encoding="utf-8")

    assert "canonical local truth" in text
    assert "Markdown" in text
    assert "threads.index.json" in text
    assert "documents.index.json" in text
    assert "If index and object disagree, object wins." in text
    assert "research index documents" in text
    assert "research show document" in text
    assert "research resolve --url" in text
```

- [ ] **Step 2: Run the doc assertion to verify it fails**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py::test_research_skill_documents_json_first_local_truth -q
```

Expected: FAIL until the skill doc includes the new commands.

- [ ] **Step 3: Update the skill doc**

In `plugins/h2t-ops/skills/research/SKILL.md`, add a section near the existing JSON-first/index documentation:

```markdown
## Local Research Navigation

Use the local navigation surface before manually opening files:

1. Query shared indexes.
2. Resolve object ids.
3. Read canonical object JSON.
4. Open Markdown mirrors only for human review.

Commands:

- `h2t-ops research index documents [--project <project>] [--output-dir <root>] [--json]`
- `h2t-ops research index threads [--project <project>] [--output-dir <root>] [--json]`
- `h2t-ops research index syntheses [--project <project>] [--output-dir <root>] [--json]`
- `h2t-ops research show document <document_id> [--output-dir <root>] [--json]`
- `h2t-ops research show thread <thread_id> [--output-dir <root>] [--json]`
- `h2t-ops research show run <run_id> [--output-dir <root>] [--json]`
- `h2t-ops research show synthesis <synthesis_id> [--output-dir <root>] [--json]`
- `h2t-ops research resolve --url <url> [--output-dir <root>] [--json]`

Indexes are navigation caches. Canonical object JSON is truth.
If index and object disagree, object wins.
```

- [ ] **Step 4: Run command tests**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_commands.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add plugins/h2t-ops/skills/research/SKILL.md tests/connectors/research/test_commands.py
git commit -m "docs(research): document navigation commands"
```

---

### Task 7: Integrated Verification And Smoke Report

**Files:**
- Create: `docs/reports/2026-05-27-research-navigation-smoke.md`

- [ ] **Step 1: Run the focused test suite**

Run:

```powershell
uv.exe run pytest tests/connectors/research/test_navigation.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full research test suite**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected: PASS.

- [ ] **Step 3: Generate local smoke artifacts**

Use existing local research artifacts if present, or create a small local test root through existing commands:

```powershell
uv.exe run h2t-ops research fetch --url https://exa.ai/docs/reference/answer --provider jina --project demo --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Expected:

- command exits 0
- output contains `artifact.research_refs.document_id`

If network/provider access fails, use test-generated fixtures from pytest and record the environment gate in the report.

- [ ] **Step 4: Run navigation smoke commands**

Run:

```powershell
uv.exe run h2t-ops research index documents --project demo --output-dir C:/tmp/h2t-research-navigation-smoke --json
uv.exe run h2t-ops research show document <document_id> --output-dir C:/tmp/h2t-research-navigation-smoke --json
uv.exe run h2t-ops research resolve --url https://exa.ai/docs/reference/answer --output-dir C:/tmp/h2t-research-navigation-smoke --json
```

Expected:

- `index documents` returns `count >= 1`
- `show document` returns `kind=research_object`
- `resolve --url` returns `object_exists=true`

- [ ] **Step 5: Create the smoke report**

Create `docs/reports/2026-05-27-research-navigation-smoke.md`:

```markdown
---
title: Research Navigation Surface Smoke
date: 2026-05-27
status: done
issue: 192
---

# Research Navigation Surface Smoke

## Commands

- `uv.exe run pytest tests/connectors/research/test_navigation.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q`
- `uv.exe run pytest tests/connectors/research -q`
- `uv.exe run h2t-ops research index documents --project demo --output-dir C:/tmp/h2t-research-navigation-smoke --json`
- `uv.exe run h2t-ops research show document <document_id> --output-dir C:/tmp/h2t-research-navigation-smoke --json`
- `uv.exe run h2t-ops research resolve --url https://exa.ai/docs/reference/answer --output-dir C:/tmp/h2t-research-navigation-smoke --json`

## Result

- index listing: PASS
- canonical object show: PASS
- URL alias resolution: PASS
- stale alias behavior covered by unit tests

## Notes

- Markdown mirrors were not parsed.
- `--output-dir` was used for all navigation smoke commands.
```

Replace `<document_id>` with the actual id from the smoke output.

- [ ] **Step 6: Commit**

```powershell
git add docs/reports/2026-05-27-research-navigation-smoke.md
git commit -m "docs(research): record navigation smoke"
```

---

### Task 8: Final Branch Hygiene And PR

**Files:**
- No code files unless tests reveal a bug.

- [ ] **Step 1: Check worktree state**

Run:

```powershell
git status -sb
```

Expected:

- feature branch is clean except known unrelated files such as `uv.lock`
- no unrelated `docs/handoffs/` or `docs/README.md` changes are staged

- [ ] **Step 2: Run final focused verification**

Run:

```powershell
uv.exe run pytest tests/connectors/research -q
```

Expected: PASS.

- [ ] **Step 3: Push branch**

Run:

```powershell
git push -u origin codex-research-navigation-surface
```

Expected: branch pushed.

- [ ] **Step 4: Open PR**

Run:

```powershell
$body = @'
## Summary
- add local research index/show/resolve navigation commands
- expose read-only navigation over canonical object JSON and shared indexes
- document lookup order and record smoke evidence

## Verification
- uv.exe run pytest tests/connectors/research/test_navigation.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q
- uv.exe run pytest tests/connectors/research -q
- h2t-ops research navigation smoke recorded in docs/reports/2026-05-27-research-navigation-smoke.md

Closes part of #192.
'@
gh pr create --base main --head codex-research-navigation-surface --title "feat(research): add local navigation surface" --body $body
```

Expected: PR URL printed.

- [ ] **Step 5: Comment on issue #192**

Run:

```powershell
gh issue comment 192 --body "Navigation surface is implemented in <PR URL>.

Delivered:
- research index documents/threads/syntheses
- research show document/thread/run/synthesis
- research resolve --url/--alias
- --output-dir support
- missing index/object/stale alias behavior
- skill docs and smoke report

Verification:
- focused research tests PASS
- full research suite PASS
- local navigation smoke PASS"
```

Expected: comment URL printed.

## Self-Review

Spec coverage:

- `index documents/threads/syntheses`: Task 1, Task 4, Task 5.
- `show document/thread/run/synthesis`: Task 2, Task 3, Task 4, Task 5.
- `resolve --url/--alias --alias-type`: Task 2, Task 4, Task 5.
- `--output-dir` on navigation commands: Task 4 and smoke in Task 7.
- Missing index empty list: Task 1.
- Missing object `NotFoundError`: Task 2.
- Stale alias non-failing resolve: Task 2 and Task 5.
- Schema mismatch `ConfigError`: Task 2.
- Project filtering including thread `owner_context.context_id` and synthesis `project_ids`: Task 1.
- Skill docs: Task 6.
- Smoke evidence: Task 7.

Placeholder scan:

- No `TBD`, `TODO`, or open-ended "handle errors" steps.
- Error behavior is implemented through explicit `UsageError`, `NotFoundError`, and `ConfigError` cases.

Type consistency:

- Command names match spec: `index`, `show`, `resolve`.
- Args match spec: `--output-dir`, `--project`, `--alias-type`.
- Client methods are named consistently:
  - `list_research_index`
  - `show_research_object`
  - `resolve_research_alias`
- Object type names match `navigation.OBJECTS`.
