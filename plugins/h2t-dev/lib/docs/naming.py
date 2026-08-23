"""Extended naming convention checks for all docs/ markdown files."""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

_ALLOWED_NAMES = frozenset({
    "README.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md",
    "GEMINI.md", "index.md", "LICENSE.md",
})
_KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*\.md$")
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_DATE_REQUIRED_SUBDIRS = frozenset({"superpowers/specs", "superpowers/plans"})


def _requires_date_prefix(rel_path: str) -> bool:
    """True if the path is inside a dir that requires YYYY-MM-DD- prefix."""
    return any(d in rel_path for d in _DATE_REQUIRED_SUBDIRS)


def check_naming_all_docs(repo_root: Path, exclude_dirs: list[str] | None = None, naming_exceptions: list[str] | None = None) -> list[dict]:
    """
    Check all .md files in docs/ for:
    1. lowercase kebab-case (spaces, uppercase, underscores → finding)
    2. date prefix where required (superpowers/specs/, superpowers/plans/)
    Returns list of finding dicts.
    """
    from docs.reporter import finding as make_finding

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    _excluded = {(repo_root / d).resolve() for d in (exclude_dirs or [])}

    def _is_excluded(p: Path) -> bool:
        rp = p.resolve()
        return any(rp == ex or ex in rp.parents for ex in _excluded)

    findings = []
    for md_file in docs_dir.rglob("*.md"):
        if _is_excluded(md_file):
            continue
        name = md_file.name
        if name in _ALLOWED_NAMES:
            continue
        rel = str(md_file.relative_to(repo_root)).replace("\\", "/")
        rel_posix = rel
        if any(fnmatch.fnmatch(rel_posix, pat) for pat in (naming_exceptions or [])):
            continue

        if not _KEBAB_RE.match(name):
            proposed = re.sub(r"[\s_]+", "-", name).lower()
            findings.append(
                make_finding(
                    "naming",
                    "warn",
                    rel,
                    f"Not lowercase kebab-case: '{name}'",
                    safe_fix=f"rename to '{proposed}'",
                )
            )
            continue  # skip date-prefix check on badly-named file

        if _requires_date_prefix(rel) and not _DATE_PREFIX_RE.match(name):
            findings.append(
                make_finding(
                    "naming",
                    "warn",
                    rel,
                    f"Missing date prefix in {rel.rsplit('/', 1)[0]}: '{name}'",
                    safe_fix=f"rename to 'YYYY-MM-DD-{name}'",
                )
            )

    return findings
