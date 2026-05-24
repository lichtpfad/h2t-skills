"""Tests for DriveClient.share_file() — spec #168."""
from __future__ import annotations

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
