"""The previous session of this project, from every machine, through the index (#548 §5)."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.gather.briefing import format_briefing
from h2t_ops.lifecycle.gather.sessions import (
    find_latest_session_index,
    find_session_files,
    get_machine_name,
)


def _ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _md(machine, project, sid, updated_at, **extra):
    meta = {"session_id": sid, "machine": machine, "project": project, "domain": "dev",
            "updated_at": updated_at, "branch": "feat/x", "commits": ["a1b2c3d"],
            "done": f"done in {sid}", "remains": "- [ ] carry on", "artifacts": [], **extra}
    f = session_record.session_path(machine, project, sid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(session_record.render(meta, b"# body\n"))
    return f


def _briefing(latest, machine="macbook-pro-3"):
    md, _ = format_briefing({"project": {"id": "p"}, "git": {}, "github": {}, "stack": {},
                             "sessions": ["x"], "latest_session": latest, "machine": machine})
    return md


def test_get_machine_name_prefers_h2t_env(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "h2t-name")
    monkeypatch.setenv("DOR_MACHINE_NAME", "dor-name")

    assert get_machine_name() == "h2t-name"


def test_previous_session_names_machine_and_age(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "automata")
    _md("automata", "p", "s1", _ago(2))

    latest = find_latest_session_index("p")

    assert (latest["machine"], latest["branch"], latest["last_commit"]) == ("automata", "feat/x", "a1b2c3d")
    assert latest["summary_short"] == "done in s1" and latest["next_actions"] == ["carry on"]
    assert latest["here"] is None
    md = _briefing(latest, machine="automata")
    assert "### Previous Session  (automata, 2 дн. назад)" in md
    assert "ветка feat/x, последний коммит a1b2c3d" in md
    assert "⚠" not in md


def test_warning_only_when_other_machine_is_newer(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "macbook-pro-3")
    _md("automata", "p", "there", _ago(2))

    alone = find_latest_session_index("p")
    assert alone["here"] is None, "no session of this project here: nothing to be behind"
    assert "⚠" not in _briefing(alone)

    _md("macbook-pro-3", "p", "here", _ago(5))
    behind = find_latest_session_index("p")
    assert behind["session_id"] == "there" and behind["here"]["machine"] == "macbook-pro-3"
    assert ("⚠ на automata работали позже, чем здесь (macbook-pro-3, 5 дн. назад) — git fetch"
            in _briefing(behind))

    _md("macbook-pro-3", "p", "newest", _ago(0))
    ahead = find_latest_session_index("p")
    assert ahead["session_id"] == "newest" and ahead["here"] is None
    assert "⚠" not in _briefing(ahead)
    assert "(macbook-pro-3, сегодня)" in _briefing(ahead)


def test_other_projects_never_appear(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "m")
    mine = _md("m", "p", "mine", _ago(3))
    _md("m", "q", "theirs", _ago(0))
    _md("other", "q", "theirs-too", _ago(0))

    assert find_latest_session_index("p")["session_id"] == "mine"
    assert find_session_files("p") == [str(mine)]
    assert find_latest_session_index("nope") is None
    assert find_session_files("nope") == []


def test_project_id_and_repo_name_are_both_asked(monkeypatch):
    """#377: project.id first, the repo name for records written before the mapping."""
    old = _md("m", "h2t-skills", "old", _ago(3))
    new = _md("m", "agent-skills", "new", _ago(1))

    assert find_latest_session_index("agent-skills", "h2t-skills")["session_id"] == "new"
    assert find_session_files("agent-skills", "h2t-skills") == [str(new), str(old)]


def test_broken_frontmatter_is_skipped_and_the_rest_shown(monkeypatch):
    """Review Focus 3, as gather sees it: the broken md is not a session, the good one is."""
    good = _md("m", "p", "good", _ago(1))
    broken = good.with_name("broken.md")
    broken.write_bytes(b"---\nsession_id: [unclosed\n---\n")

    assert find_session_files("p") == [str(good)]
    assert find_latest_session_index("p")["session_id"] == "good"


def test_the_latest_is_bounded():
    _md("m", "p", "s1", _ago(0), done="x" * 4000,
        remains="\n".join(f"- [ ] {i} {'a' * 1000}" for i in range(20)),
        artifacts=[{"type": "commit", "ref": str(i)} for i in range(20)])

    latest = find_latest_session_index("p")

    assert len(latest["summary_short"]) <= 1200
    assert len(latest["next_actions"]) == 5
    assert all(len(item) <= 240 for item in latest["next_actions"])
    assert len(latest["artifacts"]) == 10
    assert latest["truncated"] is True


def test_briefing_limit_keeps_the_warning():
    latest = {"machine": "automata", "updated_at": _ago(1), "summary_short": "s" * 1200,
              "next_actions": ["n" * 240] * 5, "artifacts": [{"type": "commit", "ref": "r" * 200}] * 10,
              "here": {"machine": "mac", "updated_at": _ago(4)}}
    section = _briefing(latest).split("### Previous Session", 1)[1]
    section = "### Previous Session" + section.split("\n\n", 1)[0]

    assert len(section) <= 1800
    assert "- [previous session truncated]" in section
    assert section.endswith("— git fetch")


def _legacy_latest(machine, key, data):
    leaf = paths.legacy("sessions.h2t") / machine / key
    leaf.mkdir(parents=True, exist_ok=True)
    (leaf / "latest.json").write_text(json.dumps(data), encoding="utf-8")
    return leaf


def _legacy_tree() -> dict:
    roots = (paths.legacy("sessions.h2t"), paths.legacy("sessions.dor"))
    return {str(f): f.stat().st_mtime_ns for r in roots for f in r.rglob("*")}


def test_legacy_fallback_before_migration(monkeypatch):
    """4.0.x before sync: the index has nothing for the project, the 3.x roots do."""
    leaf = _legacy_latest("automata", "p", {"version": 1, "session_id": "old-3x",
                                            "summary_short": "from 3.x", "next_actions": ["go"]})
    (leaf / "old-3x.md").write_text("# 3.x handoff\n", encoding="utf-8")
    dor = paths.legacy("sessions.dor") / "laptop" / "p" / "dor.md"
    dor.parent.mkdir(parents=True)
    dor.write_text("# dor handoff\n", encoding="utf-8")
    before = _legacy_tree()

    latest = find_latest_session_index("p")

    assert latest["session_id"] == "old-3x" and latest["machine"] == "automata"
    assert set(find_session_files("p")) == {str(leaf / "old-3x.md"), str(dor)}
    md = _briefing(latest)
    assert "from 3.x" in md
    assert "ℹ сессии ещё в старом месте — h2t-setup sync перенесёт их" in md
    assert _legacy_tree() == before, "the 3.x roots are read, never written"


def test_legacy_is_not_read_once_the_index_knows_the_project(monkeypatch):
    _legacy_latest("automata", "p", {"version": 1, "session_id": "old-3x"})
    _md("m", "p", "new", _ago(0))

    latest = find_latest_session_index("p")

    assert latest["session_id"] == "new" and "legacy" not in latest
    assert "старом месте" not in _briefing(latest)


def test_legacy_latest_json_is_newest_by_mtime():
    older = _legacy_latest("machine-a", "repo", {"version": 1, "session_id": "older"}) / "latest.json"
    newer = _legacy_latest("machine-b", "repo", {"version": 1, "session_id": "newer"}) / "latest.json"
    st = newer.stat()
    os.utime(newer, (st.st_atime + 10, st.st_mtime + 10))
    assert older.is_file()

    assert find_latest_session_index("repo")["session_id"] == "newer"


def test_an_index_that_cannot_open_is_a_failed_source(monkeypatch, capfd, tmp_path):
    """gather still prints, and names the dead source instead of a silent empty history."""
    import sqlite3
    import sys

    from h2t_ops.lifecycle import session_start

    def dead(*a, **kw):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setenv("H2T_EVALS_MODE", "off")
    monkeypatch.setattr(session_start, "identify_project", lambda cwd: {"id": "p", "domain": "dev"})
    monkeypatch.setattr(session_start, "find_session_files", dead)
    monkeypatch.setattr(sys, "argv", ["h2t-gather", "--cwd", str(tmp_path)])
    session_start.main()

    data = json.loads(capfd.readouterr().out)
    assert data["_meta"]["sources_failed"] == ["sessions"]
    assert data["sessions"] == [] and data["latest_session"] is None
