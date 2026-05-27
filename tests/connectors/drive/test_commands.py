"""Tests for h2t_ops.connectors.drive.commands — registration and dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import UsageError


def _build_parser():
    from h2t_ops.connectors.drive.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_register_creates_subparsers_for_drive_verbs():
    parser = _build_parser()
    cases = [
        ("list", []),
        ("search", ["query"]),
        ("folders", []),
        ("create-folder", ["New Folder"]),
        ("docs-tab", ["list", "doc1"]),
        ("download", ["file1"]),
        ("export", ["file1"]),
        ("upload", ["note.md", "--folder", "Target"]),
        ("upload-folder", ["deploy", "--parent-id", "folder1"]),
        ("rename", ["file1", "renamed.txt"]),
        ("copy", ["file1"]),
        ("move", ["file1", "--to", "folder1"]),
    ]
    for cmd, extra in cases:
        ns = parser.parse_args(["drive", cmd, *extra])
        assert ns.drive_cmd == cmd


def test_each_verb_supports_json_and_format_flags():
    parser = _build_parser()
    non_export = [
        ("list", []),
        ("search", ["query"]),
        ("folders", []),
        ("create-folder", ["New Folder"]),
        ("docs-tab", ["list", "doc1"]),
        ("download", ["file1"]),
        ("upload", ["note.md", "--folder", "Target"]),
        ("upload-folder", ["deploy", "--parent-id", "folder1"]),
        ("rename", ["file1", "renamed.txt"]),
        ("copy", ["file1"]),
        ("move", ["file1", "--to", "folder1"]),
    ]
    for cmd, extra in non_export:
        ns = parser.parse_args(["drive", cmd, *extra, "--json"])
        assert ns.as_json is True
        ns_md = parser.parse_args(["drive", cmd, *extra, "--format", "md"])
        assert ns_md.fmt == "md"
        ns_human = parser.parse_args(["drive", cmd, *extra, "--format", "human"])
        assert ns_human.fmt == "human"

    ns = parser.parse_args(["drive", "export", "file1", "--json"])
    assert ns.as_json is True
    ns_exp = parser.parse_args(["drive", "export", "file1", "--format", "text"])
    assert ns_exp.export_format == "text"
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "list", "--format", "json"])


def test_help_exits_zero():
    parser = _build_parser()
    with pytest.raises(SystemExit) as ei:
        parser.parse_args(["drive", "--help"])
    assert ei.value.code == 0
    for cmd in (
        "list",
        "search",
        "folders",
        "create-folder",
        "docs-tab",
        "download",
        "export",
        "upload",
        "upload-folder",
        "rename",
        "copy",
        "move",
    ):
        with pytest.raises(SystemExit) as sub_ei:
            argv = ["drive", cmd, "--help"]
            if cmd == "search":
                argv = ["drive", cmd, "query", "--help"]
            elif cmd == "create-folder":
                argv = ["drive", cmd, "New Folder", "--help"]
            elif cmd == "docs-tab":
                argv = ["drive", cmd, "list", "doc1", "--help"]
            elif cmd == "download":
                argv = ["drive", cmd, "file1", "--help"]
            elif cmd == "export":
                argv = ["drive", cmd, "file1", "--help"]
            elif cmd == "upload":
                argv = ["drive", cmd, "note.md", "--folder", "Target", "--help"]
            elif cmd == "upload-folder":
                argv = ["drive", cmd, "deploy", "--parent-id", "folder1", "--help"]
            elif cmd == "rename":
                argv = ["drive", cmd, "file1", "renamed.txt", "--help"]
            elif cmd == "copy":
                argv = ["drive", cmd, "file1", "--help"]
            elif cmd == "move":
                argv = ["drive", cmd, "file1", "--to", "folder1", "--help"]
            parser.parse_args(argv)
        assert sub_ei.value.code == 0


def test_list_returns_envelope_rows(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def list_files(self, folder=None, max_results=None):
            return [{"id": "1", "name": "A"}]

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="list", folder=None, max=None, as_json=True, fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert out["result"]["rows"][0]["id"] == "1"
    assert out["result"]["count"] == 1


def test_download_returns_envelope_with_saved_path(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def download_file(self, file_id, dest=None):
            return {"saved_path": "out.txt", "file_id": file_id, "name": "out.txt",
                    "mimeType": "text/plain"}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="download", file_id="file1", dest=None, as_json=True, fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["saved_path"] == "out.txt"
    assert "size" not in out["result"]


def test_create_folder_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def create_folder(self, name, *, parent=None):
            return {
                "file_id": "folder1",
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": ["root"] if parent is None else ["parent1"],
                "web_view_link": "https://drive/folder1",
                "parent_name": parent or "root",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="create-folder", name="Projects", parent=None, as_json=True, fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["file_id"] == "folder1"
    assert out["result"]["parent_name"] == "root"


def test_rename_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def rename_file(self, file_id, new_name):
            return {
                "file_id": file_id,
                "name": new_name,
                "mimeType": "text/plain",
                "web_view_link": "https://drive/file1",
                "modifiedTime": "2026-05-25T18:00:00Z",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="rename",
        file_id="file1",
        new_name="renamed.txt",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["name"] == "renamed.txt"


def test_copy_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def copy_file(self, file_id, *, new_name=None, folder=None):
            return {
                "file_id": "copy1",
                "source_file_id": file_id,
                "name": new_name or "Copy of file",
                "parents": [folder] if folder else [],
                "mimeType": "text/plain",
                "web_view_link": "https://drive/copy1",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="copy",
        file_id="file1",
        new_name="copy.txt",
        folder="folder1",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["file_id"] == "copy1"
    assert out["result"]["parents"] == ["folder1"]


def test_move_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def move_file(self, file_id, *, destination_folder_id):
            return {
                "file_id": file_id,
                "name": "report.txt",
                "parents": [destination_folder_id],
                "mimeType": "text/plain",
                "web_view_link": "https://drive/file1",
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="move",
        file_id="file1",
        destination_folder_id="folder1",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["parents"] == ["folder1"]


def test_docs_tab_list_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def list_document_tabs(self, document_id):
            return {
                "kind": "google_docs_tabs/v1",
                "document_id": document_id,
                "title": "Doc",
                "tabs": [{"tab_id": "tab1", "title": "Intro"}],
                "count": 1,
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="docs-tab",
        docs_tab_cmd="list",
        document_id="doc1",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["document_id"] == "doc1"
    assert out["result"]["count"] == 1


def test_upload_returns_envelope_with_web_view_link(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def upload_file(self, file, folder, no_convert=False, *, update_existing=False, parent_id=None):
            return {"file_id": "new1", "name": "note", "mimeType": "text/plain",
                    "web_view_link": "https://drive/new1", "folder_name": folder}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="upload", file="note.md", folder="Target", no_convert=False,
        as_json=True, fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["web_view_link"] == "https://drive/new1"


def test_upload_folder_returns_manifest(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def upload_folder(self, local_dir, *, parent_id, dry_run=False, update_existing=False):
            return {
                "local_dir": local_dir,
                "parent_id": parent_id,
                "dry_run": dry_run,
                "update_existing": update_existing,
                "entries": [
                    {"kind": "file", "action": "file_upload", "relative_path": "index.html"},
                ],
                "summary": {"file_upload": 1, "total": 1},
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="upload-folder",
        local_dir="deploy",
        parent_id="folder1",
        dry_run=True,
        update_existing=True,
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["parent_id"] == "folder1"
    assert out["result"]["dry_run"] is True
    assert out["result"]["update_existing"] is True
    assert out["result"]["summary"]["total"] == 1


def test_upload_without_folder_no_parse_error():
    """Parser should accept upload without --folder (validation in run())."""
    parser = _build_parser()
    args = parser.parse_args(["drive", "upload", "note.md"])
    assert args.drive_cmd == "upload"
    assert args.file == "note.md"
    assert args.folder is None
    assert args.parent_id is None


@pytest.mark.parametrize("fmt", ("docx", "xlsx", "pdf", "pptx"))
def test_export_print_with_binary_format_raises_usageerror(monkeypatch, fmt):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    class _Stub:
        called = False

        def export_file(self, *a, **k):
            self.called = True
            return {}

    stub = _Stub()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: stub)
    args = SimpleNamespace(
        drive_cmd="export", file_id="file1", dest=None, export_format=fmt,
        print_stdout=True, as_json=False,
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)
    assert stub.called is False


@pytest.mark.parametrize("fmt", ("text", "csv", "md"))
def test_export_print_allows_text_formats(monkeypatch, fmt):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    calls = {}

    class _Stub:
        def export_file(self, file_id, fmt=None, dest=None, to_stdout=False):
            calls["args"] = (file_id, fmt, dest, to_stdout)
            return {"text": "hello", "format": fmt}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="export", file_id="file1", dest=None, export_format=fmt,
        print_stdout=True, as_json=False,
    )
    assert cmds_mod.run(args) == "hello"
    assert calls["args"] == ("file1", fmt, None, True)


def test_client_imported_lazily_inside_run():
    src = Path("h2t_ops/connectors/drive/commands.py").read_text(encoding="utf-8")
    top_level = [ln for ln in src.splitlines() if ln and not ln.startswith((" ", "\t"))]
    assert not any("h2t_ops.connectors.drive.client" in ln for ln in top_level)


def test_docs_tab_add_returns_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def add_document_tab(self, document_id, title):
            return {
                "kind": "google_docs_tab/v1",
                "document_id": document_id,
                "tab_id": "new-tab",
                "title": title,
                "index": 1,
                "nesting_level": 0,
            }

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(
        drive_cmd="docs-tab",
        docs_tab_cmd="add",
        document_id="doc1",
        title="Methods",
        as_json=True,
        fmt="human",
    )
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["tab_id"] == "new-tab"
    assert out["result"]["title"] == "Methods"


def test_drive_p0_parser_surface():
    parser = _build_parser()
    assert parser.parse_args(["drive", "get-file", "file1"]).drive_cmd == "get-file"
    assert parser.parse_args(["drive", "trash", "file1", "--confirm-name", "A"]).drive_cmd == "trash"
    assert parser.parse_args(["drive", "delete", "file1", "--confirm-name", "A", "--confirm-permanent"]).drive_cmd == "delete"
    assert parser.parse_args(["drive", "docs", "create", "Title"]).drive_cmd == "docs"
    assert parser.parse_args(["drive", "docs-tab", "read", "doc1", "tab1"]).docs_tab_cmd == "read"
    ns = parser.parse_args(["drive", "docs-tab", "write", "doc1", "tab1", "--content-file", "x.md", "--clear-first"])
    assert ns.clear_first is True
    ns2 = parser.parse_args(["drive", "upload", "note.md", "--folder", "Folder", "--update-existing"])
    assert ns2.update_existing is True


# ---------------------------------------------------------------------------
# P0 dispatch tests
# ---------------------------------------------------------------------------

def test_get_file_dispatch_returns_metadata(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def get_file(self, file_id):
            return {"id": file_id, "name": "doc.txt", "mimeType": "text/plain",
                    "trashed": False}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="get-file", file_id="file1", as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["id"] == "file1"


def test_trash_dispatch_calls_trash_file(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def trash_file(self, file_id, *, confirm_name):
            return {"file_id": file_id, "name": confirm_name, "trashed": True, "previous": {}}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="trash", file_id="file1", confirm_name="doc.txt",
                           as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["trashed"] is True


def test_delete_requires_confirm_permanent_flag(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    class _Stub:
        called = False
        def delete_file(self, *a, **k):
            self.called = True
            return {}

    stub = _Stub()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: stub)
    args = SimpleNamespace(drive_cmd="delete", file_id="file1", confirm_name="doc.txt",
                           confirm_permanent=False, as_json=True, fmt="human")
    with pytest.raises(UsageError):
        cmds_mod.run(args)
    assert stub.called is False


def test_delete_dispatch_calls_delete_file(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def delete_file(self, file_id, *, confirm_name):
            return {"file_id": file_id, "name": confirm_name, "deleted": True}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="delete", file_id="file1", confirm_name="doc.txt",
                           confirm_permanent=True, as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["deleted"] is True


def test_docs_create_dispatch(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def create_document(self, title, *, folder_id=None):
            return {"id": "doc1", "name": title, "mimeType": "application/vnd.google-apps.document",
                    "webViewLink": "https://docs.google.com/doc1"}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="docs", docs_cmd="create", title="My Doc",
                           folder_id=None, as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["name"] == "My Doc"


def test_docs_tab_read_dispatch(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def read_tab(self, document_id, tab_id):
            return {"kind": "google_docs_tab_read/v1", "document_id": document_id,
                    "tab_id": tab_id, "text": "Hello world\n"}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="docs-tab", docs_tab_cmd="read",
                           document_id="doc1", tab_id="tab1", as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["result"]["text"] == "Hello world\n"


def test_docs_tab_write_clear_first_dispatch(monkeypatch, tmp_path, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    calls = {}

    class _Stub:
        def write_document_tab(self, document_id, tab_id, content, *, clear_first=False):
            calls["clear_first"] = clear_first
            return {"kind": "google_docs_tab_write/v1", "document_id": document_id,
                    "tab_id": tab_id, "requests_sent": 2}

    content_file = tmp_path / "content.md"
    content_file.write_text("# Hello", encoding="utf-8")

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="docs-tab", docs_tab_cmd="write",
                           document_id="doc1", tab_id="tab1",
                           content_file=str(content_file), clear_first=True,
                           as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert calls["clear_first"] is True


def test_upload_update_existing_dispatch(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    calls = {}

    class _Stub:
        def upload_file(self, file, folder, no_convert=False, *, update_existing=False, parent_id=None):
            calls["update_existing"] = update_existing
            return {"file_id": "new1", "name": "note", "mimeType": "text/plain",
                    "web_view_link": "https://drive/new1", "folder_name": folder, "action": "updated"}

    monkeypatch.setattr(client_mod, "DriveClient", lambda: _Stub())
    args = SimpleNamespace(drive_cmd="upload", file="note.md", folder="Target",
                           no_convert=False, update_existing=True, parent_id=None,
                           as_json=True, fmt="human")
    rc = emit("drive", result=cmds_mod.run(args), fmt="json")
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert calls["update_existing"] is True
