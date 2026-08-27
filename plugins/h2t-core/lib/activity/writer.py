"""Activity stream writer — Phase 1: local JSONL spool.

Each record is one JSON line in H2T_ACTIVITY_SPOOL (default: ~/.h2t/activity/spool.jsonl).
Phase 2: replace _write() with POST to POS API; local spool becomes fallback.
"""

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path


def log_session_start(
    session_id: str,
    domain: str,
    project: str,
    machine: str | None = None,
) -> str:
    """Append session.start record to local spool. Returns spool path."""
    return _write(
        session_id=session_id,
        action="session.start",
        domain=domain,
        project=project,
        machine=machine,
    )


def log_session_end(
    session_id: str,
    domain: str,
    project: str,
    artifacts: list | None = None,
    machine: str | None = None,
) -> str:
    """Append session.end record with optional artifacts. Returns spool path."""
    return _write(
        session_id=session_id,
        action="session.end",
        domain=domain,
        project=project,
        machine=machine,
        artifacts=artifacts or [],
    )


def _spool_path() -> Path:
    default = Path.home() / ".h2t" / "activity" / "spool.jsonl"
    return Path(os.environ.get("H2T_ACTIVITY_SPOOL", str(default)))


def _write(
    session_id: str,
    action: str,
    domain: str,
    project: str,
    machine: str | None = None,
    artifacts: list | None = None,
) -> str:
    path = _spool_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "session_id": session_id,
        "action": action,
        "domain": domain,
        "project": project,
        "machine": machine or platform.node(),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if artifacts:
        record["artifacts"] = artifacts

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return str(path)


def main() -> None:
    """CLI: python writer.py start --session-id <id> --domain <d> --project <p>"""
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import argparse as _argparse

    parser = _argparse.ArgumentParser(prog="writer.py", description="Activity stream writer CLI")
    sub = parser.add_subparsers(dest="cmd")

    start_cmd = sub.add_parser("start", help="Log session start")
    start_cmd.add_argument("--session-id", required=True)
    start_cmd.add_argument("--domain", required=True)
    start_cmd.add_argument("--project", required=True)
    start_cmd.add_argument("--machine", default="")

    args = parser.parse_args()
    if args.cmd == "start":
        path = log_session_start(
            session_id=args.session_id,
            domain=args.domain,
            project=args.project,
            machine=args.machine or None,
        )
        print(f"OK spool={path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
