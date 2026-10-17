"""Stop hook: an answer that breaks the plain-language rule gets a warning line.

Origin: the owner asked "explain in plain language, without jargon" repeatedly and
the rule kept being ignored (user CLAUDE.md, 2026-09-01). The rule had no check.
This hook measures the measurable part of it, after Simplified Technical Russian
(ГОСТ Р 58049-2017) and ASD-STE100:

- a sentence longer than MAX_WORDS words;
- a machine-slang word the owner banned, used outside backticks;
- the passive/bureaucratic forms "должен быть ..." and "является".

Not measured: noun chains (needs a morphological analyser, not stdlib) and whether
an internal name was explained (needs meaning, not counting).

Code blocks, inline code, «quoted examples», tables, URLs and paths are not counted.
Every answer is logged to ~/.h2t/logs/plain-guard.jsonl so the hit rate can be
reviewed after a trial week. Warn only, never block: a blocking Stop hook makes
the model rewrite the answer and doubles output tokens.

Port of the 3.x hooks-handlers/plain_guard.py, deleted in Task 12a: the measuring functions and the log row are the
original's (AST-compared until the deletion); `main()` became `handle()`, which
logs and stays silent — see the comment there for why.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from h2t_ops.hooks.emit import Reply
from h2t_ops.hooks.grade_guard import last_assistant_text

MAX_WORDS = 25
LOG_PATH = Path.home() / ".h2t" / "logs" / "plain-guard.jsonl"

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
QUOTE_RE = re.compile(r"«[^»\n]*»")
URL_RE = re.compile(r"https?://\S+")
PATH_RE = re.compile(r"(?:[A-Za-z]:)?[\w.~-]*[/\\][\w./\\~-]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*")

SLANG_RE = re.compile(
    r"(?<![\w-])("
    r"grain|provenance|candidate layer|bottom-up|distill\w*|entity|entities|arbitration"
    r")(?![\w-])",
    re.IGNORECASE,
)
PASSIVE_RE = re.compile(
    r"(?<![\w-])(должн(?:а|о|ы)?\s+быть|является|являются)(?![\w-])",
    re.IGNORECASE,
)


def prose(text: str) -> str:
    """The text a reader reads as sentences: no code, tables, URLs or paths."""
    text = FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub("CODE", text)
    text = QUOTE_RE.sub("QUOTE", text)  # a quoted example is cited, not written
    text = URL_RE.sub("URL", text)
    text = PATH_RE.sub("PATH", text)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("|")]
    return "\n".join(lines)


def long_sentences(text: str) -> list[int]:
    """Word counts of sentences longer than MAX_WORDS. Each line is its own unit."""
    counts = []
    for line in prose(text).splitlines():
        for sentence in SENTENCE_SPLIT_RE.split(line):
            n = len(WORD_RE.findall(sentence))
            if n > MAX_WORDS:
                counts.append(n)
    return counts


def check(text: str) -> dict:
    body = prose(text)
    return {
        "words": len(WORD_RE.findall(body)),
        "long": long_sentences(text),
        "slang": sorted({m.group(1).lower() for m in SLANG_RE.finditer(body)}),
        "passive": sorted({m.group(1).lower() for m in PASSIVE_RE.finditer(body)}),
    }


def warning(result: dict) -> str | None:
    parts = []
    if result["long"]:
        parts.append(f"{len(result['long'])} предл. длиннее {MAX_WORDS} слов (макс. {max(result['long'])})")
    if result["slang"]:
        parts.append("жаргон: " + ", ".join(result["slang"]))
    if result["passive"]:
        parts.append("канцелярит: " + ", ".join(result["passive"]))
    if not parts:
        return None
    return "[h2t] простой язык: " + "; ".join(parts) + "."


def log(payload: dict, result: dict, flagged: bool) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session_id": payload.get("session_id"),
            "cwd": payload.get("cwd"),
            "flagged": flagged,
            **result,
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a missing log line must never break a stop


def handle(event: dict) -> Reply:
    # Channel: none — the log row is the output. 3.x printed the warning as plain stdout,
    # which the harness shows on Stop in transcript mode only, so in the TUI this hook has
    # been silent since it shipped (f60f04d4, 3.2.48). It is a one-week trial whose data
    # is this log ("logged ... for a one-week trial review of the hit rate", CHANGELOG),
    # and the log on the author's machine flags 28 of 288 answers (2026-10-10..17):
    # promoting it to systemMessage would put a new line under one stop in ten. Turning
    # the line on is a decision for after the trial, not a side effect of the port.
    # Decision recorded in the Task 9b report.
    if event.get("stop_hook_active"):
        return Reply()
    text = last_assistant_text(event.get("transcript_path", ""))
    if not text:
        return Reply()
    result = check(text)
    log(event, result, warning(result) is not None)
    return Reply()
