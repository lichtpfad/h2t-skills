"""Tests for scaffold-project step helpers."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_SCAFFOLD_DIR = Path(__file__).parents[2] / "plugins/h2t-core/skills/scaffold-project/scripts"
sys.path.insert(0, str(_SCAFFOLD_DIR))

from scaffold_project import run_docs_init


def _make_fake_init(tmp_path: Path) -> Path:
    """Create a fake docs-init init.py under tmp_path and return plugin_root."""
    # init_script = _PLUGIN_ROOT.parent / "h2t-dev" / "skills" / "docs-init" / "scripts" / "init.py"
    # So we need: tmp_path / "h2t-dev" / "skills" / "docs-init" / "scripts" / "init.py"
    # _PLUGIN_ROOT.parent == tmp_path  →  _PLUGIN_ROOT = tmp_path / "any-child"
    fake_init_dir = tmp_path / "h2t-dev" / "skills" / "docs-init" / "scripts"
    fake_init_dir.mkdir(parents=True)
    (fake_init_dir / "init.py").write_text("# stub")
    plugin_root = tmp_path / "h2t-skills"  # .parent == tmp_path
    plugin_root.mkdir(exist_ok=True)
    return plugin_root


def test_run_docs_init_passes_repo_name_not_path(tmp_path, monkeypatch):
    """run_docs_init passes repo name (positional), not --cwd."""
    import scaffold_project
    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "my-repo"
    project_dir.mkdir()
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", project_dir)
    cmd = mock_run.call_args[0][0]
    assert "my-repo" in cmd
    assert "--cwd" not in " ".join(str(c) for c in cmd)


def test_run_docs_init_passes_apply_flag(tmp_path, monkeypatch):
    """run_docs_init always passes --apply so files are actually created."""
    import scaffold_project
    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "my-repo"
    project_dir.mkdir()
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_docs_init("my-repo", project_dir)
    cmd = mock_run.call_args[0][0]
    assert "--apply" in cmd


def test_run_docs_init_skips_non_dev_root(tmp_path):
    """Skips gracefully when project is not under DEV_ROOT."""
    result = run_docs_init("my-repo", tmp_path / "elsewhere" / "my-repo")
    assert result["status"] == "skip"


def test_run_docs_init_returns_error_on_failure(tmp_path, monkeypatch):
    import scaffold_project
    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "my-repo"
    project_dir.mkdir()
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        result = run_docs_init("my-repo", project_dir)
    assert result["status"] == "error"


def test_run_docs_init_skips_when_script_not_found(tmp_path, monkeypatch):
    """Skips gracefully when docs-init script is not found."""
    import scaffold_project
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", tmp_path / "nonexistent")
    project_dir = tmp_path / "my-repo"
    project_dir.mkdir()
    result = run_docs_init("my-repo", project_dir)
    assert result["status"] == "skip"
