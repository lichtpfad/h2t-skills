from __future__ import annotations

import json
import subprocess
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.lifecycle import handoff, session_record


def _load_writer():
    return handoff


def test_default_markdown_dir_is_under_records(monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    path = writer.default_markdown_dir("repo")

    assert path == paths.records("sessions", "test-machine") / "repo"
    assert ".dor" not in str(path)


def test_write_handoff_writes_bounded_latest_index(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

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

    assert latest_path == paths.records("sessions", "test-machine") / "repo" / "latest.json"
    assert Path(result["markdown"]).is_file()
    assert latest["version"] == 1
    assert len(latest["summary_short"]) <= writer.SUMMARY_LIMIT
    assert len(latest["next_actions"]) == writer.MAX_ITEMS
    assert all(len(item) <= writer.ITEM_LIMIT for item in latest["next_actions"])
    assert len(latest["artifacts"]) == writer.MAX_ARTIFACTS
    assert latest["truncated"] is True


def test_write_handoff_deduplicates_artifacts_and_carry_forward_items(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

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
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    # A create that fails for every name: no -2, -3 can rescue the md.
    def fail(path, *a, **kw):
        raise OSError("mirror write failed")

    monkeypatch.setattr(store, "create", fail)

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
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

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
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

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


def _git_checkout(path: Path) -> Path:
    """A repository of the test's own, so branch and commits do not depend on the runner."""
    path.mkdir()
    for argv in (["init", "-q", "-b", "topic"], ["commit", "-q", "--allow-empty", "-m", "one"]):
        subprocess.run(["git", *argv], cwd=path, check=True)
    return path


def _handoff(writer, session_id="dev-repo-record-2026-10-18", done="- did it", **kw):
    return writer.write_handoff(session_id=session_id, domain="dev", project="repo",
                                what_done=done, what_remains="- [ ] next",
                                artifacts=["commit:abc123"], **kw)


def test_handoff_writes_a_self_describing_md_and_latest_beside_it(tmp_path, monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.chdir(_git_checkout(tmp_path / "checkout"))

    result = _handoff(writer)

    md = Path(result["markdown"])
    assert md == session_record.session_path("test-machine", "repo", "dev-repo-record-2026-10-18")
    meta, body = session_record.parse(md.read_bytes())
    assert (meta["machine"], meta["project"], meta["domain"]) == ("test-machine", "repo", "dev")
    assert meta["updated_at"].endswith("Z") and meta["branch"] == "topic"
    assert len(meta["commits"]) == 1 and meta["done"] == "- did it"
    assert body.startswith(b"# Session: dev-repo-record-2026-10-18\n")
    # R10: until Task 16, latest.json sits beside the md and points at it.
    latest = json.loads((md.parent / "latest.json").read_text(encoding="utf-8"))
    assert Path(result["latest"]) == md.parent / "latest.json"
    assert latest["markdown_path"] == str(md)


def test_a_second_handoff_of_the_same_session_updates_its_record(monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    first = _handoff(writer, done="- first")
    second = _handoff(writer, done="- second")

    assert first["markdown"] == second["markdown"]
    md = Path(second["markdown"])
    assert sorted(p.name for p in md.parent.glob("*.md")) == [md.name]
    assert session_record.parse(md.read_bytes())[0]["done"] == "- second"


def test_existing_foreign_md_is_never_overwritten(monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    target = session_record.session_path("test-machine", "repo", "dev-repo-record-2026-10-18")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"# my own notes, no frontmatter\n")

    result = _handoff(writer)

    assert target.read_bytes() == b"# my own notes, no frontmatter\n"
    assert Path(result["markdown"]) == target.with_name("dev-repo-record-2026-10-18-2.md")
    assert any(str(target) in n and result["markdown"] in n for n in result["notes"])
    # The same session again: its own -2 record is updated, the foreign file still untouched.
    again = _handoff(writer, done="- again")
    assert again["markdown"] == result["markdown"]
    assert session_record.parse(Path(again["markdown"]).read_bytes())[0]["done"] == "- again"
    assert target.read_bytes() == b"# my own notes, no frontmatter\n"


def test_the_old_session_root_variable_is_not_read(tmp_path, monkeypatch):
    """R5: H2T_SESSION_ROOT is a 3.x name; 4.0 writes records/ whatever it says."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "old-sessions"))

    result = _handoff(writer)

    assert Path(result["markdown"]).parent == paths.records("sessions", "test-machine") / "repo"
    assert not (tmp_path / "old-sessions").exists()


def _spool_rows():
    return paths.activity_file("test-machine").read_text(encoding="utf-8").splitlines()


def test_a_refused_markdown_dir_degrades_after_the_spool_row(monkeypatch):
    """--markdown-dir into a package place is refused (WriteRefused, not OSError); the
    spool row is already written, so it must come back as _degraded, never an exception."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    result = _handoff(writer, markdown_dir=str(paths.secrets_shared()))

    assert result["status"] == "degraded" and result["mirror_write_failed"] is True
    assert result["mirror_error"].startswith("WriteRefused")
    assert "dev-repo-record-2026-10-18" in _spool_rows()[-1]
    assert not paths.secrets_shared().exists()


def test_refused_latest_json_degrades_after_the_spool_row(monkeypatch):
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    real_replace = store.replace

    def refuse_latest(path, *a, **kw):
        if Path(path).name == "latest.json":
            raise store.WriteRefused(f"{path}: refused for the test")
        return real_replace(path, *a, **kw)

    monkeypatch.setattr(store, "replace", refuse_latest)

    result = _handoff(writer)

    assert result["status"] == "degraded" and result["mirror_write_failed"] is True
    assert result["mirror_error"].startswith("WriteRefused")
    assert "dev-repo-record-2026-10-18" in _spool_rows()[-1]


def test_refused_md_degrades_and_keeps_latest(monkeypatch):
    """The md branch: a WriteRefused from create is a mirror failure like an OSError."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")

    def refuse(path, *a, **kw):
        raise store.WriteRefused(f"{path}: refused for the test")

    monkeypatch.setattr(store, "create", refuse)

    result = _handoff(writer)

    assert result["status"] == "degraded" and result["mirror_write_failed"] is True
    assert result["markdown"] == ""
    assert json.loads(Path(result["latest"]).read_text(encoding="utf-8"))["markdown_path"] == ""
    assert "dev-repo-record-2026-10-18" in _spool_rows()[-1]


def test_refused_backfill_keeps_the_md(monkeypatch):
    """The markdown_path backfill: the second latest.json write refused, the md stays."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    real_replace = store.replace
    seen = []

    def refuse_second_latest(path, *a, **kw):
        if Path(path).name == "latest.json":
            seen.append(path)
            if len(seen) == 2:
                raise store.WriteRefused(f"{path}: refused for the test")
        return real_replace(path, *a, **kw)

    monkeypatch.setattr(store, "replace", refuse_second_latest)

    result = _handoff(writer)

    assert result["status"] == "degraded" and result["mirror_write_failed"] is True
    assert Path(result["markdown"]).is_file()


def test_an_unreadable_path_at_the_md_name_is_foreign(monkeypatch):
    """A directory at <id>.md cannot be read, so it is not this session's record: it is
    left alone and the record lands in <id>-2.md."""
    writer = _load_writer()
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    blocker = session_record.session_path("test-machine", "repo", "dev-repo-record-2026-10-18")
    blocker.mkdir(parents=True)

    result = _handoff(writer)

    assert result["status"] == "ok", result
    assert Path(result["markdown"]) == blocker.with_name("dev-repo-record-2026-10-18-2.md")
    assert blocker.is_dir() and list(blocker.iterdir()) == []
    assert "dev-repo-record-2026-10-18" in _spool_rows()[-1]


def test_spool_frontmatter_and_directory_name_one_machine(monkeypatch):
    """The machine is resolved once; a name that changes between calls (hostname drift,
    #491) must not split one handoff across machines."""
    writer = _load_writer()
    names = iter(f"m{i}" for i in range(1, 10))
    monkeypatch.setattr(paths, "machine_name", lambda: next(names))

    result = _handoff(writer)

    md = Path(result["markdown"])
    row = json.loads(Path(result["spool"]).read_text(encoding="utf-8").splitlines()[-1])
    meta, _ = session_record.parse(md.read_bytes())
    assert row["machine"] == meta["machine"] == md.parent.parent.name == "m1"
    assert Path(result["spool"]).name == "m1.jsonl"
