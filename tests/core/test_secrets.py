"""Tests for h2t_ops.core.secrets — token resolution via ~/.dor secrets files."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from h2t_ops.core import secrets as mod
from h2t_ops.core.errors import ConfigError


def test_resolve_notion_token_reads_secrets_env(tmp_path, monkeypatch):
    """Audit #144: when NOTION_API_TOKEN lives in a secrets.env file and no
    other source is present, resolve_notion_token() must find it (parity with
    the import-time load_dotenv in lib/clients/notion.py, retired in #356).

    NOTE: load_secrets() mutates os.environ directly (not via monkeypatch), so
    we must clean NOTION_API_TOKEN explicitly to avoid leaking it into sibling
    tests.
    """
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=secret_t1_value\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", secrets_file)
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "no-legacy-secrets")
    # Route ~/.config/notion/token to a nonexistent path so only secrets.env can satisfy.
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    try:
        assert mod.resolve_notion_token() == "secret_t1_value"
    finally:
        # load_secrets() set this key in os.environ outside monkeypatch's bookkeeping;
        # pop it so the next test starts clean.
        os.environ.pop("NOTION_API_TOKEN", None)


def test_resolve_notion_token_env_var_wins_over_secrets_env(tmp_path, monkeypatch):
    """Explicit env vars must keep precedence — load_secrets is no-override.

    monkeypatch.setenv is tracked by pytest and reverted at teardown, so no
    manual cleanup is needed here.
    """
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("NOTION_API_TOKEN=from_file\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", secrets_file)
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "no-legacy-secrets")
    monkeypatch.setenv("NOTION_API_TOKEN", "from_env")
    assert mod.resolve_notion_token() == "from_env"


def test_resolve_notion_token_missing_everywhere_raises_configerror(tmp_path, monkeypatch):
    """No env, no secrets.env, no ~/.config/notion/token → typed ConfigError.

    secrets.env does not exist here, so load_secrets() returns early and does
    not mutate os.environ; no extra cleanup needed.
    """
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "no-such-secrets")
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "no-legacy-secrets")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    with pytest.raises(ConfigError):
        mod.resolve_notion_token()


def test_resolve_notion_token_config_file_fallback(tmp_path, monkeypatch):
    """When env and secrets.env are absent, ~/.config/notion/token must be read."""
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "no-such-secrets")
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "no-legacy-secrets")
    cfg = tmp_path / ".config" / "notion" / "token"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("filetok\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert mod.resolve_notion_token() == "filetok"


def test_resolve_notion_token_configerror_hint_mentions_token(tmp_path, monkeypatch):
    """ConfigError.hint must guide the operator to set NOTION_API_TOKEN."""
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "no-such-secrets")
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "no-legacy-secrets")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "nonexistent_home")
    with pytest.raises(ConfigError) as ei:
        mod.resolve_notion_token()
    assert ei.value.hint and "NOTION_API_TOKEN" in ei.value.hint


def test_load_secrets_is_non_override(tmp_path, monkeypatch):
    """load_secrets() must NOT override existing env vars, but must insert new keys."""
    monkeypatch.setenv("FOO", "shell")
    env = tmp_path / "secrets.env"
    env.write_text("FOO=file\nBAR=baz\n", encoding="utf-8")
    try:
        mod.load_secrets(env_file=env)
        assert os.environ["FOO"] == "shell"
        assert os.environ["BAR"] == "baz"
    finally:
        # BAR is set by load_secrets() outside monkeypatch's bookkeeping; pop it.
        os.environ.pop("BAR", None)
        # FOO is set via monkeypatch.setenv and will be auto-reverted at teardown.


def test_load_secrets_prefers_canonical_then_legacy(tmp_path, monkeypatch):
    """Canonical secrets load first; legacy file only fills missing keys."""
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAR", raising=False)
    canonical = tmp_path / ".dor" / "secrets" / "secrets.env"
    legacy = tmp_path / ".dor" / "secrets.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("FOO=canonical\n", encoding="utf-8")
    legacy.write_text("FOO=legacy\nBAR=legacy-only\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", canonical)
    monkeypatch.setattr(mod, "LEGACY_SECRETS", legacy)

    try:
        mod.load_secrets()
        assert os.environ["FOO"] == "canonical"
        assert os.environ["BAR"] == "legacy-only"
    finally:
        os.environ.pop("FOO", None)
        os.environ.pop("BAR", None)


def test_load_secrets_h2t_secrets_file_override(tmp_path, monkeypatch):
    """H2T_SECRETS_FILE gives tests and multi-account setups an explicit source."""
    monkeypatch.delenv("FOO", raising=False)
    env_file = tmp_path / "override.env"
    env_file.write_text("FOO=override\n", encoding="utf-8")
    monkeypatch.setenv(mod.ENV_OVERRIDE, str(env_file))
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "canonical")
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "legacy")

    try:
        mod.load_secrets()
        assert os.environ["FOO"] == "override"
    finally:
        os.environ.pop("FOO", None)
