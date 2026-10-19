"""Doctors report what they checked, the way the code they vouch for does (#451)."""
import os
import sys
from pathlib import Path

import pytest

from h2t_ops import cli
from h2t_ops.core import paths
from h2t_ops.lifecycle.activity import writer as activity_writer
from h2t_ops.setup import legacy as setup_h2t


def _no_host_overrides(monkeypatch):
    for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME"):
        monkeypatch.delenv(var, raising=False)


def test_plugin_cache_found_under_any_marketplace_newest_last(tmp_path, monkeypatch):
    _no_host_overrides(monkeypatch)
    for version in ("3.2.9", "3.2.10"):
        (tmp_path / ".claude" / "plugins" / "cache" / "my-fork" / "h2t-core" / version).mkdir(parents=True)

    status = setup_h2t.plugin_cache_status(tmp_path)

    assert status["status"] == "present"
    assert Path(status["latest"]).name == "3.2.10"
    assert Path(status["h2t_core_cache"]).parent.name == "my-fork"


def test_plugin_cache_found_under_codex(tmp_path, monkeypatch):
    _no_host_overrides(monkeypatch)
    (tmp_path / ".codex" / "plugins" / "cache" / "lichtpfad" / "h2t-core" / "local").mkdir(parents=True)

    assert setup_h2t.plugin_cache_status(tmp_path)["status"] == "present"


def test_plugin_cache_missing_when_nothing_is_installed(tmp_path, monkeypatch):
    _no_host_overrides(monkeypatch)

    assert setup_h2t.plugin_cache_status(tmp_path)["status"] == "missing"


def test_plugin_cache_names_the_directory_it_searched(tmp_path, monkeypatch):
    """CLAUDE_CONFIG_DIR set and empty: the report must not point at ~/.claude (#522)."""
    _no_host_overrides(monkeypatch)
    config = tmp_path / "cfg"
    config.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    (tmp_path / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-core" / "3.2.55").mkdir(parents=True)

    status = setup_h2t.plugin_cache_status(tmp_path)

    assert status["status"] == "missing"
    assert Path(status["h2t_core_cache"]).is_relative_to(config)


def _executable(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX bin layout and exec bits")
def test_doctor_reports_the_users_h2t_ops_not_the_running_venvs(tmp_path, monkeypatch):
    """`uv run` inside a checkout runs from the repo .venv and puts its bin first (#523)."""
    venv = tmp_path / "repo" / ".venv"
    _executable(venv / "bin", "h2t-ops")
    users = _executable(tmp_path / "local" / "bin", "h2t-ops")
    monkeypatch.setattr(sys, "prefix", str(venv))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "python"))
    monkeypatch.setenv("PATH", f"{venv / 'bin'}:{users.parent}")

    assert setup_h2t.resolve_h2t_ops(home=tmp_path)["path"] == str(users)


def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    # core.secrets resolves its paths at call time: a tmp HOME is the whole isolation.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("H2T_PATH_ROOT", raising=False)
    secrets_dir = paths.legacy("secrets.h2t")
    secrets_dir.mkdir(parents=True)
    return secrets_dir


def test_doctor_sees_a_notion_token_kept_in_a_secrets_file(tmp_path, monkeypatch, capsys):
    secrets_dir = _home(tmp_path, monkeypatch)
    (secrets_dir / "notion.env").write_text("NOTION_API_TOKEN=secret\n", encoding="utf-8")
    try:
        cli._doctor()
    finally:
        import os
        os.environ.pop("NOTION_API_TOKEN", None)

    assert "NOTION_API_TOKEN=present" in capsys.readouterr().out


def test_doctor_does_not_take_client_credentials_for_a_gmail_token(tmp_path, monkeypatch, capsys):
    _home(tmp_path, monkeypatch)
    store = tmp_path / ".config" / "google-calendar-mcp"
    store.mkdir(parents=True)
    (store / "credentials.json").write_text("{}", encoding="utf-8")

    cli._doctor()
    out = capsys.readouterr().out

    assert "gmail token=MISSING" in out
    assert "not checked here:" in out and "telegram" in out


def _google_token(tmp_path, monkeypatch, body: str):
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text(body, encoding="utf-8")
    return token


def test_doctor_sees_a_google_token_in_secrets_local(tmp_path, monkeypatch, capsys):
    _google_token(tmp_path, monkeypatch, '{"refresh_token": "fake-r"}')
    assert cli._doctor() == 0
    assert "gmail token=present" in capsys.readouterr().out


def test_doctor_reports_a_malformed_google_token_and_exits_0(tmp_path, monkeypatch, capsys):
    _google_token(tmp_path, monkeypatch, "{not json")
    assert cli._doctor() == 0
    assert "gmail token=UNREADABLE" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_doctor_reports_an_unreadable_google_token_and_exits_0(tmp_path, monkeypatch, capsys):
    token = _google_token(tmp_path, monkeypatch, '{"refresh_token": "fake-r"}')
    token.chmod(0)
    try:
        if os.access(token, os.R_OK):
            pytest.skip("running as a user that reads 0000 files (root)")
        assert cli._doctor() == 0
    finally:
        token.chmod(0o600)
    assert "gmail token=UNREADABLE" in capsys.readouterr().out


def test_plugin_cache_orders_non_semver_dirs_by_mtime(tmp_path, monkeypatch):
    _no_host_overrides(monkeypatch)
    plugin = tmp_path / ".codex" / "plugins" / "cache" / "curated" / "h2t-core"
    older, newer = plugin / "zzzz-old-hash", plugin / "aaaa-new-hash"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    import os
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))

    assert Path(setup_h2t.plugin_cache_status(tmp_path)["latest"]).name == "aaaa-new-hash"


def test_doctor_reports_an_unreadable_secrets_file_instead_of_crashing(tmp_path, monkeypatch, capsys):
    secrets_dir = _home(tmp_path, monkeypatch)
    (secrets_dir / "notion.env").write_bytes(b"NOTION_API_TOKEN=\xff\xfe\n")

    cli._doctor()

    assert "NOTION_API_TOKEN=UNREADABLE" in capsys.readouterr().out


def test_doctor_is_a_report_and_exits_0_on_an_unconfigured_machine(tmp_path, monkeypatch, capsys):
    """#451, owner's decision: doctor reports, connectors-check gates."""
    _home(tmp_path, monkeypatch)

    assert cli._doctor() == 0
    assert "NOTION_API_TOKEN=MISSING" in capsys.readouterr().out


def test_activity_log_help_names_the_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["h2t-activity-log", "--help"])

    with pytest.raises(SystemExit):
        activity_writer.main()

    assert capsys.readouterr().out.startswith("usage: h2t-activity-log")


def _legacy_venv(home, target):
    """A ~/.h2t/venv whose `h2t` comes from an editable install pointing at `target` (#476)."""
    venv = home / ".h2t" / "venv"
    windows = sys.platform.startswith("win")
    scripts = venv / ("Scripts" if windows else "bin")
    site = venv / ("Lib/site-packages" if windows else "lib/python3.11/site-packages")
    scripts.mkdir(parents=True)
    site.mkdir(parents=True)
    (scripts / ("h2t.exe" if windows else "h2t")).write_text("", encoding="utf-8")
    dist = site / "h2t_core_cli-3.0.7.dist-info"
    dist.mkdir()
    (dist / "entry_points.txt").write_text("[console_scripts]\nh2t = lib.cli.main:main\n", encoding="utf-8")
    (site / "__editable___h2t_core_cli_3_0_7_finder.py").write_text(
        f"MAPPING: dict[str, str] = {{'lib': {str(target)!r}}}\n", encoding="utf-8"
    )


def test_doctor_reports_a_legacy_h2t_pinned_to_a_deleted_cache(tmp_path):
    _legacy_venv(tmp_path, tmp_path / "plugins" / "cache" / "h2t-core" / "3.0.7" / "lib")

    status = setup_h2t.legacy_shim_status(tmp_path)

    assert status["status"] == "stale"
    assert status["package"] == "h2t_core_cli 3.0.7"
    assert status["remediation"].startswith("uv pip uninstall --python ")


def test_doctor_is_quiet_when_the_legacy_h2t_still_resolves(tmp_path):
    target = tmp_path / "live-lib"
    target.mkdir()
    _legacy_venv(tmp_path, target)

    assert setup_h2t.legacy_shim_status(tmp_path)["status"] == "ok"


def test_doctor_is_quiet_without_a_legacy_venv(tmp_path):
    assert setup_h2t.legacy_shim_status(tmp_path) == {"status": "ok"}


def _matrix_row(tmp_path, monkeypatch, connector):
    monkeypatch.setattr(setup_h2t, "resolve_h2t_ops", lambda home=None: {"status": "missing", "path": ""})
    rows = setup_h2t.connector_matrix(tmp_path)["connectors"]
    return next(r for r in rows if r["connector"] == connector)


def _put(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_connectors_check_sees_google_files_in_the_4_0_places(tmp_path, monkeypatch):
    """client in secrets/shared, this machine's token in secrets/local (§4, R19)."""
    _home(tmp_path, monkeypatch)
    _put(paths.secrets_shared() / "google.client.json", '{"installed": {}}')
    _put(paths.secrets_local() / "google.token.json", '{"refresh_token": "fake-r"}')
    row = _matrix_row(tmp_path, monkeypatch, "calendar")
    assert row["status"] == "ready"
    assert row["checks"]["tokens"] == {"path": str(paths.secrets_local() / "google.token.json"),
                                       "status": "present"}


def test_connectors_check_reports_a_corrupt_google_token_without_crashing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    _put(paths.secrets_local() / "google.token.json", "{not json")
    row = _matrix_row(tmp_path, monkeypatch, "gmail")
    assert row["status"] == "missing" and row["checks"]["tokens"]["status"] == "unreadable"


def test_connectors_check_sees_a_key_only_in_secrets_shared(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    _put(paths.secrets_shared() / "meetgeek.env", "MEETGEEK_API_KEY=fake-mg\n")
    assert _matrix_row(tmp_path, monkeypatch, "meetgeek")["status"] == "ready"


def _no_telegram_env(monkeypatch):
    for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH"):
        monkeypatch.delenv(k, raising=False)


def test_connectors_check_sees_telegram_in_the_4_0_places(tmp_path, monkeypatch):
    """A new user: keys in shared/telegram.env, session in local (§12 acceptance)."""
    _home(tmp_path, monkeypatch)
    _no_telegram_env(monkeypatch)
    _put(paths.secrets_shared() / "telegram.env", "TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=fake-hash\n")
    _put(paths.secrets_local() / "telegram.session", "fake-session")
    row = _matrix_row(tmp_path, monkeypatch, "telegram")
    assert row["status"] == "ready"
    assert row["checks"]["session"] == {"path": str(paths.secrets_local() / "telegram.session"),
                                        "status": "present"}


def test_connectors_check_telegram_falls_back_per_key_to_the_3x_files(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    _no_telegram_env(monkeypatch)
    _put(paths.secrets_shared() / "telegram.env", "TELEGRAM_API_ID=\nTELEGRAM_API_HASH=fake-new\n")
    _put(paths.legacy("telegram") / "config.json", '{"api_id": 7, "api_hash": "fake-old"}')
    _put(paths.legacy("telegram") / "session.session", "fake-old-session")
    row = _matrix_row(tmp_path, monkeypatch, "telegram")
    assert row["status"] == "ready"
    assert row["checks"]["session"]["path"] == str(paths.legacy("telegram") / "session.session")


def test_connectors_check_telegram_missing_and_unreadable(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    _no_telegram_env(monkeypatch)
    _put(paths.secrets_shared() / "telegram.env", "TELEGRAM_API_ID=1\n")
    assert _matrix_row(tmp_path, monkeypatch, "telegram")["status"] == "missing"
    _put(paths.legacy("telegram") / "config.json", "{not json")
    row = _matrix_row(tmp_path, monkeypatch, "telegram")
    assert row["status"] == "missing" and row["checks"]["config"]["status"] == "unreadable"
