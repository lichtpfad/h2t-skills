"""Doctors report what they checked, the way the code they vouch for does (#451)."""
import sys
from pathlib import Path

from h2t_ops import cli
from h2t_ops.core import secrets as core_secrets

SCRIPTS_DIR = Path(__file__).parent.parent / "plugins" / "h2t-core" / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import setup_h2t  # noqa: E402


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


def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    secrets_dir = tmp_path / ".h2t" / "config" / "secrets"
    secrets_dir.mkdir(parents=True)
    monkeypatch.setattr(core_secrets, "H2T_CONFIG_SECRETS", secrets_dir / "secrets.env")
    monkeypatch.setattr(core_secrets, "DEFAULT_SECRETS", tmp_path / "absent-dor.env")
    monkeypatch.setattr(core_secrets, "LEGACY_SECRETS", tmp_path / "absent-legacy.env")
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
