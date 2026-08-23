import json
import os
import sys
from pathlib import Path

import pytest

from lib.activity.writer import log_session_end, log_session_start


def test_log_session_start_creates_spool(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        result = log_session_start("my-session-123", "dev", "h2t-ai")
        assert spool.exists()
        record = json.loads(spool.read_text().strip())
        assert record["session_id"] == "my-session-123"
        assert record["action"] == "session.start"
        assert record["domain"] == "dev"
        assert record["project"] == "h2t-ai"
        assert "timestamp" in record
        assert result == str(spool)
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_session_end_appends_with_artifacts(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("ses-1", "dev", "proj-a")
        log_session_end("ses-1", "dev", "proj-a", artifacts=[{"type": "commit", "ref": "abc123"}])
        lines = spool.read_text().strip().splitlines()
        assert len(lines) == 2
        end_record = json.loads(lines[1])
        assert end_record["action"] == "session.end"
        assert end_record["artifacts"][0]["type"] == "commit"
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_creates_parent_directories(tmp_path):
    spool = tmp_path / "nested" / "deep" / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("s", "art", "my-project")
        assert spool.exists()
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_machine_uses_hostname_by_default(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("s", "dev", "p")
        record = json.loads(spool.read_text().strip())
        assert len(record["machine"]) > 0
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_writer_cli_start(tmp_path, monkeypatch):
    """CLI: `writer.py start` subcommand writes correct record to spool."""
    from lib.activity.writer import main as writer_main

    spool = tmp_path / "cli_spool.jsonl"
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(spool))
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
