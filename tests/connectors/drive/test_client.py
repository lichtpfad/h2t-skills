"""Tests for h2t_ops.connectors.drive.client.DriveClient."""
from __future__ import annotations

import sys
from pathlib import Path
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

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


class FakeHttpError(Exception):
    def __init__(self, status: int, message: str = "error"):
        super().__init__(message)
        self.resp = SimpleNamespace(status=status)


@pytest.fixture
def client_obj():
    """Construct a DriveClient WITHOUT running __init__ (no network / SDK)."""
    from h2t_ops.connectors.drive.client import DriveClient
    c = object.__new__(DriveClient)
    c.service = MagicMock()
    c._docs_service = MagicMock()
    c._creds = "creds"
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


def test_create_folder_defaults_to_root(client_obj):
    files = client_obj.service.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "folder1",
        "name": "Projects",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["root"],
        "webViewLink": "https://drive/folder1",
    }

    result = client_obj.create_folder("Projects")

    assert result["file_id"] == "folder1"
    assert result["parent_name"] == "root"
    assert files.create.call_args.kwargs["body"] == {
        "name": "Projects",
        "mimeType": "application/vnd.google-apps.folder",
    }
    assert files.create.call_args.kwargs["supportsAllDrives"] is True


def test_create_folder_resolves_parent(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda parent: ("parent1", "Target", False))
    files.create.return_value.execute.return_value = {
        "id": "folder2",
        "name": "Archive",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["parent1"],
        "webViewLink": "https://drive/folder2",
    }

    result = client_obj.create_folder("Archive", parent="Target")

    assert result["parent_name"] == "Target"
    assert files.create.call_args.kwargs["body"]["parents"] == ["parent1"]


def test_rename_file_updates_name_and_returns_metadata(client_obj):
    files = client_obj.service.files.return_value
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "renamed.txt",
        "mimeType": "text/plain",
        "webViewLink": "https://drive/file1",
        "modifiedTime": "2026-05-25T18:00:00Z",
    }

    result = client_obj.rename_file("file1", "renamed.txt")

    assert result["file_id"] == "file1"
    assert result["name"] == "renamed.txt"
    assert result["mimeType"] == "text/plain"
    assert result["web_view_link"] == "https://drive/file1"
    assert result["modifiedTime"] == "2026-05-25T18:00:00Z"
    assert files.update.call_args.kwargs["fileId"] == "file1"
    assert files.update.call_args.kwargs["body"] == {"name": "renamed.txt"}
    assert files.update.call_args.kwargs["fields"] == "id, name, mimeType, webViewLink, modifiedTime"
    assert files.update.call_args.kwargs["supportsAllDrives"] is True


def test_rename_file_requires_non_empty_name(client_obj):
    with pytest.raises(UsageError):
        client_obj.rename_file("file1", "   ")


def test_copy_file_without_folder_copies_in_place(client_obj):
    files = client_obj.service.files.return_value
    files.copy.return_value.execute.return_value = {
        "id": "copy1",
        "name": "Copy of report.txt",
        "mimeType": "text/plain",
        "parents": ["parent1"],
        "webViewLink": "https://drive/copy1",
    }

    result = client_obj.copy_file("file1")

    assert result["file_id"] == "copy1"
    assert result["source_file_id"] == "file1"
    assert files.copy.call_args.kwargs["fileId"] == "file1"
    assert files.copy.call_args.kwargs["supportsAllDrives"] is True


def test_copy_file_with_name_and_folder_sets_body(client_obj):
    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "folder1",
                "name": "Target",
                "mimeType": "application/vnd.google-apps.folder",
            },
        ],
    }
    files.copy.return_value.execute.return_value = {
        "id": "copy1",
        "name": "copy.txt",
        "mimeType": "text/plain",
        "parents": ["folder1"],
        "webViewLink": "https://drive/copy1",
    }

    result = client_obj.copy_file("file1", new_name=" copy.txt ", folder="Target")

    assert result["parents"] == ["folder1"]
    assert files.list.call_args.kwargs["q"] == (
        "name='Target' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    assert files.copy.call_args.kwargs["body"] == {
        "name": "copy.txt",
        "parents": ["folder1"],
    }


def test_copy_file_to_explicit_root_sets_parents_field(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: (None, "root", False))
    files.copy.return_value.execute.return_value = {
        "id": "copy-root",
        "name": "copy.txt",
        "mimeType": "text/plain",
        "parents": ["root"],
        "webViewLink": "https://drive/copy-root",
    }

    result = client_obj.copy_file("file1", new_name=" copy.txt ", folder="root")

    assert files.copy.call_args.kwargs["body"] == {
        "name": "copy.txt",
        "parents": ["root"],
    }
    assert result["parents"] == ["root"]


def test_move_file_replaces_existing_parents(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(
        client_obj,
        "_resolve_folder_id",
        lambda folder: ("folder2", "Archive", False),
    )
    files.get.return_value.execute.side_effect = [
        {
            "id": "folder2",
            "name": "Archive",
            "mimeType": "application/vnd.google-apps.folder",
        },
        {
            "id": "file1",
            "name": "report.txt",
            "mimeType": "text/plain",
            "parents": ["parent1", "parentA"],
        },
    ]
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": ["folder2"],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id="Archive")

    assert result["file_id"] == "file1"
    assert result["parents"] == ["folder2"]
    assert files.update.call_args.kwargs["addParents"] == "folder2"
    assert files.update.call_args.kwargs["removeParents"] == "parent1,parentA"
    assert files.update.call_args.kwargs["fields"] == "id, name, mimeType, parents, webViewLink"
    assert files.update.call_args.kwargs["supportsAllDrives"] is True


def test_move_file_requires_destination_to_be_folder(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(
        client_obj,
        "_resolve_folder_id",
        lambda folder: ("file-as-dest", "Bad", False),
    )
    files.get.return_value.execute.return_value = {
        "id": "file-as-dest",
        "name": "Bad",
        "mimeType": "text/plain",
    }

    with pytest.raises(UsageError) as ei:
        client_obj.move_file("file1", destination_folder_id="Bad")

    assert str(ei.value) == "destination 'Bad' is not a Drive folder"


def test_move_file_requires_non_empty_destination(client_obj):
    with pytest.raises(UsageError) as ei:
        client_obj.move_file("file1", destination_folder_id="   ")

    assert str(ei.value) == "drive move: destination folder is required"


def test_move_file_strips_destination_before_resolving(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    resolved = {}

    def fake_resolve(folder):
        resolved["folder"] = folder
        return None, "root", False

    monkeypatch.setattr(client_obj, "_resolve_folder_id", fake_resolve)
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": ["parent1"],
    }
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": [],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id="  root  ")

    assert resolved["folder"] == "root"
    assert result["parents"] == []
    assert files.update.call_args.kwargs["addParents"] == "root"


def test_move_file_to_root_skips_folder_validation_fetch(client_obj, monkeypatch):
    files = client_obj.service.files.return_value
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: (None, "root", False))
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": ["parent1"],
    }
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": [],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id="root")

    assert result["parents"] == []
    assert files.update.call_args.kwargs["addParents"] == "root"
    assert files.update.call_args.kwargs["removeParents"] == "parent1"
    files.get.assert_called_once_with(
        fileId="file1",
        fields="id, name, mimeType, parents",
        supportsAllDrives=True,
    )


def test_move_file_to_shared_drive_root_skips_destination_file_validation(client_obj):
    shared_drive_id = "0AExampleShared123"
    files = client_obj.service.files.return_value
    drives = client_obj.service.drives.return_value
    files.get.return_value.execute.side_effect = [
        FakeHttpError(404, "missing file"),
        {
            "id": "file1",
            "name": "report.txt",
            "mimeType": "text/plain",
            "parents": ["parent1"],
        },
    ]
    drives.get.return_value.execute.return_value = {
        "id": shared_drive_id,
        "name": "Shared Root",
    }
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "parents": [shared_drive_id],
        "webViewLink": "https://drive/file1",
    }

    result = client_obj.move_file("file1", destination_folder_id=shared_drive_id)

    assert result["parents"] == [shared_drive_id]
    assert files.update.call_args.kwargs["addParents"] == shared_drive_id
    assert files.update.call_args.kwargs["removeParents"] == "parent1"
    assert files.get.call_count == 2
    files.get.assert_any_call(
        fileId=shared_drive_id,
        fields="id,name,mimeType",
        supportsAllDrives=True,
    )
    files.get.assert_any_call(
        fileId="file1",
        fields="id, name, mimeType, parents",
        supportsAllDrives=True,
    )
    drives.get.assert_called_once_with(
        driveId=shared_drive_id,
        fields="id,name",
    )


def test_list_document_tabs_flattens_nested_tabs(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "doc1",
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
        "webViewLink": "https://docs.google.com/document/d/doc1/edit",
    }
    client_obj._docs_service.documents.return_value.get.return_value.execute.return_value = {
        "documentId": "doc1",
        "title": "Doc",
        "tabs": [
            {
                "tabProperties": {
                    "tabId": "tab-root",
                    "title": "Root",
                    "index": 0,
                    "nestingLevel": 0,
                },
                "childTabs": [
                    {
                        "tabProperties": {
                            "tabId": "tab-child",
                            "title": "Child",
                            "parentTabId": "tab-root",
                            "index": 0,
                            "nestingLevel": 1,
                            "iconEmoji": "📄",
                        },
                    },
                ],
            },
        ],
    }

    result = client_obj.list_document_tabs("doc1")

    assert result["kind"] == "google_docs_tabs/v1"
    assert result["document_id"] == "doc1"
    assert result["count"] == 2
    assert result["tabs"][0]["tab_id"] == "tab-root"
    assert result["tabs"][0]["has_children"] is True
    assert result["tabs"][1]["parent_tab_id"] == "tab-root"
    assert result["tabs"][1]["icon_emoji"] == "📄"


def test_list_document_tabs_requires_google_doc_mime(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "Sheet",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    with pytest.raises(UsageError):
        client_obj.list_document_tabs("file1")


def test_add_document_tab_returns_normalized(client_obj):
    client_obj.service.files.return_value.get.return_value.execute.return_value = {
        "id": "doc1",
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    client_obj._docs_service.documents.return_value.batchUpdate.return_value.execute.return_value = {
        "replies": [
            {
                "addDocumentTab": {
                    "tabProperties": {
                        "tabId": "new-tab-id",
                        "title": "Methods",
                        "index": 1,
                        "nestingLevel": 0,
                    }
                }
            }
        ]
    }

    result = client_obj.add_document_tab("doc1", "Methods")

    req = client_obj._docs_service.documents.return_value.batchUpdate.call_args.kwargs
    assert req["documentId"] == "doc1"
    assert req["body"]["requests"][0]["addDocumentTab"]["tabProperties"]["title"] == "Methods"
    assert result["kind"] == "google_docs_tab/v1"
    assert result["tab_id"] == "new-tab-id"
    assert result["title"] == "Methods"
    assert result["index"] == 1


def test_add_document_tab_requires_google_doc_mime(client_obj):
    client_obj.service.files.return_value.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "Sheet",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    with pytest.raises(UsageError):
        client_obj.add_document_tab("file1", "New Tab")


def test_add_document_tab_maps_sdk_exc(client_obj):
    from h2t_ops.core.errors import ProviderError
    client_obj.service.files.return_value.get.return_value.execute.side_effect = RuntimeError("boom")

    with pytest.raises(ProviderError):
        client_obj.add_document_tab("doc1", "New Tab")


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


def test_export_md_falls_back_without_html2text(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    files.export.return_value.execute.return_value = b"<h1>Hello</h1><p>Body</p>"
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "html2text", None)
        result = client_obj.export_file("doc1", fmt="md", to_stdout=True)

    assert result["format"] == "md"
    assert "# Hello" in result["text"]
    assert "Body" in result["text"]


def test_export_txt_alias_returns_text(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    files.export.return_value.execute.return_value = b"hello"

    result = client_obj.export_file("doc1", fmt="txt", to_stdout=True)

    assert result["text"] == "hello"
    assert result["export_mime"] == "text/plain"
    assert result["format"] == "text"


@pytest.mark.parametrize("fmt", ("docx", "xlsx", "pdf", "pptx"))
def test_export_print_rejects_binary_formats(client_obj, fmt):
    with pytest.raises(UsageError):
        client_obj.export_file("doc1", fmt=fmt, to_stdout=True)
    assert not client_obj.service.files.return_value.export.called


@pytest.mark.parametrize("fmt", ("pdf", "docx"))
def test_export_binary_format_writes_bytes_verbatim(client_obj, tmp_path, fmt):
    # Binary export body with a non-UTF-8 byte (0xd3) must not be decoded.
    payload = b"%PDF-1.4\n\xd3\xd3binary\x00body"
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    files.export.return_value.execute.return_value = payload
    dest = tmp_path / f"out.{fmt}"
    result = client_obj.export_file("doc1", fmt=fmt, dest=dest)
    assert dest.read_bytes() == payload
    assert result["saved_path"] == str(dest)
    assert result["size"] == len(payload)
    assert "text" not in result


@pytest.mark.parametrize("folder", (None, ""))
def test_upload_requires_folder_name(client_obj, folder):
    with pytest.raises(UsageError):
        client_obj.upload_file("some.md", folder=folder)


def test_upload_resolves_folder_by_name(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    src = tmp_path / "note.md"
    src.write_text("# Note", encoding="utf-8")
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder1", folder, False))
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


def _sheets_values_mock(client_obj):
    client_obj._sheets_service = MagicMock()
    return client_obj._sheets_service.spreadsheets.return_value.values.return_value


def test_sheets_read_returns_values(client_obj):
    values = _sheets_values_mock(client_obj)
    values.get.return_value.execute.return_value = {
        "range": "Sheet1!A1:B2", "values": [["a", "b"], ["c", "d"]],
    }
    result = client_obj.sheets_read("sheet1", cell_range="Sheet1!A1:B2")
    assert values.get.call_args.kwargs == {
        "spreadsheetId": "sheet1", "range": "Sheet1!A1:B2",
    }
    assert result["values"] == [["a", "b"], ["c", "d"]]
    assert result["range"] == "Sheet1!A1:B2"


def test_sheets_update_single_value_uses_raw_and_wraps_2d(client_obj):
    values = _sheets_values_mock(client_obj)
    values.update.return_value.execute.return_value = {
        "updatedRange": "Sheet1!B12", "updatedCells": 1,
        "updatedRows": 1, "updatedColumns": 1,
    }
    result = client_obj.sheets_update("sheet1", cell_range="Sheet1!B12", value="hi")
    kwargs = values.update.call_args.kwargs
    assert kwargs["spreadsheetId"] == "sheet1"
    assert kwargs["range"] == "Sheet1!B12"
    assert kwargs["valueInputOption"] == "RAW"
    assert kwargs["body"] == {"values": [["hi"]]}  # single value wrapped to 2D
    assert result["updated_cells"] == 1


def test_sheets_update_values_file_reads_2d_array(client_obj, tmp_path):
    values = _sheets_values_mock(client_obj)
    values.update.return_value.execute.return_value = {"updatedRange": "Sheet1!B12:C12"}
    f = tmp_path / "cells.json"
    f.write_text('[["x", "y"]]', encoding="utf-8")
    client_obj.sheets_update("sheet1", cell_range="Sheet1!B12:C12", values_file=str(f))
    assert values.update.call_args.kwargs["body"] == {"values": [["x", "y"]]}


def test_sheets_update_requires_exactly_one_of_value_or_file(client_obj):
    _sheets_values_mock(client_obj)
    with pytest.raises(UsageError):
        client_obj.sheets_update("sheet1", cell_range="A1")  # neither
    with pytest.raises(UsageError):
        client_obj.sheets_update("sheet1", cell_range="A1", value="v", values_file="f.json")


def test_sheets_update_rejects_non_2d_values_file(client_obj, tmp_path):
    _sheets_values_mock(client_obj)
    f = tmp_path / "bad.json"
    f.write_text('["flat", "list"]', encoding="utf-8")  # 1D, not 2D
    with pytest.raises(UsageError):
        client_obj.sheets_update("sheet1", cell_range="A1", values_file=str(f))


def test_sheets_update_missing_values_file_raises_usageerror(client_obj):
    _sheets_values_mock(client_obj)
    with pytest.raises(UsageError):
        client_obj.sheets_update("sheet1", cell_range="A1", values_file="nonexistent.json")


def test_upload_title_overrides_document_name(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    src = tmp_path / "brief.md"
    src.write_text("# Brief", encoding="utf-8")
    monkeypatch.setattr(dmod, "_media_file_upload", lambda: lambda *a, **k: "media")
    files = client_obj.service.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "new2", "name": "Interview Guide",
        "mimeType": "application/vnd.google-apps.document",
        "webViewLink": "https://drive/new2",
    }
    client_obj.upload_file(str(src), folder=None, parent_id="folder1",
                           title="Interview Guide")
    body = files.create.call_args.kwargs["body"]
    # --title overrides the filename-derived name.
    assert body["name"] == "Interview Guide"
    # Still converts markdown to a native Google Doc.
    assert body["mimeType"] == "application/vnd.google-apps.document"


def test_upload_folder_dry_run_preserves_relative_paths(client_obj, tmp_path):
    root = tmp_path / "deploy"
    (root / "raw" / "videos").mkdir(parents=True)
    (root / "raw" / "assets").mkdir(parents=True)
    (root / "presentation.html").write_text("<video></video>", encoding="utf-8")
    (root / "raw" / "videos" / "clip.mp4").write_bytes(b"mp4")
    (root / "raw" / "assets" / "cover.png").write_bytes(b"png")

    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {"files": []}

    result = client_obj.upload_folder(root, parent_id="drive-folder", dry_run=True)
    entries = result["entries"]
    by_rel = {entry["relative_path"]: entry for entry in entries}

    assert by_rel["raw"]["action"] == "folder_create"
    assert by_rel["raw/videos"]["action"] == "folder_create"
    assert by_rel["raw/assets"]["action"] == "folder_create"
    assert by_rel["presentation.html"]["action"] == "file_upload"
    assert by_rel["raw/videos/clip.mp4"]["action"] == "file_upload"
    assert by_rel["raw/assets/cover.png"]["action"] == "file_upload"
    assert by_rel["presentation.html"]["mimeType"] == "text/html"
    assert result["summary"]["total"] == 6
    assert not files.create.called
    assert not files.update.called


def test_upload_folder_skips_existing_file_by_default(client_obj, tmp_path):
    root = tmp_path / "deploy"
    root.mkdir()
    (root / "presentation.html").write_text("<html></html>", encoding="utf-8")

    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "existing1",
                "name": "presentation.html",
                "mimeType": "text/html",
                "webViewLink": "https://drive/existing1",
            },
        ],
    }

    result = client_obj.upload_folder(root, parent_id="drive-folder")
    entry = result["entries"][0]

    assert entry["action"] == "file_skipped"
    assert entry["file_id"] == "existing1"
    assert not files.create.called
    assert not files.update.called


def test_upload_folder_updates_existing_file_when_requested(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    root = tmp_path / "deploy"
    root.mkdir()
    (root / "presentation.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(dmod, "_media_file_upload", lambda: lambda *a, **k: "media")

    files = client_obj.service.files.return_value
    files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "existing1",
                "name": "presentation.html",
                "mimeType": "text/html",
            },
        ],
    }
    files.update.return_value.execute.return_value = {
        "id": "existing1",
        "name": "presentation.html",
        "mimeType": "text/html",
        "webViewLink": "https://drive/existing1",
    }

    result = client_obj.upload_folder(
        root,
        parent_id="drive-folder",
        update_existing=True,
    )
    entry = result["entries"][0]

    assert entry["action"] == "file_updated"
    assert entry["file_id"] == "existing1"
    assert files.update.call_args.kwargs["fileId"] == "existing1"
    assert files.update.call_args.kwargs["media_body"] == "media"
    assert not files.create.called


def test_upload_folder_requires_directory(client_obj, tmp_path):
    src = tmp_path / "note.txt"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(UsageError):
        client_obj.upload_folder(src, parent_id="drive-folder")


def test_drive_upload_mime_fallbacks_cover_web_assets():
    from h2t_ops.connectors.drive.client import _guess_mime

    assert _guess_mime(Path("image.webp")) == "image/webp"
    assert _guess_mime(Path("diagram.svg")) == "image/svg+xml"
    assert _guess_mime(Path("clip.mkv")) == "video/x-matroska"


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


def test_resolve_folder_id_like_missing_falls_back_to_name_search(client_obj):
    folder_id = "1AbCdEfGhIjKlMn0"
    files = client_obj.service.files.return_value
    drives = client_obj.service.drives.return_value
    files.get.return_value.execute.side_effect = FakeHttpError(404, "missing file")
    drives.get.return_value.execute.side_effect = FakeHttpError(404, "missing drive")
    files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "folder-by-name",
                "name": folder_id,
                "mimeType": "application/vnd.google-apps.folder",
            },
        ],
    }

    resolved_id, resolved_name, is_shared_drive = client_obj._resolve_folder_id(folder_id)

    assert resolved_id == "folder-by-name"
    assert resolved_name == folder_id
    assert is_shared_drive is False
    assert files.list.call_args.kwargs["q"] == (
        f"name='{folder_id}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )


def test_resolve_folder_id_like_regular_file_is_rejected(client_obj):
    folder_id = "1AbCdEfGhIjKlMn0"
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": folder_id,
        "name": "notes.txt",
        "mimeType": "text/plain",
    }

    with pytest.raises(UsageError) as ei:
        client_obj._resolve_folder_id(folder_id)

    assert str(ei.value) == f"target is not a Drive folder: {folder_id}"
    client_obj.service.drives.return_value.get.assert_not_called()
    files.list.assert_not_called()


def test_resolve_folder_id_like_auth_error_is_preserved(client_obj):
    folder_id = "1AbCdEfGhIjKlMn0"
    files = client_obj.service.files.return_value
    drives = client_obj.service.drives.return_value
    files.get.return_value.execute.side_effect = FakeHttpError(403, "forbidden")

    with pytest.raises(AuthError):
        client_obj._resolve_folder_id(folder_id)

    drives.get.assert_not_called()


def test_http_401_maps_to_autherror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=401)), op="list files")
    assert isinstance(err, AuthError)


def test_http_404_maps_to_notfounderror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=404)), op="get file")
    assert isinstance(err, NotFoundError)


def test_docs_service_disabled_maps_to_configerror():
    from h2t_ops.connectors.drive.client import _map_http_error

    err = _map_http_error(
        Exception(
            'HttpError 403 ... "reason": "SERVICE_DISABLED" ... docs.googleapis.com ...'
        ),
        op="list document tabs",
    )
    assert isinstance(err, ConfigError)
    assert "docs.googleapis.com" in str(err)


def test_sheets_service_disabled_maps_to_configerror_not_auth():
    from h2t_ops.connectors.drive.client import _map_http_error

    msg = (
        'HttpError 403 when requesting '
        'https://sheets.googleapis.com/v4/spreadsheets/ID/values/A1 returned '
        '"Google Sheets API has not been used in project 645225611930 before or it '
        'is disabled." Details: "[{\'reason\': \'SERVICE_DISABLED\', '
        '\'service\': \'sheets.googleapis.com\'}]"'
    )
    # status=403 present → proves SERVICE_DISABLED is caught before the 403→auth branch.
    err = _map_http_error(FakeHttpError(403, msg), op="update sheet ID range A1")
    # SERVICE_DISABLED is a setup/config problem, NOT auth — must not become AuthError.
    assert isinstance(err, ConfigError)
    assert not isinstance(err, AuthError)
    assert "sheets.googleapis.com" in str(err)
    assert "disabled" in str(err).lower()
    assert "enable" in (getattr(err, "hint", "") or "").lower()


def test_http_500_maps_to_providererror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(SimpleNamespace(resp=SimpleNamespace(status=500)), op="list files")
    assert isinstance(err, ProviderError)


def test_transport_timeout_maps_to_networkerror():
    from h2t_ops.connectors.drive.client import _map_http_error
    err = _map_http_error(TimeoutError("timed out"), op="download file")
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


# ---------------------------------------------------------------------------
# P0 new client method tests
# ---------------------------------------------------------------------------

def test_get_file_returns_metadata(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "report.pdf",
        "mimeType": "application/pdf",
        "trashed": False,
    }
    result = client_obj.get_file("file1")
    assert result["id"] == "file1"
    assert result["name"] == "report.pdf"
    assert files.get.call_args.kwargs["fileId"] == "file1"
    assert files.get.call_args.kwargs["supportsAllDrives"] is True


def test_trash_requires_confirm_name_match(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "actual-name.txt",
        "mimeType": "text/plain",
    }
    with pytest.raises(UsageError) as ei:
        client_obj.trash_file("file1", confirm_name="wrong-name.txt")
    assert "name mismatch" in str(ei.value)
    files.update.assert_not_called()


def test_trash_file_sends_update_trashed_true(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "doc.txt",
        "mimeType": "text/plain",
    }
    files.update.return_value.execute.return_value = {
        "id": "file1",
        "name": "doc.txt",
        "trashed": True,
    }
    result = client_obj.trash_file("file1", confirm_name="doc.txt")
    assert result["trashed"] is True
    assert result["file_id"] == "file1"
    assert files.update.call_args.kwargs["body"] == {"trashed": True}
    assert files.update.call_args.kwargs["supportsAllDrives"] is True


def test_delete_requires_confirm_name_match(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "actual.txt",
        "mimeType": "text/plain",
    }
    with pytest.raises(UsageError) as ei:
        client_obj.delete_file("file1", confirm_name="wrong.txt")
    assert "name mismatch" in str(ei.value)
    files.delete.assert_not_called()


def test_delete_file_calls_files_delete(client_obj):
    files = client_obj.service.files.return_value
    files.get.return_value.execute.return_value = {
        "id": "file1",
        "name": "doc.txt",
        "mimeType": "text/plain",
    }
    files.delete.return_value.execute.return_value = None
    result = client_obj.delete_file("file1", confirm_name="doc.txt")
    assert result["deleted"] is True
    assert result["file_id"] == "file1"
    files.delete.assert_called_once_with(fileId="file1", supportsAllDrives=True)


def test_docs_create_calls_files_create_google_doc(client_obj):
    files = client_obj.service.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "doc1",
        "name": "My Report",
        "mimeType": "application/vnd.google-apps.document",
        "webViewLink": "https://docs.google.com/doc1",
    }
    result = client_obj.create_document("My Report")
    assert result["id"] == "doc1"
    body = files.create.call_args.kwargs["body"]
    assert body["name"] == "My Report"
    assert body["mimeType"] == "application/vnd.google-apps.document"
    assert "parents" not in body


def test_docs_create_with_folder_id_sets_parents(client_obj):
    files = client_obj.service.files.return_value
    files.create.return_value.execute.return_value = {
        "id": "doc2",
        "name": "Nested",
        "mimeType": "application/vnd.google-apps.document",
        "parents": ["folder1"],
    }
    client_obj.create_document("Nested", folder_id="folder1")
    body = files.create.call_args.kwargs["body"]
    assert body["parents"] == ["folder1"]


def test_upload_update_existing_uses_files_update(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    src = tmp_path / "note.md"
    src.write_text("# Hello", encoding="utf-8")
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder1", folder, False))
    monkeypatch.setattr(dmod, "_media_file_upload", lambda: lambda *a, **k: "media")
    files = client_obj.service.files.return_value
    # _find_child_by_name returns existing file
    files.list.return_value.execute.return_value = {
        "files": [{"id": "existing1", "name": "note", "mimeType": "text/plain"}]
    }
    files.update.return_value.execute.return_value = {
        "id": "existing1",
        "name": "note",
        "mimeType": "text/plain",
        "webViewLink": "https://drive/existing1",
    }

    result = client_obj.upload_file(str(src), folder="Target", update_existing=True)
    assert result["file_id"] == "existing1"
    assert result["action"] == "updated"
    assert files.update.call_args.kwargs["fileId"] == "existing1"
    assert not files.create.called


def test_upload_update_existing_rejects_duplicate_matches(client_obj, tmp_path, monkeypatch):
    from h2t_ops.connectors.drive import client as dmod

    src = tmp_path / "note.md"
    src.write_text("# Hello", encoding="utf-8")
    monkeypatch.setattr(client_obj, "_resolve_folder_id", lambda folder: ("folder1", folder, False))
    monkeypatch.setattr(dmod, "_media_file_upload", lambda: lambda *a, **k: "media")
    files = client_obj.service.files.return_value
    # _find_child_by_name sees 2 files = raises UsageError("ambiguous Drive file …")
    files.list.return_value.execute.return_value = {
        "files": [
            {"id": "a1", "name": "note", "mimeType": "text/plain"},
            {"id": "a2", "name": "note", "mimeType": "text/plain"},
        ]
    }

    with pytest.raises(UsageError):
        client_obj.upload_file(str(src), folder="Target", update_existing=True)


def test_docs_tab_write_clear_first_sends_delete_before_insert(client_obj):
    """clear_first=True: deleteContentRange request precedes insertText."""
    client_obj.service.files.return_value.get.return_value.execute.return_value = {
        "id": "doc1",
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    # Simulate existing tab body with content ending at index 50
    client_obj._docs_service.documents.return_value.get.return_value.execute.return_value = {
        "tabs": [
            {
                "tabProperties": {"tabId": "t1"},
                "documentTab": {
                    "body": {
                        "content": [
                            {"endIndex": 50, "paragraph": {"elements": [{"textRun": {"content": "old"}}]}}
                        ]
                    }
                },
            }
        ]
    }
    client_obj._docs_service.documents.return_value.batchUpdate.return_value.execute.return_value = {
        "writeControl": {"requiredRevisionId": "rev1"}
    }

    client_obj.write_document_tab("doc1", "t1", "# New", clear_first=True)

    call_body = client_obj._docs_service.documents.return_value.batchUpdate.call_args.kwargs["body"]
    requests = call_body["requests"]
    assert requests[0].get("deleteContentRange") is not None
    del_range = requests[0]["deleteContentRange"]["range"]
    assert del_range["startIndex"] == 1
    assert del_range["endIndex"] == 49  # end_index - 1 = 50 - 1
    assert del_range["tabId"] == "t1"
    # insertText follows
    assert any("insertText" in r for r in requests[1:])


def test_docs_tab_read_extracts_text(client_obj):
    client_obj.service.files.return_value.get.return_value.execute.return_value = {
        "id": "doc1",
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    client_obj._docs_service.documents.return_value.get.return_value.execute.return_value = {
        "tabs": [
            {
                "tabProperties": {"tabId": "tab1"},
                "documentTab": {
                    "body": {
                        "content": [
                            {
                                "paragraph": {
                                    "elements": [
                                        {"textRun": {"content": "Hello "}},
                                        {"textRun": {"content": "world\n"}},
                                    ]
                                }
                            }
                        ]
                    }
                },
            }
        ]
    }

    result = client_obj.read_tab("doc1", "tab1")
    assert result["kind"] == "google_docs_tab_read/v1"
    assert result["text"] == "Hello world\n"
    assert result["document_id"] == "doc1"
    assert result["tab_id"] == "tab1"


def test_docs_tab_read_tab_not_found_raises(client_obj):
    from h2t_ops.core.errors import NotFoundError
    client_obj.service.files.return_value.get.return_value.execute.return_value = {
        "id": "doc1",
        "name": "Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    client_obj._docs_service.documents.return_value.get.return_value.execute.return_value = {
        "tabs": [{"tabProperties": {"tabId": "other-tab"}, "documentTab": {"body": {"content": []}}}]
    }
    with pytest.raises(NotFoundError):
        client_obj.read_tab("doc1", "missing-tab")


def test_md_to_docs_requests_inline_bold_italic_ranges():
    from h2t_ops.connectors.drive.client import _md_to_docs_requests

    reqs = _md_to_docs_requests("Hello **bold** and *italic* text", "t.abc")
    style_reqs = [r for r in reqs if "updateTextStyle" in r]
    assert len(style_reqs) == 2
    bold_req = next(r for r in style_reqs if r["updateTextStyle"]["textStyle"].get("bold"))
    italic_req = next(r for r in style_reqs if r["updateTextStyle"]["textStyle"].get("italic"))
    # "Hello " = 6 chars, bold starts at index 1+6=7
    assert bold_req["updateTextStyle"]["range"]["startIndex"] == 7
    assert bold_req["updateTextStyle"]["range"]["endIndex"] == 7 + len("bold")
    # After "bold" (4 chars) and " and " (5 chars), italic starts
    # Text inserted: "Hello bold and italic text\n" => "italic" at pos 1+16=17
    italic_start = bold_req["updateTextStyle"]["range"]["endIndex"] + len(" and ")
    assert italic_req["updateTextStyle"]["range"]["startIndex"] == italic_start
