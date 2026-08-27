"""h2t_secrets — single source of truth for h2t skill secrets.

Reads ~/.dor/secrets/secrets.env into os.environ without overriding existing
shell-exported values. See docs/superpowers/specs/2026-05-07-secrets-loader.md.
"""
from __future__ import annotations

__version__ = "0.1.0"

import os
from pathlib import Path
from typing import Final

H2T_CONFIG_SECRETS_FILE: Final[Path] = Path.home() / ".h2t" / "config" / "secrets" / "secrets.env"
DEFAULT_SECRETS_FILE: Final[Path] = Path.home() / ".dor" / "secrets" / "secrets.env"
LEGACY_SECRETS_FILE: Final[Path] = Path.home() / ".dor" / "secrets.env"
SECRETS_DIR: Final[Path] = Path.home() / ".dor" / "secrets"
ENV_OVERRIDE: Final[str] = "H2T_SECRETS_FILE"


def _candidate_secrets_files() -> list[Path]:
    """The same chain as h2t_ops.core.secrets.candidate_secret_files (#448 review).

    Merged, not chosen. #432 made this pick one file — the documented path if present,
    else the shared one — so a user who created ~/.h2t/config/secrets/secrets.env with a
    single key lost every key still living in ~/.dor/secrets/secrets.env, and
    exa_search.py die(4)'d on a machine that had been configured correctly.

    This script is imported dynamically from the plugin cache and cannot import h2t_ops,
    so the list is duplicated on purpose. tests/test_secrets_path_parity.py and the merge
    test below are what hold the two copies together.
    """
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return [Path(override).expanduser()]
    return [H2T_CONFIG_SECRETS_FILE, DEFAULT_SECRETS_FILE, LEGACY_SECRETS_FILE]


def bootstrap(*, env_file: Path | None = None) -> dict[str, str]:
    """Read secrets.env and merge missing keys into os.environ.

    Args:
        env_file: A single secrets file. Default: the whole candidate chain
            ($H2T_SECRETS_FILE, else documented -> shared -> legacy), merged in
            order, with an earlier file winning a key collision.

    Returns:
        Dict of keys that were newly set (i.e., not already in os.environ).
        Existing os.environ keys are preserved (shell-export wins).

    Raises:
        FileNotFoundError: no candidate file exists.
        ValueError: a non-blank, non-comment line is not in KEY=VALUE form.
    """
    candidates = [env_file] if env_file is not None else _candidate_secrets_files()
    present = [path for path in candidates if path.is_file()]

    if not present:
        raise FileNotFoundError(
            f"h2t_secrets: secrets file not found at {candidates[0]}. "
            f"Create ~/.h2t/config/secrets/secrets.env (see "
            f"docs/superpowers/specs/2026-05-07-secrets-loader.md §5)."
        )

    new_keys: dict[str, str] = {}
    for path in present:
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(
                    f"h2t_secrets: malformed line {lineno} in {path}: {raw!r} "
                    f"(expected KEY=VALUE)"
                )
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip matching surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key in os.environ:
                continue  # shell-export wins, and so does an earlier file in the chain
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
