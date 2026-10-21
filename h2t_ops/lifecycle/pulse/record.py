"""The session record keyed by the program's own UUID, and the draft that precedes it.

SessionStart writes a draft under state/ (a record in `records` syncs between machines and
cannot be removed, so a session that never gets a user message must not become one).
SessionEnd promotes the draft with `upsert`. A record is never moved or removed: when the
project changes, the file stays and its frontmatter `project` changes; the index reads the
project from the frontmatter.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.gather.project import identify_project
from h2t_ops.lifecycle.gather.sessions import get_machine_name

_GIT_TIMEOUT = 5


def _git(cwd: str, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=_GIT_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def git_facts(cwd: str) -> dict:
    """{"branch", "repo", "worktree"}; every value "" outside git or when git fails."""
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    top = _git(cwd, "rev-parse", "--show-toplevel")
    return {
        "branch": _git(cwd, "branch", "--show-current"),
        "repo": str(Path(common).parent) if common else "",
        "worktree": str(Path(top)) if top else "",
    }


def project_of(cwd: str) -> tuple[str, str]:
    """(project id, domain); ("unregistered", "") when the cwd maps to no project."""
    found = identify_project(cwd)
    project = found.get("id") or ""
    if not project or project == "unknown":
        return "unregistered", ""
    return project, found.get("domain") or ""


def find(session_id: str, machine: str) -> Path | None:
    hits = sorted(paths.records("sessions", machine).glob(f"*/{session_id}.md"))
    return hits[0] if hits else None


def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _merge(old: dict, new: dict, keep_earliest: tuple[str, ...]) -> dict:
    merged = dict(old)
    for key, value in new.items():
        if _empty(value):
            continue
        if key in keep_earliest and not _empty(merged.get(key)):
            merged[key] = min(str(merged[key]), str(value))
        else:
            merged[key] = value
    return merged


def _lock(session_id: str) -> Path:
    return paths.state_dir() / "locks" / f"session-{session_id}.lock"


def draft_path(session_id: str) -> Path:
    return paths.state_dir() / "pulse" / "open" / f"{session_id}.json"


def read_draft(session_id: str) -> dict:
    try:
        data = json.loads(draft_path(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store_draft(session_id: str, fields: dict, keep_earliest: tuple[str, ...]) -> Path:
    path = draft_path(session_id)
    data = json.dumps(_merge(read_draft(session_id), fields, keep_earliest),
                      ensure_ascii=False, sort_keys=True).encode("utf-8")
    if path.exists():
        return store.replace(path, data, place="state")
    return store.create(path, data, place="state")


def _remove_draft(session_id: str) -> None:
    store.remove(draft_path(session_id), place="state")


def write_draft(session_id: str, fields: dict, *, keep_earliest=("started_at",)) -> Path:
    with store.locked(_lock(session_id), place="state"):
        return _store_draft(session_id, fields, keep_earliest)


def drop_draft(session_id: str) -> None:
    with store.locked(_lock(session_id), place="state"):
        _remove_draft(session_id)


def upsert(session_id: str, fields: dict, *, body: bytes | None = None,
           keep_earliest=("started_at",)) -> Path:
    """Create or merge the record of this session; a draft is the base of a new record."""
    machine = get_machine_name()
    now = datetime.now(UTC)
    stamps = {"date": now.strftime("%Y-%m-%d"), "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    with store.locked(_lock(session_id), place="state"):
        existing = find(session_id, machine)
        if existing is not None:
            meta, old_body = session_record.parse(existing.read_bytes())
            merged = _merge(meta, {**fields, **stamps}, keep_earliest)
            data = session_record.render(merged, old_body if body is None else body)
            written = store.replace(existing, data, place="records.sessions")
        else:
            merged = _merge(read_draft(session_id), {**fields, **stamps}, keep_earliest)
            merged.update(session_id=session_id, machine=machine)
            if not merged.get("project"):
                raise ValueError(f"session {session_id}: no project to file the record under")
            data = session_record.render(merged, body or b"")
            target = session_record.session_path(machine, merged["project"], session_id)
            written = store.create(target, data, place="records.sessions")
        _remove_draft(session_id)
    return written


def _norm(cwd: str) -> str:
    return str(cwd).replace("\\", "/").rstrip("/").lower()


def find_open(tool: str, cwd: str) -> str | None:
    """The one session of this machine with this tool and cwd and no ended_at, in a draft or
    a record; None when there are none or several. A draft and a record of one id count once."""
    machine = get_machine_name()
    wanted = _norm(cwd)
    open_ids: set[str] = set()
    known: set[str] = set()
    for path in paths.records("sessions", machine).glob("*/*.md"):
        try:
            meta, _ = session_record.parse(path.read_bytes())
        except (OSError, ValueError):
            continue
        sid = str(meta.get("session_id") or path.stem)
        known.add(sid)
        if meta.get("tool") == tool and _norm(meta.get("cwd") or "") == wanted \
                and not meta.get("ended_at"):
            open_ids.add(sid)
    for path in (paths.state_dir() / "pulse" / "open").glob("*.json"):
        if path.stem in known:
            continue
        draft = read_draft(path.stem)
        if draft.get("tool") == tool and _norm(draft.get("cwd") or "") == wanted \
                and not draft.get("ended_at"):
            open_ids.add(path.stem)
    return next(iter(open_ids)) if len(open_ids) == 1 else None
