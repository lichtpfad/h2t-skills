"""Every secrets surface reads the path #432 made canonical (#448).

#432 added ~/.h2t/config/secrets/secrets.env to h2t_ops.core.secrets and stopped there.
The research connector and the setup skill each carried their own candidate list, so a key
written to the documented location was invisible to `h2t-ops research` and reported MISSING
by `setup doctor` — while `h2t-ops notion` found it.

Each side's own tests stayed green throughout: the defect lived in the seam. This is the
round trip — one key, written only to the documented location, read by all three.
"""
import sys
from pathlib import Path

import pytest

from h2t_ops.connectors.research import client
from h2t_ops.core import secrets as core_secrets

SCRIPTS_DIR = Path(__file__).parent.parent / "plugins" / "h2t-core" / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import setup_h2t  # noqa: E402

KEY = "EXA_API_KEY"
VALUE = "documented-path-value"


@pytest.fixture
def documented_only(tmp_path, monkeypatch):
    """A home whose ONLY secrets file is the documented one."""
    for name in (KEY, "H2T_SECRETS_FILE"):
        monkeypatch.delenv(name, raising=False)
    documented = tmp_path / ".h2t" / "config" / "secrets" / "secrets.env"
    documented.parent.mkdir(parents=True)
    documented.write_text(f"{KEY}={VALUE}\n", encoding="utf-8")
    monkeypatch.setattr(core_secrets, "H2T_CONFIG_SECRETS", documented)
    monkeypatch.setattr(core_secrets, "DEFAULT_SECRETS", tmp_path / ".dor" / "absent.env")
    monkeypatch.setattr(core_secrets, "LEGACY_SECRETS", tmp_path / ".dor" / "absent-legacy.env")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def test_core_reads_documented_path(documented_only, monkeypatch):
    core_secrets.load_secrets()
    import os
    assert os.environ.get(KEY) == VALUE


def test_research_reads_documented_path(documented_only):
    assert client.resolve_secret(KEY) == VALUE


def test_setup_sees_documented_path(documented_only):
    assert setup_h2t._secret_present(KEY, documented_only) is True


def test_research_hint_names_documented_path(tmp_path, monkeypatch):
    """A miss must point at the location every other message names."""
    for name in (KEY, "H2T_SECRETS_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(core_secrets, "H2T_CONFIG_SECRETS", tmp_path / "absent-documented.env")
    monkeypatch.setattr(core_secrets, "DEFAULT_SECRETS", tmp_path / "absent-dor.env")
    monkeypatch.setattr(core_secrets, "LEGACY_SECRETS", tmp_path / "absent-legacy.env")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with pytest.raises(client.ConfigError) as ei:
        client.resolve_secret(KEY)

    assert "~/.h2t/config/secrets/secrets.env" in (ei.value.hint or "")
