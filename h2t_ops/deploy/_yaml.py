"""Shared YAML loading helpers for deploy config files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from h2t_ops.core.errors import ConfigError


def load_yaml_mapping(path: Path, *, top_level_key: str) -> dict[str, Any]:
    """Load a deploy YAML file and validate its top-level section shape."""
    if not path.exists():
        raise ConfigError(f"Deploy config file not found: {path}")

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(loaded, Mapping):
        raise ConfigError(f"Deploy config {path} must contain a top-level mapping")

    if top_level_key not in loaded:
        raise ConfigError(f"Deploy config {path} missing required top-level key: {top_level_key}")

    section = loaded[top_level_key]
    if not isinstance(section, Mapping):
        raise ConfigError(f"Deploy config section {top_level_key!r} in {path} must be a mapping")

    return dict(loaded)
