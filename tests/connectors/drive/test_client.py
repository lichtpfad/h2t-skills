"""Tests for h2t_ops.connectors.drive.client.DriveClient."""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError, UsageError,
)


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


@pytest.fixture
def client_obj():
    """Construct a DriveClient WITHOUT running __init__ (no network / SDK)."""
    from h2t_ops.connectors.drive.client import DriveClient
    c = object.__new__(DriveClient)
    c.service = MagicMock()
    return c


def test_module_has_no_module_level_google_import():
    src = Path("h2t_ops/connectors/drive/client.py").read_text(encoding="utf-8")
    forbidden = (
        "import google",
        "from google",
        "import googleapiclient",
        "from googleapiclient",
    )
    top_level = [ln for ln in src.splitlines() if ln and not ln.startswith((" ", "\t"))]
    assert not any(ln.startswith(forbidden) for ln in top_level)


def test_client_init_consumes_shared_substrate(monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    calls = {}

    def fake_resolve(service_name, scopes):
        calls["resolve"] = (service_name, scopes)
        return "creds"

    def fake_build(api, version, creds):
        calls["build"] = (api, version, creds)
        return "service"

    monkeypatch.setattr(dmod, "resolve_google_credentials", fake_resolve)
    monkeypatch.setattr(dmod, "build_google_service", fake_build)

    c = dmod.DriveClient()
    assert c.service == "service"
    assert calls["resolve"] == ("drive", [DRIVE_SCOPE])
    assert calls["build"] == ("drive", "v3", "creds")


def test_list_files_paginates_and_returns_rows(client_obj):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.side_effect = [
        {
            "files": [
                {"id": "1", "name": "A", "mimeType": "text/plain", "modifiedTime": "t1"},
            ],
            "nextPageToken": "next",
        },
        {
            "files": [
                {"id": "2", "name": "B", "mimeType": "text/plain", "modifiedTime": "t2"},
            ],
        },
    ]

    rows = client_obj.list_files()
    assert len(rows) == 2
    assert rows[0]["id"] == "1"
    assert {"id", "name", "mimeType", "modifiedTime"}.issubset(rows[0])


@pytest.mark.parametrize(
    ("mime_filter", "mime_type"),
    [
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("folder", "application/vnd.google-apps.folder"),
    ],
)
def test_search_files_applies_mime_filter(client_obj, mime_filter, mime_type):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {"files": []}
    client_obj.search_files("project", mime_filter=mime_filter)
    assert f"mimeType='{mime_type}'" in files.list.call_args.kwargs["q"]


def test_list_folders_returns_folder_rows(client_obj):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "f1",
                "name": "Folder",
                "mimeType": "application/vnd.google-apps.folder",
                "modifiedTime": "t",
            },
        ]
    }
    rows = client_obj.list_folders()
    assert rows[0]["mimeType"] == "application/vnd.google-apps.folder"
    assert "mimeType='application/vnd.google-apps.folder'" in files.list.call_args.kwargs["q"]


def test_download_default_dest_is_cwd_with_original_name(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    monkeypatch.chdir(tmp_path)
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "report.txt",
        "mimeType": "text/plain",
        "size": "4",
    }
    files.get_media.return_value = object()

    class FakeDownload:
        def __init__(self, buf, request):
            self.buf = buf
            self.done = False

        def next_chunk(self):
            self.buf.write(b"data")
            return None, True

    monkeypatch.setattr(dmod, "_media_io_base_download", lambda: FakeDownload)
    result = client_obj.download_file("file1")
    assert result["saved_path"] == str(tmp_path / "report.txt")
    assert Path(result["saved_path"]).read_bytes() == b"data"


def test_download_envelope_size_is_optional(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    monkeypatch.chdir(tmp_path)
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "report.txt",
        "mimeType": "text/plain",
    }

    class FakeDownload:
        def __init__(self, buf, request):
            self.buf = buf

        def next_chunk(self):
            self.buf.write(b"data")
            return None, True

    monkeypatch.setattr(dmod, "_media_io_base_download", lambda: FakeDownload)
    result = client_obj.download_file("file1")
    assert "size" not in result


def test_download_never_writes_to_stdout(client_obj, tmp_path, monkeypatch, capsys):
    from h2t_ops.connectors.drive import client as dmod

    monkeypatch.chdir(tmp_path)
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {"name": "a.bin", "mimeType": "application/octet-stream"}

    class FakeDownload:
        def __init__(self, buf, request):
            self.buf = buf

        def next_chunk(self):
            self.buf.write(b"x")
            return None, True

    monkeypatch.setattr(dmod, "_media_io_base_download", lambda: FakeDownload)
    client_obj.download_file("file1")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_export_text_format_returns_text(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    files.export.return_value.execute.return_value = b"hello"
    result = client_obj.export_file("doc1", fmt="text", to_stdout=True)
    assert result["text"] == "hello"
    assert result["source_mime"] == "application/vnd.google-apps.document"
    assert result["export_mime"] == "text/plain"
    assert result["format"] == "text"


def test_export_md_requires_html2text(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    files.export.return_value.execute.return_value = b"<h1>Hello</h1>"
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "html2text", None)
        with pytest.raises(ConfigError):
            client_obj.export_file("doc1", fmt="md")


@pytest.mark.parametrize("fmt", ("docx", "xlsx", "pdf", "pptx"))
def test_export_print_rejects_binary_formats(client_obj, fmt):
    with pytest.raises(UsageError):
        client_obj.export_file("doc1", fmt=fmt, to_stdout=True)
    assert not client_obj.service.files.return_value.export.called


@pytest.mark.parametrize("folder", (None, ""))
def test_upload_requires_folder_name(client_obj, folder):
    with pytest.raises(UsageError):
        client_obj.upload_file("some.md", folder=folder)


def test_upload_resolves_folder_by_name(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    src = tmp_path / "note.md"
    src.write_text("# Note", encoding="utf-8")
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder1", folder))
    monkeypatch.setattr(dmod, "_media_file_upload", lambda: lambda *a, **k: "media")
    files = client_obj.service.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "new1",
        "name": "note",
        "mimeType": "application/vnd.google-apps.document",
        "webViewLink": "https://drive/new1",
    }
    result = client_obj.upload_file(str(src), folder="Target")
    assert result["file_id"] == "new1"
    assert files.create.call_args.kwargs["body"]["parents"] == ["folder1"]


def test_upload_ambiguous_folder_raises_usageerror(client_obj):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [{"id": "1", "name": "Target"}, {"id": "2", "name": "Target"}]
    }
    with pytest.raises(UsageError) as ei:
        client_obj._resolve_folder_id("Target")
    assert "ambiguous folder" in str(ei.value)


def test_upload_missing_folder_raises_notfounderror(client_obj):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {"files": []}
    with pytest.raises(NotFoundError):
        client_obj._resolve_folder_id("Missing")


def test_http_401_maps_to_autherror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=401)), op="list files")
    assert isinstance(err, AuthError)


def test_http_404_maps_to_notfounderror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=404)), op="get file")
    assert isinstance(err, NotFoundError)


def test_http_500_maps_to_providererror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=500)), op="list files")
    assert isinstance(err, ProviderError)


def test_transport_timeout_maps_to_networkerror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(socket.timeout("timed out"), op="download file")
    assert isinstance(err, NetworkError)


def test_missing_drive_scope_raises_configerror(tmp_path, monkeypatch):
    from tests.core.test_google_auth import CAL_SCOPE, GMAIL_READ_SCOPE, _write_token

    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    _write_token(shared, [CAL_SCOPE, GMAIL_READ_SCOPE], expiry="2099-01-01T00:00:00Z")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from h2t_ops.connectors.drive.client import DriveClient
    with pytest.raises(ConfigError) as ei:
        DriveClient()
    assert "Google OAuth bootstrap" in (ei.value.hint or "")
