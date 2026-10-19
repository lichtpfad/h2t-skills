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
    # HOME is enough for the secrets files too: h2t_ops.core.secrets resolves every path at
    # call time through core.paths (#548) and no longer reads H2T_SECRETS_FILE (R5).


@pytest.fixture
def inbox(tmp_path):
    """paths.yaml declares an inbox outside ~/.h2t; downloads with no path land there."""
    from h2t_ops.core import paths

    box = tmp_path / "inbox"
    box.mkdir()
    cfg = paths.paths_yaml()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(f"version: 1\nplaces:\n  inbox: {box}\n", encoding="utf-8")
    return box
