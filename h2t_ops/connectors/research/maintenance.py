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
    _, findings = _load_objects(Path(root))
    return {
        "kind": "research_doctor",
        "root": str(root),
        "status": _status(findings),
        "counts": _counts(findings),
        "findings": findings,
    }


def rebuild_indexes(root: Path) -> None:
    raise UsageError("research maintenance rebuild_indexes is not implemented yet")


def cleanup(root: Path, dry_run: bool = True) -> None:
    raise UsageError("research maintenance cleanup is not implemented yet")
