"""Session lifecycle: gather, handoff, activity, eval, and the project scripts.

The modules beside this file began as copies of the h2t-core plugin scripts, with the
`sys.path` bootstrap replaced by package imports. Task 12 deleted the originals: this is
the only implementation.
"""
from __future__ import annotations

import sys
from collections.abc import Callable


def run_main(main: Callable[[], object], prog: str, argv: list[str] | None = None) -> int:
    """Call a script's `main()` the way its console script calls it.

    The scripts read `sys.argv` themselves. `argv`, when given, stands in for it during
    the call, so a caller can pass arguments without a subprocess.
    """
    if argv is None:
        result = main()
    else:
        saved = sys.argv
        sys.argv = [prog, *argv]
        try:
            result = main()
        finally:
            sys.argv = saved
    return int(result) if isinstance(result, int) else 0

