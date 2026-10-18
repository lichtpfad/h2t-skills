"""doctor's storage checks (#548 §7.4): one test per code, each on a minimal state built in
the test's own HOME — a config git repo with secrets/x.env tracked in it, as at the author's."""
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


def _write(p: Path, text: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def config_repo():
    cfg = paths.config_dir()
    _write(cfg / "secrets" / "x.env", "EXA_API_KEY=fake\n")
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
    for name in ("state", "records", "sessions", "activity", "evals", "research", "creative"):
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
        "H2T_LAKE_ROOT": "the value moved to paths.yaml (lake)",
        "H2T_SECRETS_FILE": "the migration read that file as a secrets source",
        "H2T_EVALS_SPOOL": "the migration copied that spool into state/evals-spool.sqlite",
        **{n: "the package does not read it — remove it" for n in
           ("H2T_CONFIG_ROOT", "H2T_SESSION_ROOT", "H2T_ACTIVITY_SPOOL", "H2T_EVALS_ROOT")}}


def test_place_missing_for_paths_yaml_and_vault(tmp_path):
    _paths_yaml(f"version: 1\nplaces:\n  lake: {tmp_path / 'no-lake'}\n")
    texts = _texts("place-missing")
    assert f"lake {tmp_path / 'no-lake'} does not exist" in texts
    assert any(t.startswith("vault ~/.dor/vault does not exist") for t in texts)
    (tmp_path / "no-lake").mkdir()
    (paths.vault()).mkdir(parents=True)
    assert _texts("place-missing") == []


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


def test_from_copy_that_is_not_utf8_is_unreadable_and_doctor_exits_0(capsys):
    p = paths.secrets_shared() / "exa.env.from-dor"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"EXA_API_KEY=\xff\xfe\n")
    assert cli._doctor() == 0
    out = capsys.readouterr().out
    assert "storage: info from-copies: ~/.h2t/secrets/shared/exa.env.from-dor: UNREADABLE (UnicodeDecodeError)" in out


def test_stale_temp_older_than_a_day(tmp_path):
    old = _write(paths.state_dir() / ".index.sqlite.ab12.h2t-tmp", "12345")
    lake = tmp_path / "lake"
    stale_in_lake = _write(lake / ".rec.mp4.cd34.h2t-tmp", "1")
    _write(paths.records("activity") / ".m.jsonl.ef56.h2t-tmp")             # fresh
    day_ago = time.time() - 2 * 24 * 3600
    for p in (old, stale_in_lake):
        os.utime(p, (day_ago, day_ago))
    _paths_yaml(f"version: 1\nplaces:\n  lake: {lake}\n")
    assert sorted(_texts("stale-temp")) == sorted([
        "~/.h2t/state/.index.sqlite.ab12.h2t-tmp (5 bytes) is left from a killed write; remove it by hand",
        f"{stale_in_lake} (1 bytes) is left from a killed write; remove it by hand"])
    assert old.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows: the profile ACL protects (§11.3)")
def test_perms_on_posix():
    base = paths.root() / "secrets"
    good = _write(paths.secrets_shared() / "exa.env")
    bad = _write(paths.secrets_local() / "google.token.json")
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
