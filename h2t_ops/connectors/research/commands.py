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

    visual_ocr = cmds.add_parser(
        "visual-ocr",
        help="Create a review-required OCR rescue artifact",
    )
    # Manual mode (existing)
    visual_ocr.add_argument("--fetch-sidecar", dest="fetch_sidecar")
    visual_ocr.add_argument("--image-path", dest="image_path")
    # Auto-capture mode (new)
    visual_ocr.add_argument("--url", dest="visual_ocr_url")
    visual_ocr.add_argument("--project", default="default")
    visual_ocr.add_argument("--output-dir", dest="output_dir")
    add_fmt(visual_ocr)

    similar = cmds.add_parser("similar", help="Find pages similar to a URL using Exa")
    similar.add_argument("--url", required=True, dest="url")
    similar.add_argument("--num-results", type=int, dest="num_results")
    similar.add_argument("--include-domains", dest="include_domains")
    similar.add_argument("--exclude-domains", dest="exclude_domains")
    add_fmt(similar)

    nav_index = cmds.add_parser("index", help="List canonical research index")
    nav_index.add_argument("index_name", choices=["documents", "threads", "syntheses"])
    nav_index.add_argument("--project", dest="project")
    nav_index.add_argument("--output-dir", dest="output_dir")
    add_fmt(nav_index)

    nav_show = cmds.add_parser("show", help="Show a canonical research object")
    nav_show.add_argument("object_type", choices=["document", "thread", "run", "synthesis"])
    nav_show.add_argument("object_id")
    nav_show.add_argument("--output-dir", dest="output_dir")
    add_fmt(nav_show)

    nav_resolve = cmds.add_parser("resolve", help="Resolve aliases to research objects")
    nav_resolve.add_argument("--output-dir", dest="output_dir")
    nav_resolve.add_argument(
        "--alias-type",
        dest="alias_type",
        default="url",
    )
    alias_group = nav_resolve.add_mutually_exclusive_group(required=True)
    alias_group.add_argument("--url", dest="url_value")
    alias_group.add_argument("--alias", dest="alias_value")
    add_fmt(nav_resolve)

    doctor = cmds.add_parser("doctor", help="Inspect local research store health")
    doctor.add_argument("--output-dir", dest="output_dir")
    add_fmt(doctor)

    rebuild = cmds.add_parser(
        "rebuild-indexes",
        help="Rebuild research indexes from canonical object JSON",
    )
    rebuild.add_argument("--output-dir", dest="output_dir")
    add_fmt(rebuild)

    cleanup = cmds.add_parser(
        "cleanup",
        help="Report safe cleanup candidates for local research artifacts",
    )
    cleanup.add_argument("--output-dir", dest="output_dir")
    cleanup.add_argument("--dry-run", action="store_true", required=True, dest="dry_run")
    add_fmt(cleanup)

    answer_p = cmds.add_parser("answer", help="Get a direct LLM-grounded answer from Exa")
    answer_p.add_argument("--query", required=True)
    add_fmt(answer_p)

    resolve_author = cmds.add_parser("resolve-author", help="Resolve an author name to a channel URL")
    resolve_author.add_argument("--name", required=True)
    resolve_author.add_argument("--keywords", dest="keywords")
    resolve_author.add_argument("--hint", dest="hint")
    add_fmt(resolve_author)

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
    if cmd == "visual-ocr":
        if getattr(args, "visual_ocr_url", None):
            return client.visual_ocr_auto(
                args.visual_ocr_url,
                project=args.project,
            )
        if not (args.fetch_sidecar and args.image_path):
            raise UsageError(
                "visual-ocr requires either --url or both --fetch-sidecar and --image-path"
            )
        return client.visual_ocr(
            fetch_sidecar=args.fetch_sidecar,
            image_path=args.image_path,
            project=args.project,
        )
    if cmd == "similar":
        return client.similar(
            args.url,
            num_results=args.num_results,
            include_domains=_split_csv(args.include_domains),
            exclude_domains=_split_csv(args.exclude_domains),
        )
    if cmd == "index":
        return client.list_research_index(args.index_name, project=args.project)
    if cmd == "show":
        return client.show_research_object(args.object_type, args.object_id)
    if cmd == "resolve":
        if args.url_value is not None:
            return client.resolve_research_alias(args.url_value, alias_type="url")
        return client.resolve_research_alias(args.alias_value, alias_type=args.alias_type)
    if cmd == "doctor":
        return client.research_doctor()
    if cmd == "rebuild-indexes":
        return client.rebuild_research_indexes()
    if cmd == "cleanup":
        return client.cleanup_research(dry_run=args.dry_run)
    if cmd == "answer":
        return client.answer(args.query)
    if cmd == "resolve-author":
        return client.resolve_author(
            args.name,
            keywords=_split_csv(args.keywords),
            hint=args.hint,
        )
    raise UsageError(f"unknown research subcommand: {cmd}")
