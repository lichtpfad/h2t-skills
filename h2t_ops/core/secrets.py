"""Minimal secrets loader + Notion token resolution (spec §11: minimal only)."""
from __future__ import annotations

import os
from pathlib import Path

from h2t_ops.core.errors import ConfigError

DEFAULT_SECRETS = Path.home() / ".dor" / "secrets.env"


def load_secrets(env_file: Path | None = None) -> None:
    """Merge KEY=VALUE lines into os.environ WITHOUT overriding existing keys."""
    path = env_file or DEFAULT_SECRETS
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip()


def resolve_notion_token() -> str:
    """Env var → ~/.dor/secrets.env → ~/.config/notion/token → ConfigError.

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
        hint="Set NOTION_API_TOKEN in ~/.dor/secrets.env or create ~/.config/notion/token",
    )
