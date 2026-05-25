"""Deploy registry models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeployTargetBinding:
    name: str
    profile: str
    config: dict[str, Any]


@dataclass(frozen=True)
class DeployServiceSpec:
    name: str
    service_type: str
    help: str
    default_target: str
    targets: dict[str, DeployTargetBinding]


@dataclass(frozen=True)
class ScriptStep:
    run: str


@dataclass(frozen=True)
class DeployProfileSpec:
    name: str
    contract_version: int
    kind: str
    inputs: list[str]
    deploy: ScriptStep
    status: ScriptStep
