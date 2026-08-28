"""Generate new plan/spec/adr files with correct frontmatter.

Backs the `docs-lint new <kind> <slug>` command (issue #264, A'). Field lists
are sourced from FRONTMATTER_RULES so the generator can never drift from the
validator (check_frontmatter). Values are built directly here — this creates a
fresh file, so nothing exists to read defaults back from.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from docs.common import FRONTMATTER_RULES

# kind -> directory (relative to repo root)
KIND_DIR = {
    "plan": "docs/superpowers/plans",
    "spec": "docs/superpowers/specs",
    "adr": "docs/adr",
}

# kind -> FRONTMATTER_RULES key
_KIND_RULE = {
    "plan": "superpowers/plans",
    "spec": "superpowers/specs",
    "adr": "adr",
}


def slugify(raw: str) -> str:
    """Lowercase, collapse non-alphanumerics to single hyphens, trim."""
    return re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")


def _humanize(slug: str) -> str:
    words = slug.replace("-", " ").split()
    return " ".join(words).capitalize() if words else slug


def next_adr_number(adr_dir: Path) -> str:
    """Return the next 4-digit ADR number (max existing + 1, gaps allowed)."""
    mx = 0
    if adr_dir.exists():
        for f in adr_dir.glob("*.md"):
            m = re.match(r"(\d{4})-", f.name)
            if m:
                mx = max(mx, int(m.group(1)))
    return f"{mx + 1:04d}"


def _git_user(rp: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(rp), "config", "user.name"],
            capture_output=True, text=True,
        )
        name = r.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return "lichtpfad"


def create_doc(
    rp,
    kind: str,
    slug: str,
    *,
    today: str,
    milestone: str = "",
    title: str | None = None,
    author: str | None = None,
    issue: str = "",
    reason: str = "",
) -> Path:
    """Create a plan/spec/adr file with required frontmatter. Returns its path.

    Raises ValueError for an unknown kind or empty slug, FileExistsError if the
    target already exists (never overwrites).
    """
    rp = Path(rp)
    kind = kind.lower()
    if kind not in KIND_DIR:
        raise ValueError(f"unknown kind {kind!r}; choose plan|spec|adr")
    norm = slugify(slug)
    if not norm:
        raise ValueError(f"slug {slug!r} produced an empty name")

    doc_title = title or _humanize(norm)
    target_dir = rp / KIND_DIR[kind]
    if kind == "adr":
        filename = f"{next_adr_number(target_dir)}-{norm}.md"
    else:
        filename = f"{today}-{norm}.md"
    path = target_dir / filename
    if path.exists():
        raise FileExistsError(str(path))

    values = {
        "title": doc_title,
        "status": "proposed" if kind == "adr" else "draft",
        "owner": author or _git_user(rp),
        "date": today,
        "milestone": milestone,
        "issue": issue,
    }
    fields = FRONTMATTER_RULES[_KIND_RULE[kind]]
    lines = ["---"]
    for f in fields:
        lines.append(f'{f}: "{values.get(f, "")}"')
    # `reason` is not in FRONTMATTER_RULES: it is required only when `issue` is `none`,
    # and a field required always would be a finding on every linked document.
    if reason:
        lines.append(f'reason: "{reason}"')
    lines += ["---", "", f"# {doc_title}", ""]

    target_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
