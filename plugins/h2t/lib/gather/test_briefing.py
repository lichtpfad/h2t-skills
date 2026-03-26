"""Tests for briefing formatter."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from unittest.mock import patch

from gather.briefing import format_briefing, _build_slug_template, _build_hints


def _minimal_data(**overrides):
    """Git-only project, no GitHub."""
    base = {
        "project": {"id": "my-tool", "domain": "dev", "type": "git", "github": None},
        "git": {"branch": "main", "status": "", "stash": "", "log": [], "remote": ""},
        "github": {},
        "stack": {"name": "python", "commands": {}},
        "sessions": [],
        "machine": "automata",
        "user": {"name": "stan"},
        "session_id": "abc123",
    }
    base.update(overrides)
    return base


def test_minimal_briefing():
    """Git-only project, no GitHub — header, stack, slug present."""
    data = _minimal_data()
    md, meta = format_briefing(data)

    assert "## Сессия: my-tool (`main`)" in md
    assert "**Stack:** python" in md
    assert "### Задачи" not in md
    assert meta["slug_template"].startswith("my-tool-{task}-")
    assert meta["project"]["id"] == "my-tool"
    assert meta["machine"] == "automata"
    assert meta["session_id"] == "abc123"


def test_full_briefing_with_github():
    """Full briefing: milestones, issues, bugs, PRs, sessions, stash."""
    data = _minimal_data(
        github={
            "current_milestone": {"title": "Phase 5", "open": 3, "closed": 7},
            "milestone_issues": [
                {"number": 10, "title": "Add auth", "labels": [{"name": "priority:p0"}]},
                {"number": 11, "title": "Fix crash", "labels": [{"name": "bug"}]},
                {"number": 12, "title": "Refactor DB", "labels": []},
            ],
            "issues": [{"number": 99, "title": "Other", "labels": []}],
            "bugs": [{"number": 11, "title": "Fix crash"}],
            "prs": [{"number": 5, "title": "feat: auth", "headRefName": "feat/auth"}],
        },
        git={
            "branch": "feat/auth",
            "status": "M  src/main.py\n?? temp.txt",
            "stash": "stash@{0}: WIP on main",
            "log": ["abc1234 initial"],
            "remote": "",
        },
        sessions=["session1.md", "session2.md"],
    )
    md, meta = format_briefing(data)

    # Milestone
    assert "**Milestone:** Phase 5" in md
    assert "3/10 issues open" in md

    # Tasks — uses milestone_issues, not plain issues
    assert "- P0 #10 Add auth" in md
    assert "- BUG #11 Fix crash" in md
    assert "- #12 Refactor DB" in md
    assert "#99" not in md  # plain issues skipped when milestone_issues present

    # Uncommitted
    assert "M  src/main.py" in md
    assert "**Stash:** stash@{0}: WIP on main" in md

    # PRs
    assert "- #5 feat: auth (`feat/auth`)" in md

    # Sessions
    assert "Handoff-файлы: 2" in md


def test_slug_template_with_milestone():
    """Slug with milestone shortening."""
    project = {"id": "crypto"}
    github = {"current_milestone": {"title": "Phase 5"}}

    with patch("gather.briefing.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 26, 14, 30)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        slug = _build_slug_template(project, github)

    assert slug == "crypto-p5-{task}-2026-03-26-1430"


def test_slug_template_without_milestone():
    """Slug without milestone."""
    project = {"id": "art-project"}
    github = {}

    with patch("gather.briefing.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 26, 10, 15)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        slug = _build_slug_template(project, github)

    assert slug == "art-project-{task}-2026-03-26-1015"


def test_workspace_hint():
    """Workspace type shows children list."""
    data = _minimal_data(
        project={
            "id": "workspace", "type": "workspace", "github": None,
            "children": [
                {"id": "h2t-ai", "domain": "dev"},
                {"id": "h2t-vision", "domain": "dev"},
            ],
        },
    )
    md, _ = format_briefing(data)

    assert "Workspace с 2 проектами (h2t-ai, h2t-vision)" in md


def test_unknown_project_hint():
    """Unknown project suggests init-project."""
    data = _minimal_data(
        project={"id": "unknown", "type": "git", "github": None},
    )
    md, _ = format_briefing(data)

    assert "/h2t:init-project" in md


def test_empty_github_no_crash():
    """Empty github dict produces no tasks section, no crash."""
    data = _minimal_data(github={})
    md, meta = format_briefing(data)

    assert "### Задачи" not in md
    assert "### Открытые PR" not in md
    assert "## Сессия:" in md
