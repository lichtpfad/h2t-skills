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
    p = subparsers.add_parser("dropbox", help="Dropbox folders and files over HTTP API v2 (read; upload, link, delete)")
    cmds = p.add_subparsers(dest="dropbox_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human")

    ap = cmds.add_parser("account", help="Show the account and its namespace ids")
    add_fmt(ap)

    link_help = ("a shared link (/sh/ or /scl/fo/); the path is then inside the linked "
                 "folder. Read-only")

    lp = cmds.add_parser("list", help="List a folder (path is from the Dropbox root)")
    lp.add_argument("path", nargs="?", default="", help='folder path, "" or "/" for the root')
    lp.add_argument("--link", default=None, help=link_help)
    lp.add_argument("--recursive", action="store_true")
    lp.add_argument("--limit", type=int, default=None)
    add_fmt(lp)

    mp = cmds.add_parser("meta", help="Show metadata for one path or shared link")
    mp.add_argument("path", nargs="?", default="")
    mp.add_argument("--link", default=None, help=link_help)
    add_fmt(mp)

    dp = cmds.add_parser("download", help="Stream a file to disk, online-only placeholders included")
    dp.add_argument("path")
    dp.add_argument("dest", nargs="?", default=None,
                    help="destination file or directory (default: a new file in the inbox place)")
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

    xp = cmds.add_parser("delete", help=("Delete files or folders; Dropbox keeps them in its "
                                         "deleted files, where they can be restored"))
    xp.add_argument("paths", nargs="+", help="paths from the Dropbox root")
    xp.add_argument("--confirm-delete", dest="confirm_delete", action="store_true",
                    help="required: acknowledge a delete in Dropbox (files/delete_v2)")
    xp.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="show what would be deleted and stop")
    add_fmt(xp)

    p.set_defaults(_handler=run)


RESTORE_NOTE = ("Dropbox keeps deleted items in its deleted files; restore them from there "
                "(dropbox.com, Deleted files).")


def _mb(n: int) -> str:
    return f"{n / (1 << 20):.1f} MB"


def _delete(client: Any, paths: list[str], dry_run: bool) -> dict:
    """Read every path's metadata and print the plan to stderr; --dry-run stops there.
    A path that is missing or fails is reported in its row and the rest go on; the
    command then fails with every row in the error details."""
    import sys

    from h2t_ops.connectors.dropbox.client import normalize_path
    from h2t_ops.core.errors import H2TError, NotFoundError, ProviderError, UsageError

    api_paths = [normalize_path(p) for p in paths]  # a bad argument stops before any request
    if not all(api_paths):
        raise UsageError("dropbox delete: the Dropbox root cannot be deleted; name a path")
    rows = []
    for api_path in api_paths:
        row: dict[str, Any] = {"path": api_path, "kind": None, "size": None}
        try:
            md = client.meta(api_path)
        except NotFoundError:
            row["status"] = "not found"
        except H2TError as exc:
            row["status"] = f"failed: {exc}"
        else:
            row.update(kind=md.get(".tag", ""), status="would delete", size=md.get("size"))
            if row["kind"] == "folder":
                try:
                    count = client.folder_count(api_path)
                except H2TError:
                    count = {"entries": None, "bytes": None, "complete": False}
                row.update(size=count["bytes"], entries=count["entries"],
                           entries_complete=count["complete"])
        rows.append(row)
        if row["status"] != "would delete":
            what = row["status"]
        elif row["kind"] == "folder" and row["entries"] is not None:
            more = "" if row["entries_complete"] else "+"
            what = f"folder, {row['entries']}{more} entries, {_mb(row['size'])}{more}"
        elif row["kind"] == "folder":
            what = "folder, entries not counted"
        else:
            what = f"{row['kind']}, {_mb(row['size'] or 0)}"
        print(f"{what}: {row['path']}", file=sys.stderr)

    if not dry_run:
        for row in rows:
            if row["status"] != "would delete":
                continue
            try:
                done = client.delete(row["path"])
            except H2TError as exc:
                row["status"] = f"failed: {exc}"
            else:
                row["status"] = ("deleted" if done.get("status") == "deleted"
                                 else "already gone (removed after it was listed)")
            print(f"{row['status']}: {row['path']}", file=sys.stderr)

    result = {"dry_run": dry_run, "items": rows, "restore": RESTORE_NOTE}
    bad = [r for r in rows if r["status"] == "not found" or r["status"].startswith("failed")]
    deleted = sum(1 for r in rows if r["status"] == "deleted")
    print(f"{deleted} deleted, {len(bad)} failed of {len(rows)}"
          f"{' (dry run)' if dry_run else ''}. {RESTORE_NOTE}", file=sys.stderr)
    if bad:
        msg = f"{len(bad)} of {len(rows)} paths failed: " + "; ".join(
            f"{r['path']}: {r['status']}" for r in bad)
        kind = NotFoundError if all(r["status"] == "not found" for r in bad) else ProviderError
        raise kind(msg, details=result)
    return result


def _upload(client: Any, local: str, dest: str) -> list[dict]:
    """A file goes to `dest`; a folder's files go under `dest` keeping their sub-paths.
    Progress goes to stderr, one line per file, so --json on stdout stays clean."""
    import sys
    from pathlib import Path

    from h2t_ops.core.errors import H2TError, ProviderError, UsageError

    src = Path(local)
    if src.is_file():
        return [client.upload(str(src), dest)]
    if not src.is_dir():
        raise UsageError(f"dropbox upload: no such file or folder: {local}")
    files = sorted(f for f in src.rglob("*") if f.is_file())
    if not files:
        raise UsageError(f"dropbox upload: {local} has no files")
    rows, failed = [], []
    for i, f in enumerate(files, 1):
        target = dest.rstrip("/") + "/" + f.relative_to(src).as_posix()
        print(f"[{i}/{len(files)}] {target}", file=sys.stderr)
        try:
            row = client.upload(str(f), target)
        except H2TError as exc:  # network, auth, size too: keep going; the summary fails loud
            failed.append(f"{target}: {exc}")
            print(f"  failed: {exc}", file=sys.stderr)
            continue
        rows.append(row)
        if str(row.get("status", "")).startswith("skipped"):
            print(f"{row['status']}: {target}", file=sys.stderr)
    counts = {k: sum(1 for r in rows if str(r.get("status", "")).startswith(k))
              for k in ("uploaded", "exists", "skipped")}
    print(f"{counts['uploaded']} uploaded, {counts['exists']} exists, "
          f"{counts['skipped']} skipped, {len(failed)} failed", file=sys.stderr)
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
    if cmd == "delete" and not getattr(args, "confirm_delete", False):
        raise UsageError("dropbox delete removes paths from Dropbox: --confirm-delete is "
                         "required, --dry-run included")
    link = getattr(args, "link", None)
    if cmd == "meta" and not (link or args.path):
        raise UsageError("dropbox meta: a path or --link is required")
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
    if cmd == "list" and link:
        entries = client.list_link(link, args.path, recursive=args.recursive,
                                   limit=args.limit)
        return [{**_entry_row(e), "path": e["link_path"],
                 "content_hash": e.get("content_hash")} for e in entries]
    if cmd == "list":
        entries = client.list_folder(args.path, recursive=args.recursive, limit=args.limit)
        return [_entry_row(e) for e in entries]
    if cmd == "meta" and link:
        return _entry_row(client.link_meta(link, args.path))
    if cmd == "meta":
        return _entry_row(client.meta(args.path))
    if cmd == "download":
        return client.download(args.path, args.dest, gunzip=args.gunzip)
    if cmd == "upload":
        return _upload(client, args.local, args.dest)
    if cmd == "link":
        return client.link(args.path)
    if cmd == "delete":
        return _delete(client, args.paths, args.dry_run)

    raise UsageError(f"unknown dropbox subcommand: {cmd!r}")
