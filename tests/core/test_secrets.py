"""Tests for h2t_ops.core.secrets — the 3.x ladder, read as the 4.0.x fallback.

secrets.py resolves every path at call time through core.paths, so HOME and USERPROFILE
pointed at tmp are the whole isolation: no module constant fixes a path at import any more.
The new places (secrets/shared) are in test_secrets_v4.py; these pin that the 3.x order
still holds for a provider that has no new file yet.
"""
from __future__ import annotations

import os

import pytest

from h2t_ops.core import paths
from h2t_ops.core import secrets as mod
from h2t_ops.core.errors import ConfigError

TOUCHED = ("NOTION_API_TOKEN", "FOO", "BAR", "DOCUMENTED_ONLY", "SHARED_ONLY", "WHO_WINS",
           "PROVIDER_ONLY", "SHELL_WINS")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """An empty home for every test. load_secrets() writes os.environ outside monkeypatch's
    bookkeeping, so the keys it may set are popped at teardown."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV or k in TOUCHED:
            monkeypatch.delenv(k, raising=False)
    yield h
    for k in TOUCHED:
        os.environ.pop(k, None)


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_resolve_notion_token_reads_secrets_env(home):
    """Audit #144: a NOTION_API_TOKEN kept only in a secrets file must be found."""
    _w(paths.legacy("secrets.dor"), "NOTION_API_TOKEN=fake-t1\n")
    assert mod.resolve_notion_token() == "fake-t1"


def test_resolve_notion_token_env_var_wins_over_secrets_env(home, monkeypatch):
    _w(paths.legacy("secrets.dor"), "NOTION_API_TOKEN=fake-file\n")
    monkeypatch.setenv("NOTION_API_TOKEN", "fake-env")
    assert mod.resolve_notion_token() == "fake-env"


def test_resolve_notion_token_missing_everywhere_raises_configerror(home):
    with pytest.raises(ConfigError):
        mod.resolve_notion_token()


def test_resolve_notion_token_config_file_fallback(home):
    """When env and every secrets file are absent, ~/.config/notion/token is read."""
    _w(paths.legacy("notion.token"), "fake-filetok\n")
    assert mod.resolve_notion_token() == "fake-filetok"


def test_resolve_notion_token_configerror_hint_mentions_token(home):
    with pytest.raises(ConfigError) as ei:
        mod.resolve_notion_token()
    assert ei.value.hint and "NOTION_API_TOKEN" in ei.value.hint


def test_load_secrets_is_non_override(tmp_path, monkeypatch):
    """load_secrets() must NOT override existing env vars, but must insert new keys."""
    monkeypatch.setenv("FOO", "shell")
    env = tmp_path / "secrets.env"
    env.write_text("FOO=file\nBAR=baz\n", encoding="utf-8")
    mod.load_secrets(env_file=env)
    assert os.environ["FOO"] == "shell"
    assert os.environ["BAR"] == "baz"


def test_load_secrets_prefers_canonical_then_legacy(home):
    """~/.dor/secrets/secrets.env first; ~/.dor/secrets.env only fills missing keys."""
    _w(paths.legacy("secrets.dor"), "FOO=canonical\n")
    _w(paths.legacy("secrets.dor_old"), "FOO=legacy\nBAR=legacy-only\n")
    mod.load_secrets()
    assert os.environ["FOO"] == "canonical"
    assert os.environ["BAR"] == "legacy-only"


def test_load_secrets_ignores_h2t_secrets_file(home, monkeypatch, tmp_path):
    """3.x read H2T_SECRETS_FILE instead of every default; 4.0 does not read it (R5)."""
    env_file = tmp_path / "override.env"
    env_file.write_text("FOO=override\n", encoding="utf-8")
    _w(paths.legacy("secrets.dor"), "FOO=ladder\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(env_file))
    mod.load_secrets()
    assert os.environ["FOO"] == "ladder"


def test_the_documented_secrets_path_is_actually_read(home):
    """#432: a key that exists *only* in ~/.h2t/config/secrets/secrets.env must resolve."""
    _w(paths.legacy("secrets.h2t") / "secrets.env", "DOCUMENTED_ONLY=yes\n")
    mod.load_secrets()
    assert os.environ["DOCUMENTED_ONLY"] == "yes"


def test_an_existing_install_is_untouched_by_the_new_candidate(home):
    """The negative control: a machine with only ~/.dor/secrets/secrets.env still resolves."""
    _w(paths.legacy("secrets.dor"), "SHARED_ONLY=still-here\n")
    mod.load_secrets()
    assert os.environ["SHARED_ONLY"] == "still-here"


def test_the_documented_path_wins_a_tie(home):
    _w(paths.legacy("secrets.h2t") / "secrets.env", "WHO_WINS=documented\n")
    _w(paths.legacy("secrets.dor"), "WHO_WINS=shared\n")
    mod.load_secrets()
    assert os.environ["WHO_WINS"] == "documented"


@pytest.fixture
def documented_dir(home):
    """The documented 3.x directory, empty (#483)."""
    directory = paths.legacy("secrets.h2t")
    directory.mkdir(parents=True)
    return directory


def test_a_per_provider_file_in_the_documented_directory_is_read(documented_dir):
    """#483: keys live one file per provider (anysite.env, fred.env); none of them was read."""
    (documented_dir / "anysite.env").write_text("PROVIDER_ONLY=yes\n", encoding="utf-8")
    (documented_dir / "notes.md").write_text("PROVIDER_ONLY=not-an-env-file\n", encoding="utf-8")
    mod.load_secrets()
    assert os.environ["PROVIDER_ONLY"] == "yes"


def test_secrets_env_wins_over_a_per_provider_file(documented_dir):
    (documented_dir / "secrets.env").write_text("WHO_WINS=secrets\n", encoding="utf-8")
    (documented_dir / "anysite.env").write_text("WHO_WINS=anysite\n", encoding="utf-8")
    mod.load_secrets()
    assert os.environ["WHO_WINS"] == "secrets"


def test_per_provider_files_resolve_a_duplicate_alphabetically(documented_dir):
    (documented_dir / "zeta.env").write_text("WHO_WINS=zeta\n", encoding="utf-8")
    (documented_dir / "alpha.env").write_text("WHO_WINS=alpha\n", encoding="utf-8")
    mod.load_secrets()
    assert os.environ["WHO_WINS"] == "alpha"


def test_a_per_provider_file_never_overrides_the_environment(documented_dir, monkeypatch):
    monkeypatch.setenv("SHELL_WINS", "shell")
    (documented_dir / "anysite.env").write_text("SHELL_WINS=file\n", encoding="utf-8")
    mod.load_secrets()
    assert os.environ["SHELL_WINS"] == "shell"


def test_an_empty_documented_directory_adds_nothing(documented_dir):
    assert mod.candidate_secret_files()[0] == documented_dir / "secrets.env"
    assert len(mod.candidate_secret_files()) == 3
