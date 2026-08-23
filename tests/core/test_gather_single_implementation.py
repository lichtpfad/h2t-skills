"""`h2t-ops gather` and `h2t-gather` must be the same program.

They were not: h2t-ops routed to lib/cli/main.py, which never gained
find_latest_session_index, so its briefing silently lacked "### Previous Session".
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


# h2t_ops.gather_entry defines main() with no `if __name__ == "__main__"` guard, so
# `python -m h2t_ops.gather_entry` imports it, runs nothing, and exits 0 with empty output
# — a broken probe that reads exactly like "produced no briefing". Call main() instead.
_ENTRY = ("import sys; sys.argv = ['h2t-gather', *sys.argv[1:]]; "
          "from h2t_ops.gather_entry import main; sys.exit(main())")


def _without_timing(text):
    return re.sub(r'"gather_ms":\s*\d+', '"gather_ms": N', text)


def _run(argv):
    env = dict(os.environ, H2T_EVALS_MODE="off")
    return subprocess.run([sys.executable, "-m", *argv], capture_output=True,
                          text=True, cwd=ROOT, env=env, check=False)


def _run_gather_entry(*args):
    env = dict(os.environ, H2T_EVALS_MODE="off")
    return subprocess.run([sys.executable, "-c", _ENTRY, *args], capture_output=True,
                          text=True, cwd=ROOT, env=env, check=False)


def test_the_gather_entry_probe_is_not_silently_empty():
    """Control: without this, an empty h2t-gather side would look like agreement."""
    result = _run_gather_entry("--cwd", str(ROOT), "--briefing-only")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("BRIEFING:"), result.stdout[:200]


def _session_store(tmp_path, work, env):
    """A session store of the test's own, holding one previous session.

    The block under test only renders when a `latest.json` exists for the resolved project,
    so asserting on this machine's real ~/.h2t/sessions made the test a statement about the
    developer's history: green here, red on a CI runner that has none. The store is built
    from the project id gather itself reports, so it lands where the reader will look.
    """
    root = tmp_path / "sessions"
    env = dict(env, H2T_SESSION_ROOT=str(root), H2T_MACHINE_NAME="test-machine")

    probe = subprocess.run(
        [sys.executable, "-c", _ENTRY, "--cwd", str(work), "--briefing-only"],
        capture_output=True, text=True, cwd=ROOT, env=env, check=False,
    )
    assert probe.returncode == 0, probe.stderr
    meta = json.loads(probe.stdout.split("\n\nGATHER_META: ", 1)[1])
    project = meta["project"]["id"]

    directory = root / "test-machine" / project
    directory.mkdir(parents=True)
    (directory / "latest.json").write_text(json.dumps({
        "version": 1,
        "session_id": "prior-session-2026-08-22",
        "project": project,
        "domain": meta["project"].get("domain", "dev"),
        "updated_at": "2026-08-22T10:00:00+00:00",
        "summary_short": "the session before this one",
        "next_actions": ["carry on"],
        "blockers": [],
        "artifacts": [],
        "markdown_path": str(directory / "prior-session-2026-08-22.md"),
    }), encoding="utf-8")
    return env


def test_both_entry_points_produce_the_same_briefing(tmp_path):
    """A directory outside git on purpose: no live source, no flake.

    Pointed at this repo, the briefing calls out to `gh` on every run, and two consecutive
    runs genuinely disagree — one session's handoff recorded exactly that, the first run
    timing out on every gh call (gather_ms 15110 == runner._run_one's cap) and the second
    listing 20 issues. Comparing two live runs byte for byte would make this test flake in
    CI. What it is here to check is that the two entry points execute the same code.
    """
    work = tmp_path / "checkout"
    work.mkdir()
    env = _session_store(tmp_path, work, dict(os.environ, H2T_EVALS_MODE="off"))

    via_ops = subprocess.run(
        [sys.executable, "-m", "h2t_ops.cli", "gather", "session-start",
         "--cwd", str(work), "--briefing-only"],
        capture_output=True, text=True, cwd=ROOT, env=env, check=False)
    via_gather = subprocess.run(
        [sys.executable, "-c", _ENTRY, "--cwd", str(work), "--briefing-only"],
        capture_output=True, text=True, cwd=ROOT, env=env, check=False)

    assert via_ops.returncode == 0, via_ops.stderr
    assert via_gather.returncode == 0, via_gather.stderr
    assert "### Previous Session" in via_ops.stdout, (
        "the h2t-ops side lost the block the second implementation never had"
    )
    # gather_ms is a wall-clock measurement of the run itself; two runs cannot share it.
    assert _without_timing(via_ops.stdout) == _without_timing(via_gather.stdout)


def test_missing_skill_still_exits_2():
    result = _run(["h2t_ops.cli", "gather"])
    assert result.returncode == 2, (result.returncode, result.stdout[:200])
    assert "requires a skill name" in result.stderr


def test_a_leading_flag_is_not_eaten_as_the_skill():
    """`h2t-ops gather --cwd X` has no skill; --cwd must not be consumed as one."""
    result = _run(["h2t_ops.cli", "gather", "--cwd", str(ROOT), "--briefing-only"])
    assert result.returncode == 2, (result.returncode, result.stdout[:200])
    assert "requires a skill name" in result.stderr


def test_options_may_precede_the_skill():
    """argparse accepts the optional positional anywhere; hand-rolled slicing did not.

    `h2t-ops gather --cwd /tmp session-start --format-briefing` parsed to
    skill='session-start' under the legacy parser — measured against a reconstruction of
    lib/cli/main.py's subparser before it was deleted.
    """
    result = _run(["h2t_ops.cli", "gather", "--cwd", str(ROOT),
                   "session-start", "--briefing-only"])
    assert result.returncode == 0, (result.returncode, result.stderr[:300])
    assert result.stdout.startswith("BRIEFING:"), result.stdout[:200]


def test_an_unrecognised_skill_is_still_accepted():
    """Legacy never validated the name; this task does not start."""
    result = _run(["h2t_ops.cli", "gather", "nosuch-skill",
                   "--cwd", str(ROOT), "--briefing-only"])
    assert result.returncode == 0, result.stderr
    assert "BRIEFING:" in result.stdout
