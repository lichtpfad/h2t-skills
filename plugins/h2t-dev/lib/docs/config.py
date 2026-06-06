"""Per-repo docs-lint configuration discovery.

Search order:
  1. .h2t/docs-lint.yaml   — project-level (new)
  2. .claude/rules/docs-lint.yaml  — legacy location
"""
from __future__ import annotations
import datetime
from pathlib import Path
from typing import Any

CONFIG_PATHS = [".h2t/docs-lint.yaml", ".claude/rules/docs-lint.yaml"]
_STALE_DAYS = 90

_DEFAULTS: dict[str, Any] = {
    "docs_root": "docs",
    "required_dirs": [
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        "docs/adr",
        "docs/reports",
    ],
    "exceptions": [],
    "exclude_dirs": [],
    "naming_exceptions": [],
    "template": None,       # internal key; set from 'project_type' or 'template'
    "custom_root_dirs": [],
    "project_checks": False,
    "deliverables_dir": "deliverables",
    "_config_source": None,
}


def load_config(repo_root: Path) -> dict[str, Any]:
    """Load config from first found path; fall back to defaults."""
    for config_path in CONFIG_PATHS:
        cfg_path = repo_root / config_path
        if not cfg_path.exists():
            continue
        text = cfg_path.read_text(encoding="utf-8", errors="replace")
        try:
            import yaml
            data = yaml.safe_load(text) or {}
        except ImportError:
            return dict(_DEFAULTS)
        merged = dict(_DEFAULTS)
        for k, v in data.items():
            if v is not None:
                merged[k] = v
        # Normalize: 'project_type' (new) takes precedence over 'template' (legacy)
        if data.get("project_type"):
            merged["template"] = data["project_type"]
        elif data.get("template"):
            merged["template"] = data["template"]
        merged["_config_source"] = config_path
        return merged
    return dict(_DEFAULTS)


def get_exception_warnings(exceptions: list, repo_root: Path) -> list[dict]:
    """Return warning findings for stale or orphan dict-exceptions.

    String exceptions (legacy format like 'eval') are silently skipped.
    """
    from docs.reporter import finding
    warnings = []
    today = datetime.date.today()
    for exc in exceptions:
        if not isinstance(exc, dict):
            continue  # legacy string format — no warnings
        path = exc.get("path", "")
        reviewed_str = exc.get("reviewed")
        full_path = repo_root / path.rstrip("/")
        if not full_path.exists():
            warnings.append(finding(
                "structure", "important", path,
                f"orphan exception in docs-lint config: '{path}' no longer exists — remove from config",
            ))
            continue
        if reviewed_str:
            try:
                reviewed = datetime.date.fromisoformat(str(reviewed_str))
                age = (today - reviewed).days
                if age > _STALE_DAYS:
                    warnings.append(finding(
                        "structure", "low", path,
                        f"stale exception: '{path}' last reviewed {age}d ago (>{_STALE_DAYS}d) — re-confirm or remove",
                    ))
            except (ValueError, TypeError):
                pass
    return warnings
