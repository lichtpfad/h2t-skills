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
