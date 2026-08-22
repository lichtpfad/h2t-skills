"""Git context gathering."""

import re
from .runner import run_parallel


def gather_git(cwd: str = ".") -> dict:
    """Gather git repo info: remote, branch, log, status, owner/repo."""
    raw = run_parallel({
        "remote": ["git", "-C", cwd, "remote", "get-url", "origin"],
        "branch": ["git", "-C", cwd, "branch", "--show-current"],
        "head":   ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
        "log":    ["git", "-C", cwd, "log", "--oneline", "-5"],
        "status": ["git", "-C", cwd, "status", "--short"],
        "stash":  ["git", "-C", cwd, "stash", "list"],
    })
    remote = (raw["remote"] or "").strip()
    return {
        "remote": remote,
        "branch": _display_branch(raw["branch"] or "", raw["head"] or ""),
        "log": (raw["log"] or "").strip().splitlines(),
        "status": (raw["status"] or "").strip(),
        "stash": (raw["stash"] or "").strip(),
        "owner_repo": _parse_owner_repo(remote),
    }


def _display_branch(branch: str, head: str) -> str:
    """Return a non-empty branch label, including detached CI checkouts."""
    branch_name = branch.strip()
    if branch_name:
        return branch_name
    short_head = head.strip()
    return f"detached:{short_head}" if short_head else "detached"


def _parse_owner_repo(remote_url: str) -> str:
    """Extract 'owner/repo' from git remote URL."""
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote_url)
    return m.group(1) if m else ""
