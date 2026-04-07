"""GEPA Batch — Generative Eval Pipeline Architecture.

Closes the eval→lesson→pattern→skill loop:
1. scan  — read eval-findings from skill-lessons, LLM-judge → staging
2. list  — show staging files pending review
3. approve — write approved patterns to skill-patterns

Usage:
    python -m lib.skill_graph.gepa_batch scan
    python -m lib.skill_graph.gepa_batch list
    python -m lib.skill_graph.gepa_batch approve <staging-file> [--indices 0,2,3]

Requires: ANTHROPIC_API_KEY env var (for LLM judge), h2t-graphs tokens in ~/.dor/secrets.env.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.skill_graph.client import SkillGraphClient

_log = logging.getLogger(__name__)

GEPA_ROOT = Path.home() / ".h2t" / "gepa"
STAGING_DIR = GEPA_ROOT / "staging"
LAST_RUN_FILE = GEPA_ROOT / "last_run.json"


def _load_last_run() -> Optional[str]:
    """Return ISO date of last GEPA run, or None."""
    if LAST_RUN_FILE.exists():
        data = json.loads(LAST_RUN_FILE.read_text(encoding="utf-8"))
        return data.get("last_run")
    return None


def _save_last_run(ts: str) -> None:
    GEPA_ROOT.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(json.dumps({"last_run": ts}), encoding="utf-8")


def _fetch_eval_findings(client: SkillGraphClient, since: Optional[str] = None) -> list[dict]:
    """Query skill-lessons for eval-finding entries."""
    results = client.query(
        context="eval-finding score change",
        sources=("skill-lessons",),
        top_k=50,
    )
    findings = [r for r in results if r.get("lesson_type") == "eval-finding"
                or r.get("node", {}).get("lesson_type") == "eval-finding"]
    if since:
        findings = [f for f in findings
                    if (f.get("date", "") or f.get("node", {}).get("date", "")) > since]
    return findings


def _llm_judge(findings: list[dict]) -> list[dict]:
    """Send findings to Claude API for pattern suggestion generation.

    Returns list of suggested patterns (not yet written to graph).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        _log.error("ANTHROPIC_API_KEY not set — cannot run LLM judge")
        return []

    findings_text = json.dumps(findings, indent=2, ensure_ascii=False, default=str)
    prompt = f"""You are an expert at analyzing skill evaluation findings and extracting actionable patterns.

Below are eval-finding lessons from a skill intelligence graph. Each finding records a score change
during skill evaluation.

Your task: analyze these findings and suggest improvement patterns that could prevent future issues
or improve skill performance.

For each pattern suggestion, output:
- pattern_type: "eval-derived"
- title: concise pattern name
- body: actionable description (what to do, when, why)
- applies_to: list of skill names this applies to
- confidence: 0.0-1.0 based on evidence strength
- tags: relevant tags

Findings:
{findings_text}

Respond with a JSON array of pattern suggestions. Only output valid JSON, no other text."""

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        text = data.get("content", [{}])[0].get("text", "[]")
        # Extract JSON array from response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return []
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        _log.error("LLM judge failed: %s", exc)
        return []


def cmd_scan(args: argparse.Namespace) -> None:
    """Scan eval-findings, run LLM judge, write staging file."""
    client = SkillGraphClient()
    since = _load_last_run()

    print(f"Scanning eval-findings since: {since or 'all time'}")
    findings = _fetch_eval_findings(client, since)
    if not findings:
        print("No new eval-findings found.")
        return

    print(f"Found {len(findings)} eval-finding(s). Running LLM judge...")
    suggestions = _llm_judge(findings)
    if not suggestions:
        print("LLM judge returned no suggestions.")
        return

    # Write staging file
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    staging_file = STAGING_DIR / f"gepa-{ts}.json"

    staging = {
        "created": datetime.now(timezone.utc).isoformat(),
        "findings_count": len(findings),
        "suggestions": suggestions,
        "approved": [],
    }
    staging_file.write_text(json.dumps(staging, indent=2, ensure_ascii=False), encoding="utf-8")

    _save_last_run(datetime.now(timezone.utc).isoformat())

    print(f"\nStaging file: {staging_file}")
    print(f"Suggestions: {len(suggestions)}")
    print("\nReview suggestions:")
    for i, s in enumerate(suggestions):
        print(f"  [{i}] {s.get('title', '?')} (confidence: {s.get('confidence', '?')})")
        print(f"      applies_to: {s.get('applies_to', [])}")
    print(f"\nApprove with: python -m lib.skill_graph.gepa_batch approve {staging_file.name}")


def cmd_list(args: argparse.Namespace) -> None:
    """List pending staging files."""
    if not STAGING_DIR.exists():
        print("No staging files.")
        return
    files = sorted(STAGING_DIR.glob("gepa-*.json"))
    if not files:
        print("No staging files.")
        return
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        n_sugg = len(data.get("suggestions", []))
        n_appr = len(data.get("approved", []))
        print(f"  {f.name}  suggestions={n_sugg}  approved={n_appr}  created={data.get('created', '?')}")


def cmd_approve(args: argparse.Namespace) -> None:
    """Approve suggestions and write to skill-patterns."""
    staging_path = STAGING_DIR / args.file if not Path(args.file).is_absolute() else Path(args.file)
    if not staging_path.exists():
        print(f"File not found: {staging_path}", file=sys.stderr)
        sys.exit(1)

    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    suggestions = staging.get("suggestions", [])

    if args.indices:
        indices = [int(i.strip()) for i in args.indices.split(",")]
    else:
        indices = list(range(len(suggestions)))

    client = SkillGraphClient()
    if not client.writable:
        print("Error: no RW token configured. Cannot write patterns.", file=sys.stderr)
        sys.exit(1)

    written = []
    for i in indices:
        if i < 0 or i >= len(suggestions):
            print(f"  Skipping invalid index: {i}")
            continue
        s = suggestions[i]
        try:
            node_id = client.add_pattern(
                pattern_type="eval-derived",
                title=s.get("title", "untitled"),
                body=s.get("body", ""),
                source="gepa",
                applies_to=s.get("applies_to", []),
                confidence=s.get("confidence", 0.5),
                tags=s.get("tags", []),
            )
            written.append({"index": i, "node_id": node_id, "title": s.get("title")})
            print(f"  [{i}] Written: {node_id} — {s.get('title')}")
        except Exception as exc:
            print(f"  [{i}] Failed: {exc}")

    staging["approved"] = staging.get("approved", []) + written
    staging_path.write_text(json.dumps(staging, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(written)} pattern(s) written to skill-patterns.")


def main() -> None:
    parser = argparse.ArgumentParser(description="GEPA batch — eval→pattern improvement loop")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan eval-findings, run LLM judge, write staging")
    sub.add_parser("list", help="List pending staging files")

    approve_p = sub.add_parser("approve", help="Approve staged suggestions → skill-patterns")
    approve_p.add_argument("file", help="Staging file name or path")
    approve_p.add_argument("--indices", help="Comma-separated indices to approve (default: all)")

    args = parser.parse_args()
    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "approve":
        cmd_approve(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
