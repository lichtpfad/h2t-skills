import json
from pathlib import Path

from lib.eval.session import SkillEval


def test_gather_emits_sources_failed_count(tmp_path, monkeypatch):
    """The gather call-site pattern emits skills.sources_failed_count."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    evals_root = tmp_path / "evals"
    sources_failed = ["github"]
    with SkillEval("session-start", domain="d", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.sources_failed_count", value_num=float(len(sources_failed)), level="unit")
    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    m = {x["key"]: x for x in json.loads(Path(files[0]).read_text())["metrics"]}
    assert m["skills.sources_failed_count"]["value_num"] == 1.0
