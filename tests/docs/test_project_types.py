# tests/docs/test_project_types.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.project_types import (
    PROJECT_TYPES,
    SCAFFOLD_TYPE_TO_TEMPLATE,
    detect_template,
)
from docs.common import REQUIRED_CORE_DIRS


def test_all_templates_have_required_keys():
    for name, spec in PROJECT_TYPES.items():
        assert "root_dirs" in spec, f"{name} missing root_dirs"
        assert "docs_dirs" in spec, f"{name} missing docs_dirs"
        assert "root_files_required" in spec, f"{name} missing root_files_required"
        assert isinstance(spec["root_dirs"], list), f"{name}.root_dirs must be list"
        assert isinstance(spec["docs_dirs"], list), f"{name}.docs_dirs must be list"


def test_scaffold_type_to_template_covers_all_scaffold_types():
    expected = {"code-github", "code-local", "docs", "dcc", "directory"}
    assert set(SCAFFOLD_TYPE_TO_TEMPLATE.keys()) == expected


def test_scaffold_type_to_template_maps_to_known_templates():
    for t, tmpl in SCAFFOLD_TYPE_TO_TEMPLATE.items():
        assert tmpl in PROJECT_TYPES, f"{t} maps to unknown template {tmpl}"


def test_detect_template_reads_docs_lint_yaml(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: creative_project\n"
    )
    assert detect_template(tmp_path) == "creative_project"


def test_detect_template_ignores_unknown_template_in_yaml(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "template: nonexistent_type\n"
    )
    result = detect_template(tmp_path)
    assert result == "code_repo"  # unknown template → fall through to default


def test_detect_template_fallback_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert detect_template(tmp_path) == "code_repo"


def test_detect_template_fallback_deliverables(tmp_path):
    (tmp_path / "deliverables").mkdir()
    assert detect_template(tmp_path) == "client_project"


def test_detect_template_default(tmp_path):
    assert detect_template(tmp_path) == "code_repo"


def test_no_docs_dir_duplicates_required_core():
    """docs_dirs must not repeat REQUIRED_CORE_DIRS entries."""
    required = set(REQUIRED_CORE_DIRS)
    for name, spec in PROJECT_TYPES.items():
        for d in spec["docs_dirs"]:
            assert d not in required, (
                f"{name}.docs_dirs contains {d} which is already in REQUIRED_CORE_DIRS"
            )
