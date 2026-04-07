"""Tests for GEPA batch job."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.skill_graph.gepa_batch import (
    _fetch_eval_findings,
    _load_last_run,
    _save_last_run,
    cmd_approve,
    cmd_list,
    cmd_scan,
    STAGING_DIR,
)


@pytest.fixture(autouse=True)
def _isolate_gepa(tmp_path, monkeypatch):
    """Redirect GEPA_ROOT to tmp_path for all tests."""
    import lib.skill_graph.gepa_batch as mod
    monkeypatch.setattr(mod, "GEPA_ROOT", tmp_path / "gepa")
    monkeypatch.setattr(mod, "STAGING_DIR", tmp_path / "gepa" / "staging")
    monkeypatch.setattr(mod, "LAST_RUN_FILE", tmp_path / "gepa" / "last_run.json")


def test_last_run_roundtrip(tmp_path):
    """save/load last_run timestamp."""
    assert _load_last_run() is None
    _save_last_run("2026-04-07T12:00:00Z")
    assert _load_last_run() == "2026-04-07T12:00:00Z"


def test_fetch_eval_findings_filters_by_type():
    """Only eval-finding lessons returned."""
    mock_client = MagicMock()
    mock_client.query.return_value = [
        {"lesson_type": "eval-finding", "date": "2026-04-07"},
        {"lesson_type": "bug", "date": "2026-04-07"},
        {"lesson_type": "eval-finding", "date": "2026-04-06"},
    ]
    results = _fetch_eval_findings(mock_client)
    assert len(results) == 2
    assert all(r["lesson_type"] == "eval-finding" for r in results)


def test_fetch_eval_findings_filters_by_date():
    """Since filter excludes older entries."""
    mock_client = MagicMock()
    mock_client.query.return_value = [
        {"lesson_type": "eval-finding", "date": "2026-04-07"},
        {"lesson_type": "eval-finding", "date": "2026-04-05"},
    ]
    results = _fetch_eval_findings(mock_client, since="2026-04-06")
    assert len(results) == 1
    assert results[0]["date"] == "2026-04-07"


@patch("lib.skill_graph.gepa_batch._llm_judge")
@patch("lib.skill_graph.gepa_batch.SkillGraphClient")
def test_cmd_scan_writes_staging(mock_client_cls, mock_judge, tmp_path, capsys):
    """scan writes staging file with suggestions."""
    mock_client = MagicMock()
    mock_client.query.return_value = [
        {"lesson_type": "eval-finding", "date": "2026-04-07", "trigger": "test"},
    ]
    mock_client_cls.return_value = mock_client
    mock_judge.return_value = [
        {"pattern_type": "eval-derived", "title": "Test Pattern", "confidence": 0.8,
         "body": "Do X", "applies_to": ["session-start"], "tags": ["test"]},
    ]

    import lib.skill_graph.gepa_batch as mod
    staging_dir = mod.STAGING_DIR

    args = MagicMock()
    cmd_scan(args)

    files = list(staging_dir.glob("gepa-*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["findings_count"] == 1
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["title"] == "Test Pattern"


@patch("lib.skill_graph.gepa_batch.SkillGraphClient")
def test_cmd_approve_writes_patterns(mock_client_cls, tmp_path):
    """approve writes selected patterns to graph."""
    import lib.skill_graph.gepa_batch as mod
    staging_dir = mod.STAGING_DIR
    staging_dir.mkdir(parents=True)

    staging = {
        "created": "2026-04-07T12:00:00Z",
        "findings_count": 1,
        "suggestions": [
            {"title": "Pattern A", "body": "Do A", "confidence": 0.9,
             "applies_to": ["session-start"], "tags": ["eval"]},
            {"title": "Pattern B", "body": "Do B", "confidence": 0.6,
             "applies_to": ["handoff"], "tags": ["test"]},
        ],
        "approved": [],
    }
    staging_file = staging_dir / "gepa-test.json"
    staging_file.write_text(json.dumps(staging))

    mock_client = MagicMock()
    mock_client.writable = True
    mock_client.add_pattern.return_value = "pattern-eval-derived-abc"
    mock_client_cls.return_value = mock_client

    args = MagicMock()
    args.file = "gepa-test.json"
    args.indices = "0"
    cmd_approve(args)

    # Only index 0 was approved
    mock_client.add_pattern.assert_called_once()
    kw = mock_client.add_pattern.call_args[1]
    assert kw["title"] == "Pattern A"
    assert kw["pattern_type"] == "eval-derived"

    # Staging file updated with approved list
    updated = json.loads(staging_file.read_text())
    assert len(updated["approved"]) == 1


@patch("lib.skill_graph.gepa_batch.SkillGraphClient")
def test_cmd_approve_rejects_without_rw_token(mock_client_cls, tmp_path):
    """approve exits if graph not writable."""
    import lib.skill_graph.gepa_batch as mod
    staging_dir = mod.STAGING_DIR
    staging_dir.mkdir(parents=True)

    staging_file = staging_dir / "gepa-test.json"
    staging_file.write_text(json.dumps({"suggestions": [{"title": "X"}], "approved": []}))

    mock_client = MagicMock()
    mock_client.writable = False
    mock_client_cls.return_value = mock_client

    args = MagicMock()
    args.file = "gepa-test.json"
    args.indices = None

    with pytest.raises(SystemExit):
        cmd_approve(args)

    mock_client.add_pattern.assert_not_called()
