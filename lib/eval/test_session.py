import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lib.eval.session import SkillEval


def test_skill_eval_local_write_on_success(tmp_path):
    """SkillEval writes local JSON file with success status."""
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="h2t-ai", evals_root=str(evals_root)):
        pass  # success (no exception)

    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["skill"] == "session-start"
    assert record["status"] == "success"
    assert "started_at" in record
    assert "ended_at" in record


def test_skill_eval_local_write_on_failure(tmp_path):
    """SkillEval writes failure status when exception raised."""
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="dev", project="p", evals_root=str(evals_root)):
            raise ValueError("simulated failure")

    files = list((evals_root / "handoff" / "sessions").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["status"] == "failure"


def test_skill_eval_metrics_recorded(tmp_path):
    """Metrics passed via .metric() appear in local JSON."""
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.gather_source_success_rate", value_num=0.85)
        ev.metric("skills.token_consumption", value_num=512.0)

    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    record = json.loads(files[0].read_text())
    keys = [m["key"] for m in record["metrics"]]
    assert "skills.gather_source_success_rate" in keys
    assert "skills.token_consumption" in keys


def test_skill_eval_does_not_suppress_exceptions(tmp_path):
    """__exit__ returns False — exceptions propagate."""
    evals_root = tmp_path / "evals"
    with pytest.raises(RuntimeError, match="boom"):
        with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)):
            raise RuntimeError("boom")
