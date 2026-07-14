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


def _dt(day):  # a July-2026 UTC timestamp
    return f"2026-07-{day:02d}T12:00:00+00:00"


def test_build_report_success_and_fallback_math():
    sessions = [
        _session(status="success", started=_dt(14),
                 metrics=[{"key": "core.deflection_rate", "value_num": 1.0}]),
        _session(status="failure", started=_dt(14),
                 metrics=[{"key": "core.deflection_rate", "value_num": 0.0},
                          {"key": "skills.error_class", "value_text": "ValueError"}]),
        _session(status="success", started=_dt(14),
                 metrics=[{"key": "core.deflection_rate", "value_num": 0.5}]),  # off-scale
    ]
    for s in sessions:
        s["_started_dt"] = rep._parse_dt(s["started_at"])
    r = rep.build_report(sessions, now=rep._parse_dt(_dt(14)),
                         recent_days=7, min_n=1)
    row = {s["skill"]: s for s in r["skills"]}["session-start"]
    assert row["runs_recent"] == 3
    assert row["success_rate"] == pytest.approx(2 / 3)
    # fallback denominator excludes the 0.5 off-scale record: 1 degraded / 2 clean
    assert row["fallback_rate"] == pytest.approx(1 / 2)
    assert row["fallback_unknown"] == 1
    assert row["top_error"] == "ValueError"


def test_build_report_duration_percentiles_with_n():
    sessions = []
    for v in (100.0, 200.0, 300.0, 400.0):
        s = _session(started=_dt(14),
                     metrics=[{"key": "skills.duration_ms", "value_num": v}])
        s["_started_dt"] = rep._parse_dt(s["started_at"])
        sessions.append(s)
    r = rep.build_report(sessions, now=rep._parse_dt(_dt(14)), min_n=1)
    row = r["skills"][0]
    assert row["dur_n"] == 4
    assert row["dur_p50"] == pytest.approx(250.0)
    assert row["dur_p95"] == pytest.approx(385.0)


def _runs(skill, day, n, status="success"):
    out = []
    for _ in range(n):
        s = _session(skill=skill, status=status, started=_dt(day))
        s["_started_dt"] = rep._parse_dt(s["started_at"])
        out.append(s)
    return out


def test_trend_regression_flagged_when_both_windows_meet_min_n():
    # now = max(started_at) = day 12. recent=[day5, day12] (has day12);
    # prior=[day-2, day5) (has day4). 7-day windows.
    prior = _runs("session-start", 4, 10, status="success")          # 100% prior
    recent = (_runs("session-start", 12, 6, status="success")
              + _runs("session-start", 12, 4, status="failure"))     # 60% recent
    r = rep.build_report(prior + recent, recent_days=7, min_n=5, regress_pp=10.0)
    row = {s["skill"]: s for s in r["skills"]}["session-start"]
    assert row["runs_recent"] == 10
    assert row["runs_prior"] == 10
    assert row["success_rate"] == pytest.approx(0.6)
    assert row["success_delta"] == pytest.approx(-0.4)
    assert row["regressed"] is True


def test_trend_not_flagged_when_prior_below_min_n():
    prior = _runs("handoff", 4, 2)                                   # < min_n
    recent = _runs("handoff", 12, 6, status="failure")
    r = rep.build_report(prior + recent, recent_days=7, min_n=5)
    row = {s["skill"]: s for s in r["skills"]}["handoff"]
    assert row["regressed"] is False
    assert row["success_delta"] is None


def test_now_data_anchored_report_nonempty_on_old_sessions():
    old = _runs("session-start", 14, 5)  # July 2026; wall-clock windows would be empty
    r = rep.build_report(old, recent_days=7, min_n=1)   # now defaults to max(started_at)
    assert r["generated_now"] is not None
    assert r["skills"] and r["skills"][0]["runs_recent"] == 5


def test_low_sample_partitioned_and_main_sorted_worst_first():
    sessions = (
        _runs("good", 14, 10, status="success")                      # 100% ok
        + _runs("bad", 14, 6, status="failure") + _runs("bad", 14, 4, status="success")  # 40%
        + _runs("tiny", 14, 2, status="failure")                     # < min_n
    )
    r = rep.build_report(sessions, recent_days=7, min_n=5)
    main = [s["skill"] for s in r["skills"]]
    low = [s["skill"] for s in r["low_sample"]]
    assert "tiny" not in main and "tiny" in low
    assert main[0] == "bad"           # worst success first
    assert main == ["bad", "good"]
