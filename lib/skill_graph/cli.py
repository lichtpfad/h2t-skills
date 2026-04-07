"""CLI for skill_graph — called from SKILL.md bash steps.

Usage:
    $H2T_PYTHON -m skill_graph.cli query --context "hook injection"
    $H2T_PYTHON -m skill_graph.cli add-lesson --skill session-start --trigger "..." --resolution "..."
    $H2T_PYTHON -m skill_graph.cli add-pattern --type hook --title "..." --body "..." --source gstack
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from .client import SkillGraphClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill_graph")
    sub = parser.add_subparsers(dest="command", required=True)

    # query
    q = sub.add_parser("query", help="Semantic search across skill-patterns and skill-lessons")
    q.add_argument("--context", required=True, help="Natural language query")
    q.add_argument("--skill", default=None, help="Skill name (optional filter)")
    q.add_argument("--top-k", type=int, default=5)

    # add-lesson
    al = sub.add_parser("add-lesson", help="Write a lesson learned to skill-lessons")
    al.add_argument("--skill", dest="skill_name", required=True)
    al.add_argument("--trigger", required=True, help="What caused the issue")
    al.add_argument("--resolution", required=True, help="How it was fixed")
    al.add_argument("--type", dest="lesson_type", default="bug",
                    choices=["bug", "anti-pattern", "eval-finding", "regression"])
    al.add_argument("--session-id", default=None)

    # add-pattern
    ap = sub.add_parser("add-pattern", help="Write a best-practice pattern to skill-patterns")
    ap.add_argument("--type", dest="pattern_type", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--confidence", type=float, default=0.7)
    ap.add_argument("--source-url", default=None)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    client = SkillGraphClient()

    if args.command == "query":
        results = client.query(args.context, skill_name=args.skill, top_k=args.top_k)
        if not results:
            print("No results found.")
            return
        for r in results:
            title = r.get("title") or r.get("id", "?")
            body = r.get("body", "")
            score = r.get("score", 0.0)
            print(f"[{score:.2f}] {title}")
            if body:
                print(f"  {body[:200]}")
            print()

    elif args.command == "add-lesson":
        node_id = client.add_lesson(
            skill_name=args.skill_name,
            trigger=args.trigger,
            resolution=args.resolution,
            lesson_type=args.lesson_type,
            session_id=args.session_id,
        )
        print(f"Lesson written: {node_id}")

    elif args.command == "add-pattern":
        node_id = client.add_pattern(
            pattern_type=args.pattern_type,
            title=args.title,
            body=args.body,
            source=args.source,
            confidence=args.confidence,
            source_url=args.source_url,
        )
        print(f"Pattern written: {node_id}")

    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
