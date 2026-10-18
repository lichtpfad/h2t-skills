"""state/index.sqlite, derived from session md frontmatter and the ontology (#548 §5)."""
import json
import multiprocessing
import os
import shutil
import sqlite3
import sys
import time

import pytest

from h2t_ops.core import paths
from h2t_ops.lifecycle import index, session_record
from h2t_ops.lifecycle.index import query, schema


def _md(machine, project, sid, updated_at="2026-10-18T10:00:00Z", name=None, **extra):
    meta = {"session_id": sid, "machine": machine, "project": project, "domain": "dev",
            "date": updated_at[:10], "updated_at": updated_at, "branch": "feat/x",
            "commits": ["a1b2c3d newest", "0000000 older"], "done": "- did", "remains": "- [ ] next",
            "artifacts": ["pr:1"], **extra}
    f = paths.records("sessions", machine) / project / (name or f"{sid}.md")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(session_record.render(meta, b"# body\n"))
    return f


def _domains(label):
    f = paths.config_dir() / "domains.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"domains:\n  dev:\n    projects:\n      - id: p\n        label: {label}\n",
                 encoding="utf-8")
    return f


def _rows(sql):
    with index.connect(refresh=False) as conn:
        return [dict(r) for r in conn.execute(sql)]


def test_rebuild_reads_frontmatter_of_every_machine():
    _md("mac", "p", "s1", "2026-10-17T09:00:00Z")
    _md("laptop", "p", "s2", "2026-10-18T09:00:00Z")
    _domains("Proj")
    (paths.config_dir() / "repo-mapping.yaml").write_text(
        "mappings:\n  h2t-skills: dev/p\ncwd_patterns:\n  /w/x: dev/q\n", encoding="utf-8")
    imports = paths.records("imports")
    imports.mkdir(parents=True)
    (imports / "dor-registry.jsonl").write_text(
        '{"id": "r1", "status": "done", "ts": "2026-03-17T10:00:00Z", "host": "mac", "cwd": "/w/p", '
        '"repo": "h2t-skills", "branch": "main", "domain": "dev", "project": "p", "resume": "x"}\n'
        'not json\n',
        encoding="utf-8")

    assert index.rebuild() == {"sessions": 2, "projects": 1, "problems": 0}
    got = {r["machine"]: r for r in _rows("SELECT * FROM sessions")}
    assert set(got) == {"mac", "laptop"}
    assert got["mac"]["last_commit"] == "a1b2c3d newest"
    assert got["mac"]["branch"] == "feat/x" and got["mac"]["conflict"] == 0
    assert _rows("SELECT id, domain, label FROM projects") == [{"id": "p", "domain": "dev", "label": "Proj"}]
    assert {(r["pattern"], r["kind"], r["project"]) for r in _rows("SELECT * FROM repos")} == {
        ("h2t-skills", "mapping", "p"), ("/w/x", "cwd", "q")}
    hist = _rows("SELECT line, ts, machine, project, status, raw FROM registry_history ORDER BY line")
    assert [(h["line"], h["ts"], h["machine"], h["project"], h["status"]) for h in hist] == [
        (1, "2026-03-17T10:00:00Z", "mac", "p", "done"), (2, None, None, None, None)]
    assert hist[1]["raw"] == "not json"
    mapping, domains = index.ontology()
    assert mapping["mappings"] == {"h2t-skills": "dev/p"}
    assert domains["domains"]["dev"]["projects"][0]["label"] == "Proj"


def test_new_file_from_another_machine_is_seen_on_next_connect():
    _md("mac", "p", "s1", "2026-10-17T09:00:00Z")
    index.rebuild()
    _md("laptop", "p", "s2", "2026-10-18T09:00:00Z")     # a directory that did not exist
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["s2", "s1"]


def test_yaml_edit_in_place_is_seen():
    f = _domains("AAAA")
    assert index.ontology()[1]["domains"]["dev"]["projects"][0]["label"] == "AAAA"
    before = f.stat()
    f.write_text(f.read_text(encoding="utf-8").replace("AAAA", "BBBB"), encoding="utf-8")
    later = before.st_mtime_ns + 5_000_000_000
    os.utime(f, ns=(later, later))
    assert f.stat().st_size == before.st_size
    assert index.ontology()[1]["domains"]["dev"]["projects"][0]["label"] == "BBBB"
    assert _rows("SELECT label FROM projects") == [{"label": "BBBB"}]


def test_broken_frontmatter_is_skipped_and_reported():
    """Review Focus 3: a hand edit or a sync conflict breaks one header; the rest still show."""
    good = _md("mac", "p", "good")
    leaf = good.parent
    (leaf / "yaml.md").write_bytes(b"---\nsession_id: [unclosed\n---\n# body\n")
    (leaf / "plain.md").write_bytes(b"# a session written by hand\n")
    (leaf / "partial.md").write_bytes(session_record.render({"session_id": "x"}, b""))

    assert index.rebuild() == {"sessions": 1, "projects": 0, "problems": 3}
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["good"]
    got = {p["path"]: p["error"] for p in index.problems()}
    assert set(got) == {str(leaf / n) for n in ("yaml.md", "plain.md", "partial.md")}
    assert "does not parse" in got[str(leaf / "yaml.md")]
    assert got[str(leaf / "plain.md")] == "no frontmatter"
    assert "lacks machine, project" in got[str(leaf / "partial.md")]

    (leaf / "yaml.md").write_bytes(session_record.render(
        {"session_id": "fixed", "machine": "mac", "project": "p", "updated_at": "2026-10-19T00:00:00Z"}, b""))
    os.utime(leaf, ns=(time.time_ns() + 10**9,) * 2)      # the repair must move the leaf's stat
    assert len(index.problems()) == 2
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["fixed", "good"]


def test_schema_mismatch_rebuilds():
    _md("mac", "p", "s1")
    index.rebuild()
    db = sqlite3.connect(query.index_path())
    db.execute("UPDATE meta SET value='0' WHERE key='schema_version'")
    db.execute("INSERT INTO sessions(path, project, updated_at) VALUES ('stale', 'p', '9999')")
    db.commit()
    db.close()
    assert [s["path"] for s in index.latest_sessions(["p"])] != ["stale"]
    assert _rows("SELECT value FROM meta WHERE key='schema_version'") == [{"value": str(index.SCHEMA_VERSION)}]
    assert [r["session_id"] for r in _rows("SELECT session_id FROM sessions")] == ["s1"]


def test_corrupt_db_rebuilds():
    _md("mac", "p", "s1")
    index.rebuild()
    query.index_path().write_bytes(b"this is not a database at all " * 200)
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["s1"]


def test_sync_conflict_file_is_flagged():
    f = _md("mac", "p", "s1")
    _md("mac", "p", "s1", name="s1.sync-conflict-20261018-120000-ABCDEFG.md")
    (f.parent / "s1.md.from-laptop").write_bytes(f.read_bytes())
    _md("mac", "p", "s1", name="s1.from-laptop.md")
    index.rebuild()
    got = {os.path.basename(r["path"]): r["conflict"] for r in _rows("SELECT path, conflict FROM sessions")}
    assert got == {"s1.md": 0, "s1.sync-conflict-20261018-120000-ABCDEFG.md": 1}


def test_latest_sessions_orders_across_machines_by_updated_at():
    _md("mac", "p", "old", "2026-10-01T00:00:00Z")
    _md("laptop", "p", "newest", "2026-10-18T00:00:00Z")
    _md("mac", "p", "mid", "2026-10-10T00:00:00Z")
    _md("laptop", "q", "other", "2026-10-30T00:00:00Z")
    got = index.latest_sessions(["p"])
    assert [(s["session_id"], s["machine"]) for s in got] == [
        ("newest", "laptop"), ("mid", "mac"), ("old", "mac")]
    assert [s["session_id"] for s in index.latest_sessions(["p"], limit=2)] == ["newest", "mid"]
    assert [s["session_id"] for s in index.latest_sessions(["p", "q"], limit=1)] == ["other"]


def test_vanished_directory_drops_its_rows():
    gone = _md("laptop", "p", "s2").parent
    _md("mac", "p", "s1")
    (gone / "bad.md").write_bytes(b"no header")
    index.rebuild()
    shutil.rmtree(gone)
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["s1"]
    assert index.problems() == []


def _first_open(barrier, q):
    try:
        barrier.wait()
        q.put(("ok", len(index.latest_sessions(["p"], limit=100))))
    except BaseException as exc:                     # noqa: BLE001 — reported to the parent
        q.put(("err", repr(exc)))


@pytest.mark.skipif(sys.platform == "win32", reason="fork start method")
def test_concurrent_first_open_neither_raises_nor_removes(tmp_path, monkeypatch):
    """Four session-starts on a machine with no index yet, released together: a peer's lock
    or half-made schema is not damage, so nobody raises and nobody removes the base."""
    ctx = multiprocessing.get_context("fork")
    bad = []
    for trial in range(6):
        home = tmp_path / f"h{trial}"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("USERPROFILE", str(home))
        for s in range(40):
            _md(f"m{s % 2}", "p", f"s{s}")
        barrier, q = ctx.Barrier(4), ctx.Queue()
        procs = [ctx.Process(target=_first_open, args=(barrier, q)) for _ in range(4)]
        for p in procs:
            p.start()
        got = [q.get(timeout=60) for _ in procs]
        for p in procs:
            p.join(timeout=60)
        bad += [f"trial {trial}: {g}" for g in got if g != ("ok", 40)]
        log = paths.logs_dir() / "writes.jsonl"
        ops = [json.loads(line)["op"] for line in log.read_text(encoding="utf-8").splitlines()]
        bad += [f"trial {trial}: a remove row" for op in ops if op == "remove"]
    assert bad == []


def test_schema_creation_is_atomic_for_peers(tmp_path):
    """A peer opening the new file right after the first CREATE must wait for the lock, never
    see tables without the version row (that reads as Mismatch and triggers a rebuild)."""
    db = tmp_path / "new.sqlite"
    seen = []

    class Creator:            # the connection creating the schema, with a peer at the seam
        def __init__(self):
            self.conn = sqlite3.connect(db)

        def execute(self, sql, *args):
            cur = self.conn.execute(sql, *args)
            if sql.lstrip().startswith("CREATE TABLE") and not seen:
                peer = sqlite3.connect(db, timeout=0)
                try:
                    schema.ensure(peer)
                    seen.append("created again")
                except Exception as exc:  # noqa: BLE001 — the outcome is the assertion
                    seen.append(repr(exc))
                finally:
                    peer.close()
            return cur

        def commit(self):
            self.conn.commit()

        def rollback(self):
            self.conn.rollback()

    creator = Creator()
    assert schema.ensure(creator) is True
    creator.conn.close()
    assert seen == ["OperationalError('database is locked')"]


def test_locked_base_is_served_not_removed(monkeypatch):
    """A peer holding the write lock past the busy timeout: the base is served as it stands
    (without the refresh), never removed or replaced."""
    _md("mac", "p", "s1", "2026-10-17T00:00:00Z")
    index.rebuild()
    _md("laptop", "p", "s2", "2026-10-18T00:00:00Z")    # would need a refresh to be seen
    monkeypatch.setattr(query, "BUSY_MS", 50)
    inode = query.index_path().stat().st_ino
    log = paths.logs_dir() / "writes.jsonl"
    rows_before = len(log.read_text(encoding="utf-8").splitlines())
    peer = sqlite3.connect(query.index_path(), timeout=0)
    peer.execute("BEGIN IMMEDIATE")
    try:
        assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["s1"]
    finally:
        peer.rollback()
        peer.close()
    assert query.index_path().stat().st_ino == inode
    new = [json.loads(line)["op"] for line in log.read_text(encoding="utf-8").splitlines()[rows_before:]]
    assert "remove" not in new and "replace" not in new, new
    assert [s["session_id"] for s in index.latest_sessions(["p"])] == ["s2", "s1"]   # lock gone


@pytest.mark.slow
def test_build_and_stat_pass_fit_the_budget():
    """§11.2: a full build over ~318 md measured 15-66 ms and a stat pass 0.3-0.7 ms; the
    budget here is 3 s and 0.1 s, loose enough for CI, tight enough to catch a re-read."""
    for m in ("mac", "laptop"):
        for p in range(16):
            for s in range(10):
                _md(m, f"p{p}", f"s{s}", f"2026-10-{s + 10}T00:00:00Z")
    t0 = time.perf_counter()
    assert index.rebuild()["sessions"] == 320
    assert time.perf_counter() - t0 < 3
    t0 = time.perf_counter()
    with index.connect():
        pass
    assert time.perf_counter() - t0 < 0.1
