"""A test directory nobody runs is documentation, not a test.

25 meetgeek tests landed in #389/#390 and never executed on GitHub, and eight of the ten
plugin test directories outside CI were found green on 2026-08-23 only because someone
looked (#381). This file used to check that every plugin test directory had a CI step.

Since Task 12 (#541) the plugins ship text only and their tests live in tests/, which CI
runs whole. So the guard is now the other way round: no test may land in plugins/, where
the one CI step does not reach; and every path a workflow hands pytest must exist, since
a step pointing at a deleted directory fails on an empty collection.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _plugin_test_files():
    return sorted(
        path.relative_to(ROOT).as_posix()
        for pattern in ("test_*.py", "*_test.py", "conftest.py")
        for path in (ROOT / "plugins").rglob(pattern)
        if "__pycache__" not in path.parts
    )


def test_plugins_ship_no_tests():
    assert _plugin_test_files() == [], "tests belong in tests/, which CI runs"


def _pytest_run_lines():
    """`run:` commands that actually invoke pytest, comments excluded."""
    lines = []
    for path in WORKFLOWS.glob("*.yml"):
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.startswith("#") or "run:" not in stripped:
                continue
            command = stripped.split("run:", 1)[1].strip()
            if re.search(r"\bpytest\b", command):
                lines.append(command)
    return lines


def test_the_workflow_probe_finds_pytest_runs():
    """Control: an empty command list would make the next test vacuously true."""
    commands = _pytest_run_lines()
    assert any("pytest tests/" in c for c in commands), commands


def _has_python(path: Path) -> bool:
    """A deleted test directory can survive on disk as bare __pycache__ dirs."""
    if path.is_file():
        return True
    return any("__pycache__" not in p.parts for p in path.rglob("*.py"))


def test_every_path_a_workflow_hands_pytest_exists():
    missing = []
    for command in _pytest_run_lines():
        after = command.split("pytest", 1)[1].split()
        for arg in after:
            if arg.startswith("-") or "${{" in arg:
                continue
            if "/" in arg and not _has_python(ROOT / arg):
                missing.append(f"{arg}  ({command})")
    assert not missing, "\n".join(missing)
