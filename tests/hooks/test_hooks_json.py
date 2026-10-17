"""Every hooks.json entry goes through `hooks/run <name>` with a deliberate timeout (spec §5, §6.1.4).

The command form is fixed: `bash "${CLAUDE_PLUGIN_ROOT}/hooks/run" <name> <t-1>` with
`"timeout": <t>`. The wrapper's own watchdog must fire a second before the harness's,
because a harness timeout throws away everything the hook printed.

The timeout is the second positional argument, not a `VAR=value` prefix: a leading
assignment needs a POSIX shell, and on Windows the shell that runs a `command` hook is not
probed (Claude Code 2.1.301: "PowerShell on Windows without Git Bash"). `bash "<path>" a b`
reads the same in sh, bash, zsh, PowerShell and cmd. Without the argument the wrapper falls
back to 9 s.

Every plugin with a hooks.json carries the same `hooks/run` and a `release.env` whose
VERSION is its plugin.json version (until Task 13 writes one version for all).
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "plugins" / "h2t-core"
PLUGINS = sorted(p for p in (ROOT / "plugins").iterdir() if (p / ".claude-plugin").is_dir())
WITH_HOOKS = [p for p in PLUGINS if (p / "hooks" / "hooks.json").is_file()]
FORM = re.compile(r'^bash "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/run" ([a-z0-9-]+) (\d+)$')

# The harness timeout per hook, in seconds, and why. 3.x set none.
TIMEOUTS = {
    # Local reads only; measured p95 59 ms (Task 9b budgets).
    "inject-h2t-context": 10,
    # gather runs in-process; budget 3 s, measured p95 91 ms. A gather slower than 29 s is
    # broken, and the skills fall back to `h2t-gather` when the briefing is missing (§6.3).
    # The PreToolUse hook holds the Skill call for as long as it runs.
    "gather-on-skill": 30,
    "gather-on-prompt": 30,
    # A guard on every Write/Edit: local checks, milliseconds. A timeout lets the write through.
    "structure-guard": 10,
    # Transcript reads, local; both Stop guards measured p95 122 ms together.
    "grade-guard": 10,
    "plain-guard": 10,
    # `gh pr view` inside has its own 30 s timeout, then the plan edits: 30 + margin.
    "plan-closer": 45,
    # Regex over the command, no I/O beyond the reply.
    "new-repo-hint": 10,
    # Windows only: process listing (30 s cap) and taskkill (15 s cap); elsewhere it returns
    # at once. The harness sizes the whole SessionEnd budget from the largest SessionEnd
    # timeout (max(1.5 s, min(t, 60 s)) in 2.1.301), so 3.x had 1.5 s. 15 s bounds the exit
    # delay while giving a PowerShell listing room.
    "session-end-reap-codex": 15,
}


def entries():
    for plugin in WITH_HOOKS:
        data = json.loads((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        for event, groups in data["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    yield plugin.name, event, hook


def test_there_are_entries_to_check():
    assert len(list(entries())) >= 11


@pytest.mark.parametrize("plugin,event,hook", list(entries()),
                         ids=[f"{p}:{e}:{h['command'][-30:]}" for p, e, h in entries()])
def test_every_entry_has_the_one_form_and_its_timeout(plugin, event, hook):
    match = FORM.match(hook["command"])
    assert match, hook["command"]
    name, inner = match.group(1), int(match.group(2))
    assert hook["type"] == "command"
    assert hook.get("timeout") == TIMEOUTS[name], (name, hook.get("timeout"))
    assert inner == hook["timeout"] - 1, hook


def test_every_timeout_is_used():
    assert {FORM.match(h["command"]).group(1) for _, _, h in entries()} == set(TIMEOUTS)


def test_hooks_run_is_byte_identical_in_every_plugin_with_hooks():
    reference = (CORE / "hooks" / "run").read_bytes()
    assert WITH_HOOKS, "no plugin has a hooks.json — the probe is broken"
    for plugin in WITH_HOOKS:
        assert (plugin / "hooks" / "run").read_bytes() == reference, plugin.name


def test_a_plugin_without_hooks_carries_no_wrapper():
    for plugin in PLUGINS:
        if plugin not in WITH_HOOKS:
            assert not (plugin / "hooks" / "run").exists(), plugin.name


@pytest.mark.parametrize("plugin", WITH_HOOKS, ids=[p.name for p in WITH_HOOKS])
def test_release_env_version_is_the_plugin_json_version(plugin):
    lines = (plugin / "release.env").read_text(encoding="utf-8").splitlines()
    versions = [line.split("=", 1)[1] for line in lines if line.startswith("VERSION=")]
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert versions == [manifest["version"]]


SHELLS = [s for s in ("/bin/sh", "/bin/bash", "/bin/zsh") if Path(s).is_file()]


@pytest.mark.skipif(os.name == "nt" or not SHELLS or shutil.which("bash") is None,
                    reason="the POSIX shells the harness uses")
@pytest.mark.parametrize("shell", SHELLS)
def test_the_command_runs_through_a_posix_shell(shell, tmp_path):
    """The hooks.json command, run the way the harness runs it, reaches the handler, and the
    timeout it names reaches the wrapper's watchdog: with the number lowered to 1 a handler
    that sleeps 30 s is cut off well before that."""
    plugin_name, _, hook = next((p, e, h) for p, e, h in entries() if "plan-closer" in h["command"])
    plugin = ROOT / "plugins" / plugin_name
    version = (plugin / "release.env").read_text(encoding="utf-8").split("=", 1)[1].strip()
    home = tmp_path / "home"
    (home / ".h2t" / "run").mkdir(parents=True)
    fake = tmp_path / "h2t-hook"
    fake.write_text('#!/usr/bin/env bash\ncat >/dev/null\n[ -n "${SLOW:-}" ] && exec sleep 30\n'
                    'printf "%s|%s" "$1" "${2:-}"\n', encoding="utf-8")
    fake.chmod(0o755)
    (home / ".h2t" / "run" / "install.env").write_text(
        f"STATE=ready\nVERSION={version}\nH2T_HOOK={fake}\n", encoding="utf-8")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home),
           "CLAUDE_PLUGIN_ROOT": str(plugin)}
    event = json.dumps({"hook_event_name": "PostToolUse", "tool_input": {"command": "gh pr merge 1"}})
    done = subprocess.run([shell, "-c", hook["command"]], input=event.encode(), env=env,
                          capture_output=True, timeout=30, check=False)
    # The handler gets its name only: the timeout is the wrapper's business.
    assert (done.returncode, done.stdout.decode()) == (0, "plan-closer|"), done.stderr

    assert hook["command"].endswith(" 44")
    started = time.monotonic()
    done = subprocess.run([shell, "-c", hook["command"][:-len("44")] + "1"], input=event.encode(),
                          env={**env, "SLOW": "1"}, capture_output=True, timeout=30, check=False)
    assert time.monotonic() - started < 5, done.stderr
    assert done.returncode == 0 and done.stdout == b"", done
