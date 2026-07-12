import json
from unittest.mock import MagicMock

import pytest

from lib.eval import session as sess
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

    def _boom(self, status, metrics):
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


def test_metric_records_level_and_unit_in_local(tmp_path, monkeypatch):
    """metric(level=..., unit=...) is preserved in the local JSON entry."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.research_cost_usd", value_num=0.42, level="business", unit="usd")
    files = list((evals_root / "research" / "sessions").glob("*.json"))
    entry = next(m for m in json.loads(files[0].read_text())["metrics"]
                 if m["key"] == "skills.research_cost_usd")
    assert entry["level"] == "business"
    assert entry["unit"] == "usd"
    assert entry["value_num"] == 0.42


def test_metric_level_defaults_to_none_when_omitted(tmp_path, monkeypatch):
    """Omitting level leaves it absent (no forced 'unit') in the stored entry."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    entry = next(m for m in json.loads(files[0].read_text())["metrics"]
                 if m["key"] == "skills.token_consumption")
    assert "level" not in entry


def test_metric_level_unit_propagate_to_central(tmp_path, monkeypatch):
    """level/unit reach the central SDK path (not just local). business != unit."""
    import sys
    import types
    captured = []

    class FakeSession:
        def __init__(self, **kw):
            pass

        def start(self):
            pass

        def metric(self, key, **kw):
            captured.append((key, kw))

        def finish(self, **kw):
            pass

    class FakeClient:
        def __init__(self, **kw):
            pass

        def flush(self, **kw):
            pass

    fake = types.ModuleType("h2t_evals.sdk")
    fake.EvalClient = FakeClient
    fake.EvalSession = FakeSession
    monkeypatch.setitem(sys.modules, "h2t_evals", types.ModuleType("h2t_evals"))
    monkeypatch.setitem(sys.modules, "h2t_evals.sdk", fake)
    monkeypatch.setenv("H2T_EVALS_MODE", "push")
    with SkillEval("research", domain="d", project="p",
                   evals_root=str(tmp_path / "evals")) as ev:
        ev.metric("skills.research_cost_usd", value_num=0.4, level="business", unit="usd")
    biz = [kw for key, kw in captured if key == "skills.research_cost_usd"]
    assert biz and biz[0]["level"] == "business" and biz[0]["unit"] == "usd"


CORE_KEYS = {
    "core.task_success", "core.op_type_correct_rate", "core.deflection_rate",
    "core.time_to_first_valid_ms", "core.tool_call_success_rate",
}


def _local_metrics(evals_root, skill):
    files = list((evals_root / skill / "sessions").glob("*.json"))
    return {m["key"]: m for m in json.loads(files[0].read_text())["metrics"]}


def test_local_write_contains_all_five_core(tmp_path, monkeypatch):
    """_write_local carries all 5 core.* (not only caller metrics)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.token_consumption", value_num=1.0)
    m = _local_metrics(evals_root, "session-start")
    assert CORE_KEYS <= set(m)


def test_core_task_success_reflects_status(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
            raise ValueError("boom")
    m = _local_metrics(evals_root, "handoff")
    assert m["core.task_success"]["value_bool"] is False
    assert m["core.tool_call_success_rate"]["value_num"] == 0.0


def test_op_type_correct_rate_from_record_op_type(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.record_op_type(False)  # schema-invalid output
    m = _local_metrics(evals_root, "research")
    assert m["core.op_type_correct_rate"]["value_num"] == 0.0


def test_deflection_rate_from_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.record_fallback()  # degraded path taken
    m = _local_metrics(evals_root, "research")
    assert m["core.deflection_rate"]["value_num"] == 0.0
    assert m["skills.fallback_used"]["value_bool"] is True


def test_caller_core_override_wins_no_duplicate(tmp_path, monkeypatch):
    """A caller-emitted core.* overrides the proxy; exactly one entry survives."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("research", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("core.op_type_correct_rate", value_num=0.5, level="unit")
    files = list((evals_root / "research" / "sessions").glob("*.json"))
    entries = [m for m in json.loads(files[0].read_text())["metrics"]
               if m["key"] == "core.op_type_correct_rate"]
    assert len(entries) == 1
    assert entries[0]["value_num"] == 0.5


def test_time_to_first_valid_is_nonneg_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
        pass
    m = _local_metrics(evals_root, "session-start")
    assert m["core.time_to_first_valid_ms"]["value_num"] >= 0.0


def test_auto_custom_duration_always_emitted(tmp_path, monkeypatch):
    """skills.duration_ms is auto-emitted for every session (emit-ahead)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
        pass
    m = _local_metrics(evals_root, "session-start")
    assert m["skills.duration_ms"]["value_num"] >= 0.0
    assert m["skills.duration_ms"]["unit"] == "ms"


def test_auto_custom_error_class_on_failure(tmp_path, monkeypatch):
    """skills.error_class carries the exception class name on failure; absent on success."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
            raise ValueError("boom")
    m = _local_metrics(evals_root, "handoff")
    assert m["skills.error_class"]["value_text"] == "ValueError"
    with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
        pass
    ok = list((evals_root / "handoff" / "sessions").glob("*.json"))
    latest = max(ok, key=lambda p: p.stat().st_mtime)
    assert "skills.error_class" not in {mm["key"] for mm in json.loads(latest.read_text())["metrics"]}


def test_eval_set_resolved_per_class():
    from lib.eval.skill_class import eval_set_for
    ev = SkillEval("research", domain="d", project="p")
    assert ev._eval_set == eval_set_for("research") == "skills-integration-baseline-v1"
    ev2 = SkillEval("handoff", domain="d", project="p")
    assert ev2._eval_set == "skills-gather-baseline-v1"


def test_write_local_no_collision_without_glob(tmp_path, monkeypatch):
    """Many same-skill/same-day sessions produce distinct files (no seq-glob)."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    for _ in range(5):
        with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)):
            pass
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    assert len(files) == 5  # all distinct, none overwritten


def test_write_local_filename_has_no_seq_suffix(tmp_path, monkeypatch):
    """Filename no longer uses the 3-digit seq scheme (…-NNN.json)."""
    import re
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    with SkillEval("handoff", domain="d", project="p", evals_root=str(evals_root)):
        pass
    name = list((evals_root / "handoff" / "sessions").glob("*.json"))[0].name
    assert not re.search(r"-\d{3}\.json$", name)


def test_record_eval_module_removed():
    """The vestigial gather.eval module and its exports are gone."""
    import importlib
    import lib.gather as g
    assert not hasattr(g, "record_eval")
    assert not hasattr(g, "estimate_tokens")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("lib.gather.eval")
