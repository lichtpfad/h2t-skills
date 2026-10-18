"""A session record: markdown whose YAML frontmatter describes the session (#548 §5).

The file describes itself — machine, project and session id travel with it — so the index
(Task 14) and the migration can read a record without knowing the path it came from.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from h2t_ops.core import paths

FIELDS = ("session_id", "machine", "project", "domain", "date", "updated_at", "branch",
          "commits", "done", "remains", "artifacts", "migrated_from")

_OPEN = b"---\n"
_CLOSE = b"\n---\n"


def render(meta: dict, body: bytes) -> bytes:
    """Known fields in FIELDS order, then anything else; the body is kept byte for byte."""
    ordered = {k: meta[k] for k in FIELDS if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    header = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True).encode("utf-8")
    return _OPEN + header + b"---\n" + body


def parse(raw: bytes) -> tuple[dict, bytes]:
    """(meta, body). ValueError when there is no frontmatter or it does not parse as a mapping."""
    if not raw.startswith(_OPEN):
        raise ValueError("no frontmatter")
    end = raw.find(_CLOSE, len(_OPEN) - 1)
    if end < 0:
        raise ValueError("frontmatter is not closed")
    try:
        meta = yaml.safe_load(raw[len(_OPEN):end + 1].decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValueError(f"frontmatter does not parse: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("frontmatter is not a mapping")
    return meta, raw[end + len(_CLOSE):]


def session_path(machine: str, project: str, session_id: str) -> Path:
    return paths.records("sessions", machine) / project / f"{session_id}.md"
