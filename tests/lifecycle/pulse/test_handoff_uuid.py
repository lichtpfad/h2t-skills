"""Handoff writes into the session's UUID record when the program's own id is known."""

from __future__ import annotations

import pytest

from h2t_ops.core import paths, store
from h2t_ops.lifecycle import handoff, session_record
from h2t_ops.lifecycle.gather import sessions
from h2t_ops.lifecycle.pulse import record


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setattr(record, "CODEX_ID_VARS", ("FAKE_CODEX_ID",))
    monkeypatch.setattr(record, "CODEX_SHELL_MARKERS", ("FAKE_CODEX_SHELL",))
    monkeypatch.delenv("FAKE_CODEX_ID", raising=False)
    monkeypatch.delenv("FAKE_CODEX_SHELL", raising=False)
    monkeypatch.chdir(tmp_path)


def _md_files():
    return sorted(paths.records("sessions").rglob("*.md"))


def _handoff(slug="dev-x-topic-2026-10-19"):
    return handoff.write_handoff(slug, "dev", "x", "- did", "- [ ] next", ["commit:abc1234"])


def test_handoff_with_claude_id_enriches_the_hook_record(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "u1")
    hook_path = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z"})
    res = _handoff()
    assert res["markdown"] == str(hook_path) and res["session_uuid"] == "u1"
    meta, body = session_record.parse(hook_path.read_bytes())
    assert meta["name"] == "dev-x-topic-2026-10-19" and meta["started_at"] == "2026-10-19T10:00:00Z"
    assert meta["tool"] == "claude" and meta["project"] == "x"
    assert meta["done"] == "- did" and b"## What Was Done" in body
    assert len(_md_files()) == 1


def test_handoff_with_claude_id_and_only_a_draft_promotes_it(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "u2")
    record.write_draft("u2", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z"})
    res = _handoff()
    assert res["session_uuid"] == "u2"
    assert record.read_draft("u2") == {}
    assert len(_md_files()) == 1


def _open_codex(sid, cwd):
    record.write_draft(sid, {"project": "unregistered", "tool": "codex", "cwd": str(cwd),
                             "started_at": "2026-10-19T10:00:00Z"})


def test_codex_handoff_by_id_var(monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_ID", "cx9")
    res = _handoff()
    assert res["session_uuid"] == "cx9"
    meta, _ = session_record.parse(_md_files()[0].read_bytes())
    assert meta["session_id"] == "cx9" and meta["tool"] == "codex"


def test_codex_handoff_finds_the_single_open_record(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CODEX_SHELL", "1")
    _open_codex("cx1", tmp_path)
    res = _handoff()
    assert res["session_uuid"] == "cx1"
    meta, _ = session_record.parse(_md_files()[0].read_bytes())
    assert meta["session_id"] == "cx1" and meta["name"] == "dev-x-topic-2026-10-19"
    assert meta["tool"] == "codex" and meta["done"] == "- did"
    assert len(_md_files()) == 1


def test_codex_handoff_ambiguous_writes_marked_slug_record(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CODEX_SHELL", "1")
    _open_codex("cx1", tmp_path)
    _open_codex("cx2", tmp_path)
    res = _handoff()
    assert "session_uuid" not in res
    files = _md_files()
    assert [f.stem for f in files] == ["dev-x-topic-2026-10-19"]
    meta, _ = session_record.parse(files[0].read_bytes())
    assert meta["tool"] == "codex" and meta["origin"] == "live" and meta["user_msgs"] == 1
    assert sorted(meta["candidates"]) == ["cx1", "cx2"]
    assert meta["cwd"] == str(tmp_path)
    assert record.read_draft("cx1")["project"] == "unregistered"
    assert record.read_draft("cx2")["project"] == "unregistered"


def test_codex_handoff_with_no_open_record_has_no_candidates(monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_SHELL", "1")
    _handoff()
    meta, _ = session_record.parse(_md_files()[0].read_bytes())
    assert meta["tool"] == "codex" and "candidates" not in meta


def test_handoff_without_program_id_keeps_the_slug_file():
    res = _handoff()
    assert "session_uuid" not in res
    files = _md_files()
    assert [f.stem for f in files] == ["dev-x-topic-2026-10-19"]
    meta, _ = session_record.parse(files[0].read_bytes())
    assert meta["session_id"] == "dev-x-topic-2026-10-19"
    assert "tool" not in meta


def test_program_session_none_without_markers():
    assert record.program_session() is None


def _seed(session_id, updated_at, done):
    meta = {"session_id": session_id, "machine": "test-machine", "project": "briefproj",
            "date": "2026-10-19", "updated_at": updated_at}
    if done:
        meta["done"] = done
    target = session_record.session_path("test-machine", "briefproj", session_id)
    store.create(target, session_record.render(meta, b""), place="records.sessions")


def test_briefing_skips_hook_only_records():
    _seed("handoff-one", "2026-10-19T10:00:00Z", "- did")
    _seed("hook-two", "2026-10-19T11:00:00Z", "")
    assert sessions.find_latest_session_index("briefproj")["session_id"] == "handoff-one"
    assert len(sessions.find_session_files("briefproj")) == 1


def test_explicit_markdown_dir_wins_over_the_uuid_record(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "u1")
    hook_path = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z"})
    before = hook_path.read_bytes()
    target = tmp_path / "chosen"
    res = handoff.write_handoff("dev-x-topic-2026-10-19", "dev", "x", "- did", "- [ ] next", [],
                                markdown_dir=str(target))
    assert "session_uuid" not in res
    assert res["markdown"] == str(target / "dev-x-topic-2026-10-19.md")
    assert (target / "dev-x-topic-2026-10-19.md").is_file()
    assert hook_path.read_bytes() == before
