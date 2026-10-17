"""Stop hook: suggest milestone-closure when an open milestone has no open issues.

Not a hooks.json entry: scaffold-project writes `h2t-hook on-stop` into a project's
`.claude/settings.json` (h2t_ops/lifecycle/scaffold_project.py). Those files are committed
and outlive any plugin version, so the 3.x contract is kept as it was: stdin is not read,
arguments are ignored, the suggestion is plain stdout, and the exit code is always 0.

Port of the 3.x python handler of the same name; the functions are the original's.
"""
from __future__ import annotations

import json
import subprocess


def _resolve_repo_slug() -> str:
    r = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def _closed_ready_milestones(repo_slug: str) -> list[str]:
    if not repo_slug:
        return []
    r = subprocess.run(
        ["gh", "api", f"repos/{repo_slug}/milestones?state=open"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        milestones = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    return [
        str(m["title"])
        for m in milestones
        if int(m.get("open_issues", 0)) == 0
    ]


def _check_milestones() -> None:
    try:
        repo_slug = _resolve_repo_slug()
        for title in _closed_ready_milestones(repo_slug):
            print(
                f"[h2t] Milestone '{title}' has no open issues -- "
                "consider /h2t-dev:milestone-closure"
            )
    except Exception:
        return


def main(argv: list[str]) -> int:
    _check_milestones()
    return 0
