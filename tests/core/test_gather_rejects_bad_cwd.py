"""A cwd that does not exist is a broken instrument, not an empty result.

Measured on 2026-08-23: `h2t-gather --cwd /nonexistent/whatever --briefing-only` exited 0
and printed a plausible briefing for project `unknown`, whose one "handoff file" came from
~/.h2t/sessions/<machine>/unknown/. Nothing distinguished that from a real, empty project.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATHER = ROOT / "plugins" / "h2t-core" / "skills" / "session-start" / "scripts" / "gather.py"


def _run(cwd_arg):
    env = dict(os.environ, H2T_EVALS_MODE="off")
    return subprocess.run([sys.executable, str(GATHER), "--cwd", cwd_arg, "--briefing-only"],
                          capture_output=True, text=True, env=env, check=False)


def test_nonexistent_cwd_exits_config_error(tmp_path):
    result = _run(str(tmp_path / "no-such-dir"))
    assert result.returncode == 3, (result.returncode, result.stdout[:200])
    assert "BRIEFING:" not in result.stdout
    assert "no-such-dir" in result.stderr


def test_a_file_is_not_a_working_directory(tmp_path):
    not_a_dir = tmp_path / "regular-file"
    not_a_dir.write_text("", encoding="utf-8")
    result = _run(str(not_a_dir))
    assert result.returncode == 3, (result.returncode, result.stdout[:200])


def test_real_cwd_still_succeeds(tmp_path):
    """The control: the same probe must return 0 where the directory exists."""
    result = _run(str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "BRIEFING:" in result.stdout
