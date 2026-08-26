"""The wheel must carry everything the installed commands need.

`h2t-handoff`, `h2t-gather` and `h2t-activity-log` load plugin-owned scripts. On a
machine with no plugin host installed (Codex-only, CI, a bare server) nothing else
puts those scripts on disk, so `uv tool install git+...` has to ship them itself.
"""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = "h2t_ops/_plugin_payload"


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


def test_wheel_ships_the_scripts_the_entrypoints_load(wheel_names):
    assert f"{PAYLOAD}/skills/handoff/scripts/writer.py" in wheel_names
    assert f"{PAYLOAD}/skills/session-start/scripts/gather.py" in wheel_names
    assert f"{PAYLOAD}/lib/activity/writer.py" in wheel_names
    # #357: the lifecycle skills call these as commands, so the wheel is their only carrier
    assert f"{PAYLOAD}/skills/project-audit/scripts/scan.py" in wheel_names
    assert f"{PAYLOAD}/skills/project-audit/scripts/report.py" in wheel_names
    assert f"{PAYLOAD}/skills/init-project/scripts/apply_registration.py" in wheel_names
    assert f"{PAYLOAD}/skills/scaffold-project/scripts/scaffold_project.py" in wheel_names


def test_wheel_ships_the_lib_those_scripts_import(wheel_names):
    assert f"{PAYLOAD}/lib/gather/briefing.py" in wheel_names
    assert f"{PAYLOAD}/lib/eval/session.py" in wheel_names


def test_wheel_payload_carries_no_bytecode(wheel_names):
    """A stale .pyc next to the payload would shadow the source it was built from.

    The plugin's own test modules do ride along: hatchling's `exclude` does not apply to
    `force-include`, and they are inert (nothing imports them at runtime).
    """
    assert [n for n in wheel_names if n.startswith(PAYLOAD) and "__pycache__" in n] == []


def test_wheel_still_ships_the_package_and_its_data(wheel_names):
    assert "h2t_ops/cli.py" in wheel_names
    # lib/cli/main.py is deliberately absent now — _legacy() guards the import and the
    # contract for an unrecognised command stays exit 2.
    assert f"{PAYLOAD}/lib/eval/session.py" in wheel_names
    assert "h2t_ops/connectors/research/systemprompts/academic.md" in wheel_names


def test_wheel_ships_the_hook_handlers_h2t_hook_resolves(wheel_names):
    """`h2t-hook <name>` is on PATH as soon as the wheel installs, but it resolves the
    handler through the plugin ladder — and on a host with no plugin cache the payload is
    the only rung left. Without these files the command exists and exits 5, which for a
    hook means silence.
    """
    for handler in ("on-stop", "post-git-commit-docs-lint", "post_git_commit_docs_lint.py"):
        assert f"{PAYLOAD}/hooks-handlers/{handler}" in wheel_names, handler


def test_the_wheel_claims_no_generic_top_level_name(wheel_names):
    """`lib` in site-packages is about as generic a name as a distribution can claim.

    Nothing else in the wheel needs it: the payload carries the same modules under
    h2t_ops/_plugin_payload, which is where every entry point already looks.
    """
    tops = {n.split("/")[0] for n in wheel_names if "/" in n}
    assert tops, "no entries read from the wheel — the fixture is broken, not the wheel"
    assert "lib" not in tops, f"wheel claims the top-level name 'lib': {sorted(tops)}"


def test_each_payload_module_ships_once(wheel_names):
    for name in ("eval/session.py", "eval/skill_class.py", "activity/writer.py"):
        copies = [n for n in wheel_names if n.endswith(name)]
        assert len(copies) == 1, f"{name} ships {len(copies)} times: {copies}"


def test_the_payload_lib_is_complete(wheel_names):
    """The evals connector reaches status/report through the payload now."""
    assert f"{PAYLOAD}/lib/eval/status.py" in wheel_names
    assert f"{PAYLOAD}/lib/eval/report.py" in wheel_names
