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
        ("download", ["file1"]),
        ("export", ["file1"]),
        ("upload", ["note.md", "--folder", "Target"]),
        ("upload-folder", ["deploy", "--parent-id", "folder1"]),
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
        ("download", ["file1"]),
        ("upload", ["note.md", "--folder", "Target"]),
        ("upload-folder", ["deploy", "--parent-id", "folder1"]),
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
    for cmd in ("list", "search", "folders", "download", "export", "upload", "upload-folder"):
        with pytest.raises(SystemExit) as sub_ei:
            parser.parse_args(["drive", cmd, "--help"])
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


def test_upload_returns_envelope_with_web_view_link(monkeypatch, capsys):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.output import emit

    class _Stub:
        def upload_file(self, file, folder, no_convert=False):
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


def test_upload_without_folder_raises_usageerror():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "upload", "note.md"])


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
