#!/usr/bin/env python3
"""Apply project registration to repo-mapping.yaml and domains.yaml.

Usage: $H2T_PYTHON apply_registration.py --id X --domain Y --type Z --label L --task-tracker T [--github G] [--stack S] [--cwd P] [--config-root R]
Outputs JSON to stdout.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
except ImportError:
    print(json.dumps({
        "status": "error",
        "error": "ruamel.yaml required. Install: pip install ruamel.yaml into ~/.h2t/venv",
    }))
    sys.exit(1)


def _backup(path: Path) -> None:
    """Create .bak backup of a file."""
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


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
) -> dict:
    """Register project in repo-mapping.yaml and domains.yaml.

    Returns result dict with status and actions list.
    """
    root = Path(config_root) if config_root else Path.home() / ".h2t" / "config"
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

    with open(mapping_path, "w", encoding="utf-8") as f:
        yaml.dump(mapping, f)

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
        if task_tracker != "none":
            existing["task_tracker"] = task_tracker
        actions.append(f"Updated {project_id} in domains.yaml under {domain}")
    else:
        # Add new entry
        new_entry = {"id": project_id, "label": label, "description": ""}
        if task_tracker != "none":
            new_entry["task_tracker"] = task_tracker
        domain_data["projects"].append(new_entry)
        actions.append(f"Added {project_id} to domains.yaml under {domain}")

    with open(domains_path, "w", encoding="utf-8") as f:
        yaml.dump(domains, f)

    # 3. Create .claude/project-id if cwd provided
    if cwd:
        pid_dir = Path(cwd) / ".claude"
        pid_file = pid_dir / "project-id"
        if not pid_file.exists():
            pid_dir.mkdir(parents=True, exist_ok=True)
            pid_file.write_text(project_id + "\n", encoding="utf-8")
            actions.append("Created .claude/project-id")

    return {
        "status": "ok",
        "actions": actions,
        "next_steps": [
            "Next /session-start will recognize this project",
            "Run /h2t:scaffold-project for full setup (CLAUDE.md, milestones, issues)",
        ],
    }


def main():
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
    )

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
