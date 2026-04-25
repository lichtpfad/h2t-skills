#!/usr/bin/env python3
"""Scaffold a new project directory in h2t ecosystem.

Usage:
  scaffold_project.py create --id X --type TYPE --stack S --dir D [--description T] [--dry-run]
  scaffold_project.py github --github OWNER/REPO --source PATH [--description T] [--private]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


GITIGNORE_TEMPLATES: dict[str, str] = {
    "python": """\
.venv/
__pycache__/
*.pyc
*.pyo
*.pyd
dist/
build/
*.egg-info/
.env
.env.*
""",
    "js": """\
node_modules/
dist/
.env
.env.*
*.log
.DS_Store
""",
    "ts": """\
node_modules/
dist/
.env
.env.*
*.log
*.js.map
.DS_Store
""",
    "rust": """\
target/
.env
.env.*
""",
    "none": """\
.env
.env.*
*.log
""",
}

DCC_GITIGNORE = """\
*.cache
*.bak
Backup/
.env
.env.*
"""

CLAUDE_MD_TEMPLATE = """\
# {id}

## What

{description}

## Stack

{stack_display}

## Commands

```bash
# TODO: fill in
```
"""

README_TEMPLATE = "# {id}\n\n{description}\n"

DIR_STRUCTURE: dict[str, list[str]] = {
    "code": ["src", "tests", "docs"],
    "docs": ["docs", "research"],
    "dcc": ["assets", "scripts", "exports"],
    "directory": [],
}


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def cmd_create(args: argparse.Namespace) -> dict:
    base = Path(args.dir).expanduser().resolve()
    project_dir = base / args.id
    type_base = args.type.split("-")[0]  # "code-github" -> "code"
    dirs = DIR_STRUCTURE.get(type_base, [])
    is_git = args.type in ("code-github", "code-local")

    if args.dry_run:
        items = [f"mkdir {project_dir}"]
        items += [f"mkdir {project_dir / d}" for d in dirs]
        items.append(f"write {project_dir / '.gitignore'}")
        items.append(f"write {project_dir / 'README.md'}")
        items.append(f"write {project_dir / 'CLAUDE.md'}")
        if is_git:
            items.append(f"git init {project_dir}")
            items.append("initial commit (chore: initial scaffold)")
        return {"status": "dry-run", "path": str(project_dir), "would_create": items}

    # Check if already exists
    if project_dir.exists():
        return {"status": "exists", "path": str(project_dir),
                "message": f"Directory {project_dir} already exists"}

    project_dir.mkdir(parents=True)
    actions = [f"Created {project_dir}"]

    for d in dirs:
        (project_dir / d).mkdir(exist_ok=True)
        actions.append(f"Created {project_dir / d}")

    # .gitignore
    if type_base == "dcc":
        gitignore_content = DCC_GITIGNORE
    else:
        gitignore_content = GITIGNORE_TEMPLATES.get(args.stack or "none",
                                                     GITIGNORE_TEMPLATES["none"])
    (project_dir / ".gitignore").write_text(gitignore_content, encoding="utf-8")
    actions.append("Created .gitignore")

    # README.md
    desc = args.description or "TODO"
    (project_dir / "README.md").write_text(
        README_TEMPLATE.format(id=args.id, description=desc), encoding="utf-8"
    )
    actions.append("Created README.md")

    # CLAUDE.md
    stack_display = args.stack if (args.stack and args.stack != "none") else "N/A"
    (project_dir / "CLAUDE.md").write_text(
        CLAUDE_MD_TEMPLATE.format(
            id=args.id, description=desc, stack_display=stack_display
        ),
        encoding="utf-8",
    )
    actions.append("Created CLAUDE.md")

    # git init + initial commit
    if is_git:
        r = _run(["git", "init"], cwd=str(project_dir))
        if r.returncode != 0:
            return {"status": "error", "error": f"git init failed: {r.stderr.strip()}"}
        actions.append("git init")

        _run(["git", "add", "."], cwd=str(project_dir))
        r2 = _run(["git", "commit", "-m", "chore: initial scaffold"], cwd=str(project_dir))
        if r2.returncode == 0:
            actions.append("Initial commit: chore: initial scaffold")
        else:
            actions.append(f"Initial commit skipped: {r2.stderr.strip()}")

    return {"status": "ok", "path": str(project_dir), "actions": actions}


def cmd_github(args: argparse.Namespace) -> dict:
    cmd = [
        "gh", "repo", "create", args.github,
        "--description", args.description or "",
        "--source", args.source,
        "--remote", "origin",
        "--push",
    ]
    if args.private:
        cmd.append("--private")
    else:
        cmd.append("--public")

    r = _run(cmd)
    if r.returncode == 0:
        url = r.stdout.strip() or f"https://github.com/{args.github}"
        return {"status": "ok", "repo": args.github, "url": url}
    return {"status": "error", "error": r.stderr.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold h2t project")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("--id", required=True)
    p_create.add_argument("--type", required=True,
                          choices=["code-github", "code-local", "dcc", "docs", "directory"])
    p_create.add_argument("--stack", default="none",
                          choices=["python", "js", "ts", "rust", "none"])
    p_create.add_argument("--dir", required=True)
    p_create.add_argument("--description", default="")
    p_create.add_argument("--dry-run", action="store_true")

    p_gh = sub.add_parser("github")
    p_gh.add_argument("--github", required=True, help="owner/repo")
    p_gh.add_argument("--description", default="")
    p_gh.add_argument("--source", required=True, help="local project directory")
    p_gh.add_argument("--private", action="store_true")

    args = parser.parse_args()

    if args.cmd == "create":
        result = cmd_create(args)
    elif args.cmd == "github":
        result = cmd_github(args)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
