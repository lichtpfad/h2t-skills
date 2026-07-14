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


EXCLUDED_PROXIES = (
    "core.op_type_correct_rate",
    "core.tool_call_success_rate",
    "core.time_to_first_valid_ms",
)


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

    instrumented = {s.get("skill") for s in dated if s.get("skill")}
    known = set(known_skills or ())
    coverage_gap = sorted(known - instrumented)
    coverage_unmatched = sorted(instrumented - known) if known else []

    filtered = dated
    if skill_filter:
        filtered = [s for s in filtered if s.get("skill") == skill_filter]
    if project_filter:
        filtered = [s for s in filtered if s.get("project") == project_filter]

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

    return {
        "generated_now": now.isoformat() if now else None,
        "recent_days": recent_days,
        "skills": rated,
        "low_sample": low,
        "coverage_gap": coverage_gap,
        "coverage_unmatched": coverage_unmatched,
        "excluded_proxies": list(EXCLUDED_PROXIES),
        "load": _load_dict(load_stats),
    }
