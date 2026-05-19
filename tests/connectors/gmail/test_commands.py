import argparse
import sys
import builtins
from h2t_ops.connectors.gmail.commands import register


def _parser():
    p = argparse.ArgumentParser(prog="h2t-ops")
    sub = p.add_subparsers(dest="connector")
    register(sub)
    return p


def test_register_adds_gmail_subcommands():
    ns = _parser().parse_args(["gmail", "list", "--max", "5"])
    assert ns.connector == "gmail" and ns.gmail_cmd == "list" and ns.max == 5


def test_register_has_format_and_json_flags():
    p = _parser()
    assert p.parse_args(["gmail", "list", "--json"]).as_json is True
    assert p.parse_args(["gmail", "read", "MID", "--format", "md"]).fmt == "md"


def test_importing_commands_does_not_import_client(monkeypatch):
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__
    seen = {"client": False}

    def guard(name, *a, **k):
        if name == "h2t_ops.connectors.gmail.client":
            seen["client"] = True
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    import importlib
    importlib.reload(importlib.import_module("h2t_ops.connectors.gmail.commands"))
    assert seen["client"] is False
