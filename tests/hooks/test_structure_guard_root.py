"""Root scratch and undeclared new root directories are blocked without opt-in."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path


def _load():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "structure_guard.py"
    spec = importlib.util.spec_from_file_location("structure_guard_root_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_root_scratch_blocked(tmp_path):
    m = _load()
    for name in ("null", "run.log", "diag_x.py", "tmp_out.json", "dump.jsonl", "spec.md.bak"):
        code, msg = m.check_root_universal(name, None, tmp_path)
        assert code == 2, name
        assert "BLOCKED" in msg


def test_root_files_otherwise_allowed(tmp_path):
    m = _load()
    for name in ("README.md", "pyproject.toml", "CLAUDE.md", ".gitignore"):
        assert m.check_root_universal(name, None, tmp_path)[0] == 0, name


def test_new_root_dir_blocked_existing_or_declared_allowed(tmp_path):
    m = _load()
    (tmp_path / "transcription").mkdir()
    assert m.check_root_universal("transcription/x.py", None, tmp_path)[0] == 0   # exists
    assert m.check_root_universal("docs/x.md", None, tmp_path)[0] == 0            # always
    assert m.check_root_universal("newthing/x.py", None, tmp_path)[0] == 2        # undeclared
    cfg = {"allowed_root_dirs": ["newthing/"]}
    assert m.check_root_universal("newthing/x.py", cfg, tmp_path)[0] == 0         # declared


def test_main_blocks_root_scratch_without_config(tmp_path, monkeypatch, capsys):
    m = _load()
    monkeypatch.chdir(tmp_path)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "null"), "content": ""}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert m.main() == 2
    assert "BLOCKED" in capsys.readouterr().err
