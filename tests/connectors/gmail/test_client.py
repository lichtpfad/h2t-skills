"""Auth re-wrap tests for the Gmail connector client (Task 2, §4.1 enforcement).

Three behavioral assertions (per plan):
  (a) missing google libs            -> ConfigError
  (b) no creds & no refresh token    -> ConfigError AND browser never launched
  (c) creds.refresh() raising        -> AuthError

Seam note: the plan's reference test patched `_install_app_flow` and
`_load_credentials`. Implementer discretion (explicitly permitted, seam shape
only): we add a third thin seam `_request()` and patch it in test (c). Reason:
google libs are NOT installed in the `uv run h2t-ops dev pytest` env (Task 7
declares them later). Without patching `_request`, the byte-identical
`creds.refresh(_request())` would hit `from google.auth.transport.requests
import Request` and raise ImportError -> ConfigError, masking the AuthError we
mean to assert. Patching `_request` keeps test (c) exercising the *real*
refresh-failure -> AuthError code path. All three assertions still hold and
still hit real code paths.
"""
import builtins
import sys

import pytest


def test_missing_google_libs_raises_configerror(monkeypatch):
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise ImportError(f"No module named {name!r}")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    from h2t_ops.connectors.gmail.client import GmailClient
    from h2t_ops.core.errors import ConfigError
    with pytest.raises(ConfigError):
        GmailClient()


def test_no_creds_no_refresh_raises_configerror_not_browser(monkeypatch, tmp_path):
    """§4.1 enforcement: must raise ConfigError, must NOT launch run_local_server.

    Seam adjustment (discretion clause): the reference test left both
    credentials.json absent and `_load_credentials` real. With creds.json
    absent the flow short-circuits at delta 4 (missing-credentials
    ConfigError), and with google libs absent it short-circuits even earlier
    at delta 1 — in *both* cases the §4.1 branch is never reached, so the test
    would pass even if the legacy `flow.run_local_server` branch were
    reintroduced (verified via discriminator). To make this test actually
    guard §4.1 we (a) create credentials.json so delta 4 is skipped, and
    (b) stub `_load_credentials` -> None so no google import is attempted and
    no valid creds exist. The flow then reaches delta 5 and `_install_app_flow`
    must never be touched.
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import ConfigError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text("{}")
    monkeypatch.setattr(gmod.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(gmod, "_load_credentials", lambda *a, **k: None)

    launched = {"browser": False}

    class _Flow:
        @staticmethod
        def from_client_secrets_file(*a, **k):
            launched["browser"] = True
            raise AssertionError("run_local_server must never be reached")

    monkeypatch.setattr(gmod, "_install_app_flow", lambda: _Flow)
    with pytest.raises(ConfigError):
        gmod.GmailClient()
    assert launched["browser"] is False


def test_refresh_failure_raises_autherror(monkeypatch, tmp_path):
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import AuthError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text('{"installed":{"client_id":"x","client_secret":"y"}}')
    (cfg / "token.json").write_text('{"refresh_token":"r","client_id":"x","client_secret":"y","scopes":["s"]}')
    monkeypatch.setattr(gmod.Path, "home", staticmethod(lambda: tmp_path))

    class _Creds:
        valid = False
        expired = True
        refresh_token = "r"
        def refresh(self, _req): raise RuntimeError("invalid_grant")

    monkeypatch.setattr(gmod, "_load_credentials", lambda *a, **k: _Creds())
    # Seam (discretion): stub the lazy Request() import — google libs absent in test env.
    monkeypatch.setattr(gmod, "_request", lambda: object())
    with pytest.raises(AuthError):
        gmod.GmailClient()


# --- Task 3: read methods + HTTP error mapping ---

import types  # noqa: E402


class _FakeService:
    def __init__(self, **resp): self._r = resp
    def users(self): return self
    def messages(self): return self
    def labels(self): return self
    def list(self, **k): return _Exec(self._r.get("list", {}))
    def get(self, **k): return _Exec(self._r.get("get", {}))


class _Exec:
    def __init__(self, v): self._v = v
    def execute(self): return self._v


def _client_with(monkeypatch, service):
    from h2t_ops.connectors.gmail import client as gmod
    c = gmod.GmailClient.__new__(gmod.GmailClient)
    c.service = service
    return c, gmod


def test_list_messages_happy(monkeypatch):
    svc = _FakeService(list={"messages": [{"id": "1"}]},
                       get={"id": "1", "threadId": "t", "labelIds": [], "snippet": "",
                            "payload": {"headers": [{"name": "Subject", "value": "S"}]}})
    c, _ = _client_with(monkeypatch, svc)
    out = c.list_messages(max_results=1)
    assert out[0]["id"] == "1" and out[0]["subject"] == "S"


def test_get_message_404_maps_notfound(monkeypatch):
    from h2t_ops.core.errors import NotFoundError

    class _HttpErr(Exception):
        resp = types.SimpleNamespace(status=404)

    class _Svc(_FakeService):
        def get(self, **k):
            raise _HttpErr("not found")

    c, gmod = _client_with(monkeypatch, _Svc())
    monkeypatch.setattr(gmod, "HttpError", _HttpErr, raising=False)
    with pytest.raises(NotFoundError):
        c.get_message("missing")
