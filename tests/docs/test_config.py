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


def test_deliverables_dir_default(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["deliverables_dir"] == "deliverables"


def test_deliverables_dir_override_from_yaml(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\ndeliverables_dir: outputs\n"
    )
    cfg = load_config(tmp_path)
    assert cfg["deliverables_dir"] == "outputs"


import datetime


def test_h2t_config_takes_priority_over_claude_rules(tmp_path):
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("project_type: td-tool\n")
    claude_cfg = tmp_path / ".claude" / "rules" / "docs-lint.yaml"
    claude_cfg.parent.mkdir(parents=True)
    claude_cfg.write_text("template: plugin-pack\n")
    from docs.config import load_config
    cfg = load_config(tmp_path)
    assert cfg["template"] == "td-tool"
    assert cfg["_config_source"] == ".h2t/docs-lint.yaml"


def test_project_type_normalizes_to_template(tmp_path):
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("project_type: standalone-tool\n")
    from docs.config import load_config
    cfg = load_config(tmp_path)
    assert cfg["template"] == "standalone-tool"


def test_exception_stale_flag(tmp_path):
    old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(
        f"exceptions:\n  - path: old_dir/\n    reason: test\n    type: archive\n    reviewed: {old_date}\n"
    )
    (tmp_path / "old_dir").mkdir()
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("stale" in w["message"] for w in warnings)


def test_exception_orphan_flag(tmp_path):
    today = datetime.date.today().isoformat()
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text(
        f"exceptions:\n  - path: nonexistent_dir/\n    reason: test\n    type: archive\n    reviewed: {today}\n"
    )
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert any("orphan exception" in w["message"] for w in warnings)


def test_exception_string_format_no_crash(tmp_path):
    """Legacy string exceptions (e.g. 'eval') must not crash get_exception_warnings."""
    h2t_cfg = tmp_path / ".h2t" / "docs-lint.yaml"
    h2t_cfg.parent.mkdir()
    h2t_cfg.write_text("exceptions:\n  - eval\n  - ops\n")
    from docs.config import load_config, get_exception_warnings
    cfg = load_config(tmp_path)
    warnings = get_exception_warnings(cfg["exceptions"], tmp_path)
    assert isinstance(warnings, list)
