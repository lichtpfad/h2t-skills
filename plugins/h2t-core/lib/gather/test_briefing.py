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


# --- docs debt line -------------------------------------------------------


def _base(**extra) -> dict:
    data = {
        "project": {"id": "repo", "domain": "dev"},
        "git": {"branch": "main"},
        "github": {},
        "stack": {},
        "sessions": [],
    }
    data.update(extra)
    return data


def test_docs_debt_line_is_rendered():
    md, _ = format_briefing(
        _base(docs_debt={"total": 144, "open": 141, "stale": 111, "stale_days": 60})
    )
    assert "**Docs:**" in md
    assert "141" in md and "144" in md
    assert "111" in md and "60" in md


def test_docs_debt_line_absent_when_nothing_open():
    md, _ = format_briefing(
        _base(docs_debt={"total": 12, "open": 0, "stale": 0, "stale_days": 60})
    )
    assert "**Docs:**" not in md


def test_docs_debt_line_absent_when_not_collected():
    """An older gather.py sends no key at all — the briefing must still render."""
    md, _ = format_briefing(_base())
    assert "**Docs:**" not in md
    assert "## Сессия" in md


def test_docs_debt_drops_stale_clause_when_zero():
    md, _ = format_briefing(
        _base(docs_debt={"total": 5, "open": 3, "stale": 0, "stale_days": 60})
    )
    assert "**Docs:**" in md
    assert "60" not in md.split("**Docs:**")[1].splitlines()[0]
