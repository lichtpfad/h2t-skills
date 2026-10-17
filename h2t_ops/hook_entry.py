"""Run a plugin hook handler resolved through the same ladder every entry point uses.

A hook written into a *project's* `.claude/settings.json` cannot use
`${CLAUDE_PLUGIN_ROOT}` — the harness defines that only for the plugin's own hooks.json.
An absolute cache path pins the project to one plugin version and to one machine's home
directory, and `.claude/settings.json` is normally committed. This launcher resolves at
fire time instead.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from h2t_ops.plugin_entrypoints import plugin_script_path

# Not 2: for a hook, 2 is the harness's block signal, and a usage error must never read as
# a deliberate block (spec §6.1, ruling R8). 64 is EX_USAGE.
EXIT_USAGE = 64

_DEFAULT_INTERPRETER = ["bash"]
_PYTHON_NAMES = {"python", "python3"}


def interpreter_for(path: Path) -> list[str]:
    """The shebang decides.

    hooks.json hardcodes `bash` for the handlers it declares, but the two handlers
    scaffold-project writes are python3 — running those under bash is a syntax error.
    A python shebang resolves to `sys.executable` when PATH has no matching name, which
    is the normal case on Windows (`python.exe`, no `python3.exe`).
    """
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return list(_DEFAULT_INTERPRETER)
    if not first.startswith("#!"):
        return list(_DEFAULT_INTERPRETER)
    parts = first[2:].strip().split()
    if not parts:
        return list(_DEFAULT_INTERPRETER)
    if Path(parts[0]).name == "env" and len(parts) > 1:
        parts = parts[1:]
    name = Path(parts[0]).name
    resolved = shutil.which(parts[0]) or shutil.which(name)
    if resolved is None and Path(name).stem in _PYTHON_NAMES:
        resolved = sys.executable
    return [resolved or parts[0], *parts[1:]]


_USAGE = """usage: h2t-hook <handler-name> [args...]

Runs a plugin hook handler from the h2t-core plugin, resolving the plugin root the
same way a skill does. Handlers live in hooks-handlers/ and are named without a path:

  h2t-hook gather-on-prompt
  h2t-hook structure-guard

Set H2T_PLUGIN_ROOT to override where the handler is looked for.
"""


def _read_event() -> dict:
    # Bytes, decoded explicitly: sys.stdin.read() uses the console code page on Windows,
    # and under UTF-8 mode one undecodable byte becomes a lone surrogate (#453).
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        event = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return event if isinstance(event, dict) else {}


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


def run_handler(name: str, handle) -> int:
    """A handler from h2t_ops.hooks: one emitter for every exit path (spec §6.2)."""
    from h2t_ops.hooks import emit

    try:
        event = _read_event()
        return emit.write(str(event.get("hook_event_name") or ""), handle(event))
    except Exception as exc:
        print(f"h2t hook {name} failed: {type(exc).__name__}", file=sys.stderr)
        _log_failure(name, exc)
        return 1


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
    from h2t_ops.hooks import HANDLERS

    handle = HANDLERS.get(sys.argv[1])
    if handle is not None:
        if len(sys.argv) > 2:
            print(f"h2t-hook {sys.argv[1]}: takes no arguments, the event comes on stdin",
                  file=sys.stderr)
            return EXIT_USAGE
        return run_handler(sys.argv[1], handle)
    relative = f"hooks-handlers/{sys.argv[1]}"
    try:
        path = plugin_script_path(relative)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    # check=False: the handler's exit code is the launcher's exit code — a hook that
    # exits non-zero is signalling, not crashing.
    completed = subprocess.run([*interpreter_for(path), str(path), *sys.argv[2:]], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
