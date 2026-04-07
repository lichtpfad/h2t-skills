"""Unit tests for skill_graph CLI — mocks SkillGraphClient."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import json
import pytest
from unittest.mock import patch, MagicMock


def _run_cli(*args):
    """Run CLI with given args, return (stdout, exit_code)."""
    from io import StringIO
    from skill_graph.cli import main
    import contextlib
    out = StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out):
            main(list(args))
    except SystemExit as e:
        code = e.code or 0
    return out.getvalue(), code


def test_query_subcommand_prints_results():
    fake_results = [{"id": "p1", "score": 0.9, "title": "Hook pattern", "body": "Use hooks."}]
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.query.return_value = fake_results
        out, code = _run_cli("query", "--context", "hook injection")
    assert "Hook pattern" in out
    assert code == 0


def test_query_no_results_says_nothing_found():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.query.return_value = []
        out, code = _run_cli("query", "--context", "unknown topic")
    assert "No results" in out
    assert code == 0


def test_add_lesson_subcommand():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.add_lesson.return_value = "lesson-42"
        out, code = _run_cli(
            "add-lesson",
            "--skill", "session-start",
            "--trigger", "gate was skipped",
            "--resolution", "added GATE block to step 4",
        )
    assert "lesson-42" in out
    assert code == 0
    MockClient.return_value.add_lesson.assert_called_once_with(
        skill_name="session-start",
        trigger="gate was skipped",
        resolution="added GATE block to step 4",
        lesson_type="bug",
        session_id=None,
    )


def test_add_pattern_subcommand():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.add_pattern.return_value = "pat-7"
        out, code = _run_cli(
            "add-pattern",
            "--type", "hook",
            "--title", "PreToolUse injection",
            "--body", "Use PreToolUse to inject data before SKILL.md runs.",
            "--source", "gstack",
        )
    assert "pat-7" in out
    assert code == 0
