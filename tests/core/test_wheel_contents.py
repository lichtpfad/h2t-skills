"""The wheel carries the package and nothing from the plugin tree.

Until Task 12 the wheel force-included the h2t-core plugin scripts and their lib as
`h2t_ops/_plugin_payload`, because the entry points loaded plugin-owned scripts and a host
with no plugin cache had no other copy. The entry points run h2t_ops/lifecycle now, the
plugin scripts are deleted, and so is the payload.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def wheel_names(tmp_path_factory) -> set[str]:
    out_dir = tmp_path_factory.mktemp("wheel")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(REPO_ROOT), "--no-deps", "-w", str(out_dir)],
        capture_output=True,
        text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.fail(f"wheel build failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    wheel = next(out_dir.glob("h2t_ops-*.whl"))
    return set(zipfile.ZipFile(wheel).namelist())


def test_the_wheel_has_no_plugin_payload(wheel_names):
    assert wheel_names, "no entries read from the wheel — the fixture is broken, not the wheel"
    assert [n for n in wheel_names if "_plugin_payload" in n] == []
    assert [n for n in wheel_names if n.startswith(("plugins/", "skills/"))] == []


def test_the_wheel_carries_no_bytecode(wheel_names):
    """A stale .pyc would shadow the source it was built from."""
    assert [n for n in wheel_names if "__pycache__" in n or n.endswith(".pyc")] == []


def test_wheel_ships_the_package_and_its_data(wheel_names):
    assert "h2t_ops/cli.py" in wheel_names
    # lib/cli/main.py is deliberately absent — _legacy() guards the import and the
    # contract for an unrecognised command stays exit 2.
    for module in ("session_start.py", "handoff.py", "apply_registration.py",
                   "project_audit_scan.py", "project_audit_report.py", "scaffold_project.py",
                   "eval/status.py", "eval/report.py", "gather/briefing.py"):
        assert f"h2t_ops/lifecycle/{module}" in wheel_names, module
    assert "h2t_ops/connectors/research/systemprompts/academic.md" in wheel_names


def test_wheel_ships_the_hook_handlers_h2t_hook_resolves(wheel_names):
    """`h2t-hook <name>` is on PATH as soon as the wheel installs, and every name resolves
    to a module in h2t_ops/hooks (Task 12a). Without these files the command exists and
    exits 5, which for a hook means silence. The 3.x plugin handlers are not shipped.
    """
    for module in ("on_stop", "post_git_commit_docs_lint", "layout_precommit",
                   "bulk_precommit", "secrets_precommit", "gather", "structure_guard"):
        assert f"h2t_ops/hooks/{module}.py" in wheel_names, module
    assert not [n for n in wheel_names if "hooks-handlers" in n]


def test_the_wheel_claims_no_generic_top_level_name(wheel_names):
    """`lib` in site-packages is about as generic a name as a distribution can claim."""
    tops = {n.split("/")[0] for n in wheel_names if "/" in n}
    assert tops, "no entries read from the wheel — the fixture is broken, not the wheel"
    assert "lib" not in tops, f"wheel claims the top-level name 'lib': {sorted(tops)}"


def test_each_lifecycle_module_ships_once(wheel_names):
    """Once, in h2t_ops/lifecycle: the payload copy left with the force-include (Task 12)."""
    for name in ("eval/session.py", "eval/skill_class.py", "activity/writer.py"):
        copies = sorted(n for n in wheel_names if n.endswith(name))
        assert copies == [f"h2t_ops/lifecycle/{name}"], f"{name} ships {len(copies)} times: {copies}"
