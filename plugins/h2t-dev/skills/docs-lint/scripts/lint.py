#!/usr/bin/env python3
"""Documentation standards linter for h2t repos."""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, REPO_EXTRA_DIRS, STANDARDS_FILES,
    FRONTMATTER_RULES, ensure_dir, print_header, repo_path, parse_frontmatter,
)

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

YAML_FLAG_CHECKS: dict[str, str] = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report": "docs/reports",
    "docs.marketing_docs": "docs/marketing",
}


def _load_projects_yaml() -> dict:
    if not PROJECTS_YAML_PATH.exists():
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return {}


def _get_flag(project_data: dict, dotted_key: str) -> bool:
    parts = dotted_key.split(".")
    node = project_data
    for p in parts:
        if not isinstance(node, dict):
            return False
        node = node.get(p, False)
    return bool(node)


def check_projects_yaml(rp: Path, name: str, projects: dict) -> list[str]:
    if not projects:
        return []
    project_data = projects.get(name, {})
    if not project_data:
        return []
    failures = []
    for flag, required_path in YAML_FLAG_CHECKS.items():
        if _get_flag(project_data, flag):
            target = rp / required_path
            if not target.exists():
                failures.append(f"projects.yaml {flag}=true but missing: {required_path}")
    return failures


def check_structure(rp: Path) -> list[str]:
    failures = []
    for rel_dir in REQUIRED_CORE_DIRS:
        if not (rp / rel_dir).exists():
            failures.append(f"missing dir: {rel_dir}/")
    for name, path in [
        ("docs/README.md", rp / "docs" / "README.md"),
        (".claude/rules/documentation.md", rp / ".claude" / "rules" / "documentation.md"),
        (".pymarkdown.yaml", rp / ".pymarkdown.yaml"),
        (".vale.ini", rp / ".vale.ini"),
    ]:
        if not path.exists():
            failures.append(f"missing: {name}")
    return failures


def check_adr_naming(rp: Path) -> list[str]:
    failures = []
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return failures
    for adr in adr_dir.glob("[0-9]*.md"):
        if not re.match(r"^\d{4}-", adr.name):
            failures.append(f"ADR naming: {adr.name} (expected 4-digit prefix)")
    return failures


LEGACY_DIRS = [
    "docs/plans",
    "docs/specs",
    "docs/handoff",
    "docs/handoffs",
    "docs/eval",
]


def check_legacy_dirs(rp: Path, extra_dirs: list[str] | None = None) -> list[str]:
    skip = set(extra_dirs or [])
    failures = []
    for rel in LEGACY_DIRS:
        dir_name = rel.split("/")[-1]
        if dir_name in skip:
            continue
        if (rp / rel).exists():
            failures.append(f"legacy dir: {rel}/ — migrate to docs/superpowers/ or docs/archive/")
    return failures


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_NAMING_DIRS = ["docs/superpowers/specs", "docs/superpowers/plans"]
_NAMING_SKIP = {"README.md", "index.md"}


def check_naming_conventions(rp: Path) -> list[str]:
    failures = []
    for rel_dir in _NAMING_DIRS:
        d = rp / rel_dir
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            if md.name in _NAMING_SKIP:
                continue
            if not _DATE_PREFIX.match(md.name):
                failures.append(
                    f"naming: {rel_dir}/{md.name} — expected YYYY-MM-DD- prefix"
                )
    return failures


def check_frontmatter(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return failures
    for md_file in docs_dir.rglob("*.md"):
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern not in rel or not required_fields:
                continue
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            if fm is None:
                failures.append(f"{rel}: missing frontmatter")
                break
            for field in required_fields:
                if field not in fm:
                    failures.append(f"{rel}: missing field '{field}'")
    return failures


def run_pymarkdownlnt(rp: Path) -> list[str]:
    pymdl = shutil.which("pymarkdownlnt") or shutil.which("pymarkdown")
    if not pymdl:
        return []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []
    result = subprocess.run(
        [pymdl, "scan", str(docs_dir)],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode != 0:
        out = result.stdout + result.stderr
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return [f"pymarkdownlnt: {ln}" for ln in lines[:20]]
    return []


def fix_structure(rp: Path) -> list[str]:
    fixes = []
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if ensure_dir(d):
            fixes.append(f"created: {rel_dir}/")
    return fixes


def _extract_title(text: str, filename: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    # fallback: strip date prefix and extension
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", filename)
    return name.replace("-", " ").replace("_", " ").strip(".md")


def _extract_date(filename: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else "unknown"


def _extract_milestone(filename: str) -> str:
    m = re.search(r"-(m\d+)-", filename, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _git_author(rp: Path, filepath: Path) -> str:
    rel = str(filepath.relative_to(rp))
    result = subprocess.run(
        ["git", "-C", str(rp), "log", "--diff-filter=A", "--format=%an", "--", rel],
        capture_output=True, text=True,
    )
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return lines[0] if lines else "lichtpfad"


def fix_frontmatter(rp: Path) -> list[str]:
    fixes = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return fixes
    for md_file in docs_dir.rglob("*.md"):
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        matched_pattern = None
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern in rel and required_fields:
                matched_pattern = dir_pattern
                required_fields_for_pattern = required_fields
                break
        if not matched_pattern:
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm is not None and all(f in fm for f in required_fields_for_pattern):
            continue
        # Build frontmatter
        title = _extract_title(text, md_file.stem)
        date = _extract_date(md_file.name)
        milestone = _extract_milestone(md_file.name)
        lines = ["---", f'title: "{title}"', 'status: "draft"']
        if "owner" in required_fields_for_pattern:
            owner = _git_author(rp, md_file)
            lines.append(f'owner: "{owner}"')
        lines.append(f'date: "{date}"')
        if "milestone" in required_fields_for_pattern:
            lines.append(f'milestone: "{milestone}"')
        lines += ["---", ""]
        header = "\n".join(lines)
        # Strip existing frontmatter if partial
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2].lstrip("\n")
        md_file.write_text(header + text, encoding="utf-8")
        fixes.append(f"added frontmatter: {rel}")
    return fixes


def _detect_current_repo() -> str | None:
    """Detect repo name from cwd if it matches a known h2t-* repo."""
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        name = part.name
        if name in REPO_MANIFEST:
            return name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint documentation standards")
    parser.add_argument("repos", nargs="*", help="Repos to check (default: current repo)")
    parser.add_argument("--all", action="store_true", help="Check all 16 repos")
    parser.add_argument("--fix", action="store_true", help="Create missing dirs")
    parser.add_argument("--fix-frontmatter", action="store_true",
                        help="Auto-add missing frontmatter (title from heading, date from filename)")
    parser.add_argument("--no-pymarkdown", action="store_true", help="Skip pymarkdownlnt")
    args = parser.parse_args()

    if args.repos:
        targets = args.repos
    elif args.all:
        targets = REPO_MANIFEST
    else:
        detected = _detect_current_repo()
        targets = [detected] if detected else REPO_MANIFEST
    print_header(f"docs-lint: checking {len(targets)} repos")

    projects = _load_projects_yaml()

    print("\n--- Global Standards ---")
    std_dir = DEV_ROOT / "docs" / "standards"
    std_fails = [f for f in STANDARDS_FILES if not (std_dir / f).exists()]
    if std_fails:
        for f in std_fails:
            print(f"  FAIL: missing {f}")
    else:
        print(f"  OK: all {len(STANDARDS_FILES)} standards files present")

    total_failures = len(std_fails)

    for name in targets:
        rp = repo_path(name)
        if not rp.exists():
            print(f"\n--- {name} ---\n  SKIP: repo not found at {rp}")
            continue

        print(f"\n--- {name} ---")

        if args.fix:
            fixes = fix_structure(rp)
            for f in fixes:
                print(f"  FIX: {f}")

        if args.fix_frontmatter:
            fixes = fix_frontmatter(rp)
            for f in fixes:
                print(f"  FIX: {f}")

        extra = REPO_EXTRA_DIRS.get(name, [])
        failures = (
            check_structure(rp)
            + check_adr_naming(rp)
            + check_legacy_dirs(rp, extra_dirs=extra)
            + check_naming_conventions(rp)
            + check_frontmatter(rp)
            + check_projects_yaml(rp, name, projects)
            + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
        )
        if failures:
            for f in failures:
                print(f"  FAIL: {f}")
            total_failures += len(failures)
        else:
            print("  OK: all checks passed")

    print(f"\n{'=' * 60}")
    if total_failures:
        print(f"  RESULT: {total_failures} issue(s) found")
        sys.exit(1)
    else:
        print(f"  RESULT: all {len(targets)} repos compliant")


if __name__ == "__main__":
    main()
