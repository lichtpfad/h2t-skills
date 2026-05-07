"""Pytest config for h2t-ops:research tests.

Registers custom markers so pytest does not emit PytestUnknownMarkWarning.
Provides an autouse fixture that isolates h2t_secrets bootstrap from the
user's real ~/.dor/secrets/secrets.env file.
"""
from __future__ import annotations

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "optional: label for opt-in scenarios (e.g. real-trafilatura uplift). "
        "Currently still runs in baseline; reserve for future @skipif gating.",
    )


@pytest.fixture(autouse=True)
def _isolated_secrets(tmp_path_factory, monkeypatch):
    """Provide an isolated secrets.env so tests don't depend on the user's
    real ~/.dor/secrets/secrets.env file.

    Tests that monkeypatch _h2t_secrets_bootstrap directly are unaffected
    (their patch overrides this default-empty fixture).
    """
    sec_dir = tmp_path_factory.mktemp("h2t-secrets")
    env_file = sec_dir / "secrets.env"
    env_file.write_text("# test placeholder\n", encoding="utf-8")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(env_file))
    yield
