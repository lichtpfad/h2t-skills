"""Tables of state/index.sqlite (#548 §5). A different version is a rebuild, never a migration."""
from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS stamps(path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER);
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, domain TEXT, label TEXT, type TEXT, github TEXT);
CREATE TABLE IF NOT EXISTS repos(pattern TEXT, kind TEXT, project TEXT, domain TEXT);
CREATE TABLE IF NOT EXISTS sessions(path TEXT PRIMARY KEY, dir TEXT, session_id TEXT, machine TEXT,
                      project TEXT, domain TEXT, date TEXT, updated_at TEXT, branch TEXT,
                      last_commit TEXT, done TEXT, remains TEXT, artifacts TEXT, conflict INTEGER);
CREATE INDEX IF NOT EXISTS sessions_project ON sessions(project, updated_at);
CREATE TABLE IF NOT EXISTS registry_history(line INTEGER PRIMARY KEY, ts TEXT, machine TEXT, project TEXT,
                              status TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS problems(path TEXT PRIMARY KEY, error TEXT);
"""


class Mismatch(Exception):
    """The file is a database, but not this schema: drop it and build again."""


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def ensure(conn: sqlite3.Connection) -> bool:
    """True when this call created the tables; Mismatch for any other version. Creation and
    the version row are one IMMEDIATE transaction, so a peer opening the same new file waits
    and then sees either nothing or the whole schema — never tables without a version.
    A file that is not a database raises sqlite3.DatabaseError on the first query."""
    if not _tables(conn):
        conn.execute("BEGIN IMMEDIATE")
        try:
            created = not _tables(conn)          # asked again under the write lock
            if created:
                for stmt in filter(str.strip, DDL.split(";")):
                    conn.execute(stmt)
                conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)",
                             (str(SCHEMA_VERSION),))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        if created:
            return True
    tables = _tables(conn)
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() \
        if "meta" in tables else None
    if row is None or row[0] != str(SCHEMA_VERSION):
        raise Mismatch(f"schema_version {row[0] if row else None}, expected {SCHEMA_VERSION}")
    return False
