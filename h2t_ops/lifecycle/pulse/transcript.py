"""Read Claude Code and Codex transcripts (.jsonl) without changing them.

Parsing ported from session_catalog.py (lichtpfad/h2t-infra, commit 104fb24).
Broken lines (truncated writes, bad bytes) are skipped, never raised.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

LIVE_ORIGINATORS = ("codex-tui", "Codex Desktop")
MACHINE_ORIGINATORS = ("codex_exec", "Claude Code", "codex_sdk_ts")
HEADLESS_ENTRYPOINTS = ("sdk-cli",)


@dataclass(frozen=True)
class Info:
    tool: str
    session_id: str
    cwd: str
    origin: str  # "live" | "machine" | "unknown"
    start: str
    end: str
    user_msgs: int
    path: str


def iter_json(path: Path) -> Iterator[dict]:
    """Stream one JSON object per line; skip lines that do not parse or are not objects."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                yield rec


def is_user_voice(t: str) -> bool:
    """Harness wrappers and continuation summaries are not the user's voice."""
    if not t.strip() or t.startswith("<"):
        return False
    if t.startswith("This session is being continued") or "┌──" in t:
        return False
    return True


def claude_text(msg) -> str:
    if not isinstance(msg, dict):
        return ""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _codex_text(payload: dict, block_type: str) -> str:
    return "\n".join(
        b.get("text", "")
        for b in payload.get("content") or []
        if isinstance(b, dict) and b.get("type") == block_type
    )


def _codex_message(rec: dict, role: str) -> dict | None:
    p = rec.get("payload")
    if (
        rec.get("type") == "response_item"
        and isinstance(p, dict)
        and p.get("type") == "message"
        and p.get("role") == role
    ):
        return p
    return None


def _claude_origin(rec: dict) -> str:
    """Origin decided by this record alone, or "" when the record does not decide."""
    if rec.get("isSidechain") is True:
        return "machine"
    entrypoint = rec.get("entrypoint")
    if not entrypoint:
        return ""
    return "machine" if entrypoint in HEADLESS_ENTRYPOINTS else "live"


def _codex_origin(originator: str) -> str:
    if originator in LIVE_ORIGINATORS:
        return "live"
    if originator in MACHINE_ORIGINATORS:
        return "machine"
    return "unknown"


def origin_of(tool: str, path: Path) -> str:
    """Read only until the first line that decides the origin."""
    for rec in iter_json(path):
        if tool == "codex":
            if rec.get("type") == "session_meta":
                p = rec.get("payload")
                return _codex_origin(p.get("originator", "") if isinstance(p, dict) else "")
        else:
            decided = _claude_origin(rec)
            if decided:
                return decided
    return "unknown"


def read(tool: str, path: Path) -> Info | None:
    """Summarise one transcript; None when the file carries no timestamps."""
    stamps: list[str] = []
    sid, cwd, n = path.stem, "", 0
    origin = ""
    for rec in iter_json(path):
        if rec.get("timestamp"):
            stamps.append(rec["timestamp"])
        if tool == "codex":
            if rec.get("type") == "session_meta":
                p = rec.get("payload") or {}
                sid = p.get("session_id") or p.get("id") or sid
                cwd = p.get("cwd", "")
                origin = _codex_origin(p.get("originator", ""))
                continue
            msg = _codex_message(rec, "user")
            if msg is not None and is_user_voice(_codex_text(msg, "input_text")):
                n += 1
        else:
            cwd = cwd or rec.get("cwd", "")
            if not origin:  # first deciding record wins, as in origin_of
                origin = _claude_origin(rec)
            if rec.get("type") == "user" and is_user_voice(claude_text(rec.get("message"))):
                n += 1
    if not stamps:
        return None
    return Info(tool, sid, cwd, origin or "unknown", stamps[0], stamps[-1], n, str(path))


def user_messages(tool: str, path: Path) -> list[str]:
    """User-voice texts in file order."""
    out: list[str] = []
    for rec in iter_json(path):
        if tool == "codex":
            msg = _codex_message(rec, "user")
            t = _codex_text(msg, "input_text") if msg is not None else ""
        elif rec.get("type") == "user":
            t = claude_text(rec.get("message"))
        else:
            continue
        if is_user_voice(t):
            out.append(t)
    return out


def last_assistant_text(tool: str, path: Path) -> str:
    """Text of the last assistant message that has any; "" when none."""
    last = ""
    for rec in iter_json(path):
        if tool == "codex":
            msg = _codex_message(rec, "assistant")
            t = _codex_text(msg, "output_text") if msg is not None else ""
        elif rec.get("type") == "assistant":
            t = claude_text(rec.get("message"))
        else:
            continue
        if t.strip():
            last = t
    return last


def is_subagent(path: Path) -> bool:
    return path.name.startswith("agent-") or "subagents" in path.parent.parts
