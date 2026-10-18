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


CASES: list[Case] = [
    Case("store.replace.state", _store_replace_state),
    # Task 8: a refresh writes nothing; a rotated refresh token writes local and the mirror.
    Case("google.refresh", _google_refresh("fake-r1"), setup=_google_tokens),
    Case("google.refresh.new-token", _google_refresh("fake-r2"), setup=_google_tokens,
         compat=(".config/google-calendar-mcp/tokens.json",)),
]
