#!/usr/bin/env python3
"""Apply project registration to repo-mapping.yaml and domains.yaml.

Usage: $H2T_PYTHON apply_registration.py --id X --domain Y --type Z --label L --task-tracker T [--github G] [--stack S] [--cwd P] [--config-root R]
Outputs JSON to stdout.
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

from h2t_ops.core import backups, paths, store

try:
    from ruamel.yaml import YAML
except ImportError:
    # No exit at import: that turned one missing package into a pytest INTERNALERROR for the
    # whole directory (#429). main() reports it, which is the CLI's contract.
    YAML = None


def _resolve_config_root(config_root: str | None = None) -> tuple[Path, bool]:
    """(root, named): the config place, or a directory the caller named (--config-root).

    A named directory is not the config place to store — it classifies as tmp or elsewhere —
    so it is written with dest=True, which still refuses a path inside a package place (R43).
    One that is config_dir() by realpath is the config place itself. H2T_CONFIG_ROOT is not
    read (R5).
    """
    default = paths.config_dir()
    if not config_root:
        return default, False
    root = paths.expand_user_dest(config_root)
    if os.path.realpath(root) == os.path.realpath(default):
        return default, False
    return root, True


def _backup(path: Path) -> None:
    """Copy into state/backups before the edit (R14); config/ keeps no *.bak."""
    if path.exists():
        backups.save_backup(path)


def _dump(path: Path, yaml, doc, *, named: bool) -> None:
    buf = io.StringIO()
    yaml.dump(doc, buf)
    store.replace(path, buf.getvalue(), place="config", dest=named)


def apply_registration(
    project_id: str,
    domain: str,
    project_type: str,
    label: str,
    task_tracker: str = "none",
    github: str | None = None,
    stack: str | None = None,
    cwd: str | None = None,
    config_root: str | None = None,
    description: str = "",
) -> dict:
    """Register project in repo-mapping.yaml and domains.yaml.

    Returns result dict with status and actions list.
    """
    root, named = _resolve_config_root(config_root)
    mapping_path = root / "repo-mapping.yaml"
    domains_path = root / "domains.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    actions = []

    # 1. Update repo-mapping.yaml
    _backup(mapping_path)
    mapping = yaml.load(mapping_path) if mapping_path.exists() else {}
    if mapping is None:
        mapping = {}

    if "mappings" not in mapping:
        mapping["mappings"] = {}
    if "cwd_patterns" not in mapping:
        mapping["cwd_patterns"] = {}

    domain_project = f"{domain}/{project_id}"

    if project_type in ("git", "git-local"):
        # Use repo name (last part of github or project_id) as key
        repo_key = github.split("/")[-1] if github else project_id
        mapping["mappings"][repo_key] = domain_project
        actions.append(f"Added {repo_key} to repo-mapping.yaml mappings")
    else:
        # directory type → cwd_patterns
        if cwd:
            normalized = cwd.replace("\\", "/")
            mapping["cwd_patterns"][normalized] = domain_project
            actions.append(f"Added {normalized} to repo-mapping.yaml cwd_patterns")
        else:
            actions.append("Skipped cwd_patterns — no --cwd provided for directory type")

    _dump(mapping_path, yaml, mapping, named=named)

    # 2. Update domains.yaml
    _backup(domains_path)
    domains = yaml.load(domains_path) if domains_path.exists() else {}
    if domains is None:
        domains = {}

    if "domains" not in domains:
        domains["domains"] = {}
    if domain not in domains["domains"]:
        domains["domains"][domain] = {"label": domain.capitalize(), "projects": []}

    domain_data = domains["domains"][domain]
    if "projects" not in domain_data:
        domain_data["projects"] = []

    # Check if project already exists in domain
    existing = None
    for proj in domain_data["projects"]:
        if proj.get("id") == project_id:
            existing = proj
            break

    if existing:
        # Update existing entry
        existing["label"] = label
        # Only fill a blank one: a description written by hand outranks a re-registration.
        if description and not existing.get("description"):
            existing["description"] = description
        if task_tracker != "none":
            existing["task_tracker"] = task_tracker
        actions.append(f"Updated {project_id} in domains.yaml under {domain}")
    else:
        # Add new entry
        new_entry = {"id": project_id, "label": label, "description": description}
        if task_tracker != "none":
            new_entry["task_tracker"] = task_tracker
        domain_data["projects"].append(new_entry)
        actions.append(f"Added {project_id} to domains.yaml under {domain}")

    _dump(domains_path, yaml, domains, named=named)

    # 3. Create .claude/project-id if cwd provided — create only: an existing file is kept
    # (§7.1 "create if absent", R32).
    if cwd:
        try:
            # domain/project, not the bare id: gather.project reads this file first now,
            # and a bare id makes the domain a lookup in the very config a fresh clone
            # does not have. Existing bare-id files still resolve through domains.yaml.
            store.repo(cwd, "h2t-project-register").create(".claude/project-id", domain_project + "\n")
            actions.append("Created .claude/project-id")
        except store.AlreadyExists:
            pass

    return {
        "status": "ok",
        "actions": actions,
        "next_steps": [
            "Next /session-start will recognize this project",
            "Run /h2t-core:scaffold-project for full setup (CLAUDE.md, milestones, issues)",
        ],
    }


def main():
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if YAML is None:
        print(json.dumps({
            "status": "error",
            "error": "ruamel.yaml required. Install it for the interpreter running this "
                     "script: uv pip install ruamel.yaml",
        }))
        sys.exit(1)
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--type", required=True, dest="project_type")
    parser.add_argument("--label", required=True)
    parser.add_argument("--task-tracker", default="none")
    parser.add_argument("--github", default=None)
    parser.add_argument("--stack", default=None)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--config-root", default=None)
    parser.add_argument(
        "--description", default="",
        help="one-line summary; feeds LLM task classification in domains.yaml",
    )
    args = parser.parse_args()

    result = apply_registration(
        project_id=args.id,
        domain=args.domain,
        project_type=args.project_type,
        label=args.label,
        task_tracker=args.task_tracker,
        github=args.github,
        stack=args.stack,
        cwd=args.cwd,
        config_root=args.config_root,
        description=args.description,
    )

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
