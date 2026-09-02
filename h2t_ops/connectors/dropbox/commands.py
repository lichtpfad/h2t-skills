"""Dropbox CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

from typing import Any

PROVIDER = "dropbox"


def _entry_row(entry: dict) -> dict:
    return {
        "kind": entry.get(".tag", ""),
        "path": entry.get("path_display") or entry.get("path_lower", ""),
        "name": entry.get("name", ""),
        "size": entry.get("size"),
        "modified": entry.get("client_modified", ""),
    }


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("dropbox", help="Read Dropbox folders and files over HTTP API v2")
    cmds = p.add_subparsers(dest="dropbox_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human")

    ap = cmds.add_parser("account", help="Show the account and its namespace ids")
    add_fmt(ap)

    lp = cmds.add_parser("list", help="List a folder (path is from the Dropbox root)")
    lp.add_argument("path", nargs="?", default="", help='folder path, "" or "/" for the root')
    lp.add_argument("--recursive", action="store_true")
    lp.add_argument("--limit", type=int, default=None)
    add_fmt(lp)

    mp = cmds.add_parser("meta", help="Show metadata for one path")
    mp.add_argument("path")
    add_fmt(mp)

    dp = cmds.add_parser("download", help="Stream a file to disk, online-only placeholders included")
    dp.add_argument("path")
    dp.add_argument("dest", help="destination file or directory")
    dp.add_argument("--gunzip", action="store_true",
                    help="decompress gzip content stored under a plain name (.prproj)")
    add_fmt(dp)

    p.set_defaults(_handler=run)


def run(args: Any) -> Any:
    """Dispatch a dropbox subcommand. Returns result or raises core.errors."""
    from h2t_ops.connectors.dropbox.client import DropboxClient  # lazy

    client = DropboxClient()
    cmd = args.dropbox_cmd

    if cmd == "account":
        acc = client.account()
        root_info = acc.get("root_info") or {}
        return {
            "account_id": acc.get("account_id", ""),
            "email": acc.get("email", ""),
            "team": (acc.get("team") or {}).get("name", ""),
            "root_namespace_id": root_info.get("root_namespace_id", ""),
            "home_namespace_id": root_info.get("home_namespace_id", ""),
            "path_root_applied": client.path_root(),
        }
    if cmd == "list":
        entries = client.list_folder(args.path, recursive=args.recursive, limit=args.limit)
        return [_entry_row(e) for e in entries]
    if cmd == "meta":
        return _entry_row(client.meta(args.path))
    if cmd == "download":
        return client.download(args.path, args.dest, gunzip=args.gunzip)

    from h2t_ops.core.errors import UsageError
    raise UsageError(f"unknown dropbox subcommand: {cmd!r}")
