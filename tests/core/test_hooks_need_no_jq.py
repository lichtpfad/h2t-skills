"""No hook may need jq (D1, #541).

Measured 2026-10-15 on Windows: Git Bash ships no jq, so `gather-on-prompt` failed on every
message (`line 19: jq: command not found`) and the slash path to a session skill never
gathered. The other hook tests skip on Windows, and a POSIX runner has jq, so nothing saw it.

A stub jq on PATH that records any call makes the dependency visible on every OS — a real
jq installed elsewhere cannot hide it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDLERS = REPO_ROOT / "plugins" / "h2t-core" / "hooks-handlers"
PROMPT_HOOK = HANDLERS / "gather-on-prompt"
SKILL_HOOK = HANDLERS / "gather-on-skill"

# A command position: start of line, after a pipe, `$(`, `;`, `&&`, `||`. Mentions in
# comments and `gh … --jq` (gh's own built-in) are not calls to the jq binary.
JQ_CALL = re.compile(r"(^|[|;(&]\s*|\$\(\s*)jq(\s|$)")


def _shell_handlers():
    for path in sorted(HANDLERS.iterdir()):
        if path.is_file() and path.suffix != ".py" and path.read_text(encoding="utf-8").startswith("#!"):
            yield path


def test_no_handler_calls_jq():
    found = []
    for path in _shell_handlers():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
            if JQ_CALL.search(code):
                found.append(f"{path.name}:{n}: {line.strip()}")
    assert list(_shell_handlers()), "found no handlers — the walk, not the tree"
    assert not found, "jq is not on Windows (Git Bash):\n  " + "\n  ".join(found)


pytestmark_posix = pytest.mark.skipif(os.name == "nt", reason="bash wrapper; POSIX only")


@pytest.fixture
def stub_env(tmp_path):
    for candidate in (REPO_ROOT / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidate.is_file() and subprocess.run(
            [str(candidate), "-c", "import yaml"], capture_output=True
        ).returncode == 0:
            interpreter = candidate
            break
    else:
        pytest.skip("no interpreter with PyYAML available")
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    mark = tmp_path / "jq_called"
    jq = stub_bin / "jq"
    jq.write_text(f'#!/bin/sh\necho "$@" >> "{mark}"\nexit 127\n', encoding="utf-8")
    jq.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{stub_bin}{os.pathsep}{env['PATH']}"
    env["H2T_PYTHON"] = str(interpreter)
    env["TMPDIR"] = str(tmp_path / "tmp")
    Path(env["TMPDIR"]).mkdir()
    return env, mark


def _run(hook, env, payload):
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(hook)],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
        cwd=REPO_ROOT, env=env,
    )


@pytestmark_posix
@pytest.mark.parametrize("prompt", ["just a sentence about handoff", "/h2t-core:session-start"])
def test_the_prompt_hook_runs_without_jq(stub_env, prompt):
    env, mark = stub_env
    result = _run(PROMPT_HOOK, env, {"hook_event_name": "UserPromptSubmit", "prompt": prompt,
                                     "cwd": str(REPO_ROOT)})
    assert not mark.exists(), f"jq was called: {mark.read_text()}"
    assert result.returncode == 0, result.stderr
    if prompt.startswith("/"):
        envelope = json.loads(result.stdout)
        assert envelope["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    else:
        assert result.stdout == ""


@pytestmark_posix
def test_the_skill_hook_runs_without_jq(stub_env):
    env, mark = stub_env
    result = _run(SKILL_HOOK, env, {"hook_event_name": "PreToolUse",
                                    "tool_input": {"skill": "h2t-core:session-start"},
                                    "cwd": str(REPO_ROOT)})
    assert not mark.exists(), f"jq was called: {mark.read_text()}"
    assert result.returncode == 0, result.stderr
    assert "systemMessage" in json.loads(result.stdout)
