"""Per-repo docs-lint configuration discovery from .claude/rules/docs-lint.yaml."""
from __future__ import annotations
from pathlib import Path
from typing import Any

CONFIG_PATH = ".claude/rules/docs-lint.yaml"

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
    "template": None,
}


def load_config(repo_root: Path) -> dict[str, Any]:
    """Load config from .claude/rules/docs-lint.yaml; fall back to defaults."""
    cfg_path = repo_root / CONFIG_PATH
    if not cfg_path.exists():
        return dict(_DEFAULTS)
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
    return merged
