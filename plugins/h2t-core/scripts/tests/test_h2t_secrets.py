"""Tests for h2t_secrets loader."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Resolve module path: plugins/h2t-core/scripts/
SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))
import h2t_secrets  # noqa: E402


def test_module_exposes_public_api():
    assert hasattr(h2t_secrets, "bootstrap")
    assert hasattr(h2t_secrets, "get_blob")
    assert hasattr(h2t_secrets, "DEFAULT_SECRETS_FILE")
    assert hasattr(h2t_secrets, "SECRETS_DIR")
    assert hasattr(h2t_secrets, "ENV_OVERRIDE")


def test_default_secrets_file_path():
    assert h2t_secrets.DEFAULT_SECRETS_FILE == Path.home() / ".dor" / "secrets" / "secrets.env"


def test_secrets_dir_path():
    assert h2t_secrets.SECRETS_DIR == Path.home() / ".dor" / "secrets"


def test_env_override_constant():
    assert h2t_secrets.ENV_OVERRIDE == "H2T_SECRETS_FILE"


def test_bootstrap_raises_not_implemented_initially():
    """Will be replaced in Task 2."""
    with pytest.raises(NotImplementedError):
        h2t_secrets.bootstrap()


def test_get_blob_raises_not_implemented_initially():
    """Will be replaced in Task 3."""
    with pytest.raises(NotImplementedError):
        h2t_secrets.get_blob("foo/bar")
