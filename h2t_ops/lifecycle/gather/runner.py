"""Core parallel command runner for h2t gather framework."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def _run_one(cmd: list[str], timeout: int = 15) -> str | None:
    """Run a single command, return stdout, or None if the command did not run.

    None and "" are different answers: "" is a command that succeeded with no
    output, None is a timeout, a non-zero exit, or a missing binary. Collapsing
    both into "" let a timed-out `gh issue list` be reported as an empty backlog.
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def run_parallel(
    commands: dict[str, list[str]],
    max_workers: int = 8,
    timeout: int = 15,
) -> dict[str, str | None]:
    """Run multiple commands in parallel, return {name: stdout}.

    Failed or timed-out commands map to None; callers must treat that as an
    unknown answer, not as an empty one.
    """
    results: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_one, cmd, timeout): name
            for name, cmd in commands.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
    return results


def output_json(data: Any) -> None:
    """Write data as JSON to stdout (UTF-8 safe on Windows)."""
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    json.dump(data, out, ensure_ascii=False, indent=2)
    out.write("\n")
    out.flush()
    out.detach()  # don't close underlying buffer
