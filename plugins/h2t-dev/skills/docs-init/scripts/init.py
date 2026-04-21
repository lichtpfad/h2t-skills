#!/usr/bin/env python3
"""Scaffold standard docs/ structure for h2t repos."""

import argparse
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT, REQUIRED_CORE_DIRS, ensure_dir, git_add_commit, print_header, repo_path,
)

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

CONDITIONAL_DIRS: dict[str, str] = {
    "docs.positioning": "docs/product",
    "docs.marketing_docs": "docs/marketing",
    "docs.architecture": "docs/architecture",
    "docs.client_api": "docs/client",
    "docs.guides": "docs/guides",
    "docs.research": "docs/research",
    "docs.artifacts": "docs/.artifacts",
}

MINIMAL_README = """\
# {name} Documentation

## Quick Links

| Section | Description |
|---------|-------------|
| [Specs & Plans](superpowers/) | Design specs and implementation plans |
| [ADRs](adr/) | Architectural decisions |
| [Reports](reports/) | Milestone reports |
"""

RULES_TEMPLATE = """\
# Documentation Rules

Follow standards defined in C:/dev/docs/standards/:
- Directory structure: documentation-structure.md
- Naming: naming-conventions.md
- Git conventions: git-naming-conventions.md
- ADR process: adr-process.md
- Linting: linting.md

All documentation goes in docs/ with the standard subdirectory layout.
"""

PYMARKDOWN_YAML = """\
plugins:
  md013:
    enabled: false
  md033:
    enabled: false
  md041:
    enabled: false
"""

VALE_INI = """\
StylesPath = .vale/styles
MinAlertLevel = warning

[docs/**/*.md]
BasedOnStyles = Vale
"""


def _load_project(name: str) -> dict:
    if not PROJECTS_YAML_PATH.exists():
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        data = yaml.safe_load(text) or {}
        return data.get(name, {})
    except ImportError:
        return {}


def init_repo(name: str, *, dry_run: bool = True, commit: bool = False) -> list[str] | None:
    rp = repo_path(name)
    if not rp.exists():
        print(f"  ERROR: {rp} not found")
        return None

    project_data = _load_project(name)
    changes = []
    action = "would create" if dry_run else "created"

    # Required core dirs
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if not d.exists():
            if not dry_run:
                ensure_dir(d)
            print(f"  {action}: {rel_dir}/")
            changes.append(rel_dir)

    # Conditional dirs from projects.yaml
    for flag, rel_dir in CONDITIONAL_DIRS.items():
        parts = flag.split(".")
        node = project_data
        for p in parts:
            node = node.get(p, False) if isinstance(node, dict) else False
        if node:
            d = rp / rel_dir
            if not d.exists():
                if not dry_run:
                    ensure_dir(d)
                print(f"  {action}: {rel_dir}/ (from projects.yaml {flag}=true)")
                changes.append(rel_dir)

    # docs/README.md
    readme = rp / "docs" / "README.md"
    if not readme.exists():
        if not dry_run:
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(MINIMAL_README.format(name=name), encoding="utf-8")
        print(f"  {action}: docs/README.md")
        changes.append("docs/README.md")

    # .claude/rules/documentation.md
    rules_file = rp / ".claude" / "rules" / "documentation.md"
    if not rules_file.exists():
        if not dry_run:
            rules_file.parent.mkdir(parents=True, exist_ok=True)
            rules_file.write_text(RULES_TEMPLATE, encoding="utf-8")
        print(f"  {action}: .claude/rules/documentation.md")
        changes.append(".claude/rules/documentation.md")

    # .pymarkdown.yaml
    pm = rp / ".pymarkdown.yaml"
    if not pm.exists():
        if not dry_run:
            pm.write_text(PYMARKDOWN_YAML, encoding="utf-8")
        print(f"  {action}: .pymarkdown.yaml")
        changes.append(".pymarkdown.yaml")

    # .vale.ini
    vale = rp / ".vale.ini"
    if not vale.exists():
        if not dry_run:
            vale.write_text(VALE_INI, encoding="utf-8")
        print(f"  {action}: .vale.ini")
        changes.append(".vale.ini")

    # .gitignore — create if missing, append entry if needed
    gi = rp / ".gitignore"
    gi_entry = "docs/.artifacts/"
    gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if gi_entry not in gi_content:
        if not dry_run:
            with open(gi, "a", encoding="utf-8") as f:
                f.write(f"\n# Documentation artifacts\n{gi_entry}\n")
        print(f"  {action}: .gitignore entry for {gi_entry}")
        changes.append(".gitignore")

    if changes and not dry_run and commit:
        git_add_commit(rp, ["docs/", ".claude/", ".pymarkdown.yaml", ".vale.ini", ".gitignore"],
                       "docs: scaffold standard documentation structure")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold docs/ structure")
    parser.add_argument("repo", help="Repo name (e.g. h2t-graphs)")
    parser.add_argument("--apply", action="store_true", help="Actually create files (default: dry-run)")
    parser.add_argument("--commit", action="store_true", help="Git commit after apply")
    args = parser.parse_args()

    if args.commit and not args.apply:
        print("WARNING: --commit has no effect without --apply")
    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-init [{mode}]: {args.repo}")
    changes = init_repo(args.repo, dry_run=not args.apply, commit=args.commit)

    if changes is None:
        sys.exit(1)
    if not changes:
        print("\n  Nothing to do -- all files already exist")
    elif not args.apply:
        print(f"\n  {len(changes)} changes pending. Run with --apply to create.")


if __name__ == "__main__":
    main()
