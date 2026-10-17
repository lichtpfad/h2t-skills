"""`h2t-creative`: profiles and the assembler, from the package.

`root` prints the shipped resources (`profiles/`, `base/`, `shared/`). `profiles-dir` prints
where profiles the user creates live: `~/.h2t/creative/profiles/`, outside every install,
so an update cannot wipe them — the plugin bin this replaces answered with its own
directory, and style-create wrote new profiles into the plugin cache. `assemble` looks a
profile up there first, then among the shipped ones.
"""
from __future__ import annotations

import sys
from pathlib import Path

from h2t_ops.resources import resource_dir

USAGE = "usage: h2t-creative {root,profiles-dir,assemble} [assembler args]"


def user_profiles_dir() -> Path:
    """`~/.h2t/creative/profiles` — one root, `~/.h2t` (#548 option A)."""
    return Path.home() / ".h2t" / "creative" / "profiles"


def _profile_name(args: list[str]) -> str | None:
    for i, arg in enumerate(args):
        if arg == "--profile" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--profile="):
            return arg.split("=", 1)[1]
    return None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    command = args[0] if args else ""
    if command == "root":
        print(resource_dir("creative"))
        return 0
    if command == "profiles-dir":
        print(user_profiles_dir())
        return 0
    if command == "assemble":
        from h2t_ops.tools.creative import assembler

        name = _profile_name(args[1:])
        if name and (user_profiles_dir() / name).is_dir():
            # The assembler copy reads PROFILES_DIR once per run; base/ and shared/ stay
            # the shipped ones. A user profile shadows a shipped one of the same name.
            assembler.PROFILES_DIR = user_profiles_dir()
        # assembler.main parses sys.argv itself, exactly as the plugin script runs it.
        sys.argv = ["h2t-creative assemble", *args[1:]]
        assembler.main()
        return 0
    if command in {"-h", "--help"}:
        print(__doc__.splitlines()[0])
        print(USAGE)
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
