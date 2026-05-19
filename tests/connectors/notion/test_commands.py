import argparse
import sys
import builtins
from h2t.connectors.notion.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t")
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
    monkeypatch.delitem(sys.modules, "h2t.connectors.notion.client", raising=False)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t.connectors.notion.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t.connectors.notion.commands"))
    assert seen["client"] is False


import types
import pytest
from h2t.connectors.notion import commands as notion_cmds
from h2t.core.errors import UsageError


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
    import h2t.connectors.notion.client as _client_mod
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
