"""Local SkillEval telemetry consumer — phase 1 operational-health report.

Reads ~/.h2t/evals/<skill>/sessions/*.json (written by lib/eval/session.py) and
aggregates per-skill health. Pure core (build_report / renderers); only
load_sessions and catalog_skills touch the filesystem. See
docs/superpowers/specs/2026-07-14-evals-telemetry-consumer-phase1.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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
