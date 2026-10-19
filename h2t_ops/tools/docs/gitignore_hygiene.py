"""Gitignore hygiene checks: temp files at repo root not effectively git-ignored."""
from __future__ import annotations

import subprocess
from pathlib import Path

from h2t_ops.core import store

from .root_structure import TEMP_PATTERNS


def _is_ignored_by_git(rp: Path, filename: str) -> bool:
    """Return True if git considers `filename` (relative to rp) to be ignored."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", filename],
            cwd=str(rp), capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_gitignore_hygiene(rp: Path) -> list[dict]:
    """Return a single consolidated finding if temp-pattern files exist at root
    but are not effectively ignored by git."""
    from .reporter import finding as make_finding

    missing: list[str] = []
    for pat in TEMP_PATTERNS:
        matches = list(rp.glob(pat))
        if not matches:
            continue
        if any(not _is_ignored_by_git(rp, m.name) for m in matches):
            missing.append(pat)

    if not missing:
        return []

    pattern_list = ", ".join(f'"{p}"' for p in missing)
    return [make_finding(
        "gitignore_hygiene", "info", ".gitignore",
        f"{len(missing)} temp pattern(s) not covered by .gitignore: {pattern_list} — run fix-safe to add",
    )]


def fix_gitignore_hygiene(rp: Path) -> list[str]:
    """Append missing temp patterns to .gitignore. Atomic write (store.repo replace)."""
    missing: list[str] = []
    for pat in TEMP_PATTERNS:
        matches = list(rp.glob(pat))
        if not matches:
            continue
        if any(not _is_ignored_by_git(rp, m.name) for m in matches):
            missing.append(pat)

    if not missing:
        return []

    gi = rp / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += "\n# docs-lint: temp files\n" + "\n".join(missing) + "\n"

    store.repo(rp, "h2t-docs-lint fix-safe").replace(".gitignore", text)   # only fix-safe runs this
    return [f"added to .gitignore: {p}" for p in missing]
