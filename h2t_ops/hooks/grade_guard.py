"""Stop hook: a state claim without evidence gets a warning line in the terminal.

Origin: cross-repo audit 2026-09 — "flag says done, content missing" in 11 of 21
repos. The rule (engineering-discipline: verify state by command; grades A–D) has
no mechanism on the answer itself. This is the cheapest one: the last assistant
message claims a state (done / green / closed / passed) but shows neither a
command-output block nor a grade tag `[B …]` / `[C …]` / `[D …]`.

Warn only, never block: a blocking Stop hook re-enters the model and loops.
Reads the transcript JSONL named in the payload; stdlib only; never writes.

Port of hooks-handlers/grade_guard.py: the detection functions are the original's
(tests/hooks/test_hook_module_parity.py); `main()` became `handle()`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from h2t_ops.hooks.emit import Reply

CLAIM_RE = re.compile(
    r"(?<![\w-])("
    r"готово|сделано|закрыт[аоы]?|зел[её]н[а-я]*|прош[её]л|прошли|проходит|"
    r"done|green|closed|passed|passes|fixed|merged|deployed"
    r")(?![\w-])",
    re.IGNORECASE,
)
GRADE_RE = re.compile(r"\[(B|C|D)[:\]\s]")
EVIDENCE_RE = re.compile(r"```")


def last_assistant_text(transcript_path: str) -> str:
    """Last assistant message's text blocks, joined. Empty string on any trouble."""
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for raw in reversed(lines):
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content") or []
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def claim_without_evidence(text: str) -> str | None:
    """The claim word found when the message has no grade tag and no code block."""
    if not text or GRADE_RE.search(text) or EVIDENCE_RE.search(text):
        return None
    m = CLAIM_RE.search(text)
    return m.group(1) if m else None


def stop_warning(payload: dict) -> str | None:
    if payload.get("stop_hook_active"):
        return None
    word = claim_without_evidence(last_assistant_text(payload.get("transcript_path", "")))
    if not word:
        return None
    return (
        f"[h2t] «{word}» без вывода команды и без грейда [B]/[C]/[D] — "
        "утверждение о состоянии не проверено (Approach §1)."
    )


def handle(event: dict) -> Reply:
    # Channel: systemMessage, the human's TUI line. 3.x printed plain stdout, which the
    # harness shows on Stop in transcript mode only — but the line was written for the
    # terminal: "gets a warning line in the terminal" (this docstring, 296d6db6), "one
    # warning line in the terminal" (CHANGELOG 3.3.0). It fires only on an unbacked claim,
    # so it is not a line on every Stop. Decision recorded in the Task 9b report.
    message = stop_warning(event)
    return Reply(message) if message else Reply()
