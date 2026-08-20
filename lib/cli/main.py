"""h2t unified CLI.

Usage:
    python -m lib.cli.main gather <skill> [--cwd <path>] [--format-briefing]
    python -m lib.cli.main ingest gmail <cmd> [args...]
    python -m lib.cli.main ingest notion <cmd> [args...]
    python -m lib.cli.main ingest calendar <cmd> [args...]
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure lib/ is on sys.path for both dev and installed modes.
_root = Path(__file__).resolve().parent.parent.parent
_lib = _root / "lib"
if str(_lib) not in sys.path:
    sys.path.insert(0, str(_lib))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, get_machine_name
from gather.briefing import format_briefing
from eval.session import SkillEval


# ---------------------------------------------------------------------------
# gather subcommand
# ---------------------------------------------------------------------------

def _print_text(text: str) -> None:
    """Write plain text to stdout, UTF-8 safe on Windows (avoids cp1252 crash)."""
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    out.write(text if text.endswith("\n") else text + "\n")
    out.flush()
    out.detach()  # don't close underlying buffer


def _run_gather(skill: str, cwd: str, format_briefing_flag: bool, briefing_only: bool = False) -> None:
    start = time.monotonic()
    sources_used: list[str] = []
    sources_failed: list[str] = []

    project = identify_project(cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )

    git: dict = {}
    github: dict = {}
    if project.get("type") == "git":
        git = gather_git(cwd)
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")
        if project.get("github"):
            github = gather_github(owner_repo=project["github"])
            sources_used.append("github")

    stack = detect_stack(cwd)
    machine = get_machine_name()
    domain = project.get("domain", "dev")
    proj_id = project.get("id", "unknown")
    github_remote = project.get("github") or git.get("owner_repo", "")
    repo_name = github_remote.split("/")[-1] if github_remote else Path(cwd).resolve().name
    sessions = find_session_files(repo_name)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    data = {
        "project": project,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": sessions,
        "machine": machine,
        "user": user,
        "session_id": "",
        "_meta": {
            "sources_used": sources_used,
            "sources_failed": sources_failed,
            "gather_ms": elapsed_ms,
        },
    }

    if format_briefing_flag or briefing_only:
        briefing, meta = format_briefing(data)
        data["_briefing"] = briefing
        data["_meta"].update(meta)

    try:
        with SkillEval(skill, domain=domain, project=proj_id) as ev:
            ev.metric(
                "skills.gather_source_success_rate",
                value_num=1.0 - len(sources_failed) / max(len(sources_used), 1),
            )
            ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
            ev.metric("skills.sources_failed_count",
                      value_num=float(len(sources_failed)), level="unit")
    except Exception:
        pass

    if briefing_only:
        # Hook-identical injection format: small, UTF-8 safe, nothing to post-process.
        b = data.get("_briefing", "")
        m = json.dumps(data.get("_meta", {}), ensure_ascii=False)
        _print_text(f"BRIEFING:\n{b}\n\nGATHER_META: {m}")
    else:
        output_json(data)


def _cmd_gather(args: argparse.Namespace) -> int:
    if not args.skill:
        print("error: gather requires a skill name (e.g. session-start, handoff)", file=sys.stderr)
        return 2
    _run_gather(
        skill=args.skill,
        cwd=args.cwd,
        format_briefing_flag=args.format_briefing,
        briefing_only=args.briefing_only,
    )
    return 0


# ---------------------------------------------------------------------------
# ingest: gmail
# ---------------------------------------------------------------------------

def _emit_list(page: dict, limit: int | None, bare: bool) -> None:
    """Print a list result as an envelope, or bare for legacy consumers.

    The envelope exists so a caller cannot mistake a truncated page for the
    whole set: `count` is what came back, `truncated` is the API's own flag.
    """
    items = page["items"]
    if bare:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    envelope = {
        "items": items,
        "count": len(items),
        "limit": limit,
        "truncated": bool(page.get("has_more")),
    }
    for key in ("estimated_total", "window", "relations"):
        if page.get(key) is not None:
            envelope[key] = page[key]
    print(json.dumps(envelope, ensure_ascii=False, indent=2))


def _add_gmail_subparser(ingest_sub: argparse.Action) -> None:
    p = ingest_sub.add_parser("gmail", help="Gmail operations")
    cmds = p.add_subparsers(dest="gmail_cmd")

    # list
    lp = cmds.add_parser("list", help="List messages")
    lp.add_argument("--max", type=int, default=10)
    lp.add_argument("--unread", action="store_true")
    lp.add_argument("--query", default=None)
    lp.add_argument("--json", dest="as_json", action="store_true")
    lp.add_argument("--bare", action="store_true", help="emit a plain array, no envelope")

    # read
    rp = cmds.add_parser("read", help="Read a message")
    rp.add_argument("message_id")
    rp.add_argument("--format", choices=["plain", "json"], default="plain")

    # search
    sp = cmds.add_parser("search", help="Search messages")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=10)
    sp.add_argument("--json", dest="as_json", action="store_true")
    sp.add_argument("--bare", action="store_true", help="emit a plain array, no envelope")

    # send
    snp = cmds.add_parser("send", help="Send a message")
    snp.add_argument("to")
    snp.add_argument("subject")
    snp.add_argument("body", nargs="?")
    snp.add_argument("--file")
    snp.add_argument("--attach", nargs="+")
    snp.add_argument("--draft", action="store_true")

    # draft
    dp = cmds.add_parser("draft", help="Create a draft")
    dp.add_argument("to")
    dp.add_argument("subject")
    dp.add_argument("body", nargs="?")
    dp.add_argument("--file")
    dp.add_argument("--attach", nargs="+")
    dp.add_argument("--thread-id")
    dp.add_argument("--reply-to")

    # labels
    cmds.add_parser("labels", help="List all labels")

    # label
    lbp = cmds.add_parser("label", help="Modify message labels")
    lbp.add_argument("message_id")
    lbp.add_argument("--add", nargs="+")
    lbp.add_argument("--remove", nargs="+")


def _cmd_gmail(args: argparse.Namespace) -> int:
    from clients.gmail import GmailClient, format_message_list, format_message_detail

    cmd = args.gmail_cmd
    if not cmd:
        print("error: gmail requires a subcommand (list, read, search, send, draft, labels, label)", file=sys.stderr)
        return 2

    try:
        client = GmailClient()

        if cmd == "list":
            page = client.list_messages_page(
                max_results=args.max, query=args.query, unread_only=args.unread
            )
            if getattr(args, "as_json", False):
                _emit_list(page, args.max, getattr(args, "bare", False))
            else:
                print(format_message_list(page["items"]))

        elif cmd == "read":
            message = client.get_message(args.message_id)
            if args.format == "json":
                print(json.dumps(message, ensure_ascii=False, indent=2))
            else:
                print(format_message_detail(message))

        elif cmd == "search":
            page = client.list_messages_page(max_results=args.max, query=args.query)
            if getattr(args, "as_json", False):
                _emit_list(page, args.max, getattr(args, "bare", False))
            else:
                print(format_message_list(page["items"]))

        elif cmd in ("send", "draft"):
            body = args.body
            if args.file:
                body = Path(args.file).read_text(encoding="utf-8")
            if not body:
                print("error: provide body as argument or --file", file=sys.stderr)
                return 1
            as_draft = cmd == "draft" or getattr(args, "draft", False)
            result = client.send_message(
                to=args.to,
                subject=args.subject,
                body=body,
                attachments=args.attach,
                as_draft=as_draft,
                thread_id=getattr(args, "thread_id", None),
                reply_to_message_id=getattr(args, "reply_to", None),
            )
            if as_draft:
                print(f"✓ Draft created (ID: {result['id']})")
            else:
                print(f"✓ Message sent (ID: {result['id']})")

        elif cmd == "labels":
            labels = client.list_labels()
            print(f"Found {len(labels)} label(s):\n")
            for label in labels:
                print(f"- {label['name']} (ID: {label['id']})")

        elif cmd == "label":
            result = client.modify_labels(
                message_id=args.message_id,
                add_labels=args.add,
                remove_labels=args.remove,
            )
            print(f"✓ Labels modified. Current: {', '.join(result.get('labelIds', []))}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# ingest: notion
# ---------------------------------------------------------------------------

def _add_notion_subparser(ingest_sub: argparse.Action) -> None:
    p = ingest_sub.add_parser("notion", help="Notion operations")
    cmds = p.add_subparsers(dest="notion_cmd")

    gp = cmds.add_parser("get", help="Get page metadata")
    gp.add_argument("page_id")
    gp.add_argument("--format", choices=["json", "markdown"], default="json")

    bp = cmds.add_parser("blocks", help="Get page blocks")
    bp.add_argument("page_id")
    bp.add_argument("--limit", type=int)
    bp.add_argument("--format", choices=["json", "markdown"], default="json")

    sp = cmds.add_parser("search", help="Search database")
    sp.add_argument("database_id")
    sp.add_argument("--filter")
    sp.add_argument("--filter-json")
    sp.add_argument("--bare", action="store_true", help="emit a plain array, no envelope")
    sp.add_argument(
        "--resolve-relations",
        nargs="*",
        metavar="PROP",
        help="resolve relation properties to title+url; names limit which ones",
    )
    sp.add_argument("--limit", type=int)
    sp.add_argument("--format", choices=["json", "markdown"], default="json")

    cp = cmds.add_parser("create", help="Create page")
    cp.add_argument("parent_id")
    cp.add_argument("title")
    cp.add_argument("--content")
    cp.add_argument("--file")
    cp.add_argument("--database", action="store_true")

    up = cmds.add_parser("update", help="Update page")
    up.add_argument("page_id")
    up.add_argument("--title")
    up.add_argument("--append")
    up.add_argument("--file")
    up.add_argument("--replace", action="store_true")

    gdp = cmds.add_parser("get-database", help="Get database items")
    gdp.add_argument("database_id")
    gdp.add_argument("--format", choices=["json", "markdown"], default="markdown")
    gdp.add_argument("--limit", type=int)

    fdp = cmds.add_parser("find-databases", help="Find databases on page")
    fdp.add_argument("page_id")
    fdp.add_argument("--format", choices=["json", "markdown"], default="markdown")

    ftp = cmds.add_parser("find-project-tasks", help="Find tasks for project page")
    ftp.add_argument("project_page_id")
    ftp.add_argument("--database-id", default="beabac7bf4314952a9327759c638d89f")
    ftp.add_argument("--format", choices=["json", "markdown"], default="markdown")
    ftp.add_argument("--limit", type=int)

    syp = cmds.add_parser("sync", help="Sync page to Markdown file")
    syp.add_argument("page_id")
    syp.add_argument("output_file")
    syp.add_argument("--preserve-metadata", action="store_true")


def _cmd_notion(args: argparse.Namespace) -> int:
    from clients.notion import NotionClient

    cmd = args.notion_cmd
    if not cmd:
        print("error: notion requires a subcommand", file=sys.stderr)
        return 2

    try:
        client = NotionClient()

        if cmd == "get":
            if args.format == "json":
                page = client.get_page(args.page_id)
                print(json.dumps(page, indent=2, ensure_ascii=False))
            else:
                blocks = client.get_blocks(args.page_id)
                print(client.blocks_to_markdown(blocks))

        elif cmd == "blocks":
            blocks = client.get_blocks(args.page_id, limit=args.limit)
            if args.format == "json":
                print(json.dumps(blocks, indent=2, ensure_ascii=False))
            else:
                print(client.blocks_to_markdown(blocks))

        elif cmd == "search":
            filter_dict = None
            if getattr(args, "filter_json", None):
                filter_dict = json.loads(args.filter_json)
            elif getattr(args, "filter", None):
                parts = args.filter.split("=")
                if len(parts) == 2:
                    filter_dict = {"property": parts[0].strip(), "select": {"equals": parts[1].strip()}}
            page = client.query_database_page(
                args.database_id, filter_dict=filter_dict, limit=args.limit
            )
            results = page["items"]
            relations = None
            if getattr(args, "resolve_relations", None) is not None:
                relations = client.resolve_relations(results, args.resolve_relations or None)
            if args.format == "json":
                if relations:
                    page = {**page, "relations": relations}
                _emit_list(page, args.limit, getattr(args, "bare", False))
            else:
                db_meta = client.get_database(args.database_id)
                print(client.database_items_to_markdown(results, db_meta, relations))
                print(
                    f"_{len(results)} items, truncated: "
                    f"{str(bool(page.get('has_more'))).lower()}_"
                )

        elif cmd == "create":
            content = args.content
            if args.file:
                content = Path(args.file).read_text(encoding="utf-8")
            page = client.create_page(args.parent_id, args.title, content=content, is_database=args.database)
            print(json.dumps(page, indent=2, ensure_ascii=False))

        elif cmd == "update":
            if args.title:
                result = client.update_page(args.page_id, title=args.title)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            if args.append or args.file:
                content = args.append
                if args.file:
                    content = Path(args.file).read_text(encoding="utf-8")
                if args.replace:
                    client.replace_page_content(args.page_id, content)
                    print("✓ Page content replaced")
                else:
                    blocks = client.markdown_to_blocks(content)
                    result = client.append_blocks(args.page_id, blocks)
                    print(json.dumps(result, indent=2, ensure_ascii=False))

        elif cmd == "get-database":
            db_meta = client.get_database(args.database_id)
            items = client.query_database(args.database_id, limit=args.limit)
            if args.format == "json":
                print(json.dumps(items, indent=2, ensure_ascii=False))
            else:
                print(client.database_items_to_markdown(items, db_meta))

        elif cmd == "find-databases":
            databases = client.find_databases_on_page(args.page_id)
            if args.format == "json":
                print(json.dumps(databases, indent=2, ensure_ascii=False))
            else:
                if not databases:
                    print("No databases found on this page")
                else:
                    for i, db in enumerate(databases, 1):
                        print(f"{i}. **{db['title']}** ({db['type']}) — `{db['database_id']}`")

        elif cmd == "find-project-tasks":
            filter_dict = {"property": "Project", "relation": {"contains": args.project_page_id}}
            tasks = client.query_database(args.database_id, filter_dict=filter_dict, limit=args.limit)
            if args.format == "json":
                print(json.dumps(tasks, indent=2, ensure_ascii=False))
            else:
                if not tasks:
                    print(f"No tasks found for project {args.project_page_id}")
                else:
                    db_meta = client.get_database(args.database_id)
                    print(f"Found {len(tasks)} task(s):\n")
                    print(client.database_items_to_markdown(tasks, db_meta))

        elif cmd == "sync":
            blocks = client.get_blocks(args.page_id)
            markdown = client.blocks_to_markdown(blocks)
            if getattr(args, "preserve_metadata", False):
                page = client.get_page(args.page_id)
                frontmatter = (
                    f"---\n"
                    f"notion_id: {args.page_id}\n"
                    f"created: {page.get('created_time', '')}\n"
                    f"modified: {page.get('last_edited_time', '')}\n"
                    f"---\n\n"
                )
                markdown = frontmatter + markdown
            out = Path(args.output_file)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(markdown, encoding="utf-8")
            print(f"Synced to {out}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# ingest: calendar
# ---------------------------------------------------------------------------

def _add_calendar_subparser(ingest_sub: argparse.Action) -> None:
    p = ingest_sub.add_parser("calendar", help="Google Calendar operations")
    cmds = p.add_subparsers(dest="calendar_cmd")

    lp = cmds.add_parser("list", help="List upcoming events")
    lp.add_argument("--days", type=int, default=1, help="window of N days from local midnight")
    lp.add_argument("--max", type=int, default=20)
    lp.add_argument("--json", dest="as_json", action="store_true")
    lp.add_argument("--bare", action="store_true", help="emit a plain array, no envelope")

    sp = cmds.add_parser("search", help="Search events")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=10)
    sp.add_argument("--json", dest="as_json", action="store_true")
    sp.add_argument("--bare", action="store_true", help="emit a plain array, no envelope")

    cp = cmds.add_parser("create", help="Create event")
    cp.add_argument("summary")
    cp.add_argument("date", help="YYYY-MM-DD")
    cp.add_argument("time", help="HH:MM")
    cp.add_argument("--duration", type=int, default=60)
    cp.add_argument("--description")
    cp.add_argument("--attendees")
    cp.add_argument("--tz", default="Asia/Jerusalem")

    dp = cmds.add_parser("delete", help="Delete event by ID")
    dp.add_argument("event_id")
    dp.add_argument("--confirm", action="store_true")

    gp = cmds.add_parser("get", help="Get event by ID")
    gp.add_argument("event_id")


def _cmd_calendar(args: argparse.Namespace) -> int:
    from clients.calendar import CalendarClient

    cmd = args.calendar_cmd
    if not cmd:
        print("error: calendar requires a subcommand (list, search, create, delete, get)", file=sys.stderr)
        return 2

    try:
        client = CalendarClient()

        if cmd == "list":
            page = client.list_events_page(days=args.days, max_results=args.max)
            events = page["items"]
            if getattr(args, "as_json", False):
                _emit_list(page, args.max, getattr(args, "bare", False))
            else:
                if not events:
                    print("No events found.")
                else:
                    for e in events:
                        dur = f" ({e['duration_min']}min)" if e["duration_min"] else ""
                        loc = f" @ {e['location']}" if e["location"] else ""
                        span = (
                            f" [день {e['day_index']} из {e['days_total']}]"
                            if e.get("multi_day") and e.get("ongoing")
                            else ""
                        )
                        print(f"• {e['date']} {e['time']}: **{e['summary']}**{dur}{loc}{span}")
                        if e["description"]:
                            print(f"  {e['description'][:80]}")

        elif cmd == "search":
            page = client.search_events_page(args.query, max_results=args.max)
            events = page["items"]
            if getattr(args, "as_json", False):
                _emit_list(page, args.max, getattr(args, "bare", False))
            else:
                if not events:
                    print(f"No events matching '{args.query}'")
                else:
                    for e in events:
                        print(f"• {e['date']} {e['time']}: **{e['summary']}** (ID: {e['id']})")

        elif cmd == "create":
            event = client.create_event(
                summary=args.summary,
                date=args.date,
                time=args.time,
                duration_min=args.duration,
                description=args.description,
                attendees=args.attendees,
                tz=args.tz,
            )
            print(f"✓ Event created: {event.get('summary')} (ID: {event['id']})")
            print(f"  Link: {event.get('htmlLink', 'N/A')}")

        elif cmd == "delete":
            if not args.confirm:
                event = client.get_event(args.event_id)
                print(f"Event: {event.get('summary', '(без названия)')}")
                print("Add --confirm to delete.")
            else:
                client.delete_event(args.event_id)
                print(f"✓ Event deleted: {args.event_id}")

        elif cmd == "get":
            event = client.get_event(args.event_id)
            print(json.dumps(event, ensure_ascii=False, indent=2))

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# ingest dispatcher
# ---------------------------------------------------------------------------

def _add_ingest_subparser(subparsers: argparse._SubParsersAction) -> None:
    ingest_p = subparsers.add_parser("ingest", help="Ingest/publish via service adapters")
    ingest_sub = ingest_p.add_subparsers(dest="source")
    _add_gmail_subparser(ingest_sub)
    _add_notion_subparser(ingest_sub)
    _add_calendar_subparser(ingest_sub)


def _cmd_ingest(args: argparse.Namespace) -> int:
    if not getattr(args, "source", None):
        print("error: ingest requires a source (gmail, notion, calendar)", file=sys.stderr)
        return 2
    if args.source == "gmail":
        return _cmd_gmail(args)
    elif args.source == "notion":
        return _cmd_notion(args)
    elif args.source == "calendar":
        return _cmd_calendar(args)
    else:
        print(f"error: unknown source '{args.source}'", file=sys.stderr)
        return 2


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(prog="h2t", description="h2t unified CLI")
    subparsers = parser.add_subparsers(dest="command")

    # gather
    gather_parser = subparsers.add_parser("gather", help="Run context gather for a skill")
    gather_parser.add_argument("skill", nargs="?", default="")
    gather_parser.add_argument("--cwd", default=".")
    gather_parser.add_argument("--format-briefing", action="store_true")
    gather_parser.add_argument(
        "--briefing-only",
        action="store_true",
        help="Emit hook-format 'BRIEFING:/GATHER_META:' text instead of full JSON (small, UTF-8 safe)",
    )

    # ingest
    _add_ingest_subparser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)

    if args.command == "gather":
        sys.exit(_cmd_gather(args))
    elif args.command == "ingest":
        sys.exit(_cmd_ingest(args))
    else:
        print(f"error: unknown command '{args.command}'", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
