"""Tests for structure_guard.py PreToolUse hook."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_guard():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "structure_guard.py"
    spec = importlib.util.spec_from_file_location("structure_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ── config fixture ──────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "allowed_root_dirs": ["plugins/", "docs/", "h2t_ops/", "lib/", "scripts/", "tests/"],
    "forbidden_patterns": ["tmp_*", "*_tmp.*", "*_v2.*", "*_copy.*", "*_backup.*"],
    "plan_dirs": [
        {"path": "docs/superpowers/plans/", "pattern": r"^\d{4}-\d{2}-\d{2}-.+\.md$"},
    ],
}


# ── _parse_yaml ──────────────────────────────────────────────────────────────

def test_parse_yaml_allowed_root_dirs():
    guard = _load_guard()
    yaml_text = (
        "allowed_root_dirs:\n"
        "  - plugins/\n"
        "  - docs/\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert result["allowed_root_dirs"] == ["plugins/", "docs/"]


def test_parse_yaml_forbidden_patterns():
    guard = _load_guard()
    yaml_text = (
        "forbidden_patterns:\n"
        '  - "tmp_*"\n'
        '  - "*_v2.*"\n'
    )
    result = guard._parse_yaml(yaml_text)
    assert result["forbidden_patterns"] == ["tmp_*", "*_v2.*"]


def test_parse_yaml_plan_dirs():
    guard = _load_guard()
    yaml_text = (
        "plan_dirs:\n"
        "  - path: docs/superpowers/plans/\n"
        r'    pattern: "^\d{4}-\d{2}-\d{2}-.+\.md$"' + "\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert len(result["plan_dirs"]) == 1
    assert result["plan_dirs"][0]["path"] == "docs/superpowers/plans/"
    assert r"\d{4}" in result["plan_dirs"][0]["pattern"]


# ── check_file ───────────────────────────────────────────────────────────────

def test_forbidden_tmp_prefix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("tmp_foo.txt", SAMPLE_CONFIG)
    assert code == 2
    assert "tmp_*" in msg


def test_forbidden_v2_suffix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/something_v2.py", SAMPLE_CONFIG)
    assert code == 2


def test_plan_dir_bad_name_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/foo.md", SAMPLE_CONFIG)
    assert code == 2
    assert "YYYY-MM-DD" in msg or "pattern" in msg.lower()


def test_plan_dir_good_name_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/2026-06-14-foo.md", SAMPLE_CONFIG)
    assert code == 0


def test_known_root_dir_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/foo.py", SAMPLE_CONFIG)
    assert code == 0


def test_unknown_root_dir_warns():
    guard = _load_guard()
    code, msg = guard.check_file("random_new_dir/foo.py", SAMPLE_CONFIG)
    assert code == 1
    assert "random_new_dir" in msg or "allowlist" in msg.lower()


def test_no_config_returns_zero(tmp_path):
    guard = _load_guard()
    config = guard.load_config(tmp_path)
    assert config is None


def test_unknown_tool_name_returns_zero():
    guard = _load_guard()
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert guard._is_write_tool(payload["tool_name"]) is False


def test_write_tool_recognized():
    guard = _load_guard()
    for name in ("Write", "Edit", "MultiEdit"):
        assert guard._is_write_tool(name) is True


def test_load_config_and_check_file_integration(tmp_path):
    """End-to-end: write a real YAML file, load it, verify check_file uses it."""
    guard = _load_guard()
    yaml_content = (
        "allowed_root_dirs:\n"
        "  - plugins/\n"
        "  - docs/\n"
        "forbidden_patterns:\n"
        '  - "tmp_*"\n'
        "plan_dirs:\n"
        "  - path: docs/superpowers/plans/\n"
        '    pattern: "^\\d{4}-\\d{2}-\\d{2}-.+\\.md$"\n'
    )
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "structure.yaml").write_text(yaml_content, encoding="utf-8")

    config = guard.load_config(tmp_path)
    assert config is not None

    # Forbidden pattern from real file
    code, _ = guard.check_file("tmp_analysis.txt", config)
    assert code == 2

    # Good plan dir name from real file
    code, _ = guard.check_file("docs/superpowers/plans/2026-06-14-foo.md", config)
    assert code == 0

    # Bad plan dir name from real file
    code, _ = guard.check_file("docs/superpowers/plans/foo.md", config)
    assert code == 2
