"""The commands an install hint may name: h2t-setup, never a package index.

`h2t-ops` is not on PyPI. A hint that installs the bare name with an extra resolves it
there, and whoever registers the name would get code execution from the hint
(tests/setup/test_extra_hints.py scans the shipped trees for that form). A release
names its own bootstrap (_release.py, written by scripts/release.py); a checkout names
`dev-sync`, the one command that installs from it and records the install.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import h2t_ops
from h2t_ops.setup import _release


def checkout() -> Path | None:
    """The checkout this package runs from (an editable install or `uv run`), if any."""
    root = Path(h2t_ops.__file__).resolve().parents[1]
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    project = data.get("project")
    return root if isinstance(project, dict) and project.get("name") == "h2t-ops" else None


def _setup(mode: str) -> str:
    if checkout() is not None:
        return "h2t-setup dev-sync"
    return f"{_release.BOOTSTRAP_COMMAND or 'h2t-setup'} {mode}"


def repair() -> str:
    """Bring the install back to its release."""
    return _setup("sync")


def add_extra(name: str) -> str:
    """Add an extra to the install: recorded in install.json, kept by every later sync."""
    return f"{_setup('sync')} --extra {name}"
