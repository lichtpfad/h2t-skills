"""Tests for upload command validation (--folder vs --parent-id)."""
from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _build_parser():
    from h2t_ops.connectors.drive.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_upload_both_folder_and_parent_id_raises_usage_error(monkeypatch):
    """Both --folder and --parent-id should raise UsageError."""
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="upload",
        file="myfile.txt",
        folder="My Folder",
        parent_id="folder123",
        no_convert=False,
        update_existing=False,
        as_json=False,
        fmt="human",
    )
    with pytest.raises(UsageError, match="exactly one of --folder or --parent-id"):
        cmds_mod.run(args)


def test_upload_neither_folder_nor_parent_id_raises_usage_error(monkeypatch):
    """Neither --folder nor --parent-id should raise UsageError."""
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="upload",
        file="myfile.txt",
        folder=None,
        parent_id=None,
        no_convert=False,
        update_existing=False,
        as_json=False,
        fmt="human",
    )
    with pytest.raises(UsageError, match="exactly one of --folder or --parent-id"):
        cmds_mod.run(args)


def test_upload_with_folder_only_dispatches(monkeypatch):
    """--folder alone should dispatch successfully."""
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    mock_client = MagicMock()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: mock_client)
    args = SimpleNamespace(
        drive_cmd="upload",
        file="myfile.txt",
        folder="My Folder",
        parent_id=None,
        no_convert=False,
        update_existing=False,
        as_json=False,
        fmt="human",
    )
    cmds_mod.run(args)
    mock_client.upload_file.assert_called_once()


def test_upload_with_parent_id_only_dispatches(monkeypatch):
    """--parent-id alone should dispatch successfully."""
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    mock_client = MagicMock()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: mock_client)
    args = SimpleNamespace(
        drive_cmd="upload",
        file="myfile.txt",
        folder=None,
        parent_id="folder123",
        no_convert=False,
        update_existing=False,
        as_json=False,
        fmt="human",
    )
    cmds_mod.run(args)
    mock_client.upload_file.assert_called_once()


def test_upload_subcommand_registered():
    """upload subcommand should be registered."""
    parser = _build_parser()
    args = parser.parse_args(["drive", "upload", "myfile.txt", "--folder", "My Folder"])
    assert args.drive_cmd == "upload"
    assert args.file == "myfile.txt"
    assert args.folder == "My Folder"


def test_upload_without_destination_no_parse_error():
    """Parser should accept upload without --folder or --parent-id (post-parse validation catches it)."""
    parser = _build_parser()
    args = parser.parse_args(["drive", "upload", "myfile.txt"])
    assert args.drive_cmd == "upload"
    assert args.file == "myfile.txt"
    assert args.folder is None
    assert args.parent_id is None
