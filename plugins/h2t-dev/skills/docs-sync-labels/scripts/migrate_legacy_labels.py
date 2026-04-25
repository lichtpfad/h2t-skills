#!/usr/bin/env python3
"""Migrate legacy flat labels to namespaced-v1 schema across h2t-* repos.

Usage:
    python migrate_legacy_labels.py [--apply] [--repos REPO [REPO ...]]

Default is --dry-run. Pass --apply to execute changes.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "lib"))  # plugins/h2t-dev/lib
from docs.common import GH, REPO_MANIFEST  # noqa: E402

# Mapping: legacy label -> canonical label (None = remove without replacement)
LABEL_MAP: dict[str, str | None] = {
    "bug":           "type:bug",
    "feature":       "type:feature",
    "enhancement":   "type:enhancement",
    "refactor":      "type:refactor",
    "docs":          "type:docs",
    "documentation": "type:docs",
    "chore":         "type:chore",
    # Old priority flat
    "P0-critical":   "priority:p0",
    "P1-high":       "priority:p1",
    "P2-medium":     "priority:p2",
    "P3-low":        "priority:p3",
    # Case-duplicate uppercase
    "priority:P0":   "priority:p0",
    "priority:P1":   "priority:p1",
    "priority:P2":   "priority:p2",
    "priority:P3":   "priority:p3",
    # Platform domain taxonomy (D-series) -> remove (no canonical equivalent yet)
    "D1-methodology": None,
    "D2-workflow":    None,
    "D3-business":    None,
    "D4-repo":        None,
    "D6-research":    None,
    # GitHub defaults to remove (not in canonical)
    "duplicate":      None,
    "invalid":        None,
    "help wanted":    None,
    "good first issue": None,
    "question":       None,
    # wontfix -> status:wontfix
    "wontfix":        "status:wontfix",
}

# Labels to delete after relabelling (only if no issues remain using them)
DELETE_AFTER_MIGRATE = {
    "bug", "feature", "enhancement", "refactor", "docs", "documentation", "chore",
    "P0-critical", "P1-high", "P2-medium", "P3-low",
    "priority:P0", "priority:P1", "priority:P2", "priority:P3",
    "D1-methodology", "D2-workflow", "D3-business", "D4-repo", "D6-research",
    "duplicate", "invalid", "help wanted", "good first issue", "question", "wontfix",
}


def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def get_issues_with_label(repo: str, label: str) -> list[int]:
    out = run([GH, "issue", "list", "--repo", f"lichtpfad/{repo}",
               "--label", label, "--state", "all",
               "--json", "number", "--limit", "200"])
    if not out:
        return []
    try:
        return [i["number"] for i in json.loads(out)]
    except (json.JSONDecodeError, KeyError):
        return []


def get_repo_labels(repo: str) -> list[str]:
    out = run([GH, "label", "list", "--repo", f"lichtpfad/{repo}",
               "--json", "name", "--limit", "200"])
    if not out:
        return []
    try:
        return [l["name"] for l in json.loads(out)]
    except (json.JSONDecodeError, KeyError):
        return []


def relabel_issue(repo: str, issue: int, remove: str, add: str | None, dry_run: bool) -> None:
    cmd = [GH, "issue", "edit", str(issue), "--repo", f"lichtpfad/{repo}",
           "--remove-label", remove]
    if add:
        cmd += ["--add-label", add]
    action = "remove" if not add else f"replace -> {add}"
    if dry_run:
        print(f"  [DRY] #{issue}: {remove} {action}")
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            print(f"  ✓ #{issue}: {remove} {action}")
        else:
            print(f"  ✗ #{issue}: {r.stderr.strip()}")


def delete_label(repo: str, label: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY] delete label: {label}")
    else:
        r = subprocess.run(
            [GH, "label", "delete", label, "--repo", f"lichtpfad/{repo}", "--yes"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            print(f"  ✓ deleted: {label}")
        else:
            print(f"  ✗ {label}: {r.stderr.strip()}")


def migrate_repo(repo: str, dry_run: bool) -> dict:
    existing = set(get_repo_labels(repo))
    legacy_present = [l for l in LABEL_MAP if l in existing]
    if not legacy_present:
        return {"repo": repo, "legacy": 0, "issues_relabelled": 0, "labels_deleted": 0}

    issues_relabelled = 0
    labels_deleted = 0
    print(f"\n--- {repo} ({len(legacy_present)} legacy labels) ---")

    for legacy in legacy_present:
        canonical = LABEL_MAP[legacy]
        issues = get_issues_with_label(repo, legacy)
        if issues:
            print(f"  {legacy} -> {canonical or '(remove)'}: {len(issues)} issues")
            for issue in issues:
                relabel_issue(repo, issue, legacy, canonical, dry_run)
            issues_relabelled += len(issues)

        if legacy in DELETE_AFTER_MIGRATE:
            remaining = get_issues_with_label(repo, legacy) if not dry_run else issues
            if not remaining:
                delete_label(repo, legacy, dry_run)
                labels_deleted += 1

    return {"repo": repo, "legacy": len(legacy_present),
            "issues_relabelled": issues_relabelled, "labels_deleted": labels_deleted}


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy labels to namespaced-v1")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--repos", nargs="*", help="Repos to process (default: all 16)")
    args = parser.parse_args()

    dry_run = not args.apply
    repos = args.repos or REPO_MANIFEST
    mode = "DRY RUN" if dry_run else "APPLY"
    print(f"migrate_legacy_labels — {mode} — {len(repos)} repos")

    totals = {"issues_relabelled": 0, "labels_deleted": 0}
    for repo in repos:
        result = migrate_repo(repo, dry_run)
        totals["issues_relabelled"] += result["issues_relabelled"]
        totals["labels_deleted"] += result["labels_deleted"]

    print(f"\n{'=' * 50}")
    print(f"Total issues relabelled: {totals['issues_relabelled']}")
    print(f"Total labels deleted:    {totals['labels_deleted']}")
    if dry_run:
        print("\nRun with --apply to execute.")


if __name__ == "__main__":
    main()
