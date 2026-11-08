"""The answer guards are off until `guards: [...]` in user.yaml names them (§15 rule 5)."""
from __future__ import annotations

import importlib
import json

import pytest

from h2t_ops.core import paths
from h2t_ops.hooks.emit import Reply

CLAIM = "Готово, всё сделано."
LONG = " ".join(["слово"] * 40) + "."


def _transcript(tmp_path, text):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(p)


def _case(name, tmp_path, monkeypatch):
    """(module, event, the file the guard leaves behind when it acts)."""
    m = importlib.import_module(f"h2t_ops.hooks.{name}_guard")
    if name == "structure":
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "docs" / "superpowers" / "plans" / "_scratch.jsonl"
        return m, {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": ""}}, None
    return m, {"transcript_path": _transcript(tmp_path, CLAIM if name == "grade" else LONG),
               "session_id": "s1"}, m.log_path()


def _user_yaml(text):
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("name", ["grade", "plain", "structure"])
def test_guard_silent_unless_enabled(name, tmp_path, monkeypatch):
    m, event, log = _case(name, tmp_path, monkeypatch)
    assert m.handle(event) == Reply()                       # no user.yaml at all
    assert log is None or not log.exists()
    _user_yaml("guards: [other]\n")                         # a guard that is not this one
    assert m.handle(event) == Reply()
    assert log is None or not log.exists()
    _user_yaml(f"guards: [{name}]\n")
    reply = m.handle(event)
    if name == "structure":
        assert reply.block is True and "BLOCKED" in reply.text   # the universal plan-dir rule
    else:
        assert reply == Reply() and log.is_file()           # today's behaviour: a log row


@pytest.mark.parametrize("name", ["grade", "plain", "structure"])
@pytest.mark.parametrize("body", ["guards: [unclosed\n", "guards: 5\n", "guards: grade\n"])
def test_a_user_yaml_that_cannot_say_leaves_the_guard_off(name, body, tmp_path, monkeypatch):
    """A hook must not break the session: ConfigError or a wrong shape means disabled."""
    m, event, log = _case(name, tmp_path, monkeypatch)
    _user_yaml(body)
    assert m.handle(event) == Reply()
    assert log is None or not log.exists()
