"""Eval tracking for gather framework.

Dual-write: local JSON files + centralized h2t-evals service (when enabled).

Local:   ~/.h2t/evals/{skill}/sessions/{prefix}-{date}-{seq}.json
Central: h2t-evals SDK → service at H2T_EVALS_SERVICE_URL (with spool fallback)

Enable central: set H2T_EVALS_ENABLED=1 in environment.
"""

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path


def record_eval(
    skill_name: str,
    metrics: dict,
    evals_root: str | None = None,
    plugin_version: str = "",
) -> str | None:
    """Record eval metrics for a skill invocation.

    Writes to local JSON file always. If H2T_EVALS_ENABLED=1,
    also sends to centralized h2t-evals service via SDK.

    Args:
        skill_name: Skill identifier (e.g., "dev-session-start")
        metrics: Dict of metrics to record
        evals_root: Override eval storage root (default: ~/.h2t/evals)
        plugin_version: Plugin version for source tag (e.g., "2.12.1")

    Returns:
        Path to created local eval file, or None on failure.
    """
    # --- Local write (always) ---
    filepath = _write_local(skill_name, metrics, evals_root)

    # --- Central write (optional) ---
    if os.environ.get("H2T_EVALS_ENABLED") == "1":
        _send_central(skill_name, metrics, plugin_version)

    return filepath


def _write_local(
    skill_name: str, metrics: dict, evals_root: str | None = None,
) -> str | None:
    """Write eval record to local JSON file."""
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


def _send_central(skill_name: str, metrics: dict, plugin_version: str = "") -> None:
    """Send eval session to centralized h2t-evals service. Silent on failure."""
    try:
        from h2t_evals.sdk import EvalClient, EvalSession
    except ImportError:
        return  # SDK not installed — skip silently

    service_url = os.environ.get("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088")
    token = os.environ.get("H2T_EVALS_TOKEN", "")
    spool = os.environ.get(
        "H2T_EVALS_SPOOL",
        str(Path.home() / ".h2t" / "evals" / ".h2t_evals_spool.db"),
    )

    try:
        client = EvalClient(service_url=service_url, token=token, spool_path=spool)

        source = f"{skill_name}:v{plugin_version}" if plugin_version else skill_name
        eval_set = _skill_eval_set(skill_name)

        s = EvalSession(
            client=client,
            repo="claude-agent-skills",
            framework="h2t-skill",
            source=source,
            eval_set_id=eval_set,
            host=platform.node().lower().split(".")[0],
            run_env=os.environ.get("H2T_EVALS_RUN_ENV", "agent"),
        )
        s.start()

        # Core metrics
        duration = metrics.get("duration_ms", 0)
        sources_failed = len(metrics.get("sources_failed", []))
        task_success = sources_failed == 0

        s.metric("core.task_success", level="integration", value_bool=task_success)
        s.metric("core.time_to_first_valid_ms", level="integration", value_num=float(duration), unit="ms")
        s.metric("core.tool_call_success_rate", level="unit", value_num=1.0 if task_success else 0.0)
        s.metric("core.op_type_correct_rate", level="unit", value_num=1.0)
        s.metric("core.deflection_rate", level="business", value_num=1.0 if task_success else 0.0)

        # Custom metrics
        s.metric("claude-agent-skills.duration_ms", level="integration", value_num=float(duration), unit="ms")
        if "context_tokens_estimate" in metrics:
            s.metric("claude-agent-skills.context_tokens_estimate", level="unit", value_num=float(metrics["context_tokens_estimate"]))
        if sources_failed:
            s.metric("claude-agent-skills.sources_failed_count", level="unit", value_num=float(sources_failed))

        s.finish(status="success" if task_success else "failure")
        client.flush(limit=200)
    except Exception:
        pass  # Never crash skill for eval failure


def _skill_eval_set(skill_name: str) -> str:
    """Map skill name to eval_set_id."""
    gather_skills = {"dev-session-start", "handoff", "init-project"}
    integration_skills = {
        "gmail", "notion", "calendar", "drive", "telegram",
        "youtube-transcript", "process-transcripts", "convert-meeting-transcript",
        "daily-brief",
    }

    if skill_name in gather_skills:
        return "skills-gather-baseline-v1"
    if skill_name in integration_skills:
        return "skills-integration-baseline-v1"
    return "skills-prompt-baseline-v1"


def estimate_tokens(data: dict) -> int:
    """Rough token estimate for a dict (JSON serialized length / 4)."""
    return len(json.dumps(data, ensure_ascii=False)) // 4
