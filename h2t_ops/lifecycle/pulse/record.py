"""The session record keyed by the program's own UUID, and the draft that precedes it.

SessionStart writes a draft under state/ (a record in `records` syncs between machines and
cannot be removed, so a session that never gets a user message must not become one).
SessionEnd promotes the draft with `upsert`. A record is never moved or removed: when the
project changes, the file stays and its frontmatter `project` changes; the index reads the
project from the frontmatter.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.gather.project import identify_project
from h2t_ops.lifecycle.gather.sessions import get_machine_name
from h2t_ops.lifecycle.pulse import transcript

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
    if new.get("project") == "unregistered" and old.get("project") not in (None, "", "unregistered"):
        new = {k: v for k, v in new.items() if k not in ("project", "domain")}   # keep the known project
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


def _upsert_locked(session_id: str, fields: dict, body: bytes | None,
                   keep_earliest: tuple[str, ...]) -> Path:
    machine = get_machine_name()
    now = datetime.now(UTC)
    stamps = {"date": now.strftime("%Y-%m-%d"), "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
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


def upsert(session_id: str, fields: dict, *, body: bytes | None = None,
           keep_earliest=("started_at",)) -> Path:
    """Create or merge the record of this session; a draft is the base of a new record."""
    with store.locked(_lock(session_id), place="state"):
        return _upsert_locked(session_id, fields, body, keep_earliest)


def note_start(session_id: str, fields: dict, *, keep_earliest=("started_at",)) -> Path:
    """SessionStart: merge into the record when this session has one, else into its draft.
    One lock covers the lookup and the write, so a record and a draft never both appear."""
    with store.locked(_lock(session_id), place="state"):
        if find(session_id, get_machine_name()) is not None:
            return _upsert_locked(session_id, fields, None, keep_earliest)
        return _store_draft(session_id, fields, keep_earliest)


def _norm(cwd: str) -> str:
    return str(cwd).replace("\\", "/").rstrip("/").lower()


def open_ids(tool: str, cwd: str) -> list[str]:
    """Ids of this machine's sessions with this tool and cwd and no ended_at, in a draft or a
    record, sorted. A draft and a record of one id count once."""
    machine = get_machine_name()
    wanted = _norm(cwd)
    found: set[str] = set()
    known: set[str] = set()
    for path in paths.records("sessions", machine).glob("*/*.md"):
        try:
            meta, _ = session_record.parse(path.read_bytes())
        except (OSError, ValueError):
            continue
        sid = str(meta.get("session_id") or path.stem)
        known.add(sid)
        if meta.get("tool") == tool and _norm(meta.get("cwd") or "") == wanted                 and not meta.get("ended_at"):
            found.add(sid)
    for path in (paths.state_dir() / "pulse" / "open").glob("*.json"):
        if path.stem in known:
            continue
        draft = read_draft(path.stem)
        if draft.get("tool") == tool and _norm(draft.get("cwd") or "") == wanted                 and not draft.get("ended_at"):
            found.add(path.stem)
    return sorted(found)


def find_open(tool: str, cwd: str) -> str | None:
    """The one open session of this tool and cwd; None when there are none or several."""
    ids = open_ids(tool, cwd)
    return ids[0] if len(ids) == 1 else None


def _read(tool: str, raw_path: str) -> transcript.Info | None:
    """The transcript summarised; None when it is missing, empty or cannot be read."""
    if not raw_path or not Path(raw_path).is_file():
        return None
    try:
        return transcript.read(tool or "claude", Path(raw_path))
    except OSError:
        return None


def _settle_draft(session_id: str) -> bool:
    draft = read_draft(session_id)
    raw = draft.get("transcript") or ""
    if raw and transcript.is_subagent(Path(raw)):
        drop_draft(session_id)          # a subagent never becomes a record
        return True
    info = _read(draft.get("tool") or "", draft.get("transcript") or "")
    if info is None:
        return False
    if info.origin == "machine":
        drop_draft(session_id)          # never becomes a record
        return True
    if info.user_msgs == 0:
        return False
    fields = {"user_msgs": info.user_msgs}
    if info.origin != "unknown":
        fields["origin"] = info.origin
    try:
        upsert(session_id, fields)
    except ValueError:                  # a draft with no project cannot be filed
        return False
    return True


def _settle_record(path: Path) -> bool:
    try:
        meta, _ = session_record.parse(path.read_bytes())
    except (OSError, ValueError):
        return False
    if meta.get("ended_at") and meta.get("origin") not in (None, "", "unknown"):
        return False
    raw = meta.get("transcript") or ""
    if raw and transcript.is_subagent(Path(raw)):
        return False
    info = _read(meta.get("tool") or "", raw)
    if info is None:
        return False
    fields: dict = {}
    if info.origin != "unknown" and info.origin != meta.get("origin"):
        fields["origin"] = info.origin
    if info.user_msgs != meta.get("user_msgs"):
        fields["user_msgs"] = info.user_msgs
    if not fields:
        return False
    upsert(str(meta.get("session_id") or path.stem), fields)
    return True


def settle_open() -> int:
    """Bring this machine's open sessions up to date from their transcripts; count changed.

    A draft whose transcript has a user message becomes a record; a draft of a machine
    session is dropped. A record with no `ended_at`, or with an unknown origin, takes the
    origin and user_msgs the transcript says now (a machine session stays as a record with
    origin machine; records are never removed). An unreadable transcript is skipped."""
    changed = 0
    for path in sorted((paths.state_dir() / "pulse" / "open").glob("*.json")):
        changed += _settle_draft(path.stem)
    machine = get_machine_name()
    for path in sorted(paths.records("sessions", machine).glob("*/*.md")):
        changed += _settle_record(path)
    return changed


# Filled by the Codex probe (Task 1 Step 2); while empty, a Codex handoff takes the slug path.
CODEX_ID_VARS: tuple[str, ...] = ()        # env vars that carry a Codex session UUID
CODEX_SHELL_MARKERS: tuple[str, ...] = ()  # env vars whose presence marks a Codex shell


def in_codex_shell() -> bool:
    return any(os.environ.get(name) for name in CODEX_SHELL_MARKERS)


def program_session() -> tuple[str, str] | None:
    """(tool, session id) of the program running this process, or None when it is unknown."""
    claude = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if claude:
        return "claude", claude
    for name in CODEX_ID_VARS:
        if os.environ.get(name):
            return "codex", os.environ[name]
    if in_codex_shell():
        sid = find_open("codex", os.getcwd())
        if sid:
            return "codex", sid
    return None
