"""Exit codes are the only thing a caller can branch on; `1` for everything is no signal.

The taxonomy is the one CLAUDE.md gives the connectors: 0 ok, 2 usage, 3 config.
`h2t-ops nosuchconnector` already exits 2; these entry points are being brought in line.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRITER = "h2t_ops.lifecycle.handoff"  # the plugin script, deleted in Task 12, ran as this module


def _env(tmp_path, **extra):
    env = dict(os.environ)
    home = tmp_path / "home"
    env.update({
        "HOME": str(home),
        "USERPROFILE": str(home),
        "H2T_MACHINE_NAME": "testbox",
        "H2T_EVALS_MODE": "off",
    })
    env.update(extra)
    return env


def _run(tmp_path, *argv, **extra):
    return subprocess.run([sys.executable, "-m", WRITER, *argv],
                          capture_output=True, text=True, encoding="utf-8", check=False, env=_env(tmp_path, **extra))


def test_no_subcommand_is_a_usage_error(tmp_path):
    """argparse already exits 2 for a missing required flag; printing help must agree."""
    assert _run(tmp_path).returncode == 2


def test_missing_session_id_is_a_usage_error(tmp_path):
    assert _run(tmp_path, "write").returncode == 2


def test_a_good_write_exits_0(tmp_path):
    """The control. Without it, an exit code of 3 everywhere would satisfy the test below."""
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p", "--domain", "d")
    assert result.returncode == 0, result.stderr[-400:]
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert Path(payload["latest"]).is_file() and payload["latest"] == payload["markdown"]   # R10


def test_an_unusable_markdown_dir_exits_3_and_still_keeps_the_record(tmp_path):
    """`gates.md`: nothing may stand between work the session produced and its persistence.

    The spool write happens before the mirror. A mirror directory that cannot be created
    used to raise NotADirectoryError out of main() — exit 1, a traceback, and a session
    that looks lost even though its record is on disk.
    """
    # "/dev/null/deep" was the first form of this and only fails on POSIX: on Windows that
    # is an ordinary missing path, mkdir succeeds, and the test asserted 3 against a real 0.
    # A regular file as the parent is unusable on both.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    result = _run(tmp_path, "write", "--session-id", "probe", "--project", "p",
                  "--domain", "d", "--markdown-dir", str(blocker / "deep"))
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
    # A create refused for every name, so no -2 rescues the md; main() is the real one.
    refuse_md = ("import sys; from h2t_ops.core import store\n"
                 "def refuse(path, *a, **k): raise store.WriteRefused(f'{path}: refused')\n"
                 "store.create = refuse\n"
                 "from h2t_ops.lifecycle.handoff import main; sys.argv[0] = 'h2t-handoff'; main()\n")
    result = subprocess.run(
        [sys.executable, "-c", refuse_md, "write", "--session-id", "probe", "--project", "p",
         "--domain", "d", "--markdown-dir", str(mirror)],
        capture_output=True, text=True, encoding="utf-8", check=False, env=_env(tmp_path))
    assert result.returncode == 3, (result.returncode, result.stderr[-300:])
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    assert payload["mirror_write_failed"] is True
    assert payload["markdown"] == payload["latest"] == ""   # R10: no latest.json to fall back on


def test_an_os_error_on_the_md_also_exits_3(tmp_path):
    """The md is the whole mirror now (R10). An OSError from its write — the shape the old
    latest.json.tmp directory produced, IsADirectoryError out of main() with the spool on
    disk — must come back as _degraded, exit 3, no traceback."""
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    refuse_md = ("import sys; from h2t_ops.core import store\n"
                 "def refuse(path, *a, **k): raise IsADirectoryError(21, 'Is a directory', str(path))\n"
                 "store.create = refuse\n"
                 "from h2t_ops.lifecycle.handoff import main; sys.argv[0] = 'h2t-handoff'; main()\n")
    result = subprocess.run(
        [sys.executable, "-c", refuse_md, "write", "--session-id", "probe", "--project", "p",
         "--domain", "d", "--markdown-dir", str(mirror)],
        capture_output=True, text=True, encoding="utf-8", check=False, env=_env(tmp_path))
    assert result.returncode == 3, (result.returncode, result.stderr[-300:])
    assert "Traceback" not in result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "degraded"
    assert payload["mirror_error"].startswith("IsADirectoryError")
    spool = Path(payload["spool"])
    assert spool.is_file() and "probe" in spool.read_text(encoding="utf-8")
