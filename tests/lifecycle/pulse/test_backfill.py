"""Backfill: records for sessions the hook missed, built from transcripts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.pulse import backfill, record


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


def _write(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _user(ts: str, text: str, cwd: str, **extra) -> dict:
    return {"timestamp": ts, "type": "user", "cwd": cwd, "entrypoint": "cli",
            "message": {"role": "user", "content": text}, **extra}


def _claude(root: Path, name: str, cwd: str, texts=("hi",), end="2026-10-01T10:05:00Z") -> Path:
    recs = [_user("2026-10-01T10:00:00Z", t, cwd) for t in texts] or [
        {"timestamp": "2026-10-01T10:00:00Z", "type": "summary", "cwd": cwd, "entrypoint": "cli"}]
    recs.append({"timestamp": end, "type": "assistant", "cwd": cwd, "entrypoint": "cli",
                 "message": {"role": "assistant", "content": "ok"}})
    return _write(root / "proj" / f"{name}.jsonl", recs)


def _codex(root: Path, sid: str, originator: str, cwd: str) -> Path:
    return _write(root / "2026" / "10" / f"rollout-{sid}.jsonl", [
        {"timestamp": "2026-10-01T10:00:00Z", "type": "session_meta",
         "payload": {"id": sid, "cwd": cwd, "originator": originator}},
        {"timestamp": "2026-10-01T10:01:00Z", "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "hello"}]}},
    ])


def _meta(sid: str) -> dict:
    found = record.find(sid, "test-machine")
    assert found is not None
    return session_record.parse(found.read_bytes())[0]


def _md_files() -> list[Path]:
    return sorted(paths.records("sessions").rglob("*.md"))


def test_backfill_writes_live_skips_machine_subagent_empty(tmp_path):
    cwd = str(tmp_path / "work")
    claude_root, codex_root = tmp_path / "claude", tmp_path / "codex"
    _claude(claude_root, "live-1", cwd)
    _claude(claude_root, "agent-sub", cwd)                 # subagent: not counted at all
    _claude(claude_root, "empty-1", cwd, texts=())         # 0 user messages
    _codex(codex_root, "cx-exec", "codex_exec", cwd)       # machine
    _codex(codex_root, "cx-tui", "codex-tui", cwd)         # live
    out = backfill.run(claude_root, codex_root)
    assert out["written"] == 2
    assert out["skipped_machine"] == 1
    assert out["skipped_empty"] == 1
    assert out["seen"] == 4
    assert _meta("live-1")["tool"] == "claude"
    assert _meta("live-1")["origin"] == "live"
    assert _meta("cx-tui")["tool"] == "codex"
    assert record.find("empty-1", "test-machine") is None
    assert record.find("agent-sub", "test-machine") is None


def test_backfill_updates_end_of_a_hook_record(tmp_path):
    cwd = str(tmp_path / "work")
    claude_root = tmp_path / "claude"
    _claude(claude_root, "u1", cwd, end="2026-10-01T11:00:00Z")
    record.upsert("u1", {"project": "unregistered", "tool": "claude", "cwd": cwd,
                         "started_at": "2026-10-01T10:00:00Z"})
    assert not _meta("u1").get("ended_at")
    out = backfill.run(claude_root, tmp_path / "codex")
    assert out["written"] == 1
    meta = _meta("u1")
    assert meta["ended_at"] == "2026-10-01T11:00:00Z"
    assert meta["origin"] == "live"
    assert len(_md_files()) == 1


def test_backfill_is_idempotent(tmp_path):
    cwd = str(tmp_path / "work")
    claude_root, codex_root = tmp_path / "claude", tmp_path / "codex"
    _claude(claude_root, "u1", cwd)
    _codex(codex_root, "cx-tui", "codex-tui", cwd)
    assert backfill.run(claude_root, codex_root)["written"] == 2
    again = backfill.run(claude_root, codex_root)
    assert again["written"] == 0
    assert again["seen"] == 2
    assert len(_md_files()) == 2


def test_since_skips_old_files(tmp_path):
    cwd = str(tmp_path / "work")
    claude_root = tmp_path / "claude"
    old = _claude(claude_root, "old-1", cwd)
    new = _claude(claude_root, "new-1", cwd)
    os.utime(old, ns=(1_000_000_000, 1_000_000_000))
    since = new.stat().st_mtime_ns - 1_000
    out = backfill.run(claude_root, tmp_path / "codex", since_ns=since)
    assert out["seen"] == 1 and out["written"] == 1
    assert record.find("old-1", "test-machine") is None
    assert record.find("new-1", "test-machine") is not None
