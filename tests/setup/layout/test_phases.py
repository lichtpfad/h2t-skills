"""Layout 1, the phases after `secrets` (#548 §8 п. 3–6, §12; plan R2, R9, R15, R22, R25).

HOME is a temporary directory in every test (root conftest); the 3.x homes here are built
from fake records and fake values only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import ConfigError
from h2t_ops.lifecycle import session_record
from h2t_ops.setup import storage_doctor
from h2t_ops.setup.layout import engine, phases, rollback, verify
from h2t_ops.setup.layout import journal as journal_mod
from h2t_ops.setup.layout.journal import Journal
from h2t_ops.setup.sync import Report

M = "macbook-pro-3"
_KEYS = ("EXA_API_KEY", "MEETGEEK_API_KEY", "NOTION_API_TOKEN", "TELEGRAM_API_ID",
         "TELEGRAM_API_HASH", "H2T_EVALS_TOKEN", "JINA_API_KEY")


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", M)
    monkeypatch.delenv("DOR_MACHINE_NAME", raising=False)
    for k in (*paths.OLD_ENV, *_KEYS):
        monkeypatch.delenv(k, raising=False)


def _write(p: Path, data: str | bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
    return p


def _ctx() -> engine.PhaseContext:
    return engine.PhaseContext(journal=Journal(journal_mod.new_run_id()), machine=M,
                               machine_explicit=False, report=Report())


def _migrate(machine: str | None = None) -> Report:
    report = Report()
    engine.migrate(report, machine=machine)
    return report


def _md(stem: str, *, date="2026-08-22", domain="dev", project="h2t-skills", text="done") -> str:
    return (f"# Session: {stem}\n\n- **Date:** {date}\n- **Domain:** {domain}\n"
            f"- **Project:** {project}\n\n## What was done\n{text}\n")


def _row(sid: str, project: str = "h2t-skills", event: str = "session.start") -> str:
    return json.dumps({"event": event, "session_id": sid, "project": project,
                       "ts": "2026-08-22T10:00:00Z"})


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --- sessions ------------------------------------------------------------------------------

def _old_session(key: str, machine: str, project: str, stem: str, body: str) -> Path:
    return _write(paths.legacy(key) / machine / project / f"{stem}.md", body)


def test_session_frontmatter_from_latest_json_and_header():
    src = _old_session("sessions.h2t", M, "h2t-skills", "s1", _md("s1", project="other-name"))
    _write(src.parent / "latest.json", json.dumps({
        "session_id": "s1", "updated_at": "2026-08-22T18:00:00+00:00",
        "summary_short": "fake summary", "next_actions": ["fake next"],
        "artifacts": [{"type": "commit", "ref": "abc123"}]}))
    old = _old_session("sessions.h2t", M, "h2t-skills", "s0", _md("s0", date="2026-08-20"))
    ctx = _ctx()
    phases.phase_sessions(ctx)
    meta, body = session_record.parse(session_record.session_path(M, "h2t-skills", "s1").read_bytes())
    assert body == src.read_bytes()
    assert meta == {"session_id": "s1", "machine": M, "project": "h2t-skills", "domain": "dev",
                    "date": "2026-08-22", "updated_at": "2026-08-22T18:00:00+00:00",
                    "done": "fake summary", "remains": ["fake next"],
                    "artifacts": [{"type": "commit", "ref": "abc123"}],
                    "migrated_from": f"{src}@{_sha(src)}"}
    # latest.json names s1, so s0 takes its date: no done, no remains
    meta0, _ = session_record.parse(session_record.session_path(M, "h2t-skills", "s0").read_bytes())
    assert meta0["updated_at"] == "2026-08-20T00:00:00Z" and "done" not in meta0
    assert meta0["migrated_from"] == f"{old}@{_sha(old)}"
    assert verify.verify_transformed(ctx.journal) == []


def test_session_without_a_date_takes_the_mtime():
    src = _old_session("sessions.dor", M, "p", "nodate", "# Session: nodate\n\nfake text\n")
    os.utime(src, (1700000000, 1700000000))
    phases.phase_sessions(_ctx())
    meta, _ = session_record.parse(session_record.session_path(M, "p", "nodate").read_bytes())
    assert meta["updated_at"] == "2023-11-14T22:13:20Z" and "date" not in meta


def test_same_body_in_both_session_dirs_is_one_file():
    body = _md("s1")
    a = _old_session("sessions.h2t", M, "h2t-skills", "s1", body)
    b = _old_session("sessions.dor", M, "h2t-skills", "s1", body)
    ctx = _ctx()
    phases.phase_sessions(ctx)
    leaf = paths.records("sessions", M) / "h2t-skills"
    assert sorted(p.name for p in leaf.iterdir()) == ["s1.md"]
    # both old files point at it, so MOVED-TO.txt reaches both old directories
    target = str(leaf / "s1.md")
    olds = {r["old"] for r in ctx.journal.entries() if r["op"] == "source" and r["new"] == target}
    assert olds == {str(a), str(b)}


def test_different_bodies_keep_both_as_from_dor():
    _old_session("sessions.h2t", M, "h2t-skills", "s1", _md("s1", text="fake h2t"))
    b = _old_session("sessions.dor", M, "h2t-skills", "s1", _md("s1", text="fake dor"))
    ctx = _ctx()
    phases.phase_sessions(ctx)
    leaf = paths.records("sessions", M) / "h2t-skills"
    assert sorted(p.name for p in leaf.iterdir()) == ["s1.md", "s1.md.from-dor"]
    assert session_record.parse((leaf / "s1.md.from-dor").read_bytes())[1] == b.read_bytes()
    phases.phase_sessions(ctx)                       # a resume adds nothing
    assert sorted(p.name for p in leaf.iterdir()) == ["s1.md", "s1.md.from-dor"]
    assert verify.verify_transformed(ctx.journal) == []


def test_other_machines_sessions_are_not_copied():
    _old_session("sessions.dor", "automata", "pos", "a1", _md("a1"))
    phases.phase_sessions(_ctx())
    assert not paths.records("sessions").exists()


def test_session_body_rule_catches_an_edited_body():
    _old_session("sessions.h2t", M, "p", "s1", _md("s1"))
    ctx = _ctx()
    phases.phase_sessions(ctx)
    target = session_record.session_path(M, "p", "s1")
    with open(target, "ab") as fh:
        fh.write(b"x")
    assert verify.verify_transformed(ctx.journal) == [f"{target}: its body is not "
                                                       f"{paths.legacy('sessions.h2t') / M / 'p' / 's1.md'}"]


# --- activity ------------------------------------------------------------------------------

def _spool() -> Path:
    return paths.legacy("activity") / "spool.jsonl"


def test_activity_drops_pytest_rows_and_counts_them():
    real = [_row(f"real-{n}") for n in range(5)]
    junk = [_row(sid) for sid in sorted(phases.PYTEST_SESSION_IDS)[:2]] + [_row("x", "explicit-id")]
    _write(_spool(), "\n".join([real[0], junk[0], real[1], real[2], junk[1], real[3], junk[2], real[4]]) + "\n")
    ctx = _ctx()
    phases.phase_activity(ctx)
    copy = paths.activity_file(M)
    assert copy.read_text().splitlines() == real
    assert "layout 1: activity: 3 test rows skipped" in ctx.report.notes


def test_activity_copy_verified_by_rule():
    _write(_spool(), "\n".join([_row("real-1"), _row("some-session-2026-08-23"), _row("real-2")]))
    ctx = _ctx()
    phases.phase_activity(ctx)
    copy = paths.activity_file(M)
    assert verify.verify_transformed(ctx.journal) == []
    want = [f"{copy}: is not the filtered {_spool()}"]
    # a row a 4.0 session appends is not a mismatch (live rows may follow the legacy part) ...
    store.append(copy, _row("live-1"), place="records.activity")
    assert verify.verify_transformed(ctx.journal) == []
    # ... a test row in the file is, and so is a legacy row gone from it
    store.append(copy, _row("some-session-2026-08-23"), place="records.activity")
    assert verify.verify_transformed(ctx.journal) == want
    copy.write_text(_row("real-2") + "\n" + _row("live-1") + "\n")
    assert verify.verify_transformed(ctx.journal) == want


def test_activity_merges_with_live_rows_and_never_rewrites_them():
    """Sessions since 4.0 append to records/activity/<machine>.jsonl: the legacy rows it lacks
    go before them, a row in both is kept once, and the live bytes are untouched."""
    _write(_spool(), "\n".join([_row("old-1"), _row("both"), _row("dev-docgraph-topic-2026-08-22")]) + "\n")
    live = (_row("both") + "\n" + _row("live-1") + "\n").encode()
    copy = _write(paths.activity_file(M), live)
    ctx = _ctx()
    phases.phase_activity(ctx)
    data = copy.read_bytes()
    assert data == (_row("old-1") + "\n").encode() + live
    assert verify.verify_transformed(ctx.journal) == []
    rows = [r for r in ctx.journal.entries() if r["op"] == "replaced"]
    assert [(r["rule"], r["source_path"]) for r in rows] == [("activity-filter", str(_spool()))]
    phases.phase_activity(ctx)                       # a resume finds nothing to add
    assert copy.read_bytes() == data
    assert len([r for r in ctx.journal.entries() if r["op"] == "replaced"]) == 1


def test_activity_rows_compare_without_their_line_endings():
    """A 3.x spool written on Windows has CRLF rows; store.append writes LF. One row in both
    is one row: the merge keeps it once, and a test row appended in LF is still caught."""
    test_row = _row("some-session-2026-08-23")
    _write(_spool(), ("\r\n".join([_row("old-1"), _row("both"), test_row]) + "\r\n").encode())
    live = (_row("both") + "\n").encode()
    copy = _write(paths.activity_file(M), live)
    ctx = _ctx()
    phases.phase_activity(ctx)
    assert copy.read_bytes() == (_row("old-1") + "\r\n").encode() + live   # bytes kept as they were
    assert verify.verify_transformed(ctx.journal) == []
    store.append(copy, test_row, place="records.activity")
    assert verify.verify_transformed(ctx.journal) == [f"{copy}: is not the filtered {_spool()}"]


def test_an_append_during_the_merge_lands_in_the_merged_file(monkeypatch):
    """A live session appends between the merge's last check and its publication (the gap
    replace(expect=) leaves). The append waits on the merge lock and lands in the published
    file; without the lock it lands in the inode os.replace discards."""
    import threading
    _write(_spool(), _row("old-1") + "\n")
    copy = _write(paths.activity_file(M), _row("live-1") + "\n")
    real, threads = os.replace, []

    def replace(src, dst, *a, **kw):
        if Path(dst) == copy and not threads:
            t = threading.Thread(target=store.append, args=(copy, _row("live-2")),
                                 kwargs={"place": "records.activity"})
            threads.append(t)
            t.start()
            t.join(0.5)                 # blocked on the lock, or already written to the old inode
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(store.os, "replace", replace)
    phases.phase_activity(_ctx())
    threads[0].join(5)
    assert copy.read_text().splitlines() == [_row("old-1"), _row("live-1"), _row("live-2")]


# --- evals ---------------------------------------------------------------------------------

_DB = b"SQLite format 3\x00fake-evals-spool"


def _default_spool() -> Path:
    return paths.legacy("evals") / ".h2t_evals_spool.db"


def test_evals_spool_is_a_byte_copy_verified_by_hash():
    src = _write(_default_spool(), _DB)
    run = _write(paths.legacy("evals") / "handoff" / "sessions" / "r1.json", '{"fake": 1}')
    ctx = _ctx()
    phases.phase_evals(ctx)
    copy = paths.evals_spool()
    assert copy.read_bytes() == _DB
    assert (paths.records("evals", M) / "handoff" / "r1.json").read_bytes() == run.read_bytes()
    row = next(r for r in ctx.journal.entries() if r["op"] == "created" and r["path"] == str(copy))
    assert row["source_path"] == str(src) and "rule" not in row
    assert verify.verify_copies(ctx.journal) == []
    with open(copy, "ab") as fh:
        fh.write(b"x")
    assert verify.verify_copies(ctx.journal) == [f"copy {copy} does not match its journal hash"]


def test_evals_spool_with_a_sidecar_stops():
    _write(_default_spool(), _DB)
    _write(paths.legacy("evals") / ".h2t_evals_spool.db-wal", b"")
    _write(paths.legacy("evals") / "handoff" / "sessions" / "r1.json", '{"fake": 1}')
    with pytest.raises(ConfigError) as ei:
        phases.phase_evals(_ctx())
    assert "close the evals process (a Claude session with evals on)" in ei.value.hint
    assert "h2t-setup layout migrate" in ei.value.hint
    assert not paths.evals_spool().exists()
    assert not paths.records("evals").exists()       # nothing written before the stop


def test_evals_spool_changed_during_copy_stops(monkeypatch):
    src = _write(_default_spool(), _DB)
    real = phases._read_spool

    def touching(p):
        data = real(p)
        st = os.stat(src)
        os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        return data

    monkeypatch.setattr(phases, "_read_spool", touching)
    with pytest.raises(ConfigError) as ei:
        phases.phase_evals(_ctx())
    assert "changed while it was being read" in str(ei.value)
    assert "close the evals process" in ei.value.hint
    assert not paths.evals_spool().exists()


@pytest.mark.parametrize("where", ["dor-file", "environment"])
def test_evals_spool_path_from_the_old_secrets_file(where, monkeypatch, tmp_path):
    """R22: H2T_EVALS_SPOOL from the environment, else from the secret files (~/.dor/secrets.env
    first), else the default — 3.x read it from its environment over that file."""
    _write(_default_spool(), b"SQLite format 3\x00fake-default-spool")
    custom = _write(tmp_path / "elsewhere" / "spool.db", _DB)
    other = _write(tmp_path / "elsewhere" / "other.db", b"SQLite format 3\x00fake-other")
    name = next(n for n, u in paths.OLD_ENV.items() if u == "evals-spool-source")
    _write(paths.legacy("secrets.h2t") / "secrets.env", f"{name}={other}\n")
    if where == "dor-file":
        _write(paths.legacy("secrets.dor_old"), f"{name}={custom}\n")
    else:
        _write(paths.legacy("secrets.dor_old"), f"{name}={other}\n")
        monkeypatch.setenv(name, str(custom))
    ctx = _ctx()
    phases.phase_evals(ctx)
    assert paths.evals_spool().read_bytes() == _DB
    assert verify.verify_copies(ctx.journal) == []


# --- byte copies ---------------------------------------------------------------------------

def test_telegram_cursors_registry_and_data_are_byte_copies():
    olds = {
        paths.legacy("telegram") / "dialogs_bootstrapped": paths.state_dir() / "telegram" / "dialogs_bootstrapped",
        paths.legacy("lake.dor") / "_cursors" / "granola.json": paths.state_dir() / "cursors" / "granola.json",
        paths.legacy("lake.dor") / "_cursors" / "meetgeek.json": paths.state_dir() / "cursors" / "meetgeek.json",
        paths.legacy("registry.dor"): paths.records("imports") / "dor-registry.jsonl",
        paths.legacy("research") / "q" / "r.json": paths.data_dir() / "research" / "q" / "r.json",
        paths.legacy("creative") / "p1" / "DESIGN.md": paths.data_dir() / "creative" / "profiles" / "p1" / "DESIGN.md",
    }
    for n, src in enumerate(olds):
        _write(src, f"fake-{n}")
    _write(paths.legacy("telegram") / "mentions_cache.json", "{}")   # not moved (§8 п. 4)
    ctx = _ctx()
    for phase in (phases.phase_telegram, phases.phase_cursors, phases.phase_registry, phases.phase_data):
        phase(ctx)
    for src, dst in olds.items():
        assert dst.read_bytes() == src.read_bytes(), dst
    assert sorted(p.name for p in (paths.state_dir() / "telegram").iterdir()) == ["dialogs_bootstrapped"]
    assert verify.verify_copies(ctx.journal) == []


# --- paths.yaml ----------------------------------------------------------------------------

def test_paths_yaml_takes_lake_from_old_variable_and_never_writes_vault(monkeypatch, tmp_path):
    lake = tmp_path / "my-lake"
    lake.mkdir()
    (paths.legacy("lake.dor")).mkdir(parents=True)       # the old variable wins over it (R2)
    paths.legacy("downloads").mkdir(parents=True)
    monkeypatch.setenv(next(n for n, u in paths.OLD_ENV.items() if u == "lake"), str(lake))
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "vault"))
    phases.phase_paths_yaml(_ctx())
    doc = yaml.safe_load(paths.paths_yaml().read_text())
    assert doc == {"version": 1, "places": {"lake": str(lake), "inbox": "~/Downloads"}}
    assert paths.paths_config().places == {"lake": lake, "inbox": paths.legacy("downloads")}


def test_paths_yaml_falls_back_to_dor_lake_and_keeps_a_users_file():
    paths.legacy("lake.dor").mkdir(parents=True)
    phases.phase_paths_yaml(_ctx())
    assert yaml.safe_load(paths.paths_yaml().read_text()) == {
        "version": 1, "places": {"lake": "~/.dor/lake"}}
    mine = "version: 1\nplaces: {}\n"
    paths.paths_yaml().write_text(mine)
    phases.phase_paths_yaml(_ctx())
    assert paths.paths_yaml().read_text() == mine


def test_paths_yaml_reads_the_same_on_another_home(monkeypatch, tmp_path):
    """config/ syncs: the file one machine writes must validate on the next — another user
    name, a Windows home — and name that machine's own lake and inbox."""
    import ntpath
    from pathlib import PureWindowsPath
    paths.legacy("lake.dor").mkdir(parents=True)
    paths.legacy("downloads").mkdir(parents=True)
    phases.phase_paths_yaml(_ctx())
    text = paths.paths_yaml().read_text()
    assert str(paths.home()) not in text
    doc = yaml.safe_load(text)
    monkeypatch.setenv("USERPROFILE", r"C:\Users\other")
    for value in doc["places"].values():
        assert PureWindowsPath(ntpath.expanduser(value)).is_absolute(), value
    other = tmp_path / "other-home"
    other.mkdir()
    monkeypatch.setenv("HOME", str(other))
    got = paths.validate_config(doc, source=paths.paths_yaml()).places
    assert got == {"lake": other / ".dor" / "lake", "inbox": other / "Downloads"}


# --- index ---------------------------------------------------------------------------------

def _record(machine: str, project: str, sid: str) -> Path:
    meta = {"session_id": sid, "machine": machine, "project": project, "updated_at": "2026-10-01T00:00:00Z"}
    return _write(session_record.session_path(machine, project, sid),
                  session_record.render(meta, b"fake body\n"))


def test_index_count_includes_sessions_already_in_records():
    """A Task 13 record of this machine and a synced md of another one are there before the
    migration: the index holds them too, and a broken md is a problem, not a session."""
    _record(M, "h2t-skills", "written-by-4-0")
    _record("automata", "pos", "synced-from-automata")
    _write(paths.records("sessions", "automata") / "pos" / "broken.md", "no frontmatter\n")
    _write(paths.records("sessions", "automata") / "pos" / "c.md.from-dor", "skipped by the index\n")
    _old_session("sessions.h2t", M, "h2t-skills", "s1", _md("s1"))
    report = _migrate()
    assert report.failed == [], report.failed
    assert "layout 1: index: 1 session md unreadable, see h2t-ops index query" in report.notes


def test_index_phase_stops_when_the_index_misses_a_session(monkeypatch):
    _record(M, "p", "s1")
    from h2t_ops.lifecycle.index import build

    def unreadable(f, leaf):
        raise ValueError("fake: the index could not read it")

    monkeypatch.setattr(build, "_session_row", unreadable)    # an index that drops a session
    with pytest.raises(engine.PhaseFailed) as ei:
        phases.phase_index(_ctx())
    assert "the index holds 0 sessions" in str(ei.value)


@pytest.mark.skipif(sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="POSIX mode bits; root reads anything")
def test_an_unreadable_session_md_is_a_problem_not_a_stop():
    _record(M, "p", "s1")
    locked = _record(M, "p", "s2")
    locked.chmod(0)
    try:
        ctx = _ctx()
        phases.phase_index(ctx)
    finally:
        locked.chmod(0o644)
    assert "layout 1: index: 1 session md unreadable, see h2t-ops index query" in ctx.report.notes


def test_a_source_changed_after_its_phase_names_the_file_and_the_way_out():
    _write(_spool(), _row("real-1") + "\n")
    ctx = _ctx()
    phases.phase_activity(ctx)
    with open(_spool(), "a") as fh:
        fh.write(_row("real-2") + "\n")            # a 3.x writer still running
    with pytest.raises(engine.PhaseFailed) as ei:
        verify.phase_verify(ctx)
    assert str(_spool()) in str(ei.value)
    assert "close the program that writes it" in ei.value.hint
    assert "h2t-setup layout migrate" in ei.value.hint
    assert "h2t-setup layout rollback --sync-paused" in ei.value.hint


def test_a_session_written_after_its_phase_stops_verify_and_the_rerun_copies_it(monkeypatch):
    """A 3.x session saved after the sessions phase has no source row: verify names it and
    the migration does not complete; rollback and a new migration copy it."""
    _old_session("sessions.h2t", M, "p", "s1", _md("s1"))
    real = phases.phase_sessions
    late = paths.legacy("sessions.dor") / M / "p" / "s2.md"

    def sessions(ctx):
        real(ctx)
        _write(late, _md("s2"))                     # a 3.x handoff still running

    monkeypatch.setattr(phases, "phase_sessions", sessions)
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: verify"]
    assert f"{late}: written after the sessions phase, not copied" in report.failed[0][1]
    assert not paths.layout_file().exists()
    monkeypatch.setattr(phases, "phase_sessions", real)
    rollback.rollback(sync_paused=True)
    assert _migrate().failed == []
    assert session_record.session_path(M, "p", "s2").is_file()


# --- the whole run -------------------------------------------------------------------------

def test_every_phase_has_a_function():
    assert set(engine._phase_funcs()) == set(engine.PHASES)


def test_empty_home_migrates_to_layout_1():
    """§12, a new user: the layout appears, no 3.x place does."""
    report = _migrate()
    assert report.failed == []
    assert json.loads(paths.layout_file().read_text())["layout"] == 1
    home = paths.home()
    assert not (home / ".dor").exists()
    assert not [n for n in ("google-calendar-mcp", "gmail", "notion", "telegram")
                if (home / ".config" / n).exists()]
    # no place to declare: no file, so a lake that appears later is still written (R2)
    assert not paths.paths_yaml().exists()


_GOOGLE = {"normal": {"token": "fake-access", "refresh_token": "fake-refresh",
                      "client_id": "fake-client-id", "client_secret": "fake-client-secret",
                      "token_uri": "https://oauth2.googleapis.com/token",
                      "scope": "https://www.googleapis.com/auth/calendar",
                      "expiry_date": 1700000000000}}


def _build_3x_home() -> None:
    """§1: two machines in ~/.dor/sessions, one in ~/.h2t/sessions, Telegram, Google, evals,
    activity, cursors, registry, research, creative."""
    _old_session("sessions.dor", M, "h2t-skills", "s1", _md("s1"))
    _old_session("sessions.dor", "automata", "pos", "a1", _md("a1", project="pos"))
    _old_session("sessions.h2t", M, "h2t-skills", "s1", _md("s1"))            # the same file
    _old_session("sessions.h2t", M, "h2t-skills", "s2", _md("s2", text="fake later"))
    _write(paths.legacy("sessions.h2t") / M / "h2t-skills" / "latest.json",
           json.dumps({"session_id": "s2", "summary_short": "fake s2"}))
    _write(paths.legacy("secrets.h2t") / "secrets.env",
           "EXA_API_KEY=fake-exa\nMEETGEEK_API_KEY=fake-meetgeek\n")
    _write(paths.legacy("secrets.h2t") / "jina.env", "JINA_API_KEY=fake-jina\n")
    _write(paths.legacy("secrets.dor_old"), "H2T_EVALS_TOKEN=fake-evals\nEXA_API_KEY=fake-exa-old\n")
    _write(paths.legacy("notion.token"), "fake-notion\n")
    tg = paths.legacy("telegram")
    _write(tg / "config.json", json.dumps({"api_id": 12345, "api_hash": "fake-hash"}))
    _write(tg / "session.session", b"SQLite format 3\x00fake-session")
    _write(tg / "auth_state.json", json.dumps({"phone": "fake-phone"}))
    _write(tg / "dialogs_bootstrapped", "")
    _write(tg / "mentions_cache.json", "{}")
    _write(paths.legacy("google.store") / "credentials.json",
           json.dumps({"installed": {"client_id": "fake-client-id", "client_secret": "fake-client-secret"}}))
    _write(paths.legacy("google.store") / "tokens.json", json.dumps(_GOOGLE))
    _write(paths.legacy("evals") / "handoff" / "sessions" / "r1.json", '{"fake": 1}')
    _write(_default_spool(), _DB)
    _write(_spool(), _row("real-1") + "\n" + _row("explicit-id-row", "explicit-id") + "\n")
    _write(paths.legacy("lake.dor") / "_cursors" / "granola.json", '{"fake": "cursor"}')
    _write(paths.legacy("lake.dor") / "notes" / "n.md", "fake lake note")
    _write(paths.legacy("registry.dor"), '{"id": "fake", "host": "AUTOMATA"}\n')
    _write(paths.legacy("research") / "q" / "r.json", "{}")
    _write(paths.legacy("creative") / "p1" / "DESIGN.md", "fake design")


def _old_files() -> dict[str, str]:
    home = paths.home()
    out = {}
    for top in (home / ".dor", home / ".config", *(paths.legacy(k) for k in (
            "sessions.h2t", "activity", "evals", "research", "creative", "secrets.h2t"))):
        if top.is_dir():
            out.update({str(p): _sha(p) for p in top.rglob("*")
                        if p.is_file() and p.name != "MOVED-TO.txt"})
    return out


def _markers() -> list[Path]:
    home = paths.home()
    return sorted(p for top in (home / ".dor", home / ".config", home / ".h2t")
                  for p in top.rglob("MOVED-TO.txt"))


def test_layout1_end_to_end_on_a_3x_home():
    _build_3x_home()
    before = _old_files()
    report = _migrate(machine=M)
    assert report.failed == [], report.failed
    assert json.loads(paths.layout_file().read_text())["layout"] == 1
    sessions = paths.records("sessions")
    assert sorted(str(p.relative_to(sessions)) for p in sessions.rglob("*") if p.is_file()) == \
        [f"{M}/h2t-skills/s1.md", f"{M}/h2t-skills/s2.md"]           # automata's not copied
    assert [f for f in storage_doctor.check() if f.level == "error"] == []
    want = {paths.legacy_dir(k) for k in ("sessions.h2t", "sessions.dor", "activity", "evals",
                                          "research", "creative", "secrets.h2t", "secrets.dor_old",
                                          "notion.token", "google.store", "telegram", "registry.dor")}
    assert {p.parent for p in _markers()} == want
    assert not (paths.legacy("lake.dor") / "MOVED-TO.txt").exists()  # lake is a place (R2)
    assert _old_files() == before                                     # old files untouched

    created = [Path(r["path"]) for r in Journal.latest().entries() if r["op"] == "created"]
    out = rollback.rollback(sync_paused=True)
    assert out["kept"] == []
    assert not [p for p in created if p.exists()]
    assert _markers() == [] and not paths.layout_file().exists()
    new = [paths.root() / c for c in ("config", "secrets", "records", "data", "state")]
    left = [p for d in new if d.is_dir() for p in d.rglob("*") if p.is_file()
            and p.name not in ("index.sqlite", "index.lock")     # the derived index stays
            and paths.legacy("secrets.h2t") not in p.parents]       # 3.x, inside config/
    assert left == []
    assert _old_files() == before


def test_old_dirs_renamed_connectors_still_work(monkeypatch):
    """§12 control: with every old place renamed away, the connectors read the new ones."""
    _build_3x_home()
    assert _migrate(machine=M).failed == []
    home = paths.home()
    for old in (home / ".dor", paths.legacy("secrets.h2t"), *(home / ".config" / n for n in (
            "google-calendar-mcp", "gmail", "notion", "telegram"))):
        if old.exists():
            old.rename(old.with_name(old.name + ".gone"))
    for key, want in (("EXA_API_KEY", "fake-exa"), ("MEETGEEK_API_KEY", "fake-meetgeek"),
                      ("JINA_API_KEY", "fake-jina"), ("NOTION_API_TOKEN", "fake-notion"),
                      ("TELEGRAM_API_ID", "12345"), ("TELEGRAM_API_HASH", "fake-hash"),
                      ("H2T_EVALS_TOKEN", "fake-evals")):
        assert secrets.get(key) == want, key
    assert secrets.evals_env()["H2T_EVALS_TOKEN"] == "fake-evals"

    from google.oauth2.credentials import Credentials

    from h2t_ops.core import google_auth

    def refresh(self, request):
        self.token, self.expiry = "fake-access-2", datetime.utcnow() + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)
    monkeypatch.setattr(google_auth, "_request", lambda: None)
    creds = google_auth.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert creds.valid and creds.refresh_token == "fake-refresh"

    from h2t_ops.connectors.telegram.client import TelegramClientAdapter
    assert TelegramClientAdapter()._load_config() == {"api_id": 12345, "api_hash": "fake-hash"}
