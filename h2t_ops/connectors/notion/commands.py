"""Notion CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

PROVIDER = "notion"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("notion", help="Work with Notion pages and databases")
    cmds = p.add_subparsers(dest="notion_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/table, human = concise (default)")

    g = cmds.add_parser("get", help="Get page blocks as markdown")
    g.add_argument("page_id"); add_fmt(g)
    b = cmds.add_parser("blocks", help="Get page blocks")
    b.add_argument("page_id"); b.add_argument("--limit", type=int); add_fmt(b)
    s = cmds.add_parser("search", help="Query a database")
    s.add_argument("database_id"); s.add_argument("--filter")
    s.add_argument("--filter-json"); s.add_argument("--limit", type=int); add_fmt(s)
    gd = cmds.add_parser("get-database", help="Database items")
    gd.add_argument("database_id"); gd.add_argument("--limit", type=int); add_fmt(gd)
    sw = cmds.add_parser("search-workspace", help="Search shared Notion workspace objects")
    sw.add_argument("--object", choices=["page", "database", "data_source", "all"], default="all")
    sw.add_argument("--limit", type=int)
    add_fmt(sw)
    gr = cmds.add_parser("graph", help="Build a page subtree graph")
    gr.add_argument("root_page_id")
    gr.add_argument("--max-depth", type=int, default=3)
    db_group = gr.add_mutually_exclusive_group()
    db_group.add_argument("--include-databases", dest="include_databases",
                          action="store_true", default=True)
    db_group.add_argument("--no-include-databases", dest="include_databases",
                          action="store_false")
    gr.add_argument("--root-label")
    add_fmt(gr)
    fd = cmds.add_parser("find-databases", help="Find databases on a page")
    fd.add_argument("page_id")
    fd.add_argument("--recursive", action="store_true")
    fd.add_argument("--max-depth", type=int, default=3)
    fd.add_argument("--limit-blocks", type=int)
    fd.add_argument("--with-rows", action="store_true")
    fd.add_argument("--row-limit", type=int, default=100)
    add_fmt(fd)
    ft = cmds.add_parser("find-project-tasks",
                         help="List tasks whose Project relation points at <page_id>")
    ft.add_argument("project_page_id")
    ft.add_argument("--database-id", dest="database_id",
                    default="beabac7bf4314952a9327759c638d89f",
                    help="tasks database id (default: legacy workspace tasks db)")
    ft.add_argument("--limit", type=int)
    add_fmt(ft)
    c = cmds.add_parser("create", help="Create a page")
    c.add_argument("parent_id"); c.add_argument("title")
    c.add_argument("--content"); c.add_argument("--file")
    c.add_argument("--database", action="store_true"); add_fmt(c)
    u = cmds.add_parser("update", help="Update a page")
    u.add_argument("page_id"); u.add_argument("--title")
    u.add_argument("--append"); u.add_argument("--file")
    u.add_argument("--replace", action="store_true"); add_fmt(u)
    co = cmds.add_parser("comments", help="List top-level comments on a page")
    co.add_argument("page_id"); add_fmt(co)
    ca = cmds.add_parser("comment", help="Add a top-level comment to a page")
    ca.add_argument("page_id")
    ca.add_argument("--body", required=True, help="Comment text")
    add_fmt(ca)
    sy = cmds.add_parser("sync", help="Sync page to a markdown file")
    sy.add_argument("page_id"); sy.add_argument("output_file")
    sy.add_argument("--preserve-metadata", action="store_true")
    sy.add_argument("--include-databases", action="store_true")
    sy.add_argument("--recursive", action="store_true")
    sy.add_argument("--max-depth", type=int, default=3)
    sy.add_argument("--row-limit", type=int, default=100)
    sy.add_argument("--databases-json")
    add_fmt(sy)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a notion subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.notion.client import NotionClient  # lazy (spec §4.1)
    from h2t_ops.core.errors import UsageError

    def _read_file(path):
        from pathlib import Path as _P
        try:
            return _P(path).read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise UsageError(f"file not found: {path}") from e

    client = NotionClient()
    cmd = args.notion_cmd
    if cmd == "get":
        blocks = client.get_blocks(args.page_id)
        return blocks if _fmt(args) == "json" else client.blocks_to_markdown(blocks)
    if cmd == "blocks":
        blocks = client.get_blocks(args.page_id, limit=args.limit)
        return blocks if _fmt(args) == "json" else client.blocks_to_markdown(blocks)
    if cmd == "search":
        import json as _json
        fdict = None
        if args.filter_json:
            fdict = _json.loads(args.filter_json)
        elif args.filter and "=" in args.filter:
            k, _, v = args.filter.partition("=")
            fdict = {"property": k.strip(), "select": {"equals": v.strip()}}
        rows = client.query_database(args.database_id, filter_dict=fdict, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
    if cmd == "get-database":
        rows = client.query_database(args.database_id, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
    if cmd == "search-workspace":
        return client.search_workspace(object_type=args.object, limit=args.limit)
    if cmd == "graph":
        return client.graph_page(
            args.root_page_id,
            max_depth=args.max_depth,
            include_databases=args.include_databases,
            root_label=args.root_label,
        )
    if cmd == "find-databases":
        return client.find_databases_on_page(
            args.page_id,
            recursive=getattr(args, "recursive", False),
            max_depth=getattr(args, "max_depth", 3),
            limit_blocks=getattr(args, "limit_blocks", None),
            with_rows=getattr(args, "with_rows", False),
            row_limit=getattr(args, "row_limit", 100),
        )
    if cmd == "find-project-tasks":
        fdict = {"property": "Project", "relation": {"contains": args.project_page_id}}
        rows = client.query_database(args.database_id,
                                     filter_dict=fdict, limit=args.limit)
        return rows if _fmt(args) == "json" else client.database_items_to_markdown(
            rows, client.get_database(args.database_id))
    if cmd == "comments":
        return client.list_comments(args.page_id)
    if cmd == "comment":
        return client.create_comment(args.page_id, args.body)
    if cmd == "create":
        content = _read_file(args.file) if args.file else args.content
        return client.create_page(args.parent_id, args.title,
                                  content=content, is_database=args.database)
    if cmd == "update":
        out: dict = {}
        if args.title:
            out["title"] = client.update_page(args.page_id, title=args.title)
        if args.append or args.file:
            text = _read_file(args.file) if args.file else args.append
            if args.replace:
                client.replace_page_content(args.page_id, text)
                out["content"] = "replaced"
            else:
                out["content"] = client.append_blocks(
                    args.page_id, client.markdown_to_blocks(text))
        if not out:
            raise UsageError("update: specify --title, --append, or --file")
        return out
    if cmd == "sync":
        out_path = Path(args.output_file)
        sidecar = None
        if getattr(args, "databases_json", None):
            if not getattr(args, "include_databases", False):
                raise UsageError("sync: --databases-json requires --include-databases")
            sidecar = Path(args.databases_json)
            if out_path.resolve() == sidecar.resolve():
                raise UsageError("sync: output_file and --databases-json must be different paths")
        md = client.blocks_to_markdown(client.get_blocks(args.page_id))
        if args.preserve_metadata:
            pg = client.get_page(args.page_id)
            md = (f"---\nnotion_id: {args.page_id}\n"
                  f"created: {pg.get('created_time','')}\n"
                  f"modified: {pg.get('last_edited_time','')}\n---\n\n") + md
        discovery = None
        if getattr(args, "include_databases", False):
            discovery = client.find_databases_on_page(
                args.page_id,
                recursive=getattr(args, "recursive", False),
                max_depth=getattr(args, "max_depth", 3),
                with_rows=True,
                row_limit=getattr(args, "row_limit", 100),
            )
            lines = ["\n\n## Embedded databases\n\n"]
            for db in discovery.get("databases", []):
                lines.append(
                    f"- **{db.get('title', 'Untitled')}** "
                    f"({db.get('type', db.get('kind', 'database'))}) "
                    f"`{db.get('database_id', '')}` - rows: {db.get('row_count', 0)}\n"
                )
            md += "".join(lines)
        if sidecar is not None:
            import json as _json
            sidecar.parent.mkdir(parents=True, exist_ok=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        if sidecar is not None:
            sidecar.write_text(
                _json.dumps(discovery, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return f"Synced to {out_path}"
    raise UsageError(f"unknown notion subcommand: {cmd}")
