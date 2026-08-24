"""Count unfinished planning documents so the briefing can show the number.

docs-lint measures form — naming, frontmatter fields, reachability from the
index. It never measures lifecycle, so a plan written in May and abandoned in
May stays a perfectly valid document forever. This module measures the other
axis, and it is deliberately cheap: no git, no gh, no subprocess — the session
briefing runs it on every start.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

# Sections whose documents describe intended work. `docs/archive/` is excluded
# on purpose: archiving is the remedy this loop points at, so counting archived
# files would make the number impossible to bring down.
_SECTIONS = ("superpowers/plans", "superpowers/specs", "adr")

# A status that means the document no longer describes pending work.
_CLOSED = {
    "done", "complete", "completed", "accepted", "approved",
    "superseded", "deprecated", "rejected", "archived",
}

STALE_DAYS = 60

_DATE_IN_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
_STATUS = re.compile(r"^status:\s*(.+?)\s*$", re.MULTILINE)
_DATE_FM = re.compile(r"^date:\s*(.+?)\s*$", re.MULTILINE)


def _frontmatter(text: str) -> str:
    """The text between the opening `---` and the next one, or "" if absent."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _unquote(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _doc_date(path: Path, fm: str) -> date | None:
    """Filename date first — it is the canonical one the naming rule enforces."""
    m = _DATE_IN_NAME.match(path.name)
    if not m:
        m2 = _DATE_FM.search(fm)
        if not m2:
            return None
        m = _DATE_IN_NAME.match(_unquote(m2.group(1)) + "-")
        if not m:
            return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def gather_docs_debt(
    repo_root: Path | str, today: date | None = None, stale_days: int = STALE_DAYS
) -> dict:
    """Return {total, open, stale, stale_days}, or {} when there is nothing to count.

    `open` counts a missing status as open: unknown is not finished, and a debt
    metric that rounds the other way hides exactly the files nobody maintains.
    """
    root = Path(repo_root)
    today = today or date.today()

    total = open_count = stale = 0
    for section in _SECTIONS:
        section_dir = root / "docs" / section
        if not section_dir.is_dir():
            continue
        for f in section_dir.rglob("*.md"):
            if f.name.lower() in {"readme.md", "index.md"}:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            total += 1
            fm = _frontmatter(text)
            m = _STATUS.search(fm)
            status = _unquote(m.group(1)).lower() if m else ""
            if status in _CLOSED:
                continue
            open_count += 1
            doc_date = _doc_date(f, fm)
            if doc_date and (today - doc_date).days > stale_days:
                stale += 1

    if not total:
        return {}
    return {
        "total": total,
        "open": open_count,
        "stale": stale,
        "stale_days": stale_days,
    }
