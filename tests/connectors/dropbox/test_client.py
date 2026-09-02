"""Tests for h2t_ops.connectors.dropbox.client.DropboxClient (#469)."""
from __future__ import annotations

import gzip
import json
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)


@pytest.fixture
def client_obj():
    from h2t_ops.connectors.dropbox.client import DropboxClient
    c = object.__new__(DropboxClient)
    c._token = "test-token"
    c._timeout = 10
    c._path_root = ""
    return c


class _Resp:
    def __init__(self, status=200, payload=None, text=None, chunks=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.text = text if text is not None else json.dumps(self._payload)
        self._chunks = chunks or []

    def json(self):
        return self._payload

    def iter_content(self, chunk_size=None):
        return iter(self._chunks)


def _fake_requests(post):
    class _Exc(Exception):
        pass

    return SimpleNamespace(post=post, RequestException=_Exc), _Exc


# --- guards ------------------------------------------------------------------


def test_module_has_no_module_level_requests_import():
    src = pathlib.Path("h2t_ops/connectors/dropbox/client.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith(("import requests", "from requests")):
            assert line[0] == " ", f"line {i}: module-scope 'requests' import forbidden: {line!r}"


def test_init_without_token_raises_configerror(monkeypatch, tmp_path):
    from h2t_ops.connectors.dropbox import client as dmod

    for key in ("DROPBOX_TOKEN", "DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(dmod, "load_secrets", lambda *a, **k: None)
    monkeypatch.setattr(dmod, "PROVIDER_ENV_FILE", tmp_path / "absent.env")
    with pytest.raises(ConfigError) as exc:
        dmod.DropboxClient()
    assert "DROPBOX_TOKEN" in str(exc.value)


def test_init_reads_the_provider_env_file_the_issue_names(monkeypatch, tmp_path):
    from h2t_ops.connectors.dropbox import client as dmod

    monkeypatch.delenv("DROPBOX_TOKEN", raising=False)
    monkeypatch.setattr(dmod, "load_secrets", lambda *a, **k: None)
    env = tmp_path / "dropbox.env"
    env.write_text("DROPBOX_TOKEN=from-file\n", encoding="utf-8")
    monkeypatch.setattr(dmod, "PROVIDER_ENV_FILE", env)
    assert dmod.DropboxClient()._token == "from-file"


# --- paths -------------------------------------------------------------------


@pytest.mark.parametrize("given,expected", [
    ("", ""), ("/", ""), ("HOU2TOUCH", "/HOU2TOUCH"),
    ("/HOU2TOUCH/", "/HOU2TOUCH"), ("/a/b", "/a/b"),
])
def test_normalize_path(given, expected):
    from h2t_ops.connectors.dropbox.client import normalize_path
    assert normalize_path(given) == expected


# --- namespace ---------------------------------------------------------------


def test_path_root_uses_root_namespace_when_it_differs_from_home(client_obj):
    client_obj._path_root = None
    client_obj._rpc = MagicMock(return_value={
        "root_info": {"root_namespace_id": "9001", "home_namespace_id": "42"}
    })
    assert client_obj.path_root() == "9001"
    hdrs = client_obj._headers()
    assert json.loads(hdrs["Dropbox-API-Path-Root"]) == {".tag": "root", "root": "9001"}


def test_path_root_absent_for_a_personal_account(client_obj):
    client_obj._path_root = None
    client_obj._rpc = MagicMock(return_value={
        "root_info": {"root_namespace_id": "42", "home_namespace_id": "42"}
    })
    assert client_obj.path_root() == ""
    assert "Dropbox-API-Path-Root" not in client_obj._headers()


def test_path_root_is_resolved_once(client_obj):
    client_obj._path_root = None
    client_obj._rpc = MagicMock(return_value={
        "root_info": {"root_namespace_id": "9001", "home_namespace_id": "42"}
    })
    client_obj.path_root()
    client_obj.path_root()
    assert client_obj._rpc.call_count == 1


# --- listing -----------------------------------------------------------------


def test_list_folder_follows_the_cursor(client_obj):
    pages = [
        {"entries": [{"name": "a"}], "has_more": True, "cursor": "c1"},
        {"entries": [{"name": "b"}], "has_more": True, "cursor": "c2"},
        {"entries": [{"name": "c"}], "has_more": False},
    ]
    calls = []

    def rpc(endpoint, arg):
        calls.append((endpoint, arg))
        return pages[len(calls) - 1]

    client_obj._rpc = rpc
    out = client_obj.list_folder("/HOU2TOUCH", recursive=True)
    assert [e["name"] for e in out] == ["a", "b", "c"]
    assert calls[0][0] == "files/list_folder"
    assert calls[0][1] == {"path": "/HOU2TOUCH", "recursive": True}
    assert calls[1] == ("files/list_folder/continue", {"cursor": "c1"})


def test_list_folder_stops_at_limit(client_obj):
    client_obj._rpc = MagicMock(return_value={
        "entries": [{"name": n} for n in "abc"], "has_more": False
    })
    assert len(client_obj.list_folder("/x", limit=2)) == 2


# --- errors ------------------------------------------------------------------


def test_missing_scope_401_says_to_regenerate_the_token(client_obj, monkeypatch):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(401, text='{"error_summary": "missing_scope/.."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(AuthError) as exc:
        client_obj._rpc("files/list_folder", {"path": ""})
    assert "generate a NEW token" in (exc.value.hint or "")


def test_expired_token_401_is_an_auth_error(client_obj, monkeypatch):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(401, text='{"error_summary": "expired_access_token/"}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(AuthError) as exc:
        client_obj._rpc("files/list_folder", {"path": ""})
    assert "missing_scope" not in str(exc.value)


def test_path_not_found_409_is_a_notfound_error(client_obj, monkeypatch):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(409, text='{"error_summary": "path/not_found/."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NotFoundError):
        client_obj._rpc("files/get_metadata", {"path": "/nope"})


def test_other_409_is_a_usage_error(client_obj, monkeypatch):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(409, text='{"error_summary": "path/malformed_path/."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(UsageError):
        client_obj._rpc("files/get_metadata", {"path": "bad"})


def test_rate_limit_and_server_errors_are_provider_errors(client_obj, monkeypatch):
    for status in (429, 503):
        fake, _ = _fake_requests(lambda *a, s=status, **k: _Resp(s, text="boom"))
        monkeypatch.setitem(sys.modules, "requests", fake)
        with pytest.raises(ProviderError):
            client_obj._rpc("files/list_folder", {"path": ""})


def test_transport_failure_is_a_network_error(client_obj, monkeypatch):
    def post(*a, **k):
        raise exc_cls("connection reset")

    fake, exc_cls = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NetworkError):
        client_obj._rpc("files/list_folder", {"path": ""})


# --- download ----------------------------------------------------------------


def test_download_streams_to_disk(client_obj, monkeypatch, tmp_path):
    seen = {}

    def post(url, headers=None, stream=None, timeout=None):
        seen["url"] = url
        seen["arg"] = json.loads(headers["Dropbox-API-Arg"])
        return _Resp(200, chunks=[b"abc", b"de"])

    fake, _ = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.download("/HOU2TOUCH/clip.wav", str(tmp_path))
    assert seen["arg"] == {"path": "/HOU2TOUCH/clip.wav"}
    assert seen["url"].endswith("/files/download")
    assert (tmp_path / "clip.wav").read_bytes() == b"abcde"
    assert out["bytes"] == 5


def test_download_gunzips_content_stored_under_a_plain_name(client_obj, monkeypatch, tmp_path):
    blob = gzip.compress(b"<PremiereData/>")
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[blob]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.download("/x/seq.prproj", str(tmp_path / "seq.prproj"), gunzip=True)
    assert (tmp_path / "seq.prproj").read_bytes() == b"<PremiereData/>"
    assert out["bytes"] == len(b"<PremiereData/>")


def test_download_leaves_a_non_gzip_file_alone_under_gunzip(client_obj, monkeypatch, tmp_path):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[b"plain bytes"]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    client_obj.download("/x/notes.txt", str(tmp_path / "notes.txt"), gunzip=True)
    assert (tmp_path / "notes.txt").read_bytes() == b"plain bytes"


def test_download_rejects_the_root_path(client_obj):
    with pytest.raises(UsageError):
        client_obj.download("/", "/tmp/whatever")
