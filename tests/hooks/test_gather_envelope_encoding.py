"""The gather hook envelope must be valid JSON whatever bytes reach it.

On AUTOMATA `/h2t-core:session-start` returned

    API Error: 400 The request body is not valid JSON: invalid high surrogate in string

and every later request in that session failed the same way, in two separate chats.
The mechanism, reproduced locally: emit() read stdin with `sys.stdin.read()`, which
under UTF-8 mode decodes undecodable bytes through `surrogateescape` into lone
surrogates. json.dumps then writes `\\udcd1`, which no JSON parser accepts, and the
poisoned string lives in the conversation for the rest of the session.

Bad bytes reach the hook by two known routes, and neither is hypothetical:
`tail -c 500` truncates stderr by BYTES and splits a UTF-8 character in half, and a
localized Windows error message arrives in the console code page, not UTF-8.

The envelope is the last place this can be caught before the request leaves. It must
never emit a surrogate, whatever it was handed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HANDLER = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "gather-on-skill"
SURROGATE = re.compile(r"[\ud800-\udfff]")
# The escape as it appears in the emitted bytes. Checking the decoded envelope text is
# not enough: json.dumps writes the six ASCII characters \udcd1, so the envelope reads
# as clean ASCII while carrying a surrogate no strict parser will accept. Python's own
# json.loads accepts it too, which is why this has to be asserted on both sides.
SURROGATE_ESCAPE = re.compile(rb"\\u[dD][89abAB][0-9a-fA-F]{2}|\\u[dD][c-fC-F][0-9a-fA-F]{2}")


def _assert_no_surrogates(out: bytes) -> dict:
    assert not SURROGATE_ESCAPE.search(out), f"surrogate escape in envelope: {out!r}"
    obj = json.loads(out.decode("utf-8"))
    for value in obj.get("hookSpecificOutput", {}).values():
        if isinstance(value, str):
            assert not SURROGATE.search(value), f"surrogate in parsed envelope: {value!r}"
    return obj


def _emit_snippet() -> str:
    """The python program emit() runs, lifted from the handler itself.

    Read from the shipped file rather than copied here: a test carrying its own copy
    of the code under test passes while the handler drifts.
    """
    text = HANDLER.read_text(encoding="utf-8")
    start = text.index("'import json, sys")
    end = text.index("' \"$event\"", start)
    return text[start + 1:end]


def _run_emit(payload: bytes, event: str = "UserPromptSubmit") -> bytes:
    proc = subprocess.run(
        [sys.executable, "-c", _emit_snippet(), event],
        input=payload,
        capture_output=True,
        env={"PYTHONUTF8": "1", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout


def test_envelope_is_valid_json_for_utf8_input():
    out = _run_emit("## Сессия: agent-skills\n".encode())
    obj = json.loads(out.decode("utf-8"))
    assert obj["hookSpecificOutput"]["additionalContext"].startswith("## Сессия")


def test_envelope_survives_console_codepage_bytes():
    """A localized Windows error arrives as cp1251, which is not valid UTF-8."""
    obj = _assert_no_surrogates(_run_emit("## Сессия: agent-skills".encode("cp1251")))
    assert "additionalContext" in obj["hookSpecificOutput"]


def test_envelope_survives_a_character_split_in_half():
    """`tail -c 500` cuts by bytes and leaves half a UTF-8 character behind."""
    payload = "GATHER_ERROR: не найден интерпретатор".encode()[:-1]
    _assert_no_surrogates(_run_emit(payload))


def test_envelope_is_pure_ascii():
    """ensure_ascii keeps the envelope readable on a console with any code page."""
    out = _run_emit("эмодзи 🚀 и кириллица".encode())
    out.decode("ascii")
    obj = json.loads(out.decode("ascii"))
    assert "🚀" in obj["hookSpecificOutput"]["additionalContext"]
