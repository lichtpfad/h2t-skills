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


def build_document_id(
    *,
    canonical_url: str,
    content_hash: str,
    provider: str,
    fetched_at: str,
) -> str:
    if canonical_url.strip():
        return _sha("research-doc", canonical_url)
    return _sha("research-doc", content_hash, provider, fetched_at[:16])


def build_thread_id(
    *,
    question: str,
    context_type: str,
    context_id: str,
    created_at: str,
) -> str:
    return _sha("research-thread", question, context_type, context_id, created_at[:10])


def build_run_id(
    *,
    thread_id: str,
    query: str,
    provider_set: list[str],
    created_at: str,
) -> str:
    return _sha("research-run", thread_id, query, ",".join(sorted(provider_set)), created_at)


def build_synthesis_id(
    *,
    thread_id: str,
    run_ids: list[str],
    synthesis_type: str,
) -> str:
    return _sha("research-synthesis", thread_id, ",".join(sorted(run_ids)), synthesis_type)


def object_path(root: Path, object_kind: str, object_id: str) -> Path:
    return Path(root) / "objects" / object_kind / f"{object_id}.json"


def index_path(root: Path, index_name: str) -> Path:
    return Path(root) / "indexes" / f"{index_name}.index.json"


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_index(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_object(root: Path, object_kind: str, object_id: str, payload: dict[str, Any]) -> Path:
    path = object_path(root, object_kind, object_id)
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
        "result_counts": {
            "documents": len(document_ids),
            "accepted_documents": len(document_ids),
        },
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
        "synthesis_id": build_synthesis_id(
            thread_id=thread_id,
            run_ids=run_ids,
            synthesis_type="answer",
        ),
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


def upsert_document_index(root: Path, document: dict[str, Any]) -> None:
    path = index_path(root, "documents")
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
    rows.sort(key=lambda row: row["document_id"])
    write_json(path, rows)


def upsert_thread_index(root: Path, thread: dict[str, Any]) -> None:
    path = index_path(root, "threads")
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


def upsert_synthesis_index(
    root: Path,
    synthesis: dict[str, Any],
    *,
    project_ids: list[str],
) -> None:
    path = index_path(root, "syntheses")
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


def upsert_alias_index(root: Path, entries: list[dict[str, Any]]) -> None:
    path = index_path(root, "aliases")
    rows = _load_index(path)
    keyed = {
        (
            row["alias_type"],
            row["alias_value"],
            row["target_object_type"],
            row["target_id"],
        ): row
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
    result = sorted(
        keyed.values(),
        key=lambda row: (
            row["alias_type"],
            row["alias_value"],
            row["target_object_type"],
            row["target_id"],
        ),
    )
    write_json(path, result)
