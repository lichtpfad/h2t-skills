"""Granola CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

PROVIDER = "granola"

_YAML_UNSAFE = (":", "#", "'", '"', ",", "[", "]", "{", "}", "\n", "&", "*", "!", "|", ">", "%", "@", "`")


# ─── Display helpers ──────────────────────────────────────────────────────────

def _yaml_value(v: Any) -> str:
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return ""
    s = str(v)
    if not s:
        return '""'
    if any(c in s for c in _YAML_UNSAFE) or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for k, val in fields.items():
        if val is None or val == "":
            continue
        lines.append(f"{k}: {_yaml_value(val)}")
    lines.append("---")
    return "\n".join(lines)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock(ts: Any) -> str:
    """ISO timestamp -> HH:MM:SS; anything unparseable passes through."""
    if isinstance(ts, str) and "T" in ts:
        return ts[11:19]
    return str(ts or "")


def _people(entries: Any) -> list[str]:
    out: list[str] = []
    for e in entries or []:
        if isinstance(e, dict):
            name = e.get("name") or e.get("email") or ""
        else:
            name = str(e)
        if name:
            out.append(name)
    return out


def _speaker_label(speaker: dict[str, Any]) -> str:
    """Name when Granola resolved one, else the diarization label, else side.

    Calls recorded before Granola's Meet extension often carry no name at all —
    those fall back to Me/Them, which is why _fmt_transcript_md reports coverage.
    """
    name = (speaker.get("name") or "").strip()
    if name:
        return name
    label = (speaker.get("diarization_label") or "").strip()
    if label:
        return label
    return {"me": "Me", "them": "Them"}.get(speaker.get("attribution"), "Speaker")


def _fragment_key(item: dict[str, Any]) -> str:
    return json.dumps(
        [item.get("text"), item.get("start_time"), item.get("end_time"), item.get("speaker")],
        sort_keys=True, ensure_ascii=False,
    )


def _merge_fragments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse consecutive fragments of one speaker into readable blocks.

    Also drops a fragment that exactly repeats the one before it (same text,
    same timestamps, same speaker) — a provider-side duplication seen in real
    transcripts. Identical text at different timestamps is real speech and stays.
    """
    blocks: list[dict[str, Any]] = []
    prev_key: str | None = None
    for item in items or []:
        key = _fragment_key(item)
        if key == prev_key:
            continue
        prev_key = key
        label = _speaker_label(item.get("speaker") or {})
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if blocks and blocks[-1]["label"] == label:
            blocks[-1]["text"] = f"{blocks[-1]['text']} {text}".strip()
            blocks[-1]["end_time"] = item.get("end_time")
        else:
            blocks.append({
                "label": label,
                "text": text,
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            })
    return blocks


def _note_meta(note: dict[str, Any]) -> dict[str, Any]:
    cal = note.get("calendar_event") or {}
    owner = note.get("owner") or {}
    attendees = _people(note.get("attendees")) or _people(cal.get("invitees"))
    created = note.get("created_at") or ""
    return {
        "note_id": note.get("id") or note.get("note_id"),
        "title": note.get("title") or cal.get("event_title") or "",
        "date": created[:10],
        "created_at": created,
        "updated_at": note.get("updated_at"),
        "owner": owner.get("name") or owner.get("email"),
        "attendees": attendees,
        "folders": [f.get("name") for f in (note.get("folder_membership") or []) if f.get("name")],
        "scheduled_start": cal.get("scheduled_start_time"),
        "scheduled_end": cal.get("scheduled_end_time"),
        "web_url": note.get("web_url"),
    }


def _fmt_transcript_md(note: dict[str, Any], items: list[dict[str, Any]],
                       truncated: bool = False, raw: bool = False) -> str:
    meta = _note_meta(note)
    speakers: list[str] = []
    unnamed = 0
    for item in items or []:
        if (item.get("speaker") or {}).get("name"):
            name = item["speaker"]["name"]
            if name not in speakers:
                speakers.append(name)
        else:
            unnamed += 1
    blocks = [{"label": _speaker_label(i.get("speaker") or {}),
               "text": (i.get("text") or "").strip(),
               "start_time": i.get("start_time")} for i in items or []] if raw \
        else _merge_fragments(items)
    fm = _frontmatter({
        **meta,
        "type": "transcript",
        "speakers": speakers,
        "unnamed_fragments": unnamed,
        "transcript_truncated": True if truncated else None,
        "source": "granola-api",
        "fetched_at": _now_iso(),
    })
    title = meta["title"] or meta["note_id"] or "Note"
    lines = [fm, "", f"# {title}", "", "## Transcript", ""]
    for b in blocks:
        lines.append(f"**{b['label']}** [{_clock(b['start_time'])}] — {b['text']}")
    return "\n".join(lines) + "\n"


def _fmt_summary_md(note: dict[str, Any]) -> str:
    """Provider markdown, verbatim — no frontmatter, ready to paste elsewhere."""
    return note.get("summary_markdown") or note.get("summary_text") or ""


def _fmt_note_md(note: dict[str, Any]) -> str:
    meta = _note_meta(note)
    fm = _frontmatter({**meta, "type": "note", "source": "granola-api", "fetched_at": _now_iso()})
    body = _fmt_summary_md(note) or "_This note has no summary yet._"
    title = meta["title"] or meta["note_id"] or "Note"
    return "\n".join([fm, "", f"# {title}", "", body]) + "\n"


def _fmt_notes_md(rows: list[dict[str, Any]]) -> str:
    lines = ["| date | note_id | title |", "| --- | --- | --- |"]
    for n in rows or []:
        title = (n.get("title") or "").replace("|", "\\|")
        lines.append(f"| {(n.get('created_at') or '')[:10]} | {n.get('id')} | {title} |")
    return "\n".join(lines) + "\n"


def _fmt_folders_md(rows: list[dict[str, Any]]) -> str:
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for f in rows or []:
        by_parent.setdefault(f.get("parent_folder_id"), []).append(f)
    lines: list[str] = []

    def walk(parent: str | None, depth: int) -> None:
        for f in sorted(by_parent.get(parent, []), key=lambda x: (x.get("name") or "").casefold()):
            lines.append(f"{'  ' * depth}- {f.get('name')} ({f.get('id')})")
            walk(f.get("id"), depth + 1)

    walk(None, 0)
    return "\n".join(lines) + "\n"


# ─── Registration ─────────────────────────────────────────────────────────────

def register(subparsers: Any) -> None:
    p = subparsers.add_parser("granola", help="Work with Granola notes, summaries, and transcripts")
    cmds = p.add_subparsers(dest="granola_cmd", required=True)

    lp = cmds.add_parser("list", help="List notes")
    lp.add_argument("--limit", type=int, default=None)
    lp.add_argument("--cursor", default=None)
    lp.add_argument("--since", "--created-after", dest="since", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--until", "--created-before", dest="until", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--updated-after", dest="updated_after", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--folder", default=None, metavar="NAME|fol_ID")
    lp.add_argument("--json", dest="as_json", action="store_true")
    lp.add_argument("--format", dest="fmt", choices=["human", "md"], default="human")

    tp = cmds.add_parser("transcript", help="Get the verbatim transcript of a note")
    tp.add_argument("note_id")
    tp.add_argument("--raw", action="store_true",
                    help="keep provider fragments unmerged (no speaker grouping)")
    tp.add_argument("--json", dest="as_json", action="store_true")
    tp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md")

    ac = cmds.add_parser("auth-check", help="Validate GRANOLA_API_KEY")
    ac.add_argument("--json", dest="as_json", action="store_true")

    for verb, helptext in (("get", "Get one note with its summary"),
                           ("summary", "Get the note summary as provider markdown")):
        vp = cmds.add_parser(verb, help=helptext)
        vp.add_argument("note_id")
        vp.add_argument("--json", dest="as_json", action="store_true")
        vp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md")

    fp = cmds.add_parser("folders", help="List folders as a tree")
    fp.add_argument("--json", dest="as_json", action="store_true")
    fp.add_argument("--format", dest="fmt", choices=["human", "md"], default="human")

    wp = cmds.add_parser("webhooks", help="List registered webhook endpoints (read-only)")
    wp.add_argument("--json", dest="as_json", action="store_true")
    wp.add_argument("--format", dest="fmt", choices=["human", "md"], default="human")

    sp = cmds.add_parser("sync", help="Pull notes into a directory as markdown + raw JSON")
    sp.add_argument("--to", required=True, metavar="DIR")
    sp.add_argument("--include", default="summaries,transcripts",
                    metavar="summaries,transcripts")
    sp.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                    help="only notes updated after this date")
    sp.add_argument("--since-cursor", dest="since_cursor", action="store_true",
                    help="resume from the stored updated_at cursor")
    sp.add_argument("--folder", default=None, metavar="NAME|fol_ID")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--cursor-file", dest="cursor_file", default=None, metavar="PATH")
    sp.add_argument("--json", dest="as_json", action="store_true")

    p.set_defaults(_handler=run)


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def run(args: Any) -> Any:
    """Dispatch a granola subcommand. Returns result or raises core.errors."""
    from h2t_ops.connectors.granola import client as _client_mod  # lazy
    from h2t_ops.core.errors import NotFoundError, UsageError

    client = _client_mod.GranolaClient()
    cmd = args.granola_cmd

    if cmd == "auth-check":
        return client.auth_check()

    if cmd == "list":
        folder_id = client.resolve_folder_id(args.folder) if getattr(args, "folder", None) else None
        data = client.list_notes(
            limit=args.limit,
            cursor=args.cursor,
            created_after=args.since,
            created_before=args.until,
            updated_after=args.updated_after,
            folder_id=folder_id,
        )
        if getattr(args, "fmt", "human") == "md":
            return _fmt_notes_md(data["rows"])
        return data

    if cmd == "transcript":
        data = client.get_transcript(args.note_id)
        if args.fmt == "md":
            try:
                note = client.get_note(args.note_id)
            except NotFoundError:
                note = {"id": args.note_id}
            return _fmt_transcript_md(note, data["transcript"],
                                      truncated=data.get("truncated", False),
                                      raw=getattr(args, "raw", False))
        return data

    if cmd == "sync":
        from pathlib import Path as _Path

        from h2t_ops.connectors.granola import sync as _sync

        return _sync.sync_notes(
            client,
            to=_Path(args.to),
            include={p.strip() for p in (args.include or "").split(",") if p.strip()},
            cursor_file=_Path(args.cursor_file) if args.cursor_file else None,
            since=args.since,
            since_cursor=args.since_cursor,
            folder=args.folder,
            limit=args.limit,
        )

    if cmd == "get":
        note = client.get_note(args.note_id)
        return _fmt_note_md(note) if args.fmt == "md" else note

    if cmd == "summary":
        note = client.get_note(args.note_id)
        body = _fmt_summary_md(note)
        if not body:
            raise NotFoundError(
                f"Note {args.note_id} has no summary yet.",
                hint="Granola generates summaries after processing; retry later.",
            )
        return body if args.fmt == "md" else {"note_id": args.note_id, "summary_markdown": body}

    if cmd == "folders":
        rows = client.list_folders()["rows"]
        return _fmt_folders_md(rows) if getattr(args, "fmt", "human") == "md" else {"rows": rows}

    if cmd == "webhooks":
        rows = client.list_webhook_endpoints()["rows"]
        # Defensive: a signing secret is shown once at creation and must never be echoed.
        return {"rows": [{k: v for k, v in r.items() if k != "signing_secret"} for r in rows]}

    raise UsageError(f"unknown granola subcommand: {cmd}")
