"""CLI surface for the dropbox connector (#469)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.connectors.dropbox import commands as cmds


def _args(**kw):
    base = {"as_json": True, "fmt": "human"}
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def fake_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "h2t_ops.connectors.dropbox.client.DropboxClient", lambda: client
    )
    return client


def test_connector_is_discoverable_and_reaches_the_cli():
    from h2t_ops.cli import _MIGRATED
    from h2t_ops.core.registry import discover

    assert "dropbox" in {spec.name for spec in discover()}
    assert "dropbox" in _MIGRATED


def test_parser_exposes_the_four_verbs():
    from h2t_ops.cli import build_parser

    ns = build_parser().parse_args(["dropbox", "list", "/HOU2TOUCH", "--recursive", "--json"])
    assert (ns.dropbox_cmd, ns.path, ns.recursive) == ("list", "/HOU2TOUCH", True)
    for verb, extra in (("account", []), ("meta", ["/x"]), ("download", ["/x", "/tmp/y"])):
        assert build_parser().parse_args(["dropbox", verb, *extra]).dropbox_cmd == verb


def test_list_path_defaults_to_the_root():
    from h2t_ops.cli import build_parser

    assert build_parser().parse_args(["dropbox", "list"]).path == ""


def test_account_reports_both_namespaces_and_what_was_applied(fake_client):
    fake_client.account.return_value = {
        "account_id": "dbid:1", "email": "x@example.com",
        "team": {"name": "LichtPfad"},
        "root_info": {"root_namespace_id": "9001", "home_namespace_id": "42"},
    }
    fake_client.path_root.return_value = "9001"
    out = cmds.run(_args(dropbox_cmd="account"))
    assert out["root_namespace_id"] == "9001"
    assert out["home_namespace_id"] == "42"
    assert out["path_root_applied"] == "9001"
    assert out["team"] == "LichtPfad"


def test_list_rows_are_normalized(fake_client):
    fake_client.list_folder.return_value = [
        {".tag": "file", "name": "a.wav", "path_display": "/H/a.wav", "size": 12,
         "client_modified": "2026-09-01T00:00:00Z"},
        {".tag": "folder", "name": "sub", "path_display": "/H/sub"},
    ]
    rows = cmds.run(_args(dropbox_cmd="list", path="/H", recursive=False, limit=None))
    assert rows[0] == {"kind": "file", "path": "/H/a.wav", "name": "a.wav",
                       "size": 12, "modified": "2026-09-01T00:00:00Z"}
    assert rows[1]["kind"] == "folder" and rows[1]["size"] is None


def test_download_passes_gunzip_through(fake_client):
    fake_client.download.return_value = {"path": "/x", "saved_to": "/tmp/x", "bytes": 3}
    cmds.run(_args(dropbox_cmd="download", path="/x", dest="/tmp/x", gunzip=True))
    assert fake_client.download.call_args.kwargs["gunzip"] is True
