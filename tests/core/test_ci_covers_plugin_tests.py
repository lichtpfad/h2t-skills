"""A test directory nobody runs is documentation, not a test.

25 meetgeek tests landed in #389/#390 and have never executed on GitHub. Eight of the ten
plugin test directories outside CI were measured green on 2026-08-23 — 1185 assertions
nobody was checking — and three were red for reasons no one had seen (#381).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


# plugins/h2t/ is the rollback archive: the marketplace ships h2t-core, h2t-ops, h2t-dev,
# h2t-arch, h2t-creative and h2t-edu, and nothing else. Running an archive's tests in CI
# would gate the repo on code no one can install.
ARCHIVED = "plugins/h2t/"

# drawio's `test_*.py` are manual smoke scripts, not pytest modules: 578 lines of
# module-level asserts and print() that run on import and define no test function, so
# `pytest` there exits 5 ("no tests ran") and a CI step would fail on an empty collection.
# Converting them is #396; until then, naming them here is honest and a green CI is not
# claiming to have run them.
NOT_PYTEST = ("plugins/h2t-arch/skills/drawio/scripts",)


def _dirs_with_tests():
    return sorted({
        path.parent.relative_to(ROOT).as_posix()
        for path in (ROOT / "plugins").rglob("test_*.py")
        if "__pycache__" not in path.parts
        and not path.relative_to(ROOT).as_posix().startswith(ARCHIVED)
        and path.parent.relative_to(ROOT).as_posix() not in NOT_PYTEST
    })


def test_the_probe_finds_plugin_test_dirs():
    """Control: an empty list would make the next test vacuously true."""
    found = _dirs_with_tests()
    assert len(found) >= 10, found


def _pytest_run_lines():
    """`run:` commands that actually invoke pytest, comments excluded.

    Matching the directory name anywhere in the YAML would accept a mention in a comment,
    a job name, or a disabled workflow — a guard that can go green while CI runs nothing.
    """
    lines = []
    for path in WORKFLOWS.glob("*.yml"):
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped.startswith("#") or "run:" not in stripped:
                continue
            command = stripped.split("run:", 1)[1].strip()
            if "pytest" in command:
                lines.append(command)
    return lines


def test_the_workflow_probe_finds_pytest_runs():
    """Control: an empty command list would make the next test vacuously true."""
    commands = _pytest_run_lines()
    assert len(commands) >= 4, commands


def test_every_plugin_test_dir_is_run_by_a_workflow():
    commands = _pytest_run_lines()
    missing = [d for d in _dirs_with_tests()
               if not any(d in command for command in commands)]
    assert not missing, f"plugin test dirs never run in CI: {missing}"
