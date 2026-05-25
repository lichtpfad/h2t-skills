"""Deploy registry models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class DeployTargetBinding:
    name: str
    profile: str
    config: Mapping[str, Any]


@dataclass(frozen=True)
class DeployServiceSpec:
    name: str
    service_type: str
    help: str
    default_target: str
    targets: Mapping[str, DeployTargetBinding]


@dataclass(frozen=True)
class ScriptStep:
    run: str


@dataclass(frozen=True)
class DeployProfileSpec:
    name: str
    contract_version: int
    kind: str
    inputs: tuple[str, ...]
    deploy: ScriptStep
    status: ScriptStep
