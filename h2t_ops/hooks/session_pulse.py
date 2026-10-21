"""session-pulse (SessionStart, SessionEnd): record every live session by its program UUID.

SessionStart writes a draft under state/; SessionEnd promotes it to a record in `records`
when the session had a user message. Machine sessions (headless Claude, `codex exec`) and
subagents write nothing. The hook never fails a session: any error goes to stderr.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.hooks.emit import Reply
from h2t_ops.lifecycle.gather.sessions import get_machine_name
from h2t_ops.lifecycle.pulse import record, transcript


def _tool_of(transcript_path: str) -> str:
    return "codex" if "/.codex/" in transcript_path or "\\.codex\\" in transcript_path else "claude"


def _origin(tool: str, path: Path) -> str:
    entrypoint = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if tool == "claude" and entrypoint:
        return "machine" if entrypoint in transcript.HEADLESS_ENTRYPOINTS else "live"
    return transcript.origin_of(tool, path) if path.is_file() else "unknown"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(event: dict) -> None:
    session_id = event.get("session_id") or ""
    raw_path = event.get("transcript_path") or ""
    if os.environ.get("H2T_PULSE_SKIP") or not session_id:
        return
    path = Path(raw_path) if raw_path else Path()
    if raw_path and transcript.is_subagent(path):
        return
    tool = _tool_of(raw_path)
    origin = _origin(tool, path) if raw_path else "unknown"
    if origin == "machine":
        return
    cwd = event.get("cwd") or ""
    project, domain = record.project_of(cwd) if cwd else ("unregistered", "")
    fields = {"tool": tool, "origin": origin, "cwd": cwd, "transcript": raw_path,
              **(record.git_facts(cwd) if cwd else {}), "project": project, "domain": domain}
    if event.get("hook_event_name") == "SessionEnd":
        info = transcript.read(tool, path) if raw_path and path.is_file() else None
        fields.update(ended_at=_now(), user_msgs=info.user_msgs if info else 0)
        existing = record.find(session_id, get_machine_name())
        if existing is not None and project == "unregistered":
            del fields["project"], fields["domain"]   # never turn a known project back into none
        if fields["user_msgs"] or existing is not None:
            record.upsert(session_id, fields)
        else:
            record.drop_draft(session_id)
    else:
        record.write_draft(session_id, {**fields, "started_at": _now()})


def handle(event: dict) -> Reply:
    try:
        _run(event)
    except Exception as exc:  # a record is never worth a failed session
        print(f"session-pulse: {type(exc).__name__}: {exc}", file=sys.stderr)
    return Reply()
