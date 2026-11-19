"""Register a social process in Windows Task Scheduler (`schtasks`)."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys

from h2t_ops.core.errors import ConfigError, ProviderError, UsageError

TASK_PREFIX = "h2t-social-"
PROCESSES = ("insights",)

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def command(process: str) -> list[str]:
    return [shutil.which("h2t-ops"), "social", "run", process, "--trigger", "schedule", "--store"]


def _check(process: str, platform: str) -> str:
    if process not in PROCESSES:
        raise UsageError(f"unknown process {process!r}; available: {', '.join(PROCESSES)}")
    if platform != "win32":
        raise UsageError("schedule uses Windows Task Scheduler; cron comes at the VPS stage")
    return TASK_PREFIX + process


def _call(runner, argv: list[str]) -> None:
    result = runner(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProviderError(f"schtasks failed ({result.returncode}): {(result.stderr or '').strip()}")


def add(process: str, daily: str, runner=subprocess.run, platform: str = sys.platform) -> dict:
    task = _check(process, platform)
    if not _TIME.match(daily or ""):
        raise UsageError(f"--daily must be HH:MM (00:00-23:59), got {daily!r}")
    argv = command(process)
    if argv[0] is None:
        raise ConfigError("h2t-ops is not on PATH; install it (uv tool install) before scheduling")
    tr = subprocess.list2cmdline(argv)
    _call(runner, ["schtasks", "/Create", "/TN", task, "/TR", tr, "/SC", "DAILY", "/ST", daily, "/F"])
    return {"task": task, "command": tr, "daily": daily}


def remove(process: str, runner=subprocess.run, platform: str = sys.platform) -> dict:
    task = _check(process, platform)
    _call(runner, ["schtasks", "/Delete", "/TN", task, "/F"])
    return {"task": task}
