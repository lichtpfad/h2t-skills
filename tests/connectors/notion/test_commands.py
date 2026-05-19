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
    sys.modules.pop("h2t.connectors.notion.client", None)
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
