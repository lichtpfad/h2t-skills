"""BFS orphan detection: finds .md files unreachable from docs/README.md."""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

_LINK_RE = re.compile(r'\[(?:[^\]]*)\]\(([^)#?\s][^)]*?)(?:[#?][^)]*)?\)')


def _parse_md_links(text: str, base_dir: Path, docs_dir: Path) -> list[Path]:
    """Extract local .md link targets constrained to within docs_dir."""
    docs_resolved = docs_dir.resolve()
    links = []
    for m in _LINK_RE.finditer(text):
        href = m.group(1).strip()
        if href.startswith(("http://", "https://", "mailto:", "/")):
            continue
        target = (base_dir / href).resolve()
        if target.suffix != ".md" or not target.is_file():
            continue
        try:
            target.relative_to(docs_resolved)
        except ValueError:
            continue
        if target.is_symlink():
            continue
        links.append(target)
    return links


def find_orphan_files(repo_root: Path, exclude_dirs: list[str] | None = None) -> list[dict]:
    """
    BFS from docs/README.md. Returns finding dicts for unreachable .md files.
    """
    from docs.common import excluded_predicate
    from docs.reporter import finding as make_finding

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    _is_excluded = excluded_predicate(repo_root, exclude_dirs)

    readme = docs_dir / "README.md"
    if not readme.exists():
        orphans = [f for f in sorted(docs_dir.rglob("*.md")) if not _is_excluded(f)]
        return [
            make_finding(
                "orphan",
                "warn",
                str(f.relative_to(repo_root)).replace("\\", "/"),
                "docs/README.md missing — cannot determine reachability",
            )
            for f in orphans
        ]

    visited: set[Path] = set()
    queue: deque[Path] = deque([readme.resolve()])
    visited.add(readme.resolve())

    while queue:
        current = queue.popleft()
        if not current.is_file():
            continue
        try:
            text = current.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for linked in _parse_md_links(text, current.parent, docs_dir):
            resolved = linked.resolve()
            if resolved not in visited:
                visited.add(resolved)
                queue.append(resolved)

    all_docs = {
        f.resolve()
        for f in docs_dir.rglob("*.md")
        if not _is_excluded(f)
    }
    orphans_abs = all_docs - visited

    findings = []
    repo_resolved = repo_root.resolve()
    for abs_path in sorted(orphans_abs):
        try:
            rel = str(abs_path.relative_to(repo_resolved)).replace("\\", "/")
        except ValueError:
            rel = str(abs_path)
        findings.append(
            make_finding(
                "orphan",
                "warn",
                rel,
                "Not reachable from docs/README.md or any linked index",
            )
        )
    return findings
