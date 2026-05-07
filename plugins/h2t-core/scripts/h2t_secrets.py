"""h2t_secrets — single source of truth for h2t skill secrets.

Reads ~/.dor/secrets/secrets.env into os.environ without overriding existing
shell-exported values. See docs/superpowers/specs/2026-05-07-secrets-loader.md.
"""
from __future__ import annotations

__version__ = "0.1.0"

import os
from pathlib import Path
from typing import Final

DEFAULT_SECRETS_FILE: Final[Path] = Path.home() / ".dor" / "secrets" / "secrets.env"
SECRETS_DIR: Final[Path] = Path.home() / ".dor" / "secrets"
ENV_OVERRIDE: Final[str] = "H2T_SECRETS_FILE"


def bootstrap(*, env_file: Path | None = None) -> dict[str, str]:
    """Stub — implemented in Task 2."""
    raise NotImplementedError


def get_blob(relative_path: str) -> Path:
    """Stub — implemented in Task 3."""
    raise NotImplementedError
