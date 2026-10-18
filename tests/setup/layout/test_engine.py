"""The layout migration engine on stand-in phases (#548 §7.5, §8, plan R24, R31, R44, R49).

HOME is a temporary directory in every test (root conftest); nothing here reaches a real
home. Phases other than the engine's own are stand-ins that write through engine.put.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from h2t_ops.core import paths, store
from h2t_ops.core.errors import ConfigError, UsageError
from h2t_ops.setup import legacy
from h2t_ops.setup.layout import engine, rollback
from h2t_ops.setup.layout import journal as journal_mod
from h2t_ops.setup.layout.journal import Journal
from h2t_ops.setup.sync import Report


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "m")
    monkeypatch.delenv("DOR_MACHINE_NAME", raising=False)


def _noop(ctx):
    return None


def _funcs(**over):
    table = {p: _noop for p in engine.PHASES}
    table.update(engine._phase_funcs())
    table.update(over)
    return table


def _session(name: str) -> Path:
    return paths.records("sessions", "m") / name


def _migrate(**over) -> Report:
    report = Report()
    engine.migrate(report, funcs=_funcs(**over))
    return report


def _rollback_dirs() -> list[Path]:
    base = paths.run_dir() / "rollback"
    return sorted(base.iterdir()) if base.is_dir() else []


# --- order, resume ------------------------------------------------------------------------

def test_phases_run_in_order_and_mark_done():
    seen = []
    over = {p: (lambda ctx, p=p: seen.append(p)) for p in engine.PHASES
            if p not in ("snapshot", "config_backups", "markers")}
    report = _migrate(**over)
    assert report.failed == []
    assert seen == [p for p in engine.PHASES if p in over]
    j = Journal.latest()
    assert [r["phase"] for r in j.entries() if r["op"] == "phase_done"] == list(engine.PHASES)
    assert j.finished()
    assert json.loads(paths.layout_file().read_text())["layout"] == 1
    again = _migrate(**over)
    assert again.notes == ["layout 1: already"]
    assert seen == [p for p in engine.PHASES if p in over]   # nothing ran twice


def test_interrupted_migration_resumes_without_duplicates():
    """Review Focus 2: a kill between phases resumes at the first unfinished one."""
    calls = {"secrets": 0, "sessions": 0}
    state = {"kill": True}

    def secrets(ctx):
        calls["secrets"] += 1

    def sessions(ctx):
        calls["sessions"] += 1
        engine.put(ctx.journal, _session("a.md"), b"A", place="records.sessions", source="h2t")
        if state["kill"]:
            raise KeyboardInterrupt
        engine.put(ctx.journal, _session("b.md"), b"B", place="records.sessions", source="h2t")

    with pytest.raises(KeyboardInterrupt):
        _migrate(secrets=secrets, sessions=sessions)
    first = Journal.latest()
    assert not first.finished()
    assert first.done_phases() == {"snapshot", "secrets"}
    assert not paths.layout_file().exists()

    state["kill"] = False
    report = _migrate(secrets=secrets, sessions=sessions)
    assert report.failed == []
    assert calls == {"secrets": 1, "sessions": 2}
    assert [j.run_id for j in Journal.all()] == [first.run_id]   # the same journal, resumed
    files = sorted(p.name for p in paths.records("sessions", "m").iterdir())
    assert files == ["a.md", "b.md"]                              # no *.from-*, no second copy
    created = [r["path"] for r in Journal.latest().entries() if r["op"] == "created"]
    assert created.count(str(_session("a.md"))) == 1


def test_put_keeps_both_on_different_hash():
    j = Journal(journal_mod.new_run_id())
    t = _session("s.md")
    assert engine.put(j, t, b"one", place="records.sessions", source="h2t") == t
    assert engine.put(j, t, b"one", place="records.sessions", source="h2t") == t
    alt = engine.put(j, t, b"two", place="records.sessions", source="dor")
    assert alt == t.with_name("s.md.from-dor")
    assert t.read_bytes() == b"one" and alt.read_bytes() == b"two"
    assert engine.put(j, t, b"two", place="records.sessions", source="dor") == alt
    assert sorted(p.name for p in t.parent.iterdir()) == ["s.md", "s.md.from-dor"]
    assert [r["path"] for r in j.entries() if r["op"] == "created"] == [str(t), str(alt)]


def test_kill_after_create_before_created_row(monkeypatch):
    real_create = store.create
    state = {"kill": True}

    def create(path, data, **kw):
        out = real_create(path, data, **kw)
        if state["kill"] and Path(path).name == "a.md":
            raise KeyboardInterrupt
        return out

    monkeypatch.setattr(store, "create", create)

    def sessions(ctx):
        engine.put(ctx.journal, _session("a.md"), b"A", place="records.sessions", source="h2t")

    with pytest.raises(KeyboardInterrupt):
        _migrate(sessions=sessions)
    ops = [(r["op"], Path(r.get("path", "")).name) for r in Journal.latest().entries()]
    assert ("intent", "a.md") in ops and ("created", "a.md") not in ops

    # Rolled back as it is: the intent row is enough to remove the file it names.
    out = rollback.rollback(sync_paused=True)
    assert str(_session("a.md")) in out["removed"]
    assert not _session("a.md").exists()


def test_kill_after_create_then_resume_reconciles(monkeypatch):
    real_create = store.create
    state = {"kill": True}

    def create(path, data, **kw):
        out = real_create(path, data, **kw)
        if state["kill"] and Path(path).name == "a.md":
            state["kill"] = False
            raise KeyboardInterrupt
        return out

    monkeypatch.setattr(store, "create", create)

    def sessions(ctx):
        engine.put(ctx.journal, _session("a.md"), b"A", place="records.sessions", source="h2t")

    with pytest.raises(KeyboardInterrupt):
        _migrate(sessions=sessions)
    assert _migrate(sessions=sessions).failed == []
    rows = Journal.latest().entries()
    assert [r["op"] for r in rows if r.get("path") == str(_session("a.md"))] == ["intent", "created"]
    assert sorted(p.name for p in _session("a.md").parent.iterdir()) == ["a.md"]


def test_journal_rows_are_fsynced(monkeypatch):
    j = Journal(journal_mod.new_run_id())
    j.phase_done("snapshot")            # the directory and file exist before counting
    count = {"n": 0}
    real = os.fsync

    def fsync(fd):
        count["n"] += 1
        real(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    j.intent(_session("a.md"), "records.sessions", "h2t", "0" * 64)
    j.created(_session("a.md"), "records.sessions", "h2t", "0" * 64)
    j.winner("exa.env", "EXA_API_KEY", "1" * 64)
    j.phase_done("secrets")
    assert count["n"] == 4


# --- rollback -----------------------------------------------------------------------------

def test_rollback_removes_only_unchanged_journal_files():
    def sessions(ctx):
        for n in ("a.md", "b.md"):
            engine.put(ctx.journal, _session(n), n.encode(), place="records.sessions", source="h2t")

    assert _migrate(sessions=sessions).failed == []
    _session("b.md").write_bytes(b"edited after the migration")
    _session("later.md").write_bytes(b"written after the migration")
    out = rollback.rollback(sync_paused=True)
    assert not _session("a.md").exists()
    assert _session("b.md").read_bytes() == b"edited after the migration"
    assert _session("later.md").exists()
    assert str(_session("b.md")) in out["kept"]
    assert str(_session("a.md")) in out["removed"]


def test_rollback_restores_a_file_the_migration_extended():
    exa = paths.secrets_shared() / "exa.env"
    exa.parent.mkdir(parents=True)
    exa.write_bytes(b"EXA_API_KEY=fake-exa\n")

    def secrets(ctx):
        engine.put_union(ctx.journal, exa, b"EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                         place="secrets.shared", keys=("EXA_API_KEY", "EXA_X"))

    assert _migrate(secrets=secrets).failed == []
    assert exa.read_bytes() == b"EXA_API_KEY=fake-exa\nEXA_X=fake-x\n"
    out = rollback.rollback(sync_paused=True)
    assert exa.read_bytes() == b"EXA_API_KEY=fake-exa\n"
    assert str(exa) in out["restored"]


def test_rollback_returns_removed_config_backups():
    cfg = paths.config_dir()
    cfg.mkdir(parents=True)
    names = {"domains.yaml.bak": b"d", "repo-mapping.yaml.bak": b"r", "domains.yaml.bak-desc": b"x"}
    for n, b in names.items():
        (cfg / n).write_bytes(b)
    (cfg / "domains.yaml").write_bytes(b"live")
    assert _migrate().failed == []
    assert sorted(p.name for p in cfg.iterdir()) == ["domains.yaml"]
    moved = {p.name.rsplit(".", 1)[0]: p.read_bytes() for p in paths.backups_dir().iterdir()}
    assert moved == names
    rollback.rollback(sync_paused=True)
    assert {p.name: p.read_bytes() for p in cfg.iterdir()} == {**names, "domains.yaml": b"live"}
    assert list(paths.backups_dir().iterdir()) == []


def test_rollback_requires_sync_paused():
    def sessions(ctx):
        engine.put(ctx.journal, _session("a.md"), b"A", place="records.sessions", source="h2t")

    _migrate(sessions=sessions)
    with pytest.raises(UsageError) as exc:
        rollback.rollback(sync_paused=False)
    assert "pause the sync" in str(exc.value)
    assert _session("a.md").exists()


def test_rollback_interrupted_then_rerun(monkeypatch):
    exa = paths.secrets_shared() / "exa.env"
    exa.parent.mkdir(parents=True)
    exa.write_bytes(b"EXA_API_KEY=fake-exa\n")

    def sessions(ctx):
        for n in ("a.md", "b.md", "c.md", "d.md"):
            engine.put(ctx.journal, _session(n), n.encode(), place="records.sessions", source="h2t")
        engine.put_union(ctx.journal, exa, b"EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                         place="secrets.shared", keys=("EXA_API_KEY", "EXA_X"))

    assert _migrate(sessions=sessions).failed == []
    real = store.remove
    count = {"n": 0}

    def remove(path, **kw):
        count["n"] += 1
        if count["n"] == 3:
            raise KeyboardInterrupt
        return real(path, **kw)

    monkeypatch.setattr(store, "remove", remove)
    with pytest.raises(KeyboardInterrupt):
        rollback.rollback(sync_paused=True)
    monkeypatch.setattr(store, "remove", real)
    out = rollback.rollback(sync_paused=True)
    assert out["kept"] == []
    assert not paths.layout_file().exists()
    assert exa.read_bytes() == b"EXA_API_KEY=fake-exa\n"
    assert [p for p in paths.records("sessions", "m").iterdir()] == []


@pytest.mark.parametrize("before", [None, b'{"layout": 0}'])
def test_rollback_restores_layout_json_through_the_journal(before):
    f = paths.layout_file()
    if before is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(before)
    assert _migrate().failed == []
    assert json.loads(f.read_text())["layout"] == 1
    rows = [r for r in Journal.latest().entries() if r.get("path") == str(f)]
    assert {r["op"] for r in rows} == ({"intent", "created"} if before is None else {"replaced"})
    rollback.rollback(sync_paused=True)
    if before is None:
        assert not f.exists()
    else:
        assert f.read_bytes() == before


def test_a_rolled_back_interrupted_migration_is_not_resumed():
    """Resuming it would skip the phases whose files the rollback has just removed."""
    state = {"kill": True}

    def sessions(ctx):
        engine.put(ctx.journal, _session("a.md"), b"A", place="records.sessions", source="h2t")
        if state["kill"]:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _migrate(sessions=sessions)
    first = Journal.latest().run_id
    rollback.rollback(sync_paused=True)
    state["kill"] = False
    seen = []
    assert _migrate(snapshot=lambda ctx: seen.append("snapshot"), sessions=sessions).failed == []
    assert seen == ["snapshot"]                      # a new run, from the first phase
    assert Journal.latest().run_id != first
    assert _session("a.md").read_bytes() == b"A"


def test_resume_keeps_the_machine_the_run_started_with(monkeypatch):
    monkeypatch.setattr(legacy, "ensure_machine_name",
                        lambda *, name="": {"status": "written", "path": "s", "value": name})
    state = {"kill": True}
    seen = []

    def sessions(ctx):
        seen.append(ctx.machine)
        if state["kill"]:
            raise KeyboardInterrupt

    report = Report()
    with pytest.raises(KeyboardInterrupt):
        engine.migrate(report, machine="pinned", funcs=_funcs(sessions=sessions))
    state["kill"] = False
    other = Report()
    engine.migrate(other, machine="different", funcs=_funcs(sessions=sessions))
    assert [s for s, _ in other.failed] == ["layout 1: snapshot"]
    assert "'pinned'" in other.failed[0][1]
    again = Report()
    engine.migrate(again, funcs=_funcs(sessions=sessions))    # H2T_MACHINE_NAME is "m"
    assert again.failed == []
    assert seen == ["pinned", "pinned"]
    assert json.loads(paths.layout_file().read_text())["machine"] == "pinned"


# --- machine name -------------------------------------------------------------------------

def test_machine_name_ambiguity_stops(monkeypatch):
    monkeypatch.delenv("H2T_MACHINE_NAME")
    monkeypatch.setattr("platform.node", lambda: "other")
    (paths.legacy("sessions.h2t") / "automata").mkdir(parents=True)
    (paths.legacy("sessions.dor") / "macbook-pro-3").mkdir(parents=True)
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: snapshot"]
    remedy = report.failed[0][1]
    assert "automata" in remedy and "macbook-pro-3" in remedy
    assert "h2t-setup layout migrate --machine" in remedy
    assert not paths.layout_file().exists()


def test_machine_flag_pins_the_name_once(monkeypatch):
    calls = []

    def ensure(*, name=""):
        calls.append(name)
        return {"status": "written", "path": "settings.json", "value": name}

    monkeypatch.setattr(legacy, "ensure_machine_name", ensure)
    report = Report()
    engine.migrate(report, machine="m", funcs=_funcs())
    assert report.failed == []
    assert calls == ["m"]
    assert json.loads(paths.layout_file().read_text())["machine"] == "m"


def test_machine_flag_stops_on_a_different_pinned_name(monkeypatch):
    settings = paths.dir_of("harness") / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {"H2T_MACHINE_NAME": "other"}}), encoding="utf-8")
    before = settings.read_bytes()
    report = Report()
    engine.migrate(report, machine="m", funcs=_funcs())
    assert [s for s, _ in report.failed] == ["layout 1: snapshot"]
    assert "`other`" in report.failed[0][1] and "without --machine" in report.failed[0][1]
    assert settings.read_bytes() == before
    assert not paths.layout_file().exists()


@pytest.mark.parametrize("machine", ["m", None])
def test_machine_explicit_is_carried(monkeypatch, machine):
    calls, seen = [], []
    monkeypatch.setattr(legacy, "ensure_machine_name",
                        lambda *, name="": calls.append(name) or {"status": "written", "value": name})

    def snapshot(ctx):
        seen.append((ctx.machine, ctx.machine_explicit))
        engine.phase_snapshot(ctx)

    report = Report()
    engine.migrate(report, machine=machine, funcs=_funcs(snapshot=snapshot))
    assert report.failed == []
    assert seen == [("m", machine is not None)]
    assert calls == (["m"] if machine else [])


# --- the journal directory ----------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_rollback_dir_is_0700():
    _migrate()
    (d,) = _rollback_dirs()
    assert d.name.startswith("layout1-")
    assert d.stat().st_mode & 0o777 == 0o700


def _age(p: Path, days: int) -> None:
    t = time.time() - days * 86400
    os.utime(p, (t, t))


def test_old_finished_rollback_dirs_are_pruned_after_30_days():
    base = paths.run_dir() / "rollback"
    assert _migrate().failed == []
    (old,) = _rollback_dirs()
    _age(old / "journal.jsonl", 31)
    snap = base / "20260901T000000Z"
    snap.mkdir()
    (snap / "claude.json").write_text("{}")
    _age(snap, 31)
    pending = base / "claude-pending.json"
    pending.write_text("{}")
    _age(pending, 31)
    paths.layout_file().unlink()        # so the next run migrates again and prunes first
    assert _migrate().failed == []
    left = {p.name for p in _rollback_dirs()}
    assert old.name not in left
    assert {"20260901T000000Z", "claude-pending.json"} <= left

    # An unfinished journal of the same age is never removed.
    stale = Journal("layout1-20200101T000000000000Z")
    stale.phase_done("snapshot")
    _age(stale.file, 31)
    assert journal_mod.prune() == []
    assert stale.file.is_file()


def test_latest_ignores_sync_snapshots():
    assert _migrate().failed == []
    (mine,) = _rollback_dirs()
    newer = paths.run_dir() / "rollback" / "20991231T000000000000Z"
    newer.mkdir()
    (newer / "claude.json").write_text("{}")
    (paths.run_dir() / "rollback" / "claude-pending.json").write_text("{}")
    assert Journal.latest().run_id == mine.name


# --- the table ----------------------------------------------------------------------------

def test_missing_phase_function_fails_before_any_write():
    table = _funcs()
    del table["secrets"]
    report = Report()
    engine.migrate(report, funcs=table)
    assert [s for s, _ in report.failed] == ["layout 1: secrets is not implemented"]
    assert not (paths.run_dir() / "rollback").exists()
    assert not paths.layout_file().exists()


def test_engine_owned_phases_are_in_the_table():
    assert {"snapshot", "config_backups", "markers"} <= set(engine._phase_funcs())
    assert set(engine._phase_funcs()) <= set(engine.PHASES)


# --- journal rows -------------------------------------------------------------------------

def test_journal_rows_have_the_r31_shape(tmp_path):
    j = Journal(journal_mod.new_run_id())
    src = tmp_path / "tokens.json"
    j.winner("exa.env", "EXA_API_KEY", "a" * 64)
    j.baseline({("EXA_API_KEY", "a" * 64), ("EXA_X", "b" * 64)})
    j.created(_session("t.json"), "records.sessions", "store", "c" * 64,
              source_path=src, rule="google-durable")
    j.phase_done("secrets")
    assert j.entries() == [
        {"op": "winner", "target": "exa.env", "key": "EXA_API_KEY", "sha256": "a" * 64},
        {"op": "baseline", "key": "EXA_API_KEY", "sha256": "a" * 64},
        {"op": "baseline", "key": "EXA_X", "sha256": "b" * 64},
        {"op": "created", "path": str(_session("t.json")), "place": "records.sessions",
         "source": "store", "sha256": "c" * 64, "source_path": str(src), "rule": "google-durable"},
        {"op": "phase_done", "phase": "secrets"},
    ]


def test_replaced_and_removed_persist_previous_bytes():
    j = Journal(journal_mod.new_run_id())
    a = j.replaced(_session("x.md"), "records.sessions", b"old", "d" * 64)
    b = j.removed(_session("y.md"), "records.sessions", b"gone")
    assert a != b and a.startswith("prev/") and b.startswith("prev/")
    assert j.prev_bytes(a) == b"old" and j.prev_bytes(b) == b"gone"
    assert (j.dir / a).read_bytes() == b"old"
    if sys.platform != "win32":
        assert (j.dir / a).stat().st_mode & 0o777 == 0o600
        assert (j.dir / b).stat().st_mode & 0o777 == 0o600
    rows = j.entries()
    assert rows[0] == {"op": "replaced", "path": str(_session("x.md")), "place": "records.sessions",
                       "prev_sha": store.sha256(b"old"), "new_sha": "d" * 64, "prev": a}
    assert rows[1] == {"op": "removed", "path": str(_session("y.md")), "place": "records.sessions",
                       "prev_sha": store.sha256(b"gone"), "prev": b}


# --- quiet sqlite -------------------------------------------------------------------------

def test_quiet_sqlite_bytes_stops_on_sidecar_and_on_change(tmp_path):
    db = tmp_path / "session.session"
    db.write_bytes(b"SQLite format 3\x00fake")
    assert engine.quiet_sqlite_bytes(db) == b"SQLite format 3\x00fake"

    def touching(p):
        data = p.read_bytes()
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        return data

    with pytest.raises(ConfigError) as exc:
        engine.quiet_sqlite_bytes(db, read=touching)
    assert "changed while" in str(exc.value) and "Telegram" in exc.value.hint
    assert "h2t-setup layout migrate" in exc.value.hint

    (tmp_path / "session.session-wal").write_bytes(b"")
    with pytest.raises(ConfigError) as exc:
        engine.quiet_sqlite_bytes(db)
    assert "-wal" in str(exc.value)


# --- markers ------------------------------------------------------------------------------

def test_markers_go_into_old_directories_only(monkeypatch):
    old = paths.legacy("sessions.h2t") / "m"
    old.mkdir(parents=True)
    (old / "s.md").write_bytes(b"S")
    lake = paths.legacy("lake.dor")
    (lake / "_cursors").mkdir(parents=True)
    (lake / "_cursors" / "c.json").write_bytes(b"{}")
    cfg = paths.config_dir()
    cfg.mkdir(parents=True)
    (cfg / "paths.yaml").write_text(f"places:\n  lake: {lake}\n", encoding="utf-8")

    def sessions(ctx):
        engine.put(ctx.journal, _session("s.md"), b"S", place="records.sessions", source="h2t",
                   source_path=old / "s.md")
        engine.put(ctx.journal, paths.state_dir() / "cursors" / "c.json", b"{}", place="state",
                   source="lake", source_path=lake / "_cursors" / "c.json")

    assert _migrate(sessions=sessions).failed == []
    marker = paths.legacy("sessions.h2t") / "MOVED-TO.txt"
    assert str(paths.records("sessions", "m")) in marker.read_text()
    assert not (lake / "MOVED-TO.txt").exists() and not (lake / "_cursors" / "MOVED-TO.txt").exists()
    assert not (paths.home() / ".dor" / "MOVED-TO.txt").exists()
    assert (old / "s.md").read_bytes() == b"S"      # the old file is left as it was
    rollback.rollback(sync_paused=True)
    assert not marker.exists()
    assert (old / "s.md").read_bytes() == b"S"


def test_markers_for_same_hash_and_merged_sources():
    """A target already there with the same bytes writes no file row, and a merged file has
    no single source_path; both still mark the old directories they were read from."""
    same = paths.legacy("sessions.dor") / "m"
    same.mkdir(parents=True)
    (same / "s.md").write_bytes(b"S")
    _session("s.md").parent.mkdir(parents=True)
    _session("s.md").write_bytes(b"S")              # e.g. delivered by sync from a peer
    a = paths.legacy("secrets.h2t") / "secrets.env"
    b = paths.legacy("secrets.dor")
    c = paths.legacy("secrets.dor_old")             # ~/.dor/secrets.env: only put_union reads it
    for p in (a, b, c):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"EXA_API_KEY=fake-exa\n")
    exa = paths.secrets_shared() / "exa.env"
    exa.parent.mkdir(parents=True)
    exa.write_bytes(b"EXA_API_KEY=fake-exa\n")

    def secrets(ctx):
        engine.put(ctx.journal, paths.secrets_shared() / "other.env", b"X=fake-x\n",
                   place="secrets.shared", source="ladder", sources=(a, b))
        engine.put_union(ctx.journal, exa, b"EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                         place="secrets.shared", keys=("EXA_API_KEY", "EXA_X"), sources=(c,))

    def sessions(ctx):
        engine.put(ctx.journal, _session("s.md"), b"S", place="records.sessions", source="dor",
                   source_path=same / "s.md")

    assert _migrate(secrets=secrets, sessions=sessions).failed == []
    assert not [r for r in Journal.latest().entries()
                if r.get("path") == str(_session("s.md"))]   # no file row: it was there
    for d in (paths.legacy("sessions.dor"), a.parent, b.parent, c.parent):
        assert (d / "MOVED-TO.txt").is_file(), d
    assert str(paths.secrets_shared()) in (b.parent / "MOVED-TO.txt").read_text()


def test_a_failed_create_leaves_its_old_dir_unmarked(monkeypatch):
    """The source row precedes the create; a create that failed and was not redone on resume
    must not put MOVED-TO.txt next to an original that was never copied."""
    lost = paths.legacy("sessions.dor") / "m"
    lost.mkdir(parents=True)
    (lost / "s.md").write_bytes(b"S")
    fine = paths.legacy("sessions.h2t") / "m"
    fine.mkdir(parents=True)
    (fine / "t.md").write_bytes(b"T")
    real_create = store.create

    def create(path, data, **kw):
        if Path(path).name == "s.md":
            raise OSError("disk went away")
        return real_create(path, data, **kw)

    def secrets(ctx):
        engine.put(ctx.journal, _session("t.md"), b"T", place="records.sessions", source="h2t",
                   source_path=fine / "t.md")

    def sessions(ctx):
        engine.put(ctx.journal, _session("s.md"), b"S", place="records.sessions", source="dor",
                   source_path=lost / "s.md")

    monkeypatch.setattr(store, "create", create)
    assert [s for s, _ in _migrate(secrets=secrets, sessions=sessions).failed] == ["layout 1: sessions"]
    monkeypatch.setattr(store, "create", real_create)
    report = _migrate(secrets=secrets, sessions=_noop)      # the resume does not re-put it
    assert report.failed == []
    assert not (paths.legacy("sessions.dor") / "MOVED-TO.txt").exists()
    assert (paths.legacy("sessions.h2t") / "MOVED-TO.txt").is_file()
    assert any(str(paths.legacy("sessions.dor")) in n for n in report.notes)


def test_a_held_lock_stops_migrate_and_rollback():
    with store.locked(paths.run_dir() / "layout.lock", place="run"):
        with pytest.raises(ConfigError) as exc:
            _migrate()
        assert "another layout migration or rollback is running" in str(exc.value)
        with pytest.raises(ConfigError):
            rollback.rollback(sync_paused=True)
    assert not (paths.run_dir() / "rollback").exists()
    assert not paths.layout_file().exists()
    assert _migrate().failed == []                  # free again


def test_interrupted_rollback_blocks_migrate_until_finished(monkeypatch):
    exa = paths.secrets_shared() / "exa.env"
    exa.parent.mkdir(parents=True)
    exa.write_bytes(b"EXA_API_KEY=fake-exa\n")

    def sessions(ctx):
        for n in ("a.md", "b.md", "c.md"):
            engine.put(ctx.journal, _session(n), n.encode(), place="records.sessions", source="h2t")
        engine.put_union(ctx.journal, exa, b"EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                         place="secrets.shared", keys=("EXA_API_KEY", "EXA_X"))

    assert _migrate(sessions=sessions).failed == []
    a = Journal.latest().run_id
    real, count = store.remove, {"n": 0}

    def remove(path, **kw):
        count["n"] += 1
        if count["n"] == 2:                         # layout.json is gone, the sessions not
            raise KeyboardInterrupt
        return real(path, **kw)

    monkeypatch.setattr(store, "remove", remove)
    with pytest.raises(KeyboardInterrupt):
        rollback.rollback(sync_paused=True)
    monkeypatch.setattr(store, "remove", real)
    assert not paths.layout_file().exists()

    with pytest.raises(ConfigError) as exc:
        _migrate(sessions=sessions)
    assert "rollback --sync-paused" in exc.value.hint
    assert [j.run_id for j in Journal.all()] == [a]  # nothing new was started

    # Even with a newer finished journal beside it (another machine's, a manual copy),
    # rollback takes up the half-done one.
    newer = Journal("layout1-29991231T000000000000Z")
    newer.phase_done("markers")
    out = rollback.rollback(sync_paused=True)
    assert out["journal"].endswith(a) and out["kept"] == []
    assert list(paths.records("sessions", "m").iterdir()) == []
    assert exa.read_bytes() == b"EXA_API_KEY=fake-exa\n"
    assert not Journal.latest().rollback_pending()


def test_a_torn_row_does_not_block_the_journal():
    j = Journal(journal_mod.new_run_id())
    j.phase_done("snapshot")
    with open(j.file, "ab") as fh:                  # a kill mid-row, cut inside a character
        fh.write('{"op": "phase_done", "phase": "sé'.encode()[:-1])
    assert j.done_phases() == {"snapshot"}
    j.phase_done("secrets")                         # the next append after the resume
    j.phase_done("sessions")
    assert j.done_phases() == {"snapshot", "secrets", "sessions"}
    assert [r["op"] for r in j.entries()] == ["phase_done"] * 3


@pytest.mark.parametrize("tail", [
    b'{"op": "phase_done", "pha\n',                          # the repair kept only its newline
    b'{"op": "phase_done", "pha\n{"op": "tor',               # the repair cut mid-marker
])
def test_a_torn_repair_does_not_block_the_journal(tail):
    j = Journal(journal_mod.new_run_id())
    j.phase_done("snapshot")
    with open(j.file, "ab") as fh:
        fh.write(tail)
    assert j.done_phases() == {"snapshot"}
    j.phase_done("secrets")
    j.phase_done("sessions")
    assert j.done_phases() == {"snapshot", "secrets", "sessions"}


def test_damage_a_kill_cannot_leave_is_an_error_that_keeps_the_journal():
    j = Journal(journal_mod.new_run_id())
    j.phase_done("snapshot")
    with open(j.file, "ab") as fh:
        fh.write(b"garbage\n")
        fh.write(json.dumps({"op": "phase_done", "phase": "secrets"}).encode() + b"\n")
    with pytest.raises(ConfigError) as exc:
        j.entries()
    assert "line 2" in str(exc.value)
    assert "remove" not in exc.value.hint and "keep this directory" in exc.value.hint


def test_pinned_name_without_flag_stops(monkeypatch):
    """R4: outside Claude the pin is not in the env; it is read from the settings."""
    settings = paths.dir_of("harness") / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"env": {"H2T_MACHINE_NAME": "automata"}}), encoding="utf-8")
    report = _migrate()                             # this process sees H2T_MACHINE_NAME=m
    assert [s for s, _ in report.failed] == ["layout 1: snapshot"]
    assert "--machine automata" in report.failed[0][1]
    assert not paths.layout_file().exists()
    monkeypatch.setenv("H2T_MACHINE_NAME", "automata")
    assert _migrate().failed == []
