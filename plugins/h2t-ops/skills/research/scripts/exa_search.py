#!/usr/bin/env python3
"""exa_search.py — Exa API wrapper for h2t-ops:research skill.

See docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md
"""
from __future__ import annotations

__version__ = "0.1.0"

import argparse
import sys
from typing import Any

# Mode → Exa API params (spec §5.2).
# highlight_chars = default maxCharacters for contents.highlights.
MODE_CONFIG: dict[str, dict[str, Any]] = {
    "fast":       {"type": "fast", "category": None,             "highlight_chars": 2000, "num_results": 10},
    "generic":    {"type": "auto", "category": None,             "highlight_chars": 4000, "num_results": 10},
    "news":       {"type": "auto", "category": "news",           "highlight_chars": 3000, "num_results": 10},
    "academic":   {"type": "auto", "category": "research paper", "highlight_chars": 4000, "num_results": 8},
    "competitor": {"type": "auto", "category": "company",        "highlight_chars": 4000, "num_results": 10},
    "people":     {"type": "auto", "category": "people",         "highlight_chars": 3000, "num_results": 10},
    "deep":       {"type": "deep", "category": None,             "highlight_chars": 5000, "num_results": 10},
}

# Category-specific param incompatibilities (spec §5.7).
# Each listed param causes HTTP 400 from Exa when combined with that category.
CATEGORY_BLOCKS: dict[str, set[str]] = {
    "company":          {"start_date", "end_date", "include_domains", "exclude_domains"},
    "people":           {"start_date", "end_date", "include_text", "exclude_text", "exclude_domains"},
    "financial report": {"exclude_text"},
}


def die(code: int, stderr_msg: str) -> None:
    """Write structured error to stderr and exit. Spec §5.4."""
    print(stderr_msg, file=sys.stderr)
    sys.exit(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exa_search",
        description="Exa API wrapper (preflight / search / crawl subcommands).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"exa_search {__version__}",
    )
    sub = parser.add_subparsers(dest="cmd", required=False)
    # subcommands added in later tasks
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
