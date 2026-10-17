"""`h2t-setup sync`: the executor of the target release (spec §7.3.2) and the steps after it.

Only the target's own code, run from an isolated `uvx`, may bring an install to the target:
an older executor does not know the newer steps, and one running from the installed tool's
environment would be replacing the environment it runs from.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import h2t_ops
from h2t_ops.core.errors import ConfigError
from h2t_ops.setup import state
from h2t_ops.setup.manifest import render
from h2t_ops.setup.version_check import inside

# Set to the target version before the re-launch. If the process it starts is still not the
# target, the release's bootstrap does not produce its own version, and launching it again
# would loop forever.
RELAUNCH_ENV = "H2T_SETUP_RELAUNCHED_FOR"
# Read at call time, so a test can choose the branch without changing os.name for everyone.
OS_NAME = os.name


def uv_tool_root(which=shutil.which, run=subprocess.run) -> str | None:
    """The `h2t-ops` directory under `uv tool dir`, if there is one: a 3.x install has no
    install.json, and its executor must still count as the installed tool."""
    uv = which("uv")
    if not uv:
        return None
    try:
        done = run([uv, "tool", "dir"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    root = Path(done.stdout.strip()) / "h2t-ops"
    return str(root) if root.is_dir() else None


def installed_tool_root(detect=None) -> str | None:
    install = state.read()
    if install is not None and install.tool_root:
        return install.tool_root
    return (detect or uv_tool_root)()


def receipt_editable(tool_root: str | None = None) -> str | None:
    """The checkout an install without install.json (3.x) is editable from, per uv's receipt.

    uv records `[tool] requirements = [{ name = "h2t-ops", editable = "<path>" }]`; a wheel or
    git install has no `editable` key there."""
    root = tool_root or uv_tool_root()
    if not root:
        return None
    try:
        data = tomllib.loads((Path(root) / "uv-receipt.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):  # TOMLDecodeError and UnicodeDecodeError are ValueError
        return None
    tool = data.get("tool")
    requirements = tool.get("requirements") if isinstance(tool, dict) else None
    for req in requirements if isinstance(requirements, list) else []:
        if isinstance(req, dict) and req.get("name") == "h2t-ops":
            editable = req.get("editable")
            return editable if isinstance(editable, str) and editable else None
    return None


def relaunch_command(target: dict, mode: str, argv: list[str]) -> list[str]:
    """The frozen word order (§7.3.2): the mode is the first word after the bootstrap, the
    original arguments follow it."""
    return list(target["bootstrap"]) + [mode] + list(argv)


def ensure_executor(target: dict, mode: str, argv: list[str], *, prefix: str | None = None,
                    version: str | None = None, tool_root: str | None = None,
                    execvp=None, os_name: str | None = None, spawn=None,
                    detect_tool_root=None) -> None:
    """Return if this process may act for `target`; otherwise hand over to its bootstrap.

    Continues only when this is the target version AND `prefix` lies outside the installed
    tool. Otherwise runs `relaunch_command`: the same mode and arguments, so `update` stays
    `update` (§7.3.2). POSIX replaces the process with `execvp`.

    Windows has no real exec. From outside the installed tool (an older isolated executor)
    the bootstrap runs as a child and its exit code becomes ours. From inside it (the
    installed h2t-setup started to repair itself) nothing is spawned: the waiting parent
    would hold the very environment the reinstall must delete, and Windows locks it. That
    case stops with ConfigError (exit 3, reason `relaunch_required`) whose hint is the exact
    command to run from a terminal.
    """
    prefix = sys.prefix if prefix is None else prefix
    version = h2t_ops.__version__ if version is None else version
    if tool_root is None:
        tool_root = installed_tool_root(detect=detect_tool_root)
    from_tool = bool(tool_root) and inside(prefix, tool_root)
    if version == target["version"] and not from_tool:
        # The marker scopes one re-launch; a child this run starts must not inherit it.
        os.environ.pop(RELAUNCH_ENV, None)
        return
    if os.environ.get(RELAUNCH_ENV) == target["version"]:
        raise ConfigError(
            f"the bootstrap of {target['version']} started h2t-setup {version} "
            f"from {prefix}; it does not reach its own release",
            hint="the release manifest is inconsistent; report it with h2t-core:report-issue")
    command = relaunch_command(target, mode, argv)
    windows = (os_name or OS_NAME) == "nt"
    if windows and from_tool:
        raise ConfigError(
            f"h2t-setup {version} runs from the installed tool {tool_root}, which the update "
            "replaces and Windows keeps locked while this process lives; run the command in "
            "the hint from a terminal",
            hint=render(command),
            details={"reason": "relaunch_required", "command": command})
    os.environ[RELAUNCH_ENV] = target["version"]
    if windows:
        done = (spawn or subprocess.run)(command)
        raise SystemExit(done.returncode)
    (execvp or os.execvp)(command[0], command)


def run(mode: str, target: dict | None, argv: list[str]):
    """Steps 3–8 of §7.3 (snapshot, CLI, plugins, Codex, cache, report) and dev-sync (§7.4).

    A stub: Task 15 replaces it. It raises rather than reporting success, so nobody reads
    a run that did nothing as a run that converged."""
    raise NotImplementedError(
        f"h2t-setup {mode}: the steps after the executor are not implemented yet (Task 15)")
