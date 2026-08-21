"""Views API — sorts, filters and column layout, unreachable before #372.

Notion shipped the Views API in `2025-09-03`. The rest of this client speaks
`2022-06-28`, where the data-source model differs, so the newer version is sent
per-request for views only rather than by bumping the whole connector.
"""

import json
from types import SimpleNamespace

import pytest

from h2t_ops.connectors.notion import client as client_mod
from h2t_ops.connectors.notion import commands as cmds_mod
from h2t_ops.core.errors import UsageError

VIEWS_VERSION = "2025-09-03"


@pytest.fixture
def client_obj():
    """A NotionClient without __init__ — no token resolution, no SDK."""
    from h2t_ops.connectors.notion.client import NotionClient
    c = object.__new__(NotionClient)
    c.token = "ntn_test"
    return c


def _record(client_obj, responses):
    """Stub _http_request, returning queued responses and recording calls."""
    calls = []
    queue = list(responses)

    def _stub(method, url, headers, json_body=None):
        calls.append({"method": method, "url": url, "headers": headers, "body": json_body})
        return queue.pop(0)

    client_obj._http_request = _stub
    return calls


# --- client ------------------------------------------------------------------

def test_list_views_sends_the_views_api_version(client_obj):
    calls = _record(client_obj, [{"results": [{"id": "v1"}], "has_more": False}])
    client_obj.list_views(data_source_id="ds-1")
    assert calls[0]["headers"]["Notion-Version"] == VIEWS_VERSION


def test_other_commands_keep_the_old_api_version(client_obj):
    """The version bump must not leak into the rest of the connector."""
    import inspect
    from h2t_ops.connectors.notion.client import NotionClient
    src = inspect.getsource(NotionClient.query_database_page)
    assert "2022-06-28" in src


def test_list_views_accepts_a_database_id(client_obj):
    calls = _record(client_obj, [{"results": [], "has_more": False}])
    client_obj.list_views(database_id="db-1")
    assert "database_id=db-1" in calls[0]["url"]


def test_list_views_accepts_a_data_source_id(client_obj):
    calls = _record(client_obj, [{"results": [], "has_more": False}])
    client_obj.list_views(data_source_id="ds-1")
    assert "data_source_id=ds-1" in calls[0]["url"]


def test_list_views_requires_exactly_one_parent(client_obj):
    with pytest.raises(UsageError):
        client_obj.list_views()
    with pytest.raises(UsageError):
        client_obj.list_views(database_id="db-1", data_source_id="ds-1")


def test_list_views_reports_truncation_from_has_more(client_obj):
    _record(client_obj, [{"results": [{"id": "v1"}], "has_more": True,
                          "next_cursor": "c1"}])
    page = client_obj.list_views(data_source_id="ds-1", limit=1)
    assert page == {"items": [{"id": "v1"}], "truncated": True}


def test_list_views_follows_the_cursor_until_exhausted(client_obj):
    calls = _record(client_obj, [
        {"results": [{"id": "v1"}], "has_more": True, "next_cursor": "c1"},
        {"results": [{"id": "v2"}], "has_more": False},
    ])
    page = client_obj.list_views(data_source_id="ds-1")
    assert [v["id"] for v in page["items"]] == ["v1", "v2"]
    assert page["truncated"] is False
    assert "start_cursor=c1" in calls[1]["url"]


def test_get_view_reads_one_view(client_obj):
    calls = _record(client_obj, [{"id": "v1", "name": "Untitled", "type": "table"}])
    assert client_obj.get_view("v1")["name"] == "Untitled"
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"].endswith("/views/v1")


def test_patch_view_sends_the_spec_verbatim(client_obj):
    spec = {"sorts": [{"property": "Position", "direction": "ascending"}]}
    calls = _record(client_obj, [{"id": "v1"}])
    client_obj.patch_view("v1", spec)
    assert calls[0]["method"] == "PATCH"
    assert calls[0]["body"] == spec


def test_create_view_fills_the_parent_only_when_the_spec_omits_it(client_obj):
    calls = _record(client_obj, [{"id": "v2"}, {"id": "v3"}])
    client_obj.create_view({"name": "Board"}, data_source_id="ds-1")
    assert calls[0]["body"]["parent"] == {"type": "data_source_id", "data_source_id": "ds-1"}

    own = {"name": "Board", "parent": {"type": "data_source_id", "data_source_id": "ds-9"}}
    client_obj.create_view(own, data_source_id="ds-1")
    assert calls[1]["body"]["parent"]["data_source_id"] == "ds-9"


def test_delete_view_aborts_when_the_name_does_not_match(client_obj):
    """Mirrors archive_page: a destructive call names its target first."""
    _record(client_obj, [{"id": "v1", "name": "Untitled"}])
    with pytest.raises(UsageError) as e:
        client_obj.delete_view("v1", confirm_name="Board")
    assert "Untitled" in str(e.value)


def test_delete_view_deletes_when_the_name_matches(client_obj):
    calls = _record(client_obj, [{"id": "v1", "name": "Board"}, {}])
    client_obj.delete_view("v1", confirm_name="Board")
    assert calls[1]["method"] == "DELETE"
    assert calls[1]["url"].endswith("/views/v1")


# --- commands ----------------------------------------------------------------

def _parser():
    import argparse
    p = argparse.ArgumentParser(prog="h2t-ops")
    sub = p.add_subparsers(dest="connector")
    cmds_mod.register(sub)
    return p


def test_parser_accepts_the_views_subcommands():
    for argv in (["notion", "views", "list", "--data-source-id", "ds"],
                 ["notion", "views", "get", "V"],
                 ["notion", "views", "patch", "V", "--spec-file", "s.json"],
                 ["notion", "views", "create", "--data-source-id", "ds", "--spec-file", "s.json"],
                 ["notion", "views", "delete", "V", "--confirm-name", "Board"]):
        ns = _parser().parse_args(argv)
        assert ns.notion_cmd == "views" and ns.views_cmd == argv[2]


def test_views_list_returns_an_envelope(monkeypatch):
    """A view list is a list: it must carry truncation like every other one."""
    class _Stub:
        def list_views(self, *, database_id=None, data_source_id=None, limit=None):
            assert (data_source_id, limit) == ("ds-1", 25)
            return {"items": [{"id": "v1"}], "truncated": True}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    args = SimpleNamespace(notion_cmd="views", views_cmd="list", database_id=None,
                           data_source_id="ds-1", limit=25, as_json=True, fmt="human")
    out = cmds_mod.run(args)
    assert out.items == [{"id": "v1"}]
    assert out.meta() == {"count": 1, "truncated": True, "limit": 25}


def test_views_patch_reads_the_spec_file(monkeypatch, tmp_path):
    spec = {"sorts": [{"property": "Position", "direction": "ascending"}]}
    f = tmp_path / "spec.json"
    f.write_text(json.dumps(spec), encoding="utf-8")

    seen = {}

    class _Stub:
        def patch_view(self, view_id, spec_dict):
            seen.update(view_id=view_id, spec=spec_dict)
            return {"id": view_id}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    args = SimpleNamespace(notion_cmd="views", views_cmd="patch", view_id="v1",
                           spec_file=str(f), as_json=True, fmt="human")
    cmds_mod.run(args)
    assert seen == {"view_id": "v1", "spec": spec}


def test_views_patch_rejects_a_missing_spec_file(monkeypatch):
    class _Stub:
        def patch_view(self, view_id, spec_dict):  # pragma: no cover
            raise AssertionError("must not reach the provider with an unreadable spec")

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    args = SimpleNamespace(notion_cmd="views", views_cmd="patch", view_id="v1",
                           spec_file="/nope/spec.json", as_json=True, fmt="human")
    with pytest.raises(UsageError):
        cmds_mod.run(args)
