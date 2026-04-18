#!/usr/bin/env python3
"""exa_search.py — Exa API wrapper for h2t-ops:research skill.

See docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md
"""
from __future__ import annotations

__version__ = "0.1.0"

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Module globals
SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEMPROMPTS_DIR = SCRIPT_DIR.parent / "systemprompts"

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


def validate_args(args: argparse.Namespace) -> None:
    """Fail-fast validation per spec §5.7 to prevent HTTP 400 from Exa."""
    cfg = MODE_CONFIG[args.mode]
    category = cfg["category"]

    if category in CATEGORY_BLOCKS:
        blocked = CATEGORY_BLOCKS[category]
        attempted: dict[str, Any] = {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "include_domains": args.include_domains,
            "exclude_domains": args.exclude_domains,
            "include_text": args.include_text,
            "exclude_text": args.exclude_text,
        }
        conflicts = [k for k in blocked if attempted.get(k)]
        if conflicts:
            first = conflicts[0].replace("_", "-")
            die(
                1,
                f"EXA_ERROR:ARGS mode={args.mode} (category={category}) "
                f"incompatible with --{first}. "
                f"Blocked params for this category: {sorted(blocked)}. "
                f"Switch to --mode news or generic to use these filters.",
            )

    # Universal: include_text / exclude_text are single-item only (spec §5.7).
    for name in ("include_text", "exclude_text"):
        val = getattr(args, name, None)
        if isinstance(val, list) and len(val) > 1:
            die(
                1,
                f"EXA_ERROR:ARGS --{name.replace('_', '-')} supports only "
                f"single-item arrays; got {len(val)} items. Split into separate calls.",
            )


def load_system_prompt(mode: str) -> tuple[str, dict[str, Any]]:
    """Read systemprompts/{mode}.md. Returns (body_text, output_schema_or_empty).

    YAML frontmatter recognised keys: mode, exa_type, exa_category, output_schema.
    output_schema must be a single-line JSON object OR a JSON block quoted with `|`.
    Body = systemPrompt for Exa API.
    """
    path = SYSTEMPROMPTS_DIR / f"{mode}.md"
    if not path.is_file():
        die(1, f"EXA_ERROR:ARGS systemprompt file missing: {path}")
    raw = path.read_text(encoding="utf-8")
    schema: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            fm = raw[4:end]
            body = raw[end + 5:].lstrip()
            for line in fm.splitlines():
                stripped = line.strip()
                if stripped.startswith("output_schema:"):
                    val = stripped.split(":", 1)[1].strip()
                    if val.startswith("{"):
                        try:
                            schema = json.loads(val)
                        except json.JSONDecodeError:
                            pass
    return body.strip(), schema


def build_body(
    args: argparse.Namespace,
    system_prompt: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    """Compose Exa /search request body (spec §5.2 + §5.8)."""
    cfg = MODE_CONFIG[args.mode]
    body: dict[str, Any] = {
        "query": args.query,
        "type": cfg["type"],
        "numResults": args.num_results or cfg["num_results"],
        "contents": {"highlights": {"maxCharacters": cfg["highlight_chars"]}},
    }
    if cfg["category"]:
        body["category"] = cfg["category"]
    if system_prompt:
        body["systemPrompt"] = system_prompt
    if output_schema:
        body["outputSchema"] = output_schema
        body["structuredOutput"] = True
    if args.additional_queries:
        body["additionalQueries"] = list(args.additional_queries)
    if args.start_date:
        body["startPublishedDate"] = args.start_date
    if args.end_date:
        body["endPublishedDate"] = args.end_date
    if args.include_domains:
        body["includeDomains"] = list(args.include_domains)
    if args.exclude_domains:
        body["excludeDomains"] = list(args.exclude_domains)
    if args.include_text:
        body["includeText"] = list(args.include_text)
    if args.exclude_text:
        body["excludeText"] = list(args.exclude_text)
    if args.country:
        body["userLocation"] = args.country
    if args.full_text:
        body["contents"]["text"] = {"maxCharacters": 15000}
    if args.mode == "deep" and output_schema:
        body["contents"]["highlights"] = {"maxCharacters": 1}
    return body


EXA_API = "https://api.exa.ai"


def call_exa(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    timeout: int = 60,
) -> tuple[int, dict[str, Any], int]:
    """POST to Exa. Returns (http_status, response_json_or_error_body, latency_ms).

    Network errors (URLError) exit 3 via die() — these cannot be silently swallowed.
    HTTP errors (4xx/5xx) return (status, error_body, latency) to caller for decision.
    """
    req = urllib.request.Request(
        f"{EXA_API}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - start) * 1000)
            return resp.status, json.loads(resp.read().decode("utf-8")), latency
    except urllib.error.HTTPError as e:
        latency = int((time.monotonic() - start) * 1000)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": "non_json_error_response"}
        return e.code, err_body, latency
    except urllib.error.URLError as e:
        latency = int((time.monotonic() - start) * 1000)
        die(3, f"EXA_ERROR:NETWORK {e.reason} after {latency}ms")
        raise  # unreachable — satisfies type checker


def preflight() -> None:
    """Step 0: env + connectivity probe (spec §4 Step 0)."""
    if not os.environ.get("EXA_API_KEY"):
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing; obtain at https://dashboard.exa.ai/api-keys")
    req = urllib.request.Request(f"{EXA_API}/", method="GET")
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError as e:
        die(4, f"EXA_ERROR:NETWORK cannot reach {EXA_API}: {e.reason}")
    print("OK")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 50) -> str:
    """Lowercase, collapse non-alnum → hyphen, trim, cap length."""
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len]


def output_paths(
    output_dir: Path, project: str, topic: str, date: str
) -> dict[str, Path]:
    """Per spec §8: persistence filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(project)}-{slugify(topic)}-{date}"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "final_md": output_dir / f"{base}.md",
        "sources_json": output_dir / f"{base}.sources.json",
    }


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
