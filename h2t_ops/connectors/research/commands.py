"""Argparse surface for the research connector."""
from __future__ import annotations

import argparse
from typing import Any

FETCH_PROVIDERS = [
    "auto",
    "direct",
    "jina",
    "playwright",
    "crawl4ai",
    "firecrawl",
    "browserless",
]


def add_fmt(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="raw machine-readable envelope",
    )
    sp.add_argument(
        "--format",
        dest="fmt",
        choices=["human", "md"],
        default="human",
        help="human = concise JSON-like output, md = markdown-oriented output",
    )


def register(subparsers: Any) -> None:
    p = subparsers.add_parser(
        "research",
        help="Run provider-backed web research and URL fetching",
    )
    cmds = p.add_subparsers(dest="research_cmd", required=True)

    preflight = cmds.add_parser("preflight", help="Validate Exa credentials and connectivity")
    add_fmt(preflight)

    search = cmds.add_parser("search", help="Search the web with Exa")
    search.add_argument("--query", required=True)
    search.add_argument(
        "--mode",
        default="generic",
        choices=["fast", "generic", "news", "academic", "competitor", "people", "deep"],
    )
    search.add_argument("--depth")
    search.add_argument("--num-results", type=int, dest="num_results")
    search.add_argument("--additional-queries", dest="additional_queries")
    search.add_argument("--start-date", dest="start_date")
    search.add_argument("--end-date", dest="end_date")
    search.add_argument("--include-domains", dest="include_domains")
    search.add_argument("--exclude-domains", dest="exclude_domains")
    search.add_argument("--include-text", dest="include_text")
    search.add_argument("--exclude-text", dest="exclude_text")
    search.add_argument("--country")
    search.add_argument("--full-text", action="store_true", dest="full_text")
    search.add_argument("--project", default="default")
    search.add_argument("--output-dir", dest="output_dir")
    search.add_argument("--no-retry", action="store_true", dest="no_retry")
    add_fmt(search)

    crawl = cmds.add_parser("crawl", help="Fetch URL contents with Exa")
    crawl.add_argument("--url", required=True)
    crawl.add_argument("--project", default="default")
    crawl.add_argument("--output-dir", dest="output_dir")
    add_fmt(crawl)

    fetch = cmds.add_parser("fetch", help="Fetch one URL through the research ladder")
    fetch.add_argument("--url", required=True)
    fetch.add_argument(
        "--provider",
        default="auto",
        choices=FETCH_PROVIDERS,
    )
    fetch.add_argument("--keep-raw", action="store_true", dest="keep_raw")
    fetch.add_argument("--timeout-ms", type=int, default=15000, dest="timeout_ms")
    fetch.add_argument("--min-body-chars", type=int, default=200, dest="min_body_chars")
    fetch.add_argument("--user-agent", dest="user_agent")
    fetch.add_argument("--project", default="default")
    fetch.add_argument("--output-dir", dest="output_dir")
    fetch.add_argument("--config", dest="config_path")
    add_fmt(fetch)

    p.set_defaults(_handler=run)


def _split_csv(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def run(args: Any) -> Any:
    from pathlib import Path

    from h2t_ops.connectors.research.client import ResearchClient
    from h2t_ops.core.errors import UsageError

    client = ResearchClient(
        output_dir=Path(args.output_dir) if getattr(args, "output_dir", None) else None
    )
    cmd = args.research_cmd
    if cmd == "preflight":
        return client.preflight()
    if cmd == "search":
        return client.search(
            query=args.query,
            mode=args.mode,
            depth=args.depth,
            num_results=args.num_results,
            additional_queries=_split_csv(args.additional_queries),
            start_date=args.start_date,
            end_date=args.end_date,
            include_domains=_split_csv(args.include_domains),
            exclude_domains=_split_csv(args.exclude_domains),
            include_text=_split_csv(args.include_text),
            exclude_text=_split_csv(args.exclude_text),
            country=args.country,
            full_text=args.full_text,
            project=args.project,
            no_retry=args.no_retry,
        )
    if cmd == "crawl":
        return client.crawl(args.url, project=args.project)
    if cmd == "fetch":
        return client.fetch_url(
            args.url,
            provider=args.provider,
            keep_raw=args.keep_raw,
            timeout_ms=args.timeout_ms,
            min_body_chars=args.min_body_chars,
            user_agent=args.user_agent,
            project=args.project,
            config_path=args.config_path,
        )
    raise UsageError(f"unknown research subcommand: {cmd}")
