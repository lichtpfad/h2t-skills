"""h2t gather CLI — unified context gatherer replacing per-skill gather.py scripts.

Usage:
    python -m lib.cli.main gather <skill> [--cwd <path>] [--format-briefing]

Supported subcommands:
    gather <skill>  — run context gather for any skill (session-start, handoff, etc.)
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure lib/ is on sys.path for both dev and installed modes.
_root = Path(__file__).resolve().parent.parent.parent
_lib = _root / "lib"
if str(_lib) not in sys.path:
    sys.path.insert(0, str(_lib))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, get_machine_name
from gather.briefing import format_briefing
from eval.session import SkillEval


def _run_gather(skill: str, cwd: str, format_briefing_flag: bool) -> None:
    """Run context gather for any skill. Replicates gather.py main() logic."""
    start = time.monotonic()
    sources_used: list[str] = []
    sources_failed: list[str] = []

    # Layer 0: Identity (always)
    project = identify_project(cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )

    # Layer 1: State (conditional on project type)
    git: dict = {}
    github: dict = {}
    if project.get("type") == "git":
        git = gather_git(cwd)
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")

        if project.get("github"):
            github = gather_github(owner_repo=project["github"])
            sources_used.append("github")

    # Layer 2: Stack detection
    stack = detect_stack(cwd)

    # Layer 3: Previous sessions
    machine = get_machine_name()
    domain = project.get("domain", "dev")
    proj_id = project.get("id", "unknown")
    github_remote = project.get("github") or git.get("owner_repo", "")
    repo_name = github_remote.split("/")[-1] if github_remote else Path(cwd).resolve().name
    sessions = find_session_files(repo_name)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    data = {
        "project": project,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": sessions,
        "machine": machine,
        "user": user,
        "session_id": "",  # set by user after GATE confirmation
        "_meta": {
            "sources_used": sources_used,
            "sources_failed": sources_failed,
            "gather_ms": elapsed_ms,
        },
    }

    if format_briefing_flag:
        briefing, meta = format_briefing(data)
        data["_briefing"] = briefing
        data["_meta"].update(meta)

    # Eval (silent on failure — never crash skill)
    try:
        with SkillEval(skill, domain=domain, project=proj_id) as ev:
            ev.metric(
                "skills.gather_source_success_rate",
                value_num=1.0 - len(sources_failed) / max(len(sources_used), 1),
            )
            ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
    except Exception:
        pass

    output_json(data)


def _cmd_gather(args: argparse.Namespace) -> int:
    if not args.skill:
        print("error: gather requires a skill name (e.g. session-start, handoff)", file=sys.stderr)
        return 2
    _run_gather(
        skill=args.skill,
        cwd=args.cwd,
        format_briefing_flag=args.format_briefing,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="h2t",
        description="h2t unified CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # gather subcommand
    gather_parser = subparsers.add_parser("gather", help="Run context gather for a skill")
    gather_parser.add_argument("skill", nargs="?", default="", help="Skill name (e.g. session-start)")
    gather_parser.add_argument("--cwd", default=".", help="Working directory")
    gather_parser.add_argument("--format-briefing", action="store_true", help="Include formatted briefing in output")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.command == "gather":
        sys.exit(_cmd_gather(args))
    else:
        print(f"error: unknown command '{args.command}'", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
