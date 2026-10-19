"""Bring state/index.sqlite up to date by stat (#548 §5).

The only module that parses domains.yaml and repo-mapping.yaml. What is looked at, and what
a change means:

1. each ontology file — changed, both are read again;
2. each leaf directory records/sessions/<machine>/<project>/ — changed or new, every *.md in
   it is read again; a directory that is gone takes its rows with it;
3. records/imports/dor-registry.jsonl — changed, read again.

A leaf directory's stat moves when a file in it is created, renamed or removed, which is how
handoff (store.replace) and a synchroniser publish a file. An md edited in place by an
editor that does not rename changes only the file's stat and stays unseen until the
directory changes next; §5 looks at directories, and that cost is accepted there.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path

import yaml

from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record

MAPPING, DOMAINS = "repo-mapping.yaml", "domains.yaml"
REQUIRED = ("session_id", "machine", "project")
_COLUMNS = ("path", "dir", "session_id", "machine", "project", "domain", "date", "updated_at",
            "branch", "last_commit", "done", "remains", "artifacts", "conflict")


def _load_yaml(path: Path) -> dict:
    """{} for a missing or empty file; ValueError when it does not parse as a mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"does not parse: {exc}") from exc
    if doc is None:
        return {}
    if not isinstance(doc, dict):
        raise ValueError("is not a mapping")
    return doc


def load_ontology(config_root: Path) -> tuple[dict, dict]:
    """(repo_mapping_doc, domains_doc) read straight from config_root, no index (Task 15)."""
    return _load_yaml(Path(config_root) / MAPPING), _load_yaml(Path(config_root) / DOMAINS)


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return st.st_mtime_ns, st.st_size


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _forget_problems(conn: sqlite3.Connection, keep) -> None:
    """Drop the problem rows `keep(path)` says belong to what is being read again."""
    for (p,) in conn.execute("SELECT path FROM problems").fetchall():
        if keep(Path(p)):
            conn.execute("DELETE FROM problems WHERE path=?", (p,))


def _read_ontology(conn: sqlite3.Connection, config: Path) -> None:
    docs = {}
    for name in (MAPPING, DOMAINS):
        f = config / name
        conn.execute("DELETE FROM problems WHERE path=?", (str(f),))
        try:
            docs[name] = _load_yaml(f)
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            conn.execute("INSERT INTO problems VALUES (?, ?)", (str(f), str(exc)))
            docs[name] = {}
    mapping, domains = docs[MAPPING], docs[DOMAINS]
    for key, doc in (("repo_mapping", mapping), ("domains", domains)):
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                     (key, json.dumps(doc, ensure_ascii=False, default=str)))
    conn.execute("DELETE FROM projects")
    for domain, data in (domains.get("domains") or {}).items():
        for proj in (data or {}).get("projects") or []:
            if isinstance(proj, dict) and proj.get("id"):
                # INSERT OR IGNORE: the first domain to claim an id wins, as in gather/project.py
                conn.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?, ?, ?)",
                             (_text(proj["id"]), _text(domain), _text(proj.get("label", proj["id"])),
                              _text(proj.get("type")), _text(proj.get("github"))))
    conn.execute("DELETE FROM repos")
    for kind, key in (("mapping", "mappings"), ("cwd", "cwd_patterns")):
        for pattern, target in (mapping.get(key) or {}).items():
            domain, _, project = str(target).partition("/")
            conn.execute("INSERT INTO repos VALUES (?, ?, ?, ?)",
                         (str(pattern), kind, project or "unknown", domain))


def _session_row(f: Path, leaf: Path) -> tuple:
    meta, _body = session_record.parse(f.read_bytes())
    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise ValueError(f"frontmatter lacks {', '.join(missing)}")
    commits = meta.get("commits")
    last = commits[0] if isinstance(commits, list) and commits else (commits or "")
    return (str(f), str(leaf), *(_text(meta.get(k)) for k in
            ("session_id", "machine", "project", "domain", "date", "updated_at", "branch")),
            _text(last) or "", *(_text(meta.get(k)) for k in ("done", "remains", "artifacts")),
            int(".sync-conflict-" in f.name))


def _read_leaf(conn: sqlite3.Connection, leaf: Path) -> None:
    conn.execute("DELETE FROM sessions WHERE dir=?", (str(leaf),))
    _forget_problems(conn, lambda p: p.parent == leaf)
    try:
        files = sorted(leaf.iterdir())
    except FileNotFoundError:
        return
    marks = ",".join("?" * len(_COLUMNS))
    for f in files:
        if f.suffix != ".md" or ".from-" in f.name or not f.is_file():
            continue
        try:
            row = _session_row(f, leaf)
        except (ValueError, OSError) as exc:
            conn.execute("INSERT OR REPLACE INTO problems VALUES (?, ?)", (str(f), str(exc)))
            continue
        conn.execute(f"INSERT OR REPLACE INTO sessions VALUES ({marks})", row)


def _read_registry(conn: sqlite3.Connection, f: Path) -> None:
    """DOR's rows carry id, status, ts, host, cwd, repo, branch, domain, project, resume;
    the machine is `host`. The whole line stays in `raw`."""
    conn.execute("DELETE FROM registry_history")
    conn.execute("DELETE FROM problems WHERE path=?", (str(f),))
    try:
        raw = f.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as exc:
        conn.execute("INSERT INTO problems VALUES (?, ?)", (str(f), str(exc)))
        return
    for n, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        obj = obj if isinstance(obj, dict) else {}     # the raw line keeps what did not parse
        conn.execute("INSERT INTO registry_history VALUES (?, ?, ?, ?, ?, ?)",
                     (n, _text(obj.get("ts")), _text(obj.get("host", obj.get("machine"))),
                      _text(obj.get("project")), _text(obj.get("status")), line))


def _leaves(base: Path) -> list[Path]:
    try:
        machines = [m for m in base.iterdir() if m.is_dir()]
    except FileNotFoundError:
        return []
    return [p for m in machines for p in m.iterdir() if p.is_dir()]


def refresh(conn: sqlite3.Connection) -> None:
    """Read again whatever changed by stat since the last refresh. Each stat is taken before
    its read: a file landing in between leaves the old stamp, and the next refresh reads it.
    One IMMEDIATE transaction: a peer refreshing at the same time waits, then finds the
    stamps this one wrote and has nothing left to do."""
    conn.execute("BEGIN IMMEDIATE")
    stored = {p: (m, s) for p, m, s in conn.execute("SELECT path, mtime_ns, size FROM stamps")}
    now: dict[str, tuple[int, int] | None] = {}

    def changed(path: Path) -> bool:
        key = str(path)
        now[key] = _stamp(path)
        return now[key] != stored.get(key)

    config = paths.config_dir()
    if any([changed(config / MAPPING), changed(config / DOMAINS)]):   # a list: stat both
        _read_ontology(conn, config)

    base = paths.records("sessions")
    for leaf in _leaves(base):
        if changed(leaf):
            _read_leaf(conn, leaf)

    registry = paths.records("imports") / "dor-registry.jsonl"
    if changed(registry):
        _read_registry(conn, registry)

    for key in stored.keys() - now.keys():    # a leaf that is gone, or a root that moved
        conn.execute("DELETE FROM sessions WHERE dir=?", (key,))
        _forget_problems(conn, lambda p, k=Path(key): p.parent == k)
        conn.execute("DELETE FROM stamps WHERE path=?", (key,))
    for key, st in now.items():
        if st is None:
            conn.execute("DELETE FROM stamps WHERE path=?", (key,))
        elif st != stored.get(key):
            conn.execute("INSERT OR REPLACE INTO stamps VALUES (?, ?, ?)", (key, *st))
    conn.commit()
