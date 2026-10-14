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
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("connector-home")))
