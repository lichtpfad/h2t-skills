"""Transcript reader: origin, counts and tolerance of broken lines."""

from __future__ import annotations

import json
from pathlib import Path

from h2t_ops.lifecycle.pulse import transcript


def _write(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _codex(tmp_path: Path, originator: str) -> Path:
    return _write(
        tmp_path / "rollout-1.jsonl",
        [
            {
                "timestamp": "2026-10-01T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "sid-1", "cwd": "/w", "originator": originator},
            },
            {
                "timestamp": "2026-10-01T10:01:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            },
        ],
    )


def _claude_user(ts: str, text: str, **extra) -> dict:
    return {
        "timestamp": ts,
        "type": "user",
        "cwd": "/w",
        "message": {"role": "user", "content": text},
        **extra,
    }


def test_codex_tui_is_live(tmp_path):
    info = transcript.read("codex", _codex(tmp_path, "codex-tui"))
    assert info is not None
    assert info.origin == "live"
    assert info.session_id == "sid-1"
    assert info.user_msgs == 1


def test_codex_exec_is_machine(tmp_path):
    assert transcript.read("codex", _codex(tmp_path, "codex_exec")).origin == "machine"
    assert transcript.read("codex", _codex(tmp_path, "Claude Code")).origin == "machine"


def test_unknown_originator_is_unknown(tmp_path):
    assert transcript.read("codex", _codex(tmp_path, "something-new")).origin == "unknown"


def test_claude_cli_is_live_and_counts_user_voice(tmp_path):
    path = _write(
        tmp_path / "proj" / "abc-123.jsonl",
        [
            _claude_user("2026-10-01T10:00:00Z", "first", entrypoint="cli"),
            _claude_user("2026-10-01T10:01:00Z", "second", entrypoint="cli"),
            _claude_user("2026-10-01T10:02:00Z", "<command-name>/x</command-name>", entrypoint="cli"),
        ],
    )
    info = transcript.read("claude", path)
    assert info.origin == "live"
    assert info.user_msgs == 2
    assert info.session_id == "abc-123"
    assert info.start == "2026-10-01T10:00:00Z"
    assert info.end == "2026-10-01T10:02:00Z"
    assert transcript.user_messages("claude", path) == ["first", "second"]


def test_claude_headless_is_machine(tmp_path):
    path = _write(
        tmp_path / "s.jsonl",
        [_claude_user("2026-10-01T10:00:00Z", "hi", entrypoint="sdk-cli")],
    )
    assert transcript.read("claude", path).origin == "machine"


def test_broken_lines_are_skipped(tmp_path):
    path = tmp_path / "s.jsonl"
    good = [
        _claude_user("2026-10-01T10:00:00Z", "a", entrypoint="cli"),
        _claude_user("2026-10-01T10:05:00Z", "b", entrypoint="cli"),
    ]
    body = "\n".join(json.dumps(r) for r in good).encode() + b"\n\xff\n"
    body += b'{"timestamp": "2026-10-01T11:00:00Z", "type": "us'
    path.write_bytes(body)
    info = transcript.read("claude", path)
    assert info.end == "2026-10-01T10:05:00Z"
    assert info.user_msgs == 2


def test_subagent_paths(tmp_path):
    assert transcript.is_subagent(tmp_path / "proj" / "u1" / "subagents" / "agent-a1.jsonl")
    assert not transcript.is_subagent(tmp_path / "proj" / "u1.jsonl")


def test_no_timestamps_is_none(tmp_path):
    path = _write(tmp_path / "s.jsonl", [{"type": "user", "message": {"content": "x"}}])
    assert transcript.read("claude", path) is None
