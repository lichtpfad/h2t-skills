"""Connector → providers, and the key prefix each provider owns (#548 §4).

A provider is the external service, not the connector: research talks to exa and jina.
"""
from __future__ import annotations

import re

CONNECTOR_PROVIDERS: dict[str, tuple[str, ...]] = {
    "notion": ("notion",), "gmail": ("google",), "calendar": ("google",), "drive": ("google",),
    "google": ("google",), "telegram": ("telegram",), "meetgeek": ("meetgeek",),
    "granola": ("granola",), "dropbox": ("dropbox",), "research": ("exa", "jina"),
    "evals": ("h2t-evals",),
}
KEY_PREFIX: dict[str, str] = {
    "notion": "NOTION_", "telegram": "TELEGRAM_", "meetgeek": "MEETGEEK_", "granola": "GRANOLA_",
    "dropbox": "DROPBOX_", "exa": "EXA_", "jina": "JINA_", "h2t-evals": "H2T_EVALS_",
}
PROVIDERS = frozenset(p for ps in CONNECTOR_PROVIDERS.values() for p in ps)
FILE_NAME = re.compile(r"^(?P<provider>[a-z0-9-]+)\.(env|client\.json|token\.json|session|auth-state\.json)$")
EXEMPT = re.compile(r"^other\.env$|\.from-[A-Za-z0-9_-]+(\.[a-z.]+)?$")


def provider_of_key(key: str) -> str | None:
    best = None
    for provider, prefix in KEY_PREFIX.items():
        if key.startswith(prefix) and (best is None or len(prefix) > len(KEY_PREFIX[best])):
            best = provider
    return best


def key_prefix(provider: str) -> str:
    """`<PROVIDER>_` (§4): the table's entry, or the name upper-cased (google → GOOGLE_)."""
    return KEY_PREFIX.get(provider) or provider.upper().replace("-", "_") + "_"


def is_package_provider(stem: str) -> bool:
    return stem in PROVIDERS
