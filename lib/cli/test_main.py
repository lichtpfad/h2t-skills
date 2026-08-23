"""Tests for the `h2t-ops gather` CLI.

Retargeted from `lib.cli.main` to `h2t_ops.cli` when the second gather
implementation was deleted: these six cases are the regression net for the
reroute, so they must exercise the path that survived, not the one that went.
"""
import json
import subprocess
import sys
from pathlib import Path

TEST_PYTHON = sys.executable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_h2t(*args):
    result = subprocess.run(
        [TEST_PYTHON, "-m", "h2t_ops.cli", *args],
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


def test_gather_briefing_only_outputs_injection_format():
    code, out, err = run_h2t(
        "gather", "session-start", "--cwd", str(REPO_ROOT), "--briefing-only"
    )
    assert code == 0, f"Expected exit 0. stderr: {err}"
    # Not the giant raw JSON — hook-identical injection format instead.
    assert not out.lstrip().startswith("{"), "briefing-only must not emit raw JSON"
    assert out.startswith("BRIEFING:\n"), "must start with BRIEFING: marker"
    assert "\n\nGATHER_META: " in out, "must carry a GATHER_META line"
    meta_json = out.split("\n\nGATHER_META: ", 1)[1]
    meta = json.loads(meta_json)
    assert "project" in meta, "GATHER_META must carry project for steps 5/7"
    assert meta["project"].get("domain"), "project.domain needed for activity-log"


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
