from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.connectors.research import store
from h2t_ops.core.errors import ConfigError, NotFoundError, UsageError

INDEX_NAMES = {"documents", "threads", "syntheses", "aliases"}

# Canonical object-type map for future Task 2 (show/resolve helpers): index name,
# canonical schema version, and id key for each supported object type.
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
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"cannot parse research index json: {path}"
        ) from exc


def _read_index(root: Path, index_name: str) -> list[dict[str, Any]]:
    if index_name not in INDEX_NAMES:
        raise UsageError(f"unknown research index: {index_name}")
    path = store.index_path(root, index_name)
    if not path.is_file():
        return []
    data = _read_json(path)
    if not isinstance(data, list):
        raise ConfigError(f"research index is not a list: {path}")
    if not all(isinstance(row, dict) for row in data):
        raise ConfigError(f"research index row is not an object: {path}")
    return data


def _matches_project(index_name: str, row: dict[str, Any], project: str | None) -> bool:
    normalized = normalize_project(project)
    if normalized is None:
        return True
    if index_name == "threads":
        context = row.get("owner_context")
        return isinstance(context, dict) and context.get("context_id") == normalized
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


def _object_path_for_type(root: Path, object_type: str, object_id: str) -> Path:
    if object_type not in OBJECTS:
        raise UsageError(f"unknown research object type: {object_type}")
    directory, _schema, _id_key = OBJECTS[object_type]
    return store.object_path(root, directory, object_id)


def show_object(root: Path, object_type: str, object_id: str) -> dict[str, Any]:
    root = Path(root)
    path = _object_path_for_type(root, object_type, object_id)
    if not path.is_file():
        raise NotFoundError(f"research object not found: {object_type} {object_id} at {path}")
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
    if target_type in OBJECTS:
        directory, _schema, _id_key = OBJECTS[target_type]
        return store.object_path(root, directory, target_id)
    raise ConfigError(f"unknown research target object type: {target_type}")


def resolve_alias(
    root: Path,
    alias_value: str,
    alias_type: str = "url",
) -> dict[str, Any]:
    root = Path(root)
    value = str(alias_value).strip()
    if not value:
        raise UsageError("research resolve requires a non-empty alias value")
    rows = [
        row
        for row in _read_index(root, "aliases")
        if row.get("alias_type") == alias_type and row.get("alias_value") == value
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
        "query": {"alias_type": alias_type, "alias_value": value},
        "count": len(matches),
        "matches": matches,
    }
