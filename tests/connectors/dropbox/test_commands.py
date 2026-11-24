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


def test_parser_exposes_upload_and_link():
    from h2t_ops.cli import build_parser

    ns = build_parser().parse_args(["dropbox", "upload", "a.py", "/x", "--confirm-write"])
    assert (ns.dropbox_cmd, ns.local, ns.dest, ns.confirm_write) == ("upload", "a.py", "/x", True)
    ns = build_parser().parse_args(["dropbox", "link", "/x/a.py", "--confirm-public"])
    assert (ns.dropbox_cmd, ns.confirm_public) == ("link", True)


@pytest.mark.parametrize("cmd, extra", [
    ("upload", {"local": "a.py", "dest": "/x", "confirm_write": False}),
    ("link", {"path": "/x", "confirm_public": False}),
    ("delete", {"paths": ["/x"], "confirm_delete": False, "dry_run": False}),
    ("delete", {"paths": ["/x"], "confirm_delete": False, "dry_run": True}),
])
def test_writes_are_refused_without_the_flag_before_any_client(monkeypatch, cmd, extra):
    from h2t_ops.core.errors import UsageError

    def no_client():
        pytest.fail("no client may be built without the flag")

    monkeypatch.setattr("h2t_ops.connectors.dropbox.client.DropboxClient", no_client)
    with pytest.raises(UsageError):
        cmds.run(_args(dropbox_cmd=cmd, **extra))


def test_upload_folder_keeps_the_layout_under_dest(fake_client, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.py").write_bytes(b"1")
    (tmp_path / "sub" / "b.txt").write_bytes(b"2")
    fake_client.upload.side_effect = lambda local, dest: {"path": dest, "status": "uploaded"}
    out = cmds.run(_args(dropbox_cmd="upload", local=str(tmp_path), dest="/X/",
                         confirm_write=True))
    assert [r["path"] for r in out] == ["/X/a.py", "/X/sub/b.txt"]


def test_upload_empty_folder_is_an_error(fake_client, tmp_path):
    from h2t_ops.core.errors import UsageError

    with pytest.raises(UsageError):
        cmds.run(_args(dropbox_cmd="upload", local=str(tmp_path), dest="/X",
                       confirm_write=True))


def test_upload_folder_goes_on_after_a_failure_and_then_fails_loud(fake_client, tmp_path):
    from h2t_ops.core.errors import ProviderError

    (tmp_path / "a.py").write_bytes(b"1")
    (tmp_path / "b.py").write_bytes(b"2")

    def up(local, dest):
        if dest.endswith("a.py"):
            raise ProviderError("boom")
        return {"path": dest, "status": "uploaded"}

    fake_client.upload.side_effect = up
    with pytest.raises(ProviderError) as exc:
        cmds.run(_args(dropbox_cmd="upload", local=str(tmp_path), dest="/X",
                       confirm_write=True))
    assert "1 of 2" in str(exc.value)
    assert fake_client.upload.call_count == 2


@pytest.mark.parametrize("kind", ["NetworkError", "AuthError"])
def test_upload_folder_does_not_abort_on_a_network_or_auth_error(fake_client, tmp_path, kind):
    from h2t_ops.core import errors

    (tmp_path / "a.py").write_bytes(b"1")
    (tmp_path / "b.py").write_bytes(b"2")

    def up(local, dest):
        if dest.endswith("a.py"):
            raise getattr(errors, kind)("dropped")
        return {"path": dest, "status": "uploaded"}

    fake_client.upload.side_effect = up
    with pytest.raises(errors.ProviderError) as exc:
        cmds.run(_args(dropbox_cmd="upload", local=str(tmp_path), dest="/X",
                       confirm_write=True))
    assert "1 of 2" in str(exc.value) and "/X/a.py" in str(exc.value)
    assert fake_client.upload.call_count == 2


def test_upload_folder_reports_a_refused_name_as_skipped_not_failed(
        fake_client, tmp_path, capsys):
    (tmp_path / "a.mp4").write_bytes(b"1")
    (tmp_path / "desktop.ini").write_bytes(b"2")

    def up(local, dest):
        if dest.endswith("desktop.ini"):
            return {"path": dest, "bytes": None, "status": "skipped: rejected by Dropbox"}
        return {"path": dest, "bytes": 1, "status": "uploaded"}

    fake_client.upload.side_effect = up
    out = cmds.run(_args(dropbox_cmd="upload", local=str(tmp_path), dest="/X",
                         confirm_write=True))  # no error raised
    assert [r["status"] for r in out] == ["uploaded", "skipped: rejected by Dropbox"]
    err = capsys.readouterr().err
    assert "skipped: rejected by Dropbox: /X/desktop.ini" in err
    assert "[1/2] /X/a.mp4" in err  # progress per file
    assert "1 uploaded, 0 exists, 1 skipped, 0 failed" in err


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


LINK = "https://www.dropbox.com/scl/fo/abc/def?rlkey=k&dl=0"


def test_parser_takes_a_shared_link_on_list_and_meta():
    from h2t_ops.cli import build_parser

    ns = build_parser().parse_args(["dropbox", "list", "--link", LINK, "--recursive"])
    assert (ns.link, ns.path, ns.recursive) == (LINK, "", True)
    ns = build_parser().parse_args(["dropbox", "meta", "--link", LINK])
    assert (ns.link, ns.path) == (LINK, "")
    assert build_parser().parse_args(["dropbox", "list", "/H"]).link is None


def test_list_link_rows_carry_the_path_inside_the_link_and_the_hash(fake_client):
    fake_client.list_link.return_value = [
        {".tag": "file", "name": "v.mp4", "link_path": "/L01/v.mp4", "size": 9,
         "client_modified": "2020-01-01T00:00:00Z", "content_hash": "ab12"},
        {".tag": "folder", "name": "L01", "link_path": "/L01"},
    ]
    rows = cmds.run(_args(dropbox_cmd="list", path="", link=LINK, recursive=True, limit=None))
    assert fake_client.list_link.call_args.args == (LINK, "")
    assert fake_client.list_link.call_args.kwargs == {"recursive": True, "limit": None}
    assert rows[0] == {"kind": "file", "path": "/L01/v.mp4", "name": "v.mp4", "size": 9,
                       "modified": "2020-01-01T00:00:00Z", "content_hash": "ab12"}
    assert rows[1]["kind"] == "folder" and rows[1]["content_hash"] is None
    fake_client.list_folder.assert_not_called()


def test_meta_link_reports_name_kind_and_the_account_path(fake_client):
    fake_client.link_meta.return_value = {".tag": "folder", "name": "Lesson 01",
                                          "path_lower": "/hou2touch/lesson 01"}
    row = cmds.run(_args(dropbox_cmd="meta", path="", link=LINK))
    assert fake_client.link_meta.call_args.args == (LINK, "")
    assert (row["kind"], row["name"], row["path"]) == ("folder", "Lesson 01",
                                                       "/hou2touch/lesson 01")


def test_meta_without_path_or_link_is_a_usage_error(fake_client):
    from h2t_ops.core.errors import UsageError

    with pytest.raises(UsageError):
        cmds.run(_args(dropbox_cmd="meta", path="", link=None))


def test_download_passes_gunzip_through(fake_client):
    fake_client.download.return_value = {"path": "/x", "saved_to": "/tmp/x", "bytes": 3}
    cmds.run(_args(dropbox_cmd="download", path="/x", dest="/tmp/x", gunzip=True))
    assert fake_client.download.call_args.kwargs["gunzip"] is True


def test_download_without_dest_leaves_the_place_to_the_client(fake_client):
    """`download <path>` alone: dest is None, which the client turns into the inbox."""
    from h2t_ops.cli import build_parser

    ns = build_parser().parse_args(["dropbox", "download", "/HOU2TOUCH/clip.wav", "--json"])
    assert ns.dest is None
    fake_client.download.return_value = {"path": "/x", "saved_to": "/i/clip.wav", "bytes": 3}
    cmds.run(ns)
    assert fake_client.download.call_args.args == ("/HOU2TOUCH/clip.wav", None)


# --- delete ------------------------------------------------------------------


def test_parser_exposes_delete_with_several_paths():
    from h2t_ops.cli import build_parser

    ns = build_parser().parse_args(["dropbox", "delete", "/x/a.exe", "/x/b.vst3",
                                    "--confirm-delete", "--dry-run", "--json"])
    assert (ns.dropbox_cmd, ns.paths, ns.confirm_delete, ns.dry_run) == (
        "delete", ["/x/a.exe", "/x/b.vst3"], True, True)
    ns = build_parser().parse_args(["dropbox", "delete", "/x/a.exe"])
    assert (ns.confirm_delete, ns.dry_run) == (False, False)


def _metas(table):
    from h2t_ops.core.errors import NotFoundError

    def meta(path):
        if path not in table:
            raise NotFoundError(f"Not found: files/get_metadata {path}")
        return table[path]
    return meta


_FILE = {".tag": "file", "name": "a.exe", "path_display": "/X/a.exe", "size": 151 << 20}
_FOLDER = {".tag": "folder", "name": "b.vst3", "path_display": "/X/b.vst3"}


def _delete_args(paths, dry_run=False):
    return _args(dropbox_cmd="delete", paths=paths, confirm_delete=True, dry_run=dry_run)


def test_delete_dry_run_reads_metadata_and_deletes_nothing(fake_client, capsys):
    fake_client.meta.side_effect = _metas({"/X/a.exe": _FILE, "/X/b.vst3": _FOLDER})
    fake_client.folder_count.return_value = {"entries": 7, "bytes": 3 << 20, "complete": True}
    out = cmds.run(_delete_args(["/X/a.exe", "/X/b.vst3"], dry_run=True))
    fake_client.delete.assert_not_called()
    assert [(r["path"], r["kind"], r["status"]) for r in out["items"]] == [
        ("/X/a.exe", "file", "would delete"), ("/X/b.vst3", "folder", "would delete")]
    assert out["items"][0]["size"] == 151 << 20
    assert out["items"][1]["entries"] == 7 and out["items"][1]["entries_complete"] is True
    assert "restore" in out["restore"]
    err = capsys.readouterr().err
    assert "/X/a.exe" in err and "7 entries" in err


def test_delete_calls_the_client_for_each_path_and_says_it_can_be_restored(fake_client):
    fake_client.meta.side_effect = _metas({"/X/a.exe": _FILE, "/X/b.vst3": _FOLDER})
    fake_client.folder_count.return_value = {"entries": 2, "bytes": 10, "complete": True}
    fake_client.delete.side_effect = lambda p: {"path": p, "status": "deleted"}
    out = cmds.run(_delete_args(["/X/a.exe", "/X/b.vst3"]))
    assert [c.args for c in fake_client.delete.call_args_list] == [("/X/a.exe",), ("/X/b.vst3",)]
    assert [r["status"] for r in out["items"]] == ["deleted", "deleted"]
    assert "deleted files" in out["restore"]


def test_delete_reports_a_missing_path_goes_on_and_fails(fake_client):
    from h2t_ops.core.errors import H2TError, exit_code_for

    fake_client.meta.side_effect = _metas({"/X/a.exe": _FILE})
    fake_client.delete.side_effect = lambda p: {"path": p, "status": "deleted"}
    with pytest.raises(H2TError) as exc:
        cmds.run(_delete_args(["/X/nope.exe", "/X/a.exe"]))
    assert exit_code_for(exc.value) != 0
    rows = exc.value.details["items"]
    assert [(r["path"], r["status"]) for r in rows] == [("/X/nope.exe", "not found"),
                                                       ("/X/a.exe", "deleted")]
    assert [c.args for c in fake_client.delete.call_args_list] == [("/X/a.exe",)]


def test_delete_dry_run_with_a_missing_path_fails_too(fake_client):
    from h2t_ops.core.errors import H2TError

    fake_client.meta.side_effect = _metas({})
    with pytest.raises(H2TError):
        cmds.run(_delete_args(["/X/nope.exe"], dry_run=True))
    fake_client.delete.assert_not_called()


def test_delete_a_failed_delete_is_reported_and_the_rest_go_on(fake_client):
    from h2t_ops.core.errors import NetworkError, ProviderError

    fake_client.meta.side_effect = _metas({"/X/a.exe": _FILE, "/X/c.exe": _FILE})

    def delete(p):
        if p == "/X/a.exe":
            raise NetworkError("reset")
        return {"path": p, "status": "deleted"}

    fake_client.delete.side_effect = delete
    with pytest.raises(ProviderError) as exc:
        cmds.run(_delete_args(["/X/a.exe", "/X/c.exe"]))
    assert [r["status"] for r in exc.value.details["items"]] == ["failed: reset", "deleted"]


def test_delete_gone_at_delete_time_is_not_a_failure(fake_client):
    """Listed, then gone when delete ran: its parent folder went first, or a resent
    request after a reset had already landed. The path is absent either way."""
    fake_client.meta.side_effect = _metas({"/X/a.exe": _FILE})
    fake_client.delete.return_value = {"path": "/X/a.exe", "status": "gone"}
    out = cmds.run(_delete_args(["/X/a.exe"]))
    assert out["items"][0]["status"].startswith("already gone")


@pytest.mark.parametrize("bad", ["C:/Program Files/Git/X/a.exe", "/", ""])
def test_delete_checks_every_path_before_touching_any(fake_client, bad):
    from h2t_ops.core.errors import UsageError

    with pytest.raises(UsageError):
        cmds.run(_delete_args(["/X/a.exe", bad]))
    fake_client.meta.assert_not_called()
    fake_client.delete.assert_not_called()
