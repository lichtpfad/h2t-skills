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

from docs.common import REPO_MANIFEST, parse_frontmatter, print_header, repo_path


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


def _collect_dir(rp: Path, subpath: str, glob: str = "*.md") -> list[dict]:
    d = rp / "docs" / subpath
    if not d.exists():
        return []
    rows = []
    for f in sorted(d.glob(glob), reverse=True):
        if f.name in ("index.md", "README.md"):
            continue
        meta = _meta(f)
        rows.append({"file": f.name, **meta})
    return rows


def _status_badge(status: str) -> str:
    mapping = {
        "draft": "draft", "proposed": "proposed", "accepted": "accepted",
        "implemented": "done", "done": "done", "completed": "done",
        "deprecated": "deprecated", "superseded": "superseded",
    }
    return mapping.get(status.lower(), status) if status else ""


_SECTION_MAP = [
    ("superpowers", "Specs & Plans", "Design specs and implementation plans"),
    ("reports",     "Reports",       "Milestone reports"),
    ("guides",      "Guides",        "How-to documentation"),
    ("api",         "API",           "API reference"),
]


def build_navigation_index(rp: Path, repo_name: str) -> str:
    docs_dir = rp / "docs"
    lines = [f"# {repo_name} Documentation", ""]

    # Quick Links — only when at least one section dir exists (adr excluded: has own table)
    present = [
        (anchor, title, desc)
        for anchor, title, desc in _SECTION_MAP
        if (docs_dir / anchor).exists()
    ]
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
            badge = _status_badge(adr["status"])
            lines.append(f"| {num} | {link} | {badge} | {adr['date']} |")
        lines.append("")

    # Preserve Specs, Plans, Reports tables
    specs = _collect_dir(rp, "superpowers/specs")
    if specs:
        lines += ["## Specs", ""]
        lines += ["| Title | Status | Date |", "|-------|--------|------|"]
        for r in specs:
            badge = _status_badge(r["status"])
            lines.append(f"| [{r['title']}](superpowers/specs/{r['file']}) | {badge} | {r['date']} |")
        lines.append("")

    plans = _collect_dir(rp, "superpowers/plans")
    if plans:
        lines += ["## Plans", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in plans:
            lines.append(f"| [{r['title']}](superpowers/plans/{r['file']}) | {r['date']} |")
        lines.append("")

    reports = _collect_dir(rp, "reports")
    if reports:
        lines += ["## Reports", ""]
        lines += ["| Title | Date |", "|-------|------|"]
        for r in reports:
            lines.append(f"| [{r['title']}](reports/{r['file']}) | {r['date']} |")
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
