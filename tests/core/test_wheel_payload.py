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
        text=True,
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
    assert "lib/cli/main.py" in wheel_names
    assert "h2t_ops/connectors/research/systemprompts/academic.md" in wheel_names
