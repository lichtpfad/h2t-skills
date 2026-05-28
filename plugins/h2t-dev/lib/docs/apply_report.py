# plugins/h2t-dev/lib/docs/apply_report.py
"""Builds h2t_docs_fix_apply_report/v0.1 — audit trail of a fix run."""
from __future__ import annotations
import datetime
import hashlib
from pathlib import Path

APPLY_SCHEMA = "h2t_docs_fix_apply_report/v0.1"


def action_result(
    action_id: str,
    status: str,      # applied | skipped | failed | waived
    message: str = "",
    before_hash: str = "",
    after_hash: str = "",
) -> dict:
    return {
        "action_id": action_id,
        "status": status,
        "message": message,
        "before_hash": before_hash,
        "after_hash": after_hash,
    }


def file_hash(path: "Path | str") -> str:
    """SHA256 of file content (first 16 hex chars), empty string if absent."""
    p = Path(path)
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build_apply_report(
    *,
    plan_id: str,
    run_id: str,
    actions: list[dict],
) -> dict:
    return {
        "schema": APPLY_SCHEMA,
        "schema_version": "0.1",
        "plan_id": plan_id,
        "run_id": run_id,
        "applied_at": datetime.datetime.utcnow().isoformat() + "Z",
        "actions": actions,
    }
