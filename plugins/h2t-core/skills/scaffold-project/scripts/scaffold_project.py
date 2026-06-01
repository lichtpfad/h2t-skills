#!/usr/bin/env python3
"""Scaffold a new project directory in h2t ecosystem.

Usage:
  scaffold_project.py create --id X --type TYPE --stack S --dir D [--description T] [--dry-run]
  scaffold_project.py github --github OWNER/REPO --source PATH [--description T] [--private]
"""
import argparse
import json
import os
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

TYPE_TO_TEMPLATE = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}


def template_for_type(project_type: str) -> str:
    return TYPE_TO_TEMPLATE.get(project_type, "code_repo")


def write_setup_report(
    *,
    project_dir: Path,
    project_id: str,
    template: str,
    status: str,
    actions: list[str],
) -> dict:
    import datetime

    report = {
        "schema": "h2t_project_setup_report/v0.1",
        "schema_version": "0.1",
        "producer": "h2t-core/scaffold-project",
        "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
        "project_id": project_id,
        "template": template,
        "repo_root": str(project_dir),
        "status": status,
        "actions": actions,
        "safe_next_action": "Run h2t-core:session-start in the project directory",
        "evidence": {
            "project_dir_exists": project_dir.exists(),
        },
    }
    out = project_dir / ".h2t" / "project-setup-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return report


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def cmd_create(args: argparse.Namespace) -> dict:
    base = Path(args.dir).expanduser().resolve()
    project_dir = base / args.id
    type_base = args.type.split("-")[0]  # "code-github" -> "code"
    template = template_for_type(args.type)
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

    if not args.dry_run:
        di = run_docs_init(args.id, project_dir, template=template)
        actions.append(f"docs-init: {di['status']}")
        if di["status"] == "error":
            return {"status": "error", "error": f"docs-init failed: {di['error']}"}

    if is_git and not args.dry_run:
        ih = install_hooks(project_dir)
        actions.append(f"install-hooks: {ih['status']}")

    if not args.dry_run:
        write_setup_report(
            project_dir=project_dir,
            project_id=args.id,
            template=template,
            status="ok",
            actions=actions,
        )

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
        repo_name_only = args.github.split("/")[-1] if "/" in args.github else args.github
        sl = run_sync_labels(repo_name_only)
        return {"status": "ok", "repo": args.github, "url": url, "sync_labels": sl["status"]}
    return {"status": "error", "error": r.stderr.strip()}


_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))


def run_docs_init(repo_name: str, project_dir: Path, *, template: str = "code_repo") -> dict:
    init_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-init" / "scripts" / "init.py"
    if not init_script.exists():
        return {"status": "skip", "reason": "docs-init script not found"}
    r = subprocess.run(
        [
            sys.executable,
            str(init_script),
            repo_name,
            "--repo-root",
            str(project_dir),
            "--template",
            template,
            "--apply",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()[:400]}
    return {"status": "error", "error": r.stderr.strip()[:400] or r.stdout.strip()[:400]}


def run_sync_labels(repo_name: str) -> dict:
    if not repo_name:
        return {"status": "skip", "reason": "no repo name"}
    sync_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-sync-labels" / "scripts" / "sync_labels.py"
    if not sync_script.exists():
        return {"status": "skip", "reason": "sync_labels script not found"}
    r = subprocess.run(
        [sys.executable, str(sync_script), repo_name, "--apply"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()[:200]}
    return {"status": "error", "error": r.stderr.strip()[:200]}


_HOOK_BASE = "~/.claude/plugins/cache/lichtpfad/h2t-core/latest"

_HOOK_ENTRIES = {
    "Stop": [
        {
            "matcher": "",
            "command": f"{_HOOK_BASE}/hooks-handlers/on-stop",
        }
    ],
}


def install_hooks(project_dir: Path) -> dict:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    else:
        data = {}
    hooks = data.setdefault("hooks", {})
    for event, entries in _HOOK_ENTRIES.items():
        existing = hooks.setdefault(event, [])
        for entry in entries:
            if not any(entry["command"] in h.get("command", "") for h in existing):
                existing.append(entry)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "ok", "path": str(settings_path)}


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
