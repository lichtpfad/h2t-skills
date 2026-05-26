from __future__ import annotations

import json
import os
from pathlib import Path

from gather.sessions import (
    find_latest_session_index,
    find_session_files,
    get_machine_name,
)


def test_get_machine_name_prefers_h2t_env(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "h2t-name")
    monkeypatch.setenv("DOR_MACHINE_NAME", "dor-name")

    assert get_machine_name() == "h2t-name"


def test_find_sessions_prefers_h2t_root_and_reads_legacy(tmp_path, monkeypatch):
    h2t_root = tmp_path / "h2t" / "sessions"
    dor_home = tmp_path / "home"
    h2t_file = h2t_root / "machine-a" / "repo" / "new.md"
    legacy_file = dor_home / ".dor" / "sessions" / "machine-b" / "repo" / "old.md"
    h2t_file.parent.mkdir(parents=True)
    legacy_file.parent.mkdir(parents=True)
    h2t_file.write_text("new", encoding="utf-8")
    legacy_file.write_text("old", encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(h2t_root))
    monkeypatch.setattr(Path, "home", lambda: dor_home)

    files = find_session_files("repo")

    assert str(h2t_file) in files
    assert str(legacy_file) in files


def test_find_latest_session_index_returns_none_when_only_markdown_exists(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    md = root / "machine-a" / "repo" / "old.md"
    md.parent.mkdir(parents=True)
    md.write_text("legacy handoff", encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    result = find_latest_session_index("repo")

    assert result is None


def test_find_latest_session_index_uses_newest_latest_json_only(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    older = root / "machine-a" / "repo" / "latest.json"
    newer = root / "machine-b" / "repo" / "latest.json"
    older.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_text(json.dumps({"version": 1, "session_id": "older"}), encoding="utf-8")
    newer.write_text(json.dumps({"version": 1, "session_id": "newer"}), encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    newer_stat = newer.stat()
    os.utime(newer, (newer_stat.st_atime + 10, newer_stat.st_mtime + 10))

    result = find_latest_session_index("repo")

    assert result is not None
    assert result["session_id"] == "newer"


def test_find_latest_session_index_repo_lookup_is_v1_boundary(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    latest = root / "machine-a" / "project-only" / "latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps({"version": 1, "session_id": "s1"}), encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    result = find_latest_session_index("non-repo-context")

    assert result is None


def test_find_latest_session_index_is_bounded(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    latest = root / "machine-a" / "repo" / "latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text(json.dumps({
        "version": 1,
        "session_id": "s1",
        "summary_short": "x" * 4000,
        "next_actions": ["a" * 1000 for _ in range(20)],
        "blockers": ["b" * 1000 for _ in range(20)],
        "artifacts": [{"type": "commit", "ref": str(i)} for i in range(20)],
    }), encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    result = find_latest_session_index("repo")

    assert result is not None
    assert len(result["summary_short"]) <= 1200
    assert len(result["next_actions"]) == 5
    assert all(len(item) <= 240 for item in result["next_actions"])
    assert len(result["blockers"]) == 5
    assert len(result["artifacts"]) == 10
