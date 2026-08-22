#!/usr/bin/env python3
"""Context gatherer for session-start v3.

Usage: $H2T_PYTHON gather.py --cwd <path> [--format-briefing]
Outputs JSON to stdout. Imports from lib/ (co-located in cache by update-plugin.sh).

In cache layout:
  <plugin_root>/
    skills/session-start/scripts/gather.py   <- this file
    lib/                                     <- copied by update-plugin.sh
      activity/
      eval/
      gather/

PLUGIN_ROOT = parent.parent.parent.parent of this file
"""

import argparse
import json
import sys
import time
from pathlib import Path

# lib/ is co-located in plugin cache root (4 levels up from this file).
# In dev/smoke-test mode, PLUGIN_ROOT/lib doesn't exist yet (before update-plugin.sh);
# fall back to repo_root/lib (PLUGIN_ROOT is plugins/h2t-core/ → repo is 2 levels up).
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_cache_lib = PLUGIN_ROOT / "lib"
_repo_lib = PLUGIN_ROOT.parent.parent / "lib"
for _lib in [_cache_lib, _repo_lib]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_latest_session_index, find_session_files, get_machine_name
from gather.briefing import format_briefing
from eval.session import SkillEval


def _print_text(text: str) -> None:
    """Write plain text to stdout, UTF-8 safe on Windows (avoids cp1252 crash)."""
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    out.write(text if text.endswith("\n") else text + "\n")
    out.flush()
    out.detach()  # don't close underlying buffer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--format-briefing", action="store_true")
    parser.add_argument(
        "--briefing-only",
        action="store_true",
        help="Emit hook-format 'BRIEFING:/GATHER_META:' text instead of full JSON (small, UTF-8 safe)",
    )
    args = parser.parse_args()

    start = time.monotonic()
    sources_used: list[str] = []
    sources_failed: list[str] = []

    # Layer 0: Identity (always)
    project = identify_project(args.cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )

    # Layer 1: State (conditional on project type)
    git: dict = {}
    github: dict = {}
    if project.get("type") == "git":
        git = gather_git(args.cwd)
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")

        if project.get("github"):
            github = gather_github(owner_repo=project["github"])
            sources_used.append("github")

    # Layer 2: Stack detection
    stack = detect_stack(args.cwd)

    # Layer 3: Previous sessions
    machine = get_machine_name()
    domain = project.get("domain", "dev")
    proj_id = project.get("id", "unknown")
    github_remote = project.get("github") or git.get("owner_repo", "")
    repo_name = github_remote.split("/")[-1] if github_remote else Path(args.cwd).resolve().name
    # project.id first: repo-mapping.yaml folds several repositories into one project
    # (DocGraph and SpecDesigner onto docgraph), and the handoff writer keys the directory
    # by project.id — so reading by repo name alone missed every handoff for the 20 of 38
    # mapped repos whose name differs from their project (#377).
    sessions = find_session_files(proj_id, repo_name)
    latest_session = find_latest_session_index(proj_id, repo_name)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    data = {
        "project": project,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": sessions,
        "latest_session": latest_session,
        "machine": machine,
        "user": user,
        "session_id": "",  # set by user after GATE confirmation
        "_meta": {
            "sources_used": sources_used,
            "sources_failed": sources_failed,
            "gather_ms": elapsed_ms,
        },
    }

    if args.format_briefing or args.briefing_only:
        briefing, meta = format_briefing(data)
        data["_briefing"] = briefing
        data["_meta"].update(meta)

    # Eval (silent on failure — never crash skill)
    try:
        with SkillEval("session-start", domain=domain, project=proj_id) as ev:
            ev.metric(
                "skills.gather_source_success_rate",
                value_num=1.0 - len(sources_failed) / max(len(sources_used), 1),
            )
            ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
    except Exception:
        pass

    if args.briefing_only:
        # Hook-identical injection format: small, UTF-8 safe, nothing to post-process.
        b = data.get("_briefing", "")
        m = json.dumps(data.get("_meta", {}), ensure_ascii=False)
        _print_text(f"BRIEFING:\n{b}\n\nGATHER_META: {m}")
    else:
        output_json(data)


if __name__ == "__main__":
    main()
