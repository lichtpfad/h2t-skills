import itertools
import json
import os
import sqlite3
import stat
import sys

import pytest

from h2t_ops.core import paths, store


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    return h


def test_managed_registers_delegation_only_while_open(home):
    db = paths.state_dir() / "index.sqlite"
    with store.managed(db, place="state", library="sqlite3") as p:
        assert store.delegated(p) == "sqlite3"
        assert store.delegated(str(p) + "-journal") == "sqlite3"
    assert store.delegated(db) is None


def test_delegation_covers_only_the_sqlite_sidecars(home):
    db = paths.state_dir() / "index.sqlite"
    with store.managed(db, place="state", library="sqlite3"):
        for side in ("-journal", "-wal", "-shm"):
            assert store.delegated(str(db) + side) == "sqlite3"
        assert store.delegated(str(db) + "-evil") is None
        assert store.delegated(str(db) + "-journal-x") is None


def test_nested_managed_keeps_the_delegation_until_the_outer_exit(home):
    """Task 9: a helper opens the same session file inside an already open client."""
    db = paths.state_dir() / "telegram.session"
    with store.managed(db, place="state", library="telethon"):
        with store.managed(db, place="state", library="telethon"):
            pass
        assert store.delegated(db) == "telethon"
    assert store.delegated(db) is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_managed_chmod_failure_is_raised(home, monkeypatch):
    db = paths.state_dir() / "index.sqlite"

    def boom(*a, **k):
        raise PermissionError("fake-chmod-denied")

    with pytest.raises(PermissionError, match="fake-chmod-denied"):
        with store.managed(db, place="state", library="sqlite3") as p:
            p.write_bytes(b"x")
            monkeypatch.setattr(os, "chmod", boom)
    monkeypatch.undo()
    assert store.delegated(db) is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_managed_chmod_failure_does_not_mask_the_body_error(home, monkeypatch):
    db = paths.state_dir() / "index.sqlite"

    def boom(*a, **k):
        raise PermissionError("fake-chmod-denied")

    with pytest.raises(RuntimeError, match="fake-library-error") as info:
        with store.managed(db, place="state", library="sqlite3") as p:
            p.write_bytes(b"x")
            monkeypatch.setattr(os, "chmod", boom)
            raise RuntimeError("fake-library-error")
    monkeypatch.undo()
    assert any("fake-chmod-denied" in n for n in getattr(info.value, "__notes__", []))


def test_repo_rename_logs_the_file_hash(home, tmp_path, monkeypatch):
    import hashlib
    import subprocess

    from h2t_ops.core import repo_writers
    monkeypatch.setitem(repo_writers.REPO_WRITERS, "fake-renamer", {"rename": ("docs/*",)})
    repo = tmp_path / "r"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "docs" / "a.md").write_text("fake-doc-a")
    (repo / "docs" / "b.md").write_text("fake-doc-b")
    subprocess.run(["git", "add", "docs"], cwd=repo, check=True)
    w = store.repo(repo, "fake-renamer")
    log = paths.logs_dir() / "writes.jsonl"
    for src, dst, git, body in (("docs/a.md", "docs/a2.md", True, "fake-doc-a"),
                                ("docs/b.md", "docs/b2.md", False, "fake-doc-b")):
        w.rename(src, dst, git=git)
        row = json.loads(log.read_text().splitlines()[-1])
        assert (row["op"], row["path"]) == ("rename", str(repo.resolve() / dst))
        assert row["sha256"] == hashlib.sha256(body.encode()).hexdigest()
    tracked = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout
    assert "docs/a2.md" in tracked.split()


def test_connect_sqlite_opens_inside_the_delegation(home):
    db = paths.state_dir() / "index.sqlite"
    with store.connect_sqlite(db, place="state") as conn:
        assert store.delegated(db) == "sqlite3"
        conn.execute("CREATE TABLE t(x)")
    assert store.delegated(db) is None
    assert sqlite3.connect(db).execute("SELECT name FROM sqlite_master").fetchall() == [("t",)]


def test_connect_sqlite_takes_a_user_path_with_dest(home, tmp_path):
    db = tmp_path / "custom" / "session.session"          # outside every package place
    with pytest.raises(store.WriteRefused):
        with store.connect_sqlite(db, place="secrets.local"):
            pass
    with store.connect_sqlite(db, place="secrets.local", dest=True) as conn:
        conn.execute("CREATE TABLE t(x)")
    assert db.is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_sqlite_copy_is_whole_and_0600_in_secrets(home, tmp_path):
    src = tmp_path / "old.session"
    with sqlite3.connect(src) as c:
        c.execute("CREATE TABLE s(k)")
        c.execute("INSERT INTO s VALUES ('fake-session-row')")
    dest = paths.secrets_local() / "telegram.session"
    store.sqlite_copy(src, dest, place="secrets.local")
    assert sqlite3.connect(dest).execute("SELECT k FROM s").fetchall() == [("fake-session-row",)]
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_old_config_backup_removable_only_while_migrating(home):
    bak = paths.config_dir() / "domains.yaml.bak"
    store.replace(bak, "x", place="config")
    with pytest.raises(store.WriteRefused):
        store.remove(bak, place="config")
    with store.migrating():
        store.remove(bak, place="config")
    assert not bak.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_managed_secret_gets_0600(home):
    sess = paths.secrets_local() / "telegram.session"
    with store.managed(sess, place="secrets.local", library="telethon") as p:
        p.write_bytes(b"x")  # stands in for the library
    assert stat.S_IMODE(sess.stat().st_mode) == 0o600


def test_repo_writer_honours_allow_list(home, tmp_path):
    # `home` matters: create() logs to logs/writes.jsonl and parses paths.yaml, and without
    # it both are the developer's real ~/.h2t until Task 7 isolates the suite.
    repo = tmp_path / "r"
    repo.mkdir()
    w = store.repo(repo, "init-project")
    w.create(".claude/project-id", "dev/x\n")
    assert (repo / ".claude" / "project-id").read_text() == "dev/x\n"
    with pytest.raises(store.WriteRefused, match="init-project"):
        w.replace(".claude/project-id", "dev/y\n")   # create if absent only (§7.1, R32)
    with pytest.raises(store.WriteRefused, match="init-project"):
        w.replace("README.md", "x")
    with pytest.raises(store.WriteRefused, match="outside"):
        w.create("../escape", "x")


@pytest.mark.parametrize("rel", [".git/config", ".git/hooks/pre-commit", ".GIT/config",
                                 "sub/.git/config", ".git"])
def test_no_command_writes_under_git(home, tmp_path, monkeypatch, rel):
    """Whatever the allow-list says (here "*"), git's own directory is not a repository
    write: any depth, any case (#548 Task 17 round 2)."""
    from h2t_ops.core import repo_writers
    monkeypatch.setitem(repo_writers.REPO_WRITERS, "fake-wide", {"replace": ("*",), "append": ("*",)})
    repo = tmp_path / "r"
    (repo / ".git").mkdir(parents=True)
    w = store.repo(repo, "fake-wide")
    with pytest.raises(store.WriteRefused, match=r"\.git"):
        w.replace(rel, "x")
    with pytest.raises(store.WriteRefused, match=r"\.git"):
        w.append(".git/info/exclude", "x")     # "*" is not the exact rule


def test_scaffold_keeps_its_one_git_path(home, tmp_path):
    repo = tmp_path / "r"
    (repo / ".git" / "info").mkdir(parents=True)
    store.repo(repo, "h2t-scaffold-project").append(".git/info/exclude", "x")
    assert (repo / ".git" / "info" / "exclude").read_text() == "x\n"


@pytest.mark.parametrize("d", ["*", ".g?t", "[.]git", "docs/[ab]"])
def test_extra_dirs_are_literal_directories(home, tmp_path, d):
    with pytest.raises(store.WriteRefused):
        store.repo(tmp_path, "h2t-docs-lint fix-safe", extra_dirs={"rename": (d,)})


def test_unknown_command_is_refused(home, tmp_path):
    with pytest.raises(store.WriteRefused, match="not in the repo allow-list"):
        store.repo(tmp_path, "h2t-something-new")


def test_ingest_is_the_vault_door(home, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    store.ingest_write(vault / "n.md", "note")
    assert (vault / "n.md").read_text() == "note"


def test_moved_marker_only_while_migrating(home):
    legacy = paths.legacy("sessions.h2t")
    legacy.mkdir(parents=True)
    with pytest.raises(store.WriteRefused):
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    with store.migrating():
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    assert (legacy / "MOVED-TO.txt").exists()


def test_writer_and_managed_log_the_file_hash(home):
    """§7.2: every write has its hash in writes.jsonl; only secrets have null."""
    import hashlib
    p = paths.state_dir() / "w.bin"
    with store.writer(p, place="state") as fh:
        fh.write(b"abc")
    rows = [json.loads(x) for x in (paths.logs_dir() / "writes.jsonl").read_text().splitlines()]
    assert rows[-1]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    db = paths.state_dir() / "m.sqlite"
    with store.connect_sqlite(db, place="state") as conn:
        conn.execute("CREATE TABLE t(x)")
    rows = [json.loads(x) for x in (paths.logs_dir() / "writes.jsonl").read_text().splitlines()]
    assert rows[-1]["sha256"] == hashlib.sha256(db.read_bytes()).hexdigest()
    with store.writer(paths.secrets_local() / "s.bin", place="secrets.local") as fh:
        fh.write(b"fake-secret-bytes")
    rows = [json.loads(x) for x in (paths.logs_dir() / "writes.jsonl").read_text().splitlines()]
    assert rows[-1]["sha256"] is None


def test_writer_streams_and_replaces_atomically(home):
    p = paths.state_dir() / "big.bin"
    with store.writer(p, place="state") as fh:
        for _ in range(3):
            fh.write(b"x" * 10)
        assert not p.exists()                     # nothing at the final path until exit
    assert p.read_bytes() == b"x" * 30
    with pytest.raises(RuntimeError):
        with store.writer(p, place="state") as fh:
            fh.write(b"half")
            raise RuntimeError("network dropped")
    assert p.read_bytes() == b"x" * 30            # the old file survives an interrupted stream
    assert [x.name for x in p.parent.iterdir()] == ["big.bin"]


def test_exclusive_writer_never_replaces_an_existing_file(home):
    """R47: a new download into lake/inbox must not overwrite a file the package does not own."""
    p = paths.data_dir() / "inbox" / "report.pdf"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"the user's own")
    with pytest.raises(store.AlreadyExists):
        with store.writer(p, place="data", exclusive=True) as fh:
            fh.write(b"downloaded")
    assert p.read_bytes() == b"the user's own"
    assert [x.name for x in p.parent.iterdir()] == ["report.pdf"]   # no temp left
    assert [q.name for q in itertools.islice(store.unique_name(p), 3)] == [
        "report.pdf", "report-2.pdf", "report-3.pdf"]
