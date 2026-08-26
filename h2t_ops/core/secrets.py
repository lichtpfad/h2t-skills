"""Minimal secrets loader + Notion token resolution (spec §11: minimal only)."""
from __future__ import annotations

import os
from pathlib import Path

from h2t_ops.core.errors import ConfigError

ENV_OVERRIDE = "H2T_SECRETS_FILE"
# The location every user-facing surface names: the SessionStart banner, the setup skill's
# `~/.h2t/config/` line, and the MeetGeek registry hint. Until #432 it was the one place
# nothing read, so a new user configured the connectors into a directory the loader never
# opened and every command answered MISSING.
H2T_CONFIG_SECRETS = Path.home() / ".h2t" / "config" / "secrets" / "secrets.env"
# Shared across the author's machines through Syncthing, which is why it became canonical
# in the first place — see #432. Kept ahead of nothing and behind the documented path, so
# existing installs are untouched.
DEFAULT_SECRETS = Path.home() / ".dor" / "secrets" / "secrets.env"
LEGACY_SECRETS = Path.home() / ".dor" / "secrets.env"


def _candidate_secret_files(env_file: Path | None = None) -> list[Path]:
    """Secrets files in load order: explicit, documented, shared, then legacy.

    Every candidate is read and merged without overriding, so listing the documented
    path first costs nothing on a machine that only has the shared one.
    """
    if env_file is not None:
        return [env_file]
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return [Path(override)]
    return [H2T_CONFIG_SECRETS, DEFAULT_SECRETS, LEGACY_SECRETS]


def load_secrets(env_file: Path | None = None) -> None:
    """Merge KEY=VALUE lines into os.environ WITHOUT overriding existing keys.

    Read in order: an explicit path, ~/.h2t/config/secrets/secrets.env (the location
    every user-facing message names), ~/.dor/secrets/secrets.env (shared between the
    author's machines over Syncthing), then the older ~/.dor/secrets.env. Files are
    merged, not chosen, so an existing machine needs no cutover.
    """
    for path in _candidate_secret_files(env_file):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = val.strip().strip('"').strip("'")


def resolve_notion_token() -> str:
    """Env var → ~/.dor/secrets/secrets.env → legacy env → token file.

    Parity with legacy lib/clients/notion.py, which did
    `load_dotenv(~/.dor/secrets.env, override=False)` at import. We do it
    on-demand inside token resolution instead (idempotent, no-override merge).
    The file IS read here, but only when a client actually needs the token —
    registry/help still stay lazy because they never instantiate the client.
    """
    load_secrets()  # merges ~/.dor/secrets.env into os.environ; no override
    tok = os.getenv("NOTION_API_TOKEN")
    if tok:
        return tok
    cfg = Path.home() / ".config" / "notion" / "token"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise ConfigError(
        "Notion API token not found.",
        hint=(
            "Set NOTION_API_TOKEN in ~/.h2t/config/secrets/secrets.env "
            "(also read: ~/.dor/secrets/secrets.env, ~/.dor/secrets.env) "
            "or create ~/.config/notion/token"
        ),
    )
