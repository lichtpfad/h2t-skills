"""Tests for h2t gather CLI."""
import json
import subprocess
import sys
from pathlib import Path

TEST_PYTHON = sys.executable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_h2t(*args):
    result = subprocess.run(
        [TEST_PYTHON, "-m", "lib.cli.main", *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT)
    )
    return result.returncode, result.stdout, result.stderr


def test_gather_session_start_returns_json():
    code, out, err = run_h2t("gather", "session-start", "--cwd", str(REPO_ROOT))
    assert code == 0, f"Expected exit 0, got {code}. stderr: {err}"
    data = json.loads(out)
    assert "project" in data
    assert "git" in data


def test_gather_with_format_briefing_includes_briefing():
    code, out, err = run_h2t("gather", "session-start", "--cwd", str(REPO_ROOT), "--format-briefing")
    assert code == 0, f"Expected exit 0. stderr: {err}"
    data = json.loads(out)
    assert "_briefing" in data
    assert len(data["_briefing"]) > 0


def test_gather_handoff_returns_json():
    code, out, err = run_h2t("gather", "handoff", "--cwd", str(REPO_ROOT))
    assert code == 0, f"Expected exit 0. stderr: {err}"
    data = json.loads(out)
    assert "project" in data
    assert "git" in data


def test_unknown_subcommand_exits_nonzero():
    code, out, err = run_h2t("unknowncommand")
    assert code != 0


def test_gather_missing_skill_exits_nonzero():
    code, out, err = run_h2t("gather")
    assert code != 0
