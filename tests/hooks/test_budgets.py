"""Per-event time budgets through the real wrapper (spec §2.7): warm runs, p95 of 20.

Each run is `bash plugins/h2t-core/hooks/run <name>` with an `install.env` under a
temporary HOME whose `H2T_HOOK` is this environment's `h2t-hook` — the console script next
to `sys.executable`, so CI's `pip install -e .` and a local venv are measured alike. The
plugin root is the checkout's plugins/h2t-core, and install.env carries its release.env
VERSION, so the wrapper takes the "versions equal" path and runs the handler.

Bounds: the spec's on macOS and Linux; four times that under `CI` (shared runners);
measured only on Windows, whose threshold waits for Task 2. `pytest -s` prints the p95.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "h2t-core"
RUN = PLUGIN / "hooks" / "run"
BASH = shutil.which("bash")
RUNS = 20
WINDOWS = sys.platform == "win32"
CI = bool(os.environ.get("CI"))


def _h2t_hook() -> str | None:
    bindir = Path(sys.executable).parent
    for candidate in (bindir / "h2t-hook", bindir / "h2t-hook.exe",
                      bindir / "Scripts" / "h2t-hook.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("h2t-hook")


HOOK = _h2t_hook()
pytestmark = [
    pytest.mark.skipif(BASH is None, reason="bash is not on PATH"),
    pytest.mark.skipif(HOOK is None, reason="no h2t-hook console script beside sys.executable"),
]


def _version() -> str:
    for line in (PLUGIN / "release.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION="):
            return line.split("=", 1)[1].strip()
    raise AssertionError("release.env has no VERSION")


@pytest.fixture
def rig(tmp_path):
    home = tmp_path / "home"
    run_dir = home / ".h2t" / "run"
    run_dir.mkdir(parents=True)
    hook = Path(HOOK).as_posix()
    (run_dir / "install.env").write_text(
        f"STATE=ready\nVERSION={_version()}\nH2T_HOOK={hook}\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in ("H2T_CONFIG_ROOT", "H2T_SESSION_ROOT", "H2T_ACTIVITY_SPOOL")}
    env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_PLUGIN_ROOT=PLUGIN.as_posix(),
               TMPDIR=str(tmp_path))
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join([
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Тесты зелёные, задача закрыта. " + "слово " * 30}]}},
            ensure_ascii=False),
    ]) + "\n", encoding="utf-8")

    def once(name: str, payload: dict) -> tuple[float, subprocess.CompletedProcess]:
        data = json.dumps(payload).encode()
        start = time.perf_counter()
        done = subprocess.run([BASH, RUN.as_posix(), name], input=data, capture_output=True,
                              cwd=work, env=env, timeout=60)
        return time.perf_counter() - start, done

    once.transcript = str(transcript)
    once.work = str(work)
    return once


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, int(round(0.95 * len(ordered))) - 1)]


def _measure(rig, entries: list[tuple[str, dict]]) -> tuple[float, list]:
    """One sample = every entry of the event in sequence, as the harness fires them."""
    for name, payload in entries:  # warm-up, and a check that the handler really ran
        _, done = rig(name, payload)
        assert done.returncode in (0, 2), (name, done.returncode, done.stderr[-300:])
        assert b"h2t: CLI" not in done.stdout, f"{name}: the wrapper noticed, it did not run"
    samples, last = [], []
    for _ in range(RUNS):
        total, last = 0.0, []
        for name, payload in entries:
            elapsed, done = rig(name, payload)
            total += elapsed
            last.append(done)
        samples.append(total)
    return _p95(samples), last


def _judge(event: str, p95: float, budget: float) -> None:
    print(f"\nbudget {event}: p95 {p95 * 1000:.1f} ms over {RUNS} runs (budget {budget * 1000:.0f} ms)")
    if WINDOWS:
        return  # measured only: the Windows threshold comes from Task 2
    bound = budget * 4 if CI else budget
    assert p95 <= bound, f"{event}: p95 {p95 * 1000:.1f} ms > {bound * 1000:.0f} ms"


def test_stop_both_guards(rig):
    payload = {"hook_event_name": "Stop", "session_id": "s1", "cwd": rig.work,
               "transcript_path": rig.transcript, "stop_hook_active": False}
    p95, last = _measure(rig, [("grade-guard", payload), ("plain-guard", payload)])
    assert b"systemMessage" in last[0].stdout, "grade-guard must have had work to do"
    _judge("Stop", p95, 0.300)


def test_post_tool_use_both_hooks_with_work(rig):
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": rig.work,
               "tool_input": {"command": "git init"}}
    p95, last = _measure(rig, [("plan-closer", payload), ("new-repo-hint", payload)])
    assert b"init-project" in last[1].stdout, "new-repo-hint must have had work to do"
    _judge("PostToolUse", p95, 0.150)


def test_post_tool_use_both_hooks_with_nothing_to_do(rig):
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": rig.work,
               "tool_input": {"command": "ls -la"}}
    p95, last = _measure(rig, [("plan-closer", payload), ("new-repo-hint", payload)])
    assert [d.stdout for d in last] == [b"", b""]
    _judge("PostToolUse (no work)", p95, 0.150)


def test_session_start(rig):
    payload = {"hook_event_name": "SessionStart", "source": "startup", "session_id": "s1",
               "cwd": rig.work}
    p95, last = _measure(rig, [("inject-h2t-context", payload)])
    assert b"h2t-context" in last[0].stdout
    _judge("SessionStart", p95, 1.0)
