"""session-pulse: a draft at SessionStart, a record at SessionEnd, only for live sessions with a user message."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from h2t_ops import hooks
from h2t_ops.core import paths
from h2t_ops.hooks import session_pulse
from h2t_ops.hooks.emit import Reply
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.pulse import record

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.delenv("H2T_PULSE_SKIP", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)


def _codex(path: Path, originator: str, user_msgs: int = 1) -> Path:
    rows = [{"timestamp": "2026-10-19T10:00:00Z", "type": "session_meta",
             "payload": {"id": "u1", "cwd": "C:/w", "originator": originator}}]
    for i in range(user_msgs):
        rows.append({"timestamp": f"2026-10-19T10:0{i + 1}:00Z", "type": "response_item",
                     "payload": {"type": "message", "role": "user",
                                 "content": [{"type": "input_text", "text": f"hello {i}"}]}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _event(name: str, transcript: Path | str, cwd: Path, sid: str = "u1") -> dict:
    return {"hook_event_name": name, "session_id": sid, "cwd": str(cwd),
            "transcript_path": str(transcript)}


def _records() -> list[Path]:
    return sorted(paths.records("sessions").rglob("*.md"))


def _meta(path: Path) -> dict:
    return session_record.parse(path.read_bytes())[0]


def test_start_writes_a_draft_not_a_record(tmp_path):
    t = _codex(tmp_path / ".codex" / "sessions" / "rollout-1.jsonl", "codex-tui")
    assert session_pulse.handle(_event("SessionStart", t, tmp_path)) == Reply()
    assert record.draft_path("u1").is_file()
    assert _records() == []
    draft = record.read_draft("u1")
    assert draft["tool"] == "codex" and draft["origin"] == "live" and draft["started_at"]
    assert draft["project"] == "unregistered" and draft["cwd"] == str(tmp_path)


def test_start_then_end_writes_one_record(tmp_path):
    t = _codex(tmp_path / ".codex" / "sessions" / "rollout-1.jsonl", "codex-tui")
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    started = record.read_draft("u1")["started_at"]
    session_pulse.handle(_event("SessionStart", t, tmp_path))   # resume: same draft
    assert record.read_draft("u1")["started_at"] == started
    assert session_pulse.handle(_event("SessionEnd", t, tmp_path)) == Reply()
    files = _records()
    assert len(files) == 1
    meta = _meta(files[0])
    assert meta["session_id"] == "u1" and meta["tool"] == "codex" and meta["origin"] == "live"
    assert meta["started_at"] == started and meta["ended_at"] and meta["user_msgs"] == 1
    assert meta["transcript"] == str(t) and meta["project"] == "unregistered"
    assert not record.draft_path("u1").exists()


def test_end_records_user_msgs(tmp_path):
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui", user_msgs=2)
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _meta(_records()[0])["user_msgs"] == 2


def test_end_without_user_messages_leaves_no_record(tmp_path):
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui", user_msgs=0)
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _records() == []
    assert not record.draft_path("u1").exists()


def test_end_without_user_messages_still_closes_an_existing_record(tmp_path):
    record.upsert("u1", {"project": "p", "tool": "codex", "started_at": "2026-10-19T10:00:00Z"})
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui", user_msgs=0)
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _meta(_records()[0])["ended_at"]


def test_codex_exec_writes_nothing(tmp_path):
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex_exec")
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _records() == [] and not record.draft_path("u1").exists()


def test_subagent_writes_nothing(tmp_path):
    t = _codex(tmp_path / "subagents" / "agent-1.jsonl", "codex-tui")
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _records() == [] and not record.draft_path("u1").exists()


def test_skip_env_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PULSE_SKIP", "1")
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui")
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _records() == [] and not record.draft_path("u1").exists()


def test_empty_session_id_writes_nothing(tmp_path):
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui")
    session_pulse.handle(_event("SessionStart", t, tmp_path, sid=""))
    assert not (paths.state_dir() / "pulse").exists()


def test_handler_never_raises_on_missing_transcript(tmp_path):
    t = tmp_path / ".codex" / "sessions" / "missing.jsonl"
    assert session_pulse.handle(_event("SessionStart", t, tmp_path)) == Reply()
    assert record.read_draft("u1")["origin"] == "unknown"
    session_pulse.handle(_event("SessionEnd", t, tmp_path))
    assert _records() == []


def test_claude_origin_from_entrypoint_without_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    t = tmp_path / "projects" / "missing.jsonl"
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    draft = record.read_draft("u1")
    assert draft["origin"] == "live" and draft["tool"] == "claude"


def test_claude_headless_entrypoint_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    session_pulse.handle(_event("SessionStart", tmp_path / "missing.jsonl", tmp_path))
    assert not record.draft_path("u1").exists()


def test_registered_in_handlers_and_hooks_json():
    assert "session-pulse" in hooks.HANDLERS
    data = json.loads((ROOT / "plugins" / "h2t-core" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for event in ("SessionStart", "SessionEnd"):
        commands = [h["command"] for g in data["hooks"][event] for h in g["hooks"]]
        assert any('hooks/run" session-pulse' in c for c in commands), event


def test_git_branch_reaches_the_draft(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q", "-b", "main"], check=True)
    t = _codex(tmp_path / ".codex" / "s" / "r.jsonl", "codex-tui")
    session_pulse.handle(_event("SessionStart", t, tmp_path))
    draft = record.read_draft("u1")
    assert draft["branch"] == "main"
    assert Path(draft["repo"]).resolve() == tmp_path.resolve()
