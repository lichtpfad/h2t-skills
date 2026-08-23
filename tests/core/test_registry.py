import builtins
import sys

from h2t_ops.core.registry import ConnectorSpec, discover, resolve_client


def test_connectorspec_fields():
    spec = ConnectorSpec(name="x", help="h", client="pkg.mod:Cls", register=lambda s: None)
    assert spec.name == "x" and spec.client == "pkg.mod:Cls"


def test_discover_finds_notion():
    specs = {s.name: s for s in discover()}
    assert "notion" in specs
    assert specs["notion"].client == "h2t_ops.connectors.notion.client:NotionClient"


def test_discover_does_not_import_notion_sdk(monkeypatch):
    real_import = builtins.__import__

    def guard(name, *a, **k):
        if name in ("notion_client", "httpx"):
            raise AssertionError(f"discovery must not import {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    # delitem (not raw pop) so the client module is restored at teardown —
    # a raw pop leaks a sys.modules-vs-package-attr desync into later tests.
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.notion.client", raising=False)
    assert "notion" in {s.name for s in discover()}


def test_resolve_client_lazy_returns_class():
    spec = next(s for s in discover() if s.name == "notion")
    assert resolve_client(spec).__name__ == "NotionClient"


def test_discover_skips_broken_connector(tmp_path, monkeypatch):
    import h2t_ops.connectors as _pkg
    pkgdir = tmp_path / "broken_conn"
    pkgdir.mkdir()
    (pkgdir / "__init__.py").write_text("raise ImportError('missing dep')\n", encoding="utf-8")
    monkeypatch.setattr(_pkg, "__path__", list(_pkg.__path__) + [str(tmp_path)])
    names = {s.name for s in discover()}          # must NOT raise
    assert "broken_conn" not in names              # broken connector skipped, not propagated
