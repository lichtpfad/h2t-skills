---
title: "Evals telemetry consumer phase1"
status: "draft"
date: "2026-07-14"
milestone: ""
---

# Evals Telemetry Consumer — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `h2t-ops evals report` command that turns ~1330 accumulated local `SkillEval` session JSON files into a per-skill operational-health report (success, fallback, top exception, duration, recent-vs-prior regression, coverage-gap) — closing gate 4 (a real telemetry consumer).

**Architecture:** A pure aggregation core `lib/eval/report.py` (`load_sessions` for I/O, `build_report` pure, `render_human`/`render_md` pure string builders, `catalog_skills` for coverage I/O). The existing `evals` connector (`h2t_ops/connectors/evals/commands.py`) gains a `report` subcommand that wires them together and picks the output format. No plugin copy / parity guard — unlike `session.py`, `report.py` is imported only by the root connector.

**Tech Stack:** Python stdlib only (`json`, `datetime`, `dataclasses`, `math`, `collections`, `pathlib`), `argparse` (connector), pytest. Direct venv paths, no activation.

**Spec:** `docs/superpowers/specs/2026-07-14-evals-telemetry-consumer-phase1.md`

**Conventions for every task below:**
- Test runner: `C:/dev/h2t-skills/.venv/Scripts/pytest`
- Lint (before each commit): `uvx ruff@latest check <changed files>`
- One logical change per commit; commit message `type: desc`.
- Bash: one command per call, no `&&` chaining.

---

## File Structure

- Create `lib/eval/report.py` — aggregation core (all pure except `load_sessions`/`catalog_skills` I/O).
- Create `lib/eval/test_report.py` — unit tests for the core (next to `test_status.py`).
- Modify `h2t_ops/connectors/evals/commands.py` — add `report` subcommand + handler.
- Create `tests/connectors/evals/test_report_cli.py` — connector smoke tests.

Data contract (from `lib/eval/session.py:_write_local`), each session JSON:
```json
{"skill":"session-start","domain":"dev","project":"h2t-ai","status":"success",
 "started_at":"2026-07-14T10:00:00+00:00","ended_at":"...","metrics":[
   {"key":"core.task_success","value_bool":true,"level":"integration"},
   {"key":"core.deflection_rate","value_num":1.0,"level":"business"},
   {"key":"skills.duration_ms","value_num":1234.5,"unit":"ms"},
   {"key":"skills.error_class","value_text":"ValueError"}]}
```

---

## Task 1: LoadStats + timestamp parse + load_sessions

**Files:**
- Create: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.eval.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/eval/report.py
"""Local SkillEval telemetry consumer — phase 1 operational-health report.

Reads ~/.h2t/evals/<skill>/sessions/*.json (written by lib/eval/session.py) and
aggregates per-skill health. Pure core (build_report / renderers); only
load_sessions and catalog_skills touch the filesystem. See
docs/superpowers/specs/2026-07-14-evals-telemetry-consumer-phase1.md.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


@dataclass
class LoadStats:
    root_readable: bool = True
    files_seen: int = 0
    loaded: int = 0
    malformed_skipped: int = 0
    undated_skipped: int = 0


def _parse_dt(raw) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp to a tz-aware UTC datetime, else None."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def load_sessions(root, *, load_since=None):
    """Return (sessions, LoadStats). Never raises for bad data.

    A session is loaded only if the file is valid JSON AND started_at parses to
    a tz-aware UTC datetime. load_since (a datetime) drops sessions strictly
    before it. Sessions carry a parsed "_started_dt" for downstream windowing.
    """
    root = Path(root)
    stats = LoadStats()
    if not root.exists() or not root.is_dir():
        stats.root_readable = False
        return [], stats
    sessions: list[dict] = []
    for path in sorted(root.glob("*/sessions/*.json")):
        stats.files_seen += 1
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stats.malformed_skipped += 1
            continue
        if not isinstance(record, dict):
            stats.malformed_skipped += 1
            continue
        started = _parse_dt(record.get("started_at"))
        if started is None:
            stats.undated_skipped += 1
            continue
        if load_since is not None and started < load_since:
            continue
        record["_started_dt"] = started
        sessions.append(record)
        stats.loaded += 1
    return sessions, stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): load_sessions with typed LoadStats (root/malformed/undated)"
```

---

## Task 2: Typed metric extraction + percentile helpers

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
import pytest


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "metric or percentile" -q`
Expected: FAIL — `AttributeError: module 'lib.eval.report' has no attribute '_metric'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to lib/eval/report.py
def _metric(session: dict, key: str, slot: str):
    """Return session's metric value for key at the given value_* slot, else None.

    None-safe: never coerces a missing value to 0. slot ∈
    {"value_bool","value_num","value_text"}.
    """
    for m in session.get("metrics", []):
        if m.get("key") == key and slot in m:
            return m[slot]
    return None


def _percentile(values, p: float):
    """Linear-interpolation percentile (p in 0..100) over an unsorted list."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    return float(s[lo] + (s[hi] - s[lo]) * (k - lo))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "metric or percentile" -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): typed None-safe metric extraction + linear-interp percentile"
```

---

## Task 3: build_report — per-skill signals over a single window (no trend yet)

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

Aggregation for the recent window only. success from top-level `status`;
fallback from inverted `core.deflection_rate` (0.0 = degraded), off-scale/absent
counted as `fallback_unknown`; top exception from `skills.error_class`; duration
p50/p95 from `skills.duration_ms`. Trend/min-N/coverage come in later tasks.

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
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
```

> Note: tests inject `_started_dt` directly because `build_report` is pure and
> consumes already-loaded sessions; `load_sessions` is what normally attaches it.

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k build_report -q`
Expected: FAIL — `AttributeError: module 'lib.eval.report' has no attribute 'build_report'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to lib/eval/report.py
EXCLUDED_PROXIES = (
    "core.op_type_correct_rate",
    "core.tool_call_success_rate",
    "core.time_to_first_valid_ms",
)


def _window_stats(sessions: list[dict]) -> dict:
    """Aggregate one already-windowed, single-skill list of sessions."""
    runs = len(sessions)
    successes = sum(1 for s in sessions if s.get("status") == "success")
    clean = degraded = unknown = 0
    for s in sessions:
        d = _metric(s, "core.deflection_rate", "value_num")
        if d in (0.0, 1.0):
            clean += 1
            if d == 0.0:
                degraded += 1
        else:
            unknown += 1
    errors = [e for s in sessions if s.get("status") == "failure"
              and (e := _metric(s, "skills.error_class", "value_text")) is not None]
    durations = [d for s in sessions
                 if (d := _metric(s, "skills.duration_ms", "value_num")) is not None]
    return {
        "runs": runs,
        "success_rate": (successes / runs) if runs else None,
        "fallback_rate": (degraded / clean) if clean else None,
        "fallback_unknown": unknown,
        "top_error": Counter(errors).most_common(1)[0][0] if errors else None,
        "dur_n": len(durations),
        "dur_p50": _percentile(durations, 50),
        "dur_p95": _percentile(durations, 95),
        "domains": sorted({s.get("domain") for s in sessions if s.get("domain")}),
        "projects": sorted({s.get("project") for s in sessions if s.get("project")}),
    }


def _row_from(skill: str, ws: dict) -> dict:
    row = {"skill": skill, "low_sample": False, "regressed": False,
           "success_delta": None, "runs_recent": ws["runs"], "runs_prior": 0}
    row.update({k: ws[k] for k in (
        "success_rate", "fallback_rate", "fallback_unknown", "top_error",
        "dur_n", "dur_p50", "dur_p95", "domains", "projects")})
    return row


def _load_dict(load_stats):
    if load_stats is None:
        return None
    return {"root_readable": load_stats.root_readable,
            "files_seen": load_stats.files_seen, "loaded": load_stats.loaded,
            "malformed_skipped": load_stats.malformed_skipped,
            "undated_skipped": load_stats.undated_skipped}


def build_report(sessions, *, now=None, recent_days=7, min_n=5, regress_pp=10.0,
                 skill_filter=None, project_filter=None, known_skills=None,
                 load_stats=None) -> dict:
    """Aggregate loaded sessions into a per-skill health report (pure)."""
    dated = [s for s in sessions if s.get("_started_dt") is not None]
    if now is None:
        now = max((s["_started_dt"] for s in dated), default=None)

    filtered = dated
    if skill_filter:
        filtered = [s for s in filtered if s.get("skill") == skill_filter]
    if project_filter:
        filtered = [s for s in filtered if s.get("project") == project_filter]

    rows = []
    if now is not None:
        recent_lo = now - timedelta(days=recent_days)
        recent_by: dict[str, list[dict]] = {}
        for s in filtered:
            if recent_lo <= s["_started_dt"] <= now:
                recent_by.setdefault(s["skill"], []).append(s)
        for skill in sorted(recent_by):
            rows.append(_row_from(skill, _window_stats(recent_by[skill])))

    return {
        "generated_now": now.isoformat() if now else None,
        "recent_days": recent_days,
        "skills": rows,
        "low_sample": [],
        "coverage_gap": [],
        "coverage_unmatched": [],
        "excluded_proxies": list(EXCLUDED_PROXIES),
        "load": _load_dict(load_stats),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k build_report -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): build_report single-window per-skill signals"
```

---

## Task 4: Trend / regression + prior window + data-anchored now

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "trend or now" -q`
Expected: FAIL — `runs_prior` always 0; `regressed` never True.

- [ ] **Step 3: Write minimal implementation**

Replace the `rows = []` … recent-only block inside `build_report` (from Task 3)
with prior-window computation:

```python
    rows = []
    if now is not None:
        recent_lo = now - timedelta(days=recent_days)
        prior_lo = now - timedelta(days=2 * recent_days)
        recent_by: dict[str, list[dict]] = {}
        prior_by: dict[str, list[dict]] = {}
        for s in filtered:
            t = s["_started_dt"]
            if recent_lo <= t <= now:
                recent_by.setdefault(s["skill"], []).append(s)
            elif prior_lo <= t < recent_lo:
                prior_by.setdefault(s["skill"], []).append(s)
        for skill in sorted(set(recent_by) | set(prior_by)):
            ws = _window_stats(recent_by.get(skill, []))
            ps = _window_stats(prior_by.get(skill, []))
            row = _row_from(skill, ws)
            row["runs_prior"] = ps["runs"]
            if (ws["runs"] >= min_n and ps["runs"] >= min_n
                    and ws["success_rate"] is not None
                    and ps["success_rate"] is not None):
                row["success_delta"] = ws["success_rate"] - ps["success_rate"]
                row["regressed"] = row["success_delta"] <= -(regress_pp / 100.0)
            rows.append(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "trend or now" -q`
Expected: PASS (3 passed). Re-run whole file → all green.

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): recent-vs-prior trend + regression flag, data-anchored now"
```

---

## Task 5: min-N low-sample partitioning + worst-first sort

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k low_sample -q`
Expected: FAIL — `tiny` present in `skills`, `low_sample` empty.

- [ ] **Step 3: Write minimal implementation**

At the end of `build_report`, after the `rows` loop and before the return,
partition + sort, then use `rated`/`low` in the return dict:

```python
    low = [r for r in rows if r["runs_recent"] < min_n]
    rated = [r for r in rows if r["runs_recent"] >= min_n]
    for r in low:
        r["low_sample"] = True

    def _sort_key(r):
        # worst-first: regressed, then low success, then high fallback
        return (
            0 if r["regressed"] else 1,
            r["success_rate"] if r["success_rate"] is not None else 1.0,
            -(r["fallback_rate"] if r["fallback_rate"] is not None else 0.0),
        )
    rated.sort(key=_sort_key)
    low.sort(key=lambda r: r["skill"])
```

Then in the returned dict set `"skills": rated` and `"low_sample": low`
(replacing `"skills": rows` and `"low_sample": []`).

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k low_sample -q`
Expected: PASS (1 passed). Re-run whole file → green.

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): min-N low-sample partition + worst-first sort"
```

---

## Task 6: Coverage-gap (catalog enumeration + gap computation)

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
def test_catalog_skills_enumerates_skill_md_dirs(tmp_path):
    (tmp_path / "h2t-ops" / "skills" / "research").mkdir(parents=True)
    (tmp_path / "h2t-ops" / "skills" / "research" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "h2t-core" / "skills" / "handoff").mkdir(parents=True)
    (tmp_path / "h2t-core" / "skills" / "handoff" / "SKILL.md").write_text("x", encoding="utf-8")
    assert rep.catalog_skills(tmp_path) == {"research", "handoff"}


def test_coverage_gap_is_global_and_filter_invariant():
    sessions = _runs("handoff", 14, 3) + _runs("handoff", 14, 1, status="failure")
    known = {"handoff", "research", "connectors"}
    r_all = rep.build_report(sessions, min_n=1, known_skills=known)
    r_filtered = rep.build_report(sessions, min_n=1, known_skills=known,
                                  project_filter="does-not-exist")
    assert r_all["coverage_gap"] == ["connectors", "research"]      # sorted, minus handoff
    assert r_filtered["coverage_gap"] == ["connectors", "research"] # filter-invariant
    assert r_all["coverage_unmatched"] == []


def test_coverage_unmatched_flags_store_dirs_without_catalog_entry():
    sessions = _runs("dev-session-start", 14, 3)
    r = rep.build_report(sessions, min_n=1, known_skills={"session-start"})
    assert r["coverage_unmatched"] == ["dev-session-start"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "catalog or coverage" -q`
Expected: FAIL — no `catalog_skills`; `coverage_gap` always `[]`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to lib/eval/report.py
def catalog_skills(plugins_root) -> set:
    """Skill ids from plugins/*/skills/*/SKILL.md parent dir names. Empty on I/O error."""
    root = Path(plugins_root)
    out: set[str] = set()
    try:
        for md in root.glob("*/skills/*/SKILL.md"):
            out.add(md.parent.name)
    except OSError:
        pass
    return out
```

In `build_report`, compute coverage from the **unfiltered dated** sessions
(before the `now`/filter logic uses `filtered`) and wire into the return dict
(replacing the `"coverage_gap": []` / `"coverage_unmatched": []` placeholders):

```python
    instrumented = {s.get("skill") for s in dated if s.get("skill")}
    known = set(known_skills or ())
    coverage_gap = sorted(known - instrumented)
    coverage_unmatched = sorted(instrumented - known) if known else []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k "catalog or coverage" -q`
Expected: PASS (3 passed). Re-run whole file → green.

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): coverage-gap catalog enumeration + filter-invariant gap"
```

---

## Task 7: Renderers — render_human / render_md

**Files:**
- Modify: `lib/eval/report.py`
- Test: `lib/eval/test_report.py`

Pure string builders. Both surface header (window, load counts, root-unreadable
warning), the worst-first table, low-sample section, coverage-gap, and the
excluded-proxy footnote. `render_md` uses markdown tables; `render_human` plain text.

- [ ] **Step 1: Write the failing test**

```python
# append to lib/eval/test_report.py
def test_render_human_surfaces_states_and_rows():
    sessions = _runs("bad", 14, 6, status="failure") + _runs("bad", 14, 4, status="success")
    r = rep.build_report(sessions, min_n=5, known_skills={"bad", "research"})
    r["load"] = {"root_readable": True, "files_seen": 11, "loaded": 10,
                 "malformed_skipped": 1, "undated_skipped": 0}
    text = rep.render_human(r)
    assert "bad" in text
    assert "malformed" in text.lower()          # data-loss surfaced
    assert "research" in text                    # coverage-gap listed
    assert any(p in text for p in rep.EXCLUDED_PROXIES)   # proxy footnote


def test_render_human_root_unreadable_distinct_from_empty():
    r = rep.build_report([], known_skills=set())
    r["load"] = {"root_readable": False, "files_seen": 0, "loaded": 0,
                 "malformed_skipped": 0, "undated_skipped": 0}
    assert "unreadable" in rep.render_human(r).lower()


def test_render_md_is_markdown_table():
    sessions = _runs("bad", 14, 6, status="failure")
    r = rep.build_report(sessions, min_n=1)
    md = rep.render_md(r)
    assert "| skill |" in md.lower()
    assert "---" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k render -q`
Expected: FAIL — no `render_human` / `render_md`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to lib/eval/report.py
def _pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def _dur(row):
    if not row["dur_n"]:
        return "—"
    p95 = "" if row["dur_p95"] is None or row["dur_n"] < 5 else f"/{row['dur_p95']:.0f}"
    return f"{row['dur_p50']:.0f}{p95} (n={row['dur_n']})"


def _delta(row):
    if row["success_delta"] is None:
        return "·"
    arrow = "▼" if row["regressed"] else ("▲" if row["success_delta"] > 0 else "flat")
    return f"{arrow} {row['success_delta'] * 100:+.0f}pp"


def _header_lines(report) -> list:
    load = report.get("load") or {}
    lines = ["Instrumented-session health"]
    if load.get("root_readable") is False:
        lines.append("⚠ telemetry root unreadable — no data read")
    lines.append(f"window: recent {report['recent_days']}d vs prior "
                 f"{report['recent_days']}d  (now={report['generated_now']})")
    warn = ""
    if load.get("malformed_skipped"):
        warn += f"  ⚠ malformed={load['malformed_skipped']}"
    if load.get("undated_skipped"):
        warn += f"  ⚠ undated={load['undated_skipped']}"
    lines.append(f"loaded: {load.get('loaded', 0)}/{load.get('files_seen', 0)}{warn}")
    return lines


def _footer_lines(report) -> list:
    lines = []
    if report["low_sample"]:
        lines.append("")
        lines.append("low-sample (< min_n, not ranked): "
                     + ", ".join(f"{r['skill']}({r['runs_recent']})"
                                 for r in report["low_sample"]))
    if report["coverage_gap"]:
        lines.append("")
        lines.append("coverage-gap (instrumented: no) → instrument next: "
                     + ", ".join(report["coverage_gap"]))
    if report["coverage_unmatched"]:
        lines.append("store dirs without a catalog match: "
                     + ", ".join(report["coverage_unmatched"]))
    lines.append("")
    lines.append("excluded proxies (not signal): " + ", ".join(report["excluded_proxies"]))
    return lines


def render_human(report) -> str:
    lines = _header_lines(report)
    lines.append("")
    lines.append(f"{'skill':22} {'runs':>9} {'success':>8} {'trend':>10} "
                 f"{'fallback':>8} {'top-exc':>16} {'dur p50/p95':>16}")
    for r in report["skills"]:
        runs = f"{r['runs_recent']}/{r['runs_prior']}"
        lines.append(f"{r['skill']:22} {runs:>9} {_pct(r['success_rate']):>8} "
                     f"{_delta(r):>10} {_pct(r['fallback_rate']):>8} "
                     f"{(r['top_error'] or '—'):>16} {_dur(r):>16}")
    return "\n".join(lines + _footer_lines(report))


def render_md(report) -> str:
    lines = list(_header_lines(report))
    lines.append("")
    lines.append("| skill | runs (r/p) | success | trend | fallback | top-exc | dur p50/p95 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in report["skills"]:
        lines.append(f"| {r['skill']} | {r['runs_recent']}/{r['runs_prior']} | "
                     f"{_pct(r['success_rate'])} | {_delta(r)} | "
                     f"{_pct(r['fallback_rate'])} | {r['top_error'] or '—'} | {_dur(r)} |")
    return "\n".join(lines + _footer_lines(report))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/eval/test_report.py -k render -q`
Expected: PASS (3 passed). Re-run whole file → green.

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py
git add lib/eval/report.py lib/eval/test_report.py
git commit -m "feat(eval): human + markdown report renderers"
```

---

## Task 8: Connector wiring — `h2t-ops evals report`

**Files:**
- Modify: `h2t_ops/connectors/evals/commands.py`
- Test: `tests/connectors/evals/test_report_cli.py`

The handler resolves the store root (`H2T_EVALS_ROOT` override, else
`~/.h2t/evals`) + plugins root (I/O), calls `load_sessions` → `build_report`,
then returns a **dict** for `--json` (emit JSON-envelopes it) or a **rendered
string** for human/`--md`. `--json`/`--md` are a mutually exclusive argparse
group (conflict → SystemExit 2, mapped to exit 2 by `_run_connector`).

- [ ] **Step 1: Write the failing test**

```python
# tests/connectors/evals/test_report_cli.py
from pathlib import Path

from h2t_ops.cli import dispatch


def _seed(root: Path):
    d = root / "session-start" / "sessions"
    d.mkdir(parents=True)
    (d / "a.json").write_text(
        '{"skill":"session-start","domain":"dev","project":"p","status":"success",'
        '"started_at":"2026-07-14T10:00:00+00:00","ended_at":"2026-07-14T10:00:01+00:00",'
        '"metrics":[{"key":"core.deflection_rate","value_num":1.0}]}',
        encoding="utf-8")


def test_report_json_returns_envelope(tmp_path, capsys, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--json", "--min-n", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"ok": true' in out
    assert '"provider": "evals"' in out
    assert "session-start" in out


def test_report_human_renders_table(tmp_path, capsys, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--min-n", "1"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Instrumented-session health" in out
    assert "session-start" in out


def test_report_json_and_md_mutually_exclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path))
    code = dispatch(["evals", "report", "--json", "--md"])
    assert code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/evals/test_report_cli.py -q`
Expected: FAIL — `report` subcommand unknown.

- [ ] **Step 3: Write minimal implementation** (full new `commands.py`)

```python
# h2t_ops/connectors/evals/commands.py
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any


def _cmd_status(ns: Any) -> dict:
    from lib.eval.status import get_status

    return get_status()


def _evals_root() -> Path:
    override = os.environ.get("H2T_EVALS_ROOT")
    return Path(override) if override else Path.home() / ".h2t" / "evals"


def _plugins_root() -> Path:
    # commands.py → connectors → h2t_ops → repo root → plugins
    return Path(__file__).resolve().parents[3] / "plugins"


def _parse_since_days(raw) -> Any:
    if not raw:
        return None
    raw = str(raw).strip().lower()
    unit = raw[-1] if raw and raw[-1] in "dwhm" else "d"
    num = raw[:-1] if raw and raw[-1] in "dwhm" else raw
    try:
        val = int(num)
    except ValueError:
        return None
    return {"h": max(1, val // 24), "d": val, "w": val * 7, "m": val * 30}.get(unit, val)


def _cmd_report(ns: Any):
    from lib.eval.report import (build_report, catalog_skills, load_sessions,
                                 render_human, render_md)

    recent_days = getattr(ns, "recent_days", 7)
    since_days = _parse_since_days(getattr(ns, "since", None))
    sessions, stats = load_sessions(_evals_root())
    if since_days is not None:
        anchor = max((s["_started_dt"] for s in sessions if s.get("_started_dt")),
                     default=None)
        if anchor is not None:
            load_since = anchor - timedelta(days=max(since_days, 2 * recent_days))
            sessions = [s for s in sessions if s["_started_dt"] >= load_since]

    report = build_report(
        sessions,
        recent_days=recent_days,
        min_n=getattr(ns, "min_n", 5),
        regress_pp=getattr(ns, "regress_pp", 10.0),
        skill_filter=getattr(ns, "skill", None),
        project_filter=getattr(ns, "project", None),
        known_skills=catalog_skills(_plugins_root()),
        load_stats=stats,
    )
    if getattr(ns, "as_json", False):
        return report
    if getattr(ns, "fmt", "human") == "md":
        return render_md(report)
    return render_human(report)


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("evals", help="Eval telemetry mode/status (read-only)")
    cmds = p.add_subparsers(dest="command")

    status = cmds.add_parser("status", help="Show resolved eval mode and availability")
    status.add_argument("--json", action="store_true", dest="as_json")
    status.set_defaults(_handler=_cmd_status)

    report = cmds.add_parser("report", help="Per-skill operational-health report (local)")
    report.add_argument("--since", default=None, help="Load horizon, e.g. 30d (default: all)")
    report.add_argument("--skill", default=None, help="Filter health rows to one skill")
    report.add_argument("--project", default=None, help="Filter health rows to one project")
    report.add_argument("--recent-days", type=int, default=7, dest="recent_days")
    report.add_argument("--min-n", type=int, default=5, dest="min_n")
    report.add_argument("--regress-pp", type=float, default=10.0, dest="regress_pp")
    fmt = report.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", dest="as_json")
    fmt.add_argument("--md", action="store_const", const="md", dest="fmt")
    report.set_defaults(_handler=_cmd_report, fmt="human")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/evals/test_report_cli.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Lint + commit**

```bash
uvx ruff@latest check h2t_ops/connectors/evals/commands.py tests/connectors/evals/test_report_cli.py
git add h2t_ops/connectors/evals/commands.py tests/connectors/evals/test_report_cli.py
git commit -m "feat(evals): h2t-ops evals report subcommand (json/md/human)"
```

---

## Task 9: Full-suite gate + audit pointer

**Files:**
- Modify: `docs/reports/2026-07-12-skill-telemetry-audit.md`

- [ ] **Step 1: Run the full CI-scoped suite**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest lib/ tests/core/ tests/connectors/ -q`
Expected: PASS — all green, including `lib/eval/test_report.py` and `tests/connectors/evals/test_report_cli.py`.

- [ ] **Step 2: Ruff over all changed paths**

Run: `uvx ruff@latest check lib/eval/report.py lib/eval/test_report.py h2t_ops/connectors/evals/commands.py tests/connectors/evals/test_report_cli.py`
Expected: `All checks passed!`

- [ ] **Step 3: Manual smoke on the real store**

Run: `C:/dev/h2t-skills/.venv/Scripts/python -m h2t_ops.cli evals report --min-n 5`
Expected: a table over the real `~/.h2t/evals` (session-start / handoff / dev-session-start / creative-thinking), a coverage-gap listing uninstrumented skills (research/connectors/docs), and the proxy footnote. Sanity-check the numbers are plausible.

- [ ] **Step 4: Add a pointer in the audit report**

In `docs/reports/2026-07-12-skill-telemetry-audit.md` §7, add:

```markdown
- **Gate-4 consumer (phase 1):** `h2t-ops evals report` — local per-skill health
  (success/fallback/error/duration + regression + coverage-gap). Spec/plan:
  `docs/superpowers/{specs,plans}/2026-07-14-evals-telemetry-consumer-phase1.md`.
```

- [ ] **Step 5: Commit**

```bash
git add docs/reports/2026-07-12-skill-telemetry-audit.md
git commit -m "docs: point telemetry audit at the gate-4 report consumer"
```

---

## Self-Review notes (author)

- **Spec coverage:** load-states (T1), typed extraction + percentile (T2),
  success/fallback/error/duration (T3), trend + data-anchored now (T4), min-N
  (T5), coverage-gap filter-invariant (T6), renderers + surfaced states + proxy
  footnote (T7), CLI + mutual-exclusion + envelope (T8), full-suite + smoke (T9).
  Every spec acceptance box maps to a task.
- **Type consistency:** report-row keys (`runs_recent`, `runs_prior`,
  `success_rate`, `success_delta`, `regressed`, `fallback_rate`,
  `fallback_unknown`, `top_error`, `dur_n/p50/p95`, `domains`, `projects`,
  `low_sample`) are defined in `_row_from` (T3) and consumed unchanged by trend
  (T4), sort (T5), and renderers (T7). `build_report` signature is fixed in T3
  and only gains behavior (not new params) afterward.
- **Deferred (not in this plan, per spec):** cost, quality/judge, central
  adapter, dev-overview hook/headline, skill_graph lesson linkage.
- **Executor note:** the `evals` connector is a plain `h2t_ops` package
  subcommand (not a versioned plugin component) → **no `bump_plugin.py`**
  expected. Confirm before assuming a bump is needed.
