"""PostToolUse(Bash): a command that created a repository offers /h2t-core:init-project.

Origin: cross-repo audit 2026-09 — 24 unregistered repos across two roots, and the
truth gate (three answers by command) was never asked because nothing asked it at
the moment the repo appeared. The moment is `git init` / `gh repo create` /
`h2t-scaffold-project create`: cheap to detect, impossible to recover later.

Replies with a hint when the command matches — `text` for the model, `notice` for
the human — and with nothing otherwise. Stdlib only, never writes.

Port of the 3.x hooks-handlers/new_repo_hint.py, deleted in Task 12a: the functions are the original's (AST-compared until the deletion);
`main()` became `handle()`, and the reply goes out through `h2t_ops.hooks.emit`.
"""
from __future__ import annotations

import re

from h2t_ops.hooks.emit import Reply

_PATTERNS = (
    re.compile(r"(^|[\s;&|(])git\s+(-C\s+\S+\s+)?init(\s|$)"),
    re.compile(r"(^|[\s;&|(])gh\s+repo\s+create(\s|$)"),
    re.compile(r"(^|[\s;&|(])h2t-scaffold-project\s+create(\s|$)"),
)

HINT = (
    "Repository created. Offer /h2t-core:init-project now: it registers the repo and runs "
    "the truth gate (three answers by command: source of truth, stage-run record, data "
    "contract) before the first line of code."
)


def command_creates_repo(command: str) -> bool:
    if not command or "--dry-run" in command:
        return False
    return any(p.search(command) for p in _PATTERNS)


NOTICE = "Новое репо → предложи /h2t-core:init-project (truth gate)."


def handle(event: dict) -> Reply:
    command = (event.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command_creates_repo(command):
        return Reply()
    return Reply(text=HINT, notice=NOTICE)
