"""A command that created a repository offers /h2t-core:init-project.

The truth gate can only be asked at the moment the repo appears; the audit found 24
repos across two roots that were never registered because nothing asked.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from h2t_ops.hooks import emit


def _load():
    path = Path(__file__).parents[2] / "h2t_ops" / "hooks" / "new_repo_hint.py"
    spec = importlib.util.spec_from_file_location("new_repo_hint_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _run(monkeypatch, capsysbinary, command: str) -> str:
    """The reply as the harness gets it: through the one emitter."""
    m = _load()
    reply = m.handle({"hook_event_name": "PostToolUse", "tool_input": {"command": command}})
    assert emit.write("PostToolUse", reply) == 0
    return capsysbinary.readouterr().out.decode("ascii")


def test_git_init_hints():
    m = _load()
    assert m.command_creates_repo("git init")
    assert m.command_creates_repo("git -C C:/dev/x init")
    assert m.command_creates_repo("cd /tmp/x; git init")


def test_gh_repo_create_and_scaffold_hint():
    m = _load()
    assert m.command_creates_repo("gh repo create lichtpfad/x --private")
    assert m.command_creates_repo("h2t-scaffold-project create --id x --type code-local")


def test_dry_run_and_unrelated_commands_stay_silent():
    m = _load()
    assert not m.command_creates_repo("h2t-scaffold-project create --id x --dry-run")
    assert not m.command_creates_repo("git status")
    assert not m.command_creates_repo("git initial-commit-helper")
    assert not m.command_creates_repo("")


def test_hint_reaches_both_readers(monkeypatch, capsysbinary):
    out = json.loads(_run(monkeypatch, capsysbinary, "git init"))
    assert "init-project" in out["systemMessage"]
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "truth gate" in out["hookSpecificOutput"]["additionalContext"]


def test_silence_is_empty_stdout(monkeypatch, capsysbinary):
    assert _run(monkeypatch, capsysbinary, "ls") == ""
