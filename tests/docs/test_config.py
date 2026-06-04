# tests/docs/test_config.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.config import load_config


def test_defaults_when_no_config_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"
    assert "docs/adr" in cfg["required_dirs"]
    assert cfg["exceptions"] == []
    assert cfg["template"] is None


def test_config_overrides_docs_root(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("docs_root: documentation\n")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "documentation"


def test_config_partial_override_keeps_defaults(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("template: client_project\n")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"
    assert cfg["template"] == "client_project"


def test_exceptions_list_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("exceptions:\n  - eval\n  - ops\n")
    cfg = load_config(tmp_path)
    assert "eval" in cfg["exceptions"]
    assert "ops" in cfg["exceptions"]


def test_empty_config_file_returns_defaults(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("")
    cfg = load_config(tmp_path)
    assert cfg["docs_root"] == "docs"


def test_custom_root_dirs_default_empty(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["custom_root_dirs"] == []


def test_project_checks_default_false(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["project_checks"] is False


def test_custom_root_dirs_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text(
        "custom_root_dirs:\n  - nimbalyst-local\n  - client-tools\n"
    )
    cfg = load_config(tmp_path)
    assert "nimbalyst-local" in cfg["custom_root_dirs"]
    assert "client-tools" in cfg["custom_root_dirs"]


def test_project_checks_configurable(tmp_path):
    rules_dir = tmp_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "docs-lint.yaml").write_text("project_checks: true\n")
    cfg = load_config(tmp_path)
    assert cfg["project_checks"] is True
