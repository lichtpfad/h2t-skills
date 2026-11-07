"""Hook handlers that run in-process under `h2t-hook <name>` (spec §6.2).

This table maps every name `h2t-hook <name>` accepts to its handler. Two kinds:

- a Claude hook named by hooks.json (`hooks/run <name>`): `handle(event: dict) -> Reply`,
  the event parsed from stdin and the reply sent through the one emitter;
- a `Command`: a handler that owns its process contract — argv in, exit code out, its own
  stdin and stdout. These are the 3.x names called from outside any hooks.json, whose
  callers are committed files that outlive a plugin version: git pre-commit hooks
  (`scripts/hooks/pre-commit`, `~/.h2t/git-hooks`), which get no event and block with
  exit 1, and the two hooks scaffold-project writes into a project's `.claude/settings.json`.
  Their 3.x contract is kept as it was (tests/hooks/test_command_hooks.py).

A name not here is unknown: `h2t-hook` exits 5.

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


class Command:
    """A handler run as `main(argv) -> exit code`, imported when it is called."""

    def __init__(self, module: str) -> None:
        self.module = module

    def __call__(self, argv: list[str]) -> int:
        return importlib.import_module(f"h2t_ops.hooks.{self.module}").main(argv)

    def __repr__(self) -> str:
        return f"Command({self.module!r})"


HANDLERS: dict[str, Callable[[dict], Reply] | Command] = {
    "gather-on-skill": _lazy("gather"),
    "gather-on-prompt": _lazy("gather", "handle_prompt"),
    "inject-h2t-context": _lazy("inject_context"),
    "structure-guard": _lazy("structure_guard"),
    "grade-guard": _lazy("grade_guard"),
    "plain-guard": _lazy("plain_guard"),
    "plan-closer": _lazy("plan_closer"),
    "new-repo-hint": _lazy("new_repo_hint"),
    "session-end-reap-codex": _lazy("reap_codex"),
    "session-pulse": _lazy("session_pulse"),
    "layout-precommit": Command("layout_precommit"),
    "bulk-precommit": Command("bulk_precommit"),
    "secrets-precommit": Command("secrets_precommit"),
    "on-stop": Command("on_stop"),
    "post-git-commit-docs-lint": Command("post_git_commit_docs_lint"),
}
