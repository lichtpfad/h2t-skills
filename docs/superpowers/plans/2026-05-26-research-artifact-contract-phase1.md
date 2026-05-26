# Research Artifact Contract Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local JSON-first research object store and shared navigation indexes to `h2t-ops:research`, then wire the existing research commands so artifacts persist as canonical documents/threads/runs/syntheses instead of only flat provider envelopes.

**Architecture:** This phase is local-first and POS-compatible. It introduces one focused research storage helper module under `h2t_ops/connectors/research/`, keeps Markdown as a mirror only, and integrates persistence through existing `ResearchClient` artifact-writing seams instead of rewriting providers. Phase 1 command mapping is explicit: `fetch_url`, `crawl`, and `visual_ocr` persist `ResearchDocument`; `search` and `similar` persist `ResearchThread` + `ResearchRun`; `answer` persists `ResearchThread` + `ResearchRun` + `ResearchSynthesis`. Promotion of search results into `ResearchDocument` objects is deferred.

**Tech Stack:** Python 3.11+, existing `h2t_ops.connectors.research` client/CLI, `pytest`, UTF-8 JSON files under `~/.h2t/research/`

---

## Scope Check

This plan intentionally covers only the first implementation wave from:

- `docs/superpowers/specs/2026-05-26-research-artifact-roles-retention-routing.md`

It does **not** implement:

- POS ingestion;
- semantic search;
- global graph edges;
- bulk migration of legacy research files;
- full historical source-version modeling;
- entity-link extraction beyond what is already explicitly available in current research results.

Phase 1 delivers:

- canonical local JSON objects;
- stable IDs where feasible;
- shared local index files;
- query/document routing semantics;
- skill docs updated to describe the new local truth and index layer.

Phase 1 command-family mapping is fixed:

- `fetch_url`, `crawl`, `visual_ocr` => `ResearchDocument`
- `search`, `similar` => `ResearchThread` + `ResearchRun`
- `answer` => `ResearchThread` + `ResearchRun` + `ResearchSynthesis`

This phase does **not** promote `search`/`similar` result rows into canonical `ResearchDocument` objects.

## File Structure

### Files to create

- `h2t_ops/connectors/research/store.py`
  - Pure helper module for:
    - stable ID builders;
    - canonical object builders;
    - local index load/write/update helpers;
    - local storage path helpers.

- `tests/connectors/research/test_store.py`
  - Focused tests for the new storage/routing helper module.

### Files to modify

- `h2t_ops/connectors/research/client.py`
  - Keep provider logic as-is.
  - After existing artifact writes, persist:
    - `ResearchDocument` objects for `fetch_url`, `crawl`, and `visual_ocr`;
    - `ResearchThread`/`ResearchRun` for `search`, `similar`, and `answer`;
    - `ResearchSynthesis` for `answer` only;
    - project attachment via `project_ids` on phase-1 objects and indexes.

- `tests/connectors/research/test_client.py`
  - Extend client tests to verify canonical object JSON + index side effects.

- `plugins/h2t-ops/skills/research/SKILL.md`
  - Update skill contract:
    - JSON objects are canonical;
    - Markdown is mirror/review only;
    - shared indexes are navigation caches, not truth.

### Files to optionally create for verification

- `docs/reports/2026-05-26-research-artifact-contract-smoke.md`
  - Short operator report for local smoke results.

## Storage Shape Decision for Phase 1

Do **not** redesign all existing artifact filenames in this wave.

Phase 1 should add a parallel structured layer under the existing research output root:

- `objects/documents/<document_id>.json`
- `objects/threads/<thread_id>.json`
- `objects/runs/<run_id>.json`
- `objects/syntheses/<synthesis_id>.json`
- `indexes/documents.index.json`
- `indexes/threads.index.json`
- `indexes/syntheses.index.json`
- `indexes/aliases.index.json`

This keeps the new contract explicit without forcing a rewrite of existing `.artifact.json`, `.sources.json`, and `.partial.md` outputs.

Phase 1 explicitly does **not** create `ProjectResearchLink` objects or `links.index.json`.
Project attachment is represented only through `project_ids` on canonical objects and index rows.

## Task 1: Add Canonical Research Store Helpers

**Files:**
- Create: `h2t_ops/connectors/research/store.py`
- Create: `tests/connectors/research/test_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/connectors/research/test_store.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

from h2t_ops.connectors.research import store


def test_document_id_prefers_canonical_url():
    document_id = store.build_document_id(
        canonical_url="https://example.com/post",
        content_hash="deadbeef",
        provider="web",
        fetched_at="2026-05-26T09:00:00Z",
    )

    assert document_id.startswith("research-doc:")
    assert document_id == store.build_document_id(
        canonical_url="https://example.com/post",
        content_hash="different",
        provider="other",
        fetched_at="2026-05-26T09:01:00Z",
    )


def test_document_id_falls_back_when_canonical_url_missing():
    first = store.build_document_id(
        canonical_url="",
        content_hash="hash-a",
        provider="visual_ocr",
        fetched_at="2026-05-26T09:00:00Z",
    )
    second = store.build_document_id(
        canonical_url="",
        content_hash="hash-b",
        provider="visual_ocr",
        fetched_at="2026-05-26T09:00:00Z",
    )

    assert first.startswith("research-doc:")
    assert first != second


def test_write_object_and_rebuildable_document_index(tmp_path):
    root = tmp_path / "research"
    doc = store.build_research_document(
        canonical_url="https://example.com/post",
        source_url="https://m.example.com/post",
        provider="web",
        title="Example Post",
        fetched_at="2026-05-26T09:00:00Z",
        content_hash="hash-a",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:default"],
        thread_ids=[],
        entity_ids=[],
    )

    path = store.write_object(root, "documents", doc["document_id"], doc)
    store.upsert_document_index(root, doc)

    loaded = json.loads(path.read_text(encoding="utf-8"))
    index = json.loads((root / "indexes" / "documents.index.json").read_text(encoding="utf-8"))

    assert loaded["document_id"] == doc["document_id"]
    assert index[0]["document_id"] == doc["document_id"]
    assert index[0]["canonical_url"] == "https://example.com/post"
    assert index[0]["project_ids"] == ["project:default"]


def test_alias_index_preserves_multiple_aliases_for_one_target(tmp_path):
    root = tmp_path / "research"
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://m.example.com/post",
                "target_object_type": "document",
                "target_id": "research-doc:1",
                "confidence": "high",
            },
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "document",
                "target_id": "research-doc:1",
                "confidence": "high",
            },
        ],
    )

    rows = json.loads((root / "indexes" / "aliases.index.json").read_text(encoding="utf-8"))
    assert [row["alias_value"] for row in rows] == [
        "https://example.com/post",
        "https://m.example.com/post",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_store.py -q
```

Expected:

- FAIL with `ModuleNotFoundError` for `h2t_ops.connectors.research.store`

- [ ] **Step 3: Write minimal implementation**

Create `h2t_ops/connectors/research/store.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha(prefix: str, *parts: str) -> str:
    payload = "||".join(part.strip() for part in parts if str(part).strip())
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_document_id(*, canonical_url: str, content_hash: str, provider: str, fetched_at: str) -> str:
    if canonical_url.strip():
        return _sha("research-doc", canonical_url)
    return _sha("research-doc", content_hash, provider, fetched_at[:16])


def build_thread_id(*, question: str, context_type: str, context_id: str, created_at: str) -> str:
    return _sha("research-thread", question, context_type, context_id, created_at[:10])


def build_run_id(*, thread_id: str, query: str, provider_set: list[str], created_at: str) -> str:
    return _sha("research-run", thread_id, query, ",".join(sorted(provider_set)), created_at)


def build_synthesis_id(*, thread_id: str, run_ids: list[str], synthesis_type: str) -> str:
    return _sha("research-synthesis", thread_id, ",".join(sorted(run_ids)), synthesis_type)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_index(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_object(root: Path, object_kind: str, object_id: str, payload: dict[str, Any]) -> Path:
    path = Path(root) / "objects" / object_kind / f"{object_id}.json"
    write_json(path, payload)
    return path


def build_research_document(
    *,
    canonical_url: str,
    source_url: str,
    provider: str,
    title: str,
    fetched_at: str,
    content_hash: str,
    artifact_refs: dict[str, Any],
    project_ids: list[str],
    thread_ids: list[str],
    entity_ids: list[str],
) -> dict[str, Any]:
    document_id = build_document_id(
        canonical_url=canonical_url,
        content_hash=content_hash,
        provider=provider,
        fetched_at=fetched_at,
    )
    return {
        "schema": "research_document/v0.1",
        "document_id": document_id,
        "canonical_url": canonical_url,
        "source_url": source_url,
        "provider": provider,
        "title": title,
        "authors": [],
        "published_at": None,
        "fetched_at": fetched_at,
        "content_hash": content_hash,
        "status": "indexed",
        "artifact_refs": artifact_refs,
        "privacy": "public",
        "review_status": "unreviewed",
        "project_ids": project_ids,
        "thread_ids": thread_ids,
        "entity_ids": entity_ids,
    }


def upsert_document_index(root: Path, document: dict[str, Any]) -> None:
    path = Path(root) / "indexes" / "documents.index.json"
    rows = [row for row in _load_index(path) if row.get("document_id") != document["document_id"]]
    rows.append(
        {
            "document_id": document["document_id"],
            "canonical_url": document["canonical_url"] or None,
            "provider": document["provider"],
            "title": document["title"] or None,
            "status": document["status"],
            "review_status": document["review_status"],
            "thread_ids": document["thread_ids"],
            "entity_ids": document["entity_ids"],
            "project_ids": document["project_ids"],
            "updated_at": document["fetched_at"],
        }
    )
    rows.sort(key=lambda row: (row["document_id"]))
    write_json(path, rows)


def upsert_alias_index(root: Path, entries: list[dict[str, Any]]) -> None:
    path = Path(root) / "indexes" / "aliases.index.json"
    rows = _load_index(path)
    keyed = {
        (row["alias_type"], row["alias_value"], row["target_object_type"], row["target_id"]): row
        for row in rows
    }
    for entry in entries:
        key = (
            entry["alias_type"],
            entry["alias_value"],
            entry["target_object_type"],
            entry["target_id"],
        )
        keyed[key] = entry
    result = sorted(keyed.values(), key=lambda row: (row["alias_type"], row["alias_value"]))
    write_json(path, result)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_store.py -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/store.py tests/connectors/research/test_store.py
git commit -m "feat(research): add canonical artifact store helpers"
```

## Task 2: Persist `ResearchDocument` Objects for URL-Backed Flows

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/connectors/research/test_client.py`:

```python
def test_write_provider_artifacts_persists_document_and_indexes(tmp_path):
    rc = client.ResearchClient(output_dir=tmp_path)
    provider_envelope = {
        "status": "OK",
        "results": [
            {
                "url": "https://example.com/post",
                "title": "Example Post",
                "text": "Example body text",
            }
        ],
        "telemetry": {"attempts": []},
        "meta": {"query": "https://example.com/post"},
    }
    telemetry = {"calls": 1, "providers": ["exa"], "estimated_cost_usd": 0.0, "cost_basis": "test"}

    artifact = rc._write_provider_artifacts(
        kind="fetch",
        slug_source="https://example.com/post",
        project="demo",
        provider_envelope=provider_envelope,
        telemetry=telemetry,
        ledger_provider="exa",
        ledger_endpoint="/contents",
        ledger_mode="fetch",
    )

    document_path = Path(artifact["research_refs"]["document_json"])
    index_path = tmp_path / "indexes" / "documents.index.json"
    aliases_path = tmp_path / "indexes" / "aliases.index.json"

    assert document_path.is_file()
    assert index_path.is_file()
    assert aliases_path.is_file()

    document = json.loads(document_path.read_text(encoding="utf-8"))
    aliases = json.loads(aliases_path.read_text(encoding="utf-8"))

    assert document["canonical_url"] == "https://example.com/post"
    assert document["project_ids"] == ["project:demo"]
    assert any(row["target_id"] == document["document_id"] for row in aliases)


def test_write_visual_ocr_artifacts_persists_document(tmp_path):
    rc = client.ResearchClient(output_dir=tmp_path)
    telemetry = {"calls": 1, "providers": ["visual_ocr"], "estimated_cost_usd": 0.0, "cost_basis": "local_ocr"}
    envelope = {
        "kind": "research_visual_ocr_envelope",
        "url": "https://example.com/post",
        "body_text_visual_ocr": "Recovered visible text",
        "visible_headings": ["Headline"],
        "ocr_confidence": "medium",
        "quote_safe": False,
        "review_status": "unreviewed",
        "provenance": {
            "captured_at": "2026-05-26T09:00:00Z",
            "image_path": "page.png",
            "text_source": "visual_ocr",
        },
    }

    artifact = rc._write_visual_ocr_artifacts(
        slug_source="https://example.com/post",
        project="demo",
        ocr_envelope=envelope,
        telemetry=telemetry,
    )

    document_path = Path(artifact["research_refs"]["document_json"])
    document = json.loads(document_path.read_text(encoding="utf-8"))

    assert document["provider"] == "visual_ocr"
    assert document["artifact_refs"]["normalized_text"] is not None


def test_search_artifact_does_not_persist_document(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("OK")
    _patch_exa_search(
        monkeypatch,
        provider_envelope=provider_envelope,
        exit_code=0,
    )

    result = client.ResearchClient(output_dir=tmp_path).search(
        query="research connector migration",
        project="demo",
    )

    assert "document_json" not in result["artifact"].get("research_refs", {})
    assert not (tmp_path / "objects" / "documents").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_client.py -k "persists_document" -q
```

Expected:

- FAIL because `artifact["research_refs"]` does not exist yet

- [ ] **Step 3: Write minimal implementation**

In `h2t_ops/connectors/research/client.py`, add near the helper section:

```python
from h2t_ops.connectors.research import store
```

Then add a helper method inside `ResearchClient`:

```python
    def _research_root(self) -> Path:
        return self.output_dir

    def _persist_document_object(
        self,
        *,
        project: str,
        provider: str,
        canonical_url: str,
        source_url: str,
        title: str,
        fetched_at: str,
        content_hash: str,
        artifact_refs: dict[str, Any],
    ) -> dict[str, Any]:
        root = self._research_root()
        document = store.build_research_document(
            canonical_url=canonical_url,
            source_url=source_url,
            provider=provider,
            title=title,
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs=artifact_refs,
            project_ids=[f"project:{project}"],
            thread_ids=[],
            entity_ids=[],
        )
        document_path = store.write_object(root, "documents", document["document_id"], document)
        store.upsert_document_index(root, document)
        alias_entries = []
        if source_url:
            alias_entries.append(
                {
                    "alias_type": "url",
                    "alias_value": source_url,
                    "target_object_type": "document",
                    "target_id": document["document_id"],
                    "confidence": "high",
                }
            )
        if canonical_url and canonical_url != source_url:
            alias_entries.append(
                {
                    "alias_type": "url",
                    "alias_value": canonical_url,
                    "target_object_type": "document",
                    "target_id": document["document_id"],
                    "confidence": "high",
                }
            )
        if alias_entries:
            store.upsert_alias_index(root, alias_entries)
        return {
            "document_id": document["document_id"],
            "document_json": str(document_path),
        }
```

Do **not** add document persistence to the generic `_write_provider_artifacts()` seam. That helper is shared by `search`, `similar`, and `answer`, and Phase 1 intentionally does not promote those query-shaped results into canonical `ResearchDocument` objects.

Instead, attach document persistence only inside URL-backed flows that already have a real source URL and concrete source artifact meaning.

Inside `crawl()`, after:

```python
        artifact = self._write_provider_artifacts(
            kind="crawl",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/contents",
            ledger_mode="crawl",
        )
```

add:

```python
        first = safe_provider_envelope.get("results", [{}])[0] if safe_provider_envelope.get("results") else {}
        source_url = str(first.get("url") or safe_provider_envelope.get("meta", {}).get("query") or "")
        canonical_url = source_url
        title = str(first.get("title") or "")
        fetched_at = artifact["created_at"]
        content_hash = store.sha256_text(
            json.dumps(first or safe_provider_envelope.get("meta", {}), sort_keys=True, ensure_ascii=False)
        )
        research_refs = self._persist_document_object(
            project=project,
            provider="exa",
            canonical_url=canonical_url,
            source_url=source_url,
            title=title,
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs={
                "metadata": artifact["artifact_refs"]["artifact_json"],
                "normalized_text": artifact["artifact_refs"]["sources_json"],
                "citation_bundle": None,
                "markdown_mirror": artifact["artifact_refs"]["partial_md"],
            },
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=self.output_dir / artifact["artifact_refs"]["artifact_json"],
            research_refs=research_refs,
        )
```

Inside `fetch_url()`, after:

```python
        artifact = self._write_provider_artifacts(
            kind="fetch",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="fetch_ladder",
            ledger_endpoint="fetch_ladder",
            ledger_mode=provider,
            raw_html_path=metadata.get("raw_html_path"),
        )
```

add:

```python
        canonical_url = str(safe_provider_envelope.get("final_url") or safe_provider_envelope.get("url") or url)
        source_url = str(safe_provider_envelope.get("url") or url)
        title = str(safe_provider_envelope.get("title") or "")
        fetched_at = artifact["created_at"]
        content_hash = store.sha256_text(
            json.dumps(
                {
                    "url": source_url,
                    "final_url": canonical_url,
                    "title": title,
                    "body_text": safe_provider_envelope.get("body_text") or "",
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        research_refs = self._persist_document_object(
            project=project,
            provider=str(safe_provider_envelope.get("provider_used") or provider),
            canonical_url=canonical_url,
            source_url=source_url,
            title=title,
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs={
                "metadata": artifact["artifact_refs"]["artifact_json"],
                "normalized_text": artifact["artifact_refs"]["sources_json"],
                "citation_bundle": None,
                "markdown_mirror": artifact["artifact_refs"]["partial_md"],
            },
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=self.output_dir / artifact["artifact_refs"]["artifact_json"],
            research_refs=research_refs,
        )
```

Inside `_write_visual_ocr_artifacts()`, after `artifact = build_research_artifact(...)`, add:

```python
        fetched_at = artifact["created_at"]
        body_text = str(ocr_envelope.get("body_text_visual_ocr") or "")
        content_hash = store.sha256_text(body_text or str(ocr_envelope.get("url") or "visual-ocr"))
        research_refs = self._persist_document_object(
            project=project,
            provider="visual_ocr",
            canonical_url=str(ocr_envelope.get("url") or ""),
            source_url=str(ocr_envelope.get("url") or ""),
            title=str((ocr_envelope.get("visible_headings") or [""])[0] or ""),
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs={
                "metadata": _artifact_ref_for_path(str(paths["artifact_json"]), output_dir=self.output_dir),
                "normalized_text": _artifact_ref_for_path(str(paths["sources_json"]), output_dir=self.output_dir),
                "citation_bundle": None,
                "markdown_mirror": _artifact_ref_for_path(str(paths["partial_md"]), output_dir=self.output_dir),
            },
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=paths["artifact_json"],
            research_refs=research_refs,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_client.py -k "persists_document" -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): persist canonical documents for url-backed flows"
```

## Task 3: Persist Threads, Runs, and Syntheses for Query-Backed Flows

**Files:**
- Modify: `h2t_ops/connectors/research/store.py`
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_store.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/connectors/research/test_store.py`:

```python
def test_thread_run_and_synthesis_indexes_are_written(tmp_path):
    root = tmp_path / "research"
    thread = store.build_research_thread(
        question="What is Exa similar API surface?",
        created_at="2026-05-26T10:00:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["exa"],
    )
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-26T10:01:00Z",
        query="exa similar api",
        provider_set=["exa"],
        document_ids=[],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="Exa similar is available.",
        created_at="2026-05-26T10:02:00Z",
    )

    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)
    store.upsert_thread_index(root, thread)
    store.upsert_synthesis_index(root, synthesis, project_ids=["project:demo"])

    threads = json.loads((root / "indexes" / "threads.index.json").read_text(encoding="utf-8"))
    syntheses = json.loads((root / "indexes" / "syntheses.index.json").read_text(encoding="utf-8"))

    assert threads[0]["thread_id"] == thread["thread_id"]
    assert syntheses[0]["thread_id"] == thread["thread_id"]
    assert syntheses[0]["has_open_questions"] is False
```

Add to `tests/connectors/research/test_client.py`:

```python
def test_search_persists_thread_and_run_artifacts(tmp_path, monkeypatch):
    rc = client.ResearchClient(output_dir=tmp_path)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "test-secret")
    _patch_exa_search(
        monkeypatch,
        provider_envelope={
            "status": "OK",
            "primary_engine": "exa",
            "fallback_engine_used": None,
            "results": [{"url": "https://example.com/post", "title": "Example Post"}],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 10, "error": None}],
                "reason_for_fallback": None,
                "total_latency_ms": 10,
                "total_cost_usd": 0.0,
            },
            "meta": {
                "query": "exa api",
                "mode": "generic",
                "num_results_requested": 10,
                "num_results_returned": 1,
                "envelope_version": "1",
            },
        },
        exit_code=0,
    )

    result = rc.search(query="exa api", project="demo")

    thread_path = Path(result["artifact"]["research_refs"]["thread_json"])
    run_path = Path(result["artifact"]["research_refs"]["run_json"])

    assert thread_path.is_file()
    assert run_path.is_file()


def test_answer_persists_synthesis_artifact(tmp_path, monkeypatch):
    rc = client.ResearchClient(output_dir=tmp_path)

    monkeypatch.setattr(
        "h2t_ops.connectors.research.exa.answer",
        lambda *args, **kwargs: (
            {
                "status": "OK",
                "primary_engine": "exa",
                "fallback_engine_used": None,
                "results": [{"answer": "Exa supports direct answers."}],
                "telemetry": {
                    "attempts": [{"engine": "exa", "endpoint": "/answer", "http": 200, "latency_ms": 10, "error": None}],
                    "reason_for_fallback": None,
                    "total_latency_ms": 10,
                    "total_cost_usd": 0.0,
                },
                "meta": {
                    "query": "what does exa answer do",
                    "mode": "answer",
                    "num_results_requested": 1,
                    "num_results_returned": 1,
                    "envelope_version": "1",
                },
            },
            0,
        ),
    )
    monkeypatch.setattr(client, "resolve_secret", lambda name: "test-secret")

    result = rc.answer("what does exa answer do")

    synthesis_path = Path(result["artifact"]["research_refs"]["synthesis_json"])
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))

    assert synthesis["status"] == "draft"
    assert synthesis["summary"] == "Exa supports direct answers."
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_store.py tests/connectors/research/test_client.py -k "thread_and_run or synthesis_artifact" -q
```

Expected:

- FAIL because thread/run/synthesis builders and `research_refs` do not exist yet

- [ ] **Step 3: Write minimal implementation**

In `h2t_ops/connectors/research/store.py`, add:

```python
def build_research_thread(
    *,
    question: str,
    created_at: str,
    context_type: str,
    context_id: str,
    domain: str,
    topics: list[str],
) -> dict[str, Any]:
    thread_id = build_thread_id(
        question=question,
        context_type=context_type,
        context_id=context_id,
        created_at=created_at,
    )
    return {
        "schema": "research_thread/v0.1",
        "thread_id": thread_id,
        "question": question,
        "created_at": created_at,
        "status": "open",
        "domain": domain,
        "topics": topics,
        "owner_context": {"context_type": context_type, "context_id": context_id},
        "latest_synthesis_id": None,
    }


def build_research_run(
    *,
    thread_id: str,
    created_at: str,
    query: str,
    provider_set: list[str],
    document_ids: list[str],
) -> dict[str, Any]:
    return {
        "schema": "research_run/v0.1",
        "run_id": build_run_id(
            thread_id=thread_id,
            query=query,
            provider_set=provider_set,
            created_at=created_at,
        ),
        "thread_id": thread_id,
        "created_at": created_at,
        "status": "completed",
        "query": query,
        "provider_set": sorted(provider_set),
        "document_ids": document_ids,
        "artifact_refs": {"query_snapshot": None, "result_manifest": None},
        "notes_ref": None,
        "result_counts": {"documents": len(document_ids), "accepted_documents": len(document_ids)},
    }


def build_research_synthesis(
    *,
    thread_id: str,
    run_ids: list[str],
    summary: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "schema": "research_synthesis/v0.1",
        "synthesis_id": build_synthesis_id(thread_id=thread_id, run_ids=run_ids, synthesis_type="answer"),
        "thread_id": thread_id,
        "run_ids": run_ids,
        "created_at": created_at,
        "status": "draft",
        "review_status": "unreviewed",
        "summary": summary,
        "claims": [],
        "open_questions": [],
        "proposed_edges": [],
    }


def upsert_thread_index(root: Path, thread: dict[str, Any]) -> None:
    path = Path(root) / "indexes" / "threads.index.json"
    rows = [row for row in _load_index(path) if row.get("thread_id") != thread["thread_id"]]
    rows.append(
        {
            "thread_id": thread["thread_id"],
            "question": thread["question"],
            "status": thread["status"],
            "owner_context": thread["owner_context"],
            "topics": thread["topics"],
            "latest_synthesis_id": thread["latest_synthesis_id"],
            "updated_at": thread["created_at"],
        }
    )
    rows.sort(key=lambda row: row["thread_id"])
    write_json(path, rows)


def upsert_synthesis_index(root: Path, synthesis: dict[str, Any], *, project_ids: list[str]) -> None:
    path = Path(root) / "indexes" / "syntheses.index.json"
    rows = [row for row in _load_index(path) if row.get("synthesis_id") != synthesis["synthesis_id"]]
    rows.append(
        {
            "synthesis_id": synthesis["synthesis_id"],
            "thread_id": synthesis["thread_id"],
            "status": synthesis["status"],
            "review_status": synthesis["review_status"],
            "confidence_summary": None,
            "has_open_questions": bool(synthesis["open_questions"]),
            "project_ids": project_ids,
            "updated_at": synthesis["created_at"],
        }
    )
    rows.sort(key=lambda row: row["synthesis_id"])
    write_json(path, rows)
```

In `h2t_ops/connectors/research/client.py`, first add a narrow artifact writeback seam:

```python
    def _attach_research_refs(
        self,
        *,
        artifact: dict[str, Any],
        artifact_json_path: Path,
        research_refs: dict[str, Any],
    ) -> dict[str, Any]:
        artifact["research_refs"] = research_refs
        write_json(artifact_json_path, artifact)
        return artifact
```

Then update `_write_provider_artifacts(...)` so it exposes the concrete artifact-json path to callers:

```python
        artifact = build_research_artifact(
            artifact_id=artifact_id(f"research-{kind}"),
            provider_status=str(provider_envelope.get("status", "FAILED")),
            tool="h2t-ops research",
            artifact_refs={
                "sources_json": paths["sources_json"].name,
                "partial_md": paths["partial_md"].name,
                "artifact_json": paths["artifact_json"].name,
                "raw_html": raw_html_ref,
            },
            telemetry=telemetry,
        )
        write_json(paths["artifact_json"], artifact)
        artifact["_artifact_json_path"] = str(paths["artifact_json"])
```

Callers must treat `_artifact_json_path` as an internal helper key:

- safe to use inside `ResearchClient`
- not part of the public stable research artifact contract
- should be removed before any future external contract freeze if needed

In `h2t_ops/connectors/research/client.py`, then add:

```python
    def _persist_thread_run(
        self,
        *,
        project: str,
        query: str,
        provider: str,
        topics: list[str],
        document_ids: list[str],
        created_at: str,
    ) -> dict[str, str]:
        root = self._research_root()
        thread = store.build_research_thread(
            question=query,
            created_at=created_at,
            context_type="project",
            context_id=f"project:{project}",
            domain="research",
            topics=topics,
        )
        run = store.build_research_run(
            thread_id=thread["thread_id"],
            created_at=created_at,
            query=query,
            provider_set=[provider],
            document_ids=document_ids,
        )
        thread_path = store.write_object(root, "threads", thread["thread_id"], thread)
        run_path = store.write_object(root, "runs", run["run_id"], run)
        store.upsert_thread_index(root, thread)
        return {
            "thread_id": thread["thread_id"],
            "thread_json": str(thread_path),
            "run_id": run["run_id"],
            "run_json": str(run_path),
        }

    def _persist_synthesis(
        self,
        *,
        thread_id: str,
        run_id: str,
        summary: str,
        created_at: str,
        project: str,
    ) -> dict[str, str]:
        root = self._research_root()
        synthesis = store.build_research_synthesis(
            thread_id=thread_id,
            run_ids=[run_id],
            summary=summary,
            created_at=created_at,
        )
        path = store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)
        store.upsert_synthesis_index(root, synthesis, project_ids=[f"project:{project}"])
        return {
            "synthesis_id": synthesis["synthesis_id"],
            "synthesis_json": str(path),
        }
```

Then, inside `search()`, after artifact write:

```python
        research_refs = self._persist_thread_run(
            project=project,
            query=query,
            provider="exa",
            topics=[mode],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=Path(artifact["_artifact_json_path"]),
            research_refs=research_refs,
        )
```

Inside `similar()`, do the same with:

```python
        research_refs = self._persist_thread_run(
            project="default",
            query=url,
            provider="exa",
            topics=["similar"],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=Path(artifact["_artifact_json_path"]),
            research_refs=research_refs,
        )
```

Inside `answer()`, do:

```python
        run_refs = self._persist_thread_run(
            project="default",
            query=query,
            provider="exa",
            topics=["answer"],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        summary_text = str((safe_provider_envelope.get("results") or [{}])[0].get("answer") or "")
        synthesis_refs = self._persist_synthesis(
            thread_id=run_refs["thread_id"],
            run_id=run_refs["run_id"],
            summary=summary_text,
            created_at=artifact["created_at"],
            project="default",
        )
        artifact = self._attach_research_refs(
            artifact=artifact,
            artifact_json_path=Path(artifact["_artifact_json_path"]),
            research_refs={**run_refs, **synthesis_refs},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_store.py tests/connectors/research/test_client.py -k "thread_and_run or synthesis_artifact" -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/store.py h2t_ops/connectors/research/client.py tests/connectors/research/test_store.py tests/connectors/research/test_client.py
git commit -m "feat(research): add thread run synthesis persistence"
```

## Task 4: Update the `h2t-ops:research` Skill Contract

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`

- [ ] **Step 1: Write the failing documentation assertions**

Append to `tests/connectors/research/test_commands.py`:

```python
def test_research_skill_documents_json_first_local_truth():
    text = Path("plugins/h2t-ops/skills/research/SKILL.md").read_text(encoding="utf-8")

    assert "canonical local truth" in text
    assert "Markdown" in text
    assert "threads.index.json" in text
    assert "documents.index.json" in text
    assert "If index and object disagree, object wins." in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py -k "json_first_local_truth" -q
```

Expected:

- FAIL because the skill doc does not mention the new index/canonicality model yet

- [ ] **Step 3: Write minimal documentation update**

Update `plugins/h2t-ops/skills/research/SKILL.md` boundary section to include:

```markdown
## Local Artifact Model

`h2t-ops:research` now maintains a local JSON-first artifact layer:

- canonical local truth = object JSON artifacts
- Markdown = review/presentation mirror only
- shared navigation caches:
  - `threads.index.json`
  - `documents.index.json`
  - `syntheses.index.json`
  - `links.index.json`
  - `aliases.index.json`

Agent lookup order:

1. query shared index
2. resolve object ids
3. read canonical object JSON
4. open Markdown mirror only for human review

Index entries are rebuildable navigation caches, not canonical truth.
If index and object disagree, object wins.
```

Also tighten the existing boundary text so it reads:

```markdown
Research artifacts are evidence, not canonical accepted knowledge.
POS may later ingest them, but local object JSON remains the canonical runtime source in this phase.
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py -k "json_first_local_truth" -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/SKILL.md tests/connectors/research/test_commands.py
git commit -m "docs(research): document canonical objects and shared indexes"
```

## Task 5: Focused Verification and Smoke Evidence

**Files:**
- Create: `docs/reports/2026-05-26-research-artifact-contract-smoke.md`

- [ ] **Step 1: Run focused test suites**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_store.py tests/connectors/research/test_client.py tests/connectors/research/test_commands.py -q
```

Expected:

- PASS

- [ ] **Step 2: Run local fetch smoke**

Run:

```bash
uv.exe run h2t-ops research fetch --url "https://example.com" --provider direct --project demo --json
```

Expected:

- JSON envelope returns normally
- `artifact.research_refs.document_json` is present

- [ ] **Step 3: Run local answer smoke**

Run:

```bash
uv.exe run h2t-ops research answer --query "What does Exa answer do?" --json
```

Expected:

- JSON envelope returns normally
- `artifact.research_refs.thread_json`, `run_json`, and `synthesis_json` are present

- [ ] **Step 4: Record smoke evidence**

Create `docs/reports/2026-05-26-research-artifact-contract-smoke.md`:

```markdown
# Research Artifact Contract Smoke

Date: 2026-05-26

Validated:

- focused research storage/client/skill tests: PASS
- `research fetch` emits canonical `ResearchDocument` object + document/alias index rows
- `research answer` emits `ResearchThread` + `ResearchRun` + `ResearchSynthesis`
- Markdown remains secondary to canonical JSON objects

Notes:

- shared indexes are navigation caches only
- if index and object disagree, object wins
- POS ingestion remains deferred
```

- [ ] **Step 5: Commit**

```bash
git add docs/reports/2026-05-26-research-artifact-contract-smoke.md
git commit -m "docs(research): record artifact contract smoke evidence"
```

## Self-Review

### Spec coverage

- canonical JSON vs Markdown rule: covered in Tasks 1, 2, and 4
- local `ResearchDocument` / `ResearchThread` / `ResearchRun` / `ResearchSynthesis`: covered in Tasks 1 and 3
- shared navigation indexes: covered in Tasks 1 and 3
- multi-key alias routing: covered in Task 1 and Task 2 alias index writes
- project association in phase 1 is represented through `project_ids` on canonical objects and index rows, not folders
- POS compatibility without POS implementation: preserved throughout

No blocking spec gap remains for a phase-1 local artifact wave.

### Placeholder scan

Checked for:

- `TBD`
- `TODO`
- “similar to”
- “appropriate error handling”
- undefined helper names

No placeholders remain.

### Type consistency

The plan consistently uses:

- `document_id`
- `thread_id`
- `run_id`
- `synthesis_id`
- `review_status`
- `artifact_refs`
- `research_refs`

No naming drift remains across tasks.
