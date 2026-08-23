"""Granola sync — the only layer that owns files and cursor state.

The client stays a pure API adapter; everything below writes to a lake
directory: <dir>/summaries/<note_id>.{md,json}, <dir>/transcripts/<note_id>.{md,json},
plus manifest.jsonl and a cursor file.

Cursor runs on updated_at, not created_at: Granola keeps editing a note after
it is created (note.edited always carries changed_fields ["summary"]), so a
created_at cursor would freeze the first version forever.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Optional, Set  # noqa: F401

from h2t_ops.core.errors import UsageError

from .commands import _fmt_note_md, _fmt_transcript_md, _now_iso

VALID_INCLUDE = {"summaries", "transcripts"}
CURSOR_PATH_DEFAULT = Path.home() / ".dor" / "lake" / "_cursors" / "granola.json"


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}


def _synced_versions(manifest: Path) -> dict[str, set[str]]:
    """(note_id, updated_at) key -> include parts already written for that version.

    Records predating include-tracking carry no "include" field. Treat them as
    complete: an existing lake must not trigger a surprise full refetch.
    """
    seen: dict[str, set[str]] = {}
    if not manifest.is_file():
        return seen
    with manifest.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("note_id"):
                key = f"{rec['note_id']}@{rec.get('updated_at') or ''}"
                parts = rec.get("include")
                covered = set(parts) if isinstance(parts, list) else set(VALID_INCLUDE)
                seen.setdefault(key, set()).update(covered)
    return seen


def _write_pair(folder: Path, note_id: str, md: str, raw: Any) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{note_id}.md").write_text(md, encoding="utf-8")
    (folder / f"{note_id}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def sync_notes(
    client: Any,
    *,
    to: Path,
    include: Iterable[str],
    cursor_file: Path | None = None,
    since: str | None = None,
    since_cursor: bool = False,
    folder: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Pull notes into a lake directory. Returns run counters."""
    include = set(include)
    unknown = include - VALID_INCLUDE
    if unknown:
        raise UsageError(
            f"unknown --include values: {sorted(unknown)} (valid: {sorted(VALID_INCLUDE)})"
        )

    lake = Path(to).expanduser()
    lake.mkdir(parents=True, exist_ok=True)
    cursor_path = Path(cursor_file).expanduser() if cursor_file else CURSOR_PATH_DEFAULT
    cursor = _load_json(cursor_path)

    updated_after = since
    if since_cursor and not updated_after:
        updated_after = cursor.get("last_seen_ts")

    folder_id = client.resolve_folder_id(folder) if folder else None
    listing = client.list_notes(limit=limit, updated_after=updated_after, folder_id=folder_id)

    manifest_path = lake / "manifest.jsonl"
    seen = _synced_versions(manifest_path)
    written: list[str] = []
    synced = skipped = errors = 0
    last_seen_ts = cursor.get("last_seen_ts")
    last_seen_id = cursor.get("last_seen_id")

    for row in listing["rows"]:
        note_id = row.get("id") or row.get("note_id")
        if not note_id:
            continue
        version = f"{note_id}@{row.get('updated_at') or ''}"
        missing = include - seen.get(version, set())
        if not missing:
            skipped += 1
            continue
        try:
            note = client.get_note(note_id)
            if "summaries" in missing:
                _write_pair(lake / "summaries", note_id, _fmt_note_md(note), note)
            if "transcripts" in missing:
                data = client.get_transcript(note_id)
                md = _fmt_transcript_md(note, data["transcript"],
                                        truncated=data.get("truncated", False))
                _write_pair(lake / "transcripts", note_id, md, data)
        except Exception as exc:  # noqa: BLE001 — one bad note must not kill the run
            errors += 1
            print(f"WARN: skip {note_id}: {exc}")
            continue

        ts = note.get("updated_at") or row.get("updated_at")
        written.append(json.dumps({
            "note_id": note_id,
            "title": note.get("title") or row.get("title"),
            "created_at": note.get("created_at") or row.get("created_at"),
            "updated_at": ts,
            "include": sorted(missing),
            "synced_at": _now_iso(),
        }, ensure_ascii=False))
        seen.setdefault(version, set()).update(missing)
        synced += 1
        if ts and (last_seen_ts is None or ts > last_seen_ts):
            last_seen_ts, last_seen_id = ts, note_id

    if written:
        with manifest_path.open("a", encoding="utf-8") as fh:
            for line in written:
                fh.write(line + "\n")

    cursor.update({
        "source": "granola",
        "cursor_type": "updated_at",
        "last_seen_ts": last_seen_ts,
        "last_seen_id": last_seen_id,
        "last_run_at": _now_iso(),
        "last_run_status": "ok" if errors == 0 else f"partial({errors})",
        "items_ingested": cursor.get("items_ingested", 0) + synced,
        "version": 1,
    })
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(cursor, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "cursor_file": str(cursor_path),
        "lake": str(lake),
    }
