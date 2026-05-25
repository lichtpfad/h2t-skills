"""Gmail CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from typing import Any

PROVIDER = "gmail"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("gmail", help="Work with Gmail messages and labels")
    cmds = p.add_subparsers(dest="gmail_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown detail, human = concise (default)")

    lp = cmds.add_parser("list", help="List messages")
    lp.add_argument("--max", type=int, default=10)
    lp.add_argument("--unread", action="store_true")
    lp.add_argument("--query", default=None); add_fmt(lp)

    rp = cmds.add_parser("read", help="Read a message")
    rp.add_argument("message_id"); add_fmt(rp)

    tp = cmds.add_parser("threads", help="List threads")
    tp.add_argument("--max", type=int, default=10)
    tp.add_argument("--unread", action="store_true")
    tp.add_argument("--query", default=None); add_fmt(tp)

    thp = cmds.add_parser("thread", help="Read a thread")
    thp.add_argument("thread_id"); add_fmt(thp)

    ap = cmds.add_parser("attachment", help="Download a message attachment")
    ap.add_argument("message_id")
    ap.add_argument("attachment_id")
    ap.add_argument("--output", required=True)
    add_fmt(ap)

    sp = cmds.add_parser("search", help="Search messages")
    sp.add_argument("query"); sp.add_argument("--max", type=int, default=10); add_fmt(sp)

    snp = cmds.add_parser("send", help="Send a message")
    snp.add_argument("to"); snp.add_argument("subject"); snp.add_argument("body", nargs="?")
    snp.add_argument("--file"); snp.add_argument("--attach", nargs="+")
    snp.add_argument("--thread-id", dest="thread_id")
    snp.add_argument("--reply-to", dest="reply_to")
    snp.add_argument("--draft", action="store_true"); add_fmt(snp)

    dp = cmds.add_parser("draft", help="Create a draft")
    dp.add_argument("to"); dp.add_argument("subject"); dp.add_argument("body", nargs="?")
    dp.add_argument("--file"); dp.add_argument("--attach", nargs="+")
    dp.add_argument("--thread-id", dest="thread_id")
    dp.add_argument("--reply-to", dest="reply_to"); add_fmt(dp)

    lbl = cmds.add_parser("labels", help="List all labels"); add_fmt(lbl)

    lm = cmds.add_parser("label", help="Modify message labels")
    lm.add_argument("message_id"); lm.add_argument("--add", nargs="+")
    lm.add_argument("--remove", nargs="+"); add_fmt(lm)

    trp = cmds.add_parser("trash", help="Move a thread to Trash (recoverable)")
    trp.add_argument("thread_id")
    trp.add_argument("--confirm-subject", dest="confirm_subject", required=True,
                     help="Exact thread subject — must match to proceed")
    add_fmt(trp)

    utp = cmds.add_parser("untrash", help="Restore a thread from Trash")
    utp.add_argument("thread_id"); add_fmt(utp)

    dlp = cmds.add_parser("delete", help="Permanently delete a thread (irreversible)")
    dlp.add_argument("thread_id")
    dlp.add_argument("--confirm-subject", dest="confirm_subject", required=True,
                     help="Exact thread subject — must match to proceed")
    dlp.add_argument("--confirm-permanent", dest="confirm_permanent", action="store_true",
                     help="Required — explicitly acknowledges permanent deletion")
    add_fmt(dlp)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a gmail subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.gmail.client import (  # lazy (spec §4.1)
        GmailClient, format_message_list, format_message_detail,
        format_thread_list, format_thread_detail,
    )
    from h2t_ops.core.errors import UsageError

    def _read_file(path):
        from pathlib import Path as _P
        try:
            return _P(path).read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise UsageError(f"file not found: {path}") from e

    client = GmailClient()
    cmd = args.gmail_cmd
    if cmd == "list":
        msgs = client.list_messages(
            max_results=args.max, query=args.query, unread_only=args.unread)
        return msgs if _fmt(args) == "json" else format_message_list(msgs)
    if cmd == "search":
        msgs = client.search_messages(args.query, max_results=args.max)
        return msgs if _fmt(args) == "json" else format_message_list(msgs)
    if cmd == "read":
        msg = client.get_message(args.message_id)
        return msg if _fmt(args) == "json" else format_message_detail(msg)
    if cmd == "threads":
        rows = client.list_threads(
            max_results=args.max, query=args.query, unread_only=args.unread)
        return rows if _fmt(args) == "json" else format_thread_list(rows)
    if cmd == "thread":
        row = client.get_thread(args.thread_id)
        return row if _fmt(args) == "json" else format_thread_detail(row)
    if cmd == "attachment":
        result = client.download_attachment(args.message_id, args.attachment_id, args.output)
        if _fmt(args) == "json":
            return result
        return f"✓ Attachment saved to {result['saved_path']}"
    if cmd in ("send", "draft"):
        body = _read_file(args.file) if args.file else args.body
        if not body:
            raise UsageError(f"{cmd}: provide body arg or --file")
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
        if _fmt(args) == "json":
            return {"id": result["id"], "draft": as_draft}
        return (f"✓ {'Draft created' if as_draft else 'Message sent'} "
                f"(ID: {result['id']})")
    if cmd == "labels":
        labels = client.list_labels()
        if _fmt(args) == "json":
            return labels
        lines = [f"Found {len(labels)} label(s):\n"]
        lines += [f"- {lb['name']} (ID: {lb['id']})" for lb in labels]
        return "\n".join(lines)
    if cmd == "label":
        result = client.modify_labels(
            message_id=args.message_id,
            add_labels=args.add,
            remove_labels=args.remove,
        )
        label_ids = result.get("labelIds", [])
        if _fmt(args) == "json":
            return {"labelIds": label_ids}
        return f"✓ Labels modified. Current: {', '.join(label_ids)}"
    if cmd == "trash":
        return client.trash_thread(args.thread_id, args.confirm_subject)
    if cmd == "untrash":
        return client.untrash_thread(args.thread_id)
    if cmd == "delete":
        if not args.confirm_permanent:
            raise UsageError(
                "gmail delete: --confirm-permanent required for irreversible deletion"
            )
        return client.delete_thread(args.thread_id, args.confirm_subject)
    raise UsageError(f"unknown gmail subcommand: {cmd}")
