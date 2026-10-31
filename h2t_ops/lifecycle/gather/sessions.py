"""The previous sessions of this project, from every machine, through the index (#548 §5).

The truth is the session md with its frontmatter; state/index.sqlite is what is asked.
Until `h2t-setup sync` has moved the 3.x roots into records/, a project the index does not
know yet is read from them the 3.x way (sessions_legacy).
"""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.lifecycle import index
from h2t_ops.lifecycle.gather import sessions_legacy

SUMMARY_LIMIT = 1200
ITEM_LIMIT = 240
MAX_ITEMS = 5
MAX_ARTIFACTS = 10


def _identity_keys(names: tuple[str, ...]) -> list[str]:
    """Project ids a session may be recorded under, most significant first.

    The writer records project.id (handoff), and several repositories map onto one project
    on purpose — DocGraph and SpecDesigner both onto docgraph — so project.id is what keeps
    their history together. Repo names are asked too, for handoffs written before a project
    was mapped. Duplicates collapse; a name with a path separator is dropped rather than
    failing the whole lookup.
    """
    keys: list[str] = []
    for name in names:
        if not name or "/" in name or "\\" in name:
            continue
        if name not in keys:
            keys.append(name)
    return keys


def _rows(keys: list[str], *, machine: str | None = None, limit: int | None = None) -> list[dict]:
    """Sessions of these projects, newest first by updated_at, from the index."""
    marks = ",".join("?" * len(keys))
    # A record with no `done` is a hook-only record (it has no briefing content); it is left out
    # here for every caller, find_session_files included. Intended: the current, empty session
    # must not be shown as the previous one.
    sql = f"SELECT * FROM sessions WHERE project IN ({marks}) AND COALESCE(done, '') <> ''"
    args: list = list(keys)
    if machine is not None:
        sql += " AND machine = ?"
        args.append(machine)
    sql += " ORDER BY updated_at DESC, path"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    with index.connect() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def find_session_files(*repo_names: str) -> list[str]:
    """Session md paths of this project from the index, newest first."""
    keys = _identity_keys(repo_names)
    if not keys:
        return []
    found = [r["path"] for r in _rows(keys)]
    if not found and sessions_legacy.roots():
        return sessions_legacy.find_session_files(keys)
    return found


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text, False
    marker = " ... [truncated]"
    return text[: max(0, limit - len(marker))].rstrip() + marker, True


def _clean_action(line: str) -> str:
    line = line.strip()
    prefixes = ("- [ ]", "- [x]", "- [X]", "- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")
    for prefix in prefixes:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return line


def _next_actions(remains: str) -> tuple[list[str], bool]:
    """The first MAX_ITEMS distinct lines of `remains`, list markers stripped, each bounded —
    the rule handoff applied when it wrote latest.json."""
    items: list[str] = []
    truncated = False
    lines = [ln for ln in str(remains or "").splitlines() if ln.strip()]
    for line in lines:
        if len(items) >= MAX_ITEMS:
            truncated = True
            break
        item, cut = _truncate(_clean_action(line), ITEM_LIMIT)
        truncated = truncated or cut
        if item not in items:
            items.append(item)
    return items, truncated


def _bounded_items(values: object, *, limit: int = MAX_ITEMS) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_truncate(str(value), ITEM_LIMIT)[0] for value in values[:limit]]


def _bounded_artifacts(values: object) -> list[dict]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:MAX_ARTIFACTS]:
        if isinstance(value, dict):
            result.append({
                "type": str(value.get("type", "artifact"))[:40],
                "ref": str(value.get("ref", ""))[:240],
            })
        else:
            result.append({"type": "artifact", "ref": str(value)[:240]})
    return result


def _from_row(row: dict) -> dict:
    summary, summary_cut = _truncate(row.get("done") or "", SUMMARY_LIMIT)
    actions, actions_cut = _next_actions(row.get("remains") or "")
    try:
        artifacts = json.loads(row.get("artifacts") or "[]")
    except ValueError:
        artifacts = []
    artifacts = artifacts if isinstance(artifacts, list) else []
    return {
        "session_id": str(row.get("session_id") or ""),
        "project": str(row.get("project") or ""),
        "domain": str(row.get("domain") or ""),
        "machine": str(row.get("machine") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "branch": str(row.get("branch") or ""),
        "last_commit": str(row.get("last_commit") or ""),
        "summary_short": summary,
        "next_actions": actions,
        "blockers": [],
        "artifacts": _bounded_artifacts(artifacts),
        "markdown_path": str(row.get("path") or ""),
        "truncated": summary_cut or actions_cut or len(artifacts) > MAX_ARTIFACTS,
        "here": None,
    }


def _from_legacy(keys: list[str]) -> dict | None:
    """3.x latest.json, bounded as 3.x bounded it; `legacy` tells the briefing to say so."""
    found = sessions_legacy.find_latest(keys)
    if found is None:
        # DOR wrote only markdown, and a 3.x latest.json may be missing or unreadable: the
        # newest md still says where the history is, and the briefing that it has not moved.
        files = sessions_legacy.find_session_files(keys)
        if not files:
            return None
        newest = Path(files[0])
        stamp = datetime.fromtimestamp(newest.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"session_id": newest.stem, "project": newest.parent.name, "domain": "",
                "machine": newest.parent.parent.name, "updated_at": stamp, "branch": "",
                "last_commit": "", "summary_short": "", "next_actions": [], "blockers": [],
                "artifacts": [], "markdown_path": str(newest), "truncated": False,
                "here": None, "legacy": True}
    data, path = found
    return {
        "session_id": str(data.get("session_id", "")),
        "project": str(data.get("project", "")),
        "domain": str(data.get("domain", "")),
        "machine": path.parent.parent.name,
        "updated_at": str(data.get("updated_at", "")),
        "branch": "",
        "last_commit": "",
        "summary_short": _truncate(str(data.get("summary_short", "")), SUMMARY_LIMIT)[0],
        "next_actions": _bounded_items(data.get("next_actions")),
        "blockers": _bounded_items(data.get("blockers")),
        "artifacts": _bounded_artifacts(data.get("artifacts")),
        "markdown_path": str(data.get("markdown_path", "")),
        "truncated": bool(data.get("truncated", False)),
        "here": None,
        "legacy": True,
    }


def _when(stamp) -> datetime:
    """updated_at as an aware datetime; an unreadable stamp is the oldest possible."""
    try:
        ts = datetime.fromisoformat(str(stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def find_latest_session_index(*repo_names: str) -> dict | None:
    """The newest session of this project from any machine, bounded for the briefing.

    `here` is this machine's own newest session of the project when the newest of all was
    written elsewhere — the briefing warns that this checkout may be behind.
    """
    keys = _identity_keys(repo_names)
    if not keys:
        return None
    rows = _rows(keys, limit=1)
    if not rows:
        return _from_legacy(keys) if sessions_legacy.roots() else None
    latest = _from_row(rows[0])
    me = paths.machine_name()
    if latest["machine"] != me:
        mine = _rows(keys, machine=me, limit=1)
        # Strictly newer: an equal stamp is a path tiebreak, not work done elsewhere later.
        if mine and _when(mine[0].get("updated_at")) < _when(latest["updated_at"]):
            latest["here"] = {"machine": me, "updated_at": str(mine[0].get("updated_at") or ""),
                              "markdown_path": str(mine[0].get("path") or "")}
    return latest

def extract_session_id(memory_dir: str | None = None) -> str:
    """Extract Claude session ID from newest .jsonl file in memory_dir parent."""
    if not memory_dir:
        return ""
    project_dir = Path(memory_dir).parent
    if not project_dir.exists():
        return ""
    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    return jsonl_files[0].stem if jsonl_files else ""

def get_machine_name() -> str:
    """The machine segment of session paths: H2T_MACHINE_NAME, DOR_MACHINE_NAME, hostname.

    The rule lives in core/paths.machine_name; this name stays for its importers (#491).
    The handoff writer, this reader and the activity spool each carried a copy, and the
    spool's kept the hostname's case, so
    one MacBook wrote `Mac` to the spool and `mac/` to the path. On macOS the hostname
    follows the network; `h2t-core:setup` pins H2T_MACHINE_NAME so it stops mattering.
    """
    return paths.machine_name()
