#!/usr/bin/env python3
"""Context gatherer for dev-session-start skill.

Usage: $H2T_PYTHON gather.py [--memory-dir <path>] [--cwd <path>]
Outputs JSON to stdout.
"""

import argparse
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, extract_session_id, get_machine_name
from gather.eval import record_eval, estimate_tokens


def read_project_filter(cwd: str = ".") -> str | None:
    pid_file = Path(cwd) / ".claude" / "project-id"
    if pid_file.exists():
        return pid_file.read_text().strip() or None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--format-briefing", action="store_true")
    args = parser.parse_args()

    start = time.monotonic()
    sources_used = []
    sources_failed = []

    # Layer 0 — Identity
    project = identify_project(args.cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )
    sources_used.append("user")

    # Layer 1 — State (conditional on project type)
    git = {}
    if project["type"] == "git":
        git = gather_git(args.cwd)
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")

    stack = detect_stack(args.cwd)
    sources_used.append("stack")

    # Layer 2 — Work Context (conditional on github)
    github = {}
    github_remote = project.get("github") or git.get("owner_repo", "")
    if github_remote:
        project_label = read_project_filter(args.cwd)
        github = gather_github(github_remote, project_label=project_label)
        sources_used.append("github")
        if not github.get("issues") and not github.get("milestones"):
            sources_failed.append("github")

    # Layer 2 — Sessions
    repo_name = github_remote.split("/")[-1] if github_remote else Path(args.cwd).resolve().name
    session_files = find_session_files(repo_name)
    sources_used.append("sessions")

    # Metadata
    session_id = extract_session_id(args.memory_dir) if args.memory_dir else ""
    machine = get_machine_name()

    result = {
        "project": project,
        "user": user,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": session_files,
        "session_id": session_id,
        "machine": machine,
    }

    if args.format_briefing:
        from gather.briefing import format_briefing as fmt_briefing
        briefing_md, briefing_meta = fmt_briefing(result)
        result["_briefing"] = briefing_md
        result["_meta"] = briefing_meta

    duration_ms = int((time.monotonic() - start) * 1000)

    # Eval — record gather metrics
    record_eval("dev-session-start", {
        "duration_ms": duration_ms,
        "layers": [0, 1, 2],
        "sources_used": sources_used,
        "sources_failed": sources_failed,
        "context_tokens_estimate": estimate_tokens(result),
        "project_type": project["type"],
        "project_domain": project.get("domain", ""),
    }, plugin_version="2.12.1")

    output_json(result)


if __name__ == "__main__":
    main()
