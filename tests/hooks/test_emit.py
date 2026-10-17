"""One emitter picks the channel by event (spec §6.2, .claude/rules/hooks.md).

The model reads `hookSpecificOutput.additionalContext`; `systemMessage` is the line the
human sees. Which events carry which channel is taken from the handlers as they emit
today: SessionStart (inject-h2t-context), UserPromptSubmit (gather-on-prompt) and
PostToolUse (plan-closer, new-repo-hint) speak to the model; PreToolUse (gather-on-skill)
and SessionEnd (reap-codex) speak to the human.
"""
import json

import pytest

from h2t_ops.hooks import emit
from h2t_ops.hooks.emit import Reply


def _out(capsysbinary):
    captured = capsysbinary.readouterr()
    return captured.out, captured.err


@pytest.mark.parametrize("event", ["SessionStart", "UserPromptSubmit", "PostToolUse"])
def test_model_events_use_additional_context(capsysbinary, event):
    assert emit.write(event, Reply("BRIEFING: x")) == 0
    out, err = _out(capsysbinary)
    assert json.loads(out) == {
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": "BRIEFING: x"},
    }
    assert err == b""


@pytest.mark.parametrize("event", ["PreToolUse", "Stop", "SessionEnd", ""])
def test_other_events_use_system_message(capsysbinary, event):
    assert emit.write(event, Reply("codex-reaper: 1")) == 0
    out, _ = _out(capsysbinary)
    assert json.loads(out) == {"systemMessage": "codex-reaper: 1"}


def test_post_tool_use_carries_both_readers(capsysbinary):
    """plan-closer and new-repo-hint send the model one text and the human another."""
    emit.write("PostToolUse", Reply("context for the model", notice="line for the human"))
    out, _ = _out(capsysbinary)
    assert json.loads(out) == {
        "systemMessage": "line for the human",
        "hookSpecificOutput": {"hookEventName": "PostToolUse",
                               "additionalContext": "context for the model"},
    }


def test_a_notice_alone_on_a_human_event_is_the_system_message(capsysbinary):
    emit.write("Stop", Reply(notice="only this"))
    out, _ = _out(capsysbinary)
    assert json.loads(out) == {"systemMessage": "only this"}


@pytest.mark.parametrize("event", ["SessionStart", "Stop", "PreToolUse", "PostToolUse"])
def test_an_empty_reply_prints_nothing(capsysbinary, event):
    assert emit.write(event, Reply()) == 0
    assert _out(capsysbinary) == (b"", b"")


@pytest.mark.parametrize("event", ["PreToolUse", "Stop", "UserPromptSubmit"])
def test_block_is_exit_2_with_the_reason_on_stderr(capsysbinary, event):
    assert emit.write(event, Reply("BLOCKED: путь вне структуры", block=True)) == 2
    out, err = _out(capsysbinary)
    assert out == b""
    assert err.decode("utf-8").strip() == "BLOCKED: путь вне структуры"


def test_the_envelope_is_ascii_bytes(capsysbinary):
    """No console code page can touch an ASCII envelope on the way out."""
    emit.write("SessionStart", Reply("кириллица\tи\r\nуправляющие"))
    out, _ = _out(capsysbinary)
    out.decode("ascii")
    assert json.loads(out)["hookSpecificOutput"]["additionalContext"] == "кириллица\tи\r\nуправляющие"


def test_a_lone_surrogate_never_reaches_the_envelope(capsysbinary):
    """json.dumps writes `\\udcd1` as six ASCII characters and the API rejects the
    request — and every later one in the session (#453)."""
    emit.write("UserPromptSubmit", Reply("bad \udcd1 byte"))
    out, _ = _out(capsysbinary)
    assert b"\\udc" not in out.lower()
    assert json.loads(out)["hookSpecificOutput"]["additionalContext"].startswith("bad ")
