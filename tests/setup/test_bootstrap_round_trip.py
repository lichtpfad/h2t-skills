"""The full bootstrap circle (#548 §7.3): what state.commit writes through paths.run_dir()
is what plugins/h2t-core/hooks/run reads from $HOME/.h2t/run in bash. Each side has its own
tests; the contract lives in the seam (verification.md)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from h2t_ops.setup import state

RUN = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "hooks" / "run"


@pytest.mark.skipif(sys.platform == "win32", reason="covered by tests/hooks/test_hooks_run.py on Git Bash")
def test_hooks_run_reads_what_state_wrote(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "elsewhere"))  # must not move run/
    hook = tmp_path / "bin" / "h2t-hook"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\necho HOOK-RAN \"$@\"\n")
    hook.chmod(0o755)
    version = (RUN.parent.parent / "release.env").read_text().split("VERSION=")[1].split()[0]
    state.commit(state.Install(version=version, generation="g1", tool_root=str(tmp_path),
                               entrypoints={"h2t-hook": str(hook)}))
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(RUN.parent.parent)}
    out = subprocess.run(["bash", str(RUN), "session-start"], input="{}", text=True,
                         capture_output=True, env=env, timeout=30)
    assert "HOOK-RAN session-start" in out.stdout, out.stderr
