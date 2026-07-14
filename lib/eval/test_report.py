# lib/eval/test_report.py
import json
from pathlib import Path

import pytest

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


def test_metric_typed_extraction_none_safe():
    s = _session(metrics=[
        {"key": "core.task_success", "value_bool": True},
        {"key": "skills.duration_ms", "value_num": 1200.0},
        {"key": "skills.error_class", "value_text": "ValueError"},
    ])
    assert rep._metric(s, "core.task_success", "value_bool") is True
    assert rep._metric(s, "skills.duration_ms", "value_num") == 1200.0
    assert rep._metric(s, "skills.error_class", "value_text") == "ValueError"
    assert rep._metric(s, "skills.duration_ms", "value_bool") is None   # wrong slot
    assert rep._metric(s, "core.absent", "value_num") is None           # absent key


@pytest.mark.parametrize("vals,p,expected", [
    ([10.0], 50, 10.0),
    ([10.0, 20.0], 50, 15.0),          # linear interpolation
    ([1.0, 2.0, 3.0, 4.0], 50, 2.5),
    ([1.0, 2.0, 3.0, 4.0], 95, 3.85),
])
def test_percentile_linear_interpolation(vals, p, expected):
    assert rep._percentile(vals, p) == pytest.approx(expected)


def test_percentile_empty_is_none():
    assert rep._percentile([], 50) is None
