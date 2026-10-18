"""Every command that writes to disk, run under a temporary HOME (#548 §7.3).

Phase-C tasks append their cases here. A case gets the sandbox and monkeypatch, fakes its
provider exactly as that connector's own tests do, and runs the command in-process.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    run: Callable
    compat: tuple[str, ...] = ()  # legacy files this case may write via store compat
    setup: Callable | None = None  # writes the starting state before the recorder is on (R30)


def _store_replace_state(sb, mp):
    from h2t_ops.core import paths, store
    store.replace(paths.state_dir() / "probe.json", "{}", place="state")


def _google_tokens(sb, mp):
    from h2t_ops.core import paths
    local = paths.secrets_local() / "google.token.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text('{"refresh_token": "fake-r1"}')
    (paths.legacy("google.store") / "tokens.json").write_text('{"refresh_token": "fake-r1"}')


def _google_refresh(refresh_token):
    def run(sb, mp):
        import json
        from types import SimpleNamespace

        from h2t_ops.core import google_auth
        scope = "https://www.googleapis.com/auth/calendar"
        state = {"refresh_token": refresh_token, "client_id": "fake-id", "client_secret": "fake-cs",
                 "token_uri": "https://oauth2.googleapis.com/token", "scopes": [scope]}
        creds = SimpleNamespace(valid=False, expired=True, refresh_token=refresh_token,
                                scopes=[scope], refresh=lambda req: None,
                                to_json=lambda: json.dumps({"token": "fake-access", **state}))
        mp.setattr(google_auth, "_load_credentials", lambda data, client: creds)
        mp.setattr(google_auth, "_request", lambda: None)
        google_auth.resolve_google_credentials("calendar", [scope])
    return run


def _telegram_cli(argv, client_cls):
    """Run `h2t-ops telegram <argv>` in-process with a stand-in for Telethon's client."""
    def run(sb, mp):
        import argparse

        from h2t_ops.connectors.telegram import client, commands
        mp.setattr(client.TelegramClientAdapter, "_telegram_client_class", lambda self: client_cls())
        p = argparse.ArgumentParser()
        commands.register(p.add_subparsers(dest="connector"))
        commands.run(p.parse_args(["telegram", *argv]))
    return run


def _telegram_fake():
    """Telethon's TelegramClient as far as the commands use it: it opens <session>.session
    itself, as SQLiteSession does, so the write must be one store.managed handed over."""
    from pathlib import Path
    from types import SimpleNamespace

    from telethon.tl.types import auth as tl_auth

    class Fake:
        def __init__(self, session, api_id, api_hash):
            p = Path(session + ".session")
            if not p.exists():
                p.write_bytes(b"fake-session")

        def connect(self):
            pass

        def disconnect(self):
            pass

        def send_code_request(self, phone):
            return SimpleNamespace(phone_code_hash="fake-hash", type=tl_auth.SentCodeTypeSms(length=5),
                                   next_type=None, timeout=None)

        def iter_dialogs(self, limit=None):
            return []

        def iter_messages(self, entity, limit=None):
            return []

        def get_messages(self, entity, ids=None):
            f = SimpleNamespace(name="report.pdf", size=8, mime_type="application/pdf", ext=".pdf")
            return SimpleNamespace(media=SimpleNamespace(), file=f)

        def download_media(self, message, file=None):
            if isinstance(file, str):           # a directory, as 3.x passed it: Telethon names
                target = Path(file) / message.file.name   # the file and writes it itself
                target.write_bytes(b"fake-pdf")
                return str(target)
            file.write(b"fake-pdf")
            return file
    return Fake


def _telegram_keys(sb, mp):
    from h2t_ops.core import paths
    shared = paths.secrets_shared()
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "telegram.env").write_text("TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=fake-hash\n")


def _sqlite_session(path, rows=()):
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE entities (id INTEGER PRIMARY KEY, hash INTEGER)")
    conn.executemany("INSERT INTO entities VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _telegram_legacy_session(sb, mp):
    import os
    import stat

    from h2t_ops.core import paths
    _telegram_keys(sb, mp)
    d = paths.legacy("telegram")
    os.chmod(d, stat.S_IRWXU)        # the sandbox closes legacy dirs; open it to plant the file
    try:
        _sqlite_session(d / "session.session", [(-1000000000010, 42)])
    finally:
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)


def _telegram_new_session(sb, mp):
    from h2t_ops.core import paths
    _telegram_keys(sb, mp)
    _sqlite_session(paths.secrets_local() / "telegram.session", [(-1000000000010, 42)])


def _provider_key(provider, text):
    def setup(sb, mp):
        import os

        from h2t_ops.core import paths, providers
        for k in [k for k in os.environ if k.startswith(providers.key_prefix(provider))]:
            mp.delenv(k)
        shared = paths.secrets_shared()
        shared.mkdir(parents=True, exist_ok=True)
        (shared / f"{provider}.env").write_text(text)
    return setup


def _research_resolve(sb, mp):
    from h2t_ops.connectors.research import client
    assert client.resolve_secret("EXA_API_KEY") == "fake-exa"


def _dropbox_init(sb, mp):
    from h2t_ops.connectors.dropbox.client import DropboxClient
    assert DropboxClient()._token == "fake-dropbox"


def _evals_load(sb, mp):
    from h2t_ops.lifecycle.eval.session import SkillEval
    from h2t_ops.lifecycle.eval.status import get_status
    assert SkillEval("session-start", domain="dev", project="p")._env["H2T_EVALS_TOKEN"] == "fake-evals"
    assert get_status()["token_present"] is True


CASES: list[Case] = [
    Case("store.replace.state", _store_replace_state),
    # Task 8: a refresh writes nothing; a rotated refresh token writes local and the mirror.
    Case("google.refresh", _google_refresh("fake-r1"), setup=_google_tokens),
    Case("google.refresh.new-token", _google_refresh("fake-r2"), setup=_google_tokens,
         compat=(".config/google-calendar-mcp/tokens.json",)),
    # Task 9: session and auth state in secrets/local, attachments through a store handle.
    Case("telegram.auth-request-code", _telegram_cli(["auth", "request-code", "--phone", "+100"],
                                                     _telegram_fake), setup=_telegram_keys),
    Case("telegram.download-media.inbox", _telegram_cli(["download-media", "chat", "55"], _telegram_fake),
         setup=_telegram_keys),
    Case("telegram.session.copy-from-legacy", _telegram_cli(["dialogs"], _telegram_fake),
         setup=_telegram_legacy_session),
    Case("telegram.messages", _telegram_cli(["messages", "10", "--limit", "5"], _telegram_fake),
         setup=_telegram_new_session),
    # Task 10: keys only through core.secrets — a read of a secrets file from any other
    # module is a violation.
    Case("research.resolve", _research_resolve, setup=_provider_key("exa", "EXA_API_KEY=fake-exa\n")),
    Case("dropbox.init", _dropbox_init, setup=_provider_key("dropbox", "DROPBOX_TOKEN=fake-dropbox\n")),
    Case("evals.load", _evals_load, setup=_provider_key("h2t-evals", "H2T_EVALS_TOKEN=fake-evals\n")),
]
