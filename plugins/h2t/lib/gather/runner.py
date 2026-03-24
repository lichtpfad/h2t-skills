"""Core parallel command runner for h2t gather framework."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def _run_one(cmd: list[str], timeout: int = 15) -> str:
    """Run a single command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def run_parallel(
    commands: dict[str, list[str]],
    max_workers: int = 8,
    timeout: int = 15,
) -> dict[str, str]:
    """Run multiple commands in parallel, return {name: stdout}.

    Failed or timed-out commands return empty string.
    """
    results: dict[str, str] = {}
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
    """Write data as JSON to stdout."""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
