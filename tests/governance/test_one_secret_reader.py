"""One secret reader (#548 §7.2): a key that sits only in secrets/shared/<provider>.env is
seen by the function each connector takes its key from.

The seam test: core.secrets' own tests stay green while a connector keeps a private reader
of its own (research read the files itself, dropbox had its own file, jina only the
environment, evals only ~/.dor/secrets.env). Here every consumer reads one planted file.
"""
from __future__ import annotations

import os

import pytest

from h2t_ops.core import paths, providers


def _research():
    from h2t_ops.connectors.research import client
    return client.resolve_secret("EXA_API_KEY")


def _jina():
    from h2t_ops.connectors.research import fetch
    return fetch._jina_key()


def _dropbox():
    from h2t_ops.connectors.dropbox import client
    return client._token_config()["DROPBOX_TOKEN"]


def _meetgeek():
    from h2t_ops.connectors.meetgeek import client
    return client._api_key()


def _granola():
    from h2t_ops.connectors.granola import client
    return client._api_key()


def _notion():
    from h2t_ops.core import secrets
    return secrets.resolve_notion_token()


def _evals():
    from h2t_ops.core import secrets
    return secrets.evals_env()["H2T_EVALS_TOKEN"]


def _telegram():
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter
    return TelegramClientAdapter()._load_config()["api_hash"]


# provider -> (lines of <provider>.env, expected value, the connector's reader)
READERS = {
    "exa": ("EXA_API_KEY=fake-exa\n", "fake-exa", _research),
    "jina": ("JINA_API_KEY=fake-jina\n", "fake-jina", _jina),
    "dropbox": ("DROPBOX_TOKEN=fake-dropbox\n", "fake-dropbox", _dropbox),
    "meetgeek": ("MEETGEEK_API_KEY=fake-meetgeek\n", "fake-meetgeek", _meetgeek),
    "granola": ("GRANOLA_API_KEY=fake-granola\n", "fake-granola", _granola),
    "notion": ("NOTION_API_TOKEN=fake-notion\n", "fake-notion", _notion),
    "h2t-evals": ("H2T_EVALS_TOKEN=fake-evals\n", "fake-evals", _evals),
    "telegram": ("TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=fake-telegram\n", "fake-telegram", _telegram),
}


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch):
    prefixes = tuple(providers.KEY_PREFIX.values())
    for k in list(os.environ):
        if k.startswith(prefixes):
            monkeypatch.delenv(k, raising=False)


def _plant(provider: str, text: str) -> None:
    shared = paths.secrets_shared()
    shared.mkdir(parents=True, exist_ok=True)
    (shared / f"{provider}.env").write_text(text, encoding="utf-8")


def test_every_env_provider_has_a_reader_here():
    """google keeps JSON files, not keys (Task 8); every other provider is covered."""
    assert set(READERS) == providers.PROVIDERS - {"google"}
    assert set(READERS) == set(providers.KEY_PREFIX)


@pytest.mark.parametrize("provider", sorted(READERS))
def test_connector_sees_the_key_in_its_provider_file(provider):
    text, value, read = READERS[provider]
    _plant(provider, text)
    assert read() == value


def test_both_evals_consumers_see_the_token():
    """R33: SkillEval and `h2t-ops evals status` read one source."""
    from h2t_ops.lifecycle.eval import session
    from h2t_ops.lifecycle.eval.status import get_status
    _plant("h2t-evals", "H2T_EVALS_TOKEN=fake-evals\n")
    assert get_status()["token_present"] is True
    assert session.SkillEval("session-start", domain="dev", project="p")._env["H2T_EVALS_TOKEN"] == "fake-evals"


def test_setup_doctor_sees_the_key_in_its_provider_file():
    from h2t_ops.setup import legacy
    _plant("exa", "EXA_API_KEY=fake-exa\n")
    assert legacy._secret_present("EXA_API_KEY", paths.home()) is True
