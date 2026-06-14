#!/usr/bin/env python3
"""PreToolUse hook: enforce file naming conventions from .h2t/structure.yaml.

Exit codes (process):
  0 — allow (includes warn cases — Claude Code exit 1 behavior is undefined)
  2 — block (prevents Write/Edit/MultiEdit)

check_file() internal codes:
  0 — allow silently
  1 — warn (main() prints to stderr, exits 0)
  2 — block (main() prints to stderr, exits 2)

Fail-open: if .h2t/structure.yaml is missing or unreadable → EXIT 0.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

_STRUCTURE_FILE = ".h2t/structure.yaml"
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def _is_write_tool(tool_name: str) -> bool:
    return tool_name in _WRITE_TOOLS


def _parse_yaml(text: str) -> dict:
    """Minimal YAML parser for structure.yaml format (stdlib only, no PyYAML)."""
    result: dict = {}
    current_list: list | None = None
    current_dict: dict | None = None

    for line in text.splitlines():
        raw = line.rstrip()
        if not raw or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())

        if indent == 0 and ":" in raw:
            key = raw.split(":", 1)[0].strip()
            result[key] = []
            current_list = result[key]
            current_dict = None

        elif indent == 2 and raw.lstrip().startswith("- ") and current_list is not None:
            content = raw.lstrip()[2:].strip()
            if ":" in content:
                k, v = content.split(":", 1)
                current_dict = {k.strip(): v.strip().strip('"').strip("'")}
                current_list.append(current_dict)
            else:
                current_dict = None
                current_list.append(content.strip('"').strip("'"))

        elif indent == 4 and current_dict is not None and ":" in raw:
            k, v = raw.strip().split(":", 1)
            current_dict[k.strip()] = v.strip().strip('"').strip("'")

    return result


def load_config(repo_root: Path) -> dict | None:
    config_path = repo_root / _STRUCTURE_FILE
    if not config_path.exists():
        return None
    try:
        text = config_path.read_text(encoding="utf-8")
        return _parse_yaml(text)
    except Exception:
        return None


def check_file(file_path: str, config: dict) -> tuple[int, str]:
    """Return (exit_code, message). 0=allow, 1=warn, 2=block."""
    norm = file_path.replace("\\", "/")
    name = Path(norm).name

    # 1. Forbidden name patterns
    for pattern in config.get("forbidden_patterns", []):
        if fnmatch.fnmatchcase(name, pattern):
            return 2, (
                f"BLOCKED: запрещённый паттерн имени {pattern!r}. "
                f"Переименуйте файл. Файл: {norm!r}"
            )

    # 2. Plan directory naming rules
    for plan_dir in config.get("plan_dirs", []):
        dir_path = plan_dir.get("path", "")
        pattern = plan_dir.get("pattern", "")
        if norm.startswith(dir_path):
            if not re.match(pattern, name):
                return 2, (
                    f"BLOCKED: файл в {dir_path!r} должен соответствовать паттерну "
                    f"YYYY-MM-DD-<name>.md. Получено: {name!r}"
                )
            return 0, ""

    # 3. Unknown root directory
    allowed = config.get("allowed_root_dirs", [])
    if allowed and "/" in norm:
        root = norm.split("/")[0]
        allowed_roots = {a.rstrip("/") for a in allowed}
        if root not in allowed_roots:
            allowed_list = ", ".join(sorted(allowed_roots))
            return 1, (
                f"WARNING: директория {root!r} не в allowlist. "
                f"Допустимые: {allowed_list}. "
                f"Создаёте новую директорию? Добавьте в .h2t/structure.yaml."
            )

    return 0, ""


def _load_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def main() -> int:
    payload = _load_payload()

    tool_name = payload.get("tool_name", "")
    if not _is_write_tool(tool_name):
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    repo_root = Path.cwd().resolve()
    config = load_config(repo_root)
    if config is None:
        return 0  # fail open — no .h2t/structure.yaml

    # Normalise to repo-relative path
    try:
        rel = Path(file_path).resolve().relative_to(repo_root)
        norm = str(rel).replace("\\", "/")
    except ValueError:
        return 0  # outside repo — not our concern

    exit_code, message = check_file(norm, config)

    if message:
        print(message, file=sys.stderr)

    # check_file code 1 = warn intent: print to stderr but EXIT 0
    # (Claude Code exit 1 semantics in PreToolUse are undefined — safer to exit 0)
    return 2 if exit_code == 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
