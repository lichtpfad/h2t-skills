"""Unit tests for docs-lint check functions."""
import sys
from pathlib import Path

# Make lint.py importable
_LINT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"
sys.path.insert(0, str(_LINT_DIR))
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from lint import check_legacy_dirs


def test_check_legacy_dirs_clean(tmp_path):
    """No legacy dirs → no failures."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    assert check_legacy_dirs(tmp_path) == []


def test_check_legacy_dirs_plans(tmp_path):
    """docs/plans/ present → failure."""
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/plans" in f for f in result)


def test_check_legacy_dirs_specs(tmp_path):
    """docs/specs/ present → failure."""
    (tmp_path / "docs" / "specs").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/specs" in f for f in result)


def test_check_legacy_dirs_handoff(tmp_path):
    """docs/handoff/ present → failure."""
    (tmp_path / "docs" / "handoff").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("handoff" in f for f in result)


def test_check_legacy_dirs_eval(tmp_path):
    """docs/eval/ present → failure."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("eval" in f for f in result)


def test_check_legacy_dirs_skips_whitelisted(tmp_path):
    """Dir in extra_dirs whitelist is not flagged."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path, extra_dirs=["eval"])
    assert result == []


def test_check_legacy_dirs_handoffs_plural(tmp_path):
    """docs/handoffs/ (plural) present → failure."""
    (tmp_path / "docs" / "handoffs").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("handoffs" in f for f in result)


from lint import check_naming_conventions


def test_naming_clean(tmp_path):
    """Dated specs and plans → no failures."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "2026-05-27-my-feature-design.md").write_text("# x")
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-05-27-my-feature-plan.md").write_text("# x")
    assert check_naming_conventions(tmp_path) == []


def test_naming_spec_missing_date(tmp_path):
    """Spec without date prefix → failure."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "my-feature-design.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-design.md" in f for f in result)


def test_naming_plan_missing_date(tmp_path):
    """Plan without date prefix → failure."""
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "my-feature-plan.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-plan.md" in f for f in result)


def test_naming_readme_ignored(tmp_path):
    """README.md in specs dir → not flagged."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# index")
    assert check_naming_conventions(tmp_path) == []


from lint import check_repo_root


def test_repo_root_clean(tmp_path):
    """Minimal clean root → no failures."""
    for name in ["README.md", "pyproject.toml", ".gitignore", "CLAUDE.md"]:
        (tmp_path / name).write_text("")
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    assert check_repo_root(tmp_path) == []


def test_repo_root_temp_dir(tmp_path):
    """temp/ in root → failure."""
    (tmp_path / "temp").mkdir()
    result = check_repo_root(tmp_path)
    assert any("temp" in f for f in result)


def test_repo_root_old_dir(tmp_path):
    """old/ in root → failure."""
    (tmp_path / "old").mkdir()
    result = check_repo_root(tmp_path)
    assert any("old" in f for f in result)


def test_repo_root_backup_dir(tmp_path):
    """backup/ in root → failure."""
    (tmp_path / "backup").mkdir()
    result = check_repo_root(tmp_path)
    assert any("backup" in f for f in result)


def test_repo_root_too_many_items(tmp_path):
    """More than 12 items in root → failure."""
    for i in range(13):
        (tmp_path / f"item_{i}.txt").write_text("")
    result = check_repo_root(tmp_path)
    assert any("root has" in f for f in result)
