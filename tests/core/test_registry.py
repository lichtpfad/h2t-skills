import sys
import builtins
from h2t.core.registry import ConnectorSpec, discover, resolve_client


def test_connectorspec_fields():
    spec = ConnectorSpec(name="x", help="h", client="pkg.mod:Cls", register=lambda s: None)
    assert spec.name == "x" and spec.client == "pkg.mod:Cls"


def test_discover_finds_notion():
    specs = {s.name: s for s in discover()}
    assert "notion" in specs
    assert specs["notion"].client == "h2t.connectors.notion.client:NotionClient"


def test_discover_does_not_import_notion_sdk(monkeypatch):
    real_import = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError(f"discovery must not import {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    sys.modules.pop("h2t.connectors.notion.client", None)
    assert "notion" in {s.name for s in discover()}


def test_resolve_client_lazy_returns_class():
    spec = next(s for s in discover() if s.name == "notion")
    assert resolve_client(spec).__name__ == "NotionClient"
