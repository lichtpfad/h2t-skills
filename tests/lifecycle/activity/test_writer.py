import json

import pytest

from h2t_ops.core import paths
from h2t_ops.lifecycle.activity.writer import log_session_end, log_session_start


@pytest.fixture
def spool(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")
    return paths.activity_file("test-machine")


def test_log_session_start_creates_spool(spool):
    result = log_session_start("my-session-123", "dev", "h2t-ai")
    assert spool.exists()
    record = json.loads(spool.read_text().strip())
    assert record["session_id"] == "my-session-123"
    assert record["action"] == "session.start"
    assert record["domain"] == "dev"
    assert record["project"] == "h2t-ai"
    assert "timestamp" in record
    assert result == str(spool)


def test_log_session_end_appends_with_artifacts(spool):
    log_session_start("ses-1", "dev", "proj-a")
    log_session_end("ses-1", "dev", "proj-a", artifacts=[{"type": "commit", "ref": "abc123"}])
    lines = spool.read_text().strip().splitlines()
    assert len(lines) == 2
    end_record = json.loads(lines[1])
    assert end_record["action"] == "session.end"
    assert end_record["artifacts"][0]["type"] == "commit"


def test_the_spool_is_one_file_per_machine_under_records(spool, tmp_path, monkeypatch):
    """records/activity/<machine>.jsonl; the 3.x H2T_ACTIVITY_SPOOL is not read (R5)."""
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "old" / "spool.jsonl"))
    log_session_start("s", "art", "my-project")
    assert spool == paths.records("activity") / "test-machine.jsonl"
    assert spool.exists()
    assert not (tmp_path / "old").exists()


def test_log_machine_uses_hostname_by_default(monkeypatch):
    monkeypatch.delenv("H2T_MACHINE_NAME", raising=False)
    monkeypatch.delenv("DOR_MACHINE_NAME", raising=False)
    log_session_start("s", "dev", "p")
    record = json.loads(paths.activity_file(paths.machine_name()).read_text().strip())
    assert len(record["machine"]) > 0


def test_writer_cli_start(spool, monkeypatch):
    """CLI: `writer.py start` subcommand writes correct record to spool."""
    from h2t_ops.lifecycle.activity.writer import main as writer_main

    monkeypatch.setattr("sys.argv", [
        "writer.py", "start",
        "--session-id", "cli-ses-1",
        "--domain", "dev",
        "--project", "h2t-core",
    ])
    writer_main()
    record = json.loads(spool.read_text().strip())
    assert record["session_id"] == "cli-ses-1"
    assert record["action"] == "session.start"
    assert record["domain"] == "dev"
