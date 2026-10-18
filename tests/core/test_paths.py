import os
import sys
from pathlib import Path

import pytest

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV \
                or k in ("H2T_MACHINE_NAME", "DOR_MACHINE_NAME", "CLAUDE_CONFIG_DIR"):
            monkeypatch.delenv(k, raising=False)
    return h


def _yaml(home, text):
    p = home / ".h2t" / "config" / "paths.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_classes_live_under_root(home):
    assert paths.dir_of("secrets.shared") == home / ".h2t" / "secrets" / "shared"
    assert paths.records("sessions", "mac") == home / ".h2t" / "records" / "sessions" / "mac"
    assert paths.run_dir() == home / ".h2t" / "run"


def test_root_override_moves_everything_but_run(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.dir_of("state") == tmp_path / "r" / "state"
    assert paths.dir_of("layout") == tmp_path / "r" / "layout.json" == paths.layout_file()
    assert paths.run_dir() == home / ".h2t" / "run"


def test_old_env_names_are_reported_not_read(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "old-sessions"))
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "a" / "spool.jsonl"))
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "old-lake"))
    monkeypatch.setenv("H2T_PATH_RECORDS", str(tmp_path / "rec"))  # never existed in 4.0
    assert paths.dir_of("records.sessions") == home / ".h2t" / "records" / "sessions"
    assert paths.activity_file("mac") == home / ".h2t" / "records" / "activity" / "mac.jsonl"
    assert paths.records("evals") == home / ".h2t" / "records" / "evals"
    assert paths.place("lake") is None
    assert paths.old_env_in_use() == ["H2T_ACTIVITY_SPOOL", "H2T_LAKE_ROOT", "H2T_SESSION_ROOT"]
    assert paths.old_env("H2T_LAKE_ROOT") == tmp_path / "old-lake"


def test_old_env_by_use_groups_set_names_by_their_fate(home, monkeypatch, tmp_path):
    """R22: callers outside paths.py ask by use and never spell the old names."""
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "old-lake"))
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "old-sessions"))
    assert paths.old_env_by_use("lake") == {"H2T_LAKE_ROOT": tmp_path / "old-lake"}
    assert paths.old_env_by_use("remove") == {"H2T_SESSION_ROOT": tmp_path / "old-sessions"}
    assert paths.old_env_by_use("secrets-source") == {}


def test_validate_config_checks_a_document_in_memory(home):
    """R34: `paths set` validates the new document without reading the file on disk."""
    assert not paths.paths_yaml().exists()
    with pytest.raises(ConfigError, match="absolute"):
        paths.validate_config({"version": 1, "places": {"lake": "relative"}}, source=Path("x"))


def test_external_place_from_yaml(home, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n")
    assert paths.place("lake") == tmp_path / "lake"
    assert paths.place("inbox") is None
    assert paths.place_or_default("inbox") == (home / ".h2t" / "data" / "inbox", True)


def test_vault_from_env_with_pos_default(home, monkeypatch, tmp_path):
    assert paths.vault() == paths.place("vault") == home / ".dor" / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "v"))
    assert paths.place("vault") == tmp_path / "v"


def test_vault_in_paths_yaml_is_rejected(home, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  vault: {tmp_path / 'v'}\n")
    with pytest.raises(ConfigError, match="H2T_PATH_VAULT"):
        paths.place("lake")


def test_legacy_root_equal_to_a_declared_place_is_not_legacy(home):
    _yaml(home, "version: 1\nplaces:\n  lake: ~/.dor/lake\n")
    roots = paths.legacy_roots()
    assert home / ".dor" / "lake" not in roots
    assert home / ".dor" in roots          # dir of the file-valued entries (secrets.env, …)
    assert home / ".dor" / "vault" not in roots


def test_tilde_in_yaml_expands(home):
    _yaml(home, "version: 1\nplaces:\n  kb: ~/kb\n")
    assert paths.place("kb") == home / "kb"


def test_overlapping_places_are_rejected(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "v"))
    _yaml(home, f"version: 1\nplaces:\n  inbox: {tmp_path / 'v' / 'in'}\n")
    with pytest.raises(ConfigError, match="vault.*inbox|inbox.*vault"):
        paths.place("lake")


def test_place_inside_root_is_rejected(home):
    _yaml(home, f"version: 1\nplaces:\n  lake: {home / '.h2t' / 'lake'}\n")
    with pytest.raises(ConfigError, match="lake"):
        paths.place("lake")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_place_through_symlink_into_root_is_rejected(home, tmp_path):
    (home / ".h2t" / "data").mkdir(parents=True)
    link = tmp_path / "innocent"
    link.symlink_to(home / ".h2t" / "data")
    _yaml(home, f"version: 1\nplaces:\n  inbox: {link}\n")
    with pytest.raises(ConfigError, match="inbox"):
        paths.place("inbox")


def test_relative_place_is_rejected(home):
    _yaml(home, "version: 1\nplaces:\n  lake: relative/lake\n")
    with pytest.raises(ConfigError, match="absolute"):
        paths.place("lake")


def test_machine_name_order(home, monkeypatch):
    monkeypatch.setattr(paths.platform, "node", lambda: "Host-X.local")
    assert paths.machine_name() == "host-x"
    monkeypatch.setenv("DOR_MACHINE_NAME", "dor")
    assert paths.machine_name() == "dor"
    monkeypatch.setenv("H2T_MACHINE_NAME", "h2t")
    assert paths.machine_name() == "h2t"
    assert not (home / ".h2t" / "state").exists()   # no file pins the name (plan R4)


def test_legacy_places_are_home_relative_and_ignore_root(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.legacy("google.store") == home / ".config" / "google-calendar-mcp"
    assert paths.legacy("sessions.dor") == home / ".dor" / "sessions"


@pytest.mark.parametrize("body", [
    b"version: 1\nplaces: [lake]\n",
    b"version: 1\nsync: [x]\n",
    b"version: 1\nplaces:\n  lake: /tmp/\xff\xfe\n",
    b"version: 1\nplaces:\n  lake: ~no-such-user-h2t-test/lake\n",
    b'version: 1\nplaces:\n  lake: "/tmp/a\\0b"\n',
    b"version: 1\nvault_rules: ~no-such-user-h2t-test/rules.md\n",
], ids=["places-list", "sync-list", "not-utf8", "unknown-user", "nul", "rules-unknown-user"])
def test_broken_paths_yaml_is_a_config_error_and_legacy_roots_survive(home, body):
    """R17: a broken paths.yaml must not stop legacy classification (spec §7.2), nor an
    internal write such as the activity row handoff appends."""
    from h2t_ops.core import store
    p = home / ".h2t" / "config" / "paths.yaml"
    p.parent.mkdir(parents=True)
    p.write_bytes(body)
    with pytest.raises(ConfigError, match="paths.yaml"):
        paths.paths_config()
    assert home / ".dor" in paths.legacy_roots()
    store.append(paths.activity_file("m"), "{}", place="records.activity")
    assert paths.activity_file("m").read_text() == "{}\n"


def test_null_places_and_sync_are_empty(home):
    _yaml(home, "version: 1\nplaces:\nsync:\n")
    assert paths.paths_config() == paths.PathsConfig()
