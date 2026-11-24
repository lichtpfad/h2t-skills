#!/usr/bin/env python3
"""Is CI green on the commit a release tag names? (#583)

    python3 scripts/release_ci_gate.py <sha> [--repo owner/name] [--timeout SEC] [--interval SEC]

Reads the commit's check runs through `gh api` and waits while a required check has not
finished. Prints `green` and exits 0 when every required check's latest run succeeded; exits 1
with the reason when one did not, or when they are still unfinished after --timeout.

The suite itself runs in tests.yml on every push to main, on Linux and Windows, ratchets and
the POS contract test included. Running it again here would only add a second suite that can
disagree with the first; the release asks the first one instead.

Only the names below count. The release workflow's own jobs are check runs on the same
commit, so "every check is green" would wait on itself.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

REQUIRED = (
    "lib/ unit tests (ubuntu-latest)",
    "lib/ unit tests (windows-latest)",
    "checks / ruff",
    "checks / gitleaks",
)


def verdict(runs: list[dict], required: tuple[str, ...] = REQUIRED) -> tuple[str, list[str]]:
    """('green' | 'pending' | 'red', reasons). A re-run is a newer run of the same name: the
    highest id wins, so a failed attempt followed by a green one counts as green."""
    latest: dict[str, dict] = {}
    for run in runs:
        name = run.get("name")
        if name in required and (name not in latest or run["id"] > latest[name]["id"]):
            latest[name] = run
    red, pending = [], []
    for name in required:
        run = latest.get(name)
        if run is None:
            pending.append(f"{name}: no run yet")
        elif run.get("status") != "completed":
            pending.append(f"{name}: {run.get('status')}")
        elif run.get("conclusion") != "success":
            red.append(f"{name}: {run.get('conclusion')}")
    if red:
        return "red", red
    if pending:
        return "pending", pending
    return "green", []


def fetch(repo: str, sha: str) -> list[dict]:
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit(f"gh api failed: {out.stderr.strip()}")
    data = json.loads(out.stdout)
    if data.get("total_count", 0) > len(data.get("check_runs", [])):
        raise SystemExit(f"{data['total_count']} check runs, one page read: raise per_page or paginate")
    return data["check_runs"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sha")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--timeout", type=float, default=2700)
    ap.add_argument("--interval", type=float, default=30)
    args = ap.parse_args(argv)
    if not args.repo:
        ap.error("--repo is required outside GitHub Actions")
    deadline = time.monotonic() + args.timeout
    while True:
        state, reasons = verdict(fetch(args.repo, args.sha))
        if state == "green":
            print("green")
            return 0
        if state == "red":
            print(f"CI is red on {args.sha}:", *reasons, sep="\n  ", file=sys.stderr)
            return 1
        if time.monotonic() >= deadline:
            print(f"CI unfinished on {args.sha} after {args.timeout:.0f}s:", *reasons,
                  sep="\n  ", file=sys.stderr)
            return 1
        print("waiting:", "; ".join(reasons), file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
