"""Drive CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from typing import Any

PROVIDER = "drive"

EXPORT_FORMATS = ("text", "csv", "md", "docx", "xlsx", "pdf", "pptx")
PRINT_ALLOWED_FORMATS = frozenset({"text", "csv", "md"})


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("drive", help="Work with Google Drive files")
    cmds = p.add_subparsers(dest="drive_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/detail output, human = concise default")

    lp = cmds.add_parser("list", help="List files in a folder")
    lp.add_argument("folder", nargs="?")
    lp.add_argument("--max", type=int)
    add_fmt(lp)

    sp = cmds.add_parser("search", help="Search Drive files")
    sp.add_argument("query")
    sp.add_argument("--type", dest="mime_filter", choices=["docx", "folder"])
    sp.add_argument("--max", type=int)
    add_fmt(sp)

    fp = cmds.add_parser("folders", help="List Drive folders")
    fp.add_argument("parent", nargs="?")
    fp.add_argument("--max", type=int, default=50)
    add_fmt(fp)

    cfp = cmds.add_parser("create-folder", help="Create a folder under Drive root or a parent folder")
    cfp.add_argument("name")
    cfp.add_argument("--parent")
    add_fmt(cfp)

    rp = cmds.add_parser("rename", help="Rename a Drive file in place")
    rp.add_argument("file_id")
    rp.add_argument("new_name")
    add_fmt(rp)

    cp = cmds.add_parser("copy", help="Copy a Drive file")
    cp.add_argument("file_id")
    cp.add_argument("--name", dest="new_name")
    cp.add_argument("--folder")
    add_fmt(cp)

    mp = cmds.add_parser("move", help="Move a Drive file to another folder")
    mp.add_argument("file_id")
    mp.add_argument("--to", dest="destination_folder_id", required=True)
    add_fmt(mp)

    # get-file
    gfp = cmds.add_parser("get-file", help="Get metadata for a Drive file by id")
    gfp.add_argument("file_id")
    add_fmt(gfp)

    # trash
    trp = cmds.add_parser("trash", help="Move a Drive file to trash (recoverable)")
    trp.add_argument("file_id")
    trp.add_argument("--confirm-name", required=True, metavar="NAME",
                     help="Exact name of the file to trash (safety guard)")
    add_fmt(trp)

    # delete
    delp = cmds.add_parser("delete", help="Permanently delete a Drive file (irreversible)")
    delp.add_argument("file_id")
    delp.add_argument("--confirm-name", required=True, metavar="NAME",
                      help="Exact name of the file to delete (safety guard)")
    delp.add_argument("--confirm-permanent", action="store_true",
                      help="Acknowledge that deletion is permanent and irreversible")
    add_fmt(delp)

    # docs (create subcommand group)
    docp = cmds.add_parser("docs", help="Create Google Docs editor files")
    doccmds = docp.add_subparsers(dest="docs_cmd", required=True)
    dcc = doccmds.add_parser("create", help="Create a new Google Doc")
    dcc.add_argument("title")
    dcc.add_argument("--folder-id", dest="folder_id", metavar="ID",
                     help="Parent folder id (optional)")
    add_fmt(dcc)

    dtp = cmds.add_parser("docs-tab", help="Inspect Google Docs tabs")
    dtcmds = dtp.add_subparsers(dest="docs_tab_cmd", required=True)
    dtl = dtcmds.add_parser("list", help="List tabs in a Google Doc")
    dtl.add_argument("document_id")
    add_fmt(dtl)
    dta = dtcmds.add_parser("add", help="Add a new tab to a Google Doc")
    dta.add_argument("document_id")
    dta.add_argument("title")
    add_fmt(dta)
    dtr = dtcmds.add_parser("read", help="Read text content of a specific tab")
    dtr.add_argument("document_id")
    dtr.add_argument("tab_id")
    add_fmt(dtr)
    dtw = dtcmds.add_parser("write", help="Write markdown content to an existing tab")
    dtw.add_argument("document_id")
    dtw.add_argument("tab_id")
    dtw.add_argument("--content-file", required=True, metavar="PATH",
                     help="Path to a markdown file whose content is written into the tab")
    dtw.add_argument("--clear-first", action="store_true",
                     help="Delete existing tab content before writing (replaces instead of append)")
    add_fmt(dtw)

    dp = cmds.add_parser("download", help="Download a Drive file by id")
    dp.add_argument("file_id")
    dp.add_argument("--dest")
    add_fmt(dp)

    ep = cmds.add_parser("export", help="Export a Google Docs editor file")
    ep.add_argument("file_id")
    ep.add_argument("--dest")
    ep.add_argument("--format", dest="export_format", choices=EXPORT_FORMATS)
    ep.add_argument("--print", dest="print_stdout", action="store_true")
    ep.add_argument("--json", dest="as_json", action="store_true",
                    help="raw machine-readable envelope")

    up = cmds.add_parser("upload", help="Upload a file to Drive")
    up.add_argument("file")
    up.add_argument("--folder", required=True)
    up.add_argument("--no-convert", action="store_true")
    up.add_argument("--update-existing", action="store_true",
                    help="Update existing same-name file instead of skipping")
    up.add_argument("--parent-id", dest="parent_id", metavar="ID",
                    help="Destination folder id (alternative to --folder name)")
    add_fmt(up)

    ufp = cmds.add_parser(
        "upload-folder",
        help="Recursively upload a local folder to Drive preserving relative paths",
    )
    ufp.add_argument("local_dir", help="Local folder to upload recursively")
    ufp.add_argument(
        "--parent-id",
        required=True,
        help="Destination Drive folder id. Use the folder id from the Drive URL.",
    )
    ufp.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan folder/file actions without creating or uploading anything",
    )
    ufp.add_argument(
        "--update-existing",
        action="store_true",
        help="Update same-name files under the same Drive folder instead of skipping",
    )
    add_fmt(ufp)

    shp = cmds.add_parser("share", help="Share a Drive file or inspect its permission state")
    shp.add_argument("file_id", help="Drive file ID")
    mode_group = shp.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--email", metavar="ADDR",
        help="Invite a specific user by email",
    )
    mode_group.add_argument(
        "--anyone", action="store_true",
        help="Open link access (anyone with the link); requires --confirm-public",
    )
    mode_group.add_argument(
        "--get-link", action="store_true", dest="get_link",
        help="Return webViewLink and permission state (read-only)",
    )
    shp.add_argument(
        "--role", choices=["reader", "writer", "commenter"], default="reader",
        help="Permission role (default: reader); applies to --email and --anyone; not valid with --get-link",
    )
    shp.add_argument(
        "--confirm-public", action="store_true", dest="confirm_public",
        help="Required with --anyone; explicitly acknowledges public exposure",
    )
    add_fmt(shp)

    p.set_defaults(_handler=run)


def _rows(rows):
    return {"rows": rows, "count": len(rows)}


def run(args) -> Any:
    """Dispatch a drive subcommand. Returns a result or raises core.errors."""
    from h2t_ops.core.errors import UsageError

    cmd = args.drive_cmd

    if cmd == "export" and getattr(args, "print_stdout", False):
        fmt = getattr(args, "export_format", None)
        if fmt in {"docx", "xlsx", "pdf", "pptx"}:
            raise UsageError(f"drive export --print cannot use binary format: {fmt}")

    if cmd == "share":
        if args.get_link and args.role != "reader":
            raise UsageError("--role cannot be used with --get-link")
        if args.anyone and not args.confirm_public:
            raise UsageError(
                "--anyone requires --confirm-public to prevent accidental public exposure"
            )

    if cmd == "delete" and not getattr(args, "confirm_permanent", False):
        raise UsageError(
            "drive delete requires --confirm-permanent to acknowledge irreversible deletion"
        )

    from h2t_ops.connectors.drive.client import DriveClient  # lazy (spec §4.1)

    client = DriveClient()
    if cmd == "list":
        return _rows(client.list_files(folder=args.folder, max_results=args.max))
    if cmd == "search":
        return _rows(client.search_files(
            args.query, mime_filter=args.mime_filter, max_results=args.max,
        ))
    if cmd == "folders":
        return _rows(client.list_folders(parent=args.parent, max_results=args.max))
    if cmd == "create-folder":
        return client.create_folder(args.name, parent=args.parent)
    if cmd == "rename":
        return client.rename_file(args.file_id, args.new_name)
    if cmd == "copy":
        return client.copy_file(
            args.file_id,
            new_name=args.new_name,
            folder=args.folder,
        )
    if cmd == "move":
        return client.move_file(
            args.file_id,
            destination_folder_id=args.destination_folder_id,
        )
    if cmd == "get-file":
        return client.get_file(args.file_id)
    if cmd == "trash":
        return client.trash_file(args.file_id, confirm_name=args.confirm_name)
    if cmd == "delete":
        return client.delete_file(args.file_id, confirm_name=args.confirm_name)
    if cmd == "docs":
        if args.docs_cmd == "create":
            return client.create_document(
                args.title,
                folder_id=getattr(args, "folder_id", None),
            )
        raise UsageError(f"unknown drive docs subcommand: {args.docs_cmd}")
    if cmd == "docs-tab":
        if args.docs_tab_cmd == "list":
            return client.list_document_tabs(args.document_id)
        if args.docs_tab_cmd == "add":
            return client.add_document_tab(args.document_id, args.title)
        if args.docs_tab_cmd == "read":
            return client.read_tab(args.document_id, args.tab_id)
        if args.docs_tab_cmd == "write":
            from pathlib import Path as _Path
            content = _Path(args.content_file).read_text(encoding="utf-8")
            clear_first = getattr(args, "clear_first", False)
            return client.write_document_tab(
                args.document_id, args.tab_id, content, clear_first=clear_first,
            )
        raise UsageError(f"unknown drive docs-tab subcommand: {args.docs_tab_cmd}")
    if cmd == "download":
        return client.download_file(args.file_id, dest=args.dest)
    if cmd == "export":
        result = client.export_file(
            args.file_id,
            fmt=args.export_format,
            dest=args.dest,
            to_stdout=args.print_stdout,
        )
        if args.print_stdout and not getattr(args, "as_json", False):
            return result.get("text", "") if isinstance(result, dict) else result
        return result
    if cmd == "upload":
        return client.upload_file(
            args.file,
            folder=args.folder,
            no_convert=args.no_convert,
            update_existing=getattr(args, "update_existing", False),
            parent_id=getattr(args, "parent_id", None),
        )
    if cmd == "upload-folder":
        return client.upload_folder(
            args.local_dir,
            parent_id=args.parent_id,
            dry_run=args.dry_run,
            update_existing=args.update_existing,
        )
    if cmd == "share":
        return client.share_file(
            args.file_id,
            email=args.email,
            role=args.role,
            anyone=args.anyone,
            get_link=args.get_link,
        )
    raise UsageError(f"unknown drive subcommand: {cmd}")
