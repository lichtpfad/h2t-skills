from lib.eval.skill_class import eval_set_for, skill_class


def test_gather_skills_map_to_gather_eval_set():
    for s in ("session-start", "handoff", "init-project"):
        assert skill_class(s) == "gather"
        assert eval_set_for(s) == "skills-gather-baseline-v1"


def test_integration_skills_map_to_integration_eval_set():
    for s in ("connectors", "research", "drive", "meetgeek", "telegram", "drawio"):
        assert skill_class(s) == "integration"
        assert eval_set_for(s) == "skills-integration-baseline-v1"


def test_unknown_skill_defaults_to_prompt():
    assert skill_class("mystery-skill") == "prompt"
    assert eval_set_for("mystery-skill") == "skills-prompt-baseline-v1"
