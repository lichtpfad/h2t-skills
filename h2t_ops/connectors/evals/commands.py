from __future__ import annotations

from typing import Any


def _cmd_status(ns: Any) -> dict:
    from lib.eval.status import get_status

    return get_status()


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("evals", help="Eval telemetry mode/status (read-only)")
    cmds = p.add_subparsers(dest="command")
    status = cmds.add_parser("status", help="Show resolved eval mode and availability")
    status.add_argument("--json", action="store_true", dest="as_json")
    status.set_defaults(_handler=_cmd_status)
