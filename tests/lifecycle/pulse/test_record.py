"""The UUID-keyed session record: one file per session id, merged, never moved."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from h2t_ops.core import paths
from h2t_ops.lifecycle import index, session_record
from h2t_ops.lifecycle.pulse import record


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _meta(path: Path) -> dict:
    return session_record.parse(path.read_bytes())[0]


def _md_files() -> list[Path]:
    return sorted(paths.records("sessions").rglob("*.md"))


def test_upsert_creates_then_merges_one_file():
    p1 = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z", "cwd": "C:/x"})
    p2 = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T11:00:00Z",
                              "ended_at": "2026-10-19T12:00:00Z"})
    assert p1 == p2
    meta = _meta(p2)
    assert meta["started_at"] == "2026-10-19T10:00:00Z"
    assert meta["ended_at"] == "2026-10-19T12:00:00Z"
    assert meta["cwd"] == "C:/x"
    assert meta["machine"] == "test-machine" and meta["session_id"] == "u1"
    assert meta["date"] and meta["updated_at"]
    assert len(_md_files()) == 1


def test_upsert_finds_record_in_another_project_dir():
    p1 = record.upsert("u1", {"project": "unregistered"})
    p2 = record.upsert("u1", {"project": "x", "ended_at": "2026-10-19T12:00:00Z"})
    assert p1 == p2 and p1.parent.name == "unregistered"
    assert _meta(p2)["project"] == "x"
    assert _md_files() == [p1]
    assert record.find("u1", "test-machine") == p1


def test_project_change_keeps_the_file():
    p = record.upsert("u1", {"project": "unregistered"})
    record.upsert("u1", {"project": "x"})
    assert p.is_file() and p.parent.name == "unregistered"
    assert not (p.parent.parent / "x" / "u1.md").exists()
    with index.connect() as conn:
        rows = conn.execute("SELECT project FROM sessions WHERE session_id='u1'").fetchall()
    assert [r["project"] for r in rows] == ["x"]


def test_upsert_keeps_given_body_else_existing_body():
    p = record.upsert("u1", {"project": "p"}, body=b"# one\n")
    record.upsert("u1", {"project": "p", "branch": "b"})
    assert session_record.parse(p.read_bytes())[1] == b"# one\n"
    record.upsert("u1", {"project": "p"}, body=b"# two\n")
    assert session_record.parse(p.read_bytes())[1] == b"# two\n"


def test_empty_new_value_does_not_erase():
    p = record.upsert("u1", {"project": "p", "cwd": "C:/x"})
    record.upsert("u1", {"project": "p", "cwd": ""})
    assert _meta(p)["cwd"] == "C:/x"


def test_upsert_promotes_a_draft():
    record.write_draft("u1", {"started_at": "2026-10-19T10:00:00Z", "cwd": "C:/x", "tool": "codex"})
    assert record.draft_path("u1").is_file()
    assert _md_files() == []
    p = record.upsert("u1", {"project": "p", "ended_at": "2026-10-19T12:00:00Z"})
    meta = _meta(p)
    assert meta["started_at"] == "2026-10-19T10:00:00Z"
    assert meta["ended_at"] == "2026-10-19T12:00:00Z"
    assert meta["cwd"] == "C:/x" and meta["tool"] == "codex"
    assert not record.draft_path("u1").exists()


def test_upsert_ignores_a_draft_when_the_record_exists_but_drops_it():
    p = record.upsert("u1", {"project": "p", "cwd": "C:/real"})
    record.write_draft("u1", {"cwd": "C:/draft", "tool": "claude"})
    record.upsert("u1", {"project": "p"})
    meta = _meta(p)
    assert meta["cwd"] == "C:/real" and "tool" not in meta
    assert not record.draft_path("u1").exists()


def test_draft_merge_keeps_earliest_start_and_new_non_empty():
    record.write_draft("u1", {"started_at": "2026-10-19T10:00:00Z", "cwd": "C:/a"})
    record.write_draft("u1", {"started_at": "2026-10-19T11:00:00Z", "cwd": "", "branch": "b"})
    assert record.read_draft("u1") == {"started_at": "2026-10-19T10:00:00Z", "cwd": "C:/a", "branch": "b"}


def test_read_draft_absent_is_empty_and_drop_is_quiet():
    assert record.read_draft("nope") == {}
    record.drop_draft("nope")


def test_project_of_unknown_is_unregistered(tmp_path):
    assert record.project_of(str(tmp_path)) == ("unregistered", "")


def test_git_facts_of_a_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "feat")
    facts = record.git_facts(str(wt))
    assert facts["branch"] == "feat"
    assert Path(facts["repo"]).resolve() == repo.resolve()
    assert Path(facts["worktree"]).resolve() == wt.resolve()


def test_git_facts_outside_git_is_empty(tmp_path):
    assert record.git_facts(str(tmp_path)) == {"branch": "", "repo": "", "worktree": ""}


def test_find_open():
    cwd = "C:/r"
    assert record.find_open("codex", cwd) is None
    record.upsert("a", {"project": "p", "tool": "codex", "cwd": cwd, "started_at": "2026-10-19T10:00:00Z"})
    assert record.find_open("codex", cwd) == "a"
    assert record.find_open("claude", cwd) is None
    assert record.find_open("codex", "C:/other") is None
    record.upsert("b", {"project": "p", "tool": "codex", "cwd": cwd, "started_at": "2026-10-19T11:00:00Z"})
    assert record.find_open("codex", cwd) is None
    record.upsert("b", {"project": "p", "ended_at": "2026-10-19T12:00:00Z"})
    assert record.find_open("codex", cwd) == "a"
    record.upsert("a", {"project": "p", "ended_at": "2026-10-19T12:00:00Z"})
    assert record.find_open("codex", cwd) is None


def test_find_open_counts_drafts_and_a_draft_plus_record_once():
    cwd = "C:/r"
    record.write_draft("d", {"tool": "codex", "cwd": cwd, "started_at": "2026-10-19T10:00:00Z"})
    assert record.find_open("codex", cwd) == "d"
    record.upsert("r", {"project": "p", "tool": "codex", "cwd": cwd, "started_at": "2026-10-19T09:00:00Z"})
    assert record.find_open("codex", cwd) is None   # two different sessions
    record.write_draft("r", {"tool": "codex", "cwd": cwd})
    record.drop_draft("d")
    assert record.find_open("codex", cwd) == "r"    # draft + record of one id count once


def test_unregistered_never_overwrites_a_project():
    p = record.upsert("u1", {"project": "x", "domain": "dev"})
    record.upsert("u1", {"project": "unregistered", "domain": ""})
    meta = _meta(p)
    assert meta["project"] == "x" and meta["domain"] == "dev"
    record.upsert("u1", {"project": "y", "domain": "ops"})
    meta = _meta(p)
    assert meta["project"] == "y" and meta["domain"] == "ops"


def test_unregistered_never_overwrites_a_project_in_a_draft():
    record.write_draft("u1", {"project": "x", "domain": "dev"})
    record.write_draft("u1", {"project": "unregistered", "domain": ""})
    assert record.read_draft("u1")["project"] == "x"
    record.write_draft("u1", {"project": "y"})
    assert record.read_draft("u1")["project"] == "y"
