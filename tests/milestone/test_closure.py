import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/milestone-closure/scripts"
sys.path.insert(0, str(_SCRIPT_DIR))

from closure import (
    build_report,
    fetch_next_open_items,
    find_milestone,
    milestone_status,
    run_docs_lint_plan,
)


def test_find_milestone_by_title():
    milestones = [
        {"number": 1, "title": "M1", "open_issues": 0, "closed_issues": 3},
        {"number": 2, "title": "M2", "open_issues": 1, "closed_issues": 4},
    ]
    assert find_milestone(milestones, "M2")["number"] == 2


def test_find_milestone_by_number_string():
    milestones = [{"number": 7, "title": "skills-release", "open_issues": 0}]
    assert find_milestone(milestones, "7")["title"] == "skills-release"


def test_milestone_status_blocked_when_open_issues():
    milestone = {"title": "M2", "open_issues": 2, "closed_issues": 5}
    assert milestone_status(milestone) == "blocked"


def test_milestone_status_ready_when_zero_open_issues():
    milestone = {"title": "M2", "open_issues": 0, "closed_issues": 5}
    assert milestone_status(milestone) == "ready"


def test_run_docs_lint_plan_uses_unified_docs_lint(tmp_path):
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="plan ok", stderr="")
        result = run_docs_lint_plan(tmp_path, python="python")
    assert result["status"] == "ok"
    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert "docs-lint" in " ".join(cmd)
    assert "plan" in cmd
    assert "--root" in cmd
    assert str(tmp_path) in cmd


def test_build_report_has_contract_fields(tmp_path):
    report = build_report(
        repo="lichtpfad/h2t-skills",
        repo_root=tmp_path,
        milestone={"number": 1, "title": "M1", "open_issues": 0, "closed_issues": 3},
        status="ready",
        docs_lint={"status": "ok"},
        safe_next_action="Review docs-lint plan",
    )
    assert report["schema"] == "h2t_milestone_closure_report/v0.1"
    assert report["producer"] == "h2t-dev/milestone-closure"
    assert report["milestone"]["title"] == "M1"


def test_fetch_next_open_items_uses_real_github_issues():
    payload = '[{"number":196,"title":"Project Lifecycle OS","labels":[{"name":"priority:p1"}]}]'
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        items = fetch_next_open_items("lichtpfad/h2t-skills", limit=3)
    assert items[0]["number"] == 196
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["gh", "issue", "list"]
    assert "--state" in cmd
    assert "open" in cmd


# Amendment A3: close_milestone confirmation tests
def test_close_milestone_refuses_on_title_mismatch():
    from closure import close_milestone
    milestone = {"number": 7, "title": "lifecycle-os", "open_issues": 0}
    with patch("closure.subprocess.run") as mock_run:
        result = close_milestone("owner/repo", milestone, confirm_title="wrong-title")
    assert result["status"] == "error"
    mock_run.assert_not_called()


def test_close_milestone_calls_gh_api_patch():
    from closure import close_milestone
    milestone = {"number": 7, "title": "lifecycle-os", "open_issues": 0}
    with patch("closure.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = close_milestone("owner/repo", milestone, confirm_title="lifecycle-os")
    assert result["status"] == "ok"
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "gh"
    assert cmd[1] == "api"
    assert "PATCH" in cmd
