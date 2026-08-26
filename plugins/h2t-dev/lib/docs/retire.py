"""Move stale planning documents into docs/archive/.

Retirement is the only remedy that lowers the docs-debt number the briefing
shows, and it is deliberately manual. Two automatic closing signals were
measured on this repo and both failed: a plan slug appears in 7 of 60 merged PR
bodies, and 47 of 140 documents were created in one commit and never touched
again — a count that cannot separate "done and never updated" from "abandoned".
Setting `status: done` on that evidence would be a guess written into the file.

So the judgement stays with a person. What this module removes is the cost of
making it: candidates come with their evidence, and one flag moves them.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

from docs.common import excluded_predicate, parse_frontmatter

# Sections that describe intended work, and where each retires to. `adr` is
# absent on purpose: an ADR is a permanent record, and a superseded one still
# explains a decision somebody has to live with.
_SECTIONS = {
    "docs/superpowers/plans": "docs/archive/plans",
    "docs/superpowers/specs": "docs/archive/specs",
}

_CLOSED = {
    "done", "complete", "completed", "accepted", "approved",
    "superseded", "deprecated", "rejected", "archived",
}

STALE_DAYS = 60

_DATE_IN_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")


def _as_date(value: str | date | None) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    m = _DATE_IN_NAME.match(str(value).strip().strip('"').strip("'") + "-")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _commit_counts(repo_root: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Per document: (commits that touched it, commits that also touched code).

    The second number is the one that discriminates. A raw commit count does
    not: on h2t-skills the modal value was 2, and for dozens of files the second
    commit was the same one — a bulk `docs-lint --fix-frontmatter` sweep. A tool
    touched the file; nobody worked the plan. A commit that changed the document
    *and* something outside docs/ is work actually shipping with it.

    One `git log` over the whole history, not per file: 140 documents would
    otherwise be 140 subprocesses. Best-effort — a directory that is not a git
    repo yields empty maps and every count reads 0.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "log", "--format=%x00", "--name-only"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return {}, {}
    if out.returncode != 0:
        return {}, {}

    touches: dict[str, int] = {}
    work: dict[str, int] = {}
    for chunk in out.stdout.split("\0")[1:]:
        files = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not files:
            continue
        with_code = any(not f.startswith("docs/") for f in files)
        for f in files:
            if not any(f.startswith(s + "/") for s in _SECTIONS):
                continue
            touches[f] = touches.get(f, 0) + 1
            if with_code:
                work[f] = work.get(f, 0) + 1
    return touches, work


def find_retire_candidates(
    repo_root: Path | str,
    today: str | date | None = None,
    stale_days: int = STALE_DAYS,
    exclude_dirs: list[str] | None = None,
    never_shipped: bool = False,
) -> list[dict]:
    """Open plans/specs older than *stale_days*, each with its evidence.

    *never_shipped* narrows the list to documents with no commit that touched
    them and code together. It selects, it does not conclude: "nothing shipped
    alongside" is what was measured, and calling that pile "done" or "abandoned"
    is the guess this module refuses to write into a file.
    """
    root = Path(repo_root)
    now = _as_date(today) or date.today()
    is_excluded = excluded_predicate(root, exclude_dirs)
    counts, work = _commit_counts(root)

    candidates: list[dict] = []
    for section in _SECTIONS:
        section_dir = root / section
        if not section_dir.is_dir():
            continue
        for f in sorted(section_dir.rglob("*.md")):
            if f.name.lower() in {"readme.md", "index.md"} or is_excluded(f):
                continue
            try:
                fm = parse_frontmatter(f.read_text(encoding="utf-8")) or {}
            except (OSError, UnicodeDecodeError):
                continue
            status = str(fm.get("status", "")).strip().strip('"').lower()
            if status in _CLOSED:
                continue
            doc_date = _as_date(f.name[:10]) or _as_date(fm.get("date"))
            if not doc_date or (now - doc_date).days <= stale_days:
                continue
            rel = f.relative_to(root).as_posix()
            if never_shipped and work.get(rel, 0) > 0:
                continue
            candidates.append({
                "path": rel,
                "target": archive_target(rel),
                "date": doc_date.isoformat(),
                "age_days": (now - doc_date).days,
                "status": status or "(нет)",
                "commits": counts.get(rel, 0),
                "work_commits": work.get(rel, 0),
            })
    return candidates


def archive_target(rel_path: str) -> str:
    """Where *rel_path* retires to, mirroring its section under docs/archive/."""
    for section, target in _SECTIONS.items():
        if rel_path.startswith(section + "/"):
            return f"{target}/{Path(rel_path).name}"
    return f"docs/archive/{Path(rel_path).name}"


def retire_files(repo_root: Path | str, candidates: list[dict]) -> list[dict]:
    """`git mv` each candidate into the archive. Never overwrites.

    A collision means a document of that name was archived before; moving over
    it would destroy the earlier one, and the two are not interchangeable just
    because they share a slug.
    """
    root = Path(repo_root)
    results: list[dict] = []
    for c in candidates:
        src, dst = root / c["path"], root / c["target"]
        if dst.exists():
            results.append({**c, "status": "skipped", "reason": "цель уже существует"})
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        moved = subprocess.run(
            ["git", "-C", str(root), "mv", c["path"], c["target"]],
            capture_output=True, text=True,
        )
        if moved.returncode != 0:
            # Untracked, or not a git repo — a plain rename still retires it.
            try:
                src.rename(dst)
            except OSError as exc:
                results.append({**c, "status": "failed", "reason": str(exc)})
                continue
        results.append({**c, "status": "moved"})
    return results
