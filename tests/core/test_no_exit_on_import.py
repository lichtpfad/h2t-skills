"""A missing dependency is reported by main(), never by sys.exit at import (#429).

An exit at module scope turned one absent package into a pytest INTERNALERROR that zeroed
a whole test directory. Each case blocks the dependency, imports the script (must not
exit), then runs it as a CLI (must still fail with the documented code). The second half
keeps "no exit on import" from being satisfied by deleting the guard.
"""
import importlib.abc
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# drive_cli.py and meetgeek_cli.py were cases here until Task 12 deleted them. The
# connectors that replaced them import their provider libraries lazily, which
# tests/connectors/*/test_*.py pins (e.g. test_module_has_no_module_level_requests_import).
CASES = [
    ("h2t_ops/lifecycle/apply_registration.py", "ruamel", 1),
]


class _Block(importlib.abc.MetaPathFinder):
    def __init__(self, prefix):
        self.prefix = prefix

    def find_spec(self, name, path=None, target=None):
        if name == self.prefix or name.startswith(self.prefix + "."):
            raise ImportError(f"blocked for the test: {name}")
        return None


def _load(rel, monkeypatch):
    script = REPO / rel
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location(f"_no_exit_{script.stem}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("rel,blocked,code", CASES, ids=[Path(c[0]).stem for c in CASES])
def test_missing_dependency_is_reported_by_main_not_at_import(rel, blocked, code, monkeypatch, capsys):
    for name in list(sys.modules):
        if name == blocked or name.startswith(blocked + "."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_Block(blocked), *sys.meta_path])
    monkeypatch.setattr(sys, "argv", [rel])

    module = _load(rel, monkeypatch)  # must not raise SystemExit

    try:
        result = module.main([]) if "argv" in module.main.__code__.co_varnames else module.main()
    except SystemExit as exc:
        result = exc.code
    assert result == code
    out = capsys.readouterr()
    assert "not installed" in out.err or json.loads(out.out)["status"] == "error"
