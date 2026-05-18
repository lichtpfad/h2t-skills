import os
import pytest
from h2t.core.secrets import resolve_notion_token, load_secrets
from h2t.core.errors import ConfigError


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("NOTION_API_TOKEN", "envtok")
    assert resolve_notion_token() == "envtok"


def test_config_file_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    cfg = tmp_path / ".config" / "notion" / "token"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("filetok\n")
    monkeypatch.setattr("h2t.core.secrets.Path.home", lambda: tmp_path)
    assert resolve_notion_token() == "filetok"


def test_missing_raises_configerror(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr("h2t.core.secrets.Path.home", lambda: tmp_path)
    with pytest.raises(ConfigError) as ei:
        resolve_notion_token()
    assert ei.value.hint and "NOTION_API_TOKEN" in ei.value.hint


def test_load_secrets_is_non_override(tmp_path, monkeypatch):
    monkeypatch.setenv("FOO", "shell")
    env = tmp_path / "secrets.env"
    env.write_text("FOO=file\nBAR=baz\n")
    load_secrets(env_file=env)
    assert os.environ["FOO"] == "shell" and os.environ["BAR"] == "baz"
