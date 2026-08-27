#!/usr/bin/env python3
"""Scaffold a new project directory in h2t ecosystem.

Usage:
  scaffold_project.py create --id X --type TYPE --stack S --dir D [--description T] [--dry-run]
  scaffold_project.py github --github OWNER/REPO --source PATH [--description T] [--private]
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

# lib path: source sibling plugins/h2t-dev/lib OR cache lichtpfad/h2t-dev/{latest}/lib
_SCAFFOLD_SCRIPT = Path(__file__).resolve()
_PLUGIN_ROOT_EARLY = _SCAFFOLD_SCRIPT.parents[3]
_H2T_DEV_LIB = _PLUGIN_ROOT_EARLY.parent / "h2t-dev" / "lib"  # source
if not _H2T_DEV_LIB.exists():
    # Cache: go up to lichtpfad/, find latest h2t-dev version
    _cache_base = _PLUGIN_ROOT_EARLY.parent.parent / "h2t-dev"
    if _cache_base.exists():
        _versions = sorted([p for p in _cache_base.iterdir() if p.is_dir()], reverse=True)
        for _v in _versions:
            if (_v / "lib").exists():
                _H2T_DEV_LIB = _v / "lib"
                break
if _H2T_DEV_LIB.exists() and str(_H2T_DEV_LIB) not in sys.path:
    sys.path.insert(0, str(_H2T_DEV_LIB))

try:
    from docs.project_types import PROJECT_TYPES, SCAFFOLD_TYPE_TO_TEMPLATE
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    _PROJECT_TYPES_AVAILABLE = False
    PROJECT_TYPES = {}
    SCAFFOLD_TYPE_TO_TEMPLATE = {}


_H2T_LINT_ENTRIES = """\
# docs-lint temp files
.h2t/lint-before.json
.h2t/lint-after.json
"""

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
""" + _H2T_LINT_ENTRIES,
    "js": """\
node_modules/
dist/
.env
.env.*
*.log
.DS_Store
""" + _H2T_LINT_ENTRIES,
    "ts": """\
node_modules/
dist/
.env
.env.*
*.log
*.js.map
.DS_Store
""" + _H2T_LINT_ENTRIES,
    "rust": """\
target/
.env
.env.*
""" + _H2T_LINT_ENTRIES,
    "none": """\
.env
.env.*
*.log
""" + _H2T_LINT_ENTRIES,
}

DCC_GITIGNORE = """\
*.cache
*.bak
Backup/
.env
.env.*
""" + _H2T_LINT_ENTRIES

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

# Local fallbacks — exact copy of old DIR_STRUCTURE/TYPE_TO_TEMPLATE
# Used only when project_types lib is unavailable (stale cache run)
_DIR_STRUCTURE_FALLBACK: dict[str, list[str]] = {
    "code": ["src", "tests", "docs"],
    "docs": ["docs", "research"],
    "dcc": ["assets", "scripts", "exports"],
    "directory": [],
}

_TYPE_TO_TEMPLATE_FALLBACK: dict[str, str] = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}


def template_for_type(project_type: str) -> str:
    mapping = SCAFFOLD_TYPE_TO_TEMPLATE if _PROJECT_TYPES_AVAILABLE else _TYPE_TO_TEMPLATE_FALLBACK
    return mapping.get(project_type, "code_repo")


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


_STRUCTURE_YAML_TEMPLATE = """\
# Structure guard configuration — managed by h2t-core:scaffold-project
# Used by plugins/h2t-core/hooks-handlers/structure_guard.py

# An unlisted top-level directory is BLOCKED, not warned about. Add a new one
# here before writing into it — including any not needed on day one.
allowed_root_dirs:
  - src/
  - tests/
  - docs/
  - scripts/
  - .h2t/
  - .claude/
  - .github/

# Sections under docs/. A NEW first-level section and a NEW loose file in the
# docs/ root are BLOCKED; a directory that already exists is allowed by existing,
# so this list never has to grow to match the repo. Add a section here only when
# you mean to introduce one.
allowed_doc_dirs:
  - superpowers/
  - adr/
  - reports/
  - archive/

# A blacklist of shapes — the obvious cases only. It can never be the main
# defence: it has to name what an agent might invent, and the next write invents
# something else. The two allowlists above are the defence.
forbidden_patterns:
  - "tmp_*"
  - "*_tmp.*"
  - "*_v2.*"
  - "*_copy.*"
  - "*_backup.*"

plan_dirs:
  - path: "docs/superpowers/plans/"
    pattern: "^\\d{4}-\\d{2}-\\d{2}-.+\\.md$"

# Dirs whose Markdown files must open with a --- frontmatter block.
# Presence-only block (structure_guard); field-level validation is docs-lint's job.
frontmatter_dirs:
  - docs/superpowers/plans/
  - docs/superpowers/specs/
  - docs/adr/
"""


def write_structure_yaml(project_dir: Path) -> bool:
    """Write .h2t/structure.yaml if it doesn't exist. Returns True if written."""
    yaml_path = project_dir / ".h2t" / "structure.yaml"
    if yaml_path.exists():
        return False
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(_STRUCTURE_YAML_TEMPLATE, encoding="utf-8")
    return True


def cmd_create(args: argparse.Namespace) -> dict:
    base = Path(args.dir).expanduser().resolve()
    project_dir = base / args.id
    type_base = args.type.split("-")[0]
    template = template_for_type(args.type)
    if _PROJECT_TYPES_AVAILABLE:
        dirs = PROJECT_TYPES.get(template, {}).get("root_dirs", [])
    else:
        dirs = _DIR_STRUCTURE_FALLBACK.get(type_base, [])
    is_git = args.type in ("code-github", "code-local")

    if args.dry_run:
        items = [f"mkdir {project_dir}"] if not project_dir.exists() else []
        for d in dirs:
            if not (project_dir / d).exists():
                items.append(f"mkdir {project_dir / d}")
        for fname in (".gitignore", "README.md", "CLAUDE.md"):
            if not (project_dir / fname).exists():
                items.append(f"write {project_dir / fname}")
        if is_git and not (project_dir / ".git").exists():
            items.append(f"git init {project_dir}")
            items.append("initial commit (chore: initial scaffold) — new files only")
        return {
            "status": "dry-run",
            "merge": project_dir.exists(),
            "path": str(project_dir),
            "would_create": items,
        }

    if project_dir.exists() and not args.merge:
        return {"status": "exists", "path": str(project_dir),
                "message": f"Directory {project_dir} already exists"}

    is_merge = project_dir.exists() and args.merge
    if not is_merge:
        project_dir.mkdir(parents=True)
        actions = [f"Created {project_dir}"]
        status_key = "ok"
    else:
        actions = [f"Merging into existing {project_dir}"]
        status_key = "merged"

    created_files: list[str] = []

    for d in dirs:
        dp = project_dir / d
        if dp.is_dir():
            continue
        if dp.exists():
            actions.append(f"Skipped {d}/ — path exists as file, not dir")
            continue
        dp.mkdir(exist_ok=True)
        actions.append(f"Created {project_dir / d}")

    gi_path = project_dir / ".gitignore"
    if not gi_path.exists():
        gi_content = DCC_GITIGNORE if type_base == "dcc" else GITIGNORE_TEMPLATES.get(
            args.stack or "none", GITIGNORE_TEMPLATES["none"]
        )
        gi_path.write_text(gi_content, encoding="utf-8")
        actions.append("Created .gitignore")
        created_files.append(".gitignore")

    desc = args.description or "TODO"
    readme_path = project_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(README_TEMPLATE.format(id=args.id, description=desc), encoding="utf-8")
        actions.append("Created README.md")
        created_files.append("README.md")

    claude_path = project_dir / "CLAUDE.md"
    if not claude_path.exists():
        stack_display = args.stack if (args.stack and args.stack != "none") else "N/A"
        claude_path.write_text(
            CLAUDE_MD_TEMPLATE.format(id=args.id, description=desc, stack_display=stack_display),
            encoding="utf-8",
        )
        actions.append("Created CLAUDE.md")
        created_files.append("CLAUDE.md")

    # Generate .h2t/structure.yaml (idempotent — skip if exists)
    if write_structure_yaml(project_dir):
        actions.append("Created .h2t/structure.yaml")
        if is_git:
            created_files.append(".h2t/structure.yaml")

    if is_git:
        needs_init = not (project_dir / ".git").exists()
        if needs_init:
            r = _run(["git", "init"], cwd=str(project_dir))
            if r.returncode != 0:
                return {"status": "error", "error": f"git init failed: {r.stderr.strip()}"}
            # Force main branch regardless of system default
            _run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=str(project_dir))
            actions.append("git init (branch: main)")

        if is_merge:
            if created_files:
                _run(["git", "add", "--"] + created_files, cwd=str(project_dir))
                r2 = _run(["git", "commit", "-m", "chore: scaffold merge — add missing files"],
                          cwd=str(project_dir))
                if r2.returncode == 0:
                    actions.append("Committed scaffold files (merge — new files only)")
                else:
                    actions.append(f"Commit skipped: {r2.stderr.strip()}")
            else:
                actions.append("No new files — commit skipped")
        else:
            _run(["git", "add", "."], cwd=str(project_dir))
            r2 = _run(["git", "commit", "-m", "chore: initial scaffold"], cwd=str(project_dir))
            if r2.returncode == 0:
                actions.append("Initial commit: chore: initial scaffold")
            else:
                actions.append(f"Initial commit skipped: {r2.stderr.strip()}")

    di = run_docs_init(args.id, project_dir, template=template)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di.get('error', '')}"}
    if di["status"] == "ok":
        _critical_files = ["docs/README.md"]
        _critical_dirs = [
            "docs/adr", "docs/reports",
            "docs/superpowers/specs", "docs/superpowers/plans",
        ]
        _missing = [
            p for p in _critical_files if not (project_dir / p).is_file()
        ] + [
            p for p in _critical_dirs if not (project_dir / p).is_dir()
        ]
        if _missing:
            return {
                "status": "error",
                "error": f"docs-init reported ok but critical paths missing: {_missing}",
            }
    if di["status"] == "skip":
        actions.append("WARNING: docs-init skipped — docs structure may be incomplete")

    if is_git:
        ih = install_hooks(project_dir)
        actions.append(f"install-hooks: {ih['status']}")

    write_setup_report(
        project_dir=project_dir,
        project_id=args.id,
        template=template,
        status=status_key,
        actions=actions,
    )

    return {"status": status_key, "path": str(project_dir), "actions": actions}


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
# There was a `_DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))` here, defined and
# never read — the sibling-plugin lookup below uses _H2T_DEV_ROOT, which is derived rather
# than configured. Removed in the #434 sweep: a hardcoded path nothing uses still answers grep,
# and it sized part of that issue against code that could not run.


def _find_h2t_dev_root() -> Path | None:
    """Find h2t-dev plugin root — works from source tree and installed cache.

    Source layout:  plugins/h2t-core/../h2t-dev  (sibling under plugins/)
    Cache layout:   cache/lichtpfad/h2t-core/{ver}/ → cache/lichtpfad/h2t-dev/{latest}/
    """
    # Source: _PLUGIN_ROOT.parent is plugins/
    candidate = _PLUGIN_ROOT.parent / "h2t-dev"
    if (candidate / "skills").exists():
        return candidate
    # Cache: _PLUGIN_ROOT.parent is h2t-core/ (all versions), go up to lichtpfad/
    cache_base = _PLUGIN_ROOT.parent.parent / "h2t-dev"
    if cache_base.exists():
        versions = sorted([p for p in cache_base.iterdir() if p.is_dir()], reverse=True)
        for v in versions:
            if (v / "skills").exists():
                return v
    return None


_H2T_DEV_ROOT = _find_h2t_dev_root()


def run_docs_init(repo_name: str, project_dir: Path, *, template: str = "code_repo") -> dict:
    if _H2T_DEV_ROOT is None:
        return {"status": "skip", "reason": "h2t-dev plugin not found"}
    init_script = _H2T_DEV_ROOT / "skills" / "docs-init" / "scripts" / "init.py"
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
    if _H2T_DEV_ROOT is None:
        return {"status": "skip", "reason": "h2t-dev plugin not found"}
    sync_script = _H2T_DEV_ROOT / "skills" / "docs-sync-labels" / "scripts" / "sync_labels.py"
    if not sync_script.exists():
        return {"status": "skip", "reason": "sync_labels script not found"}
    r = subprocess.run(
        [sys.executable, str(sync_script), repo_name, "--apply"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return {"status": "ok", "output": r.stdout.strip()[:200]}
    return {"status": "error", "error": r.stderr.strip()[:200]}


# `h2t-hook <name>`, not a path into the plugin cache. This dict is written into somebody
# else's `.claude/settings.json`, which is normally committed: an absolute path under one
# home directory is wrong on the next machine, and the `latest` junction it used to point at
# is refreshed only by `install-h2t-ops`, never by `/plugin marketplace update`. The launcher
# resolves the handler when the hook fires, through the same ladder the entry points use.
_HOOK_ENTRIES = {
    "Stop": [
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": "h2t-hook on-stop"}],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Bash(git commit*)",
            "hooks": [
                {"type": "command", "command": "h2t-hook post-git-commit-docs-lint"}
            ],
        }
    ],
}


def _entry_commands(entry: dict) -> list[str]:
    return [
        command.get("command", "")
        for command in entry.get("hooks", [])
        if command.get("type") == "command"
    ]


def ensure_hook_report_cache_ignored(project_dir: Path) -> None:
    exclude = project_dir / ".git" / "info" / "exclude"
    if not exclude.parent.exists():
        return
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    line = ".h2t/lifecycle/*.json"
    if line not in existing.splitlines():
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        exclude.write_text(existing + suffix + line + "\n", encoding="utf-8")


def install_hooks(project_dir: Path) -> dict:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    hooks = data.setdefault("hooks", {})
    for event, entries in _HOOK_ENTRIES.items():
        existing = hooks.setdefault(event, [])
        for entry in entries:
            desired_commands = set(_entry_commands(entry))
            already_present = any(
                desired_commands.intersection(_entry_commands(existing_entry))
                for existing_entry in existing
            )
            if not already_present:
                existing.append(entry)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    ensure_hook_report_cache_ignored(project_dir)
    return {"status": "ok", "path": str(settings_path)}


def _print_json(payload) -> None:
    """The report goes out as UTF-8 whatever the console codepage says.

    Windows Python encodes a piped stdout with the ANSI codepage, so the em dashes in
    these action strings left as cp1252 (byte 0x97) and every caller decoding UTF-8 got
    a decode error in place of the report — measured on windows-latest, not reasoned.
    lib/gather/runner.py:48 solves the same problem the same way.
    """
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    out.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    out.flush()
    out.detach()  # leave the underlying buffer open


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
    p_create.add_argument("--merge", action="store_true",
                          help="Supplement existing directory — idempotent, skip existing files")

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

    _print_json(result)


if __name__ == "__main__":
    main()
