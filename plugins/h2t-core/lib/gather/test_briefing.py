from __future__ import annotations

from gather.briefing import format_briefing


def test_briefing_formats_bounded_previous_session_hint():
    data = {
        "project": {"id": "repo", "domain": "dev"},
        "git": {"branch": "main"},
        "github": {},
        "stack": {},
        "sessions": ["full-handoff.md"],
        "latest_session": {
            "summary_short": "Summary",
            "next_actions": ["Next 1", "Next 2"],
            "blockers": [],
            "artifacts": [{"type": "commit", "ref": "abc123"}],
        },
        "machine": "machine",
        "user": {},
        "session_id": "",
    }

    briefing, _ = format_briefing(data)

    assert "### Previous Session" in briefing
    assert "Summary" in briefing
    assert "Next 1" in briefing
    assert "commit:abc123" in briefing
    assert "full-handoff.md" not in briefing
