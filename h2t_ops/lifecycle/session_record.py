"""A session record: markdown whose YAML frontmatter describes the session (#548 §5).

The file describes itself — machine, project and session id travel with it — so the index
(Task 14) and the migration can read a record without knowing the path it came from.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from h2t_ops.core import paths

FIELDS = ("session_id", "name", "tool", "origin", "cwd", "repo", "worktree", "started_at",
          "ended_at", "user_msgs", "transcript", "candidates", "machine", "project", "domain", "date",
          "updated_at", "branch", "commits", "done", "remains", "artifacts", "summary",
          "summary_source", "summary_stamp", "migrated_from")

_OPEN = b"---\n"
# What parse accepts: a UTF-8 BOM before the opener, and CRLF fence lines — a Windows editor
# or Git's autocrlf turns a record into that, and it is still the same record.
_BOM = b"\xef\xbb\xbf"
_OPEN_RE = re.compile(rb"---\r?\n")
_CLOSE_RE = re.compile(rb"\r?\n---\r?\n")


def render(meta: dict, body: bytes) -> bytes:
    """Known fields in FIELDS order, then anything else; the body is kept byte for byte."""
    ordered = {k: meta[k] for k in FIELDS if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    header = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True).encode("utf-8")
    return _OPEN + header + b"---\n" + body


def parse(raw: bytes) -> tuple[dict, bytes]:
    """(meta, body). ValueError when there is no frontmatter or it does not parse as a mapping.
    LF or CRLF fences and a leading BOM; the body is the bytes after the closing fence."""
    opened = _OPEN_RE.match(raw, len(_BOM) if raw.startswith(_BOM) else 0)
    if opened is None:
        raise ValueError("no frontmatter")
    closed = _CLOSE_RE.search(raw, opened.end() - 1)   # from the opener's \n: an empty header
    if closed is None:
        raise ValueError("frontmatter is not closed")
    try:
        meta = yaml.safe_load(raw[opened.end():closed.start()].decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValueError(f"frontmatter does not parse: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, raw[closed.end():]


def session_path(machine: str, project: str, session_id: str) -> Path:
    return paths.records("sessions", machine) / project / f"{session_id}.md"
