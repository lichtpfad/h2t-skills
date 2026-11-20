"""SQLite mirror of the journal, the raw zone and the insights results (opt-in, `--store`).

The JSONL files stay the record; these tables are a copy for queries. Opened only through
store.connect_sqlite.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from h2t_ops.core import paths, store

_JOURNAL_COLS = ("id", "ts", "run_id", "process", "step", "channel", "account", "action", "source_ids",
                 "context_refs", "rule_id", "decision", "approved_by", "task_id", "result")
_JSON_COLS = ("source_ids", "context_refs", "result")
_RAW_COLS = ("id", "ts", "run_id", "process", "account", "endpoint", "payload")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
    id TEXT PRIMARY KEY, ts TEXT, run_id TEXT, process TEXT, step INTEGER, channel TEXT,
    account TEXT, action TEXT, source_ids TEXT, context_refs TEXT, rule_id TEXT, decision TEXT,
    approved_by TEXT, task_id TEXT, result TEXT, extra TEXT);
CREATE INDEX IF NOT EXISTS journal_run ON journal (run_id);
CREATE TABLE IF NOT EXISTS raw (
    id TEXT PRIMARY KEY, ts TEXT, run_id TEXT, process TEXT, account TEXT, endpoint TEXT, payload TEXT);
CREATE INDEX IF NOT EXISTS raw_run ON raw (run_id);
CREATE TABLE IF NOT EXISTS results (
    run_id TEXT, account TEXT, schema_version TEXT, body TEXT, PRIMARY KEY (run_id, account));
"""


def db_path() -> Path:
    return paths.data_dir() / "social" / "social.db"


@contextmanager
def _conn():
    with store.connect_sqlite(db_path(), place="data") as conn:
        conn.executescript(_SCHEMA)
        yield conn


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def put_journal(rec: dict) -> None:
    extra = {k: v for k, v in rec.items() if k not in _JOURNAL_COLS}
    values = [_dump(rec.get(c)) if c in _JSON_COLS else rec.get(c) for c in _JOURNAL_COLS]
    with _conn() as conn:
        conn.execute(f"INSERT OR REPLACE INTO journal ({', '.join(_JOURNAL_COLS)}, extra) "
                     f"VALUES ({', '.join('?' * (len(_JOURNAL_COLS) + 1))})", [*values, _dump(extra)])


def put_raw(rec: dict) -> None:
    values = [_dump(rec.get(c)) if c == "payload" else rec.get(c) for c in _RAW_COLS]
    with _conn() as conn:
        conn.execute(f"INSERT OR REPLACE INTO raw ({', '.join(_RAW_COLS)}) "
                     f"VALUES ({', '.join('?' * len(_RAW_COLS))})", values)


def put_result(run_id: str, account: str, body: dict) -> None:
    from h2t_ops.connectors.social import journal
    from h2t_ops.connectors.social.insights import SCHEMA_VERSION

    text = _dump(body)
    journal.check_no_secret(text, f"result {run_id}/{account}")
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO results (run_id, account, schema_version, body) "
                     "VALUES (?, ?, ?, ?)", (run_id, account, SCHEMA_VERSION, text))


def read_journal(run_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(f"SELECT {', '.join(_JOURNAL_COLS)}, extra FROM journal WHERE run_id = ? "
                            "ORDER BY ts, rowid", (run_id,)).fetchall()
    out = []
    for *vals, extra in rows:
        rec = {c: (json.loads(v) if c in _JSON_COLS else v) for c, v in zip(_JOURNAL_COLS, vals)}
        out.append({**rec, **json.loads(extra)})
    return out


def read_raw(run_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(f"SELECT {', '.join(_RAW_COLS)} FROM raw WHERE run_id = ? ORDER BY ts, rowid",
                            (run_id,)).fetchall()
    return [{c: (json.loads(v) if c == "payload" else v) for c, v in zip(_RAW_COLS, row)} for row in rows]


def read_results(run_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT run_id, account, schema_version, body FROM results WHERE run_id = ? "
                            "ORDER BY account", (run_id,)).fetchall()
    return [{"run_id": r, "account": a, "schema_version": s, "body": json.loads(b)} for r, a, s, b in rows]
