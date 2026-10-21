"""The model summary: once per transcript state, never for a handoff, capped, never the real model."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from h2t_ops.lifecycle.index import query
from h2t_ops.lifecycle.pulse import record, summary


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


def _transcript(path: Path, user: str = "fix the bug", assistant: str = "fixed") -> Path:
    recs = [{"timestamp": "2026-10-10T10:00:00Z", "type": "user", "cwd": "/x", "entrypoint": "cli",
             "message": {"role": "user", "content": user}},
            {"timestamp": "2026-10-10T10:05:00Z", "type": "assistant", "cwd": "/x", "entrypoint": "cli",
             "message": {"role": "assistant", "content": assistant}}]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return path


def _session(sid: str, tmp_path: Path, **over) -> Path:
    tr = _transcript(tmp_path / "tr" / f"{sid}.jsonl")
    record.upsert(sid, {"tool": "claude", "origin": "live", "user_msgs": 1, "project": "p1",
                        "transcript": str(tr), **over})
    return tr


def _run(ask, **kw) -> dict:
    with query.connect() as conn:
        return summary.run(conn, ask=ask, **kw)


def _stored(sid: str) -> dict:
    with query.connect() as conn:
        row = conn.execute("SELECT summary, summary_source, summary_stamp FROM sessions "
                           "WHERE session_id = ?", (sid,)).fetchone()
    return dict(row)


def test_summary_written_once_per_transcript_state(tmp_path):
    tr = _session("s1", tmp_path)
    calls: list[str] = []

    def ask(prompt: str) -> str:
        calls.append(prompt)
        return "Починили баг."

    assert _run(ask) == {"written": 1, "skipped": 0}
    stored = _stored("s1")
    st = tr.stat()
    assert stored == {"summary": "Починили баг.", "summary_source": "model",
                      "summary_stamp": f"{st.st_size}:{st.st_mtime_ns}"}
    assert calls[0].startswith("Ниже — запись рабочей сессии.")
    assert _run(ask) == {"written": 0, "skipped": 0}      # same transcript state: not asked again
    assert len(calls) == 1
    _transcript(tr, user="fix another bug")                # transcript changed
    assert _run(ask) == {"written": 1, "skipped": 0}
    assert len(calls) == 2


def test_session_with_handoff_is_not_summarized(tmp_path):
    _session("s1", tmp_path, done="Всё сделано")
    asked: list[str] = []
    assert _run(lambda p: asked.append(p) or "x") == {"written": 0, "skipped": 0}
    assert asked == []


def test_cap_limits_calls(tmp_path):
    for i in range(5):
        _session(f"s{i}", tmp_path)
    asked: list[str] = []
    result = _run(lambda p: asked.append(p) or "итог", cap=2)
    assert len(asked) == 2
    assert result["written"] == 2


def test_failed_answer_is_skipped_and_writes_nothing(tmp_path):
    _session("s1", tmp_path)
    assert _run(lambda p: "   ") == {"written": 0, "skipped": 1}
    assert _stored("s1")["summary"] in (None, "")


def test_ask_runs_with_skip_env_and_no_persistence(monkeypatch):
    seen: dict = {}

    def fake_run(args, **kw):
        seen.update(args=args, **kw)
        return subprocess.CompletedProcess(args, 0, stdout="  итог\n", stderr="")

    monkeypatch.setattr(summary.shutil, "which", lambda name: "/bin/claude")
    monkeypatch.setattr(summary.subprocess, "run", fake_run)
    monkeypatch.delenv("H2T_PULSE_SKIP", raising=False)
    assert summary._ask_claude("prompt") == "итог"
    assert "--no-session-persistence" in seen["args"]
    assert seen["args"][1:4] == ["-p", "--model", "haiku"]
    assert seen["env"]["H2T_PULSE_SKIP"] == "1"
    assert seen["input"] == "prompt"
    assert seen["timeout"] == 120
    assert "H2T_PULSE_SKIP" not in os.environ


def test_ask_without_claude_binary_is_a_failed_answer(monkeypatch):
    monkeypatch.setattr(summary.shutil, "which", lambda name: None)
    assert summary._ask_claude("prompt") == ""


def test_excerpt_keeps_head_and_tail(tmp_path):
    tr = _transcript(tmp_path / "t.jsonl", user="HEAD" + "x" * 5000, assistant="y" * 5000 + "TAIL")
    out = summary.excerpt("claude", tr, limit=1000)
    assert len(out) <= 1000
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")
