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
    p = subparsers.add_parser("dropbox", help="Dropbox folders and files over HTTP API v2 (read; upload, link)")
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

    up = cmds.add_parser("upload", help="Upload a local file or folder; never overwrites")
    up.add_argument("local", help="local file, or folder (its files go under dest, same layout)")
    up.add_argument("dest", help="destination path from the Dropbox root")
    up.add_argument("--confirm-write", dest="confirm_write", action="store_true",
                    help="required: acknowledge a write to Dropbox")
    add_fmt(up)

    kp = cmds.add_parser("link", help="Existing shared link, or a new public one")
    kp.add_argument("path")
    kp.add_argument("--confirm-public", dest="confirm_public", action="store_true",
                    help="required: the link opens the file to anyone who has it")
    add_fmt(kp)

    p.set_defaults(_handler=run)


def _upload(client: Any, local: str, dest: str) -> list[dict]:
    """A file goes to `dest`; a folder's files go under `dest` keeping their sub-paths."""
    from pathlib import Path

    from h2t_ops.core.errors import ProviderError, UsageError

    src = Path(local)
    if src.is_file():
        return [client.upload(str(src), dest)]
    if not src.is_dir():
        raise UsageError(f"dropbox upload: no such file or folder: {local}")
    files = sorted(f for f in src.rglob("*") if f.is_file())
    if not files:
        raise UsageError(f"dropbox upload: {local} has no files")
    rows, failed = [], []
    for f in files:
        target = dest.rstrip("/") + "/" + f.relative_to(src).as_posix()
        try:
            rows.append(client.upload(str(f), target))
        except ProviderError as exc:  # keep going; the summary below fails loud
            failed.append(f"{target}: {exc}")
    if failed:
        raise ProviderError(f"{len(failed)} of {len(files)} uploads failed: " + "; ".join(failed))
    return rows


def run(args: Any) -> Any:
    """Dispatch a dropbox subcommand. Returns result or raises core.errors."""
    from h2t_ops.connectors.dropbox.client import DropboxClient  # lazy
    from h2t_ops.core.errors import UsageError

    cmd = args.dropbox_cmd
    # refused before a client exists: no token is read, no request is sent
    if cmd == "upload" and not getattr(args, "confirm_write", False):
        raise UsageError("dropbox upload writes to Dropbox: --confirm-write is required")
    if cmd == "link" and not getattr(args, "confirm_public", False):
        raise UsageError("dropbox link opens the path to anyone with the link: "
                         "--confirm-public is required")
    client = DropboxClient()

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
    if cmd == "upload":
        return _upload(client, args.local, args.dest)
    if cmd == "link":
        return client.link(args.path)

    raise UsageError(f"unknown dropbox subcommand: {cmd!r}")
