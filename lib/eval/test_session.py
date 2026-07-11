import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lib.eval.session import SkillEval


def test_skill_eval_local_write_on_success(tmp_path, monkeypatch):
    """SkillEval writes local JSON file with success status."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
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


def test_skill_eval_local_write_on_failure(tmp_path, monkeypatch):
    """SkillEval writes failure status when exception raised."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="dev", project="p", evals_root=str(evals_root)):
            raise ValueError("simulated failure")

    files = list((evals_root / "handoff" / "sessions").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["status"] == "failure"


def test_skill_eval_metrics_recorded(tmp_path, monkeypatch):
    """Metrics passed via .metric() appear in local JSON."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
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


def test_skill_eval_calls_add_lesson_on_exception():
    """SkillEval calls skill_graph.add_lesson() on exception."""
    mock_graph = MagicMock()
    mock_graph.add_lesson.return_value = "lesson-1"

    with pytest.raises(RuntimeError):
        with SkillEval("session-start", domain="dev", project="test",
                       skill_graph=mock_graph):
            raise RuntimeError("deliberate failure")

    mock_graph.add_lesson.assert_called_once()
    call_kwargs = mock_graph.add_lesson.call_args[1]
    assert call_kwargs["skill_name"] == "session-start"
    assert "deliberate failure" in call_kwargs["trigger"]
    assert call_kwargs["lesson_type"] == "eval-finding"
    assert call_kwargs["resolution"] == ""


def test_skill_eval_does_not_call_add_lesson_on_success():
    """SkillEval does not call add_lesson on successful execution."""
    mock_graph = MagicMock()

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph) as ev:
        ev.metric("test.metric", value_num=1.0)

    mock_graph.add_lesson.assert_not_called()


def test_skill_eval_works_without_skill_graph():
    """SkillEval works without skill_graph parameter (backward compatibility)."""
    with SkillEval("session-start", domain="dev", project="test") as ev:
        ev.metric("test.metric", value_num=1.0)
    # passes with no exception


def test_close_writes_lesson_on_significant_delta():
    """close() calls add_lesson when score delta > 0.1."""
    mock_graph = MagicMock()
    mock_graph.writable = True
    mock_graph.add_lesson.return_value = "lesson-123"

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph, score_before=0.5) as ev:
        node_id = ev.close(0.8)

    assert node_id == "lesson-123"
    mock_graph.add_lesson.assert_called_once()
    kw = mock_graph.add_lesson.call_args[1]
    assert kw["lesson_type"] == "eval-finding"
    assert kw["eval_score_before"] == 0.5
    assert kw["eval_score_after"] == 0.8
    assert kw["skill_name"] == "session-start"


def test_close_skips_when_delta_too_small():
    """close() does not write lesson when delta <= 0.1."""
    mock_graph = MagicMock()
    mock_graph.writable = True

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph, score_before=0.5) as ev:
        node_id = ev.close(0.55)

    assert node_id is None
    mock_graph.add_lesson.assert_not_called()


def test_close_skips_when_no_score_before():
    """close() does nothing if score_before was not provided."""
    mock_graph = MagicMock()
    mock_graph.writable = True

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph) as ev:
        node_id = ev.close(0.8)

    assert node_id is None
    mock_graph.add_lesson.assert_not_called()


def test_close_skips_when_graph_not_writable():
    """close() skips write if graph has no RW token."""
    mock_graph = MagicMock()
    mock_graph.writable = False

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph, score_before=0.3) as ev:
        node_id = ev.close(0.9)

    assert node_id is None
    mock_graph.add_lesson.assert_not_called()


def test_close_handles_graph_exception_gracefully():
    """close() returns None if add_lesson raises."""
    mock_graph = MagicMock()
    mock_graph.writable = True
    mock_graph.add_lesson.side_effect = ConnectionError("network down")

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph, score_before=0.2) as ev:
        node_id = ev.close(0.9)

    assert node_id is None


from lib.eval import session as sess


def test_resolve_mode_explicit_wins(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({"H2T_EVALS_MODE": "off"}) == "off"
    assert sess.resolve_mode({"H2T_EVALS_MODE": "local"}) == "local"
    assert sess.resolve_mode({"H2T_EVALS_MODE": "push"}) == "push"


def test_resolve_mode_auto_push_when_sdk_and_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({"H2T_EVALS_TOKEN": "t"}) == "push"


def test_resolve_mode_auto_off_without_sdk(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_TOKEN": "t"}) == "off"


def test_resolve_mode_auto_off_without_token(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: True)
    assert sess.resolve_mode({}) == "off"


def test_resolve_mode_legacy_enabled_maps_push(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_ENABLED": "1"}) == "push"


def test_resolve_mode_invalid_behaves_as_auto(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    assert sess.resolve_mode({"H2T_EVALS_MODE": "garbage"}) == "off"


def test_off_mode_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    for var in ("H2T_EVALS_MODE", "H2T_EVALS_TOKEN", "H2T_EVALS_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    evals_root = tmp_path / "evals"
    with sess.SkillEval("session-start", domain="d", project="p",
                        evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    assert not evals_root.exists()


def test_push_with_absent_sdk_degrades_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "push")

    def _boom(self, status):
        raise ImportError("no sdk")

    monkeypatch.setattr(sess.SkillEval, "_send_central", _boom)
    evals_root = tmp_path / "evals"
    with sess.SkillEval("handoff", domain="d", project="p",
                        evals_root=str(evals_root)):
        pass
    files = list((evals_root / "handoff" / "sessions").glob("*.json"))
    assert len(files) == 1


def test_session_imports_only_stdlib():
    import ast
    import sys
    import pathlib
    tree = ast.parse(pathlib.Path(sess.__file__).read_text(encoding="utf-8"))
    roots = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    non_stdlib = roots - set(sys.stdlib_module_names)
    assert non_stdlib == set(), f"non-stdlib top-level imports: {non_stdlib}"
