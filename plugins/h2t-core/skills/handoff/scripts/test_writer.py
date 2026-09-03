from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_writer():
    path = Path(__file__).with_name("writer.py")
    spec = importlib.util.spec_from_file_location("handoff_writer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_default_markdown_dir_uses_h2t_session_root(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    path = writer.default_markdown_dir("repo")

    assert path == tmp_path / "sessions" / "test-machine" / "repo"
    assert ".dor" not in str(path)


def test_write_handoff_writes_bounded_latest_index(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    long_done = "done " * 1000
    long_remains = "\n".join(f"- [ ] item {i} " + ("x" * 500) for i in range(10))
    result = writer.write_handoff(
        session_id="dev-repo-test-2026-05-22",
        domain="dev",
        project="repo",
        what_done=long_done,
        what_remains=long_remains,
        artifacts=[f"commit:{i}" for i in range(20)],
    )

    latest_path = Path(result["latest"])
    latest = json.loads(latest_path.read_text(encoding="utf-8"))

    assert latest_path == tmp_path / "sessions" / "test-machine" / "repo" / "latest.json"
    assert Path(result["markdown"]).is_file()
    assert latest["version"] == 1
    assert len(latest["summary_short"]) <= writer.SUMMARY_LIMIT
    assert len(latest["next_actions"]) == writer.MAX_ITEMS
    assert all(len(item) <= writer.ITEM_LIMIT for item in latest["next_actions"])
    assert len(latest["artifacts"]) == writer.MAX_ARTIFACTS
    assert latest["truncated"] is True


def test_write_handoff_deduplicates_artifacts_and_carry_forward_items(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    result = writer.write_handoff(
        session_id="dev-repo-dedupe-2026-05-26",
        domain="dev",
        project="repo",
        what_done="- added deploy\n- added deploy",
        what_remains="- [ ] ship release\n- [ ] ship release\n- [ ] verify deploy",
        artifacts=["commit:abc123", "commit:abc123", "issue:185"],
    )

    latest = json.loads(Path(result["latest"]).read_text(encoding="utf-8"))
    refs = [(item["type"], item["ref"]) for item in latest["artifacts"]]

    assert result["artifacts"] == 2
    assert refs == [("commit", "abc123"), ("issue", "185")]
    assert latest["next_actions"] == ["ship release", "verify deploy"]


def test_write_handoff_returns_degraded_when_markdown_write_fails(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    original_write_text = Path.write_text

    def fail_only_markdown(self, content, encoding="utf-8"):
        if self.name.endswith(".md"):
            raise OSError("mirror write failed")
        return original_write_text(self, content, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", fail_only_markdown)

    result = writer.write_handoff(
        session_id="dev-repo-degraded-2026-05-26",
        domain="dev",
        project="repo",
        what_done="- finished task",
        what_remains="- [ ] next task",
        artifacts=["commit:abc123"],
    )

    latest = json.loads(Path(result["latest"]).read_text(encoding="utf-8"))

    assert result["status"] == "degraded"
    assert result["mirror_write_failed"] is True
    assert result["markdown"] == ""
    assert Path(result["latest"]).is_file()
    assert latest["markdown_path"] == ""


def test_response_counts_what_was_recorded_not_the_capped_index(tmp_path, monkeypatch):
    """`artifacts` in the response must describe the durable record, not latest.json.

    Reproduced in a real handoff on 2026-09-03: eleven artifacts in, `"artifacts": 10`
    and `"status": "ok"` out. Nothing was lost — the markdown carries all eleven and the
    index flags itself `truncated` — but the number the caller reads counts the bounded
    index while its name promises the handoff's artifacts, and no field in the response
    tells the two apart (#438). `_degraded` already reports `len(parsed_artifacts)`, so
    the two exit paths disagreed about what the field means.
    """
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    given = [f"commit:{i:02d}" for i in range(writer.MAX_ARTIFACTS + 1)]
    result = writer.write_handoff(
        session_id="dev-repo-count-2026-09-03",
        domain="dev",
        project="repo",
        what_done="- one line",
        what_remains="- [ ] one item",
        artifacts=given,
    )

    assert result["artifacts"] == len(given)
    assert result["index_truncated"] is True

    # the last one is the one that fell out of the index, and it must still be recorded
    latest = json.loads(Path(result["latest"]).read_text(encoding="utf-8"))
    assert len(latest["artifacts"]) == writer.MAX_ARTIFACTS
    assert Path(result["markdown"]).read_text(encoding="utf-8").count("commit: ") == len(given)


def test_response_says_not_truncated_when_everything_fits(tmp_path, monkeypatch):
    """The flag has to distinguish, or it carries no information."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "activity" / "spool.jsonl"))

    result = writer.write_handoff(
        session_id="dev-repo-fits-2026-09-03",
        domain="dev",
        project="repo",
        what_done="- one line",
        what_remains="- [ ] one item",
        artifacts=["commit:abc1234", "pr:470"],
    )

    assert result["artifacts"] == 2
    assert result["index_truncated"] is False
