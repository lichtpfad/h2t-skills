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
from docs.project_types import PROJECT_TYPES

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

DOCS_LINT_CONFIG = """\
schema: h2t_docs_lint_config/v0.1
docs_root: docs
template: {template}
exceptions: []
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


def init_repo(
    name: str,
    *,
    repo_root: Path | None = None,
    dry_run: bool = True,
    commit: bool = False,
    template: str = "code_repo",
) -> list[str] | None:
    rp = repo_root.expanduser().resolve() if repo_root else repo_path(name)
    if not rp.exists():
        print(f"  ERROR: {rp} not found")
        return None
    # Guard against accidental writes to system paths
    _HOME = Path.home().resolve()
    _DANGER = (
        rp == _HOME
        or rp == _HOME.parent
        or len(rp.parts) <= 1
        or (len(rp.parts) == 2 and rp.drive and rp.parts[1] == "\\")  # Windows root C:\
    )
    if _DANGER:
        print(f"  ERROR: {rp} is a system path — pass a project subdirectory")
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

    # Template extra dirs
    for rel_dir in PROJECT_TYPES.get(template, {}).get("docs_dirs", []):
        d = rp / rel_dir
        if not d.exists():
            if not dry_run:
                ensure_dir(d)
            print(f"  {action}: {rel_dir}/ (from template {template})")
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

    # .claude/rules/docs-lint.yaml
    docs_lint_cfg = rp / ".claude" / "rules" / "docs-lint.yaml"
    if not docs_lint_cfg.exists():
        if not dry_run:
            docs_lint_cfg.parent.mkdir(parents=True, exist_ok=True)
            docs_lint_cfg.write_text(
                DOCS_LINT_CONFIG.format(template=template),
                encoding="utf-8",
            )
        print(f"  {action}: .claude/rules/docs-lint.yaml")
        changes.append(".claude/rules/docs-lint.yaml")

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

    # .gitignore — create if missing, append missing entries
    gi = rp / ".gitignore"
    gi_content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    _gi_entries = [
        ("docs/.artifacts/", "# Documentation artifacts"),
        (".h2t/lint-before.json", "# docs-lint temp files"),
        (".h2t/lint-after.json", None),
    ]
    for gi_entry, gi_comment in _gi_entries:
        if gi_entry not in gi_content:
            if not dry_run:
                with open(gi, "a", encoding="utf-8") as f:
                    if gi_comment:
                        f.write(f"\n{gi_comment}\n")
                    f.write(f"{gi_entry}\n")
                gi_content += f"\n{gi_entry}\n"
            print(f"  {action}: .gitignore entry for {gi_entry}")
            if ".gitignore" not in changes:
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
    parser.add_argument("--repo-root", default=None, help="Explicit repo root path; bypasses DEV_ROOT/repo resolution")
    parser.add_argument("--template", default="code_repo", choices=list(PROJECT_TYPES))
    args = parser.parse_args()

    if args.commit and not args.apply:
        print("WARNING: --commit has no effect without --apply")
    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-init [{mode}]: {args.repo}")
    changes = init_repo(
        args.repo,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        dry_run=not args.apply,
        commit=args.commit,
        template=args.template,
    )

    if changes is None:
        sys.exit(1)
    if not changes:
        print("\n  Nothing to do -- all files already exist")
    elif not args.apply:
        print(f"\n  {len(changes)} changes pending. Run with --apply to create.")


if __name__ == "__main__":
    main()
