"""Tables of state/index.sqlite (#548 §5). A different version is a rebuild, never a migration."""
from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE stamps(path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER);
CREATE TABLE projects(id TEXT PRIMARY KEY, domain TEXT, label TEXT, type TEXT, github TEXT);
CREATE TABLE repos(pattern TEXT, kind TEXT, project TEXT, domain TEXT);
CREATE TABLE sessions(path TEXT PRIMARY KEY, dir TEXT, session_id TEXT, machine TEXT,
                      project TEXT, domain TEXT, date TEXT, updated_at TEXT, branch TEXT,
                      last_commit TEXT, done TEXT, remains TEXT, artifacts TEXT, conflict INTEGER);
CREATE INDEX sessions_project ON sessions(project, updated_at);
CREATE TABLE registry_history(line INTEGER PRIMARY KEY, ts TEXT, machine TEXT, project TEXT,
                              status TEXT, raw TEXT);
CREATE TABLE problems(path TEXT PRIMARY KEY, error TEXT);
"""


class Mismatch(Exception):
    """The file is a database, but not this schema: drop it and build again."""


def ensure(conn: sqlite3.Connection) -> bool:
    """True when the tables were just created in an empty database; Mismatch for any other
    version. A file that is not a database raises sqlite3.DatabaseError on the first query."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables:
        conn.executescript(DDL)
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()
        return True
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() \
        if "meta" in tables else None
    if row is None or row[0] != str(SCHEMA_VERSION):
        raise Mismatch(f"schema_version {row[0] if row else None}, expected {SCHEMA_VERSION}")
    return False
