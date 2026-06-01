from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_gh_memory_skill_is_explicitly_deprecated():
    text = (ROOT / "plugins/h2t-dev/skills/gh-memory/SKILL.md").read_text(encoding="utf-8")
    assert "status: deprecated" in text
    assert "compatibility shim" in text.lower()
    assert "h2t-core:session-start" in text
    assert "h2t-core:handoff" in text


def test_gh_memory_no_longer_promotes_persistent_agent_memory():
    text = (ROOT / "plugins/h2t-dev/skills/gh-memory/SKILL.md").read_text(encoding="utf-8")
    forbidden = [
        "This skill should be used when GitHub Issues are needed as persistent agent memory",
        "Purpose: Persistent cross-session memory",
    ]
    for phrase in forbidden:
        assert phrase not in text


def test_h2t_dev_readme_marks_gh_memory_deprecated():
    text = (ROOT / "plugins/h2t-dev/README.md").read_text(encoding="utf-8")
    assert "gh-memory" in text
    assert "deprecated" in text.lower()
    assert "session-start" in text
    assert "handoff" in text
