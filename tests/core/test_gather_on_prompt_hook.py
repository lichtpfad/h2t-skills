"""The slash path to a session skill must still gather (#378 follow-up).

`PreToolUse: Skill` covers only one of the two ways a skill is invoked. Measured
2026-08-22 with a dump hook in a fresh headless session:

    plain text "сделай handoff"  -> Skill tool called, PreToolUse fires
    "/h2t-core:dev-overview"     -> UserPromptSubmit only, Skill dumper stays silent

So the accurate user — the one who types the slash command — was the only one whose
gather never ran, silently, from 14e2b42 until now.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers" / "gather-on-prompt"
SKILL_HOOK = REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers" / "gather-on-skill"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="bash wrapper; POSIX only")


@pytest.fixture
def hook_env(tmp_path):
    """A deterministic interpreter and a private TMPDIR so the 30s dedup lock is fresh."""
    for candidate in (REPO_ROOT / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidate.is_file() and subprocess.run(
            [str(candidate), "-c", "import yaml"], capture_output=True
        ).returncode == 0:
            interpreter = candidate
            break
    else:
        pytest.skip("no interpreter with PyYAML available")

    env = dict(os.environ)
    env["H2T_PYTHON"] = str(interpreter)
    env["TMPDIR"] = str(tmp_path / "tmp")
    Path(env["TMPDIR"]).mkdir(parents=True)
    return env


def _run_hook(env, prompt, cwd=REPO_ROOT, field="prompt"):
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(HOOK)],
        input=json.dumps(
            {"hook_event_name": "UserPromptSubmit", field: prompt, "cwd": str(cwd)}
        ),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def _context(result):
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "systemMessage" not in payload, (
        "systemMessage is the user-visible TUI channel; the model reads additionalContext"
    )
    specific = payload["hookSpecificOutput"]
    assert specific["hookEventName"] == "UserPromptSubmit"
    return specific["additionalContext"]


@pytest.mark.parametrize(
    "prompt",
    ["/h2t-core:session-start", "/session-start", "  /h2t-core:session-start  "],
)
def test_slash_session_start_gathers(hook_env, prompt):
    assert "BRIEFING:" in _context(_run_hook(hook_env, prompt))


def test_slash_init_project_gets_init_data(hook_env, tmp_path):
    context = _context(_run_hook(hook_env, "/h2t-core:init-project", cwd=tmp_path))
    assert context.startswith("INIT_DATA:")


def test_user_prompt_field_is_also_accepted(hook_env):
    """plugin-dev docs say `user_prompt`, the shipped warp hook reads `.prompt`."""
    assert "BRIEFING:" in _context(
        _run_hook(hook_env, "/h2t-core:session-start", field="user_prompt")
    )


@pytest.mark.parametrize(
    "prompt",
    [
        "сделай handoff",
        "давай обсудим, почему session-start молчит",
        "/h2t-core:dev-overview",
        "<task-notification>\n<output-file>/tmp/handoff/x.output</output-file>",
        "смотри /tmp/session-start.log",
    ],
)
def test_non_invocations_are_ignored(hook_env, prompt):
    """Anchored match. Plain text already reaches gather-on-skill via the Skill tool,
    and UserPromptSubmit also fires for harness messages carrying these words in paths.
    """
    result = _run_hook(hook_env, prompt)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_skill_tool_path_still_uses_the_tui_channel(hook_env):
    """PreToolUse is not a UserPromptSubmit; do not change the channel underneath it."""
    result = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(SKILL_HOOK)],
        input=json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_input": {"skill": "h2t-core:session-start"},
                "cwd": str(REPO_ROOT),
            }
        ),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=hook_env,
    )
    assert result.returncode == 0, result.stderr
    assert "BRIEFING:" in json.loads(result.stdout)["systemMessage"]


def test_both_entrypoints_are_registered():
    config = json.loads(
        (REPO_ROOT / "plugins" / "h2t-core" / "hooks" / "hooks.json").read_text()
    )["hooks"]
    assert "gather-on-prompt" in json.dumps(config["UserPromptSubmit"])
    skill_matchers = [e for e in config["PreToolUse"] if e.get("matcher") == "Skill"]
    assert "gather-on-skill" in json.dumps(skill_matchers)


def test_resolver_failure_reaches_the_model_on_the_slash_path(hook_env, tmp_path):
    """codex review, 2026-08-22: the early exit kept the old envelope.

    On a machine with no PyYAML interpreter the hook returns before emit() exists, so the
    envelope is hand-written there — and it used `systemMessage`, the TUI channel. The
    slash user was then told nothing the model could act on.
    """
    # Shadow every interpreter the resolver probes rather than emptying PATH: the hook
    # still needs jq, cat and friends, and "python exists but the probe fails" is the
    # real shape of the failure (an interpreter without PyYAML).
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name in ("python3", "python", "py"):
        stub = fake_bin / name
        stub.write_text("#!/bin/sh\nexit 1\n")
        stub.chmod(0o755)
    env = dict(hook_env)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(tmp_path)          # no ~/.h2t/venv either
    env["H2T_PYTHON"] = str(fake_bin / "python3")

    result = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(HOOK)],
        input=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "prompt": "/h2t-core:session-start",
                "cwd": str(REPO_ROOT),
            }
        ),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "systemMessage" not in payload
    assert "GATHER_ERROR" in payload["hookSpecificOutput"]["additionalContext"]
