"""Run a plugin hook handler resolved through the same ladder every entry point uses.

A hook written into a *project's* `.claude/settings.json` cannot use
`${CLAUDE_PLUGIN_ROOT}` — the harness defines that only for the plugin's own hooks.json.
An absolute cache path pins the project to one plugin version and to one machine's home
directory, and `.claude/settings.json` is normally committed. This launcher resolves at
fire time instead.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from h2t_ops.plugin_entrypoints import plugin_script_path

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


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1]:
        print(_USAGE, file=sys.stderr)
        return 2
    # `--help` is what a person types first, and it is not a handler name. Without this
    # it was resolved as one: `h2t-hook --help` looked for `hooks-handlers/--help`, did
    # not find it, and exited 5 — a real answer to a question nobody asked.
    if sys.argv[1] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0
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
