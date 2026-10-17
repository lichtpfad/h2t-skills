"""scripts/check_issue_links.py must start in the CI environment: stdlib plus pyyaml.

The CI step installs only pyyaml before calling the script. The script once imported
`docs.common` from plugins/h2t-dev/lib; that directory became package code and the step died
with ModuleNotFoundError before pytest was ever installed. Exit code 0 or 1 is legitimate
(it depends on what the branch touched); an import failure is not.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_script_imports_resolve() -> None:
    r = subprocess.run(
        [sys.executable, "scripts/check_issue_links.py", "HEAD"],
        capture_output=True, text=True, cwd=ROOT, encoding="utf-8",
    )
    assert "ModuleNotFoundError" not in r.stderr, r.stderr
    assert "ImportError" not in r.stderr, r.stderr
    assert "Traceback" not in r.stderr, r.stderr
