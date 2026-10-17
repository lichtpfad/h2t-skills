"""Session lifecycle: gather, handoff, activity, eval, and the project scripts.

The modules beside this file are copies of the h2t-core plugin scripts, with the
`sys.path` bootstrap replaced by package imports. The originals stay in the plugin until
the 3.x plugin layout is retired (plan Task 12): skills and hooks of 3.x still run them.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path


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


def plugin_script_anchor(relative_path: str, fallback: Path) -> Path:
    """Where this script sits in the h2t-core plugin tree, or `fallback` if nowhere.

    Two of the copied scripts find the sibling h2t-dev plugin relative to their own
    `__file__`. Inside the package that file is no longer in a plugin tree, so the copy
    asks the same ladder the 3.x entry point used to load the original — which keeps the
    lookup where it was. With no plugin found, the lookups miss and report a skip, as
    the originals do when h2t-dev is absent.
    """
    from h2t_ops.plugin_entrypoints import plugin_script_path

    try:
        return plugin_script_path(relative_path).resolve()
    except FileNotFoundError:
        return fallback
