"""Git context gathering."""

import re
from .runner import run_parallel


def gather_git(cwd: str = ".") -> dict:
    """Gather git repo info: remote, branch, log, status, owner/repo."""
    raw = run_parallel({
        "remote": ["git", "-C", cwd, "remote", "get-url", "origin"],
        "branch": ["git", "-C", cwd, "branch", "--show-current"],
        "log":    ["git", "-C", cwd, "log", "--oneline", "-5"],
        "status": ["git", "-C", cwd, "status", "--short"],
        "stash":  ["git", "-C", cwd, "stash", "list"],
    })
    remote = raw["remote"].strip()
    return {
        "remote": remote,
        "branch": raw["branch"].strip(),
        "log": raw["log"].strip().splitlines(),
        "status": raw["status"].strip(),
        "stash": raw["stash"].strip(),
        "owner_repo": _parse_owner_repo(remote),
    }


def _parse_owner_repo(remote_url: str) -> str:
    """Extract 'owner/repo' from git remote URL."""
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote_url)
    return m.group(1) if m else ""
