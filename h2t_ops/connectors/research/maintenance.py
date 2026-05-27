from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from h2t_ops.connectors.research import store
from h2t_ops.core.errors import UsageError


OBJECTS = {
    "document": {
        "directory": "documents",
        "schema": "research_document/v0.1",
        "id_key": "document_id",
    },
    "thread": {
        "directory": "threads",
        "schema": "research_thread/v0.1",
        "id_key": "thread_id",
    },
    "run": {
        "directory": "runs",
        "schema": "research_run/v0.1",
        "id_key": "run_id",
    },
    "synthesis": {
        "directory": "syntheses",
        "schema": "research_synthesis/v0.1",
        "id_key": "synthesis_id",
    },
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
    finding: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        finding["path"] = str(path)
    if object_type is not None:
        finding["object_type"] = object_type
    if object_id is not None:
        finding["object_id"] = object_id
    if ref is not None:
        finding["ref"] = ref
    return finding


def _read_json_file(path: Path) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        detail = getattr(exc, "msg", str(exc))
        return None, _finding(
            "error",
            "object_json_invalid",
            f"Invalid JSON: {detail}",
            path=path,
        )


def _iter_object_files(root: Path, directory: str) -> list[Path]:
    object_dir = Path(root) / "objects" / directory
    if not object_dir.is_dir():
        return []
    paths = list(object_dir.glob("*.json"))
    if os.name == "nt":
        paths.extend(_iter_windows_alternate_json_streams(object_dir))
    return sorted(paths)


def _iter_windows_alternate_json_streams(object_dir: Path) -> list[Path]:
    import ctypes
    from ctypes import wintypes

    class WIN32_FIND_STREAM_DATA(ctypes.Structure):
        _fields_ = [
            ("StreamSize", wintypes.LARGE_INTEGER),
            ("cStreamName", wintypes.WCHAR * 296),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstStreamW
    find_first.argtypes = [
        wintypes.LPCWSTR,
        wintypes.INT,
        ctypes.POINTER(WIN32_FIND_STREAM_DATA),
        wintypes.DWORD,
    ]
    find_first.restype = wintypes.HANDLE
    find_next = kernel32.FindNextStreamW
    find_next.argtypes = [wintypes.HANDLE, ctypes.POINTER(WIN32_FIND_STREAM_DATA)]
    find_next.restype = wintypes.BOOL
    find_close = kernel32.FindClose
    find_close.argtypes = [wintypes.HANDLE]
    find_close.restype = wintypes.BOOL
    invalid_handle = wintypes.HANDLE(-1).value

    paths: list[Path] = []
    for base_path in object_dir.iterdir():
        if not base_path.is_file():
            continue
        data = WIN32_FIND_STREAM_DATA()
        handle = find_first(str(base_path), 0, ctypes.byref(data), 0)
        if handle == invalid_handle:
            continue
        try:
            while True:
                stream_name = data.cStreamName
                if stream_name.startswith(":") and stream_name.endswith(":$DATA"):
                    stream = stream_name[1:-6]
                    if stream.endswith(".json"):
                        paths.append(Path(f"{base_path}:{stream}"))
                if not find_next(handle, ctypes.byref(data)):
                    break
        finally:
            find_close(handle)
    return paths


def _load_objects(root: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    objects: dict[str, dict[str, dict[str, Any]]] = {object_type: {} for object_type in OBJECTS}
    findings: list[dict[str, Any]] = []

    for object_type, spec in OBJECTS.items():
        directory = spec["directory"]
        expected_schema = spec["schema"]
        id_key = spec["id_key"]
        for path in _iter_object_files(root, directory):
            data, finding = _read_json_file(path)
            if finding is not None:
                findings.append(finding)
                continue
            if not isinstance(data, dict):
                findings.append(
                    _finding(
                        "error",
                        "object_not_mapping",
                        "Canonical object JSON must be an object",
                        path=path,
                        object_type=object_type,
                    )
                )
                continue

            declared_id = data.get(id_key)
            schema_matches = data.get("schema") == expected_schema
            id_matches = declared_id == path.stem

            if not schema_matches:
                findings.append(
                    _finding(
                        "error",
                        "object_schema_mismatch",
                        f"Expected schema {expected_schema!r}",
                        path=path,
                        object_type=object_type,
                        object_id=declared_id if isinstance(declared_id, str) else None,
                        ref="schema",
                    )
                )
            if not id_matches:
                findings.append(
                    _finding(
                        "error",
                        "object_id_mismatch",
                        f"Expected {id_key} to match filename stem",
                        path=path,
                        object_type=object_type,
                        object_id=declared_id if isinstance(declared_id, str) else None,
                        ref=id_key,
                    )
                )
            if schema_matches and id_matches and isinstance(declared_id, str):
                objects[object_type][declared_id] = data

    return objects, findings


def _read_index(root: Path, index_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = store.index_path(root, index_name)
    if not path.is_file():
        return [], []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        detail = getattr(exc, "msg", str(exc))
        return [], [
            _finding(
                "error",
                "index_json_invalid",
                f"Invalid index JSON: {detail}",
                path=path,
            )
        ]

    if not isinstance(data, list):
        return [], [
            _finding(
                "error",
                "index_not_list",
                "Research index JSON must be a list",
                path=path,
            )
        ]

    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, dict):
            rows.append(row)
            continue
        findings.append(
            _finding(
                "error",
                "index_row_not_mapping",
                "Research index row must be an object",
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
        path = store.index_path(root, index_name)
        rows, index_findings = _read_index(root, index_name)
        findings.extend(index_findings)
        for row in rows:
            object_id = row.get(id_key)
            if not isinstance(object_id, str) or not object_id.strip():
                continue
            if object_id in objects[object_type]:
                continue
            findings.append(
                _finding(
                    "warning",
                    "index_object_missing",
                    "Index row points to a missing canonical object",
                    path=path,
                    object_type=object_type,
                    object_id=object_id,
                    ref=id_key,
                )
            )
    return findings


def _check_alias_refs(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    path = store.index_path(root, "aliases")
    rows, findings = _read_index(root, "aliases")
    for row in rows:
        target_type = row.get("target_object_type")
        target_id = row.get("target_id")
        object_type = target_type if isinstance(target_type, str) else None
        object_id = target_id if isinstance(target_id, str) else None

        if object_type not in objects:
            findings.append(
                _finding(
                    "error",
                    "alias_target_type_unknown",
                    "Alias target object type is unknown",
                    path=path,
                    object_type=object_type,
                    object_id=object_id,
                    ref="target_object_type",
                )
            )
            continue
        if not isinstance(target_id, str) or not target_id.strip():
            findings.append(
                _finding(
                    "warning",
                    "alias_target_missing",
                    "Alias target object does not exist",
                    path=path,
                    object_type=target_type,
                    object_id=object_id,
                    ref="target_id",
                )
            )
            continue
        if target_id not in objects[target_type]:
            findings.append(
                _finding(
                    "warning",
                    "alias_target_missing",
                    "Alias target object does not exist",
                    path=path,
                    object_type=target_type,
                    object_id=target_id,
                    ref="target_id",
                )
            )
    return findings


def _artifact_ref_path(root: Path, raw_ref: Any) -> Path | None:
    if not isinstance(raw_ref, str) or not raw_ref.strip():
        return None
    path = Path(raw_ref)
    if path.is_absolute():
        return path
    return Path(root) / path


def _check_artifact_refs(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for object_type, typed_objects in objects.items():
        id_key = OBJECTS[object_type]["id_key"]
        for object_id, data in typed_objects.items():
            refs: list[tuple[str, Any]] = []
            artifact_refs = data.get("artifact_refs")
            if isinstance(artifact_refs, dict):
                refs.extend((f"artifact_refs.{key}", value) for key, value in artifact_refs.items())
            refs.append(("notes_ref", data.get("notes_ref")))

            for ref_key, raw_ref in refs:
                ref_path = _artifact_ref_path(root, raw_ref)
                if ref_path is None or ref_path.exists():
                    continue
                findings.append(
                    _finding(
                        "warning",
                        "artifact_ref_missing",
                        "Artifact reference points to a missing file",
                        path=ref_path,
                        object_type=object_type,
                        object_id=data.get(id_key) if isinstance(data.get(id_key), str) else object_id,
                        ref=ref_key,
                    )
                )
    return findings


def _check_cross_object_refs(
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for thread_id, thread in objects["thread"].items():
        synthesis_id = thread.get("latest_synthesis_id")
        if not isinstance(synthesis_id, str) or not synthesis_id.strip():
            continue
        if synthesis_id not in objects["synthesis"]:
            findings.append(
                _finding(
                    "warning",
                    "thread_latest_synthesis_missing",
                    "Thread latest synthesis does not exist",
                    object_type="thread",
                    object_id=thread_id,
                    ref=synthesis_id,
                )
            )

    for run_id, run in objects["run"].items():
        thread_id = run.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip() and thread_id not in objects["thread"]:
            findings.append(
                _finding(
                    "warning",
                    "run_thread_missing",
                    "Run thread does not exist",
                    object_type="run",
                    object_id=run_id,
                    ref=thread_id,
                )
            )

        document_ids = run.get("document_ids")
        if not isinstance(document_ids, list):
            continue
        for document_id in document_ids:
            if not isinstance(document_id, str) or not document_id.strip():
                continue
            if document_id in objects["document"]:
                continue
            findings.append(
                _finding(
                    "warning",
                    "run_document_missing",
                    "Run document does not exist",
                    object_type="run",
                    object_id=run_id,
                    ref=document_id,
                )
            )

    for synthesis_id, synthesis in objects["synthesis"].items():
        thread_id = synthesis.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip() and thread_id not in objects["thread"]:
            findings.append(
                _finding(
                    "warning",
                    "synthesis_thread_missing",
                    "Synthesis thread does not exist",
                    object_type="synthesis",
                    object_id=synthesis_id,
                    ref=thread_id,
                )
            )

        run_ids = synthesis.get("run_ids")
        if not isinstance(run_ids, list):
            continue
        for run_id in run_ids:
            if not isinstance(run_id, str) or not run_id.strip():
                continue
            if run_id in objects["run"]:
                continue
            findings.append(
                _finding(
                    "warning",
                    "synthesis_run_missing",
                    "Synthesis run does not exist",
                    object_type="synthesis",
                    object_id=synthesis_id,
                    ref=run_id,
                )
            )

    return findings


def _status(findings: list[dict[str, Any]]) -> str:
    severities = {finding.get("severity") for finding in findings}
    if "error" in severities:
        return "error"
    if "warning" in severities:
        return "warning"
    return "ok"


def _counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "errors": sum(1 for finding in findings if finding.get("severity") == "error"),
        "warnings": sum(1 for finding in findings if finding.get("severity") == "warning"),
        "info": sum(1 for finding in findings if finding.get("severity") == "info"),
    }


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


def _document_index_row(document: dict[str, Any]) -> dict[str, Any]:
    return {
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


def _thread_index_row(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "thread_id": thread["thread_id"],
        "question": thread["question"],
        "status": thread["status"],
        "owner_context": thread["owner_context"],
        "topics": thread["topics"],
        "latest_synthesis_id": thread["latest_synthesis_id"],
        "updated_at": thread["created_at"],
    }


def _synthesis_project_ids(
    synthesis: dict[str, Any],
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    thread_id = synthesis.get("thread_id")
    if not isinstance(thread_id, str):
        return []
    thread = objects.get("thread", {}).get(thread_id)
    if not isinstance(thread, dict):
        return []
    owner_context = thread.get("owner_context")
    if not isinstance(owner_context, dict):
        return []
    context_id = owner_context.get("context_id")
    if isinstance(context_id, str) and context_id.startswith("project:"):
        return [context_id]
    return []


def _synthesis_index_row(
    synthesis: dict[str, Any],
    objects: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "synthesis_id": synthesis["synthesis_id"],
        "thread_id": synthesis["thread_id"],
        "status": synthesis["status"],
        "review_status": synthesis["review_status"],
        "confidence_summary": None,
        "has_open_questions": bool(synthesis["open_questions"]),
        "project_ids": _synthesis_project_ids(synthesis, objects),
        "updated_at": synthesis["created_at"],
    }


ALIAS_SORT_KEYS = ("alias_type", "alias_value", "target_object_type", "target_id")

REBUILD_REQUIRED_FIELDS = {
    "document": (
        "document_id",
        "canonical_url",
        "provider",
        "title",
        "status",
        "review_status",
        "thread_ids",
        "entity_ids",
        "project_ids",
        "fetched_at",
    ),
    "thread": (
        "thread_id",
        "question",
        "status",
        "owner_context",
        "topics",
        "latest_synthesis_id",
        "created_at",
    ),
    "run": ("run_id", "thread_id", "document_ids"),
    "synthesis": (
        "synthesis_id",
        "thread_id",
        "status",
        "review_status",
        "open_questions",
        "created_at",
    ),
}


def _alias_rows(objects: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    keyed: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for document_id, document in objects["document"].items():
        values: set[str] = set()
        for key in ("canonical_url", "source_url"):
            value = document.get(key)
            if isinstance(value, str) and value.strip():
                values.add(value)
        for alias_value in values:
            row = {
                "alias_type": "url",
                "alias_value": alias_value,
                "target_object_type": "document",
                "target_id": document_id,
                "confidence": "high",
            }
            keyed[
                (
                    row["alias_type"],
                    row["alias_value"],
                    row["target_object_type"],
                    row["target_id"],
                )
            ] = row
    return sorted(keyed.values(), key=lambda row: tuple(row[key] for key in ALIAS_SORT_KEYS))


def _preserved_alias_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, findings = _read_index(root, "aliases")
    if findings:
        return [], findings
    preserved = [
        row
        for row in rows
        if row.get("alias_type") != "url" or row.get("target_object_type") != "document"
    ]
    return sorted(
        preserved,
        key=lambda row: tuple(str(row.get(key, "")) for key in ALIAS_SORT_KEYS),
    ), []


def _validate_rebuild_objects(
    root: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for object_type, typed_objects in objects.items():
        required_fields = REBUILD_REQUIRED_FIELDS[object_type]
        id_key = OBJECTS[object_type]["id_key"]
        directory = OBJECTS[object_type]["directory"]
        for object_id, data in typed_objects.items():
            for field in required_fields:
                if field in data:
                    continue
                declared_id = data.get(id_key)
                findings.append(
                    _finding(
                        "error",
                        "object_required_field_missing",
                        f"Canonical object is missing required field {field!r}",
                        path=store.object_path(root, directory, object_id),
                        object_type=object_type,
                        object_id=declared_id if isinstance(declared_id, str) else object_id,
                        ref=field,
                    )
                )
    return findings


def _rebuild_counts(
    objects: dict[str, dict[str, dict[str, Any]]],
    alias_count: int,
) -> dict[str, int]:
    return {
        "documents": len(objects["document"]),
        "threads": len(objects["thread"]),
        "runs": len(objects["run"]),
        "syntheses": len(objects["synthesis"]),
        "aliases": alias_count,
    }


def _empty_rebuild_counts() -> dict[str, int]:
    return {
        "documents": 0,
        "threads": 0,
        "runs": 0,
        "syntheses": 0,
        "aliases": 0,
    }


def _rebuild_error_envelope(
    root: Path,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "kind": "research_rebuild_indexes",
        "root": str(root),
        "status": "error",
        "written": [],
        "counts": _empty_rebuild_counts(),
        "findings": findings,
    }


def rebuild_indexes(root: Path) -> dict[str, Any]:
    root = Path(root)
    objects, findings = _load_objects(root)
    if findings:
        return _rebuild_error_envelope(root, findings)

    findings = _validate_rebuild_objects(root, objects)
    preserved_aliases, alias_findings = _preserved_alias_rows(root)
    findings.extend(alias_findings)
    if findings:
        return _rebuild_error_envelope(root, findings)

    documents = [
        _document_index_row(document)
        for _, document in sorted(objects["document"].items())
    ]
    threads = [
        _thread_index_row(thread)
        for _, thread in sorted(objects["thread"].items())
    ]
    syntheses = [
        _synthesis_index_row(synthesis, objects)
        for _, synthesis in sorted(objects["synthesis"].items())
    ]
    aliases = sorted(
        [*preserved_aliases, *_alias_rows(objects)],
        key=lambda row: tuple(str(row.get(key, "")) for key in ALIAS_SORT_KEYS),
    )

    indexes = {
        "documents": documents,
        "threads": threads,
        "syntheses": syntheses,
        "aliases": aliases,
    }
    written: list[str] = []
    for index_name, rows in indexes.items():
        path = store.index_path(root, index_name)
        store.write_json(path, rows)
        written.append(str(path))

    return {
        "kind": "research_rebuild_indexes",
        "root": str(root),
        "status": "ok",
        "written": written,
        "counts": _rebuild_counts(objects, len(aliases)),
        "findings": [],
    }


def cleanup(root: Path, dry_run: bool = True) -> None:
    raise UsageError("research maintenance cleanup is not implemented yet")
