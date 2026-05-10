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
    """Read secrets.env and merge missing keys into os.environ.

    Args:
        env_file: Path to secrets file. Defaults to:
            $H2T_SECRETS_FILE env var if set, else DEFAULT_SECRETS_FILE.

    Returns:
        Dict of keys that were newly set (i.e., not already in os.environ).
        Existing os.environ keys are preserved (shell-export wins).

    Raises:
        FileNotFoundError: env_file does not exist.
        ValueError: a non-blank, non-comment line is not in KEY=VALUE form.
    """
    if env_file is None:
        override = os.environ.get(ENV_OVERRIDE)
        env_file = Path(override) if override else DEFAULT_SECRETS_FILE

    if not env_file.is_file():
        raise FileNotFoundError(
            f"h2t_secrets: secrets file not found at {env_file}. "
            f"Create ~/.dor/secrets/secrets.env (see "
            f"docs/superpowers/specs/2026-05-07-secrets-loader.md §5)."
        )

    new_keys: dict[str, str] = {}
    for lineno, raw in enumerate(env_file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(
                f"h2t_secrets: malformed line {lineno} in {env_file}: {raw!r} "
                f"(expected KEY=VALUE)"
            )
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key in os.environ:
            continue  # shell-export wins
        os.environ[key] = value
        new_keys[key] = value
    return new_keys


def get_blob(relative_path: str) -> Path:
    """Return absolute Path to a credential blob under SECRETS_DIR.

    Args:
        relative_path: e.g. 'google/gmail-oauth.json' or 'telegram/h2t.session'.

    Returns:
        Absolute resolved Path.

    Raises:
        FileNotFoundError: blob does not exist at the resolved path.
    """
    candidate = (SECRETS_DIR / relative_path).resolve()
    if not candidate.is_file():
        raise FileNotFoundError(
            f"h2t_secrets: blob not found at {candidate} "
            f"(relative_path={relative_path!r})"
        )
    return candidate
