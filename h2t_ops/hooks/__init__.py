"""Hook handlers that run in-process under `h2t-hook <name>` (spec §6.2).

Each module exposes `handle(event: dict) -> Reply`; this table maps the name the wrapper
passes (`hooks/run <name>`) to it. A name not here falls through to the 3.x path in
`h2t_ops.hook_entry`. The keys are the hooks.json handler names, so Task 12 can write
`hooks/run <name>` for each entry without a second table.

A handler's module is imported when the handler is called, not when this table is: one
`h2t-hook` process runs one handler, and PostToolUse fires two of them on every Bash call
with 150 ms for both (spec §2.7). Importing all nine cost each run about 20 ms.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable

from h2t_ops.hooks.emit import Reply


def _lazy(module: str, attr: str = "handle") -> Callable[[dict], Reply]:
    def handle(event: dict) -> Reply:
        return getattr(importlib.import_module(f"h2t_ops.hooks.{module}"), attr)(event)

    handle.__qualname__ = f"{module}.{attr}"
    return handle


HANDLERS: dict[str, Callable[[dict], Reply]] = {
    "gather-on-skill": _lazy("gather"),
    "gather-on-prompt": _lazy("gather", "handle_prompt"),
    "inject-h2t-context": _lazy("inject_context"),
    "structure-guard": _lazy("structure_guard"),
    "grade-guard": _lazy("grade_guard"),
    "plain-guard": _lazy("plain_guard"),
    "plan-closer": _lazy("plan_closer"),
    "new-repo-hint": _lazy("new_repo_hint"),
    "session-end-reap-codex": _lazy("reap_codex"),
}
