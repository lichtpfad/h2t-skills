"""Exit codes are the only thing a caller can branch on; `1` for everything is no signal.

The taxonomy is the one CLAUDE.md gives the connectors: 0 ok, 2 usage, 3 config.
`h2t-ops nosuchconnector` already exits 2; these entry points are being brought in line.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "plugins" / "h2t-core" / "skills" / "handoff" / "scripts" / "writer.py"


def _env(tmp_path, **extra):
    env = dict(os.environ)
    env.update({
        "H2T_ACTIVITY_SPOOL": str(tmp_path / "spool.jsonl"),
        "H2T_SESSION_ROOT": str(tmp_path / "sessions"),
        "H2T_MACHINE_NAME": "testbox",
        "H2T_EVALS_MODE": "off",
    })
    env.update(extra)
    return env


def _run(tmp_path, *argv, **extra):
    return subprocess.run([sys.executable, str(WRITER), *argv],
                          capture_output=True, text=True, check=False, env=_env(tmp_path, **extra))


def test_no_subcommand_is_a_usage_error(tmp_path):
    """argparse already exits 2 for a missing required flag; printing help must agree."""
    assert _run(tmp_path).returncode == 2


def test_missing_session_id_is_a_usage_error(tmp_path):
    assert _run(tmp_path, "write").returncode == 2


def test_a_good_write_exits_0(tmp_path):
    """The control. Without it, an exit code of 3 everywhere would satisfy the test below."""
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p", "--domain", "d")
    assert result.returncode == 0, result.stderr[-400:]
    assert json.loads(result.stdout)["status"] == "ok"


def test_an_unusable_markdown_dir_exits_3_and_still_keeps_the_record(tmp_path):
    """`gates.md`: nothing may stand between work the session produced and its persistence.

    The spool write happens before the mirror. A mirror directory that cannot be created
    used to raise NotADirectoryError out of main() — exit 1, a traceback, and a session
    that looks lost even though its record is on disk.
    """
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p",
                  "--domain", "d", "--markdown-dir", "/dev/null/deep")
    assert result.returncode == 3, (result.returncode, result.stderr[-400:])
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    spool = Path(payload["spool"])
    assert spool.is_file(), "the record was lost — the point of the exit code is that it is not"
    assert "probe" in spool.read_text(encoding="utf-8")


def test_a_failed_markdown_file_also_exits_3(tmp_path):
    """The pre-existing degraded path — mirror directory fine, file write refused.

    write_handoff already returned status "degraded" here, but main() exited 0, so a caller
    branching on the exit code could not tell a complete write from a partial one.
    """
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "probe.md").mkdir()  # the file path is a directory: write_text raises OSError
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p",
                  "--domain", "d", "--markdown-dir", str(mirror))
    assert result.returncode == 3, (result.returncode, result.stderr[-300:])
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    assert payload["mirror_write_failed"] is True
    assert Path(payload["latest"]).is_file(), "latest.json is writable here and must be written"


def test_an_unwritable_latest_json_also_exits_3(tmp_path):
    """latest.json is part of the same mirror and used to sit outside every guard.

    Reproduced before this test existed: a directory named latest.json.tmp raised
    IsADirectoryError out of main() — exit 1, a traceback, and the spool already on disk.
    """
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "latest.json.tmp").mkdir()
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p",
                  "--domain", "d", "--markdown-dir", str(mirror))
    assert result.returncode == 3, (result.returncode, result.stderr[-300:])
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    spool = Path(payload["spool"])
    assert spool.is_file() and "probe" in spool.read_text(encoding="utf-8")
