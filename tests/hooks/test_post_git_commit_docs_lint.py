import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_HOOK_DIR = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers"
sys.path.insert(0, str(_HOOK_DIR))

import post_git_commit_docs_lint as hook


def test_is_git_commit_payload_accepts_bash_git_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_accepts_git_c_repo_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git -C C:/work/rejuve commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_accepts_git_config_commit():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git -c user.name=test commit -m test"}}
    assert hook.is_git_commit_payload(payload) is True


def test_is_git_commit_payload_rejects_other_commands():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
    assert hook.is_git_commit_payload(payload) is False


def test_is_git_commit_payload_rejects_echo_false_positive():
    payload = {"tool_name": "Bash", "tool_input": {"command": 'echo "git commit -m test"'}}
    assert hook.is_git_commit_payload(payload) is False


def test_changed_docs_from_head_filters_docs_markdown(tmp_path):
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="docs/a.md\nsrc/app.py\ndocs/data.json\nREADME.md\n",
            stderr="",
        )
        changed = hook.changed_docs_from_head(tmp_path)

    assert changed == ["docs/a.md"]
    cmd = mock_run.call_args[0][0]
    assert cmd[:4] == ["git", "-C", str(tmp_path), "diff-tree"]


def test_changed_docs_returns_empty_on_git_error(tmp_path):
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad revision")
        assert hook.changed_docs_from_head(tmp_path) == []


def test_find_docs_lint_script_prefers_env(tmp_path, monkeypatch):
    script = tmp_path / "lint.py"
    script.write_text("# lint", encoding="utf-8")
    monkeypatch.setenv("H2T_DOCS_LINT_SCRIPT", str(script))
    assert hook.find_docs_lint_script() == script


def test_build_report_records_skipped_state(tmp_path):
    report = hook.build_hook_report(
        repo_root=tmp_path,
        status="skipped",
        changed_docs=[],
        docs_lint=None,
        message="no docs changed",
    )
    assert report["schema"] == "h2t_lifecycle_report/v0.1"
    assert report["command"] == "post-git-commit-docs-lint"
    assert report["status"] == "skipped"
    assert report["evidence"]["hook"] == "PostToolUse:git-commit:docs-lint"


def test_write_report_uses_h2t_lifecycle_dir(tmp_path):
    report = hook.build_hook_report(
        repo_root=tmp_path,
        status="ok",
        changed_docs=["docs/a.md"],
        docs_lint={"status": "ok"},
        message="done",
    )
    path = hook.write_report(tmp_path, report)
    assert path == tmp_path / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "ok"


def test_run_docs_lint_doctor_uses_timeout(tmp_path):
    lint = tmp_path / "lint.py"
    lint.write_text("# lint", encoding="utf-8")
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"status":"ok"}', stderr="")
        result = hook.run_docs_lint_doctor(tmp_path, lint, timeout=3)
    assert result["status"] == "ok"
    assert mock_run.call_args.kwargs["timeout"] == 3


def test_hook_timeout_seconds_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("H2T_LINT_HOOK_TIMEOUT", "bad")
    assert hook.hook_timeout_seconds() == 8


def test_main_writes_error_report_when_lint_script_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "changed_docs_from_head", lambda _: ["docs/a.md"])
    monkeypatch.setattr(hook, "find_docs_lint_script", lambda: None)
    monkeypatch.chdir(tmp_path)
    hook.main()
    report_path = tmp_path / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert "not found" in data["summary"]


def test_run_docs_lint_doctor_error_on_nonzero_exit(tmp_path):
    lint = tmp_path / "lint.py"
    lint.write_text("# lint", encoding="utf-8")
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="some output", stderr="some error")
        result = hook.run_docs_lint_doctor(tmp_path, lint, timeout=3)
    assert result["status"] == "error"
    assert result["exit_code"] == 1


def test_run_docs_lint_doctor_timeout(tmp_path):
    import subprocess as _subprocess
    lint = tmp_path / "lint.py"
    lint.write_text("# lint", encoding="utf-8")
    with patch.object(hook.subprocess, "run") as mock_run:
        exc = _subprocess.TimeoutExpired(cmd=["python"], timeout=3)
        exc.stdout = "partial output"
        exc.stderr = ""
        mock_run.side_effect = exc
        result = hook.run_docs_lint_doctor(tmp_path, lint, timeout=3)
    assert result["status"] == "error"
    assert result["message"] == "hook timeout"


def test_wrapper_exists_and_references_backend():
    wrapper = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers/post-git-commit-docs-lint"
    text = wrapper.read_text(encoding="utf-8")
    assert "post_git_commit_docs_lint" in text
    assert "raise SystemExit" in text
