#!/usr/bin/env python3
"""Context gatherer for handoff skill. Layers 0 + 1 only."""

import argparse, sys, time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.git import gather_git
from gather.sessions import extract_session_id, get_machine_name
from gather.eval import record_eval, estimate_tokens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-dir", default="")
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    start = time.monotonic()

    project = identify_project(args.cwd)
    git = gather_git() if project["type"] == "git" else {}
    session_id = extract_session_id(args.memory_dir) if args.memory_dir else ""
    machine = get_machine_name()

    result = {
        "project": project,
        "git": git,
        "session_id": session_id,
        "machine": machine,
    }

    record_eval("handoff", {
        "duration_ms": int((time.monotonic() - start) * 1000),
        "sources_used": ["project", "git", "sessions"],
        "context_tokens_estimate": estimate_tokens(result),
    })

    output_json(result)


if __name__ == "__main__":
    main()
