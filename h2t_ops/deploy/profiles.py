"""Deploy profile registry loader."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError

from .models import DeployProfileSpec, ScriptStep
from ._yaml import load_yaml_mapping

_PROFILES_RELATIVE_PATH = Path(".h2t/config/deploy/profiles.yaml")


def load_profile_registry(path: Path | None = None) -> Mapping[str, DeployProfileSpec]:
    """Load deploy profiles from YAML."""
    config_path = path or (Path.home() / _PROFILES_RELATIVE_PATH)
    raw = load_yaml_mapping(config_path, top_level_key="profiles")

    profiles: dict[str, DeployProfileSpec] = {}
    for name, payload in raw["profiles"].items():
        spec = _parse_profile(name, payload)
        profiles[name] = spec
    return MappingProxyType(profiles)


def _parse_profile(name: str, payload: Any) -> DeployProfileSpec:
    if not isinstance(payload, Mapping):
        raise ConfigError(f"Deploy profile {name!r} must be a mapping")

    contract_version = payload.get("contract_version")
    if contract_version != 1:
        raise ConfigError(
            f"Deploy profile {name!r} must set contract_version to 1; got {contract_version!r}"
        )

    kind = payload.get("kind")
    if kind != "script-bundle":
        raise ConfigError(
            f"Deploy profile {name!r} must set kind to 'script-bundle'; got {kind!r}"
        )

    inputs = payload.get("inputs", [])
    if not isinstance(inputs, list) or any(not isinstance(item, str) for item in inputs):
        raise ConfigError(f"Deploy profile {name!r} inputs must be a list of strings")

    deploy = _parse_script_step(name, "deploy", payload.get("deploy"))
    status = _parse_script_step(name, "status", payload.get("status"))

    return DeployProfileSpec(
        name=name,
        contract_version=contract_version,
        kind=kind,
        inputs=tuple(inputs),
        deploy=deploy,
        status=status,
    )


def _parse_script_step(profile_name: str, step_name: str, payload: Any) -> ScriptStep:
    if not isinstance(payload, Mapping):
        raise ConfigError(f"Deploy profile {profile_name!r} field {step_name!r} must be a mapping")

    run = payload.get("run")
    if not isinstance(run, str) or not run.strip():
        raise ConfigError(
            f"Deploy profile {profile_name!r} field {step_name}.run must be a non-empty string"
        )
    return ScriptStep(run=run)
