"""Stop hook: a state claim without evidence gets a warning line in the terminal.

Origin: cross-repo audit 2026-09 — "flag says done, content missing" in 11 of 21
repos. The rule (engineering-discipline: verify state by command; grades A–D) has
no mechanism on the answer itself. This is the cheapest one: the last assistant
message claims a state (done / green / closed / passed) but shows neither a
command-output block nor a grade tag `[B …]` / `[C …]` / `[D …]`.

Warn only, never block: a blocking Stop hook re-enters the model and loops.
Reads the transcript JSONL named in the payload; stdlib only. Every answer is logged
to ~/.h2t/logs/grade-guard.jsonl; the hook itself prints nothing (see handle()).

Port of the 3.x hooks-handlers/grade_guard.py, deleted in Task 12a: the detection functions are the original's
(AST-compared until the deletion); `main()` became `handle()`.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.core.errors import H2TError
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


def log_path() -> Path:
    """Resolved per call: the logs place follows HOME and H2T_PATH_ROOT as they are now."""
    return paths.logs_dir() / "grade-guard.jsonl"


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


def warning(word: str) -> str:
    return (
        f"[h2t] «{word}» без вывода команды и без грейда [B]/[C]/[D] — "
        "утверждение о состоянии не проверено (Approach §1)."
    )


def log(payload: dict, word: str | None) -> None:
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "flagged": word is not None,
        "word": word,
    }
    try:
        store.append(log_path(), json.dumps(row, ensure_ascii=False), place="logs")
    except (OSError, H2TError) as exc:
        # A missing log line must never break a stop; it is said, not swallowed (hooks.md).
        print(f"h2t grade-guard: log row not written: {exc}", file=sys.stderr)


def handle(event: dict) -> Reply:
    # Silent, with a log row — like plain-guard. 3.x printed plain stdout, which the harness
    # shows on Stop in transcript mode only, so in the TUI it was never seen, and its firing
    # rate is unmeasured (spec §2.4: never noisy). Once the log gives that rate, a TUI line is
    # a one-line switch: `return Reply(warning(word) if word else "")`.
    if event.get("stop_hook_active"):
        return Reply()
    text = last_assistant_text(event.get("transcript_path", ""))
    if not text:
        return Reply()
    word = claim_without_evidence(text)
    log(event, word)
    return Reply()
