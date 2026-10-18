"""gather-on-skill (PreToolUse: Skill) and gather-on-prompt (UserPromptSubmit).

The hook is the executor on purpose. 672249e (2026-03-25) moved gathering out of the
model's hands — "Closes #12 — gather.py can no longer be ignored by Claude". Do not
replace this with an instruction telling the agent to run something itself.

Two entry paths, one implementation (.claude/rules/hooks.md). Plain text such as
"сделай handoff" calls the Skill tool, so PreToolUse fires with `tool_input.skill`. The
slash form `/h2t-core:session-start` is expanded into the prompt by the harness and no
Skill call happens (measured 2026-08-22), so only UserPromptSubmit sees it. The prompt
path is anchored to a leading slash: UserPromptSubmit also fires for harness messages —
a <task-notification> carries paths that contain "handoff" — and for any sentence that
merely discusses the skills.

Port of the 3.x bash handlers. Gone with the port: the interpreter lookup, and the
PyYAML-missing error, which this package cannot hit. Kept: the per-skill, per-cwd 30 s
lock written only after a successful run, and the GATHER_ERROR / INIT_ERROR texts.
New (spec §6.3): the briefing's GATHER_META JSON carries `cwd` and `at`, so a skill can
tell a briefing for this directory, made just now, from a stale or foreign one.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from h2t_ops.hooks.emit import Reply

_SKILLS = ("session-start", "handoff", "init-project")
_SLASH = re.compile(
    r"\s*/((?:[A-Za-z0-9_.-]+:)?(?:session-start|handoff|init-project))(?:\s|$)")
LOCK_SECONDS = 30
_STDERR_TAIL = 500  # bytes, as `tail -c 500` cut it
_META_SEP = "\n\nGATHER_META: "
_NO_OUTPUT = ("GATHER_ERROR: h2t gather returned no output. Run /h2t-core:setup doctor, "
              "or reinstall the CLI with uv tool install.")


def _event_name(event: dict) -> str:
    name = event.get("hook_event_name")
    if name:
        return str(name)
    return "UserPromptSubmit" if ("prompt" in event or "user_prompt" in event) else "PreToolUse"


def _slash_skill(event: dict) -> str:
    prompt = event.get("prompt") or event.get("user_prompt") or ""
    m = _SLASH.match(prompt) if isinstance(prompt, str) else None
    return m.group(1) if m else ""


def _skill(event: dict) -> str:
    if _event_name(event) == "UserPromptSubmit":
        return _slash_skill(event)
    skill = (event.get("tool_input") or {}).get("skill") or ""
    return skill if isinstance(skill, str) else ""


def _lock_file(skill: str, cwd: str) -> Path:
    # Imported here: a Skill call for any other skill returns before this (spec §2.7).
    from h2t_ops.core import paths

    # Keyed by cwd as well as skill, so a run in one repo cannot silence another.
    key = re.sub(r"[/:]", "_", skill) + "_" + hashlib.sha1(cwd.encode("utf-8", "replace")).hexdigest()[:12]
    # In state, not tmp: tmp is only store.scratch(), removed on exit, so it cannot hold a
    # lock from one hook process to the next (plan R23).
    return paths.state_dir() / "locks" / f"gather-{key}.lock"


def _locked(lock: Path, now: int) -> bool:
    try:
        then = int(lock.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return False
    return now - then < LOCK_SECONDS


def _write_lock(lock: Path, now: int) -> None:
    from h2t_ops.core import store
    from h2t_ops.core.errors import H2TError

    try:
        store.replace(lock, f"{now}\n", place="state")
    except (OSError, H2TError) as exc:
        # A missing lock costs one duplicate gather, never the briefing; it is said, not
        # swallowed (hooks.md).
        print(f"h2t gather: lock not written: {exc}", file=sys.stderr)


def _tail(raw: bytes) -> str:
    # `$(tail -c 500 …)`: the last 500 bytes, trailing newlines dropped. A cut through a
    # UTF-8 character becomes U+FFFD, never a lone surrogate (#453).
    return raw[-_STDERR_TAIL:].decode("utf-8", "replace").rstrip("\n")


def _detect_project(cwd: str, at: str) -> str:
    """INIT_DATA for init-project: its SKILL.md step 1 reads detection, not a briefing.

    In-process since detect_project moved into the package (Task 12). The JSON carries
    `cwd` and `at` as GATHER_META does, so the skill can apply the same freshness rule and
    run `h2t-detect-project` itself when the data is stale or for another directory.
    """
    from h2t_ops.lifecycle.detect_project import detect_project

    try:
        result = detect_project(cwd)
    except Exception as exc:  # detection crashing is an INIT_ERROR, not a hook failure
        return f"INIT_ERROR: h2t-detect-project failed. {type(exc).__name__}: {exc}"
    result["cwd"] = cwd
    result["at"] = at
    return "INIT_DATA: " + json.dumps(result, ensure_ascii=False, indent=2)


def _run_gather(cwd: str) -> tuple[int, str, bytes]:
    """`h2t-gather --cwd <cwd> --briefing-only`, in-process: (rc, stdout, stderr).

    The gather code writes through `sys.stdout.buffer`; both streams are swapped for
    byte buffers for the call, so nothing it prints can reach the hook's own stdout,
    which carries only the envelope. Its subprocesses capture their output (runner.py).
    """
    from h2t_ops.lifecycle import run_main, session_start

    out, err = io.BytesIO(), io.BytesIO()
    wrappers = (io.TextIOWrapper(out, encoding="utf-8", newline=""),
                io.TextIOWrapper(err, encoding="utf-8", errors="replace", newline=""))
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = wrappers
    try:
        rc = run_main(session_start.main, "h2t-gather", ["--cwd", cwd, "--briefing-only"])
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:  # the script crashing is a GATHER_ERROR, not a hook failure
        wrappers[1].write(f"{type(exc).__name__}: {exc}\n")
        rc = 1
    finally:
        sys.stdout, sys.stderr = saved
        for wrapper in wrappers:
            wrapper.flush()
            wrapper.detach()  # a collected wrapper would close the buffer under it
    return rc, out.getvalue().decode("utf-8", "replace").rstrip("\n"), err.getvalue()


def stamp_meta(briefing: str, cwd: str, at: str) -> str:
    """Put `cwd` and `at` into the GATHER_META JSON (spec §6.3).

    Inside the JSON, not as `cwd=… at=…` text: session-start parses the line as JSON
    (`GATHER_META.project`, `.sessions`, `.machine`), and a second format would break it.
    A briefing without a parseable meta object is passed through unchanged.
    """
    head, sep, raw = briefing.rpartition(_META_SEP)
    if not sep:
        return briefing
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError:
        return briefing
    if not isinstance(meta, dict):
        return briefing
    meta["cwd"] = cwd
    meta["at"] = at
    return head + _META_SEP + json.dumps(meta, ensure_ascii=False)


def handle(event: dict) -> Reply:
    """gather-on-skill: both payload shapes — tool_input.skill, or a slash prompt."""
    skill = _skill(event)
    if not any(s in skill for s in _SKILLS):
        return Reply()
    cwd = event.get("cwd") or "."
    cwd = cwd if isinstance(cwd, str) else "."

    lock = _lock_file(skill, cwd)
    now = int(time.time())
    if _locked(lock, now):
        return Reply()

    if "init-project" in skill:
        text = _detect_project(cwd, datetime.now().astimezone().isoformat(timespec="seconds"))
        if text.startswith("INIT_DATA:"):
            _write_lock(lock, now)
        return Reply(text)

    rc, out, err = _run_gather(cwd)
    if rc != 0:
        return Reply(f"GATHER_ERROR: h2t-gather failed. {_tail(err) or 'no stderr'}")
    if not out:
        return Reply(_NO_OUTPUT)
    _write_lock(lock, now)
    return Reply(stamp_meta(out, cwd, datetime.now().astimezone().isoformat(timespec="seconds")))


def handle_prompt(event: dict) -> Reply:
    """gather-on-prompt: only a prompt that opens with a session-skill slash command."""
    if not _slash_skill(event):
        return Reply()
    return handle(event)
