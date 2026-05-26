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
