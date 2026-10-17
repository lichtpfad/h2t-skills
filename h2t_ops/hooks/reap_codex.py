"""SessionEnd hook: reap the Codex app-server broker this session leaked (Windows only).

On Windows the Codex CLI (`@openai/codex`) leaves its `app-server-broker.mjs`
process running after the chat that spawned it ends. Measured on AUTOMATA
2026-09-04: nine broker processes had accumulated over eight days — one per
session — and the oldest was 7.8 days old. One of them held its `--cwd` — a git
worktree that had since been removed — open, so the directory could not be
deleted ("Device or resource busy") until the broker was
killed. The broker is the leak that matters: it is the only Codex process that
records a working directory, and it is the one that pins a directory open.

Mac/Linux do not orphan the broker this way, so this hook is a no-op off
Windows — both the bash wrapper (uname guard) and this script (`sys.platform`)
bail early.

Scope — which brokers this session may kill:

- `session`: the broker whose `--cwd` equals the ending session's cwd. Under the
  house rule that every parallel session works in its own git worktree, that cwd
  is unique to this session, so this is exactly "this chat's own Codex". The one
  case it is not: two chats sharing one working tree (the flagged anti-pattern
  `kraken-parallel-sessions-worktree`). There a sibling's live broker shares the
  cwd and would be killed too — one more reason to keep the worktree discipline,
  not a case this hook can tell apart, because the broker is detached from the
  session's process tree (its parent has already exited — measured), so ancestry
  cannot distinguish them and only the per-session `cxc-<token>`, which lives in
  the Codex plugin and not here, could.
- `orphan`: any broker whose `--cwd` no longer exists on disk. That broker can
  belong to no live session, so killing it is always safe, and it collects the
  historical leaks that a per-session reap would never revisit.

A broker whose cwd exists and differs from this session's is left alone — that is
a live sibling in another worktree.

Only the broker is reaped. The actual app-server pair (`codex.js app-server`
node → `codex.exe app-server`) carries neither a `--cwd` nor the token in its
command line, so it cannot be scoped safely from here; it is expected to shut
down when the broker's pipe closes. If it is later found to survive, that is a
separate, v2 problem — not a reason to widen the kill to processes this hook
cannot attribute to a session.

Exit code is always 0. A SessionEnd hook that errored must never look like a
failed session teardown.

Port of the 3.x hooks-handlers/reap_codex.py, deleted in Task 12a: the functions are the original's (AST-compared until the deletion);
`main()` became `handle()`, and the reply goes out through `h2t_ops.hooks.emit`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from h2t_ops.hooks.emit import Reply

# The broker announces itself with this script name and always carries `--cwd`.
# The app-server pair does not, which is why only the broker is addressable here.
_BROKER_MARK = "app-server-broker"
_CWD_ARG = re.compile(r"--cwd\s+(\S+)")


def _norm(path: str) -> str:
    """Canonical form for comparing two Windows paths.

    Codex writes `--cwd` with forward slashes (`C:/proj`); the SessionEnd
    payload carries the cwd in whatever form the harness used (often `C:\\proj`).
    Compare on unified separators, no trailing slash, case-folded — Windows
    paths are case-insensitive.
    """
    return path.replace("\\", "/").rstrip("/").casefold()


def select_targets(brokers, session_cwd, path_exists):
    """Pick the brokers to kill. Pure, so it is the part under test.

    `brokers` is a list of ``{"pid": int, "cwd": str}``. `path_exists` is
    injected (`os.path.isdir` in production) so a test never touches the disk.
    Returns ``{"pid", "cwd", "reason"}`` dicts; reason is ``"session"`` or
    ``"orphan"``.
    """
    scwd = _norm(session_cwd) if session_cwd else None
    targets = []
    for b in brokers:
        cwd = (b.get("cwd") or "").strip()
        if not cwd:
            # No working directory to reason about — cannot attribute or clear it.
            continue
        if scwd is not None and _norm(cwd) == scwd:
            targets.append({"pid": b["pid"], "cwd": cwd, "reason": "session"})
        elif not path_exists(cwd):
            targets.append({"pid": b["pid"], "cwd": cwd, "reason": "orphan"})
    return targets


def _list_brokers():
    """Enumerate live Codex broker processes as ``{"pid", "cwd"}`` (Windows).

    Reads the process list through PowerShell CIM because the broker's `--cwd`
    lives in its command line, which `tasklist` does not print. Any failure
    yields an empty list — reaping is best effort.
    """
    ps = (
        "Get-CimInstance Win32_Process "
        "| Where-Object { $_.CommandLine -match 'app-server-broker' } "
        "| ForEach-Object { [pscustomobject]@{ pid = $_.ProcessId; cmd = $_.CommandLine } } "
        "| ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0 or not out.stdout.strip():
        return []
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return []
    # ConvertTo-Json emits a bare object for a single match, a list for many.
    if isinstance(data, dict):
        data = [data]
    brokers = []
    for row in data:
        cmd = row.get("cmd") or ""
        if _BROKER_MARK not in cmd:
            continue
        m = _CWD_ARG.search(cmd)
        if not m:
            continue
        brokers.append({"pid": int(row["pid"]), "cwd": m.group(1)})
    return brokers


def _kill(pid: int) -> bool:
    """Kill a broker and any children it owns. Best effort, never raises."""
    try:
        r = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _session_cwd(payload: dict) -> str:
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def summary(killed: list[dict]) -> str:
    own = sum(1 for t in killed if t["reason"] == "session")
    orphan = sum(1 for t in killed if t["reason"] == "orphan")
    parts = []
    if own:
        parts.append(f"{own} этой сессии")
    if orphan:
        parts.append(f"{orphan} осиротевш(их) (мёртвая cwd)")
    return "codex-reaper: убито брокеров — " + ", ".join(parts)


def handle(event: dict) -> Reply:
    # Windows-only: the leak this addresses does not happen elsewhere, and both
    # PowerShell and taskkill are Windows tools. 3.x guarded twice (uname in bash, then
    # sys.platform); without the bash layer this is the one guard, and it comes first.
    if sys.platform != "win32":
        return Reply()

    session_cwd = _session_cwd(event)

    targets = select_targets(_list_brokers(), session_cwd, os.path.isdir)
    if not targets:
        return Reply()

    killed = [t for t in targets if _kill(t["pid"])]
    if not killed:
        return Reply()
    return Reply(summary(killed))
