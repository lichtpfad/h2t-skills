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


def test_run_docs_init_passes_repo_root_for_non_dev_project(tmp_path, monkeypatch):
    """run_docs_init supports repos outside DEV_ROOT via --repo-root."""
    import scaffold_project

    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_DEV_ROOT", tmp_path / "dev")
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "work" / "my-repo"
    project_dir.mkdir(parents=True)

    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_docs_init("my-repo", project_dir, template="client_project")

    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert result["status"] == "ok"
    assert "--repo-root" in cmd
    assert str(project_dir) in cmd
    assert "--template" in cmd
    assert "client_project" in cmd


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


from scaffold_project import run_sync_labels


def test_run_sync_labels_passes_apply_flag(tmp_path):
    """--apply is required to actually sync labels; must be present."""
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced", stderr="")
        run_sync_labels("h2t-skills")
    cmd = mock_run.call_args[0][0]
    assert "--apply" in cmd


def test_run_sync_labels_passes_repo_name(tmp_path):
    """repo name is passed as a positional argument."""
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_sync_labels("h2t-skills")
    cmd = mock_run.call_args[0][0]
    assert "h2t-skills" in cmd


def test_run_sync_labels_skip_if_no_repo_name():
    """Returns skip status when repo name is empty."""
    result = run_sync_labels("")
    assert result["status"] == "skip"


def test_run_sync_labels_error_on_failure():
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="gh not found")
        result = run_sync_labels("h2t-skills")
    assert result["status"] == "error"


import json
from scaffold_project import install_hooks


def test_install_hooks_creates_settings(tmp_path):
    """Creates .claude/settings.json with Stop hook."""
    install_hooks(tmp_path)
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()


def test_install_hooks_has_stop_hook(tmp_path):
    """Stop hook entry references on-stop handler."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    assert any("on-stop" in h.get("command", "") for h in stop_hooks)


def test_install_hooks_stop_hook_points_to_latest(tmp_path):
    """Stop hook path starts with ~ (portable) and references latest/ junction."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    cmd = stop_hooks[0]["command"]
    assert cmd.startswith("~")
    assert "latest" in cmd


def test_install_hooks_idempotent(tmp_path):
    """Calling twice does not duplicate hooks."""
    install_hooks(tmp_path)
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    on_stop = [h for h in stop_hooks if "on-stop" in h.get("command", "")]
    assert len(on_stop) == 1


def test_run_docs_init_passes_repo_root_for_docs_type(tmp_path, monkeypatch):
    """docs-type project (not is_git) also gets docs-init via --repo-root."""
    import scaffold_project
    plugin_root = _make_fake_init(tmp_path)
    monkeypatch.setattr(scaffold_project, "_PLUGIN_ROOT", plugin_root)
    project_dir = tmp_path / "my-docs"
    project_dir.mkdir()
    with patch("scaffold_project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_docs_init("my-docs", project_dir, template="research_project")
    assert result["status"] == "ok"
    cmd = [str(x) for x in mock_run.call_args[0][0]]
    assert "--repo-root" in cmd
    assert "--template" in cmd
    assert "research_project" in cmd


from scaffold_project import write_setup_report, template_for_type


def test_template_for_type_maps_client_docs():
    assert template_for_type("docs") == "research_project"
    assert template_for_type("code-github") == "code_repo"


def test_write_setup_report_creates_machine_readable_file(tmp_path):
    report = write_setup_report(
        project_dir=tmp_path,
        project_id="example",
        template="client_project",
        status="ok",
        actions=["created docs"],
    )

    assert report["schema"] == "h2t_project_setup_report/v0.1"
    report_path = tmp_path / ".h2t" / "project-setup-report.json"
    assert report_path.exists()
    assert "client_project" in report_path.read_text(encoding="utf-8")
