"""MeetGeek CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

PROVIDER = "meetgeek"

# Handled by pipeline.py; pipeline.VERBS must hold exactly these.
PIPELINE_VERBS = frozenset({
    "download", "convert", "drive-upload", "drive-audit", "staging-purge",
    "upload", "sync", "webhook-server",
})

# ─── Display helpers ──────────────────────────────────────────────────────────

_YAML_UNSAFE = (":", "#", "'", '"', ",", "[", "]", "{", "}", "\n", "&", "*", "!", "|", ">", "%", "@", "`")


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


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for k, val in fields.items():
        if val is None or val == "":
            continue
        lines.append(f"{k}: {_yaml_value(val)}")
    lines.append("---")
    return "\n".join(lines)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_meeting(m: dict) -> dict:
    """Normalize API field aliases for display/frontmatter.

    Supports id|meeting_id and timestamp_start_utc|start_time per spec
    and the e29804a date-field regression guard.
    """
    attendees = m.get("attendees") or m.get("participants") or []
    names = []
    for a in attendees:
        if isinstance(a, dict):
            names.append(a.get("name") or a.get("email") or "")
        elif isinstance(a, str):
            names.append(a)
    start_ts = (
        m.get("timestamp_start_utc")
        or m.get("start_time")
        or m.get("created_at")
    )
    end_ts = m.get("timestamp_end_utc") or m.get("end_time")
    meeting_id = m.get("id") or m.get("meeting_id")
    return {
        "meeting_id": meeting_id,
        "title": m.get("title") or m.get("name") or "",
        "attendees": [n for n in names if n],
        "date": (start_ts or "")[:10],
        "timestamp_start_utc": start_ts,
        "timestamp_end_utc": end_ts,
        "duration_seconds": m.get("duration") or m.get("duration_seconds"),
        "language": m.get("language") or m.get("language_code"),
        # meetgeek_cli.py wrote this into every frontmatter and lake manifest line (#541).
        "provider_url": f"https://app2.meetgeek.ai/meeting/{meeting_id}" if meeting_id else None,
    }


def _fmt_transcript_md(meeting: dict, transcript: dict) -> str:
    meta = _normalize_meeting(meeting)
    speakers = []
    for s in transcript.get("sentences") or []:
        sp = (s.get("speaker") or s.get("speaker_name") or "").strip()
        if sp and sp not in speakers:
            speakers.append(sp)
    if not meta["attendees"]:
        meta = {**meta, "attendees": speakers}
    fm = _frontmatter({**meta, "source": "meetgeek-api", "fetched_at": _now_iso(), "api_version": "v1"})
    title = meta["title"] or meta["meeting_id"] or "Meeting"
    lines = [fm, "", f"# {title}", "", "## Transcript", ""]
    for s in transcript.get("sentences") or []:
        speaker = s.get("speaker") or s.get("speaker_name") or "Speaker"
        ts = s.get("timestamp")
        if ts is None:
            ts = s.get("start_time") or ""
        text = s.get("transcript") or s.get("text") or ""
        if isinstance(ts, (int, float)):
            mins, secs = divmod(int(ts), 60)
            hrs, mins = divmod(mins, 60)
            ts = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        elif isinstance(ts, str) and "T" in ts:
            ts = ts[11:19]
        lines.append(f"**{speaker}** [{ts}] — {text}")
    return "\n".join(lines) + "\n"


def _fmt_summary_md(meeting: dict, summary: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "summary", "source": "meetgeek-api", "fetched_at": _now_iso()})
    body = summary.get("summary") or summary.get("text") or ""
    parts = [fm, "", f"# Summary — {meta['title'] or meta['meeting_id']}", "", body, ""]
    actions = summary.get("action_items") or []
    if actions:
        parts.append("## Action Items\n")
        for a in actions:
            owner = a.get("owner") or a.get("assignee") or "—"
            text = a.get("text") or a.get("description") or ""
            parts.append(f"- [ ] **{owner}**: {text}")
    return "\n".join(parts) + "\n"


def _fmt_highlights_md(meeting: dict, highlights: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "highlights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    items = highlights.get("highlights") or highlights.get("items") or []
    parts = [fm, "", f"# Highlights — {meta['title'] or meta['meeting_id']}", ""]
    for h in items:
        text = h.get("text") or h.get("description") or ""
        ts = h.get("timestamp") or ""
        parts.append(f"- [{ts}] {text}" if ts else f"- {text}")
    return "\n".join(parts) + "\n"


def _fmt_insights_md(meeting: dict, insights: dict) -> str:
    meta = _normalize_meeting(meeting)
    fm = _frontmatter({**meta, "type": "insights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    return fm + "\n\n# Insights\n\n```json\n" + json.dumps(insights, ensure_ascii=False, indent=2) + "\n```\n"


# ─── Registration ──────────────────────────────────────────────────────────────

def register(subparsers: Any) -> None:
    p = subparsers.add_parser("meetgeek", help="Work with MeetGeek meetings, transcripts, and summaries")
    cmds = p.add_subparsers(dest="meetgeek_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human")

    # auth-check
    ac = cmds.add_parser("auth-check", help="Validate MEETGEEK_API_KEY")
    ac.add_argument("--json", dest="as_json", action="store_true")

    # teams
    tp = cmds.add_parser("teams", help="List user teams")
    add_fmt(tp)

    # list
    lp = cmds.add_parser("list", help="List meetings")
    lp.add_argument("--limit", type=int, default=None)
    lp.add_argument("--cursor", default=None)
    lp.add_argument("--from-date", "--from", dest="from_date", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--to-date", "--to", dest="to_date", default=None, metavar="YYYY-MM-DD")
    add_fmt(lp)

    # get
    gp = cmds.add_parser("get", help="Get one meeting by ID")
    gp.add_argument("meeting_id")
    add_fmt(gp)

    # transcript / summary / highlights / insights
    for verb in ("transcript", "summary", "highlights", "insights"):
        vp = cmds.add_parser(verb, help=f"Get {verb} for a meeting")
        vp.add_argument("meeting_id")
        vp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md")
        vp.add_argument("-o", "--output", default=None, metavar="PATH",
                        help="write the payload to PATH and print the path")
        vp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")

    # download-url
    dp = cmds.add_parser("download-url", help="Get signed recording URL for a meeting")
    dp.add_argument("meeting_id")
    add_fmt(dp)

    # submit-url (provider-write verb)
    su = cmds.add_parser("submit-url", help="Submit a public URL to MeetGeek for transcription (POST /v1/upload)")
    su.add_argument("download_url", help="Publicly accessible URL of the recording")
    su.add_argument("--title", default=None)
    su.add_argument("--language-code", dest="language_code", default=None, metavar="CODE")
    su.add_argument("--template", dest="template_name", default=None)
    su.add_argument("--json", dest="as_json", action="store_true")

    # action-items
    aip = cmds.add_parser("action-items", help="Get action items from a meeting summary")
    aip.add_argument("meeting_id")
    add_fmt(aip)

    _register_pipeline(cmds)

    p.set_defaults(_handler=run)


def _register_pipeline(cmds: Any) -> None:
    """Verbs ported from meetgeek_cli.py with its flags (#541); handlers in pipeline.py."""
    import argparse

    # recovery.HOUSEKEEPING_MIN_AGE_HOURS; repeated here so the parser imports nothing.
    housekeeping_hours = 24.0

    def add_json(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")

    s = cmds.add_parser("download", help="Get recording download URL, or the file with -o")
    s.add_argument("meeting_id")
    s.add_argument("-o", "--output", default=None,
                   help="If omitted, prints URL; otherwise downloads to PATH")
    add_json(s)

    s = cmds.add_parser("convert", help="Convert media file (webm→mp4 default)")
    s.add_argument("input")
    s.add_argument("-o", "--output", default=None,
                   help="Output path; default: <lake>/meetgeek/uploads-staging/{YYYY-MM-DD}/{name}.mp4")
    s.add_argument("--audio-only", action="store_true", help="Strip video; output .m4a")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix",
                   help="Multi-track audio strategy (default: amix — sums all tracks)")
    s.add_argument("--probe", action="store_true", help="Print probe info as JSON and exit")
    add_json(s)

    s = cmds.add_parser("drive-upload", help="Upload a file to Drive (idempotent by name)")
    s.add_argument("file")
    s.add_argument("--folder", default=None,
                   help="Path like 'MeetGeek Uploads/2026-05-06'; default: MeetGeek Uploads/{today UTC}")
    s.add_argument("--make-public", action=argparse.BooleanOptionalAction, default=True,
                   help="Set permissions to anyone-with-link reader (default on)")
    add_json(s)

    s = cmds.add_parser("drive-audit", help="Report anyone-with-link access on uploaded recordings")
    s.add_argument("--revoke", action="store_true",
                   help="Remove the anyone permission (off by default; only safe once "
                        "MeetGeek has fetched the recording)")
    s.add_argument("--min-age-hours", type=float, default=0.0,
                   help="Leave uploads younger than this alone when revoking (default 0)")
    add_json(s)

    s = cmds.add_parser("staging-purge",
                        help="Delete converted media whose recording is submitted, still "
                             "on Drive, and still has its source")
    s.add_argument("--min-age-hours", type=float, default=housekeeping_hours,
                   help=f"Keep media submitted less than this long ago (default {housekeeping_hours:g})")
    s.add_argument("--dry-run", action="store_true", help="Report what would be deleted; delete nothing")
    s.add_argument("--verify-drive", action=argparse.BooleanOptionalAction, default=True,
                   help="Check the Drive copy still exists before deleting (default on)")
    add_json(s)

    s = cmds.add_parser("upload", help="Submit URL or local file to MeetGeek /v1/upload")
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--download-url", default=None,
                     help="Public URL MeetGeek will fetch (e.g. Drive uc?export=download)")
    grp.add_argument("--from-file", default=None,
                     help="Local file path or glob; orchestrates convert + drive-upload + upload")
    s.add_argument("--title", default=None)
    s.add_argument("--language", default=None, help="Language hint (ru, en, auto, etc.)")
    s.add_argument("--audio-only", action="store_true")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix")
    s.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True,
                   help="Skip files already in manifest with status=submitted (default on)")
    s.add_argument("--dry-run", action="store_true", help="Print plan; do not convert/upload")
    s.add_argument("--housekeeping", action=argparse.BooleanOptionalAction, default=True,
                   help=f"After the batch, revoke public ACLs and purge staged media "
                        f"older than {housekeeping_hours:g}h (default on)")
    add_json(s)

    s = cmds.add_parser("sync", help="Bulk pull to a lake folder (manifest.jsonl + per-asset folders)")
    s.add_argument("--to", required=True, help="Lake destination (e.g. <lake>/meetgeek/historical/)")
    s.add_argument("--include", default="transcripts",
                   help="Comma-separated: transcripts,summaries,highlights,insights,recordings")
    s.add_argument("--since", default=None, help="ISO date YYYY-MM-DD")
    s.add_argument("--since-cursor", action="store_true",
                   help="Resume from last_seen_ts in cursor file")
    s.add_argument("--to-date", dest="to_date", default=None)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--cursor-file", dest="cursor_file", default=None,
                   help="Default: state/cursors/meetgeek.json")
    s.add_argument("--watch", type=int, default=None, metavar="SECONDS",
                   help="Run sync in a loop every N seconds (min 30); Ctrl-C to stop")
    add_json(s)

    s = cmds.add_parser("webhook-server", help="Receive MeetGeek webhook events to disk")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--bind", default="127.0.0.1")
    s.add_argument("--out", default=None,
                   help="Directory to dump received events as JSON (default: <lake>/meetgeek/webhooks)")
    # Default resolved at run time from MEETGEEK_WEBHOOK_SECRET, never into the parser.
    s.add_argument("--secret", default=None,
                   help="Optional shared secret; if set, requests without matching "
                        "X-Webhook-Secret are 401'd (default: MEETGEEK_WEBHOOK_SECRET)")
    add_json(s)


def _write_output(payload: Any, path: str) -> str:
    """meetgeek_cli.py's -o: write the payload, print the path instead of it."""
    from pathlib import Path

    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return path


# ─── Dispatch ──────────────────────────────────────────────────────────────────

def run(args: Any) -> Any:
    """Dispatch a meetgeek subcommand. Returns result or raises core.errors."""
    cmd = args.meetgeek_cmd
    if cmd in PIPELINE_VERBS:
        # lazy: ffmpeg, Drive, manifest
        from h2t_ops.connectors.meetgeek import pipeline

        # Before the client: convert, drive-* and staging-purge never needed an API key.
        return pipeline.VERBS[cmd](args)

    result = _run_api(args, cmd)
    if cmd in ("transcript", "summary", "highlights", "insights") and getattr(args, "output", None):
        return _write_output(result, args.output)
    return result


def _run_api(args: Any, cmd: str) -> Any:
    from h2t_ops.connectors.meetgeek.client import MeetGeekClient  # lazy
    from h2t_ops.core.errors import NotFoundError, UsageError

    client = MeetGeekClient()

    def meeting_for_markdown(meeting_id: str) -> dict:
        try:
            return client.get_meeting(meeting_id)
        except NotFoundError:
            return {"meeting_id": meeting_id}

    if cmd == "auth-check":
        return client.auth_check()

    if cmd == "teams":
        return client.get_teams()

    if cmd == "list":
        from_date = getattr(args, "from_date", None)
        to_date = getattr(args, "to_date", None)
        if bool(from_date) != bool(to_date):
            raise UsageError("meetgeek list: --from and --to must be used together")
        return client.list_meetings(
            limit=args.limit,
            cursor=args.cursor,
            from_date=from_date,
            to_date=to_date,
        )

    if cmd == "get":
        return client.get_meeting(args.meeting_id)

    if cmd == "transcript":
        transcript = client.get_transcript(args.meeting_id)
        if args.fmt == "md":
            meeting = meeting_for_markdown(args.meeting_id)
            return _fmt_transcript_md(meeting, transcript)
        return transcript

    if cmd == "summary":
        summary = client.get_summary(args.meeting_id)
        if args.fmt == "md":
            meeting = meeting_for_markdown(args.meeting_id)
            return _fmt_summary_md(meeting, summary)
        return summary

    if cmd == "highlights":
        highlights = client.get_highlights(args.meeting_id)
        if args.fmt == "md":
            meeting = meeting_for_markdown(args.meeting_id)
            return _fmt_highlights_md(meeting, highlights)
        return highlights

    if cmd == "insights":
        insights = client.get_insights(args.meeting_id)
        if args.fmt == "md":
            meeting = meeting_for_markdown(args.meeting_id)
            return _fmt_insights_md(meeting, insights)
        return insights

    if cmd == "download-url":
        return client.get_download_url(args.meeting_id)

    if cmd == "submit-url":
        return client.submit_url(
            args.download_url,
            title=args.title,
            language_code=args.language_code,
            template_name=args.template_name,
        )

    if cmd == "action-items":
        return client.action_items(args.meeting_id)

    raise UsageError(f"unknown meetgeek subcommand: {cmd}")
