#!/usr/bin/env python3
"""Generate docs/README.md index for an h2t repo."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    REPO_MANIFEST,
    excluded_predicate,
    parse_frontmatter,
    print_header,
    repo_path,
)


def _detect_current_repo() -> str | None:
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part.name
    return None


def _meta(f: Path) -> dict:
    """Extract title, status, date from frontmatter or filename."""
    text = f.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text) or {}
    title = fm.get("title") or _title_from_file(text, f.stem)
    status = fm.get("status", "")
    date = fm.get("date") or _date_from_name(f.name)
    return {"title": title, "status": status, "date": date}


def _title_from_file(text: str, stem: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stem)
    return name.replace("-", " ").replace("_", " ")


def _date_from_name(name: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else ""


def _collect_adrs(rp: Path) -> list[dict]:
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return []
    rows = []
    for f in sorted(adr_dir.glob("[0-9]*.md")):
        m = re.match(r"^(\d+)", f.name)
        num = m.group(1).lstrip("0") or "0" if m else "?"
        meta = _meta(f)
        rows.append({"num": num, "file": f.name, **meta})
    return rows


def _collect_dir(rp: Path, subpath: str, glob: str = "*.md", is_excluded=None) -> list[dict]:
    """Collect docs under `subpath`, recursively.

    `file` is the path relative to the section dir, so a caller building
    `f"{anchor}/{row['file']}"` links a nested document instead of the
    directory it lives in. A link to a directory is a dead end for the
    orphan detector's BFS — that is what left 44 documents unreachable.
    """
    d = rp / "docs" / subpath
    if not d.exists():
        return []
    rows = []
    for f in sorted(d.rglob(glob), reverse=True):
        # A nested README/index is the entry point of its subtree, so it is
        # listed. Only docs/README.md is skipped, and that one lives above
        # every section dir — it can never appear here.
        if is_excluded and is_excluded(f):
            continue
        meta = _meta(f)
        rows.append({"file": f.relative_to(d).as_posix(), **meta})
    return rows


def _collect_root_docs(rp: Path, is_excluded=None) -> list[dict]:
    """Markdown sitting directly in docs/ — no section dir claims these."""
    d = rp / "docs"
    if not d.exists():
        return []
    rows = []
    for f in sorted(d.glob("*.md"), reverse=True):
        if f.name == "README.md":   # the index itself
            continue
        if is_excluded and is_excluded(f):
            continue
        rows.append({"file": f.name, **_meta(f)})
    return rows


def _status_badge(status: str) -> str:
    mapping = {
        "draft": "draft", "proposed": "proposed", "accepted": "accepted",
        "implemented": "done", "done": "done", "completed": "done",
        "deprecated": "deprecated", "superseded": "superseded",
    }
    return mapping.get(status.lower(), status) if status else ""


# Known section metadata — anchor → (title, description)
_KNOWN_SECTIONS: dict[str, tuple[str, str]] = {
    "superpowers": ("Specs & Plans", "Design specs and implementation plans"),
    "reports":     ("Reports",       "Milestone reports"),
    "guides":      ("Guides",        "How-to documentation"),
    "api":         ("API",           "API reference"),
    "research":    ("Research",      "Research documents"),
    "product":     ("Product",       "Product documentation"),
    "marketing":   ("Marketing",     "Marketing documentation"),
    "architecture":("Architecture",  "Architecture documentation"),
    "client":      ("Client",        "Client documentation"),
}

# These dirs have dedicated sections in the index — exclude from Quick Links
_QUICK_LINKS_EXCLUDE = {"adr", ".artifacts"}


def _discover_sections(docs_dir: Path, is_excluded=None) -> list[tuple[str, str, str]]:
    """Return (anchor, title, description) for all docs/ subdirs that have .md files."""
    if not docs_dir.exists():
        return []
    result = []
    for d in sorted(docs_dir.iterdir()):
        if not d.is_dir():
            continue
        if d.name in _QUICK_LINKS_EXCLUDE or d.name.startswith("."):
            continue
        if is_excluded and is_excluded(d):
            continue
        if not any(f for f in d.rglob("*.md") if not (is_excluded and is_excluded(f))):
            continue
        anchor = d.name
        title, desc = _KNOWN_SECTIONS.get(
            anchor, (anchor.replace("-", " ").title(), f"{anchor.title()} documents")
        )
        result.append((anchor, title, desc))
    return result


def build_navigation_index(rp: Path, repo_name: str, exclude_dirs: list[str] | None = None) -> str:
    docs_dir = rp / "docs"
    is_excluded = excluded_predicate(rp, exclude_dirs)
    linked: set[str] = set()
    lines = [f"# {repo_name} Documentation", ""]

    # Quick Links — dynamic: scan all docs/ subdirs with .md content
    present = _discover_sections(docs_dir, is_excluded)
    if present:
        lines += ["## Quick Links", ""]
        lines += ["| Section | Description |", "|---------|-------------|"]
        for anchor, title, desc in present:
            lines.append(f"| [{title}]({anchor}/) | {desc} |")
        lines.append("")

    # ADR table — uses _collect_adrs() schema: num, file, title, status, date
    adrs = _collect_adrs(rp)
    if adrs:
        lines += ["## Architecture Decisions", ""]
        lines += ["| # | Title | Status | Date |", "|---|-------|--------|------|"]
        for adr in adrs:
            num = adr["num"]
            link = f"[{adr['title']}](adr/{adr['file']})"
            linked.add(f"adr/{adr['file']}")
            badge = _status_badge(adr["status"])
            lines.append(f"| {num} | {link} | {badge} | {adr['date']} |")
        lines.append("")
        # adr/index.md is outside the [0-9]*.md glob above, so it needs its own link
        if (rp / "docs" / "adr" / "index.md").exists():
            lines += ["See also: [ADR Index](adr/index.md)", ""]
            linked.add("adr/index.md")

    # Preserve Specs, Plans, Reports tables
    specs = _collect_dir(rp, "superpowers/specs", is_excluded=is_excluded)
    if specs:
        lines += ["## Specs", ""]
        lines += ["| Title | Status | Date |", "|-------|--------|------|"]
        for r in specs:
            badge = _status_badge(r["status"])
            lines.append(f"| [{r['title']}](superpowers/specs/{r['file']}) | {badge} | {r['date']} |")
            linked.add(f"superpowers/specs/{r['file']}")
        lines.append("")

    plans = _collect_dir(rp, "superpowers/plans", is_excluded=is_excluded)
    if plans:
        lines += ["## Plans", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in plans:
            lines.append(f"| [{r['title']}](superpowers/plans/{r['file']}) | {r['date']} |")
            linked.add(f"superpowers/plans/{r['file']}")
        lines.append("")

    reports = _collect_dir(rp, "reports", is_excluded=is_excluded)
    if reports:
        lines += ["## Reports", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in reports:
            lines.append(f"| [{r['title']}](reports/{r['file']}) | {r['date']} |")
            linked.add(f"reports/{r['file']}")
        lines.append("")

    # Dynamic sections — generate individual file links so orphan detector can follow them.
    # `linked` is what the dedicated tables above already cover; everything else in a
    # section still needs a link, including subtrees those tables do not reach
    # (superpowers/references/ is the case that motivated this).
    _HANDLED_SECTIONS = {"adr"}
    for anchor, title, _desc in present:
        if anchor in _HANDLED_SECTIONS:
            continue
        section_files = [
            r for r in _collect_dir(rp, anchor, is_excluded=is_excluded)
            if f"{anchor}/{r['file']}" not in linked
        ]
        if section_files:
            lines += [f"## {title}", ""]
            lines += ["| Title | Date |", "|-------|------|"]
            for r in section_files:
                lines.append(f"| [{r['title']}]({anchor}/{r['file']}) | {r['date']} |")
                linked.add(f"{anchor}/{r['file']}")
            lines.append("")

    # Loose markdown directly in docs/ — no section dir claims these, and the
    # repo's own baseline plan (docs/h2t-ops-roadmap.md) was one of them.
    root_docs = _collect_root_docs(rp, is_excluded)
    if root_docs:
        lines += ["## Documents", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in root_docs:
            lines.append(f"| [{r['title']}]({r['file']}) | {r['date']} |")
        lines.append("")

    # Preserve custom sections from existing README (## Notes, ## Team, ## Links)
    readme = rp / "docs" / "README.md"
    if readme.exists():
        existing = readme.read_text(encoding="utf-8")
        preserved = _extract_custom_sections(existing)
        if preserved:
            lines += ["", preserved]

    return "\n".join(lines) + "\n"


def _extract_custom_sections(text: str) -> str:
    """Keep sections under ## Notes or ## Team (user-maintained)."""
    custom_headers = {"## notes", "## team", "## links"}
    in_custom = False
    kept = []
    for line in text.splitlines():
        if line.startswith("## ") and line.lower().strip() in custom_headers:
            in_custom = True
        elif line.startswith("## ") and in_custom:
            if line.lower().strip() not in custom_headers:
                in_custom = False
        if in_custom:
            kept.append(line)
    return "\n".join(kept)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate docs/README.md index")
    parser.add_argument("repo", nargs="?", help="Repo name (default: auto-detect from cwd)")
    parser.add_argument("--apply", action="store_true", help="Write docs/README.md")
    parser.add_argument("--commit", action="store_true", help="Git commit after writing")
    args = parser.parse_args()

    name = args.repo or _detect_current_repo()
    if not name:
        print("ERROR: cannot detect repo from cwd. Pass repo name as argument.")
        sys.exit(1)

    rp = repo_path(name)
    if not rp.exists():
        print(f"ERROR: {rp} not found")
        sys.exit(1)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-index [{mode}]: {name}")

    content = build_navigation_index(rp, name)
    print(content)

    if not args.apply:
        print("--- Run with --apply to write docs/README.md ---")
        return

    readme = rp / "docs" / "README.md"
    readme.write_text(content, encoding="utf-8")
    print(f"Written: {readme}")

    if args.commit:
        subprocess.run(
            ["git", "-C", str(rp), "add", "docs/README.md"], check=True,
        )
        result = subprocess.run(
            ["git", "-C", str(rp), "diff", "--cached", "--quiet"],
            capture_output=True,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "-C", str(rp), "commit", "-m", "docs: regenerate docs/README.md index"],
                check=True,
            )
            print("Committed.")
        else:
            print("No changes to commit.")


if __name__ == "__main__":
    main()
