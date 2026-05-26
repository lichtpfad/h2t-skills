from __future__ import annotations

import pytest

from h2t_ops.connectors.research import navigation, store
from h2t_ops.core.errors import ConfigError, UsageError


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
