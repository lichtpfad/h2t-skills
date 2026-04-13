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
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, STANDARDS_FILES,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint documentation standards")
    parser.add_argument("repos", nargs="*", help="Repos to check (default: all 16)")
    parser.add_argument("--fix", action="store_true", help="Create missing dirs")
    parser.add_argument("--no-pymarkdown", action="store_true", help="Skip pymarkdownlnt")
    args = parser.parse_args()

    targets = args.repos or REPO_MANIFEST
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

        failures = (
            check_structure(rp)
            + check_adr_naming(rp)
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
