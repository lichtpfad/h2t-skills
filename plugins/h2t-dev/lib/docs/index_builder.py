"""Marker-based docs/README.md index builder with bootstrap support."""
from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

INDEX_START = "<!-- h2t-index-start -->"
INDEX_END = "<!-- h2t-index-end -->"

_MARKER_RE = re.compile(
    r"<!-- h2t-index-start -->.*?<!-- h2t-index-end -->",
    re.DOTALL,
)


def _default_generate(repo_root: Path, repo_name: str) -> str:
    """Import and call build_navigation_index from docs-index script."""
    import sys
    _index_dir = Path(__file__).parents[3] / "skills" / "docs-index" / "scripts"
    if str(_index_dir) not in sys.path:
        sys.path.insert(0, str(_index_dir))
    from index import build_navigation_index
    return build_navigation_index(repo_root, repo_name)


def compute_index_update(
    repo_root: Path,
    repo_name: str,
    readme_path: Path | None = None,
    *,
    generate: Callable[[Path, str], str] | None = None,
) -> tuple[str, str, bool]:
    """
    Compute new README content without writing.
    Returns (new_content, operation, has_markers).
    operation: 'replace' | 'append'
    has_markers: True if README already has index markers.
    """
    if generate is None:
        generate = _default_generate
    if readme_path is None:
        readme_path = repo_root / "docs" / "README.md"

    generated = generate(repo_root, repo_name)
    wrapped = f"{INDEX_START}\n{generated}\n{INDEX_END}"

    if not readme_path.exists():
        return wrapped + "\n", "append", False

    existing = readme_path.read_text(encoding="utf-8", errors="replace")

    if INDEX_START in existing:
        new_content = _MARKER_RE.sub(wrapped, existing)
        return new_content, "replace", True

    # Bootstrap: append section below existing content
    new_content = existing.rstrip() + "\n\n" + wrapped + "\n"
    return new_content, "append", False


def write_index(
    repo_root: Path,
    repo_name: str,
    *,
    apply: bool = False,
    readme_path: Path | None = None,
    generate: Callable[[Path, str], str] | None = None,
) -> dict:
    """
    Dry-run or apply index update. Returns operation report.
    On apply, uses atomic tmp-file + os.replace() (Windows-safe).
    """
    if readme_path is None:
        readme_path = repo_root / "docs" / "README.md"

    new_content, operation, has_markers = compute_index_update(
        repo_root, repo_name, readme_path, generate=generate
    )

    report: dict = {
        "readme_path": str(readme_path),
        "operation": operation,
        "has_markers": has_markers,
        "applied": False,
        "status": "dry_run",
    }

    if not apply:
        return report

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=readme_path.parent,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(new_content)
        tmp_path = tf.name

    try:
        os.replace(tmp_path, readme_path)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    report["applied"] = True
    report["status"] = "applied"
    return report
