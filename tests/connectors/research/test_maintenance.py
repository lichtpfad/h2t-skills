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


def test_doctor_reports_non_utf8_canonical_object_as_error(tmp_path):
    root = tmp_path / "research"
    path = store.object_path(root, "documents", "research-doc:bad-encoding")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00")

    result = maintenance.doctor(root)

    matching_findings = [
        finding
        for finding in result["findings"]
        if finding["code"] == "object_json_invalid" and finding["path"] == str(path)
    ]
    assert result["status"] == "error"
    assert matching_findings


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


def _write_existing_indexes(root):
    rows = {
        "documents": [{"document_id": "research-doc:existing", "project_ids": ["project:demo"]}],
        "threads": [{"thread_id": "research-thread:existing", "topics": ["demo"]}],
        "syntheses": [{"synthesis_id": "research-synthesis:existing", "project_ids": ["project:demo"]}],
        "aliases": [
            {
                "alias_type": "topic",
                "alias_value": "demo",
                "target_object_type": "thread",
                "target_id": "research-thread:existing",
                "confidence": "medium",
            }
        ],
    }
    for index_name, index_rows in rows.items():
        store.write_json(store.index_path(root, index_name), index_rows)
    return {
        index_name: store.index_path(root, index_name).read_text(encoding="utf-8")
        for index_name in rows
    }


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
    artifact_findings = [
        finding for finding in result["findings"] if finding["code"] == "artifact_ref_missing"
    ]
    refs = {finding["ref"] for finding in artifact_findings}
    assert "artifact_refs.metadata" in refs
    assert "artifact_refs.normalized_text" in refs
    assert "artifact_refs.markdown_mirror" in refs
    assert "artifact_refs.citation_bundle" not in refs
    assert document["document_id"] in {
        finding.get("object_id") for finding in artifact_findings
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
        created_at="2026-05-27T10:01:00Z",
        query="What is Exa?",
        provider_set=["exa"],
        document_ids=[document["document_id"]],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="Summary",
        created_at="2026-05-27T10:02:00Z",
    )
    thread["latest_synthesis_id"] = synthesis["synthesis_id"]
    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)

    result = maintenance.rebuild_indexes(root)

    assert result["kind"] == "research_rebuild_indexes"
    assert result["status"] == "ok"
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

    assert documents == [maintenance._document_index_row(document)]
    assert threads == [maintenance._thread_index_row(thread)]
    assert syntheses == [
        maintenance._synthesis_index_row(
            synthesis,
            {"thread": {thread["thread_id"]: thread}},
        )
    ]
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
        [{"document_id": "research-doc:stale", "project_ids": ["project:stale"]}],
    )

    result = maintenance.rebuild_indexes(root)

    documents = json.loads(store.index_path(root, "documents").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert documents == [maintenance._document_index_row(document)]


def test_rebuild_indexes_preserves_non_url_alias_rows(tmp_path):
    root = tmp_path / "research"
    document = _demo_document(root)
    preserved_alias = {
        "alias_type": "topic",
        "alias_value": "demo",
        "target_object_type": "thread",
        "target_id": "research-thread:demo",
        "confidence": "medium",
    }
    stale_url_alias = {
        "alias_type": "url",
        "alias_value": "https://example.com/stale",
        "target_object_type": "document",
        "target_id": "research-doc:stale",
        "confidence": "high",
    }
    store.write_json(store.index_path(root, "aliases"), [stale_url_alias, preserved_alias])

    result = maintenance.rebuild_indexes(root)

    aliases = json.loads(store.index_path(root, "aliases").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert aliases == [
        preserved_alias,
        {
            "alias_type": "url",
            "alias_value": "https://example.com/post",
            "target_object_type": "document",
            "target_id": document["document_id"],
            "confidence": "high",
        },
    ]


def test_rebuild_indexes_with_malformed_object_does_not_overwrite_existing_indexes(tmp_path):
    root = tmp_path / "research"
    before = _write_existing_indexes(root)
    malformed = store.object_path(root, "documents", "research-doc:bad")
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{bad json", encoding="utf-8")

    result = maintenance.rebuild_indexes(root)

    assert result["status"] == "error"
    assert result["written"] == []
    assert {
        index_name: store.index_path(root, index_name).read_text(encoding="utf-8")
        for index_name in before
    } == before


def test_rebuild_indexes_with_incomplete_object_does_not_overwrite_existing_indexes(tmp_path):
    root = tmp_path / "research"
    before = _write_existing_indexes(root)
    document_id = "research-doc:incomplete"
    store.write_json(
        store.object_path(root, "documents", document_id),
        {
            "schema": "research_document/v0.1",
            "document_id": document_id,
        },
    )

    result = maintenance.rebuild_indexes(root)

    assert result["status"] == "error"
    assert result["written"] == []
    assert "object_required_field_missing" in {
        finding["code"] for finding in result["findings"]
    }
    assert {
        index_name: store.index_path(root, index_name).read_text(encoding="utf-8")
        for index_name in before
    } == before


def test_rebuild_indexes_with_malformed_alias_index_does_not_overwrite_existing_indexes(tmp_path):
    root = tmp_path / "research"
    before = _write_existing_indexes(root)
    store.index_path(root, "aliases").write_text("{bad json", encoding="utf-8")
    before["aliases"] = store.index_path(root, "aliases").read_text(encoding="utf-8")

    result = maintenance.rebuild_indexes(root)

    assert result["status"] == "error"
    assert result["written"] == []
    assert result["findings"][0]["code"] == "index_json_invalid"
    assert {
        index_name: store.index_path(root, index_name).read_text(encoding="utf-8")
        for index_name in before
    } == before
