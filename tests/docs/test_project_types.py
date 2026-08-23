import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/lib"))

from docs.project_types import PROJECT_TYPES, detect_template  # noqa: F401


def test_detect_from_h2t_docs_lint_yaml_project_type(tmp_path):
    """v2 path: .h2t/docs-lint.yaml with project_type field."""
    h2t = tmp_path / ".h2t"
    h2t.mkdir()
    (h2t / "docs-lint.yaml").write_text("project_type: research_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "research_project"


def test_detect_from_claude_rules_docs_lint_yaml_template(tmp_path):
    """Legacy path: .claude/rules/docs-lint.yaml with template field."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text("template: creative_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "creative_project"


def test_h2t_path_takes_priority_over_claude_rules(tmp_path):
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "docs-lint.yaml").write_text(
        "project_type: research_project\n", encoding="utf-8"
    )
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text("template: creative_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "research_project"


def test_unknown_project_type_falls_through_to_heuristics(tmp_path):
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "docs-lint.yaml").write_text(
        "project_type: totally_unknown_type\n", encoding="utf-8"
    )
    assert detect_template(tmp_path) == "code_repo"  # heuristic default


def test_detect_falls_back_to_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert detect_template(tmp_path) == "code_repo"
