"""plans/ and specs/ hold dated Markdown only — with or without .h2t/structure.yaml.

The opt-in `plan_dirs` rule protected the repos that had opted in. h2t-transcription had
not, and its plans/ held 200 non-plan files at the 2026-09 audit.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path


def _load():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "structure_guard.py"
    spec = importlib.util.spec_from_file_location("structure_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_dated_markdown_and_index_pass():
    m = _load()
    assert m.check_plan_dirs_universal("docs/superpowers/plans/2026-09-08-x.md")[0] == 0
    assert m.check_plan_dirs_universal("docs/superpowers/specs/2026-09-08-x-design.md")[0] == 0
    assert m.check_plan_dirs_universal("docs/superpowers/plans/README.md")[0] == 0


def test_scratch_shapes_are_blocked():
    m = _load()
    for p in (
        "docs/superpowers/plans/_gc_capture_608494924.jsonl",
        "docs/superpowers/plans/_gc_capture.py",
        "docs/superpowers/plans/_269_reenrich_run.log",
        "docs/superpowers/plans/course-titles-draft.json",
        "docs/superpowers/plans/_draft_00_overview.md",
        "docs/superpowers/plans/review-итог.md",
        "docs/superpowers/plans/_sdtd_sessions/Session_00.md",
    ):
        code, msg = m.check_plan_dirs_universal(p)
        assert code == 2, p
        assert "BLOCKED" in msg


def test_other_paths_untouched():
    m = _load()
    assert m.check_plan_dirs_universal("docs/reports/_scratch.json")[0] == 0
    assert m.check_plan_dirs_universal("scripts/_gc_capture.py")[0] == 0


def test_main_blocks_without_structure_yaml(tmp_path, monkeypatch, capsys):
    """The point of the change: no config file, still blocked."""
    m = _load()
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "docs" / "superpowers" / "plans" / "_gc_capture_1.jsonl"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "{}"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert m.main() == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_main_still_fails_open_elsewhere_without_config(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "anything" / "x.jsonl"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": ""}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert m.main() == 0
