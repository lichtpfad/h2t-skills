from __future__ import annotations

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


def test_list_index_unknown_raises_usage_error(tmp_path):
    with pytest.raises(UsageError, match="unknown research index"):
        navigation.list_index(tmp_path / "research", "unknown")


def test_list_documents_index_filters_by_project(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "document_id": "research-doc:demo",
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
            "document_id": "research-doc:other",
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
    assert result["items"][0]["document_id"] == "research-doc:demo"


def test_list_threads_index_filters_by_owner_context(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "thread_id": "research-thread:demo",
            "question": "A?",
            "status": "open",
            "owner_context": {"context_type": "project", "context_id": "project:demo"},
            "topics": ["a"],
            "latest_synthesis_id": None,
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "thread_id": "research-thread:other",
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
    assert result["items"][0]["thread_id"] == "research-thread:demo"


def test_list_syntheses_index_filters_by_project(tmp_path):
    root = tmp_path / "research"
    rows = [
        {
            "synthesis_id": "research-synthesis:demo",
            "thread_id": "research-thread:demo",
            "status": "draft",
            "review_status": "unreviewed",
            "confidence_summary": None,
            "has_open_questions": False,
            "project_ids": ["project:demo"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "synthesis_id": "research-synthesis:other",
            "thread_id": "research-thread:other",
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
    assert result["items"][0]["synthesis_id"] == "research-synthesis:demo"


def test_list_index_non_list_raises_configerror(tmp_path):
    root = tmp_path / "research"
    store.write_json(store.index_path(root, "documents"), {"not": "a list"})

    with pytest.raises(ConfigError, match="research index is not a list"):
        navigation.list_index(root, "documents")


def test_list_index_invalid_json_raises_configerror(tmp_path):
    root = tmp_path / "research"
    path = store.index_path(root, "documents")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ConfigError, match="cannot parse research index json"):
        navigation.list_index(root, "documents")


def test_list_index_non_object_row_raises_configerror(tmp_path):
    root = tmp_path / "research"
    store.write_json(store.index_path(root, "documents"), ["not-a-object"])

    with pytest.raises(ConfigError, match="research index row is not an object"):
        navigation.list_index(root, "documents")


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

    assert result == {
        "kind": "research_object",
        "object_type": "document",
        "object_id": document["document_id"],
        "root": str(root),
        "object": document,
    }


def test_show_object_missing_file_raises_notfound(tmp_path):
    with pytest.raises(NotFoundError, match="research object not found"):
        navigation.show_object(tmp_path / "research", "document", "research-doc:missing")


def test_show_object_schema_mismatch_raises_configerror(tmp_path):
    root = tmp_path / "research"
    bad = {
        "schema": "research_thread/v0.1",
        "document_id": "research-doc:bad",
    }
    store.write_json(store.object_path(root, "documents", "research-doc:bad"), bad)

    with pytest.raises(ConfigError, match="research object schema mismatch"):
        navigation.show_object(root, "document", "research-doc:bad")


def test_show_object_id_mismatch_raises_configerror(tmp_path):
    root = tmp_path / "research"
    bad = {
        "schema": "research_document/v0.1",
        "document_id": "research-doc:other",
    }
    store.write_json(store.object_path(root, "documents", "research-doc:bad"), bad)

    with pytest.raises(ConfigError, match="research object id mismatch"):
        navigation.show_object(root, "document", "research-doc:bad")


def test_show_object_unknown_type_raises_usageerror(tmp_path):
    with pytest.raises(UsageError, match="unknown research object type"):
        navigation.show_object(tmp_path / "research", "bad-type", "research-bad:abc")


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


def test_resolve_alias_returns_stale_state(tmp_path):
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


def test_resolve_alias_rejects_path_like_unknown_target_type(tmp_path):
    root = tmp_path / "research"
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "../secrets",
                "target_id": "x",
                "confidence": "high",
            }
        ],
    )

    with pytest.raises(ConfigError, match="unknown research target object type"):
        navigation.resolve_alias(root, alias_value="https://example.com/post", alias_type="url")


def test_resolve_alias_empty_value_raises_usageerror(tmp_path):
    with pytest.raises(UsageError, match="research resolve requires a non-empty alias value"):
        navigation.resolve_alias(tmp_path / "research", alias_value="")
