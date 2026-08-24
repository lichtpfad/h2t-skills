"""Tests for DriveClient.share_file() — spec #168."""
from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sc():
    """DriveClient with mocked service — no network."""
    from h2t_ops.connectors.drive.client import DriveClient
    c = object.__new__(DriveClient)
    c.service = MagicMock()
    return c


def _setup_create(sc, perm_id="perm1", link="https://docs.google.com/file"):
    sc.service.permissions.return_value.create.return_value.execute.return_value = {"id": perm_id}
    sc.service.files.return_value.get.return_value.execute.return_value = {"webViewLink": link}


def _setup_get_link(sc, permissions, link="https://docs.google.com/file"):
    sc.service.files.return_value.get.return_value.execute.return_value = {"webViewLink": link}
    sc.service.permissions.return_value.list.return_value.execute.return_value = {
        "permissions": permissions
    }


# --- --email mode ---

def test_email_calls_permissions_create_type_user(sc):
    _setup_create(sc)
    sc.share_file("fid1", email="user@example.com")
    call = sc.service.permissions.return_value.create.call_args
    assert call.kwargs["body"]["type"] == "user"
    assert call.kwargs["body"]["emailAddress"] == "user@example.com"
    assert call.kwargs["sendNotificationEmail"] is False


def test_email_result_granted_to(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="alice@example.com")
    assert result["granted_to"] == "alice@example.com"


def test_email_default_role_reader(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="user@example.com")
    call = sc.service.permissions.return_value.create.call_args
    assert call.kwargs["body"]["role"] == "reader"
    assert result["role"] == "reader"


def test_email_role_writer_passed_to_api_and_result(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="user@example.com", role="writer")
    call = sc.service.permissions.return_value.create.call_args
    assert call.kwargs["body"]["role"] == "writer"
    assert result["role"] == "writer"


def test_email_result_kind_and_type(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", email="user@example.com")
    assert result["kind"] == "drive_share/v1"
    assert result["type"] == "user"
    assert "permission_id" in result


# --- --anyone mode ---

def test_anyone_calls_permissions_create_no_email_key(sc):
    _setup_create(sc)
    sc.share_file("fid1", anyone=True)
    call = sc.service.permissions.return_value.create.call_args
    body = call.kwargs["body"]
    assert body["type"] == "anyone"
    assert "emailAddress" not in body


def test_anyone_result_granted_to_anyone(sc):
    _setup_create(sc)
    result = sc.share_file("fid1", anyone=True)
    assert result["granted_to"] == "anyone"
    assert result["type"] == "anyone"


# --- --get-link mode ---

def test_get_link_never_calls_permissions_create(sc):
    _setup_get_link(sc, permissions=[])
    sc.share_file("fid1", get_link=True)
    sc.service.permissions.return_value.create.assert_not_called()


def test_get_link_has_anyone_permission_true(sc):
    _setup_get_link(sc, permissions=[{"type": "anyone", "role": "reader"}])
    result = sc.share_file("fid1", get_link=True)
    assert result["has_anyone_permission"] is True


def test_get_link_has_anyone_permission_false(sc):
    _setup_get_link(sc, permissions=[{"type": "user", "role": "writer"}])
    result = sc.share_file("fid1", get_link=True)
    assert result["has_anyone_permission"] is False


def test_get_link_excludes_granted_to_and_permission_id(sc):
    _setup_get_link(sc, permissions=[])
    result = sc.share_file("fid1", get_link=True)
    assert "granted_to" not in result
    assert "permission_id" not in result
    assert result["type"] == "get-link"
    assert result["kind"] == "drive_share/v1"


# --- command: parser registration ---


def _build_parser():
    from h2t_ops.connectors.drive.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_share_subcommand_registered():
    parser = _build_parser()
    args = parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com"])
    assert args.drive_cmd == "share"
    assert args.email == "u@e.com"


def test_no_mode_flag_exits_nonzero():
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["drive", "share", "fid1"])
    assert exc.value.code == 2


def test_email_and_anyone_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com", "--anyone"])


def test_email_and_get_link_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--email", "u@e.com", "--get-link"])


def test_anyone_and_get_link_mutually_exclusive():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--anyone", "--get-link"])


# --- command: dispatch post-parse checks ---

def test_get_link_with_role_raises_usage_error(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=False, get_link=True, revoke_anyone=False,
        role="writer", confirm_public=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError, match="--role cannot be used with --get-link"):
        cmds_mod.run(args)


def test_anyone_without_confirm_public_raises_usage_error(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=True, get_link=False, revoke_anyone=False,
        role="reader", confirm_public=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError, match="--confirm-public"):
        cmds_mod.run(args)


def test_share_email_dispatches_to_share_file(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    mock_client = MagicMock()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: mock_client)
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email="a@b.com", anyone=False, get_link=False, revoke_anyone=False,
        role="writer", confirm_public=False,
        as_json=False, fmt="human",
    )
    cmds_mod.run(args)
    mock_client.share_file.assert_called_once_with(
        "fid1", email="a@b.com", role="writer", anyone=False, get_link=False,
        revoke_anyone=False,
    )


# --- --revoke-anyone mode (#386, defect 2) ---
#
# `--anyone` was a one-way door: the connector could open link access and had no
# way to close it, so the documented MeetGeek upload flow left every recording
# world-readable — 26 of them, for 108 days.

def _setup_revoke(sc, permissions):
    sc.service.permissions.return_value.list.return_value.execute.return_value = {
        "permissions": permissions
    }


def test_revoke_anyone_deletes_only_the_anyone_permission(sc):
    _setup_revoke(sc, [
        {"id": "P1", "type": "anyone", "role": "reader"},
        {"id": "P2", "type": "user", "role": "owner"},
    ])
    result = sc.share_file("fid1", revoke_anyone=True)
    delete = sc.service.permissions.return_value.delete
    assert delete.call_count == 1
    assert delete.call_args.kwargs["permissionId"] == "P1"
    assert result["revoked"] == 1
    assert result["has_anyone_permission"] is False


def test_revoke_anyone_is_a_no_op_on_a_private_file(sc):
    _setup_revoke(sc, [{"id": "P2", "type": "user", "role": "owner"}])
    result = sc.share_file("fid1", revoke_anyone=True)
    sc.service.permissions.return_value.delete.assert_not_called()
    assert result["revoked"] == 0


def test_revoke_anyone_removes_every_anyone_grant(sc):
    """Drive can carry more than one; leaving the second is leaving it public."""
    _setup_revoke(sc, [
        {"id": "P1", "type": "anyone", "role": "reader"},
        {"id": "P3", "type": "anyone", "role": "writer"},
    ])
    result = sc.share_file("fid1", revoke_anyone=True)
    assert result["revoked"] == 2
    deleted = [c.kwargs["permissionId"]
               for c in sc.service.permissions.return_value.delete.call_args_list]
    assert deleted == ["P1", "P3"]


def test_revoke_anyone_never_creates_a_permission(sc):
    _setup_revoke(sc, [{"id": "P1", "type": "anyone", "role": "reader"}])
    sc.share_file("fid1", revoke_anyone=True)
    sc.service.permissions.return_value.create.assert_not_called()


def test_revoke_anyone_result_shape(sc):
    _setup_revoke(sc, [])
    result = sc.share_file("fid1", revoke_anyone=True)
    assert result["kind"] == "drive_share/v1"
    assert result["type"] == "revoke-anyone"
    assert "granted_to" not in result
    assert "permission_id" not in result


def test_revoke_anyone_registered_and_exclusive():
    parser = _build_parser()
    args = parser.parse_args(["drive", "share", "fid1", "--revoke-anyone"])
    assert args.revoke_anyone is True
    with pytest.raises(SystemExit):
        parser.parse_args(["drive", "share", "fid1", "--anyone", "--revoke-anyone"])


def test_revoke_anyone_needs_no_confirm_public():
    """Closing an exposure is not the risky direction; only opening one is."""
    parser = _build_parser()
    args = parser.parse_args(["drive", "share", "fid1", "--revoke-anyone"])
    assert args.confirm_public is False


def test_revoke_anyone_with_role_raises_usage_error(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod
    from h2t_ops.core.errors import UsageError

    monkeypatch.setattr(client_mod, "DriveClient", lambda: MagicMock())
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=False, get_link=False, revoke_anyone=True,
        role="writer", confirm_public=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError, match="--role cannot be used with --revoke-anyone"):
        cmds_mod.run(args)


def test_share_revoke_anyone_dispatches_to_share_file(monkeypatch):
    import h2t_ops.connectors.drive.client as client_mod
    from h2t_ops.connectors.drive import commands as cmds_mod

    mock_client = MagicMock()
    monkeypatch.setattr(client_mod, "DriveClient", lambda: mock_client)
    args = SimpleNamespace(
        drive_cmd="share", file_id="fid1",
        email=None, anyone=False, get_link=False, revoke_anyone=True,
        role="reader", confirm_public=False,
        as_json=False, fmt="human",
    )
    cmds_mod.run(args)
    mock_client.share_file.assert_called_once_with(
        "fid1", email=None, role="reader", anyone=False, get_link=False,
        revoke_anyone=True,
    )
