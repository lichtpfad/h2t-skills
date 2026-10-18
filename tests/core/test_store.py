import json
import os
import stat
import sys
import tempfile

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


def test_replace_writes_atomically_and_logs(home):
    target = paths.state_dir() / "x.json"
    store.replace(target, '{"a": 1}', place="state")
    assert target.read_text() == '{"a": 1}'
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["op"] == "replace" and row["place"] == "state" and row["path"] == str(target)
    assert row["caller"].startswith("tests.core.test_store") or "test_store" in row["caller"]


def _save_after_the_temp_file(monkeypatch, target, text):
    """Another program saves the target after store wrote its temp file, before publication."""
    real = store._tmp_beside

    def tmp_then_save(path, payload, mode):
        tmp = real(path, payload, mode)
        target.write_text(text)
        os.utime(target, ns=(1, 10**18))
        return tmp
    monkeypatch.setattr(store, "_tmp_beside", tmp_then_save)


def test_replace_with_expect_does_not_publish_over_a_concurrent_save(home, monkeypatch):
    target = paths.state_dir() / "s.json"
    store.replace(target, "mine", place="state")
    seen = store.stamp(target)
    _save_after_the_temp_file(monkeypatch, target, "theirs")
    with pytest.raises(store.Changed):
        store.replace(target, "stale copy", place="state", expect=seen)
    assert target.read_text() == "theirs"
    assert sorted(p.name for p in target.parent.iterdir()) == ["s.json"]   # no temp left


def test_replace_with_expect_none_needs_the_target_still_absent(home, monkeypatch):
    target = paths.state_dir() / "new.json"
    _save_after_the_temp_file(monkeypatch, target, "theirs")
    with pytest.raises(store.Changed):
        store.replace(target, "mine", place="state", expect=None)
    assert target.read_text() == "theirs"


def test_replace_with_a_matching_expect_publishes(home):
    target = paths.state_dir() / "s.json"
    store.replace(target, "one", place="state", expect=None)
    store.replace(target, "two", place="state", expect=store.stamp(target))
    assert target.read_text() == "two"


def test_write_is_classified_by_real_path_not_by_name(home):
    with pytest.raises(store.WriteRefused, match="secrets.shared"):
        store.replace(paths.secrets_shared() / "x.env", "K=fake-k", place="state")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_symlink_does_not_launder_a_write(home, tmp_path):
    paths.secrets_shared().mkdir(parents=True)
    link = paths.state_dir() / "sneaky"
    link.parent.mkdir(parents=True)
    link.symlink_to(paths.secrets_shared())
    with pytest.raises(store.WriteRefused):
        store.replace(link / "exa.env", "EXA_API_KEY=fake-exa", place="state")


def test_vault_write_refused_outside_ingest(home, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    with pytest.raises(store.WriteRefused, match="ingest"):
        store.replace(vault / "n.md", "x", place="vault")
    with pytest.raises(store.WriteRefused):
        store.replace(vault / "n.md", "x", place="elsewhere", dest=True)


def test_default_vault_under_dor_is_vault_not_legacy(home):
    with pytest.raises(store.WriteRefused, match="ingest"):
        store.replace(home / ".dor" / "vault" / "n.md", "x", place="vault")


def test_lake_at_the_old_dor_path_classifies_as_lake(home):
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text("version: 1\nplaces:\n  lake: ~/.dor/lake\n")
    assert store.classify(home / ".dor" / "lake" / "granola" / "n.md") == "lake"
    assert store.classify(home / ".dor" / "secrets.env") == "legacy"


def test_legacy_write_refused_without_compat(home):
    with pytest.raises(store.WriteRefused, match="legacy"):
        store.replace(paths.legacy("telegram") / "config.json", "{}", place="legacy")


def test_broken_paths_yaml_still_allows_package_writes(home, tmp_path, monkeypatch):
    # tmp_path lies under the system temp dir, so every path here would classify as "tmp";
    # move the temp dir aside so a path outside ~/.h2t is really "elsewhere".
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "systmp"))
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text("version: 1\nplaces:\n  lake: [broken\n")
    p = paths.records("sessions", "m") / "proj" / "s.md"
    store.replace(p, "work survives", place="records.sessions")
    assert p.read_text() == "work survives"
    store.append(paths.activity_file("m"), "x", place="records.activity")
    with pytest.raises(store.WriteRefused, match="paths.yaml"):
        store.replace(home / "Documents" / "f.txt", "x", place="elsewhere", dest=True)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_secret_files_are_0600_and_dirs_0700(home):
    p = store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\n",
                      place="secrets.shared")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE(p.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(p.parent.parent.stat().st_mode) == 0o700
    log = (paths.logs_dir() / "writes.jsonl").read_text()
    assert "fake-exa" not in log and '"sha256": null' in log


def test_secret_write_logs_key_names_never_values(home):
    store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                  place="secrets.shared", keys=("EXA_X", "EXA_API_KEY"))
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["keys"] == ["EXA_API_KEY", "EXA_X"] and row["sha256"] is None
    assert "fake" not in json.dumps(row)


def test_secret_written_to_a_user_path_is_logged_as_a_secret(home, tmp_path):
    """dest=True classifies elsewhere/tmp; keys still mark the write secret (no file hash)."""
    store.replace(tmp_path / "mine" / "auth.json", '{"k": "fake-k"}', place="secrets.local",
                  dest=True, keys=("k",))
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["sha256"] is None and row["keys"] == ["k"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_non_secret_files_follow_umask(home):
    old = os.umask(0o022)
    try:
        p = store.replace(paths.state_dir() / "a.json", "{}", place="state")
    finally:
        os.umask(old)
    assert stat.S_IMODE(p.stat().st_mode) == 0o644


def test_create_never_overwrites(home):
    p = paths.records("sessions", "m") / "proj" / "s.md"
    store.create(p, "one", place="records.sessions")
    with pytest.raises(store.AlreadyExists):
        store.create(p, "two", place="records.sessions")
    assert p.read_text() == "one"
    assert [x.name for x in p.parent.iterdir()] == ["s.md"]  # no temp file left behind


def test_create_without_hard_links_writes_nothing(home, monkeypatch):
    """R20: no fallback that writes the final path directly."""
    def no_links(src, dst, **kw):
        raise OSError(1, "Operation not permitted")
    monkeypatch.setattr(store.os, "link", no_links)
    p = paths.records("sessions", "m") / "proj" / "s.md"
    with pytest.raises(store.ConfigError, match="hard link"):
        store.create(p, "one", place="records.sessions")
    assert not p.exists()
    assert list(p.parent.iterdir()) == []                   # the temp file is gone too


def test_append_one_line_per_call(home):
    p = paths.activity_file("m")
    store.append(p, '{"a":1}', place="records.activity")
    store.append(p, '{"a":2}\n', place="records.activity")
    assert p.read_text().splitlines() == ['{"a":1}', '{"a":2}']


def test_append_under_unicode_home(tmp_path, monkeypatch):
    h = tmp_path / "Лидия Иванова"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    p = paths.activity_file("m")
    store.append(p, "x", place="records.activity")
    assert p.read_text(encoding="utf-8") == "x\n"


def test_remove_only_in_package_places(home, tmp_path):
    p = store.replace(paths.state_dir() / "t", "x", place="state")
    store.remove(p, place="state")
    assert not p.exists()
    s = store.replace(paths.records("sessions", "m") / "a.md", "x", place="records.sessions")
    with pytest.raises(store.WriteRefused, match="remove"):
        store.remove(s, place="records.sessions")


def test_writes_log_rotates(home, monkeypatch):
    monkeypatch.setattr(store, "_LOG_LIMIT", 200)
    for i in range(40):
        store.replace(paths.state_dir() / f"f{i}", "x", place="state")
    names = sorted(p.name for p in paths.logs_dir().iterdir())
    assert "writes.jsonl" in names and "writes.1.jsonl" in names
    assert len([n for n in names if n.startswith("writes")]) <= 6


def test_dest_allows_explicit_user_path_but_not_package_places(home, tmp_path):
    out = tmp_path / "anywhere" / "f.txt"
    store.replace(out, "x", place="elsewhere", dest=True)
    assert out.read_text() == "x"
    with pytest.raises(store.WriteRefused):
        store.replace(paths.secrets_shared() / "a.env", "x", place="elsewhere", dest=True)
    with pytest.raises(store.WriteRefused, match="h2t-root"):     # unclassified, directly in ~/.h2t
        store.replace(paths.root() / "stray.txt", "x", place="elsewhere", dest=True)
    assert not (paths.root() / "stray.txt").exists()


def _broken_yaml(home):
    (home / ".h2t" / "config").mkdir(parents=True, exist_ok=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text("version: 1\nplaces:\n  lake: [broken\n")


def test_declared_place_under_a_broken_paths_yaml_names_the_file(home, tmp_path):
    """lake: ~/.dor/lake (R2) classifies legacy, a lake in the temp dir classifies tmp, while
    the file is broken; either way the refusal must point at paths.yaml."""
    _broken_yaml(home)
    with pytest.raises(store.WriteRefused, match="paths.yaml"):
        store.replace(home / ".dor" / "lake" / "granola" / "n.md", "x", place="lake")
    with pytest.raises(store.WriteRefused, match="paths.yaml"):
        store.replace(tmp_path / "lake" / "n.md", "x", place="lake")


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl probe of the lock")
def test_log_rotation_happens_under_the_log_lock(home, monkeypatch):
    import fcntl
    held = []
    real_rotate = store._rotate

    def probe(log):
        fd = os.open(log.with_name(store._LOG_LOCK), os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            held.append(False)
        except BlockingIOError:
            held.append(True)
        finally:
            os.close(fd)
        real_rotate(log)

    monkeypatch.setattr(store, "_rotate", probe)
    store.replace(paths.state_dir() / "a", "x", place="state")
    assert held == [True]


def test_a_lost_log_row_is_said_on_stderr_and_the_write_stands(home, capsys):
    logs = paths.logs_dir()
    logs.parent.mkdir(parents=True)
    logs.write_text("not a directory")          # the journal cannot be written
    p = store.replace(paths.state_dir() / "a.json", "{}", place="state")
    assert p.read_text() == "{}"
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and str(logs / "writes.jsonl") in err[0] and "Errno" in err[0]


def test_short_os_write_is_completed(home, monkeypatch):
    real_write = os.write
    p = paths.activity_file("m")
    with monkeypatch.context() as m:       # scoped: undo() would also restore the real HOME
        m.setattr(os, "write", lambda fd, data: real_write(fd, bytes(data[:3])))
        store.append(p, '{"line": "' + "y" * 50 + '"}', place="records.activity")
        store.replace(paths.state_dir() / "a.json", "{}", place="state")
    assert p.read_text() == '{"line": "' + "y" * 50 + '"}\n'
    rows = [json.loads(x) for x in (paths.logs_dir() / "writes.jsonl").read_text().splitlines()]
    assert [r["op"] for r in rows] == ["append", "replace"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_secret_files_are_0600_whatever_mode_is_passed(home):
    p = store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\n",
                      place="secrets.shared", mode=0o644)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    q = store.create(paths.secrets_local() / "x.env", "X_KEY=fake-x\n", place="secrets.local",
                     mode=0o644)
    assert stat.S_IMODE(q.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_append_repairs_an_existing_secret_file_mode(home):
    p = paths.secrets_local() / "telegram.log"
    p.parent.mkdir(parents=True)
    p.write_text("")
    os.chmod(p, 0o644)
    store.append(p, "fake-line", place="secrets.local")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits make rmtree fail")
def test_remove_tree_failure_propagates_and_is_not_logged(home):
    d = paths.state_dir() / "tree"
    (d / "locked").mkdir(parents=True)
    (d / "locked" / "f").write_text("x")
    os.chmod(d / "locked", 0o500)
    try:
        with pytest.raises(PermissionError):
            store.remove_tree(d, place="state")
    finally:
        os.chmod(d / "locked", 0o700)
    log = paths.logs_dir() / "writes.jsonl"
    assert not log.exists() or '"remove_tree"' not in log.read_text()


def test_remove_tree_of_nothing_is_quiet_and_not_logged(home):
    store.remove_tree(paths.state_dir() / "absent", place="state")
    assert not (paths.logs_dir() / "writes.jsonl").exists()
    d = store.mkdir(paths.state_dir() / "t", place="state")
    store.remove_tree(d, place="state")
    assert not d.exists()
    assert '"remove_tree"' in (paths.logs_dir() / "writes.jsonl").read_text()


# --- replace(in_place=True): only an NTFS stream name, never a secret (#548 §7.2) ---------


def test_in_place_refuses_a_plain_name(home):
    target = paths.data_dir() / "research" / "plain.json"
    with pytest.raises(store.WriteRefused, match="NTFS stream"):
        store.replace(target, "{}", place="data", in_place=True)
    assert not target.exists() and not target.parent.exists()


@pytest.mark.parametrize("place", ["secrets.shared", "secrets.local"])
def test_in_place_refuses_secrets(home, place):
    target = paths.dir_of(place) / "x:y.env"
    with pytest.raises(store.WriteRefused, match="NTFS stream"):
        store.replace(target, "fake-x", place=place, in_place=True)
    assert not target.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_in_place_writes_a_stream_name_with_the_place_mode(home, monkeypatch):
    target = paths.data_dir() / "research" / "objects" / "research-doc:1.json"
    target.parent.mkdir(parents=True)
    target.write_text("old")
    os.chmod(target, 0o666)
    synced = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd)))
    um = os.umask(0o022)
    try:
        store.replace(target, "{}", place="data", in_place=True)
    finally:
        os.umask(um)
    assert synced, "the in-place write must reach the disk before it is logged"
    assert target.read_text() == "{}"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
    assert sorted(p.name for p in target.parent.iterdir()) == ["research-doc:1.json"]
