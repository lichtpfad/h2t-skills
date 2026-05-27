"""Tests for scaffold-project step helpers."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_SCAFFOLD_DIR = Path(__file__).parents[2] / "plugins/h2t-core/skills/scaffold-project/scripts"
sys.path.insert(0, str(_SCAFFOLD_DIR))

from scaffold_project import run_docs_init


def test_run_docs_init_passes_repo_name_not_path(tmp_path):
    """run_docs_init passes repo name (positional), not --cwd."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", Path("C:/dev/my-repo"))
    cmd = mock_run.call_args[0][0]
    assert "my-repo" in cmd
    assert "--cwd" not in " ".join(str(c) for c in cmd)


def test_run_docs_init_passes_apply_flag(tmp_path):
    """run_docs_init always passes --apply so files are actually created."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", Path("C:/dev/my-repo"))
    cmd = mock_run.call_args[0][0]
    assert "--apply" in cmd


def test_run_docs_init_skips_non_dev_root(tmp_path):
    """Skips gracefully when project is not under DEV_ROOT."""
    result = run_docs_init("my-repo", tmp_path / "elsewhere" / "my-repo")
    assert result["status"] == "skip"


def test_run_docs_init_returns_error_on_failure(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        result = run_docs_init("my-repo", Path("C:/dev/my-repo"))
    assert result["status"] == "error"
