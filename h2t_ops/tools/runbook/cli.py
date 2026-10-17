"""`h2t-runbook`: the autonomous-run skill's three scripts as one command.

The skill used to import `new_runbook.create_runbook(...)` and run `runbook_state.py` and
`validate_runbook.py` by path. The modules beside this file are copies of those scripts
(parity: tests/tools/test_tool_copy_parity.py); this adds only the command line.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from h2t_ops.tools.runbook import new_runbook, runbook_state, validate_runbook


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="h2t-runbook", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="write a validated runbook (never writes an invalid one)")
    new.add_argument("dest", help="docs/superpowers/plans/<date>-<slug>-runbook.md")
    new.add_argument("--title", required=True)
    new.add_argument("--today", default=None, help="YYYY-MM-DD (default: today)")
    new.add_argument("--branch", required=True)
    new.add_argument("--spec-path", required=True)
    new.add_argument("--issue", required=True)
    new.add_argument("--venv-test", required=True, help="the test command of the run")
    new.add_argument("--e2e-state", required=True,
                     help="starts with applies, N/A or BLOCKED-DEFERRED")
    new.add_argument("--json", action="store_true")

    for name, text in (("validate", "check a runbook against the schema"),
                       ("state", "list the unchecked pipeline steps")):
        verb = sub.add_parser(name, help=text)
        verb.add_argument("runbook")
        verb.add_argument("--json", action="store_true")
    return parser


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _fail(as_json: bool, code: int, message: str, hint: str) -> int:
    """Every error: `{"ok": false, "error": {"message", "hint"}}`, or both lines on stderr."""
    if as_json:
        _print({"ok": False, "error": {"message": message, "hint": hint}})
    else:
        print(f"ERROR: {message}\n  {hint}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    if args.command == "new":
        try:
            path = new_runbook.create_runbook(
                args.dest, title=args.title, today=args.today or date.today().isoformat(),
                runbook_path=args.dest, branch=args.branch, spec_path=args.spec_path,
                issue=args.issue, venv_test=args.venv_test, e2e_state=args.e2e_state)
        except (ValueError, validate_runbook.RunbookInvalid) as exc:
            return _fail(args.json, 2, str(exc), "Fix the field named above and run "
                         "`h2t-runbook new` again; nothing was written.")
        except OSError as exc:
            return _fail(args.json, 1, f"cannot write {args.dest}: {exc}",
                         "Check that the directory is writable.")
        if args.json:
            _print({"ok": True, "path": str(path)})
        else:
            print(path)
        return 0

    try:
        text = Path(args.runbook).read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail(args.json, 5, f"no runbook at {args.runbook}",
                     "Give the path of an existing docs/superpowers/plans/*-runbook.md.")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(args.json, 1, f"cannot read {args.runbook}: {exc}",
                     "Give the path of a readable UTF-8 runbook.")
    if args.command == "validate":
        if not args.json:
            return validate_runbook._main(["validate_runbook.py", args.runbook])
        problems = validate_runbook.validate(text)
        _print({"ok": not problems, "problems": problems})
        return 1 if problems else 0
    if not args.json:
        return runbook_state._main(["runbook_state.py", args.runbook])
    left = runbook_state.unchecked_steps(text)
    _print({"ok": True, "unchecked": left, "active": bool(left)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
