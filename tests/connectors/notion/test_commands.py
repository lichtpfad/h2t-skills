import argparse
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
