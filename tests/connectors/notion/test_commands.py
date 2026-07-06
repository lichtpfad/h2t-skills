import argparse
import json
import sys
import builtins
from h2t_ops.connectors.notion.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t-ops")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_notion_subcommands():
    ns = _parser().parse_args(["notion", "get", "PAGEID"])
    assert ns.connector == "notion" and ns.notion_cmd == "get" and ns.page_id == "PAGEID"


def test_notion_p0_parser_surface():
    p = _parser()
    assert p.parse_args(["notion", "create-db-item", "db1", "--title", "Task"]).notion_cmd == "create-db-item"
    assert p.parse_args(["notion", "update-db-item", "page1", "--property-json", '{"Status":{"select":{"name":"Done"}}}']).notion_cmd == "update-db-item"
    assert p.parse_args(["notion", "archive", "page1", "--confirm-title", "Task"]).notion_cmd == "archive"
    assert p.parse_args(["notion", "append-blocks", "page1", "--content-file", "x.md"]).notion_cmd == "append-blocks"
    assert p.parse_args(["notion", "replace-content", "page1", "--content-file", "x.md", "--confirm-title", "Task"]).notion_cmd == "replace-content"


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["notion", "get", "PID", "--json"]).as_json is True
    assert p.parse_args(["notion", "blocks", "PID", "--format", "md"]).fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    # delitem (not raw pop) so the popped client module is restored at
    # teardown -- a raw pop leaks a sys.modules-vs-package-attr desync that
    # breaks string-target monkeypatching in later tests.
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.notion.client", raising=False)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t_ops.connectors.notion.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t_ops.connectors.notion.commands"))
    assert seen["client"] is False


import types
import pytest
from h2t_ops.connectors.notion import commands as notion_cmds
from h2t_ops.core.errors import UsageError


class _FakeClient:
    def get_blocks(self, page_id, limit=None): return [{"type": "paragraph", "id": "b1"}]
    def blocks_to_markdown(self, blocks): return "MD"
    def update_page(self, *a, **k): return {"id": "p"}
    def list_comments(self, page_id): return [{"id": "c1", "text": "hi", "created_time": "2026-05-25T10:00:00.000Z", "created_by_id": "u1"}]
    def create_comment(self, page_id, body): return {"id": "c2", "text": body, "created_time": "2026-05-25T10:00:00.000Z", "created_by_id": "u1"}
    def create_database(self, parent_page_id, *, title, properties):
        return {"id": "db-new", "object": "database", "_title": title, "_props": properties}
    def patch_db_schema(self, database_id, *, properties, data_source_id=None):
        return {"id": "ds1", "object": "data_source", "_props": properties, "_ds": data_source_id}


def _ns(**kw):
    return types.SimpleNamespace(**kw)


# Patch the LIVE client module object (resolves via sys.modules, the same
# path run()'s lazy `from ...client import NotionClient` uses). A string
# target would resolve via package attrs and desync if an upstream test
# raw-popped the client from sys.modules.
def _patch_client(monkeypatch):
    import h2t_ops.connectors.notion.client as _client_mod
    monkeypatch.setattr(_client_mod, "NotionClient", lambda *a, **k: _FakeClient())


def test_get_json_returns_raw_blocks(monkeypatch):
    _patch_client(monkeypatch)
    out = notion_cmds.run(_ns(notion_cmd="get", page_id="P", as_json=True, fmt="human"))
    assert out == [{"type": "paragraph", "id": "b1"}]          # raw list, not "MD"


def test_get_human_returns_markdown(monkeypatch):
    _patch_client(monkeypatch)
    out = notion_cmds.run(_ns(notion_cmd="get", page_id="P", as_json=False, fmt="human"))
    assert out == "MD"


def test_update_noop_raises_usageerror(monkeypatch):
    _patch_client(monkeypatch)
    with pytest.raises(UsageError):
        notion_cmds.run(_ns(notion_cmd="update", page_id="P", title=None,
                            append=None, file=None, replace=False))


from h2t_ops.cli import build_parser, dispatch


def test_version_branch_exits_zero(capsys):
    assert dispatch(["--version"]) == 0
    assert "h2t-ops " in capsys.readouterr().out


def test_connectors_list_no_heavy_import(capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError("connectors list must not import SDK")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert dispatch(["connectors"]) == 0
    assert "notion" in capsys.readouterr().out


def test_doctor_reports_connectors(capsys):
    assert dispatch(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "notion" in out and "secrets" in out


def test_ingest_notion_shim_warns_on_human(monkeypatch, capsys):
    called = {}

    def fake_run(args):
        called["ran"] = True
        return "OK"

    monkeypatch.setattr("h2t_ops.connectors.notion.commands.run", fake_run)
    code = dispatch(["ingest", "notion", "get", "PID"])
    err = capsys.readouterr().err
    assert called.get("ran") is True
    assert "deprecat" in err.lower()
    assert code == 0


def test_ingest_notion_shim_silent_on_json(monkeypatch, capsys):
    def fake_run_json(args):
        return {"id": "x"}

    monkeypatch.setattr("h2t_ops.connectors.notion.commands.run", fake_run_json)
    code = dispatch(["ingest", "notion", "get", "PID", "--json"])
    cap = capsys.readouterr()
    assert "deprecat" not in cap.err.lower()
    assert code == 0


def test_register_adds_comments_subcommands():
    p = _parser()
    ns = p.parse_args(["notion", "comments", "PAGE1"])
    assert ns.notion_cmd == "comments" and ns.page_id == "PAGE1"
    ns = p.parse_args(["notion", "comment", "PAGE1", "--body", "Hello"])
    assert ns.notion_cmd == "comment" and ns.page_id == "PAGE1" and ns.body == "Hello"


def test_comments_dispatch(monkeypatch):
    _patch_client(monkeypatch)
    out = notion_cmds.run(_ns(notion_cmd="comments", page_id="page1", as_json=True, fmt="human"))
    assert isinstance(out, list)
    assert out[0]["id"] == "c1"


def test_comment_dispatch(monkeypatch):
    _patch_client(monkeypatch)
    out = notion_cmds.run(_ns(notion_cmd="comment", page_id="page1", body="Hello", as_json=True, fmt="human"))
    assert out["id"] == "c2"
    assert out["text"] == "Hello"


def test_create_database_and_patch_schema_parser_surface():
    p = _parser()
    cd = p.parse_args(["notion", "create-database", "parent1",
                       "--title", "Partners", "--properties-file", "s.json"])
    assert cd.notion_cmd == "create-database" and cd.parent_page_id == "parent1"
    assert cd.title == "Partners" and cd.properties_file == "s.json"
    ps = p.parse_args(["notion", "patch-db-schema", "db1",
                       "--properties-file", "s.json", "--data-source-id", "ds9"])
    assert ps.notion_cmd == "patch-db-schema" and ps.database_id == "db1"
    assert ps.data_source_id == "ds9"


def test_create_database_dispatch_reads_properties_file(monkeypatch, tmp_path):
    _patch_client(monkeypatch)
    f = tmp_path / "schema.json"
    f.write_text('{"Company": {"title": {}}, "Score": {"number": {}}}', encoding="utf-8")
    out = notion_cmds.run(_ns(notion_cmd="create-database", parent_page_id="parent1",
                              title="Partners", properties_file=str(f),
                              as_json=True, fmt="human"))
    assert out["id"] == "db-new"
    assert out["_title"] == "Partners"
    assert out["_props"]["Company"] == {"title": {}}


def test_patch_db_schema_dispatch_reads_properties_file(monkeypatch, tmp_path):
    _patch_client(monkeypatch)
    f = tmp_path / "schema.json"
    f.write_text('{"Website": {"url": {}}}', encoding="utf-8")
    out = notion_cmds.run(_ns(notion_cmd="patch-db-schema", database_id="db1",
                              properties_file=str(f), data_source_id=None,
                              as_json=True, fmt="human"))
    assert out["id"] == "ds1"
    assert out["_props"] == {"Website": {"url": {}}}


def test_patch_db_schema_dispatch_missing_file_raises_usageerror(monkeypatch):
    _patch_client(monkeypatch)
    with pytest.raises(UsageError):
        notion_cmds.run(_ns(notion_cmd="patch-db-schema", database_id="db1",
                            properties_file="nonexistent.json", data_source_id=None,
                            as_json=True, fmt="human"))


def test_connector_help_exits_zero(capsys):
    """_run_connector must return 0 for --help (argparse SystemExit(0))."""
    code = dispatch(["notion", "--help"])
    assert code == 0
    assert "notion" in capsys.readouterr().out


def test_connector_subcommand_help_exits_zero(capsys):
    code = dispatch(["notion", "get", "--help"])
    assert code == 0


def test_find_project_tasks_parser_registered():
    """Audit #144: find-project-tasks must exist as a notion subcommand with the
    legacy default database id."""
    import argparse
    from h2t_ops.connectors.notion.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    args = parser.parse_args(["notion", "find-project-tasks", "proj-page-id"])
    assert args.notion_cmd == "find-project-tasks"
    assert args.project_page_id == "proj-page-id"
    assert args.database_id == "beabac7bf4314952a9327759c638d89f"  # legacy default
    assert args.limit is None


def test_find_project_tasks_dispatch_uses_relation_filter(monkeypatch):
    """find-project-tasks must build the Project-relation filter shape
    {'property':'Project','relation':{'contains': <page_id>}} and pass --limit
    through to client.query_database."""
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls: list[tuple] = []

    class _StubClient:
        def query_database(self, db, *, filter_dict=None, limit=None, **_):
            calls.append(("query", db, filter_dict, limit))
            return [{"id": "task-1"}, {"id": "task-2"}]

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _StubClient())

    args = SimpleNamespace(
        notion_cmd="find-project-tasks",
        project_page_id="proj-1",
        database_id="db-1",
        limit=5,
        as_json=True,
        fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "task-1"}, {"id": "task-2"}]
    assert calls == [(
        "query",
        "db-1",
        {"property": "Project", "relation": {"contains": "proj-1"}},
        5,
    )]


def test_find_project_tasks_dispatch_markdown_uses_database_metadata(monkeypatch):
    """Human/md output path must call get_database + database_items_to_markdown
    (mirrors `search` and `get-database` dispatch in the same module)."""
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    class _StubClient:
        def query_database(self, db, *, filter_dict=None, limit=None, **_):
            return [{"id": "task-1"}]
        def get_database(self, db):
            return {"id": db, "title": [{"plain_text": "Tasks"}]}
        def database_items_to_markdown(self, rows, meta):
            return f"# {meta['title'][0]['plain_text']} ({len(rows)} rows)"

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _StubClient())

    args = SimpleNamespace(
        notion_cmd="find-project-tasks",
        project_page_id="proj-1",
        database_id="db-1",
        limit=None,
        as_json=False,
        fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == "# Tasks (1 rows)"


def test_find_databases_parser_accepts_recursive_rows_limits_and_json():
    ns = _parser().parse_args([
        "notion", "find-databases", "PAGE",
        "--recursive", "--max-depth", "4", "--limit-blocks", "200",
        "--with-rows", "--row-limit", "5", "--json",
    ])
    assert ns.recursive is True
    assert ns.max_depth == 4
    assert ns.limit_blocks == 200
    assert ns.with_rows is True
    assert ns.row_limit == 5
    assert ns.as_json is True


def test_search_workspace_parser_accepts_object_limit_and_json():
    ns = _parser().parse_args([
        "notion", "search-workspace", "--object", "page", "--limit", "5", "--json",
    ])
    assert ns.notion_cmd == "search-workspace"
    assert ns.object == "page"
    assert ns.limit == 5
    assert ns.as_json is True

    ns2 = _parser().parse_args([
        "notion", "search-workspace", "--object", "data_source", "--json",
    ])
    assert ns2.object == "data_source"


def test_search_workspace_and_graph_parsers_registered():
    parser = _parser()
    ns = parser.parse_args([
        "notion", "graph", "ROOT", "--max-depth", "2", "--include-databases", "--json",
    ])
    assert ns.notion_cmd == "graph"
    assert ns.root_page_id == "ROOT"
    assert ns.max_depth == 2
    assert ns.include_databases is True
    assert ns.as_json is True

    ns2 = parser.parse_args(["notion", "graph", "ROOT", "--json"])
    assert ns2.include_databases is True

    ns3 = parser.parse_args(["notion", "graph", "ROOT", "--no-include-databases", "--json"])
    assert ns3.include_databases is False


def test_find_databases_dispatch_passes_recursive_options(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def find_databases_on_page(self, page_id, **kwargs):
            calls.append((page_id, kwargs))
            return {"kind": "notion_database_discovery/v1"}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="find-databases",
        page_id="PAGE",
        recursive=True,
        max_depth=4,
        limit_blocks=200,
        with_rows=True,
        row_limit=5,
        as_json=True,
        fmt="human",
    ))

    assert out == {"kind": "notion_database_discovery/v1"}
    assert calls == [("PAGE", {
        "recursive": True,
        "max_depth": 4,
        "limit_blocks": 200,
        "with_rows": True,
        "row_limit": 5,
    })]


def test_graph_dispatch_passes_options(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def graph_page(self, root_page_id, **kwargs):
            calls.append((root_page_id, kwargs))
            return {"kind": "notion_workspace_graph/v1"}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="graph",
        root_page_id="ROOT",
        max_depth=2,
        include_databases=True,
        root_label="KB",
        as_json=True,
        fmt="human",
    ))

    assert out == {"kind": "notion_workspace_graph/v1"}
    assert calls == [("ROOT", {
        "max_depth": 2,
        "include_databases": True,
        "root_label": "KB",
    })]


def test_find_databases_recursive_json_uses_universal_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.notion.client as client_mod

    class _Stub:
        def find_databases_on_page(self, page_id, **kwargs):
            return {"kind": "notion_database_discovery/v1", "databases": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    code = dispatch(["notion", "find-databases", "PAGE", "--recursive", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["provider"] == "notion"
    assert payload["result"]["kind"] == "notion_database_discovery/v1"


def test_search_workspace_json_uses_universal_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.notion.client as client_mod

    class _Stub:
        def search_workspace(self, object_type="all", *, limit=None):
            assert object_type == "page"
            assert limit == 0
            return {"kind": "notion_workspace_search/v1", "results": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    code = dispatch(["notion", "search-workspace", "--object", "page", "--limit", "0", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "notion_workspace_search/v1"


def test_graph_json_uses_universal_envelope(monkeypatch, capsys):
    import h2t_ops.connectors.notion.client as client_mod

    class _Stub:
        def graph_page(self, root_page_id, **kwargs):
            assert root_page_id == "ROOT"
            return {"kind": "notion_workspace_graph/v1", "nodes": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    code = dispatch(["notion", "graph", "ROOT", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "notion_workspace_graph/v1"


def test_search_workspace_json_default_limit_is_none(monkeypatch, capsys):
    import h2t_ops.connectors.notion.client as client_mod

    calls = []

    class _Stub:
        def search_workspace(self, object_type="all", *, limit=None):
            calls.append({"object_type": object_type, "limit": limit})
            return {"kind": "notion_workspace_search/v1", "results": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    cli_main = dispatch

    code = cli_main(["notion", "search-workspace", "--object", "page", "--json"])

    assert code == 0
    assert calls == [{"object_type": "page", "limit": None}]
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "notion_workspace_search/v1"


def test_sync_databases_json_without_include_databases_raises(tmp_path, monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def get_blocks(self, page_id):
            calls.append(("get_blocks", page_id))
            raise AssertionError("get_blocks must not be called")

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())

    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            notion_cmd="sync",
            page_id="P",
            output_file=str(tmp_path / "page.md"),
            preserve_metadata=False,
            include_databases=False,
            recursive=False,
            max_depth=3,
            row_limit=100,
            databases_json=str(tmp_path / "sidecar.json"),
            as_json=False,
            fmt="human",
        ))

    assert calls == []


def test_sync_databases_json_same_as_output_raises_before_client_io(tmp_path, monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    from pathlib import Path

    calls = []
    writes = []

    class _Stub:
        def get_blocks(self, page_id):
            calls.append(("get_blocks", page_id))
            raise AssertionError("get_blocks must not be called")

        def find_databases_on_page(self, page_id, **kwargs):
            calls.append(("find_databases_on_page", page_id, kwargs))
            raise AssertionError("find_databases_on_page must not be called")

    original_write_text = Path.write_text

    def spy_write_text(self, *args, **kwargs):
        writes.append(self)
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    monkeypatch.setattr(Path, "write_text", spy_write_text)
    output = tmp_path / "page.md"

    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            notion_cmd="sync",
            page_id="P",
            output_file=str(output),
            preserve_metadata=False,
            include_databases=True,
            recursive=False,
            max_depth=3,
            row_limit=100,
            databases_json=str(output),
            as_json=False,
            fmt="human",
        ))

    assert calls == []
    assert writes == []
    assert not output.exists()


def test_sync_include_databases_writes_markdown_and_json_sidecar(tmp_path, monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def get_blocks(self, page_id):
            return [{"id": "b1", "type": "paragraph"}]

        def blocks_to_markdown(self, blocks):
            return "Body\n"

        def find_databases_on_page(self, page_id, **kwargs):
            calls.append((page_id, kwargs))
            return {
                "kind": "notion_database_discovery/v1",
                "databases": [
                    {"title": "Tasks", "database_id": "db1", "type": "child_database",
                     "row_count": 1},
                ],
                "stats": {"databases_found": 1},
            }

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    md = tmp_path / "page.md"
    sidecar = tmp_path / "nested" / "sidecar.json"

    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="sync",
        page_id="P",
        output_file=str(md),
        preserve_metadata=False,
        include_databases=True,
        recursive=True,
        max_depth=3,
        row_limit=5,
        databases_json=str(sidecar),
        as_json=False,
        fmt="human",
    ))

    assert "Synced to" in out
    assert "## Embedded databases" in md.read_text(encoding="utf-8")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["kind"] == "notion_database_discovery/v1"
    assert calls == [("P", {
        "recursive": True,
        "max_depth": 3,
        "with_rows": True,
        "row_limit": 5,
    })]


def test_sync_primary_markdown_write_failure_does_not_create_sidecar(tmp_path, monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace
    from pathlib import Path

    class _Stub:
        def get_blocks(self, page_id):
            return [{"id": "b1", "type": "paragraph"}]

        def blocks_to_markdown(self, blocks):
            return "Body\n"

        def find_databases_on_page(self, page_id, **kwargs):
            return {
                "kind": "notion_database_discovery/v1",
                "databases": [
                    {"title": "Tasks", "database_id": "db1", "type": "child_database",
                     "row_count": 1},
                ],
            }

    original_write_text = Path.write_text
    md = tmp_path / "page.md"
    sidecar = tmp_path / "sidecar.json"

    def fail_primary_write_only(self, *args, **kwargs):
        if self == md:
            raise OSError("deterministic primary write failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    monkeypatch.setattr(Path, "write_text", fail_primary_write_only)

    with pytest.raises(OSError, match="deterministic primary write failure"):
        cmds_mod.run(SimpleNamespace(
            notion_cmd="sync",
            page_id="P",
            output_file=str(md),
            preserve_metadata=False,
            include_databases=True,
            recursive=False,
            max_depth=3,
            row_limit=100,
            databases_json=str(sidecar),
            as_json=False,
            fmt="human",
        ))

    assert not sidecar.exists()


# --- P0 lifecycle command dispatch tests ---

def test_create_db_item_dispatch(monkeypatch, tmp_path):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def create_db_item(self, database_id, *, title, property_json=None):
            calls.append(("create_db_item", database_id, title, property_json))
            return {"id": "new-page"}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="create-db-item",
        database_id="db1",
        title="My Task",
        property_json=None,
        as_json=True,
        fmt="human",
    ))
    assert out == {"id": "new-page"}
    assert calls == [("create_db_item", "db1", "My Task", None)]


def test_update_db_item_dispatch(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def update_db_item(self, page_id, *, property_json):
            calls.append(("update_db_item", page_id, property_json))
            return {"id": page_id}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="update-db-item",
        page_id="page1",
        property_json='{"Status":{"select":{"name":"Done"}}}',
        as_json=True,
        fmt="human",
    ))
    assert out == {"id": "page1"}
    assert calls[0][0] == "update_db_item"


def test_archive_dispatch(monkeypatch):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    calls = []

    class _Stub:
        def archive_page(self, page_id, *, confirm_title):
            calls.append(("archive", page_id, confirm_title))
            return {"id": page_id, "archived": True}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="archive",
        page_id="page1",
        confirm_title="My Page",
        as_json=True,
        fmt="human",
    ))
    assert out["archived"] is True
    assert calls == [("archive", "page1", "My Page")]


def test_append_blocks_dispatch(monkeypatch, tmp_path):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    md_file = tmp_path / "content.md"
    md_file.write_text("# Hello\n", encoding="utf-8")
    calls = []

    class _Stub:
        def append_blocks_from_file(self, page_id, content_file):
            calls.append(("append", page_id, content_file))
            return {"results": []}

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="append-blocks",
        page_id="page1",
        content_file=str(md_file),
        as_json=True,
        fmt="human",
    ))
    assert calls == [("append", "page1", str(md_file))]


def test_replace_content_dispatch(monkeypatch, tmp_path):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands as cmds_mod
    from types import SimpleNamespace

    md_file = tmp_path / "content.md"
    md_file.write_text("Replacement.\n", encoding="utf-8")
    calls = []

    class _Stub:
        def replace_page_content_safe(self, page_id, content_file, *, confirm_title):
            calls.append(("replace", page_id, content_file, confirm_title))

    monkeypatch.setattr(client_mod, "NotionClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        notion_cmd="replace-content",
        page_id="page1",
        content_file=str(md_file),
        confirm_title="My Page",
        as_json=True,
        fmt="human",
    ))
    assert out == {"status": "replaced", "page_id": "page1"}
    assert calls == [("replace", "page1", str(md_file), "My Page")]
