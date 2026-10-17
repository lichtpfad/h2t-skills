"""`h2t-creative`: the same surface as the plugin's `bin/h2t-creative`, from the package.

The skills call `h2t-creative root` to find `profiles/` and `h2t-creative assemble ...` to
build. The plugin's shell script answers with its own directory and runs `assembler.py`
through `uv run`; this answers with the package resources and runs the package assembler.
Whichever of the two is first on PATH, the skill gets the same answer to the same call.
"""
from __future__ import annotations

import sys

from h2t_ops.resources import resource_dir

USAGE = "usage: h2t-creative root | h2t-creative assemble [assembler args]"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    command = args[0] if args else ""
    if command == "root":
        print(resource_dir("creative"))
        return 0
    if command == "assemble":
        from h2t_ops.tools.creative import assembler

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
