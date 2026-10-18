"""Open, rebuild and ask state/index.sqlite (#548 §5). The base is derived and never synced:
a different schema or a damaged file is removed and built again from records and config."""
from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.lifecycle.index import build, schema


def index_path() -> Path:
    return paths.state_dir() / "index.sqlite"


def _drop(path: Path) -> None:
    for side in (path, path.with_name(path.name + "-journal")):
        store.remove(side, place="state")


@contextlib.contextmanager
def connect(*, refresh: bool = True) -> Iterator[sqlite3.Connection]:
    """A connection to an index whose schema matches, refreshed by stat unless refresh=False
    (a new, empty base is always filled). Opened only through store.connect_sqlite (R18)."""
    path = index_path()
    for attempt in (0, 1):
        stack = contextlib.ExitStack()
        try:
            conn = stack.enter_context(store.connect_sqlite(path, place="state"))
            if schema.ensure(conn) or refresh:
                build.refresh(conn)
        except BaseException as exc:
            stack.__exit__(type(exc), exc, exc.__traceback__)   # closed without a commit
            if attempt or not isinstance(exc, (sqlite3.DatabaseError, schema.Mismatch)):
                raise
            _drop(path)
            continue
        with stack:
            conn.row_factory = sqlite3.Row
            yield conn
        return


def rebuild() -> dict:
    _drop(index_path())
    with connect() as conn:
        return {name: conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in ("sessions", "projects", "problems")}


def latest_sessions(project_ids: list[str], limit: int = 5) -> list[dict]:
    """Newest first by updated_at, across every machine."""
    if not project_ids:
        return []
    marks = ",".join("?" * len(project_ids))
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM sessions WHERE project IN ({marks}) "
                            "ORDER BY updated_at DESC, path LIMIT ?", (*project_ids, limit))
        return [dict(r) for r in rows]


def ontology() -> tuple[dict, dict]:
    """(repo_mapping_doc, domains_doc) as parsed by build; {} for a file that is missing."""
    with connect() as conn:
        meta = dict(conn.execute("SELECT key, value FROM meta WHERE key IN ('repo_mapping', 'domains')"))
    return (json.loads(meta.get("repo_mapping", "{}")), json.loads(meta.get("domains", "{}")))


def problems() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT path, error FROM problems ORDER BY path")]
