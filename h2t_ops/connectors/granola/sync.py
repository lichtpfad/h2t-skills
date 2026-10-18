"""Granola sync — the only layer that owns files and cursor state.

The client stays a pure API adapter; everything below writes to a lake
directory: <dir>/summaries/<note_id>.{md,json}, <dir>/transcripts/<note_id>.{md,json},
through core.lake — manifest.jsonl, own files only — and a cursor in state/cursors.

Cursor runs on updated_at, not created_at: Granola keeps editing a note after
it is created (note.edited always carries changed_fields ["summary"]), so a
created_at cursor would freeze the first version forever.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from h2t_ops.core import lake as _lake
from h2t_ops.core import paths
from h2t_ops.core.errors import UsageError

from .commands import _fmt_note_md, _fmt_transcript_md, _now_iso

VALID_INCLUDE = {"summaries", "transcripts"}


def _synced_versions(manifest: Path) -> dict[str, set[str]]:
    """(note_id, updated_at) key -> include parts already written for that version.

    Read from the committed rows of the manifest: they carry the 3.x row fields as meta.
    Records predating include-tracking carry no "include" field. Treat them as
    complete: an existing lake must not trigger a surprise full refetch.
    """
    seen: dict[str, set[str]] = {}
    for rec in _lake.ConnectorDir("granola", root=manifest.parent).committed_rows():
        if rec.get("note_id"):
            key = f"{rec['note_id']}@{rec.get('updated_at') or ''}"
            parts = rec.get("include")
            covered = set(parts) if isinstance(parts, list) else set(VALID_INCLUDE)
            seen.setdefault(key, set()).update(_covered(covered, rec.get("refused") or ()))
    return seen


def _covered(parts: Iterable[str], refused: Iterable[str]) -> set[str]:
    """A part with a refused (foreign) file is not synced: the next run tries it again."""
    refused = list(refused)
    return {p for p in parts if not any(r.startswith(f"{p}/") for r in refused)}


def _pair(part: str, note_id: str, md: str, raw: Any) -> dict[str, bytes]:
    return {f"{part}/{note_id}.md": md.encode("utf-8"),
            f"{part}/{note_id}.json": json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8")}


def sync_notes(
    client: Any,
    *,
    to: Path | None = None,
    include: Iterable[str],
    cursor_file: Path | None = None,
    since: str | None = None,
    since_cursor: bool = False,
    folder: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Pull notes into a lake directory (default <lake>/granola). Returns run counters."""
    include = set(include)
    unknown = include - VALID_INCLUDE
    if unknown:
        raise UsageError(
            f"unknown --include values: {sorted(unknown)} (valid: {sorted(VALID_INCLUDE)})"
        )

    lake = _lake.ConnectorDir("granola", root=paths.expand_user_dest(str(to)) if to else None)
    lake.recover()
    cursor_path = paths.expand_user_dest(str(cursor_file)) if cursor_file else None
    cursor = _lake.read_cursor("granola", cursor_path)

    updated_after = since
    if since_cursor and not updated_after:
        updated_after = cursor.get("last_seen_ts")

    folder_id = client.resolve_folder_id(folder) if folder else None
    listing = client.list_notes(limit=limit, updated_after=updated_after, folder_id=folder_id)

    seen = _synced_versions(lake.manifest)
    synced = skipped = errors = refused = 0
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
        files: dict[str, bytes] = {}
        try:
            note = client.get_note(note_id)
            if "summaries" in missing:
                files.update(_pair("summaries", note_id, _fmt_note_md(note), note))
            if "transcripts" in missing:
                data = client.get_transcript(note_id)
                md = _fmt_transcript_md(note, data["transcript"],
                                        truncated=data.get("truncated", False))
                files.update(_pair("transcripts", note_id, md, data))
        except Exception as exc:  # noqa: BLE001 — one bad note must not kill the run
            errors += 1
            print(f"WARN: skip {note_id}: {exc}")
            continue

        ts = note.get("updated_at") or row.get("updated_at")
        # The committed row carries the 3.x manifest row's fields: _synced_versions reads them.
        meta = {
            "note_id": note_id,
            "title": note.get("title") or row.get("title"),
            "created_at": note.get("created_at") or row.get("created_at"),
            "updated_at": ts,
            "include": sorted(missing),
            "synced_at": _now_iso(),
        }
        rejected = lake.publish(files, op_id=uuid.uuid4().hex, meta=meta)
        if rejected:
            refused += len(rejected)
            print(f"WARN: {note_id}: not replacing files the package did not write: {', '.join(rejected)}")
        seen.setdefault(version, set()).update(_covered(missing, rejected))
        synced += 1
        if ts and (last_seen_ts is None or ts > last_seen_ts):
            last_seen_ts, last_seen_id = ts, note_id

    if refused:
        # A refused note is not synced; --since-cursor must list it again next run.
        last_seen_ts, last_seen_id = cursor.get("last_seen_ts"), cursor.get("last_seen_id")
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
    written = _lake.write_cursor("granola", cursor, cursor_path)

    return {
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "refused": refused,
        "cursor_file": str(written),
        "lake": str(lake.root),
    }
