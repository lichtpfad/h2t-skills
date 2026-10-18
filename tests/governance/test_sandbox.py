import contextlib
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import paths
from tests.governance import audit
from tests.governance.sandbox_cases import CASES


def compat_allowed(p: Path, home: Path, compat: tuple[str, ...]) -> bool:
    """A compat write touches the file, its directory (os.mkdir with exist_ok raises the
    event) and store's temp file beside it (.<name>.XXXX, store._tmp_beside)."""
    for rel in compat:
        target = Path(os.path.realpath(home / rel))
        if p in (target, target.parent):
            return True
        if p.parent == target.parent and p.name.startswith("." + target.name + "."):
            return True
    return False


@contextlib.contextmanager
def build_sandbox(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    lake, inbox, vault = (tmp_path / n for n in ("lake", "inbox", "vault"))
    for d in (lake, inbox, vault):
        d.mkdir()
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    cfg = home / ".h2t" / "config"
    cfg.mkdir(parents=True)
    (cfg / "paths.yaml").write_text(
        f"version: 1\nplaces:\n  lake: {lake}\n  inbox: {inbox}\n", encoding="utf-8")
    dirs = {paths.legacy_dir(n) for n in paths.LEGACY if n != "downloads"}
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    closed = [d for d in dirs if d != home and paths.root() not in (d, *d.parents)
              and d != paths.legacy("google.store")]   # the one compat mirror (§9)
    if sys.platform != "win32":
        for d in closed:
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
    # tmp (§7.1: only through store.scratch) and harness (only h2t-setup) are places too.
    guarded = [paths.root(), lake, inbox, vault, paths.dir_of("tmp"), paths.dir_of("harness"),
               *paths.legacy_roots()]
    secret_dirs = [paths.root() / "secrets", *(paths.legacy(n) for n in
                   ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                    "google.store", "google.gmail", "google.dor", "telegram"))]
    shared, local = paths.secrets_shared(), paths.secrets_local()
    twins = {paths.legacy("google.store") / "tokens.json": local / "google.token.json",
             paths.legacy("google.gmail") / "token.json": local / "google.token.json",
             paths.legacy("google.store") / "credentials.json": shared / "google.client.json",
             paths.legacy("google.gmail") / "credentials.json": shared / "google.client.json",
             paths.legacy("google.dor"): shared / "google.client.json",
             paths.legacy("notion.token"): shared / "notion.env",
             paths.legacy("telegram") / "auth_state.json": local / "telegram.auth-state.json",
             paths.legacy("telegram") / "session.session": local / "telegram.session"}
    try:
        yield SimpleNamespace(home=home, lake=lake, inbox=inbox, vault=vault,
                              recorder=audit.Recorder(guarded, secret_dirs, paths.legacy_roots(), twins))
    finally:
        if sys.platform != "win32":
            for d in closed:
                os.chmod(d, stat.S_IRWXU)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    with build_sandbox(tmp_path, monkeypatch) as sb:
        yield sb


def run_case(case, sb, monkeypatch) -> None:
    if case.setup is not None:
        case.setup(sb, monkeypatch)            # starting state, recorder off (R30)
    with sb.recorder.active():
        case.run(sb, monkeypatch)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_command_touches_only_through_the_doors(case, sandbox, monkeypatch):
    run_case(case, sandbox, monkeypatch)
    rec = sandbox.recorder
    unseen = f"\nchild processes the audit cannot see: {rec.popen}" if rec.popen else ""
    assert rec.violations == [], "\n".join(rec.violations) + unseen
    stray = {p for p in rec.legacy_writes if not compat_allowed(p, sandbox.home, case.compat)}
    assert stray == set(), f"legacy writes outside compat: {sorted(map(str, stray))}{unseen}"


def test_worker_thread_events_reach_the_recorder(sandbox):
    import threading
    f = sandbox.lake / "t.md"
    with sandbox.recorder.active():
        t = threading.Thread(target=lambda: f.write_text("x"))
        t.start()
        t.join()
    assert any("t.md" in v for v in sandbox.recorder.violations)


@pytest.mark.skipif(sys.platform == "win32", reason="rmtree on Windows takes no dir_fd path")
def test_fd_relative_remove_is_attributed(sandbox):
    (sandbox.lake / "sub").mkdir()
    (sandbox.lake / "sub" / "a.md").write_text("x")
    import shutil
    with sandbox.recorder.active():
        shutil.rmtree(sandbox.lake / "sub")   # members go through os.remove(name, dir_fd=…)
    assert any("a.md" in v for v in sandbox.recorder.violations)


def test_legacy_read_while_the_new_twin_exists_is_caught_even_from_secrets(sandbox):
    from h2t_ops.core import secrets
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.write_text('{"refresh_token": "fake-old"}')
    with sandbox.recorder.active():
        secrets.read_json("google.token")      # no new file yet: the legacy read is fine
    assert sandbox.recorder.violations == []
    new = paths.secrets_local() / "google.token.json"
    new.parent.mkdir(parents=True)
    new.write_text('{"refresh_token": "fake-new"}')
    with sandbox.recorder.active():
        legacy.read_text()
    # " while ", not "while": tmp_path carries the test name, and that has "_while_" in it
    assert any(" while " in v for v in sandbox.recorder.violations)


def test_direct_secret_read_is_caught(sandbox):
    target = paths.secrets_shared() / "exa.env"
    target.parent.mkdir(parents=True)
    target.write_text("EXA_API_KEY=fake")
    with sandbox.recorder.active():
        target.read_text()
    assert sandbox.recorder.violations and " read " in sandbox.recorder.violations[0]  # not tmp_path's name


@pytest.mark.parametrize("op", ["write", "rename", "remove"])
def test_direct_mutation_inside_lake_is_caught(sandbox, op):
    f = sandbox.lake / "a.md"
    f.write_text("x")
    with sandbox.recorder.active():
        if op == "write":
            f.write_text("y")
        elif op == "rename":
            os.rename(f, sandbox.lake / "b.md")
        else:
            os.remove(f)
    assert sandbox.recorder.violations


def test_sqlite_without_delegation_is_caught(sandbox):
    import sqlite3
    db = paths.state_dir() / "x.sqlite"
    db.parent.mkdir(parents=True)
    with sandbox.recorder.active():
        sqlite3.connect(db).close()
    assert any("sqlite3.connect" in v for v in sandbox.recorder.violations)


def test_compat_write_allowed_only_for_the_google_mirror(sandbox):
    from h2t_ops.core import store
    with sandbox.recorder.active():
        store.replace(paths.legacy("google.store") / "tokens.json", "{}", place="legacy", compat=True)
        with pytest.raises(store.WriteRefused):
            store.replace(paths.legacy("telegram") / "x.json", "{}", place="legacy", compat=True)
    assert sandbox.recorder.violations == []
    compat = (".config/google-calendar-mcp/tokens.json",)
    # the mirror's own events (dir, temp beside, target) pass; nothing else was written
    assert sandbox.recorder.legacy_writes
    assert all(compat_allowed(p, sandbox.home, compat) for p in sandbox.recorder.legacy_writes)
    assert not compat_allowed(paths.legacy("telegram") / "x.json", sandbox.home, compat)


def test_writers_are_recorded_by_module(sandbox, tmp_path):
    """Positive control for R27: a module whose file lies under an h2t_ops/ directory and
    writes through store is named; the test's own frames are not."""
    import importlib.util
    mod_file = tmp_path / "pkg" / "h2t_ops" / "zz_writer.py"
    mod_file.parent.mkdir(parents=True)
    mod_file.write_text("from h2t_ops.core import paths, store\n"
                        "def go():\n"
                        "    store.replace(paths.state_dir() / 'w.json', '{}', place='state')\n")
    spec = importlib.util.spec_from_file_location("zz_writer", mod_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with sandbox.recorder.active():
        mod.go()
    assert sandbox.recorder.writers == {"zz_writer.py"}


def test_direct_write_into_tmp_is_caught(sandbox, tmp_path):
    """§7.1: tmp only through store.scratch(). The probe file lies under this test's own
    tmp_path (inside the system temp dir, outside every other guarded root), so no file
    the test does not own is ever touched."""
    from h2t_ops.core import store
    with sandbox.recorder.active():
        with store.scratch() as d:
            store.replace(d / "in.json", "{}", place="tmp")
    assert sandbox.recorder.violations == []
    probe = tmp_path / "direct-probe.txt"
    with sandbox.recorder.active():
        probe.write_text("x")
    assert any("direct-probe" in v for v in sandbox.recorder.violations)
