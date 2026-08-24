# plugins/h2t-dev/lib/docs/misplaced_files.py
"""Detect misplaced deliverable files (html/pdf/pptx) inside docs/."""
from __future__ import annotations

import subprocess
from pathlib import Path

_DELIVERABLE_EXTS: frozenset[str] = frozenset({
    ".html", ".htm", ".pdf", ".pptx", ".docx", ".xlsx",
})


def _is_tracked(rp: Path, filepath: Path) -> bool:
    """Return True if filepath is tracked by git (relative to rp)."""
    try:
        rel = str(filepath.relative_to(rp))
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=str(rp),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_misplaced_deliverables(
    rp: Path,
    deliverables_dir: str = "deliverables",
    exclude_dirs: list[str] | None = None,
) -> list[dict]:
    """Find non-markdown deliverable files inside docs/ and propose moving them.

    Returns findings with extra fields: target_path, is_tracked.

    `exclude_dirs` matters most here: golden references under a visual-regression
    tree are fixtures pinned to their path, and "move to deliverables/" would
    break the baselines they exist to hold.
    """
    from docs.common import excluded_predicate
    from docs.reporter import finding as make_finding

    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []

    is_excluded = excluded_predicate(rp, exclude_dirs)

    findings: list[dict] = []
    for f in sorted(docs_dir.rglob("*")):
        if not f.is_file() or is_excluded(f):
            continue
        if f.suffix.lower() not in _DELIVERABLE_EXTS:
            continue
        rel = str(f.relative_to(rp)).replace("\\", "/")
        target = f"{deliverables_dir}/{f.name}"
        tracked = _is_tracked(rp, f)
        fd = make_finding(
            "misplaced_deliverable", "warn", rel,
            f"deliverable file in docs/: {rel} — move to {target}",
        )
        fd["target_path"] = target
        fd["is_tracked"] = tracked
        findings.append(fd)
    return findings
