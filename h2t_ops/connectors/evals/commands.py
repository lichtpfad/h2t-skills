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
