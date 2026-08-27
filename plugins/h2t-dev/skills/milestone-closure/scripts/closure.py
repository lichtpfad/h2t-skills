#!/usr/bin/env python3
"""Deterministic milestone closure backend for h2t-dev."""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "h2t_milestone_closure_report/v0.1"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def resolve_repo(repo_arg: str | None) -> str:
    if repo_arg:
        return repo_arg
    r = _run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh repo view failed")
    return r.stdout.strip()


def fetch_milestones(repo: str) -> list[dict]:
    r = _run(["gh", "api", f"repos/{repo}/milestones?state=all"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh api milestones failed")
    return json.loads(r.stdout or "[]")


def find_milestone(milestones: list[dict], selector: str) -> dict:
    for milestone in milestones:
        if str(milestone.get("number")) == selector or milestone.get("title") == selector:
            return milestone
    raise ValueError(f"milestone not found: {selector}")


def milestone_status(milestone: dict) -> str:
    return "blocked" if int(milestone.get("open_issues", 0)) > 0 else "ready"


def run_docs_lint_plan(repo_root: Path, *, python: str = sys.executable) -> dict:
    lint = Path(__file__).resolve().parents[2] / "docs-lint" / "scripts" / "lint.py"
    r = _run([python, str(lint), "plan", "--root", str(repo_root)])
    return {
        "status": "ok" if r.returncode == 0 else "error",
        "exit_code": r.returncode,
        "stdout": r.stdout[-4000:],
        "stderr": r.stderr[-2000:],
    }


def fetch_next_open_items(repo: str, *, limit: int = 5) -> list[dict]:
    r = _run([
        "gh", "issue", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", str(limit),
        "--json", "number,title,labels,milestone",
    ])
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return []


def close_milestone(repo: str, milestone: dict, *, confirm_title: str) -> dict:
    title = str(milestone.get("title", ""))
    if confirm_title.strip() != title:
        return {
            "status": "error",
            "exit_code": None,
            "error": f"confirmation mismatch: expected {title!r}, got {confirm_title!r}",
        }
    number = milestone.get("number")
    if number is None:
        return {
            "status": "error",
            "exit_code": None,
            "error": "milestone dict missing 'number' field",
        }
    r = _run([
        "gh", "api", f"repos/{repo}/milestones/{number}",
        "-X", "PATCH", "-f", "state=closed",
    ])
    return {
        "status": "ok" if r.returncode == 0 else "error",
        "exit_code": r.returncode,
        "stdout": r.stdout[-1000:],
        "stderr": r.stderr[-1000:],
    }


def build_report(
    *,
    repo: str,
    repo_root: Path,
    milestone: dict,
    status: str,
    docs_lint: dict,
    safe_next_action: str,
    next_open_items: list[dict] | None = None,
    close_result: dict | None = None,
) -> dict:
    return {
        "schema": SCHEMA,
        "schema_version": "0.1",
        "producer": "h2t-dev/milestone-closure",
        "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
        "repo": repo,
        "repo_root": str(repo_root),
        "status": status,
        "milestone": {
            "number": milestone.get("number"),
            "title": milestone.get("title"),
            "open_issues": milestone.get("open_issues", 0),
            "closed_issues": milestone.get("closed_issues", 0),
            "state": milestone.get("state"),
        },
        "docs_lint": docs_lint,
        "next_open_items": next_open_items or [],
        "safe_next_action": safe_next_action,
        "close_result": close_result,
    }


def write_report(repo_root: Path, report: dict) -> Path:
    out_dir = repo_root / ".h2t" / "lifecycle"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^\w\-]", "-", str(report["milestone"]["title"]).lower())
    out = out_dir / f"milestone-closure-{safe_title}.json"
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


def main(argv: list[str] | None = None) -> int:
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None, help="owner/repo; defaults to gh repo view")
    parser.add_argument("--repo-root", default=".", help="local repo root")
    parser.add_argument("--milestone", required=True, help="milestone title or API number")
    parser.add_argument("--close", action="store_true", help="close GitHub milestone after checks")
    parser.add_argument("--confirm-title", default="", help="required with --close")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.close and not args.confirm_title:
        parser.error("--confirm-title is required with --close")

    repo_root = Path(args.repo_root).expanduser().resolve()
    try:
        repo = resolve_repo(args.repo)
        milestone = find_milestone(fetch_milestones(repo), args.milestone)
        status = milestone_status(milestone)
        docs_lint = run_docs_lint_plan(repo_root)
        next_open_items = fetch_next_open_items(repo)
        close_result = None
        safe_next = "Review docs-lint plan before any archive/move; run docs-lint fix-index after approved cleanup"
        if status == "blocked":
            safe_next = "Resolve or move open milestone issues before closure"
        elif args.close:
            close_result = close_milestone(repo, milestone, confirm_title=args.confirm_title)
            status = "closed" if close_result["status"] == "ok" else "partial"
            safe_next = "Write handoff / release report"
        report = build_report(
            repo=repo,
            repo_root=repo_root,
            milestone=milestone,
            status=status,
            docs_lint=docs_lint,
            next_open_items=next_open_items,
            safe_next_action=safe_next,
            close_result=close_result,
        )
        report_path = write_report(repo_root, report)
        report["refs"] = [{"type": "report_json", "uri": str(report_path)}]
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "schema_version": "0.1",
            "producer": "h2t-dev/milestone-closure",
            "produced_at": datetime.datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(exc),
            "safe_next_action": "Fix milestone closure error and rerun dry-run",
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") not in {"error", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
