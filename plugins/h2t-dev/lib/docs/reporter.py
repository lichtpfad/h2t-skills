# plugins/h2t-dev/lib/docs/reporter.py
"""h2t_lifecycle_report/v0.1 envelope builder."""
from __future__ import annotations
import datetime

SCHEMA = "h2t_lifecycle_report/v0.1"
SCHEMA_VERSION = "0.1"


def finding(
    type_: str,
    severity: str,
    path: str,
    message: str,
    safe_fix: str | None = None,
) -> dict:
    """Build a single finding dict. safe_fix omitted when None."""
    result: dict = {
        "type": type_,
        "severity": severity,
        "path": path,
        "message": message,
    }
    if safe_fix is not None:
        result["safe_fix"] = safe_fix
    return result


def build_report(
    *,
    command: str,
    repo_root: str,
    status: str,
    summary: str,
    findings: list[dict],
    safe_next_action: str,
    git_head: str = "",
) -> dict:
    """Build a complete h2t_lifecycle_report/v0.1 envelope."""
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "repo_root": repo_root,
        "status": status,
        "summary": summary,
        "findings": findings,
        "safe_next_action": safe_next_action,
        "evidence": {
            "git_head": git_head,
            "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
    }


def status_from_findings(findings: list[dict]) -> str:
    """Derive status from severity of findings list."""
    if not findings:
        return "ok"
    severities = {f["severity"] for f in findings}
    if severities & {"error", "critical"}:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "ok"
