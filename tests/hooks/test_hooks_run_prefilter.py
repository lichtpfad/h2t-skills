"""The wrapper's per-hook prefilter for PostToolUse (spec §2.7: Python only if the hook has work).

plan-closer and new-repo-hint fire on every Bash call. The wrapper leaves before reading any
file unless the payload carries a substring their handlers cannot act without. The filter
must be looser than or equal to the handler, never stricter: a missed trigger silences the
hook with nothing to show for it. So the property is checked against the handlers' own
trigger functions, on every recorded case and on spellings the handlers accept.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from h2t_ops.hooks.new_repo_hint import command_creates_repo
from h2t_ops.hooks.plan_closer import extract_pr_number
from tests.hooks import hook_cases as hc

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "plugins" / "h2t-core" / "hooks" / "run"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not on PATH")

# The handlers' own trigger conditions: the prefilter is judged against these.
ACTS = {
    "plan-closer": lambda command: extract_pr_number(command) is not None,
    "new-repo-hint": command_creates_repo,
}
# Spellings the handlers' regexes accept and a literal substring match might not.
VARIANTS = [
    "gh pr merge 408 --squash", "gh  pr   merge 7", "gh\tpr\tmerge 9", "x; gh pr merge 3",
    "git init", "git -C /tmp/x init", "git  init", "cd x && git\tinit", "(git init)",
    "gh repo create lichtpfad/x", "gh\trepo  create x", "h2t-scaffold-project create --id x",
    "ls -la", "git status", "gh pr view 408", "git commit -m 'gh pr merge 12'",
]


def _commands(name: str) -> list[str]:
    recorded = [hc.load(path)["event"].get("tool_input", {}).get("command", "")
                for hook, _, path in hc.all_cases() if hook == name]
    return [c for c in recorded + VARIANTS if c]


@pytest.fixture
def wrapper(tmp_path):
    home = tmp_path / "home"
    (home / ".h2t" / "run").mkdir(parents=True)
    marker = tmp_path / "started"
    fake = tmp_path / "h2t-hook"
    fake.write_text(f'#!/usr/bin/env bash\ntouch "{marker.as_posix()}"\ncat >/dev/null\n',
                    encoding="utf-8")
    fake.chmod(0o755)
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "release.env").write_text("VERSION=4.0.0\n", encoding="utf-8")
    (home / ".h2t" / "run" / "install.env").write_text(
        f"STATE=ready\nVERSION=4.0.0\nH2T_HOOK={fake.as_posix()}\n", encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": home.as_posix(),
           "CLAUDE_PLUGIN_ROOT": plugin.as_posix()}
    for key in ("SYSTEMROOT", "TEMP", "TMP", "TMPDIR"):
        if key in os.environ:
            env[key] = os.environ[key]

    def started(name: str, command: str) -> bool:
        marker.unlink(missing_ok=True)
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command}, "cwd": tmp_path.as_posix()}
        done = subprocess.run([BASH, RUN.as_posix(), name], input=json.dumps(payload).encode(),
                              capture_output=True, env=env, timeout=30)
        assert done.returncode == 0, done.stderr
        return marker.exists()
    return started


@pytest.mark.parametrize("name", sorted(ACTS))
def test_the_prefilter_passes_every_command_its_handler_acts_on(wrapper, name):
    acting = [c for c in _commands(name) if ACTS[name](c)]
    assert len(acting) >= 3, "control: the case list must contain commands the handler acts on"
    missed = [c for c in acting if not wrapper(name, c)]
    assert not missed, f"{name}: the prefilter stops commands its handler acts on: {missed}"


@pytest.mark.parametrize("name", sorted(ACTS))
def test_an_ordinary_command_starts_no_python(wrapper, name):
    assert not wrapper(name, "ls -la"), f"{name}: h2t-hook started for `ls -la`"


def test_other_hooks_are_not_prefiltered(wrapper):
    """The filter is per name: a Stop or PreToolUse handler must still be started."""
    assert wrapper("grade-guard", "ls -la")
