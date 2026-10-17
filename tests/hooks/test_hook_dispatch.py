"""`h2t-hook <name>`: a name in HANDLERS runs in-process through the one emitter (spec §6.2).

A name outside HANDLERS exits 5 (tests/core/test_hook_entry.py). The `Command` entries keep
their own 3.x process contract (tests/hooks/test_command_hooks.py).
"""
import io
import json
import sys

import pytest

from h2t_ops import hook_entry, hooks
from h2t_ops.hooks.emit import Reply


@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def _run(name, handler, stdin: bytes, *extra):
        monkeypatch.setitem(hooks.HANDLERS, name, handler)
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin)))
        monkeypatch.setattr(sys, "argv", ["h2t-hook", name, *extra])
        return hook_entry.main()
    return _run


# Every name the 3.x plugin shipped in hooks-handlers/, deleted in Task 12a. hooks.json,
# projects' settings.json and git hooks call these names, so none may be renamed.
NAMES_3X = {"gather-on-skill", "gather-on-prompt", "inject-h2t-context", "structure-guard",
            "grade-guard", "plain-guard", "plan-closer", "new-repo-hint",
            "session-end-reap-codex", "layout-precommit", "bulk-precommit",
            "secrets-precommit", "on-stop", "post-git-commit-docs-lint"}


def test_handlers_are_keyed_by_the_3x_handler_names():
    assert set(hooks.HANDLERS) == NAMES_3X
    for name, handle in hooks.HANDLERS.items():
        assert callable(handle), name


def test_a_registered_handler_gets_the_parsed_event_and_its_reply_is_emitted(run, capsysbinary):
    seen = {}

    def handle(event):
        seen.update(event)
        return Reply("BRIEFING: ok")

    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "/handoff"}
    assert run("probe", handle, json.dumps(payload).encode()) == 0
    assert seen == payload
    out = json.loads(capsysbinary.readouterr().out)
    assert out["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit",
                                         "additionalContext": "BRIEFING: ok"}


@pytest.mark.parametrize("stdin,error", [
    (b"{not json", "JSONDecodeError"),
    (b"", "JSONDecodeError"),
    (b"[1, 2]", "ValueError"),
    (b'"a string"', "ValueError"),
])
def test_an_event_that_is_not_a_json_object_fails_loudly(run, capsys, tmp_path, stdin, error):
    """A silent hook is a failure (.claude/rules/hooks.md): no handler runs on `{}`."""
    seen = []
    assert run("probe", lambda e: seen.append(e) or Reply("ran"), stdin) == 1
    assert seen == [], "the handler must not run on an event that did not parse"
    captured = capsys.readouterr()
    assert captured.err == f"h2t hook probe failed: {error}\n"
    assert captured.out == ""
    rows = (tmp_path / ".h2t" / "logs" / "hooks.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert (row["hook"], row["rc"], row["error"]) == ("probe", 1, error)


def test_undecodable_bytes_become_replacement_characters(run):
    seen = []
    raw = b'{"hook_event_name": "Stop", "x": "\xd1 half"}'
    run("probe", lambda e: seen.append(e) or Reply(), raw)
    assert seen[0]["x"] == "� half"


def test_a_block_reply_exits_2(run, capsysbinary):
    rc = run("probe", lambda e: Reply("BLOCKED: no", block=True), b'{"hook_event_name": "PreToolUse"}')
    assert rc == 2
    assert capsysbinary.readouterr().err.decode().strip() == "BLOCKED: no"


def test_an_exception_is_one_stderr_line_exit_1_and_a_log_row(run, capsys, tmp_path):
    def handle(event):
        raise ValueError("secret detail")

    assert run("probe", handle, b"{}") == 1
    captured = capsys.readouterr()
    assert captured.err == "h2t hook probe failed: ValueError\n"
    assert captured.out == ""
    rows = (tmp_path / ".h2t" / "logs" / "hooks.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert row["hook"] == "probe"
    assert row["error"] == "ValueError"
    assert "secret detail" in row["traceback"]


def test_an_unwritable_log_still_exits_1(run, capsys, tmp_path):
    (tmp_path / ".h2t").write_text("a file where the directory should be", encoding="utf-8")
    assert run("probe", lambda e: 1 / 0, b"{}") == 1
    assert capsys.readouterr().err == "h2t hook probe failed: ZeroDivisionError\n"


def test_extra_arguments_to_a_registered_handler_are_a_usage_error(run, capsys):
    assert run("probe", lambda e: Reply(), b"{}", "--unexpected") == 64


@pytest.mark.parametrize("argv", [["h2t-hook"], ["h2t-hook", ""]])
def test_a_missing_or_empty_name_is_64_not_2(monkeypatch, argv):
    """Exit 2 is the harness's block signal; a usage error must never read as one (R8)."""
    monkeypatch.setattr(sys, "argv", argv)
    assert hook_entry.main() == 64
