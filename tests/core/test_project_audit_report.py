"""The project-audit report script has no tests of its own; this covers the path
ruff's F821 exposed — `json.dumps` on the not-found branch, with `json` never imported.

Reproduced before the fix: `NameError: name 'json' is not defined`, exit 1 with a
traceback, on the branch whose whole job is to report the error politely.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "plugins" / "h2t-core" / "skills" / "project-audit" / "scripts" / "report.py"


def _run(tmp_path, project_id):
    projects = tmp_path / "projects.yaml"
    projects.write_text("projects:\n  - id: something-else\n    claude_md: false\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(REPORT), project_id, "--field", "claude_md=true",
         "--projects-yaml", str(projects)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


def test_a_missing_project_reports_json_instead_of_crashing(tmp_path):
    result = _run(tmp_path, "no-such-project")
    assert "NameError" not in result.stderr, result.stderr[-300:]
    assert "Traceback" not in result.stderr, result.stderr[-300:]
    # the script prints the error object first, then a summary object — read the first line
    payload = json.loads(result.stdout.strip().splitlines()[0])
    assert "not found" in payload["error"]


def test_a_present_project_is_still_updated(tmp_path):
    """The control. Without it, a script that printed the error for every input
    would satisfy the test above."""
    result = _run(tmp_path, "something-else")
    assert "NameError" not in result.stderr
    assert "not found" not in result.stdout
