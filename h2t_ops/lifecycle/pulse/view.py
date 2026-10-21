"""The terminal view of the pulse: sessions grouped domain → project → repo → branch.

Reads the index only; `cli list` settles open sessions and local branch status first.
"""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from datetime import datetime

from h2t_ops.core import user_config
from h2t_ops.lifecycle.index import query
from h2t_ops.lifecycle.pulse import daily

_DASH = "—"


@dataclass
class Filters:
    domain: str | None = None
    project: str | None = None
    repo: str | None = None          # a part of the repo path, any case
    status: str | None = None        # the verdict of the branch
    pr: str | None = None            # the PR label of the branch
    tool: str | None = None
    since: str | None = None         # YYYY-MM-DD: sessions started on or after it
    all: bool = False                # also unknown-origin and empty sessions (machine: never)


_SQL = ("SELECT s.*, b.files AS b_files, b.branch_state AS b_state, b.pr AS b_pr, "
        "b.pr_url AS b_pr_url, b.issues AS b_issues, b.verdict AS b_verdict "
        "FROM sessions s LEFT JOIN branch_status b ON b.repo = s.repo AND b.branch = s.branch "
        "ORDER BY s.started_at DESC, s.path")


def _done_lines(done: str) -> list[str]:
    """`done` is text, or a list the index stored as JSON."""
    if done.startswith("["):
        try:
            items = json.loads(done)
        except ValueError:
            items = None
        if isinstance(items, list):
            return [str(i) for i in items]
    return done.splitlines()


def _summary(row: dict) -> tuple[str, str]:
    if row.get("summary"):
        return row["summary"], row.get("summary_source") or ""
    lines = [ln for ln in _done_lines(row.get("done") or "") if ln.strip()][:3]
    return ("\n".join(lines), "handoff") if lines else ("", row.get("summary_source") or "")


def _keep(row: dict, f: Filters) -> bool:
    if row["origin"] == "machine":       # never listed, with or without --all
        return False
    if not f.all and (row["origin"] != "live" or not row["user_msgs"]):
        return False
    if f.domain and row["domain"] != f.domain:
        return False
    if f.project and row["project"] != f.project:
        return False
    if f.repo and f.repo.lower() not in (row["repo"] or "").lower():
        return False
    if f.status and row["verdict"] != f.status:
        return False
    if f.pr and row["pr"] != f.pr:
        return False
    if f.tool and row["tool"] != f.tool:
        return False
    return not (f.since and (row["started_at"] or "") < f.since)


def rows(f: Filters) -> list[dict]:
    """Sessions joined with `branch_status` on (repo, branch), newest first."""
    with query.connect() as conn:
        found = [dict(r) for r in conn.execute(_SQL)]
    out = []
    for r in found:
        r["files"], r["branch_state"], r["pr"] = r.pop("b_files"), r.pop("b_state"), r.pop("b_pr")
        r["pr_url"], r["issues"], r["verdict"] = r.pop("b_pr_url"), r.pop("b_issues"), r.pop("b_verdict")
        if _keep(r, f):
            r["summary"], r["summary_source"] = _summary(r)
            out.append(r)
    return out


def _is_windows() -> bool:
    return os.name == "nt"


def _quote(cwd: str) -> str:
    """The cwd as one shell word: POSIX quoting, or PowerShell single quotes on Windows
    (a single quote is doubled; `$` and the backtick stay literal inside them)."""
    if _is_windows():
        return "'" + cwd.replace("'", "''") + "'"
    return shlex.quote(cwd)


def resume_command(tool: str, session_id: str, cwd: str) -> str:
    if tool == "codex":
        return f"codex resume {session_id} -C {_quote(cwd)}"
    return f"cd {_quote(cwd)}; claude --resume {session_id}"


def _local_time(stamp: str | None) -> str:
    try:
        return datetime.fromisoformat((stamp or "").replace("Z", "+00:00")).astimezone() \
            .strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return stamp or _DASH


def _issues(raw: str | None) -> str:
    try:
        found = json.loads(raw or "{}")
    except ValueError:
        return ""
    if not isinstance(found, dict):
        return ""
    return " ".join(f"#{n} {'?' if s == 'unknown' else s}" for n, s in found.items())


def _branch_line(group: list[dict]) -> str:
    b = group[0]
    line = f"{b['branch'] or _DASH}  [{b['verdict'] or _DASH}]  PR: {b['pr'] or _DASH}  {b['files'] or _DASH}"
    issues = _issues(b["issues"])
    return f"{line}  {issues}" if issues else line


def _nest(rows_: list[dict], keys: tuple[str, ...]) -> dict:
    tree: dict = {}
    for r in rows_:                       # rows_ is newest first, so every list stays so
        node = tree
        for key in keys[:-1]:
            node = node.setdefault(r[key] or _DASH, {})
        node.setdefault(r[keys[-1]] or _DASH, []).append(r)
    return tree


def render(rows: list[dict], footer: str) -> str:
    ordered = sorted(rows, key=lambda r: r["started_at"] or "", reverse=True)
    lines: list[str] = []
    tree = _nest(ordered, ("domain", "project", "repo", "branch"))
    for domain in sorted(tree):
        lines.append(domain)
        for project in sorted(tree[domain]):
            lines.append(f"  {project}")
            for repo in sorted(tree[domain][project]):
                lines.append(f"    {repo}")
                branches = tree[domain][project][repo]
                for branch in sorted(branches, key=lambda k: branches[k][0]["started_at"] or "",
                                     reverse=True):
                    group = branches[branch]
                    lines.append(f"      {_branch_line(group)}")
                    for s in group:
                        summary = " ".join((s["summary"] or _DASH).split())
                        lines.append(f"        {_local_time(s['started_at'])}  {s['tool']}  {summary}")
                        lines.append(f"        {resume_command(s['tool'], s['session_id'], s['cwd'] or s['worktree'] or '')}")
    lines.append(footer)
    return "\n".join(lines)


def footer() -> str:
    """The line about work outside sessions, from the daily pass's audit_map answer."""
    prefix = "Работа без сессии:"
    if not user_config.get("sessions.audit_map"):
        return f"{prefix} audit_map не настроен (sessions.audit_map в config/user.yaml)"
    found = daily.read_stamp().get("audit_map")
    if not found:
        return f"{prefix} ещё не считалось (h2t-ops sessions daily)"
    if found.get("error"):
        return f"{prefix} audit_map не отработал ({found['error']})"
    return (f"{prefix} {found['branches']} веток, {found['stash']} stash — "
            f"{found['report']} ({found['ran_at'][:10]})")
