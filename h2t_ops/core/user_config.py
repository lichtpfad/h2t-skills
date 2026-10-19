"""The user's own settings: config/user.yaml (#548 R45).

The file belongs to the user (§7.1); the package only reads it. It holds the values that
used to sit in the code as the author's: `timezone`, `notion.tasks_database_id`,
`domain_patterns`. A missing file or key is None — each caller decides what that means.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


def path() -> Path:
    return paths.config_dir() / "user.yaml"


def get(key: str) -> Any | None:
    """`a.b` reads `{a: {b: ...}}`. No file, no key, or a non-mapping on the way → None."""
    f = path()
    if not f.is_file():
        return None
    try:
        doc = yaml.safe_load(f.read_bytes().decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{f} is not UTF-8: {exc}", hint="save the file as UTF-8") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = f" (line {mark.line + 1})" if mark is not None else ""
        raise ConfigError(f"{f} is not valid YAML{line}: {exc}",
                          hint="fix the file or remove it") from exc
    value: Any = doc
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value
