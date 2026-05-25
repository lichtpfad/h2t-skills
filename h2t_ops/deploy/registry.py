"""Deploy service registry loader."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from h2t_ops.core.errors import ConfigError

from .models import DeployServiceSpec, DeployTargetBinding, DeployProfileSpec
from .profiles import load_profile_registry
from ._yaml import load_yaml_mapping

_SERVICES_RELATIVE_PATH = Path(".h2t/config/deploy/services.yaml")


def load_service_registry(
    path: Path | None = None,
    *,
    profiles: Mapping[str, DeployProfileSpec] | None = None,
) -> Mapping[str, DeployServiceSpec]:
    """Load deploy services from YAML and validate referenced profiles."""
    config_path = path or (Path.home() / _SERVICES_RELATIVE_PATH)
    raw = load_yaml_mapping(config_path, top_level_key="services")
    profile_registry = profiles if profiles is not None else load_profile_registry()

    services: dict[str, DeployServiceSpec] = {}
    for name, payload in raw["services"].items():
        spec = _parse_service(name, payload, profiles=profile_registry)
        services[name] = spec
    return MappingProxyType(services)


def _parse_service(
    name: str,
    payload: Any,
    *,
    profiles: Mapping[str, DeployProfileSpec],
) -> DeployServiceSpec:
    if not isinstance(payload, Mapping):
        raise ConfigError(f"Deploy service {name!r} must be a mapping")

    service_type = payload.get("service_type")
    if not isinstance(service_type, str) or not service_type.strip():
        raise ConfigError(f"Deploy service {name!r} missing required field: service_type")

    help_text = payload.get("help", "")
    if not isinstance(help_text, str):
        raise ConfigError(f"Deploy service {name!r} field 'help' must be a string")

    default_target = payload.get("default_target")
    if not isinstance(default_target, str) or not default_target.strip():
        raise ConfigError(f"Deploy service {name!r} missing required field: default_target")

    raw_targets = payload.get("targets")
    if not isinstance(raw_targets, Mapping) or not raw_targets:
        raise ConfigError(f"Deploy service {name!r} field 'targets' must be a non-empty mapping")

    targets: dict[str, DeployTargetBinding] = {}
    for target_name, target_payload in raw_targets.items():
        binding = _parse_target(name, target_name, target_payload, profiles=profiles)
        targets[target_name] = binding

    if default_target not in targets:
        raise ConfigError(
            f"Deploy service {name!r} default_target {default_target!r} does not match any target"
        )

    return DeployServiceSpec(
        name=name,
        service_type=service_type,
        help=help_text,
        default_target=default_target,
        targets=MappingProxyType(targets),
    )


def _parse_target(
    service_name: str,
    target_name: str,
    payload: Any,
    *,
    profiles: Mapping[str, DeployProfileSpec],
) -> DeployTargetBinding:
    if not isinstance(payload, Mapping):
        raise ConfigError(f"Deploy target {service_name!r}.{target_name!r} must be a mapping")

    profile_name = payload.get("profile")
    if not isinstance(profile_name, str) or not profile_name.strip():
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} missing required field: profile"
        )

    if profile_name not in profiles:
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} references unknown profile {profile_name!r}"
        )

    config = payload.get("config", {})
    if not isinstance(config, Mapping):
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} field 'config' must be a mapping"
        )

    _validate_target_config(
        service_name,
        target_name,
        dict(config),
        profiles[profile_name],
    )

    return DeployTargetBinding(
        name=target_name,
        profile=profile_name,
        config=MappingProxyType(dict(config)),
    )


def _validate_target_config(
    service_name: str,
    target_name: str,
    config: dict[str, Any],
    profile: DeployProfileSpec,
) -> None:
    required_keys = set(profile.inputs)
    actual_keys = set(config)

    missing_keys = sorted(required_keys - actual_keys)
    if missing_keys:
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} missing required config keys "
            f"for profile {profile.name!r}: {', '.join(missing_keys)}"
        )

    unknown_keys = sorted(actual_keys - required_keys)
    if unknown_keys:
        raise ConfigError(
            f"Deploy target {service_name!r}.{target_name!r} has unknown config keys "
            f"for profile {profile.name!r}: {', '.join(unknown_keys)}"
        )
