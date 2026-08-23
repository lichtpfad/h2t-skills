"""
report.py — Stage 5 of /project-audit pipeline.
Updates projects.yaml docs fields after audit.

Usage:
    python report.py <project_id> [--field key=value ...] [--projects-yaml <path>]

Example:
    python report.py h2t-snap --field claude_md=true --field readme=true --field marketing_docs=true
"""

import argparse
import json
import re
import sys
from pathlib import Path


def update_project_docs(yaml_path: Path, project_id: str, fields: dict[str, bool]) -> bool:
    """Update docs fields for a project in projects.yaml using regex (no PyYAML needed)."""
    text = yaml_path.read_text(encoding="utf-8")

    # Find the project block by id
    # Pattern: "- id: {project_id}" followed by its content until next "- id:" or end
    pattern = rf"(- id: {re.escape(project_id)}\n)(.*?)(?=\n  - id:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        print(json.dumps({"error": f"Project '{project_id}' not found in {yaml_path}"}))
        return False

    block = match.group(0)
    updated_block = block

    for field, value in fields.items():
        val_str = "true" if value else "false"
        # Try to update existing field
        field_pattern = rf"({field}:\s*)(true|false)"
        if re.search(field_pattern, updated_block):
            updated_block = re.sub(field_pattern, rf"\g<1>{val_str}", updated_block)
        # If field doesn't exist in docs block, skip (don't add new fields via regex)

    if updated_block != block:
        text = text.replace(block, updated_block)
        yaml_path.write_text(text, encoding="utf-8")

    # Build report
    report = {
        "project_id": project_id,
        "updated_fields": {k: v for k, v in fields.items()},
        "yaml_path": str(yaml_path),
    }
    return True


def main():
    import json

    parser = argparse.ArgumentParser(description="Update projects.yaml after audit")
    parser.add_argument("project_id", help="Project ID from projects.yaml")
    parser.add_argument("--field", action="append", default=[], help="key=value pairs (e.g. claude_md=true)")
    parser.add_argument(
        "--projects-yaml",
        default="C:/dev/h2t-landings/projects.yaml",
        help="Path to projects.yaml",
    )
    args = parser.parse_args()

    fields = {}
    for f in args.field:
        k, v = f.split("=", 1)
        fields[k] = v.lower() in ("true", "1", "yes")

    if not fields:
        print(json.dumps({"error": "No fields specified"}))
        sys.exit(1)

    yaml_path = Path(args.projects_yaml)
    if not yaml_path.exists():
        print(json.dumps({"error": f"File not found: {yaml_path}"}))
        sys.exit(1)

    ok = update_project_docs(yaml_path, args.project_id, fields)
    result = {
        "success": ok,
        "project_id": args.project_id,
        "fields": {k: v for k, v in fields.items()},
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
