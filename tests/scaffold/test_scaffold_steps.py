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
    # run_docs_init reads the module-level _H2T_DEV_ROOT (resolved once at import),
    # not _DEV_ROOT/_PLUGIN_ROOT — point it at a dir with no docs-init script.
    monkeypatch.setattr(scaffold_project, "_H2T_DEV_ROOT", tmp_path / "nonexistent")
    project_dir = tmp_path / "my-repo"
    project_dir.mkdir()
    result = run_docs_init("my-repo", project_dir)
    assert result["status"] == "skip"


def test_gitignore_python_includes_lint_temp_files():
    """scaffold .gitignore must exclude docs-lint temp files from day 0."""
    from scaffold_project import GITIGNORE_TEMPLATES
    gi = GITIGNORE_TEMPLATES["python"]
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi


def test_gitignore_none_includes_lint_temp_files():
    from scaffold_project import GITIGNORE_TEMPLATES
    gi = GITIGNORE_TEMPLATES["none"]
    assert ".h2t/lint-before.json" in gi
    assert ".h2t/lint-after.json" in gi


def test_gitignore_dcc_includes_lint_temp_files():
    from scaffold_project import DCC_GITIGNORE
    assert ".h2t/lint-before.json" in DCC_GITIGNORE
    assert ".h2t/lint-after.json" in DCC_GITIGNORE


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


def _hook_commands(entries):
    return [
        command["command"]
        for entry in entries
        for command in entry.get("hooks", [])
        if command.get("type") == "command"
    ]


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
    stop_commands = _hook_commands(stop_hooks)
    assert any("on-stop" in cmd for cmd in stop_commands)


def test_install_hooks_stop_hook_points_to_latest(tmp_path):
    """Stop hook path starts with ~ (portable) and references latest/ junction."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    stop_commands = _hook_commands(stop_hooks)
    cmd = stop_commands[0]
    assert cmd.startswith("~")
    assert "latest" in cmd


def test_install_hooks_idempotent(tmp_path):
    """Calling twice does not duplicate hooks."""
    install_hooks(tmp_path)
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = data.get("hooks", {}).get("Stop", [])
    on_stop_cmds = [cmd for cmd in _hook_commands(stop_hooks) if "on-stop" in cmd]
    assert len(on_stop_cmds) == 1


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


def test_install_hooks_has_posttooluse_git_commit_hook(tmp_path):
    """PostToolUse hook runs docs-lint after git commit."""
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    commands = _hook_commands(hooks)
    assert any("post-git-commit-docs-lint" in command for command in commands)


def test_install_hooks_posttooluse_matcher_targets_bash_git_commit(tmp_path):
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    matching = [
        entry for entry in hooks
        if any("post-git-commit-docs-lint" in command for command in _hook_commands([entry]))
    ]
    assert matching
    assert "Bash" in matching[0].get("matcher", "")
    assert "git commit" in matching[0].get("matcher", "")


def test_install_hooks_posttooluse_idempotent(tmp_path):
    install_hooks(tmp_path)
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {}).get("PostToolUse", [])
    matching = [
        entry for entry in hooks
        if any("post-git-commit-docs-lint" in command for command in _hook_commands([entry]))
    ]
    assert len(matching) == 1


def test_install_hooks_ignores_lifecycle_report_cache(tmp_path):
    git_info = tmp_path / ".git" / "info"
    git_info.mkdir(parents=True)
    install_hooks(tmp_path)
    exclude = git_info / "exclude"
    assert ".h2t/lifecycle/*.json" in exclude.read_text(encoding="utf-8")


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


def test_cmd_create_code_repo_root_dirs(tmp_path, monkeypatch):
    """code-github creates src, tests, docs, scripts at root."""
    import scaffold_project
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "skip"}):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                import argparse
                args = argparse.Namespace(
                    id="test-proj", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False, merge=False,
                )
                result = scaffold_project.cmd_create(args)
    assert result["status"] == "ok"
    proj = tmp_path / "test-proj"
    assert (proj / "src").exists()
    assert (proj / "tests").exists()
    assert (proj / "scripts").exists()


def test_cmd_create_dcc_uses_dcc_gitignore(tmp_path, monkeypatch):
    """dcc type uses DCC_GITIGNORE (*.cache, *.bak), not python gitignore."""
    import scaffold_project
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "creative_project": {"root_dirs": ["assets", "scripts", "exports", "docs"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"dcc": "creative_project"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "skip"}):
        import argparse
        args = argparse.Namespace(
            id="my-dcc", type="dcc", stack="none",
            dir=str(tmp_path), description="dcc project", dry_run=False,
        )
        result = scaffold_project.cmd_create(args)
    assert result["status"] == "ok"
    gitignore = (tmp_path / "my-dcc" / ".gitignore").read_text(encoding="utf-8")
    assert "*.cache" in gitignore
    assert "*.pyc" not in gitignore


def test_cmd_create_dry_run_lists_would_create(tmp_path):
    """dry-run returns would_create list without touching disk."""
    import scaffold_project
    import argparse
    args = argparse.Namespace(
        id="dry-proj", type="code-local", stack="python",
        dir=str(tmp_path), description="", dry_run=True,
    )
    result = scaffold_project.cmd_create(args)
    assert result["status"] == "dry-run"
    assert any("dry-proj" in item for item in result["would_create"])
    assert not (tmp_path / "dry-proj").exists()


def test_cmd_create_fails_when_docs_init_ok_but_paths_missing(tmp_path, monkeypatch):
    """scaffold returns error if docs-init reports ok but critical docs paths are absent.

    This catches the silent-skip case where docs-init returns status='ok' but
    didn't actually write any files (e.g. script path mismatch).
    """
    import scaffold_project
    import argparse
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})
    with patch("scaffold_project.run_docs_init", return_value={"status": "ok", "output": ""}):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                args = argparse.Namespace(
                    id="test-proj", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False, merge=False,
                )
                result = scaffold_project.cmd_create(args)

    # docs-init reported ok but docs/README.md was never created
    assert result["status"] == "error"
    assert "docs-init" in result["error"].lower() or "missing" in result["error"].lower()


def test_cmd_create_succeeds_when_docs_init_ok_and_paths_present(tmp_path, monkeypatch):
    """scaffold succeeds when docs-init ok AND critical paths exist."""
    import scaffold_project
    import argparse
    monkeypatch.setattr(scaffold_project, "_PROJECT_TYPES_AVAILABLE", True)
    monkeypatch.setattr(scaffold_project, "PROJECT_TYPES", {
        "code_repo": {"root_dirs": ["src", "tests", "docs", "scripts"], "docs_dirs": [], "root_files_required": []},
    })
    monkeypatch.setattr(scaffold_project, "SCAFFOLD_TYPE_TO_TEMPLATE", {"code-github": "code_repo"})

    def fake_docs_init(repo_name, project_dir, *, template="code_repo"):
        # Simulate real docs-init: create critical paths matching REQUIRED_CORE_DIRS
        (project_dir / "docs" / "README.md").parent.mkdir(parents=True, exist_ok=True)
        (project_dir / "docs" / "README.md").write_text("# docs\n")
        (project_dir / "docs" / "adr").mkdir(exist_ok=True)
        (project_dir / "docs" / "reports").mkdir(exist_ok=True)
        (project_dir / "docs" / "superpowers" / "specs").mkdir(parents=True, exist_ok=True)
        (project_dir / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
        return {"status": "ok", "output": ""}

    with patch("scaffold_project.run_docs_init", side_effect=fake_docs_init):
        with patch("scaffold_project.install_hooks", return_value={"status": "ok"}):
            with patch("scaffold_project.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                args = argparse.Namespace(
                    id="test-proj2", type="code-github", stack="python",
                    dir=str(tmp_path), description="test", dry_run=False, merge=False,
                )
                result = scaffold_project.cmd_create(args)

    assert result["status"] == "ok"
