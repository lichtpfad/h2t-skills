import os
import textwrap
from pathlib import Path
from types import MappingProxyType

from h2t_ops.deploy.executor import execute_deploy_action
from h2t_ops.deploy.models import (
    DeployProfileSpec,
    DeployServiceSpec,
    DeployTargetBinding,
    ScriptStep,
)


def test_execute_deploy_action_returns_successful_json_result(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        import json
        import os
        from pathlib import Path

        payload = json.loads(Path(os.environ["H2T_DEPLOY_INPUT_JSON"]).read_text(encoding="utf-8"))
        print(json.dumps({
            "ok": True,
            "provider": "deploy",
            "result": {
                "service": payload["service"],
                "target": payload["target"],
                "status": "deployed",
                "details": {
                    "profile": payload["profile"],
                    "action": os.environ["H2T_DEPLOY_ACTION"],
                    "dry_run_env": os.environ["H2T_DEPLOY_DRY_RUN"],
                    "config": payload["config"],
                },
            },
        }))
        """,
    )
    profile = _profile(
        inputs=("host", "service"),
        deploy_run="scripts/deploy/bundle/deploy.py",
    )
    services = _service_registry(
        config={"host": "${DEPLOY_HOST}", "service": "h2t-graphs"},
        profile_name=profile.name,
    )

    result = execute_deploy_action(
        "h2t-graphs",
        action="deploy",
        dry_run=True,
        repo_root=repo_root,
        services=services,
        profiles={profile.name: profile},
        environ={"DEPLOY_HOST": "deploy.example"},
    )

    assert result == {
        "ok": True,
        "provider": "deploy",
        "result": {
            "service": "h2t-graphs",
            "target": "prod",
            "status": "deployed",
            "details": {
                "profile": "bundle",
                "action": "deploy",
                "dry_run_env": "true",
                "config": {"host": "deploy.example", "service": "h2t-graphs"},
            },
        },
    }


def test_execute_deploy_action_maps_non_zero_exit_to_error_envelope(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        import sys

        print("ignored stdout")
        print("boom", file=sys.stderr)
        raise SystemExit(7)
        """,
    )
    profile = _profile(deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["provider"] == "deploy"
    assert result["error"]["type"] == "provider"
    assert "exit code 7" in result["error"]["message"]
    assert result["error"]["details"]["stderr"] == "boom"


def test_execute_deploy_action_preserves_non_zero_typed_script_error_envelope(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        import json
        import sys

        print(json.dumps({
            "ok": False,
            "provider": "deploy",
            "error": {
                "type": "config",
                "message": "missing workflow config",
                "hint": "Set workflow in target config.",
                "details": {"field": "workflow"},
            },
        }))
        raise SystemExit(1)
        """,
    )
    profile = _profile(deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "config"
    assert result["error"]["message"] == "missing workflow config"
    assert result["error"]["details"]["script_error_details"] == {"field": "workflow"}


def test_execute_deploy_action_rejects_invalid_json_output(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        print("not-json")
        """,
    )
    profile = _profile(deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "provider"
    assert result["error"]["message"] == "Deploy script returned invalid JSON"


def test_execute_deploy_action_rejects_success_result_missing_required_field(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        import json

        print(json.dumps({
            "ok": True,
            "provider": "deploy",
            "result": {
                "service": "h2t-graphs",
                "status": "dispatched",
            },
        }))
        """,
    )
    profile = _profile(deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "provider"
    assert result["error"]["message"] == "Deploy script result missing required field: target"


def test_execute_deploy_action_preserves_typed_script_error_envelope(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        import json

        print(json.dumps({
            "ok": False,
            "provider": "deploy",
            "error": {
                "type": "config",
                "message": "missing workflow config",
                "hint": "Set workflow in target config.",
                "details": {"field": "workflow"},
            },
        }))
        """,
    )
    profile = _profile(deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "config"
    assert result["error"]["message"] == "missing workflow config"
    assert result["error"]["hint"] == "Set workflow in target config."
    assert result["error"]["details"]["script_error_details"] == {"field": "workflow"}


def test_execute_deploy_action_rejects_missing_required_profile_input(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "deploy.py",
        """
        raise SystemExit("should not run")
        """,
    )
    profile = _profile(inputs=("host", "service"), deploy_run="scripts/deploy/bundle/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "config"
    assert "missing required config values" in result["error"]["message"]
    assert "host" in result["error"]["message"]


def test_execute_deploy_action_honors_empty_injected_registries(tmp_path):
    repo_root = _make_repo_root(tmp_path)

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services={},
        profiles={},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "not_found"
    assert result["error"]["message"] == "Deploy service not found: 'h2t-graphs'"


def test_execute_deploy_action_allows_status_unsupported(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    _write_script(
        repo_root / "scripts" / "deploy" / "bundle" / "status.py",
        """
        import json

        print(json.dumps({
            "ok": True,
            "provider": "deploy",
            "result": {
                "service": "h2t-graphs",
                "target": "prod",
                "status": "unsupported",
                "details": {"reason": "profile has no meaningful health check"},
            },
        }))
        """,
    )
    profile = _profile(status_run="scripts/deploy/bundle/status.py")

    result = execute_deploy_action(
        "h2t-graphs",
        action="status",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "unsupported"
    assert result["result"]["details"]["reason"] == "profile has no meaningful health check"


def test_execute_deploy_action_rejects_script_path_outside_scripts_deploy(tmp_path):
    repo_root = _make_repo_root(tmp_path)
    outside_script = repo_root / "tools" / "deploy.py"
    _write_script(
        outside_script,
        """
        print("should not run")
        """,
    )
    profile = _profile(deploy_run="tools/deploy.py")

    result = execute_deploy_action(
        "h2t-graphs",
        repo_root=repo_root,
        services=_service_registry(config={"service": "h2t-graphs"}, profile_name=profile.name),
        profiles={profile.name: profile},
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "config"
    assert "scripts/deploy" in result["error"]["message"]


def test_execute_deploy_action_runs_real_github_actions_dispatch_dry_run(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    profiles_path, services_path = _write_github_actions_fixture(tmp_path)

    result = execute_deploy_action(
        "h2t-graphs",
        action="deploy",
        dry_run=True,
        repo_root=repo_root,
        service_registry_path=services_path,
        profile_registry_path=profiles_path,
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "dry_run"
    assert result["result"]["details"]["repo"] == "lichtpfad/h2t-graphs"
    assert result["result"]["details"]["workflow"] == "deploy.yml"
    assert result["result"]["details"]["ref"] == "main"
    assert "gh workflow run deploy.yml --repo lichtpfad/h2t-graphs --ref main" in result["result"]["details"]["resolved_command"]


def test_execute_deploy_action_runs_real_github_actions_dispatch_with_stubbed_gh(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    profiles_path, services_path = _write_github_actions_fixture(tmp_path)
    stub_dir = tmp_path / "stub-gh"
    log_path = tmp_path / "gh-workflow-run.log"
    _write_gh_stub(
        stub_dir,
        stdout_file=None,
        log_path=log_path,
    )

    result = execute_deploy_action(
        "h2t-graphs",
        action="deploy",
        dry_run=False,
        repo_root=repo_root,
        service_registry_path=services_path,
        profile_registry_path=profiles_path,
        environ=_env_with_stub_gh(stub_dir, log_path=log_path),
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "dispatched"
    assert "workflow run deploy.yml --repo lichtpfad/h2t-graphs --ref main" in log_path.read_text(encoding="utf-8")


def test_execute_deploy_action_runs_real_github_actions_status_when_no_runs(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    profiles_path, services_path = _write_github_actions_fixture(tmp_path)
    stub_dir = tmp_path / "stub-gh"
    stdout_file = tmp_path / "gh-status.json"
    stdout_file.write_text("[]", encoding="utf-8")
    log_path = tmp_path / "gh-run-list.log"
    _write_gh_stub(
        stub_dir,
        stdout_file=stdout_file,
        log_path=log_path,
    )

    result = execute_deploy_action(
        "h2t-graphs",
        action="status",
        repo_root=repo_root,
        service_registry_path=services_path,
        profile_registry_path=profiles_path,
        environ=_env_with_stub_gh(stub_dir, stdout_file=stdout_file, log_path=log_path),
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "unknown"
    assert result["result"]["details"]["reason"] == "no matching workflow runs found"
    assert result["result"]["details"]["status_scope"] == "latest_matching_workflow_run"
    assert "run list --repo lichtpfad/h2t-graphs --workflow deploy.yml --branch main" in log_path.read_text(encoding="utf-8")


def test_execute_deploy_action_runs_real_github_actions_status_maps_success(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    profiles_path, services_path = _write_github_actions_fixture(tmp_path)
    stub_dir = tmp_path / "stub-gh"
    stdout_file = tmp_path / "gh-status.json"
    stdout_file.write_text(
        '[{"databaseId": 42, "status": "completed", "conclusion": "success", "url": "https://example.test/run/42"}]',
        encoding="utf-8",
    )
    log_path = tmp_path / "gh-run-list.log"
    _write_gh_stub(
        stub_dir,
        stdout_file=stdout_file,
        log_path=log_path,
    )

    result = execute_deploy_action(
        "h2t-graphs",
        action="status",
        repo_root=repo_root,
        service_registry_path=services_path,
        profile_registry_path=profiles_path,
        environ=_env_with_stub_gh(stub_dir, stdout_file=stdout_file, log_path=log_path),
    )

    assert result["ok"] is True
    assert result["result"]["status"] == "healthy"
    assert result["result"]["details"]["reason"] == "latest workflow run completed successfully"
    assert result["result"]["details"]["status_scope"] == "latest_matching_workflow_run"
    assert result["result"]["details"]["run"]["databaseId"] == 42


def _make_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "scripts" / "deploy").mkdir(parents=True)
    return repo_root


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")


def _profile(
    *,
    inputs: tuple[str, ...] = ("service",),
    deploy_run: str = "scripts/deploy/bundle/deploy.py",
    status_run: str = "scripts/deploy/bundle/status.py",
) -> DeployProfileSpec:
    return DeployProfileSpec(
        name="bundle",
        contract_version=1,
        kind="script-bundle",
        inputs=inputs,
        deploy=ScriptStep(run=deploy_run),
        status=ScriptStep(run=status_run),
    )


def _service_registry(
    *,
    config: dict[str, object],
    profile_name: str,
) -> MappingProxyType[str, DeployServiceSpec]:
    binding = DeployTargetBinding(
        name="prod",
        profile=profile_name,
        config=MappingProxyType(dict(config)),
    )
    service = DeployServiceSpec(
        name="h2t-graphs",
        service_type="static-site",
        help="",
        default_target="prod",
        targets=MappingProxyType({"prod": binding}),
    )
    return MappingProxyType({"h2t-graphs": service})


def _write_github_actions_fixture(tmp_path: Path) -> tuple[Path, Path]:
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(
        """
profiles:
  github-actions-dispatch:
    contract_version: 1
    kind: script-bundle
    inputs:
      - repo
      - workflow
      - ref
    deploy:
      run: scripts/deploy/github-actions-dispatch/deploy.py
    status:
      run: scripts/deploy/github-actions-dispatch/status.py
""".strip(),
        encoding="utf-8",
    )
    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        """
services:
  h2t-graphs:
    service_type: static-site
    help: h2t-graphs fixture
    default_target: github-preview
    targets:
      github-preview:
        profile: github-actions-dispatch
        config:
          repo: lichtpfad/h2t-graphs
          workflow: deploy.yml
          ref: main
""".strip(),
        encoding="utf-8",
    )
    return profiles_path, services_path


# The stub stands in for the `gh` binary; a .cmd batch file only runs on Windows.
_GH_STUB_NAME = "gh.cmd" if os.name == "nt" else "gh"


def _write_gh_stub(stub_dir: Path, *, stdout_file: Path | None, log_path: Path) -> None:
    stub_dir.mkdir(parents=True, exist_ok=True)
    stdout_value = str(stdout_file) if stdout_file is not None else ""
    if os.name == "nt":
        script = f"""
@echo off
setlocal
echo %*>>"{log_path}"
if not "{stdout_value}"=="" type "{stdout_value}"
exit /b 0
"""
    else:
        script = f"""
#!/usr/bin/env bash
echo "$@" >> "{log_path}"
if [ -n "{stdout_value}" ]; then cat "{stdout_value}"; fi
exit 0
"""
    stub = stub_dir / _GH_STUB_NAME
    stub.write_text(textwrap.dedent(script).strip() + "\n", encoding="utf-8")
    stub.chmod(0o755)


def _env_with_stub_gh(
    stub_dir: Path,
    *,
    stdout_file: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = str(stub_dir) + os.pathsep + env.get("PATH", "")
    env["H2T_DEPLOY_GH"] = str(stub_dir / _GH_STUB_NAME)
    if stdout_file is not None:
        env["GH_STUB_STDOUT"] = str(stdout_file)
    if log_path is not None:
        env["GH_STUB_LOG"] = str(log_path)
    return env
