"""The one emitter for every hook reply: the event picks the channel (spec §6.2).

The model reads `hookSpecificOutput.additionalContext`; `systemMessage` is the line the
human sees in the TUI (.claude/rules/hooks.md). The split per event is the one the 3.x
handlers used:

- SessionStart (inject-h2t-context), UserPromptSubmit (gather-on-prompt) and PostToolUse
  (plan-closer, new-repo-hint) speak to the model;
- every other event — PreToolUse (gather-on-skill), Stop, SessionEnd (reap-codex) — speaks
  to the human.

A block is exit 2 with the reason on stderr, which the harness shows to the model.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass

MODEL_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "PostToolUse"})


@dataclass(frozen=True)
class Reply:
    text: str = ""
    block: bool = False
    # A separate line for the human, for the events whose `text` goes to the model.
    # plan-closer and new-repo-hint send the two readers different texts.
    notice: str = ""


def _clean(text: str) -> str:
    # A lone surrogate becomes `\udcd1` in json.dumps, and the API rejects the request and
    # every later one in the session (#453). "replace" cannot produce one.
    return text.encode("utf-8", "replace").decode("utf-8")


def envelope(event_name: str, reply: Reply) -> dict | None:
    text, notice = _clean(reply.text), _clean(reply.notice)
    if event_name in MODEL_EVENTS:
        env: dict = {}
        if notice:
            env["systemMessage"] = notice
        if text:
            env["hookSpecificOutput"] = {"hookEventName": event_name, "additionalContext": text}
        return env or None
    message = "\n".join(part for part in (text, notice) if part)
    return {"systemMessage": message} if message else None


def write(event_name: str, reply: Reply) -> int:
    """Print the reply on its channel and return the exit code: 0, or 2 for a block."""
    if reply.block:
        sys.stderr.buffer.write(_clean(reply.text).encode("utf-8") + b"\n")
        sys.stderr.flush()
        return 2
    env = envelope(event_name, reply)
    if env is not None:
        # ASCII bytes: no console code page can touch the envelope on the way out.
        sys.stdout.buffer.write(json.dumps(env).encode("ascii") + b"\n")
        sys.stdout.flush()
    return 0
