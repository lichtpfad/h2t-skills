"""MeetGeek CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

PROVIDER = "meetgeek"

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
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        ts = s.get("timestamp") or s.get("start_time") or ""
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
    lp.add_argument("--from-date", dest="from_date", default=None, metavar="YYYY-MM-DD")
    lp.add_argument("--to-date", dest="to_date", default=None, metavar="YYYY-MM-DD")
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

    p.set_defaults(_handler=run)


# ─── Dispatch ──────────────────────────────────────────────────────────────────

def run(args: Any) -> Any:
    """Dispatch a meetgeek subcommand. Returns result or raises core.errors."""
    from h2t_ops.connectors.meetgeek.client import MeetGeekClient  # lazy
    from h2t_ops.core.errors import UsageError

    client = MeetGeekClient()
    cmd = args.meetgeek_cmd

    if cmd == "auth-check":
        return client.auth_check()

    if cmd == "teams":
        return client.get_teams()

    if cmd == "list":
        return client.list_meetings(
            limit=args.limit,
            cursor=args.cursor,
            from_date=args.from_date,
            to_date=args.to_date,
        )

    if cmd == "get":
        return client.get_meeting(args.meeting_id)

    if cmd == "transcript":
        transcript = client.get_transcript(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_transcript_md(meeting, transcript)
        return transcript

    if cmd == "summary":
        summary = client.get_summary(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_summary_md(meeting, summary)
        return summary

    if cmd == "highlights":
        highlights = client.get_highlights(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
            return _fmt_highlights_md(meeting, highlights)
        return highlights

    if cmd == "insights":
        insights = client.get_insights(args.meeting_id)
        if args.fmt == "md":
            meeting = client.get_meeting(args.meeting_id)
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

    raise UsageError(f"unknown meetgeek subcommand: {cmd}")
