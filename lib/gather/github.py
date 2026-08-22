"""GitHub context gathering via gh CLI."""

import json as _json
from .runner import run_parallel


def gather_github(
    owner_repo: str,
    project_label: str | None = None,
    issue_limit: int = 20,
) -> dict:
    """Gather GitHub state: milestones, issues, bugs, PRs."""
    label_args = ["--label", f"project:{project_label}"] if project_label else []

    raw = run_parallel({
        "milestones": [
            "gh", "api", f"repos/{owner_repo}/milestones",
            "--jq", '.[] | select(.state=="open") | {title, open: .open_issues, closed: .closed_issues, due_on}',
        ],
        "issues": [
            "gh", "issue", "list", "--repo", owner_repo, "--state", "open",
            *label_args, "--json", "number,title,labels", "--limit", str(issue_limit),
        ],
        "bugs": [
            "gh", "issue", "list", "--repo", owner_repo, "--state", "open",
            "--label", "bug", *label_args, "--json", "number,title", "--limit", "10",
        ],
        "prs": [
            "gh", "pr", "list", "--repo", owner_repo, "--state", "open",
            "--json", "number,title,headRefName",
        ],
    })

    failed = [name for name, out in raw.items() if out is None]

    milestones = _parse_jsonl_or_json(raw["milestones"])
    issues = _parse_json(raw["issues"])
    bugs = _parse_json(raw["bugs"])
    prs = _parse_json(raw["prs"])

    current_milestone = max(milestones, key=lambda m: m.get("open", 0)) if milestones else None

    milestone_issues = []
    if current_milestone:
        raw_mi = run_parallel({
            "mi": [
                "gh", "issue", "list", "--repo", owner_repo,
                "--milestone", current_milestone["title"], "--state", "open",
                *label_args, "--json", "number,title,labels",
            ],
        })
        if raw_mi["mi"] is None:
            failed.append("milestone_issues")
        milestone_issues = _parse_json(raw_mi["mi"])

    return {
        "milestones": milestones, "current_milestone": current_milestone,
        "milestone_issues": milestone_issues,
        "issues": issues, "bugs": bugs, "prs": prs,
        "failed": sorted(failed),
    }


def _parse_json(raw: str | None) -> list:
    if not raw or not raw.strip():
        return []
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return []


def _parse_jsonl_or_json(raw: str | None) -> list:
    stripped = (raw or "").strip()
    if not stripped:
        return []
    try:
        result = _json.loads(stripped)
        return result if isinstance(result, list) else [result]
    except _json.JSONDecodeError:
        pass
    items = []
    for line in stripped.splitlines():
        line = line.strip()
        if line:
            try:
                items.append(_json.loads(line))
            except _json.JSONDecodeError:
                continue
    return items
