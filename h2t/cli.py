"""h2t CLI entrypoint. dev/version here; connector dispatch + doctor added later."""
from __future__ import annotations

import sys

import h2t
from h2t.dev import main as _dev_main


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "dev":
        return _dev_main(argv[1:])
    if argv and argv[0] in ("--version", "-V"):
        print(f"h2t {h2t.__version__}")
        return 0
    from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
    old = sys.argv
    sys.argv = ["h2t", *argv]
    try:
        legacy_main()
        return 0
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1  # non-zero string message -> treat as error
    finally:
        sys.argv = old


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
