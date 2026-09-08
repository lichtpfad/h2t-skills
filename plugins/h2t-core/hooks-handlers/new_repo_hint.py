"""PostToolUse(Bash): a command that created a repository offers /h2t-core:init-project.

Origin: cross-repo audit 2026-09 — 24 unregistered repos across two roots, and the
truth gate (three answers by command) was never asked because nothing asked it at
the moment the repo appeared. The moment is `git init` / `gh repo create` /
`h2t-scaffold-project create`: cheap to detect, impossible to recover later.

Reads the hook payload on stdin, prints a hint JSON when the command matches,
prints nothing otherwise. Stdlib only, never writes.
"""
from __future__ import annotations

import json
import re
import sys

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


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command_creates_repo(command):
        return 0
    print(json.dumps({
        "systemMessage": "Новое репо → предложи /h2t-core:init-project (truth gate).",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": HINT,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
