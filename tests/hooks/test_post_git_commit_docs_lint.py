import io
import json
import sys
from unittest.mock import MagicMock, patch

from h2t_ops.hooks import post_git_commit_docs_lint as hook


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


def test_docs_lint_command_prefers_env(tmp_path, monkeypatch):
    script = tmp_path / "lint.py"
    script.write_text("# lint", encoding="utf-8")
    monkeypatch.setenv("H2T_DOCS_LINT_SCRIPT", str(script))
    assert hook.docs_lint_command() == [sys.executable, str(script)]


def test_docs_lint_command_defaults_to_the_package(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_DOCS_LINT_SCRIPT", str(tmp_path / "absent.py"))
    assert hook.docs_lint_command() == [sys.executable, "-m", "h2t_ops.tools.docs.lint"]


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
        result = hook.run_docs_lint_doctor(tmp_path, [sys.executable, str(lint)], timeout=3)
    assert result["status"] == "ok"
    assert mock_run.call_args.kwargs["timeout"] == 3


def test_hook_timeout_seconds_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("H2T_LINT_HOOK_TIMEOUT", "bad")
    assert hook.hook_timeout_seconds() == 8


def test_main_records_the_doctor_result(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "changed_docs_from_head", lambda _: ["docs/a.md"])
    monkeypatch.setattr(hook, "run_docs_lint_doctor", lambda root, command, timeout: {"status": "warn"})
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.chdir(tmp_path)
    assert hook.main([]) == 0
    report_path = tmp_path / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    assert data["evidence"]["docs_lint"] == {"status": "warn"}


def test_run_docs_lint_doctor_error_on_nonzero_exit(tmp_path):
    lint = tmp_path / "lint.py"
    lint.write_text("# lint", encoding="utf-8")
    with patch.object(hook.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="some output", stderr="some error")
        result = hook.run_docs_lint_doctor(tmp_path, [sys.executable, str(lint)], timeout=3)
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
        result = hook.run_docs_lint_doctor(tmp_path, [sys.executable, str(lint)], timeout=3)
    assert result["status"] == "error"
    assert result["message"] == "hook timeout"


def test_a_refused_report_is_one_stderr_line_and_exit_0(tmp_path, monkeypatch, capsys):
    """The write failure is expected and named (stderr, no traceback, stdout empty);
    the hook stays non-blocking."""
    from h2t_ops.core import repo_writers
    monkeypatch.setattr(hook, "changed_docs_from_head", lambda _: [])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(repo_writers.REPO_WRITERS, "post-git-commit-docs-lint", {})
    assert hook.main([]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "report not written: WriteRefused" in out.err and "Traceback" not in out.err
    assert not (tmp_path / ".h2t").exists()
