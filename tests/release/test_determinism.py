"""Two installs of one release give one Python and one package set (spec §2.6).

The wheel is installed twice, into two different UV_TOOL_DIRs, exactly as the bootstrap
installs it: `--python 3.12.11 --managed-python -c constraints.txt`. Both environments must
report the same `uv pip freeze` and the same `sys.version`.

Slow (it builds a wheel and resolves ~50 packages twice), so it is deselected by default:
run it with `-m slow` (or PYTEST_ADDOPTS="-m slow"). The release workflow runs it on the
published artifacts, passed in H2T_RELEASE_WHEEL (a directory) and H2T_RELEASE_CONSTRAINTS;
without them the test builds the wheel and exports the constraints from this checkout.

Red control: H2T_DETERMINISM_RED_CONTROL=1 drops `-c` from the second install. The sets
must then diverge; if they do not, the constraints are not what holds the set still.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYTHON = "3.12.11"
UV = shutil.which("uv")

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(UV is None, reason="uv is not on PATH; the release installs through it")]


def _run(cmd, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=900, **kwargs)
    if result.returncode != 0:
        pytest.fail(f"{' '.join(map(str, cmd))} exited {result.returncode}:\n"
                    f"{result.stdout[-2000:]}\n{result.stderr[-3000:]}")
    return result


@pytest.fixture(scope="module")
def release(tmp_path_factory) -> tuple[Path, Path]:
    """The wheel and constraints.txt under test."""
    given_wheel, given_constraints = (os.environ.get("H2T_RELEASE_WHEEL"),
                                      os.environ.get("H2T_RELEASE_CONSTRAINTS"))
    if given_wheel and given_constraints:
        return next(Path(given_wheel).glob("h2t_ops-*.whl")), Path(given_constraints)
    base = tmp_path_factory.mktemp("release")
    _run([UV, "build", "--wheel", "--out-dir", base / "dist", ROOT])
    constraints = base / "constraints.txt"
    _run([UV, "export", "--project", ROOT, "--frozen", "--no-dev", "--all-extras",
          "--no-emit-project", "--no-hashes", "-o", constraints])
    return next((base / "dist").glob("h2t_ops-*.whl")), constraints


def _install(base: Path, name: str, wheel: Path, constraints: Path | None,
             pythons: Path) -> tuple[list[str], str]:
    """Install the wheel as a uv tool under base/name; return (freeze, sys.version)."""
    root = base / name
    env = {**os.environ, "UV_TOOL_DIR": str(root / "tools"), "UV_TOOL_BIN_DIR": str(root / "bin"),
           "UV_PYTHON_INSTALL_DIR": str(pythons), "UV_PYTHON_BIN_DIR": str(root / "python-bin")}
    pin = ["-c", constraints] if constraints else []
    _run([UV, "tool", "install", "--python", PYTHON, "--managed-python", *pin, wheel], env=env)
    tool = root / "tools" / "h2t-ops"
    python = tool / "Scripts" / "python.exe" if sys.platform == "win32" else tool / "bin" / "python"
    freeze = _run([UV, "pip", "freeze", "--python", python], env=env).stdout.splitlines()
    version = _run([python, "-c", "import sys; print(sys.version)"], env=env).stdout.strip()
    return sorted(freeze), version


def test_two_installs_of_one_release_are_identical(release, tmp_path):
    wheel, constraints = release
    # One managed-Python store for both: the download is the same either way, and
    # sys.version still says which interpreter each environment actually resolved.
    pythons = tmp_path / "pythons"
    first = _install(tmp_path, "first", wheel, constraints, pythons)
    red = os.environ.get("H2T_DETERMINISM_RED_CONTROL") == "1"
    second = _install(tmp_path, "second", wheel, None if red else constraints, pythons)

    assert first[1] == second[1], (first[1], second[1])
    assert first[1].startswith(PYTHON + " "), first[1]
    only_first = sorted(set(first[0]) - set(second[0]))
    only_second = sorted(set(second[0]) - set(first[0]))
    assert first[0] == second[0], {"first only": only_first, "second only": only_second}
    assert len(first[0]) > 20, first[0]
    print(f"{len(first[0])} packages, Python {first[1].split()[0]}, identical")
