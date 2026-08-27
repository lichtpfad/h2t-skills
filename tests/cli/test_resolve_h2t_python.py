"""Run the resolver's shell tests, because nothing else did.

`test_resolve_h2t_python.sh` has sat next to the Python tests since it was written,
covering the interpreter chain three hooks depend on. Neither pytest (which collects
`test_*.py`) nor CI (which invokes pytest) ever ran it. It was a file, not a test —
green by never executing.

The suite is bash-only by design: it fakes interpreters as executable scripts and
inspects `H2T_PYTHON_CMD`, which is a bash array. Rewriting it in Python would test a
reimplementation instead of the thing the hooks source.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_suffix(".sh")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_resolver_shell_suite_passes():
    result = subprocess.run(
        [shutil.which("bash"), str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, (
        f"{SCRIPT.name} failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "OK: resolve-h2t-python" in result.stdout, result.stdout
