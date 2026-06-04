"""Unit tests for docs.gitignore_hygiene module."""
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene


def test_no_temp_files_no_findings(tmp_path):
    """No temp files at root → no findings."""
    result = check_gitignore_hygiene(tmp_path)
    assert result == []


def test_temp_file_git_ignored_no_finding(tmp_path):
    """Temp file is effectively ignored by git (via git check-ignore) → no finding."""
    from unittest.mock import patch
    (tmp_path / "scratch.tmp").write_text("")
    # Mock _is_ignored_by_git to return True (file already ignored)
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=True):
        result = check_gitignore_hygiene(tmp_path)
    assert result == []


def test_temp_file_not_git_ignored_produces_finding(tmp_path):
    """Temp file at root, not ignored by git → single finding."""
    (tmp_path / "cryo_items.txt").write_text("")
    # Mock _is_ignored_by_git to return False (not ignored)
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        result = check_gitignore_hygiene(tmp_path)
    assert len(result) == 1
    assert result[0]["type"] == "gitignore_hygiene"
    assert result[0]["severity"] == "info"
    assert "cryo_*.txt" in result[0]["message"]


def test_no_temp_files_no_finding(tmp_path):
    """No temp files at root → no findings regardless of gitignore."""
    result = check_gitignore_hygiene(tmp_path)
    assert result == []


def test_multiple_missing_patterns_one_finding(tmp_path):
    """Multiple unignored temp files → single consolidated finding."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / "session_x.txt").write_text("")
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        result = check_gitignore_hygiene(tmp_path)
    assert len(result) == 1


def test_fix_appends_missing_patterns(tmp_path):
    """fix_gitignore_hygiene appends unignored patterns to .gitignore."""
    (tmp_path / "scratch.tmp").write_text("")
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        changes = fix_gitignore_hygiene(tmp_path)
    assert len(changes) >= 1
    content = (tmp_path / ".gitignore").read_text()
    assert "*.tmp" in content


def test_fix_no_op_when_already_git_ignored(tmp_path):
    """fix_gitignore_hygiene does nothing if git already ignores the file."""
    (tmp_path / "scratch.tmp").write_text("")
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=True):
        changes = fix_gitignore_hygiene(tmp_path)
    assert changes == []


def test_fix_creates_gitignore_if_missing(tmp_path):
    """fix_gitignore_hygiene creates .gitignore if it doesn't exist."""
    (tmp_path / "scratch.tmp").write_text("")
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        fix_gitignore_hygiene(tmp_path)
    assert (tmp_path / ".gitignore").exists()
    content = (tmp_path / ".gitignore").read_text()
    assert "*.tmp" in content


def test_fix_preserves_existing_content(tmp_path):
    """fix_gitignore_hygiene preserves pre-existing .gitignore content."""
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        fix_gitignore_hygiene(tmp_path)
    content = (tmp_path / ".gitignore").read_text()
    assert "*.pyc" in content
    assert "__pycache__/" in content
    assert "*.tmp" in content


def test_fix_write_is_atomic(tmp_path):
    """fix_gitignore_hygiene uses atomic write (temp + os.replace), not in-place."""
    import os
    (tmp_path / "scratch.tmp").write_text("")
    (tmp_path / ".gitignore").write_text("*.py\n")
    original_replace = os.replace
    calls = []
    def tracking_replace(src, dst):
        calls.append((src, dst))
        return original_replace(src, dst)
    from unittest.mock import patch
    with patch("docs.gitignore_hygiene._is_ignored_by_git", return_value=False):
        with patch("os.replace", side_effect=tracking_replace):
            fix_gitignore_hygiene(tmp_path)
    assert calls, "os.replace should have been called (atomic write)"
