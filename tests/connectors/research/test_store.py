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
