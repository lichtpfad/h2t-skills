"""The handoff record must be written before the skill can ask the user anything.

Handoff runs at the end of a session, when the user has often already left. A question
before `h2t-handoff write` costs the whole record: on 2026-08-23 the meetgeek session
composed its summary, asked for a session name at Step 1, and got no answer — nothing
reached ~/.h2t/sessions. Renaming a written file is cheap; an unwritten one is gone.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "h2t-core" / "skills" / "handoff" / "SKILL.md"

WRITE_CALL = "h2t-handoff write"

BLOCKING = (
    re.compile(r"\bwait for\b", re.I),
    re.compile(r"⛔\s*GATE"),
)


def _before_write(text):
    index = text.find(WRITE_CALL)
    assert index != -1, f"{SKILL} no longer calls `{WRITE_CALL}` — the writer moved"
    return text[:index]


def test_nothing_blocks_before_the_write():
    prefix = _before_write(SKILL.read_text(encoding="utf-8"))
    offenders = [p.pattern for p in BLOCKING if p.search(prefix)]
    assert not offenders, (
        f"{SKILL} blocks on the user before `{WRITE_CALL}`: {offenders}. "
        "Every value the writer needs must be derived, not asked."
    )


def test_session_name_is_derived_not_proposed():
    prefix = _before_write(SKILL.read_text(encoding="utf-8"))
    line = next(ln for ln in prefix.splitlines() if "SESSION_NAME" in ln)
    assert "propose" not in line.lower(), (
        f"{SKILL} still proposes SESSION_NAME instead of deriving it: {line.strip()!r}"
    )
