from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.connectors.research import store
from h2t_ops.core.errors import ConfigError, UsageError


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
