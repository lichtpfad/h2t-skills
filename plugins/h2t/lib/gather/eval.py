"""Eval tracking for gather framework.

Records metrics per skill invocation to ~/.h2t/evals/{skill}/sessions/.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def record_eval(
    skill_name: str,
    metrics: dict,
    evals_root: str | None = None,
) -> str | None:
    """Record eval metrics for a skill invocation.

    Args:
        skill_name: Skill identifier (e.g., "dev-session-start")
        metrics: Dict of metrics to record
        evals_root: Override eval storage root (default: ~/.h2t/evals)

    Returns:
        Path to created eval file, or None on failure.
    """
    root = Path(evals_root) if evals_root else Path.home() / ".h2t" / "evals"
    sessions_dir = root / skill_name / "sessions"

    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    existing = list(sessions_dir.glob(f"{skill_name[:2]}-{date_str}-*.json"))
    seq = len(existing) + 1

    prefix = skill_name[:2]
    filename = f"{prefix}-{date_str}-{seq:03d}.json"
    filepath = sessions_dir / filename

    record = {
        "session_id": f"{prefix}-{date_str}-{seq:03d}",
        "skill": skill_name,
        "timestamp": now.isoformat(),
        "metrics": metrics,
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        return str(filepath)
    except OSError:
        return None


def estimate_tokens(data: dict) -> int:
    """Rough token estimate for a dict (JSON serialized length / 4)."""
    return len(json.dumps(data, ensure_ascii=False)) // 4
