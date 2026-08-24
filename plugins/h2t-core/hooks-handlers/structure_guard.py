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
            return 2, (
                f"BLOCKED: директория {root!r} не в allowlist. "
                f"Допустимые: {allowed_list}. "
                f"Создаёте новую директорию осознанно? Добавьте её в "
                f".h2t/structure.yaml и повторите запись."
            )

    return 0, ""


_FM_EXEMPT_NAMES = {"readme.md", "index.md"}


def _has_frontmatter(content: str) -> bool:
    """True if *content* opens with a `---` … `---` YAML frontmatter block."""
    s = content.lstrip("﻿")
    lines = s.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    return any(line.strip() == "---" for line in lines[1:])


def check_frontmatter_presence(
    file_path: str, content: str, config: dict
) -> tuple[int, str]:
    """Block (code 2) when a Markdown file under a frontmatter_dir is written
    without a frontmatter block. Presence-only — field-level validation stays
    in docs-lint's check_frontmatter. Returns (0, "") when not applicable.

    This was a warning until 2026-08-24. A warning in PreToolUse exits 0, so
    the write lands and the message is advice the model may decline — the same
    layer as a rules file. 47 plans carried a stale `status: draft` under it.
    """
    dirs = config.get("frontmatter_dirs", [])
    if not dirs:
        return 0, ""
    norm = file_path.replace("\\", "/")
    name = Path(norm).name
    if not name.lower().endswith(".md") or name.lower() in _FM_EXEMPT_NAMES:
        return 0, ""
    if not any(norm.startswith(d) for d in dirs):
        return 0, ""
    if _has_frontmatter(content):
        return 0, ""
    return 2, (
        f"BLOCKED: {norm!r} без frontmatter. Создайте через "
        f"`docs-lint new <plan|spec|adr> <slug>` (сгенерирует поля), "
        f"либо добавьте блок --- вручную, либо после записи прогоните "
        f"`docs-lint fix-safe --only=frontmatter`."
    )


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
    if exit_code == 2:
        # Blocking beats any warning — surface it and stop.
        print(message, file=sys.stderr)
        return 2

    messages = [message] if message else []

    # Frontmatter presence — only Write carries the full file content.
    if tool_name == "Write":
        fm_code, fm_msg = check_frontmatter_presence(
            norm, tool_input.get("content", ""), config
        )
        if fm_code == 2:
            print("\n".join([*messages, fm_msg]), file=sys.stderr)
            return 2
        if fm_msg:
            messages.append(fm_msg)

    if messages:
        print("\n".join(messages), file=sys.stderr)

    # code 1 (warn) prints to stderr but EXITs 0 — Claude Code exit 1 semantics
    # in PreToolUse are undefined, so we never block on a warning.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
