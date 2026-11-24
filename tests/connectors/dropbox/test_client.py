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
    def __init__(self, status=200, payload=None, text=None, chunks=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
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
    repo = pathlib.Path(__file__).resolve().parents[3]
    src = (repo / "h2t_ops/connectors/dropbox/client.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith(("import requests", "from requests")):
            assert line[0] == " ", f"line {i}: module-scope 'requests' import forbidden: {line!r}"


def test_init_without_token_raises_configerror(monkeypatch):
    from h2t_ops.connectors.dropbox import client as dmod
    from h2t_ops.core import secrets

    for key in ("DROPBOX_TOKEN", "DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError) as exc:
        dmod.DropboxClient()
    assert "DROPBOX_TOKEN" in str(exc.value)
    assert str(secrets.provider_file("dropbox")) in exc.value.hint


def test_init_reads_the_provider_env_file(monkeypatch):
    from h2t_ops.connectors.dropbox import client as dmod
    from h2t_ops.core import secrets

    monkeypatch.delenv("DROPBOX_TOKEN", raising=False)
    env = secrets.provider_file("dropbox")
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text("DROPBOX_TOKEN=fake-from-file\n", encoding="utf-8")
    assert dmod.DropboxClient()._token == "fake-from-file"


# --- paths -------------------------------------------------------------------


@pytest.mark.parametrize("given,expected", [
    ("", ""), ("/", ""), ("HOU2TOUCH", "/HOU2TOUCH"),
    ("/HOU2TOUCH/", "/HOU2TOUCH"), ("/a/b", "/a/b"),
    # the Git Bash escape typed in PowerShell arrives unchanged: "//" is the root
    ("//", ""), ("//HOU2TOUCH", "/HOU2TOUCH"),
])
def test_normalize_path(given, expected):
    from h2t_ops.connectors.dropbox.client import normalize_path
    assert normalize_path(given) == expected


@pytest.mark.parametrize("given", [
    "C:/Program Files/Git/HOU2TOUCH",  # what Git Bash makes of "/HOU2TOUCH" (#725)
    "C:/Program Files/Git/",           # ... and of "/"
    "E:\\DROPBOX\\Team Dropbox\\Projects",
])
def test_a_drive_letter_path_is_refused_with_the_git_bash_remedy(given):
    from h2t_ops.connectors.dropbox.client import normalize_path
    with pytest.raises(UsageError) as exc:
        normalize_path(given)
    assert "MSYS_NO_PATHCONV=1" in exc.value.hint and "//" in exc.value.hint


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


def test_account_sends_json_null_body(client_obj, monkeypatch):
    # Live API, 2026-10-10: an empty body under Content-Type application/json gets
    # a 500 from users/get_current_account; the literal `null` gets a 200.
    seen = {}

    def post(url, **kw):
        seen.update(kw)
        return _Resp(200, payload={"account_id": "dbid:x"})

    fake, _ = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    client_obj.account()
    assert seen["data"] == b"null"


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


LINK = "https://www.dropbox.com/sh/abc123/XYZ?dl=0"


def test_list_link_sends_the_link_and_follows_the_cursor(client_obj):
    pages = [
        {"entries": [{".tag": "file", "name": "a.mp4"}], "has_more": True, "cursor": "c1"},
        {"entries": [{".tag": "file", "name": "b.mp4"}], "has_more": False},
    ]
    calls = []

    def rpc(endpoint, arg):
        calls.append((endpoint, arg))
        return pages[len(calls) - 1]

    client_obj._rpc = rpc
    out = client_obj.list_link(LINK)
    assert calls[0] == ("files/list_folder", {"path": "", "shared_link": {"url": LINK}})
    assert calls[1] == ("files/list_folder/continue", {"cursor": "c1"})
    # the path is the one inside the link: an outsider's link has no account path
    assert [e["link_path"] for e in out] == ["/a.mp4", "/b.mp4"]


def test_list_link_recursive_walks_subfolders_itself(client_obj):
    """Dropbox lists a shared link only non-recursively: the client descends."""
    tree = {
        "": [{".tag": "folder", "name": "L01"}, {".tag": "file", "name": "readme.txt"}],
        "/L01": [{".tag": "file", "name": "v.mp4"}, {".tag": "folder", "name": "src"}],
        "/L01/src": [{".tag": "file", "name": "a.toe"}],
    }
    calls = []

    def rpc(endpoint, arg):
        calls.append(arg)
        assert "recursive" not in arg or arg["recursive"] is False
        return {"entries": tree[arg["path"]], "has_more": False}

    client_obj._rpc = rpc
    out = client_obj.list_link(LINK, recursive=True)
    assert sorted(e["link_path"] for e in out) == [
        "/L01", "/L01/src", "/L01/src/a.toe", "/L01/v.mp4", "/readme.txt"]
    assert all(a["shared_link"] == {"url": LINK} for a in calls)


def test_list_link_starts_at_a_path_inside_the_link(client_obj):
    client_obj._rpc = MagicMock(return_value={"entries": [{".tag": "file", "name": "v.mp4"}],
                                              "has_more": False})
    out = client_obj.list_link(LINK, "L01/")
    assert client_obj._rpc.call_args.args[1]["path"] == "/L01"
    assert out[0]["link_path"] == "/L01/v.mp4"


def test_list_link_recursive_stops_at_limit(client_obj):
    client_obj._rpc = MagicMock(return_value={
        "entries": [{".tag": "folder", "name": n} for n in "abc"], "has_more": False})
    assert len(client_obj.list_link(LINK, recursive=True, limit=2)) == 2
    assert client_obj._rpc.call_count == 1


def test_link_meta_asks_the_sharing_endpoint(client_obj):
    client_obj._rpc = MagicMock(return_value={".tag": "folder", "name": "Lesson 01"})
    assert client_obj.link_meta(LINK)["name"] == "Lesson 01"
    assert client_obj._rpc.call_args.args == ("sharing/get_shared_link_metadata", {"url": LINK})
    client_obj.link_meta(LINK, "/L01/v.mp4")
    assert client_obj._rpc.call_args.args[1] == {"url": LINK, "path": "/L01/v.mp4"}


def test_unknown_shared_link_409_is_a_notfound_error(client_obj, monkeypatch):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(
        409, text='{"error_summary": "shared_link_not_found/.."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NotFoundError):
        client_obj.link_meta(LINK)


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


def test_rate_limit_waits_retry_after_and_resends(client_obj, monkeypatch):
    from h2t_ops.connectors.dropbox import client as dmod

    answers = [_Resp(429, text="too_many", headers={"Retry-After": "2"}),
               _Resp(429, text="too_many"),
               _Resp(200, payload={"entries": []})]
    fake, _ = _fake_requests(lambda *a, **k: answers.pop(0))
    monkeypatch.setitem(sys.modules, "requests", fake)
    waits = []
    monkeypatch.setattr(dmod.time, "sleep", waits.append)
    assert client_obj._rpc("files/list_folder", {"path": ""}) == {"entries": []}
    assert waits == [2.0, 1.0]  # Retry-After when given, else one second


def test_rate_limit_gives_up_after_the_retries(client_obj, monkeypatch):
    from h2t_ops.connectors.dropbox import client as dmod

    sent = []
    fake, _ = _fake_requests(lambda *a, **k: sent.append(1) or _Resp(429, text="too_many"))
    monkeypatch.setitem(sys.modules, "requests", fake)
    monkeypatch.setattr(dmod.time, "sleep", lambda s: None)
    with pytest.raises(ProviderError):
        client_obj._rpc("files/list_folder", {"path": ""})
    assert len(sent) == dmod.RATE_LIMIT_RETRIES + 1


def test_shared_link_access_denied_is_an_auth_error(client_obj, monkeypatch):
    """A password-protected or team-only link: say so, not a raw JSON body."""
    fake, _ = _fake_requests(lambda *a, **k: _Resp(
        409, text='{"error_summary": "shared_link_access_denied/.."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(AuthError) as exc:
        client_obj.link_meta(LINK)
    assert "access denied" in str(exc.value)


def test_rate_limit_and_server_errors_are_provider_errors(client_obj, monkeypatch):
    from h2t_ops.connectors.dropbox import client as dmod

    monkeypatch.setattr(dmod.time, "sleep", lambda s: None)
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


def test_download_without_dest_goes_to_the_inbox(client_obj, monkeypatch, inbox, capsys):
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[b"abc"]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.download("/HOU2TOUCH/takes/clip.wav")
    assert out["saved_to"] == str(inbox / "clip.wav") and out["defaulted"] is False
    assert (inbox / "clip.wav").read_bytes() == b"abc"
    assert f"saved to {inbox / 'clip.wav'}" in capsys.readouterr().err


def test_default_download_never_overwrites(client_obj, monkeypatch, inbox):
    (inbox / "clip.wav").write_bytes(b"theirs")
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[b"abc"]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.download("/x/clip.wav")
    assert out["saved_to"] == str(inbox / "clip-2.wav")
    assert (inbox / "clip.wav").read_bytes() == b"theirs"
    assert (inbox / "clip-2.wav").read_bytes() == b"abc"


def test_download_without_dest_or_paths_yaml_goes_to_data_inbox(client_obj, monkeypatch):
    from h2t_ops.core import paths
    blob = gzip.compress(b"<PremiereData/>")
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[blob]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.download("/x/seq.prproj", gunzip=True)
    target = paths.data_dir() / "inbox" / "seq.prproj"
    assert out["saved_to"] == str(target) and out["defaulted"] is True
    assert target.read_bytes() == b"<PremiereData/>"


def test_download_dest_into_secrets_is_refused(client_obj, monkeypatch):
    from h2t_ops.core import paths, store
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[b"abc"]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    target = paths.secrets_shared() / "x.env"
    with pytest.raises(store.WriteRefused):
        client_obj.download("/x/clip.wav", str(target))
    assert not target.exists()


def test_download_rejects_the_root_path(client_obj):
    with pytest.raises(UsageError):
        client_obj.download("/", "/tmp/whatever")


# --- adversarial review findings ---------------------------------------------


def test_path_root_is_retried_after_a_transient_failure(client_obj):
    """A failed account() must not leave the client believing it has no namespace."""
    client_obj._path_root = None
    calls = {"n": 0}

    def rpc(endpoint, arg):
        calls["n"] += 1
        if calls["n"] == 1:
            raise NetworkError("transient")
        return {"root_info": {"root_namespace_id": "9001", "home_namespace_id": "42"}}

    client_obj._rpc = rpc
    with pytest.raises(NetworkError):
        client_obj.path_root()
    assert client_obj.path_root() == "9001"


def test_download_leaves_the_previous_file_intact_when_the_stream_dies(
    client_obj, monkeypatch, tmp_path
):
    target = tmp_path / "clip.wav"
    target.write_bytes(b"the good original")

    class _Dying(_Resp):
        def iter_content(self, chunk_size=None):
            yield b"partial"
            raise _boom("connection reset mid-stream")

    fake, _boom = _fake_requests(lambda *a, **k: _Dying(200))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NetworkError):
        client_obj.download("/x/clip.wav", str(target))
    assert target.read_bytes() == b"the good original"
    assert list(tmp_path.iterdir()) == [target]


def test_download_writes_nothing_when_the_stream_dies_on_a_new_path(
    client_obj, monkeypatch, tmp_path
):
    class _Dying(_Resp):
        def iter_content(self, chunk_size=None):
            yield b"partial"
            raise _boom("connection reset mid-stream")

    fake, _boom = _fake_requests(lambda *a, **k: _Dying(200))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NetworkError):
        client_obj.download("/x/clip.wav", str(tmp_path / "clip.wav"))
    assert list(tmp_path.iterdir()) == []


def test_gunzip_refuses_to_expand_past_the_cap(client_obj, monkeypatch, tmp_path):
    bomb = gzip.compress(b"\0" * (4 << 20))
    monkeypatch.setenv("DROPBOX_MAX_GUNZIP_BYTES", str(1 << 20))
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[bomb]))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(ProviderError) as exc:
        client_obj.download("/x/seq.prproj", str(tmp_path / "seq.prproj"), gunzip=True)
    assert "cap" in str(exc.value).lower() or "limit" in str(exc.value).lower()
    assert list(tmp_path.iterdir()) == []


def test_expired_token_is_refreshed_once_and_the_call_retried(client_obj, monkeypatch):
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "r")
    monkeypatch.setenv("DROPBOX_APP_KEY", "k")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "s")
    calls = {"n": 0}

    def post(url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Resp(401, text='{"error_summary": "expired_access_token/"}')
        if "oauth2/token" in url:
            return _Resp(200, payload={"access_token": "fresh"})
        return _Resp(200, payload={"entries": [], "has_more": False})

    fake, _ = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.list_folder("/x") == []
    assert client_obj._token == "fresh"


def test_missing_scope_is_not_retried_as_a_stale_token(client_obj, monkeypatch):
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "r")
    monkeypatch.setenv("DROPBOX_APP_KEY", "k")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "s")
    fake, _ = _fake_requests(lambda *a, **k: _Resp(401, text='{"error_summary": "missing_scope/.."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(AuthError) as exc:
        client_obj.list_folder("/x")
    assert "generate a NEW token" in (exc.value.hint or "")


# --- writes: upload, link (#527) ---------------------------------------------


def _upload_post(seen, answer):
    def post(url, data=None, headers=None, timeout=None, **kw):
        seen.append({"url": url, "body": data.read() if hasattr(data, "read") else data,
                     "arg": json.loads(headers.get("Dropbox-API-Arg", "null")),
                     "raw_arg": headers.get("Dropbox-API-Arg", "")})
        return answer(len(seen))
    return post


def test_upload_adds_never_overwrites_and_reads_the_size_back(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "a.py"
    src.write_bytes(b"12345")
    seen = []
    fake, _ = _fake_requests(_upload_post(seen, lambda n: _Resp(200, payload={"size": 5})))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.upload(str(src), "/HOU2TOUCH/x/a.py")
    assert out == {"path": "/HOU2TOUCH/x/a.py", "bytes": 5, "status": "uploaded"}
    assert seen[0]["url"].endswith("/files/upload")
    assert seen[0]["body"] == b"12345"
    assert seen[0]["arg"]["mode"] == "add" and seen[0]["arg"]["autorename"] is False


def test_upload_reports_an_existing_path_and_leaves_it(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "a.py"
    src.write_bytes(b"1")
    conflict = '{"error_summary": "path/conflict/file/.."}'
    fake, _ = _fake_requests(_upload_post([], lambda n: _Resp(409, text=conflict)))
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/a.py")["status"] == "exists"


def test_upload_other_409_is_an_error_not_exists(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "a.py"
    src.write_bytes(b"1")
    other = '{"error_summary": "path/no_write_permission/.."}'
    fake, _ = _fake_requests(_upload_post([], lambda n: _Resp(409, text=other)))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(UsageError):
        client_obj.upload(str(src), "/x/a.py")


def test_upload_size_mismatch_is_a_provider_error(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "a.py"
    src.write_bytes(b"12345")
    fake, _ = _fake_requests(_upload_post([], lambda n: _Resp(200, payload={"size": 4})))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(ProviderError):
        client_obj.upload(str(src), "/x/a.py")


def _session_post(seen, answer=None):
    """Records each content call; answers start/append/finish like Dropbox does."""
    def post(url, data=None, headers=None, timeout=None, **kw):
        body = data.read() if hasattr(data, "read") else data
        seen.append({"url": url, "body": body,
                     "arg": json.loads(headers.get("Dropbox-API-Arg", "null"))})
        if answer is not None:
            got = answer(len(seen), seen[-1])
            if got is not None:
                return got
        if url.endswith("/upload_session/start"):
            return _Resp(200, payload={"session_id": "S1"})
        if url.endswith("/upload_session/append_v2"):
            return _Resp(200, text="", payload={})
        if url.endswith("/upload_session/finish"):
            return _Resp(200, payload={"size": seen[-1]["arg"]["cursor"]["offset"]})
        return _Resp(200, payload={"size": len(body or b"")})
    return post


def _small_limits(monkeypatch, limit=4, chunk=4):
    from h2t_ops.connectors.dropbox import client as dmod

    monkeypatch.setattr(dmod, "UPLOAD_LIMIT", limit)
    monkeypatch.setattr(dmod, "CHUNK_SIZE", chunk)
    monkeypatch.setattr(dmod.time, "sleep", lambda s: None)
    return dmod


def test_upload_over_the_single_request_limit_goes_through_a_session(
        client_obj, monkeypatch, tmp_path, capsys):
    _small_limits(monkeypatch)
    src = tmp_path / "big.bin"
    src.write_bytes(b"0123456789")
    seen = []
    fake, _ = _fake_requests(_session_post(seen))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.upload(str(src), "/x/big.bin")
    assert out == {"path": "/x/big.bin", "bytes": 10, "status": "uploaded"}
    steps = [c["url"].rsplit("/2/", 1)[1] for c in seen]
    assert steps == ["files/upload_session/start", "files/upload_session/append_v2",
                     "files/upload_session/append_v2", "files/upload_session/finish"]
    assert [c["body"] for c in seen] == [b"0123", b"4567", b"89", b""]
    assert [c["arg"]["cursor"]["offset"] for c in seen[1:]] == [4, 8, 10]
    assert all(c["arg"]["cursor"]["session_id"] == "S1" for c in seen[1:])
    commit = seen[-1]["arg"]["commit"]
    assert commit["path"] == "/x/big.bin"
    assert commit["mode"] == "add" and commit["autorename"] is False
    err = capsys.readouterr().err
    assert "chunk 3/3" in err  # progress per chunk, on stderr


def test_session_finish_path_conflict_is_exists_not_overwrite(client_obj, monkeypatch, tmp_path):
    _small_limits(monkeypatch)
    src = tmp_path / "big.bin"
    src.write_bytes(b"0123456789")
    conflict = '{"error_summary": "path/conflict/file/.."}'

    def answer(n, call):
        if call["url"].endswith("/finish"):
            return _Resp(409, text=conflict)
        return None

    fake, _ = _fake_requests(_session_post([], answer))
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/big.bin")["status"] == "exists"


def test_session_append_resent_after_a_reset_that_landed_is_accepted(
        client_obj, monkeypatch, tmp_path):
    """The reset came after Dropbox took the chunk: it answers incorrect_offset with
    the offset we expected next, and the upload goes on instead of failing."""
    _small_limits(monkeypatch)
    src = tmp_path / "big.bin"
    src.write_bytes(b"0123456789")
    seen = []
    box = []

    def answer(n, call):
        if n == 2:
            raise box[0]("connection reset")
        if n == 3:
            return _Resp(409, payload={"error_summary": "incorrect_offset/..",
                                       "error": {".tag": "incorrect_offset",
                                                 "correct_offset": 8}})
        return None

    fake, exc_cls = _fake_requests(_session_post(seen, answer))
    box.append(exc_cls)
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/big.bin")["status"] == "uploaded"
    assert seen[-1]["arg"]["cursor"]["offset"] == 10


def test_session_incorrect_offset_elsewhere_fails_loud(client_obj, monkeypatch, tmp_path):
    _small_limits(monkeypatch)
    src = tmp_path / "big.bin"
    src.write_bytes(b"0123456789")

    def answer(n, call):
        if n == 2:
            return _Resp(409, payload={"error_summary": "incorrect_offset/..",
                                       "error": {".tag": "incorrect_offset",
                                                 "correct_offset": 2}})
        return None

    fake, _ = _fake_requests(_session_post([], answer))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(UsageError):
        client_obj.upload(str(src), "/x/big.bin")


def test_upload_retries_a_connection_reset_then_succeeds(client_obj, monkeypatch, tmp_path):
    from h2t_ops.connectors.dropbox import client as dmod

    monkeypatch.setattr(dmod.time, "sleep", lambda s: None)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"12345")
    bodies = []

    def post(url, data=None, headers=None, timeout=None, **kw):
        bodies.append(data.read())
        if len(bodies) == 1:
            raise exc_cls("ConnectionResetError(10054)")
        return _Resp(200, payload={"size": 5})

    fake, exc_cls = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/a.mp4")["status"] == "uploaded"
    assert bodies == [b"12345", b"12345"]  # the file is read again from the start


def test_upload_gives_up_after_the_retries_and_fails(client_obj, monkeypatch, tmp_path):
    from h2t_ops.connectors.dropbox import client as dmod

    monkeypatch.setattr(dmod.time, "sleep", lambda s: None)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"1")
    sent = []

    def post(*a, **k):
        sent.append(1)
        raise exc_cls("connection reset")

    fake, exc_cls = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(NetworkError):
        client_obj.upload(str(src), "/x/a.mp4")
    assert len(sent) == dmod.UPLOAD_RETRIES + 1


def test_upload_rate_limit_waits_retry_after(client_obj, monkeypatch, tmp_path):
    from h2t_ops.connectors.dropbox import client as dmod

    waits = []
    monkeypatch.setattr(dmod.time, "sleep", waits.append)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"12")
    answers = [_Resp(429, text="too_many_write_operations", headers={"Retry-After": "7"}),
               _Resp(200, payload={"size": 2})]
    fake, _ = _fake_requests(lambda *a, **k: answers.pop(0))
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/a.mp4")["status"] == "uploaded"
    assert waits == [7.0]


def test_session_chunk_rate_limit_waits_retry_after(client_obj, monkeypatch, tmp_path):
    dmod = _small_limits(monkeypatch)
    waits = []
    monkeypatch.setattr(dmod.time, "sleep", waits.append)
    src = tmp_path / "big.bin"
    src.write_bytes(b"0123456789")
    seen = []

    def answer(n, call):
        if n == 2:
            return _Resp(429, text="too_many_requests", headers={"Retry-After": "3"})
        return None

    fake, _ = _fake_requests(_session_post(seen, answer))
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/big.bin")["status"] == "uploaded"
    assert waits == [3.0]
    assert [c["arg"]["cursor"]["offset"] for c in seen[1:]] == [4, 4, 8, 10]


def test_a_name_dropbox_refuses_is_skipped_not_an_error(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "desktop.ini"
    src.write_bytes(b"[x]")
    refused = '{"error_summary": "path/disallowed_name/.."}'
    fake, _ = _fake_requests(_upload_post([], lambda n: _Resp(409, text=refused)))
    monkeypatch.setitem(sys.modules, "requests", fake)
    out = client_obj.upload(str(src), "/x/desktop.ini")
    assert out == {"path": "/x/desktop.ini", "bytes": None,
                   "status": "skipped: rejected by Dropbox"}


def test_upload_header_is_ascii_for_a_non_ascii_name(client_obj, monkeypatch, tmp_path):
    src = tmp_path / "a.py"
    src.write_bytes(b"1")
    seen = []
    fake, _ = _fake_requests(_upload_post(seen, lambda n: _Resp(200, payload={"size": 1})))
    monkeypatch.setitem(sys.modules, "requests", fake)
    client_obj.upload(str(src), "/Курс/a.py")
    seen[0]["raw_arg"].encode("ascii")  # raises if not ASCII
    assert seen[0]["arg"]["path"] == "/Курс/a.py"


def test_upload_refreshes_an_expired_token_and_resends(client_obj, monkeypatch, tmp_path):
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "r")
    monkeypatch.setenv("DROPBOX_APP_KEY", "k")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "s")
    src = tmp_path / "a.py"
    src.write_bytes(b"12")
    bodies = []

    def post(url, data=None, headers=None, timeout=None, **kw):
        if "oauth2/token" in url:
            return _Resp(200, payload={"access_token": "fresh"})
        bodies.append(data.read())
        if len(bodies) == 1:
            return _Resp(401, text='{"error_summary": "expired_access_token/"}')
        return _Resp(200, payload={"size": 2})

    fake, _ = _fake_requests(post)
    monkeypatch.setitem(sys.modules, "requests", fake)
    assert client_obj.upload(str(src), "/x/a.py")["status"] == "uploaded"
    assert client_obj._token == "fresh"
    assert bodies == [b"12", b"12"]  # the whole file is sent again


def test_link_returns_the_existing_link_without_creating(client_obj):
    client_obj._rpc = MagicMock(return_value={"links": [{
        "url": "https://dropbox/x",
        "link_permissions": {"resolved_visibility": {".tag": "public"}}}]})
    out = client_obj.link("/x/a.py")
    assert out == {"path": "/x/a.py", "url": "https://dropbox/x", "created": False,
                   "visibility": "public"}
    assert client_obj._rpc.call_count == 1


def test_link_creates_a_public_one_when_none_exists(client_obj):
    client_obj._rpc = MagicMock(side_effect=[{"links": []}, {"url": "https://dropbox/new"}])
    out = client_obj.link("/x/a.py")
    assert out["created"] is True and out["url"] == "https://dropbox/new"
    endpoint, arg = client_obj._rpc.call_args_list[1].args
    assert endpoint == "sharing/create_shared_link_with_settings"
    assert arg["settings"] == {"requested_visibility": "public"}


def test_missing_scope_hint_names_every_scope_the_connector_calls(client_obj, monkeypatch):
    """path_root() hits users/get_current_account on the first request, and that
    route needs account_info.read — a hint listing only files.* sends the user
    back for an identically insufficient token."""
    fake, _ = _fake_requests(lambda *a, **k: _Resp(401, text='{"error_summary": "missing_scope/.."}'))
    monkeypatch.setitem(sys.modules, "requests", fake)
    with pytest.raises(AuthError) as exc:
        client_obj._rpc("files/list_folder", {"path": ""})
    hint = exc.value.hint or ""
    for scope in ("account_info.read", "files.metadata.read", "files.content.read",
                  "sharing.read"):
        assert scope in hint, f"hint does not name {scope}"
