# lib/eval/test_report.py
import json
from pathlib import Path

from lib.eval import report as rep


def _write_session(root: Path, skill: str, name: str, payload) -> None:
    d = root / skill / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        (d / name).write_text(payload, encoding="utf-8")
    else:
        (d / name).write_text(json.dumps(payload), encoding="utf-8")


def _session(skill="session-start", status="success",
             started="2026-07-14T10:00:00+00:00", metrics=None):
    return {"skill": skill, "domain": "dev", "project": "h2t-ai",
            "status": status, "started_at": started, "ended_at": started,
            "metrics": metrics or []}


def test_load_sessions_counts_good_malformed_undated_and_root(tmp_path):
    root = tmp_path / "evals"
    _write_session(root, "session-start", "a.json", _session())
    _write_session(root, "session-start", "b.json", "{not json")          # malformed
    _write_session(root, "handoff", "c.json", _session(skill="handoff",
                   started="not-a-date"))                                 # undated
    sessions, stats = rep.load_sessions(root)
    assert stats.root_readable is True
    assert stats.files_seen == 3
    assert stats.loaded == 1
    assert stats.malformed_skipped == 1
    assert stats.undated_skipped == 1
    assert [s["skill"] for s in sessions] == ["session-start"]


def test_load_sessions_missing_root_is_not_empty_store(tmp_path):
    sessions, stats = rep.load_sessions(tmp_path / "nope")
    assert stats.root_readable is False
    assert sessions == []
    assert stats.files_seen == 0
