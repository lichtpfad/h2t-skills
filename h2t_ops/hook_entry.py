"""`h2t-hook <name>`: run one hook handler from h2t_ops.hooks (spec §6.2).

Every name resolves through `h2t_ops.hooks.HANDLERS`; nothing is looked up on disk. The
plugin's hooks.json reaches a handler through `hooks/run <name>`, and the 3.x forms keep
working under the same names: the git pre-commit hooks, and the two hooks scaffold-project
writes into a project's `.claude/settings.json`, where `${CLAUDE_PLUGIN_ROOT}` does not
exist (tests/release/legacy_call_forms.json).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

# Not 2: for a hook, 2 is the harness's block signal, and a usage error must never read as
# a deliberate block (spec §6.1, ruling R8). 64 is EX_USAGE.
EXIT_USAGE = 64
EXIT_NOT_FOUND = 5

_USAGE = """usage: h2t-hook <handler-name> [args...]

Runs an h2t hook handler from the installed package. The event, if the hook has one,
comes as JSON on stdin:

  h2t-hook gather-on-prompt
  h2t-hook structure-guard
  h2t-hook layout-precommit        (a git pre-commit hook: no event, exit 1 blocks)
"""


def _read_event() -> dict:
    # Bytes, decoded explicitly: sys.stdin.read() uses the console code page on Windows,
    # and under UTF-8 mode one undecodable byte becomes a lone surrogate (#453).
    #
    # An event that is not a JSON object raises, and run_handler turns that into exit 1
    # plus a log row. Read as `{}`, it ran every handler on nothing and they all stayed
    # silent — and a silent hook is a failure, not a steady state (.claude/rules/hooks.md).
    # Undecodable bytes inside valid JSON still become U+FFFD: that is an event, not noise.
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ValueError(f"hook event is a JSON {type(event).__name__}, not an object")
    return event


def _log_failure(name: str, exc: BaseException) -> None:
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "hook": name, "rc": 1,
           "error": type(exc).__name__,
           "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))}
    try:
        path = Path.home() / ".h2t" / "logs" / "hooks.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass  # the stderr line is already the signal; a missing log row must not mask it


def _failed(name: str, exc: BaseException) -> int:
    print(f"h2t hook {name} failed: {type(exc).__name__}", file=sys.stderr)
    _log_failure(name, exc)
    return 1


def run_handler(name: str, handle) -> int:
    """A handler from h2t_ops.hooks: one emitter for every exit path (spec §6.2)."""
    from h2t_ops.hooks import emit

    try:
        event = _read_event()
        return emit.write(str(event.get("hook_event_name") or ""), handle(event))
    except Exception as exc:
        return _failed(name, exc)


def run_command(name: str, command, args: list[str]) -> int:
    """A `Command` keeps its 3.x contract: its own stdin and stdout, its exit code.

    An exception is still one stderr line, exit 1 and a log row (spec §6.2). For a git
    pre-commit hook exit 1 refuses the commit — loud, and never a silent pass.
    """
    try:
        return int(command(args))
    except Exception as exc:
        return _failed(name, exc)


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1]:
        print(_USAGE, file=sys.stderr)
        return EXIT_USAGE
    # `--help` is what a person types first, and it is not a handler name. Without this
    # it was resolved as one: `h2t-hook --help` looked for `hooks-handlers/--help`, did
    # not find it, and exited 5 — a real answer to a question nobody asked.
    if sys.argv[1] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0
    from h2t_ops.hooks import HANDLERS, Command

    name = sys.argv[1]
    handle = HANDLERS.get(name)
    if handle is None:
        print(f"h2t-hook: no handler named {name!r}. Known: {', '.join(sorted(HANDLERS))}",
              file=sys.stderr)
        return EXIT_NOT_FOUND
    if isinstance(handle, Command):
        return run_command(name, handle, sys.argv[2:])
    if len(sys.argv) > 2:
        print(f"h2t-hook {name}: takes no arguments, the event comes on stdin", file=sys.stderr)
        return EXIT_USAGE
    return run_handler(name, handle)


if __name__ == "__main__":
    raise SystemExit(main())
