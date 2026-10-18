"""Open, rebuild and ask state/index.sqlite (#548 §5). The base is derived and never synced:
a different schema or a damaged file is built again from records and config.

Several session-starts can open the base at once. A peer's lock is not damage: it is
waited on (busy timeout), retried once, and then the base is served as it stands without a
refresh. Only a schema mismatch or a file sqlite cannot read as a database is rebuilt, and
a rebuild is built aside and published over the old file in one replace — the base is never
unlinked under a peer that has it open.
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.core.errors import ConfigError
from h2t_ops.lifecycle.index import build, schema

BUSY_MS = 10_000
LOCK_S = 5.0     # state/index.lock: past this a holder is taken as hung, the base served as is


def index_path() -> Path:
    return paths.state_dir() / "index.sqlite"


def _lock_path() -> Path:
    # Beside the base, not in state/locks: a broken locks/ (gather tolerates one) must not
    # cost the briefing; whatever stops this file stops the base too.
    return paths.state_dir() / "index.lock"


def _open(path: Path, *, ensure: bool, refresh: bool,
          scratch: bool = False) -> tuple[contextlib.ExitStack, sqlite3.Connection]:
    stack = contextlib.ExitStack()
    try:
        conn = stack.enter_context(store.connect_sqlite(path, place="state"))
        conn.execute(f"PRAGMA busy_timeout = {BUSY_MS}")
        if scratch:
            # The rollback journal of a base being built aside stays in memory: a killed
            # build then leaves only the .h2t-tmp file doctor reports, no -journal beside it.
            conn.execute("PRAGMA journal_mode = MEMORY")
        if ensure and (schema.ensure(conn) or refresh):
            build.refresh(conn)
    except BaseException as exc:
        stack.__exit__(type(exc), exc, exc.__traceback__)   # closed without a commit
        raise
    return stack, conn


def _remove_if_there(p: Path) -> None:
    if p.exists():
        store.remove(p, place="state")


def _rebuild_file(path: Path) -> None:
    """Build a whole new base beside the index, then publish it with store.replace. The
    caller holds the index lock: no peer is inside a write transaction on the old file, so
    there is no live journal to remove and none to be played into the new file."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.build.h2t-tmp")  # doctor names leftovers (R48)
    journal = path.with_name(path.name + "-journal")
    try:
        _remove_if_there(tmp)
        stack, _conn = _open(tmp, ensure=True, refresh=True, scratch=True)
        stack.close()
        # A hot journal a killed writer left on the old file would be played into the new one.
        _remove_if_there(journal)
        store.replace(path, tmp.read_bytes(), place="state")
    finally:
        _remove_if_there(tmp)


_UNBUILT = "the index is not built yet and another process holds it locked; shown empty"


def _serve_empty_if_unbuilt(conn: sqlite3.Connection, path: Path) -> None:
    """A brand-new base served under a peer's long lock has no tables, and every query on it
    would raise "no such table". Shadow them with empty TEMP tables of the same schema — the
    file is not written — and say why in problems."""
    if schema._tables(conn):
        return
    for stmt in filter(str.strip, schema.DDL.split(";")):
        if stmt.lstrip().startswith("CREATE TABLE"):
            conn.execute(stmt.replace("CREATE TABLE", "CREATE TEMP TABLE", 1))
    conn.execute("INSERT INTO temp.problems VALUES (?, ?)", (str(path), _UNBUILT))


@contextlib.contextmanager
def connect(*, refresh: bool = True) -> Iterator[sqlite3.Connection]:
    """A connection to an index whose schema matches, refreshed by stat unless refresh=False
    (a new, empty base is always filled). Opened only through store.connect_sqlite (R18).
    Every write to the base — schema, refresh, rebuild — runs under state/index.lock;
    the queries after it do not."""
    path = index_path()
    try:
        with store.locked(_lock_path(), place="state", timeout=LOCK_S):
            try:
                stack, conn = _open(path, ensure=True, refresh=refresh)
            except sqlite3.OperationalError:         # busy or locked by a peer: not damage
                try:
                    stack, conn = _open(path, ensure=True, refresh=refresh)
                except sqlite3.OperationalError:
                    stack, conn = _as_it_stands(path)
            except (sqlite3.DatabaseError, schema.Mismatch):
                _rebuild_file(path)
                stack, conn = _open(path, ensure=True, refresh=False)
    except store.LockBusy:          # a hung holder must not hang session-start with it
        stack, conn = _as_it_stands(path)
    with stack:
        conn.row_factory = sqlite3.Row
        yield conn


def _as_it_stands(path: Path) -> tuple[contextlib.ExitStack, sqlite3.Connection]:
    """The base without a refresh or any write to it; empty with a problem row if unbuilt."""
    stack, conn = _open(path, ensure=False, refresh=False)
    try:
        _serve_empty_if_unbuilt(conn, path)
    except BaseException as exc:
        stack.__exit__(type(exc), exc, exc.__traceback__)
        raise
    return stack, conn


def rebuild() -> dict:
    try:
        with store.locked(_lock_path(), place="state", timeout=LOCK_S):
            _rebuild_file(index_path())
    except store.LockBusy:
        raise ConfigError("index is locked by another process", hint=(
            f"another h2t command holds {_lock_path()} for over {LOCK_S} s; "
            "retry when it has finished")) from None
    with connect(refresh=False) as conn:
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
