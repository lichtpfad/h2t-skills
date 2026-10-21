"""Work status per (repo, branch): uncommitted files, merged/pushed state, PR, issues, verdict.

Written to the `branch_status` table. "Merged" is decided by content, not ancestry: a squash
merge leaves the branch looking unmerged (.claude/rules/git.md). Every subprocess has a
timeout, and a failed call yields "" and never an exception.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

TIMEOUT_S = 20

_PR = {"OPEN": "открыт", "MERGED": "влит", "CLOSED": "закрыт"}
_CLOSES = re.compile(r"(?i)\b(?:fixes|closes)\s+#(\d+)")
_ARTIFACT = re.compile(r"issue:(\d+)")


def _run(repo: str, args: list[str]) -> tuple[int, str]:
    """(exit code, stdout) of `git -C repo ...`; (-1, "") when git cannot run or times out."""
    try:
        done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return done.returncode, done.stdout.strip()


def _git(repo: str, *args: str) -> str:
    code, out = _run(repo, list(args))
    return out if code == 0 else ""


def _ok(repo: str, *args: str) -> bool:
    return _run(repo, list(args))[0] == 0


def _gh(repo: str, args: list[str]) -> list | dict | None:
    """Parsed JSON of `gh <args>` run inside the repo; None on any failure."""
    try:
        done = subprocess.run(["gh", *args], cwd=repo, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        return json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def default_base(repo: str) -> str:
    ref = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return ref.removeprefix("origin/") if ref else "main"


def files_state(worktree: str) -> str:
    if not worktree or not Path(worktree).is_dir():
        return "нет копии"
    lines = [x for x in _git(worktree, "status", "--porcelain").splitlines() if x.strip()]
    return f"{len(lines)} незакоммиченных" if lines else "чисто"


def _base_ref(repo: str, base: str) -> str:
    return f"origin/{base}" if _ok(repo, "rev-parse", "--verify", "-q", f"origin/{base}") else base


def _ahead(repo: str, base: str, branch: str) -> int:
    out = _git(repo, "rev-list", "--count", f"{_base_ref(repo, base)}..{branch}")
    return int(out) if out.isdigit() else 0


def _content_merged(repo: str, branch: str, base: str) -> bool:
    ref = _base_ref(repo, base)
    mb = _git(repo, "merge-base", ref, branch)
    if not mb:
        return False
    changed = _git(repo, "diff", "--name-only", mb, branch).splitlines()
    return all(_ok(repo, "diff", "--quiet", ref, branch, "--", f) for f in changed)


def branch_state(repo: str, branch: str, base: str, *, pr: dict | None = None) -> str:
    if branch == base:
        return "основная"
    pr = pr or {}
    sha = pr.get("headRefOid")
    after = _git(repo, "rev-list", "--count", f"{sha}..{branch}") if sha else ""
    later_commits = after.isdigit() and int(after) > 0
    if not later_commits:
        if pr.get("state") == "MERGED" or _content_merged(repo, branch, base):
            return "влита"
    if not _ok(repo, "rev-parse", "--verify", "-q", f"origin/{branch}"):
        return "не отправлена"
    return "отправлена"


def verdict(files: str, state: str, pr: str, *, ahead: int = 0) -> str:
    """`ahead`: commits of the main branch not yet on origin; they keep it from "готово"."""
    if files.endswith("незакоммиченных"):
        return "брошено с изменениями"
    if state == "влита" or (state == "основная" and not ahead):
        return "готово"
    if state == "отправлена":
        return "ждёт PR"
    return "не отправлено"


def _pr(gh: Callable, repo: str, branch: str) -> dict | None:
    found = gh(repo, ["pr", "list", "--head", branch, "--state", "all", "--json",
                      "number,state,url,headRefOid,body", "--limit", "1"])
    return found[0] if isinstance(found, list) and found and isinstance(found[0], dict) else None


def _issue_numbers(repo: str, branch: str, base: str, artifacts: str, pr: dict | None) -> list[str]:
    nums: list[str] = _ARTIFACT.findall(artifacts)
    nums += re.findall(r"/(\d+)-", branch) + re.findall(r"-(\d+)$", branch)
    nums += _CLOSES.findall(_git(repo, "log", "--format=%B", f"{_base_ref(repo, base)}..{branch}"))
    nums += _CLOSES.findall(str((pr or {}).get("body") or ""))
    return list(dict.fromkeys(nums))


def _issue_states(gh: Callable, repo: str, nums: list[str]) -> dict[str, str]:
    out = {}
    for n in nums:
        got = gh(repo, ["issue", "view", n, "--json", "state"])
        state = str(got.get("state", "")).lower() if isinstance(got, dict) else ""
        out[n] = state if state in ("open", "closed") else "unknown"
    return out


def refresh(conn: sqlite3.Connection, *, gh: Callable = _gh) -> int:
    """One `branch_status` row per distinct (repo, branch) of live sessions; rows written."""
    groups: dict[tuple[str, str], dict] = {}
    rows = conn.execute("SELECT repo, branch, worktree, artifacts FROM sessions "
                        "WHERE origin = 'live' AND repo <> '' AND branch <> '' "
                        "ORDER BY updated_at, path").fetchall()
    for repo, branch, worktree, artifacts in rows:
        g = groups.setdefault((repo, branch), {"worktree": "", "artifacts": ""})
        g["worktree"] = worktree or g["worktree"]          # the newest session's copy wins
        g["artifacts"] += f" {artifacts or ''}"
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute("DELETE FROM branch_status")
    for (repo, branch), g in groups.items():
        base = default_base(repo)
        pr = _pr(gh, repo, branch)
        files = files_state(g["worktree"])
        state = branch_state(repo, branch, base, pr=pr)
        pr_label = _PR.get((pr or {}).get("state"), "нет")
        ahead = _ahead(repo, base, branch) if state == "основная" else 0
        issues = _issue_states(gh, repo, _issue_numbers(repo, branch, base, g["artifacts"], pr))
        conn.execute("INSERT INTO branch_status VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (repo, branch, g["worktree"], files, state, pr_label,
                      (pr or {}).get("url") or "", json.dumps(issues),
                      verdict(files, state, pr_label, ahead=ahead), now))
    conn.commit()
    return len(groups)
