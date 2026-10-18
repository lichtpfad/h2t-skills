"""doctor's storage checks (#548 §7.4): one test per code, each on a minimal state built in
the test's own HOME — a config git repo with secrets/x.env tracked in it, as at the author's."""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from h2t_ops import cli
from h2t_ops.core import paths
from h2t_ops.setup import storage_doctor
from h2t_ops.setup.storage_doctor import check, sync_status

SECRET = "fake-SECRET-VALUE-123"


def _write(p: Path, text: str = "fake-content") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def config_repo():
    cfg = paths.config_dir()
    _write(cfg / "secrets" / "x.env", "EXA_API_KEY=fake-exa-tracked\n")
    _write(cfg / "notes.md", "FOO=bar\nEXA_API_KEY=\n")       # no provider key / empty value
    subprocess.run(["git", "init", "-q", str(cfg)], check=True)
    subprocess.run(["git", "-C", str(cfg), "add", "secrets/x.env", "notes.md"], check=True)
    return cfg


def _texts(code: str) -> list[str]:
    return [f.text for f in check() if f.code == code]


def _levels(code: str) -> set[str]:
    return {f.level for f in check() if f.code == code}


def _paths_yaml(text: str) -> None:
    _write(paths.paths_yaml(), text)


def test_secret_tracked_names_the_file_and_the_key_not_the_value():
    texts = _texts("secret-tracked")
    assert texts == ["~/.h2t/config/secrets/x.env is tracked by git in ~/.h2t/config",
                     "~/.h2t/config/secrets/x.env holds a value for EXA_API_KEY and is tracked by git"]
    assert _levels("secret-tracked") == {"error"}


def test_secret_tracked_sees_yaml_and_json_by_key_not_value(config_repo):
    """A credential committed in a YAML or JSON config file: the file and the key, never
    the value; an empty value and an unknown key are not findings."""
    _write(config_repo / "notion.yaml", f"notion:\n  NOTION_API_TOKEN: {SECRET}\n  EXA_API_KEY: ''\n")
    _write(config_repo / "google.json", json.dumps(
        {"installed": {"client_id": "fake-id", "client_secret": SECRET}, "x": [{"refresh_token": SECRET}]}))
    _write(config_repo / "plain.yaml", "name: fake-name\nlake: ~/.dor/lake\n")
    subprocess.run(["git", "-C", str(config_repo), "add", "notion.yaml", "google.json", "plain.yaml"],
                   check=True)
    texts = _texts("secret-tracked")
    assert "~/.h2t/config/notion.yaml holds a value for NOTION_API_TOKEN and is tracked by git" in texts
    assert "~/.h2t/config/google.json holds a value for client_secret and is tracked by git" in texts
    assert "~/.h2t/config/google.json holds a value for refresh_token and is tracked by git" in texts
    assert not [t for t in texts if "plain.yaml" in t or "EXA_API_KEY" in t and "notion" in t]
    assert not [t for t in texts if SECRET in t]


def test_local_in_sync_by_a_marker_up_the_tree():
    (paths.root() / ".stfolder").mkdir(parents=True)
    texts = _texts("local-in-sync")
    assert "~/.h2t/state lies inside a Syncthing folder (~/.h2t/.stfolder)" in texts
    assert len(texts) == 4          # secrets.local, state, logs, run/rollback
    assert _levels("local-in-sync") == {"error"}


def test_local_in_sync_by_a_declaration_and_none_is_not_one():
    _paths_yaml("version: 1\nsync:\n  state: syncthing\n  logs: none\n")
    assert _texts("local-in-sync") == ["~/.h2t/state is declared synced (syncthing) in ~/.h2t/config/paths.yaml"]


def test_sync_status_confirmed_declared_unknown():
    (paths.root() / "records" / ".stfolder").mkdir(parents=True)
    _paths_yaml("version: 1\nsync:\n  secrets.shared: syncthing\n")
    assert sync_status("records") == ("confirmed", ".stfolder at ~/.h2t/records")
    assert sync_status("secrets.shared") == ("declared", "syncthing")
    assert sync_status("secrets.local") == ("unknown", "")
    lines = storage_doctor.report()
    assert lines[0] == "storage: layout none, root ~/.h2t"
    assert "records = confirmed (.stfolder at ~/.h2t/records)" in lines[1]
    assert "secrets.shared = declared (syncthing), secrets.local = unknown" in lines[1]


def _sessions_only() -> list[str]:
    # the fixture's config/secrets is a 3.x secrets dir: "secrets are only in" is right there
    return [t for t in _texts("legacy-only") if t.startswith("sessions")]


def test_legacy_only_once_per_class():
    _write(paths.home() / ".dor" / "sessions" / "m" / "a.md")
    _write(paths.home() / ".dor" / "sessions" / "m" / "b.md")
    assert _sessions_only() == ["sessions are only in ~/.dor/sessions — h2t-setup sync moves them"]
    assert "secrets are only in ~/.h2t/config/secrets — h2t-setup sync moves them" in _texts("legacy-only")
    _write(paths.records("sessions") / "m" / "p" / "a.md")
    assert _sessions_only() == []


def test_sync_conflict_in_records_secrets_config():
    _write(paths.records("activity") / "m.sync-conflict-20260101-000000-ABCDEFG.jsonl")
    _write(paths.secrets_shared() / "exa.sync-conflict-20260101-000000-ABCDEFG.env")
    _write(paths.data_dir() / "r.sync-conflict-20260101-000000-ABCDEFG.json")   # data: not checked
    assert sorted(_texts("sync-conflict")) == [
        "~/.h2t/records/activity/m.sync-conflict-20260101-000000-ABCDEFG.jsonl: a sync conflict copy",
        "~/.h2t/secrets/shared/exa.sync-conflict-20260101-000000-ABCDEFG.env: a sync conflict copy"]


def test_unknown_root_entry_skips_places_layout_and_3x_dirs():
    root = paths.root()
    for name in ("state", "records", "sessions", "activity", "evals", "research", "creative", "venv"):
        (root / name).mkdir(parents=True, exist_ok=True)
    _write(root / "layout.json", '{"layout": 1}')
    (root / ".git-backup").mkdir()
    _write(root / "manifest-2026-08-27.txt")
    assert _texts("unknown-root-entry") == [
        "~/.h2t/.git-backup is not a place of the package",
        "~/.h2t/manifest-2026-08-27.txt is not a place of the package"]


def _index(version: str) -> None:
    path = paths.state_dir() / "index.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (version,))
    conn.commit()
    conn.close()


def test_index_schema_mismatch_is_a_warning():
    _index("0")
    assert _texts("index-schema") == ["~/.h2t/state/index.sqlite has schema 0, expected 1 — h2t-ops index rebuild"]


def test_index_schema_current_is_quiet():
    _index("1")
    assert _texts("index-schema") == []


def test_old_env_name_says_what_became_of_each(monkeypatch):
    for name in paths.OLD_ENV:
        monkeypatch.setenv(name, str(paths.home() / "x"))
    texts = dict(t.split(" is set; the package no longer reads it: ") for t in _texts("old-env-name"))
    assert texts == {
        "H2T_LAKE_ROOT": "the migration moves the value into paths.yaml (lake)",
        "H2T_SECRETS_FILE": "the migration reads that file as a secrets source",
        "H2T_EVALS_SPOOL": "the migration copies that spool into state/evals-spool.sqlite",
        **{n: "the migration does not copy from it — move what it names to the 3.x default, then remove it" for n in
           ("H2T_CONFIG_ROOT", "H2T_SESSION_ROOT", "H2T_ACTIVITY_SPOOL", "H2T_EVALS_ROOT")}}


def test_place_missing_for_paths_yaml_and_vault(tmp_path):
    _paths_yaml(f"version: 1\nplaces:\n  lake: {tmp_path / 'no-lake'}\n")
    texts = _texts("place-missing")
    assert f"lake {tmp_path / 'no-lake'} does not exist" in texts
    assert any(t.startswith("vault ~/.dor/vault does not exist") for t in texts)
    (tmp_path / "no-lake").mkdir()
    (paths.vault()).mkdir(parents=True)
    assert _texts("place-missing") == []


def test_vault_missing_is_info_by_default_and_warn_when_set(monkeypatch, tmp_path):
    vault = [f for f in check() if f.code == "place-missing" and f.text.startswith("vault ")]
    assert [(f.level, f.text.split(" (")[0]) for f in vault] == [("info", "vault ~/.dor/vault does not exist")]
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "no-vault"))
    vault = [f for f in check() if f.code == "place-missing" and f.text.startswith("vault ")]
    assert [(f.level, f.text.split(" (")[0]) for f in vault] == [("warn", f"vault {tmp_path / 'no-vault'} does not exist")]


def test_doctor_is_clean_for_a_new_user_in_an_empty_home(capsys):
    """§12: a new user's doctor has nothing to warn about — info lines only."""
    import shutil
    shutil.rmtree(paths.root())               # drop the autouse config repo: an empty HOME
    assert list(paths.home().iterdir()) == []
    assert cli._doctor() == 0
    storage = [line for line in capsys.readouterr().out.splitlines() if line.startswith("storage: ")]
    findings = storage[2:]
    assert findings and all(line.startswith("storage: info ") for line in findings), findings
    assert list(paths.home().iterdir()) == []


def test_place_unset_is_info(tmp_path):
    assert _texts("place-unset") == [
        "lake is not set; the package uses ~/.h2t/data/lake — h2t-ops paths set lake <path>",
        "inbox is not set; the package uses ~/.h2t/data/inbox — h2t-ops paths set inbox <path>"]
    assert _levels("place-unset") == {"info"}
    (tmp_path / "lake").mkdir()
    _paths_yaml(f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n")
    assert [t.split()[0] for t in _texts("place-unset")] == ["inbox"]


def test_config_backup_is_a_warning():
    _write(paths.config_dir() / "repo-mapping.yaml.bak.20260801")
    _write(paths.config_dir() / "repo-mapping.yaml")
    assert _texts("config-backup") == [
        "~/.h2t/config/repo-mapping.yaml.bak.20260801 is a 3.x copy; copies now live in ~/.h2t/state/backups"]


def test_from_copies_are_found_in_every_destination():
    root = paths.root()
    _write(paths.secrets_shared() / "exa.env.from-dor", f"EXA_API_KEY={SECRET}\n")
    _write(paths.secrets_local() / "telegram.session.from-config", SECRET)
    _write(root / "records" / "sessions" / "m" / "p" / "s.md.from-dor", "md")
    _write(paths.state_dir() / "cursors" / "notion.json.from-dor", "{}")
    _write(paths.data_dir() / "research" / "r.json.from-h2t", "{}")
    texts = _texts("from-copies")
    assert len(texts) == 5, texts
    exa = [t for t in texts if "exa.env.from-dor" in t]
    assert exa == [f"~/.h2t/secrets/shared/exa.env.from-dor: EXA_API_KEY (len {len(SECRET)}, sha256 "
                   f"{storage_doctor._sha12(SECRET.encode())})"]
    for part in ("secrets/local/telegram.session.from-config", "records/sessions/m/p/s.md.from-dor",
                 "state/cursors/notion.json.from-dor", "data/research/r.json.from-h2t"):
        assert any(part in t and ": sha256 " in t for t in texts), part
    assert all(SECRET not in t for t in texts)


def test_numbered_from_copies_are_listed_by_key_and_session_copies_by_hash():
    """A second clash gives <stem>-2.from-<source> (store.unique_name): an env copy shows its
    keys, as the first one does; a session md's copies show their hash (Task 23)."""
    _write(paths.secrets_shared() / "meetgeek.env-2.from-dor", f"MEETGEEK_API_KEY={SECRET}\n")
    leaf = paths.records("sessions") / "m" / "p"
    _write(leaf / "s.md.from-dor", "fake-md-dor")
    _write(leaf / "s.md-2.from-dor", "fake-md-dor-2")
    texts = _texts("from-copies")
    assert f"~/.h2t/secrets/shared/meetgeek.env-2.from-dor: MEETGEEK_API_KEY (len {len(SECRET)}, " \
           f"sha256 {storage_doctor._sha12(SECRET.encode())})" in texts
    for name, body in (("s.md.from-dor", "fake-md-dor"), ("s.md-2.from-dor", "fake-md-dor-2")):
        assert f"~/.h2t/records/sessions/m/p/{name}: sha256 {storage_doctor._sha12(body.encode())}" in texts
    assert all(SECRET not in t for t in texts)


def test_from_copy_that_is_not_utf8_is_unreadable_and_doctor_exits_0(capsys):
    p = paths.secrets_shared() / "exa.env.from-dor"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"EXA_API_KEY=\xff\xfe\n")
    assert cli._doctor() == 0
    out = capsys.readouterr().out
    assert "storage: info from-copies: ~/.h2t/secrets/shared/exa.env.from-dor: UNREADABLE (UnicodeDecodeError)" in out


def test_stale_temp_older_than_a_day(tmp_path):
    old = _write(paths.state_dir() / ".index.sqlite.ab12.h2t-tmp")
    lake = tmp_path / "lake"
    stale_in_lake = _write(lake / ".rec.mp4.cd34.h2t-tmp")
    _write(paths.records("activity") / ".m.jsonl.ef56.h2t-tmp")             # fresh
    day_ago = time.time() - 2 * 24 * 3600
    for p in (old, stale_in_lake):
        os.utime(p, (day_ago, day_ago))
    _paths_yaml(f"version: 1\nplaces:\n  lake: {lake}\n")
    assert sorted(_texts("stale-temp")) == sorted([
        "~/.h2t/state/.index.sqlite.ab12.h2t-tmp (12 bytes) is left from a killed write; remove it by hand",
        f"{stale_in_lake} (12 bytes) is left from a killed write; remove it by hand"])
    assert old.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows: the profile ACL protects (§11.3)")
def test_perms_on_posix():
    base = paths.root() / "secrets"
    good = _write(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa-perms\n")
    bad = _write(paths.secrets_local() / "google.token.json", '{"refresh_token": "fake-google-refresh"}')
    for d in (base, paths.secrets_shared(), paths.secrets_local()):
        d.chmod(0o700)
    good.chmod(0o600)
    bad.chmod(0o644)
    paths.secrets_shared().chmod(0o755)
    assert sorted(_texts("perms")) == ["~/.h2t/secrets/local/google.token.json is 0644, expected 0600",
                                       "~/.h2t/secrets/shared is 0755, expected 0700"]
    assert _levels("perms") == {"error"}


def test_report_never_prints_a_value(config_repo, capsys):
    _write(config_repo / "secrets" / "x.env", f"EXA_API_KEY={SECRET}\n")
    subprocess.run(["git", "-C", str(config_repo), "add", "secrets/x.env"], check=True)
    _write(paths.secrets_shared() / "exa.env", f"EXA_API_KEY={SECRET}\n")
    _write(paths.secrets_shared() / "exa.env.from-dor", f"EXA_API_KEY={SECRET}\n")
    _write(paths.secrets_local() / "telegram.session.from-config", SECRET)
    assert cli._doctor() == 0
    out = capsys.readouterr().out
    assert "storage: ERROR secret-tracked:" in out and "from-copies" in out
    assert SECRET not in out


def test_doctor_prints_storage_after_secrets_and_exits_0(capsys):
    assert cli._doctor() == 0
    lines = capsys.readouterr().out.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("storage: "))
    assert lines[first - 1].startswith("secrets: gmail token=")
    assert lines[first] == "storage: layout none, root ~/.h2t"


def test_index_missing_is_info_not_a_write():
    assert _texts("index-schema") == ["~/.h2t/state/index.sqlite is not built yet; the first "
                                      "session-start or h2t-ops index rebuild builds it"]
    assert _levels("index-schema") == {"info"}
    assert not paths.state_dir().exists()


def _granola_with_a_foreign_file() -> Path:
    from h2t_ops.core.lake import ConnectorDir, manifest_line
    cdir = ConnectorDir("granola")
    _write(cdir.root / "summaries" / "n2.md", "fake-users-own-note")        # there before publish
    assert cdir.publish({"summaries/n1.md": b"fake-n1", "summaries/n2.md": b"fake-n2"}, op_id="o1") \
        == ["summaries/n2.md"]
    with cdir.manifest.open("a", encoding="utf-8") as fh:                   # a kill after pending
        fh.write(manifest_line({"op": "o2", "state": "pending",
                                "files": {"transcripts/n3.md": {"sha256": "0" * 64, "owned_before": False}}}) + "\n")
        fh.write(manifest_line({"note_id": "n4", "include": ["summaries"]}) + "\n")   # a 3.x row
    _write(cdir.root / "transcripts" / "n3.md", "fake-other-bytes")
    _write(cdir.root / "summaries" / "n4.md", "fake-3x-note")
    return cdir.root


def test_foreign_file_on_a_connector_create_path():
    root = _granola_with_a_foreign_file()
    assert root == paths.data_dir() / "lake" / "granola"
    tail = "is not granola's own (its manifest does not list it); the connector leaves it untouched"
    assert _texts("foreign-file") == [f"~/.h2t/data/lake/granola/summaries/n2.md {tail}",
                                      f"~/.h2t/data/lake/granola/transcripts/n3.md {tail}"]
    assert (root / "summaries" / "n2.md").read_text() == "fake-users-own-note"


def test_broken_paths_yaml_is_one_line_and_other_checks_still_run(capsys):
    _paths_yaml("version: 1\nplaces: [unclosed\n")
    _write(paths.config_dir() / "domains.yaml.bak")
    found = check()
    broken = [f for f in found if f.code == "paths-yaml"]
    assert len(broken) == 1 and broken[0].level == "error"
    text = broken[0].text
    assert text.startswith("~/.h2t/config/paths.yaml: is not valid YAML: ") and "\n" not in text
    assert str(paths.home()) not in text
    assert "— fix the file or remove it" in text
    assert {"place-unset", "config-backup", "secret-tracked"} <= {f.code for f in found}
    assert cli._doctor() == 0
    out = capsys.readouterr().out.splitlines()
    i = next(n for n, line in enumerate(out) if "paths-yaml" in line)
    assert out[i].startswith("storage: ERROR paths-yaml: ~/.h2t/config/paths.yaml: ")
    assert out[i + 1].startswith("storage: ")


def _tree(home: Path) -> dict:
    out = {}
    for d, dirs, files in os.walk(home):
        for name in dirs + files:
            p = Path(d) / name
            st = os.lstat(p)
            out[str(p.relative_to(home))] = (st.st_mode, st.st_mtime_ns,
                                             p.read_bytes() if p.is_file() and not p.is_symlink() else None)
    return out


def test_doctor_leaves_the_tree_byte_identical():
    """doctor is a report: no log row, no lock, no directory, no chmod, no commit (#451)."""
    _index("1")
    _granola_with_a_foreign_file()
    _write(paths.secrets_shared() / "exa.env.from-dor", f"EXA_API_KEY={SECRET}\n")
    _write(paths.records("sessions") / "m" / "p" / "s.md.from-dor", "fake-md")
    (paths.root() / "state" / "index.sqlite").chmod(0o644)
    logs = paths.logs_dir()
    if logs.exists():                                    # publish above logged its writes
        import shutil
        shutil.rmtree(logs)
    before = _tree(paths.home())
    time.sleep(0.01)
    assert cli._doctor() == 0
    after = _tree(paths.home())
    assert after == before, sorted(set(after) ^ set(before)) or \
        [k for k in after if after[k] != before[k]]
    assert not logs.exists()


@pytest.mark.parametrize("failure, why", [
    ("missing", "git ls-files could not run (FileNotFoundError"),
    ("timeout", "git ls-files timed out after 30 s"),
    ("exit", "git ls-files exited 128: fatal: fake-broken-index"),
])
def test_git_failure_is_reported_not_skipped(monkeypatch, failure, why):
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[:1] == ["git"] and "ls-files" in cmd:
            if failure == "missing":
                raise FileNotFoundError(2, "No such file or directory", "git")
            if failure == "timeout":
                raise subprocess.TimeoutExpired(cmd, 30)
            return subprocess.CompletedProcess(cmd, 128, b"", b"fatal: fake-broken-index\n")
        return real(cmd, *a, **k)

    monkeypatch.setattr(storage_doctor.subprocess, "run", fake)
    found = [f for f in check() if f.code == "secret-tracked"]
    assert len(found) == 1 and found[0].level == "warn"
    assert found[0].text.startswith(f"UNREADABLE ~/.h2t/config: {why}")


def test_a_cyclic_yaml_alias_does_not_hang_the_key_walk():
    """`loop: &a [*a]` is a list containing itself; the walk must end and still report a
    secret key placed elsewhere in the document. A subprocess, because a spinning thread
    cannot be killed and would hang the suite instead of failing it."""
    code = ("from h2t_ops.setup.storage_doctor import _structured_keys as k;"
            "print(k('x.yaml', b'loop: &a [*a]\\nnested:\\n  client_secret: s3cret\\n'))")
    try:
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              timeout=10)
    except subprocess.TimeoutExpired:
        pytest.fail("_structured_keys did not return on a cyclic alias within 10s")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['client_secret']"


def test_git_show_failure_names_the_file(monkeypatch):
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[:1] == ["git"] and "show" in cmd and cmd[-1] == ":notes.md":
            return subprocess.CompletedProcess(cmd, 1, b"", b"fatal: fake-bad-object\n")
        return real(cmd, *a, **k)

    monkeypatch.setattr(storage_doctor.subprocess, "run", fake)
    texts = _texts("secret-tracked")
    assert "UNREADABLE ~/.h2t/config/notes.md: git show exited 1: fatal: fake-bad-object" in texts
    assert "~/.h2t/config/secrets/x.env holds a value for EXA_API_KEY and is tracked by git" in texts


def test_one_check_failing_does_not_blank_the_others(monkeypatch):
    def boom():
        raise PermissionError(13, "Permission denied", "fake-path")

    monkeypatch.setattr(storage_doctor, "_perms", boom)
    found = check()
    assert [f.text for f in found if f.code == "perms"] == [
        "UNREADABLE: the check stopped (PermissionError: [Errno 13] Permission denied: 'fake-path')"]
    assert {"secret-tracked", "place-unset"} <= {f.code for f in found}
