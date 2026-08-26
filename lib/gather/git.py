"""Git context gathering."""

import re
from pathlib import Path

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
        "hooks_path": ["git", "-C", cwd, "config", "--get", "core.hooksPath"],
        "hooks_tracked": ["git", "-C", cwd, "ls-files", "--", "*hooks/pre-commit"],
    })
    remote = (raw["remote"] or "").strip()
    return {
        "remote": remote,
        "branch": _display_branch(raw["branch"] or "", raw["head"] or ""),
        "log": (raw["log"] or "").strip().splitlines(),
        "status": (raw["status"] or "").strip(),
        "stash": (raw["stash"] or "").strip(),
        "owner_repo": _parse_owner_repo(remote),
        "hooks": _hooks_state(
            cwd,
            (raw["hooks_path"] or "").strip(),
            raw["hooks_tracked"] or "",
        ),
    }


def _hooks_state(cwd: str, configured: str, tracked: str) -> dict:
    """Whether the repo ships a pre-commit hook, and whether git will run it.

    A hook committed to the repo but not wired into the clone is invisible: it
    reports nothing, blocks nothing, and looks exactly like a repo with no hook.
    `scripts/hooks/pre-commit` guarded marketplace.json drift for months while
    `core.hooksPath` was unset on this machine and `.git/hooks` held only samples.
    """
    files = [f.strip() for f in tracked.splitlines() if f.strip()]
    if not files:
        return {"versioned": False, "active": True, "dir": ""}
    root = Path(cwd)
    hook_dir = str(Path(files[0]).parent).replace("\\", "/")
    active = bool(configured) and (root / configured / "pre-commit").exists()
    if not active:
        active = (root / ".git" / "hooks" / "pre-commit").exists()
    return {"versioned": True, "active": active, "dir": hook_dir}


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
