#!/usr/bin/env python3
"""Handoff writer for session-end.

Usage:
  $H2T_PYTHON writer.py write \
    --session-id <id> --domain <d> --project <p> \
    --what-done "..." --what-remains "..." \
    --artifacts commit:abc123 issue:42 \
    [--markdown-dir <path>]

Writes:
  1. Activity stream entry (local JSONL spool)
  2. Markdown handoff file at markdown_dir/session_id.md

lib/ path resolution: same dev/cache fallback as gather.py.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# lib/ path: cache root (4 levels up) or repo root (6 levels up) fallback
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_cache_lib = PLUGIN_ROOT / "lib"
_repo_lib = PLUGIN_ROOT.parent.parent / "lib"
for _lib in [_cache_lib, _repo_lib]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from activity.writer import log_session_end
from eval.session import SkillEval


def default_markdown_dir(project: str) -> Path:
    machine = os.environ.get("DOR_MACHINE_NAME", "")
    if not machine:
        import platform
        machine = platform.node().lower().split(".")[0]
    return Path.home() / ".dor" / "sessions" / machine / project


def write_handoff(
    session_id: str,
    domain: str,
    project: str,
    what_done: str,
    what_remains: str,
    artifacts: list[str],
    markdown_dir: str | None = None,
) -> dict:
    """Write session end to activity stream + markdown file."""

    # Unescape literal \n sequences (bash double-quote strings don't expand \n)
    what_done = what_done.replace("\\n", "\n")
    what_remains = what_remains.replace("\\n", "\n")

    parsed_artifacts = []
    for a in artifacts:
        if ":" in a:
            t, ref = a.split(":", 1)
            parsed_artifacts.append({"type": t, "ref": ref})
        else:
            parsed_artifacts.append({"type": "artifact", "ref": a})

    spool_path = log_session_end(
        session_id=session_id,
        domain=domain,
        project=project,
        artifacts=parsed_artifacts,
    )

    md_dir = Path(markdown_dir) if markdown_dir else default_markdown_dir(project)
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{session_id}.md"

    now = datetime.now(timezone.utc)
    artifacts_md = "\n".join(
        f"- {a['type']}: {a['ref']}" for a in parsed_artifacts
    ) or "None"
    md_content = f"""# Session: {session_id}

## Meta
- **Date:** {now.strftime("%Y-%m-%d")}
- **Domain:** {domain}
- **Project:** {project}

## What Was Done
{what_done}

## What Remains
{what_remains}

## Artifacts
{artifacts_md}
"""
    md_path.write_text(md_content, encoding="utf-8")

    try:
        with SkillEval("handoff", domain=domain, project=project):
            pass
    except Exception:
        pass

    return {
        "status": "ok",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": str(md_path),
        "artifacts": len(parsed_artifacts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    w = sub.add_parser("write")
    w.add_argument("--session-id", required=True)
    w.add_argument("--domain", required=True)
    w.add_argument("--project", required=True)
    w.add_argument("--what-done", default="")
    w.add_argument("--what-remains", default="")
    w.add_argument("--artifacts", nargs="*", default=[])
    w.add_argument("--markdown-dir", default="")
    args = parser.parse_args()

    if args.cmd == "write":
        result = write_handoff(
            session_id=args.session_id,
            domain=args.domain,
            project=args.project,
            what_done=args.what_done,
            what_remains=args.what_remains,
            artifacts=args.artifacts,
            markdown_dir=args.markdown_dir or None,
        )
        print(json.dumps(result, ensure_ascii=False))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
