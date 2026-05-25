"""Deploy executor for profile-driven script bundles."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from h2t_ops.core.envelope import error_envelope, success_envelope
from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)

from .models import DeployProfileSpec, DeployServiceSpec, ScriptStep
from .profiles import load_profile_registry
from .registry import load_service_registry

_PROVIDER = "deploy"
_VALID_ACTIONS = {"deploy", "status"}
_STATUS_VALUES = {"healthy", "failed", "unknown", "unsupported"}
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SCRIPTS_ROOT = Path("scripts/deploy")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ERROR_TYPES = {
    "usage": UsageError,
    "config": ConfigError,
    "auth": AuthError,
    "not_found": NotFoundError,
    "network": NetworkError,
    "provider": ProviderError,
}


def execute_deploy_action(
    service_name: str,
    *,
    action: str = "deploy",
    target: str | None = None,
    dry_run: bool = False,
    repo_root: Path | None = None,
    services: Mapping[str, DeployServiceSpec] | None = None,
    profiles: Mapping[str, DeployProfileSpec] | None = None,
    service_registry_path: Path | None = None,
    profile_registry_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute one deploy action and return the standard envelope."""
    try:
        result = _execute_deploy_action(
            service_name,
            action=action,
            target=target,
            dry_run=dry_run,
            repo_root=repo_root,
            services=services,
            profiles=profiles,
            service_registry_path=service_registry_path,
            profile_registry_path=profile_registry_path,
            environ=environ,
        )
    except Exception as exc:  # noqa: BLE001 - central envelope normalization
        return error_envelope(_PROVIDER, exc)
    return success_envelope(_PROVIDER, result)


def _execute_deploy_action(
    service_name: str,
    *,
    action: str,
    target: str | None,
    dry_run: bool,
    repo_root: Path | None,
    services: Mapping[str, DeployServiceSpec] | None,
    profiles: Mapping[str, DeployProfileSpec] | None,
    service_registry_path: Path | None,
    profile_registry_path: Path | None,
    environ: Mapping[str, str] | None,
) -> dict[str, Any]:
    if action not in _VALID_ACTIONS:
        raise UsageError(f"Unsupported deploy action: {action!r}")

    effective_environ = dict(os.environ if environ is None else environ)
    effective_repo_root = (repo_root or _REPO_ROOT).resolve()
    profile_registry = (
        profiles if profiles is not None else load_profile_registry(profile_registry_path)
    )
    service_registry = (
        services
        if services is not None
        else load_service_registry(
            service_registry_path,
            profiles=profile_registry,
        )
    )

    service = service_registry.get(service_name)
    if service is None:
        raise NotFoundError(f"Deploy service not found: {service_name!r}")

    target_name = target or service.default_target
    binding = service.targets.get(target_name)
    if binding is None:
        raise NotFoundError(
            f"Deploy target not found for service {service_name!r}: {target_name!r}"
        )

    profile = profile_registry.get(binding.profile)
    if profile is None:
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} references unknown profile "
            f"{binding.profile!r}"
        )

    resolved_config = _expand_env_value(dict(binding.config), environ=effective_environ)
    _validate_required_inputs(service_name, target_name, profile, resolved_config)

    step = _resolve_script_step(profile, action)
    script_path = _resolve_script_path(effective_repo_root, step)
    payload = {
        "service": service.name,
        "service_type": service.service_type,
        "target": target_name,
        "profile": profile.name,
        "action": action,
        "dry_run": dry_run,
        "config": resolved_config,
    }
    return _run_script(
        script_path,
        repo_root=effective_repo_root,
        payload=payload,
        action=action,
        dry_run=dry_run,
        environ=effective_environ,
    )


def _validate_required_inputs(
    service_name: str,
    target_name: str,
    profile: DeployProfileSpec,
    config: Mapping[str, Any],
) -> None:
    missing = [
        key
        for key in profile.inputs
        if key not in config or _is_missing_value(config[key])
    ]
    if missing:
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} missing required config values "
            f"for profile {profile.name!r}: {', '.join(missing)}"
        )


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _expand_env_value(value: Any, *, environ: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _expand_env_value(item, environ=environ) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_value(item, environ=environ) for item in value]
    if isinstance(value, tuple):
        return tuple(_expand_env_value(item, environ=environ) for item in value)
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in environ:
            raise ConfigError(f"Deploy config references missing environment variable: {name}")
        return environ[name]

    return _ENV_PATTERN.sub(replace, value)


def _resolve_script_step(profile: DeployProfileSpec, action: str) -> ScriptStep:
    return profile.deploy if action == "deploy" else profile.status


def _resolve_script_path(repo_root: Path, step: ScriptStep) -> Path:
    configured_path = Path(step.run)
    if configured_path.is_absolute():
        raise ConfigError(
            f"Deploy script path must be repo-relative under {_SCRIPTS_ROOT.as_posix()}: {step.run}"
        )

    allowed_root = (repo_root / _SCRIPTS_ROOT).resolve()
    script_path = (repo_root / configured_path).resolve()
    try:
        script_path.relative_to(allowed_root)
    except ValueError as exc:
        raise ConfigError(
            f"Deploy script path must stay under {_SCRIPTS_ROOT.as_posix()}: {step.run}"
        ) from exc

    if not script_path.is_file():
        raise NotFoundError(f"Deploy script not found: {script_path}")
    return script_path


def _run_script(
    script_path: Path,
    *,
    repo_root: Path,
    payload: Mapping[str, Any],
    action: str,
    dry_run: bool,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    command = _build_command(script_path)
    script_environ = dict(environ)

    with tempfile.TemporaryDirectory(prefix="h2t-deploy-") as temp_dir:
        input_path = Path(temp_dir) / "payload.json"
        input_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        script_environ["H2T_DEPLOY_INPUT_JSON"] = str(input_path)
        script_environ["H2T_DEPLOY_ACTION"] = action
        script_environ["H2T_DEPLOY_DRY_RUN"] = "true" if dry_run else "false"

        try:
            completed = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                env=script_environ,
            )
        except OSError as exc:
            raise ProviderError(
                f"Failed to launch deploy script {script_path.name!r}: {exc}",
                details={"script": str(script_path)},
            ) from exc

    return _normalize_script_output(completed, action=action, script_path=script_path)


def _build_command(script_path: Path) -> list[str]:
    suffix = script_path.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(script_path)]
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-File", str(script_path)]
    if suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", str(script_path)]
    return [str(script_path)]


def _normalize_script_output(
    completed: subprocess.CompletedProcess[str],
    *,
    action: str,
    script_path: Path,
) -> dict[str, Any]:
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        parsed_stdout = _try_parse_json_object(stdout)
        if isinstance(parsed_stdout, Mapping) and parsed_stdout.get("ok") is False:
            error = parsed_stdout.get("error")
            raise _error_from_script_response(script_path, parsed_stdout, error)

        details = {"script": str(script_path), "returncode": completed.returncode}
        if stderr:
            details["stderr"] = stderr
        if stdout:
            details["stdout"] = stdout
        raise ProviderError(
            f"Deploy script failed with exit code {completed.returncode}",
            details=details,
        )

    if not stdout:
        raise ProviderError(
            "Deploy script returned empty stdout",
            details={"script": str(script_path)},
        )

    parsed = _try_parse_json_object(stdout)
    if parsed is None:
        raise ProviderError(
            "Deploy script returned invalid JSON",
            details={"script": str(script_path), "stdout": stdout},
        )

    if not isinstance(parsed, Mapping):
        raise ProviderError(
            "Deploy script must return a JSON object",
            details={"script": str(script_path), "stdout": parsed},
        )

    result: Any
    if "ok" in parsed:
        if parsed.get("ok") is not True:
            error = parsed.get("error")
            raise _error_from_script_response(script_path, parsed, error)
        result = parsed.get("result")
    else:
        result = parsed

    if not isinstance(result, Mapping):
        raise ProviderError(
            "Deploy script result must be a JSON object",
            details={"script": str(script_path), "response": dict(parsed)},
        )

    normalized_result = dict(result)
    for field in ("service", "target", "status"):
        value = normalized_result.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ProviderError(
                f"Deploy script result missing required field: {field}",
                details={"script": str(script_path), "response": dict(parsed)},
            )
    if action == "status":
        status = normalized_result.get("status")
        if status not in _STATUS_VALUES:
            raise ProviderError(
                f"Deploy status script returned invalid status: {status!r}",
                details={"script": str(script_path), "response": dict(parsed)},
            )

    return normalized_result


def _error_from_script_response(
    script_path: Path,
    parsed: Mapping[str, Any],
    error: Any,
) -> Exception:
    message = "Deploy script reported failure"
    details: dict[str, Any] = {
        "script": str(script_path),
        "response": dict(parsed),
    }
    exc_type = ProviderError
    hint = None

    if isinstance(error, Mapping):
        if isinstance(error.get("message"), str) and error["message"].strip():
            message = error["message"]
        if isinstance(error.get("type"), str):
            exc_type = _ERROR_TYPES.get(error["type"], ProviderError)
        if "details" in error:
            details["script_error_details"] = error["details"]
        if isinstance(error.get("hint"), str):
            hint = error["hint"]

    return exc_type(message, hint=hint, details=details)


def _try_parse_json_object(stdout: str) -> Any | None:
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None
