"""Connector tests never see the real home."""
import pytest


@pytest.fixture(autouse=True)
def _no_real_credentials(monkeypatch, tmp_path_factory):
    """Point HOME at an empty directory for every connector test.

    Tokens and keys live under the home: ~/.config/google-calendar-mcp, ~/.dor/secrets,
    ~/.config/telegram. When a mock fails to bind, the client underneath falls through to
    them — measured 2026-10-14, a module desync sent fourteen gmail tests to the live API
    with the developer's token. With no credentials reachable, the same failure is a
    ConfigError instead of a request. Tests that need a home patch Path.home themselves.
    """
    home = str(tmp_path_factory.mktemp("connector-home"))
    monkeypatch.setenv("HOME", home)
    # Windows resolves ~ from USERPROFILE and ignores HOME (ntpath.expanduser, Python 3.8+).
    monkeypatch.setenv("USERPROFILE", home)
    # HOME is not enough for the secrets files: h2t_ops.core.secrets fixes their paths at
    # import, from whatever home the process started with. Measured 2026-10-15: a Notion key
    # synced into the real ~/.dor/secrets/secrets.env, and a test patching Path.home still
    # found it. The override makes the loader read this one empty path and nothing else.
    monkeypatch.setenv("H2T_SECRETS_FILE", str(tmp_path_factory.mktemp("no-secrets") / "secrets.env"))
