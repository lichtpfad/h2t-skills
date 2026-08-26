"""Tests for h2t_ops.core.secrets — token resolution via ~/.dor secrets files."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from h2t_ops.core import secrets as mod
from h2t_ops.core.errors import ConfigError


@pytest.fixture(autouse=True)
def _isolate_documented_secrets(tmp_path_factory, monkeypatch):
    """Point H2T_CONFIG_SECRETS somewhere that does not exist, for every test here.

    #432 added ~/.h2t/config/secrets/secrets.env as the first candidate. The tests below
    patch DEFAULT_SECRETS and LEGACY_SECRETS but knew nothing about the third path, so they
    would fall through to the developer's real one — green on a machine that happens not to
    have it, and a statement about that machine rather than about the code. A test that
    wants the documented path patches it explicitly.
    """
    monkeypatch.setattr(
        mod, "H2T_CONFIG_SECRETS",
        tmp_path_factory.mktemp("no-h2t-config") / "secrets.env",
    )


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


def test_the_documented_secrets_path_is_actually_read(tmp_path, monkeypatch):
    """#432: every user-facing message names ~/.h2t/config/secrets/, and nothing read it.

    A new user put keys there, every command answered MISSING, and the hint pointed
    somewhere else again. This is the control for the fix: a key that exists *only* in the
    documented location must resolve.
    """
    monkeypatch.delenv("DOCUMENTED_ONLY", raising=False)
    documented = tmp_path / ".h2t" / "config" / "secrets" / "secrets.env"
    documented.parent.mkdir(parents=True)
    documented.write_text("DOCUMENTED_ONLY=yes\n", encoding="utf-8")
    monkeypatch.setattr(mod, "H2T_CONFIG_SECRETS", documented)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", tmp_path / "absent-dor")
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "absent-legacy")
    try:
        mod.load_secrets()
        assert os.environ["DOCUMENTED_ONLY"] == "yes"
    finally:
        os.environ.pop("DOCUMENTED_ONLY", None)


def test_an_existing_install_is_untouched_by_the_new_candidate(tmp_path, monkeypatch):
    """The negative control. Adding a candidate must not change a machine that has none.

    Without this, the test above is satisfied by a change that reads the documented path
    and nothing else — which would break both existing machines silently.
    """
    monkeypatch.delenv("SHARED_ONLY", raising=False)
    dor = tmp_path / ".dor" / "secrets" / "secrets.env"
    dor.parent.mkdir(parents=True)
    dor.write_text("SHARED_ONLY=still-here\n", encoding="utf-8")
    monkeypatch.setattr(mod, "H2T_CONFIG_SECRETS", tmp_path / ".h2t" / "absent.env")
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", dor)
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "absent-legacy")
    try:
        mod.load_secrets()
        assert os.environ["SHARED_ONLY"] == "still-here"
    finally:
        os.environ.pop("SHARED_ONLY", None)


def test_the_documented_path_wins_a_tie(tmp_path, monkeypatch):
    """Both present: the location the messages name is the one that answers."""
    monkeypatch.delenv("WHO_WINS", raising=False)
    documented = tmp_path / ".h2t" / "config" / "secrets" / "secrets.env"
    documented.parent.mkdir(parents=True)
    documented.write_text("WHO_WINS=documented\n", encoding="utf-8")
    dor = tmp_path / ".dor" / "secrets" / "secrets.env"
    dor.parent.mkdir(parents=True)
    dor.write_text("WHO_WINS=shared\n", encoding="utf-8")
    monkeypatch.setattr(mod, "H2T_CONFIG_SECRETS", documented)
    monkeypatch.setattr(mod, "DEFAULT_SECRETS", dor)
    monkeypatch.setattr(mod, "LEGACY_SECRETS", tmp_path / "absent-legacy")
    try:
        mod.load_secrets()
        assert os.environ["WHO_WINS"] == "documented"
    finally:
        os.environ.pop("WHO_WINS", None)
