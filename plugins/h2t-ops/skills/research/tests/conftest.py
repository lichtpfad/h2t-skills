"""Pytest config for h2t-ops:research tests.

Registers custom markers so pytest does not emit PytestUnknownMarkWarning.
Provides an autouse fixture that isolates h2t_secrets bootstrap from the
user's real ~/.dor/secrets/secrets.env file.
"""
from __future__ import annotations

from pathlib import Path

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


PLUGIN_ROOT = Path(__file__).resolve().parents[4] / "h2t-core"


@pytest.fixture(autouse=True)
def _h2t_plugin_root(monkeypatch):
    """Resolve h2t_secrets from this checkout instead of an installed plugin.

    `exa_search._load_h2t_secrets()` globs the plugin cache
    (`<marketplace>/h2t-core/*/scripts/h2t_secrets.py`) and falls back to
    `$H2T_PLUGIN_ROOT/scripts/h2t_secrets.py`. A CI runner has neither, so 24 of these
    tests died on `FileNotFoundError: h2t_secrets module not found. Tried: []` — the same
    24 that fail here with a clean HOME and with a real one, which is why the directory was
    never wired into CI (#381). Pointing H2T_PLUGIN_ROOT at the repo is the mechanism the
    error message itself recommends, so the resolution stays under test.

    H2T_EVALS_MODE is pinned for the same reason: now that these run in CI, an ambient
    value would decide what they exercise.
    """
    assert (PLUGIN_ROOT / "scripts" / "h2t_secrets.py").is_file(), (
        f"h2t_secrets.py not found under {PLUGIN_ROOT} — the layout moved"
    )
    monkeypatch.setenv("H2T_PLUGIN_ROOT", str(PLUGIN_ROOT))
    monkeypatch.setenv("H2T_EVALS_MODE", "off")
