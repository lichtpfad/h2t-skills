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
            args.file, folder=args.folder, no_convert=args.no_convert,
        )
    if cmd == "upload-folder":
        return client.upload_folder(
            args.local_dir,
            parent_id=args.parent_id,
            dry_run=args.dry_run,
            update_existing=args.update_existing,
        )
    raise UsageError(f"unknown drive subcommand: {cmd}")
