# plugins/h2t-dev/lib/docs/fix_plan.py
"""Converts doc findings into h2t_docs_fix_plan/v0.1 action list."""
from __future__ import annotations
import datetime
import hashlib
import re

SCHEMA = "h2t_docs_fix_plan/v0.1"


def _action_id(action_type: str, path: str, target_path: str | None = None) -> str:
    """Deterministic stable id from (type, path, target_path)."""
    key = f"{action_type}:{path}:{target_path or ''}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"docs-action:{h}"


def _extract_rename_target(safe_fix: str) -> str | None:
    """Extract target filename from safe_fix string like "rename to 'foo.md'"."""
    m = re.search(r"rename to '([^']+)'", safe_fix or "")
    return m.group(1) if m else None


def _findings_to_actions(findings: list[dict]) -> list[dict]:
    actions = []
    for f in findings:
        t = f.get("type", "")
        path = f.get("path", "")
        msg = f.get("message", "")

        if t == "orphan":
            actions.append({
                "action_id": _action_id("add_to_index", path),
                "type": "add_to_index",
                "status": "proposed",
                "risk": "review",
                "path": path,
                "target_path": None,
                "reason": msg,
                "requires_confirmation": True,
            })

        elif t == "naming":
            target = _extract_rename_target(f.get("safe_fix", ""))
            actions.append({
                "action_id": _action_id("rename_file", path, target),
                "type": "rename_file",
                "status": "proposed",
                "risk": "review",
                "path": path,
                "target_path": target,
                "reason": msg,
                "requires_confirmation": True,
            })

        elif t == "structure":
            if "missing dir:" in msg:
                dir_name = msg.split("missing dir:")[-1].strip().rstrip("/")
                actions.append({
                    "action_id": _action_id("create_dir", dir_name),
                    "type": "create_dir",
                    "status": "proposed",
                    "risk": "safe",
                    "path": dir_name,
                    "target_path": None,
                    "reason": msg,
                    "requires_confirmation": False,
                })

        elif t == "frontmatter":
            actions.append({
                "action_id": _action_id("add_frontmatter", path),
                "type": "add_frontmatter",
                "status": "proposed",
                "risk": "safe",
                "path": path,
                "target_path": None,
                "reason": msg,
                "requires_confirmation": False,
            })

    return actions


def build_fix_plan(
    *,
    repo_root: str,
    findings: list[dict],
    source_report_id: str = "",
) -> dict:
    """Build h2t_docs_fix_plan/v0.1 from a findings list."""
    actions = _findings_to_actions(findings)
    id_key = repo_root + "|" + "|".join(
        sorted(a["action_id"] for a in actions)
    )
    plan_id = "docs-fix-plan:" + hashlib.sha256(id_key.encode()).hexdigest()[:16]
    return {
        "schema": SCHEMA,
        "schema_version": "0.1",
        "plan_id": plan_id,
        "repo_root": repo_root,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_report_id": source_report_id,
        "actions": actions,
    }
