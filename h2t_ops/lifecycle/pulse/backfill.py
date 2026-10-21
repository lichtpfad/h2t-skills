"""Write records for sessions the hook missed, from the Claude and Codex transcripts.

A session that already has a record changes only in `ended_at` and `origin`; a run where
nothing changes writes nothing. Machine sessions, subagents and sessions without a user
message get no record.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.gather.sessions import get_machine_name
from h2t_ops.lifecycle.pulse import record, transcript


def _files(root: Path, pattern: str, since_ns: int) -> Iterator[Path]:
    for path in sorted(root.glob(pattern)):
        if transcript.is_subagent(path):
            continue
        try:
            if path.stat().st_mtime_ns >= since_ns:
                yield path
        except OSError:
            continue


def _update_existing(existing: Path, info: transcript.Info) -> bool:
    """Change `ended_at` / `origin` of a recorded session; True when something was written."""
    meta, _ = session_record.parse(existing.read_bytes())
    fields: dict = {}
    if info.end and info.end > str(meta.get("ended_at") or ""):
        fields["ended_at"] = info.end
    if meta.get("origin") in (None, "", "unknown") and info.origin != "unknown":
        fields["origin"] = info.origin
    if not fields:
        return False
    record.upsert(info.session_id, fields)
    return True


def _new_fields(info: transcript.Info) -> dict:
    project, domain = record.project_of(info.cwd)
    fields = {
        "tool": info.tool, "origin": info.origin, "cwd": info.cwd, "transcript": info.path,
        "started_at": info.start, "ended_at": info.end, "project": project, "domain": domain,
    }
    if info.cwd and Path(info.cwd).is_dir():
        fields.update(record.git_facts(info.cwd))
    return fields


def run(claude_root: Path | None = None, codex_root: Path | None = None, since_ns: int = 0) -> dict:
    claude_root = claude_root if claude_root is not None else paths.home() / ".claude" / "projects"
    codex_root = codex_root if codex_root is not None else paths.home() / ".codex" / "sessions"
    machine = get_machine_name()
    counts = {"seen": 0, "written": 0, "skipped_machine": 0, "skipped_empty": 0, "unknown": 0,
              "errors": 0}
    sources = (("claude", _files(claude_root, "*/*.jsonl", since_ns)),
               ("codex", _files(codex_root, "**/*.jsonl", since_ns)))
    for tool, files in sources:
        for path in files:
            try:
                _one(tool, path, machine, counts)
            except OSError:   # deleted or unreadable since it was listed
                counts["errors"] += 1
    return counts


def _one(tool: str, path: Path, machine: str, counts: dict) -> None:
    info = transcript.read(tool, path)
    if info is None:
        return
    counts["seen"] += 1
    if info.origin == "machine":
        counts["skipped_machine"] += 1
        return
    if info.user_msgs == 0:
        counts["skipped_empty"] += 1
        return
    if info.origin == "unknown":
        counts["unknown"] += 1
    existing = record.find(info.session_id, machine)
    if existing is not None:
        counts["written"] += _update_existing(existing, info)
        return
    record.upsert(info.session_id, _new_fields(info))
    counts["written"] += 1
