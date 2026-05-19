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

    sp = cmds.add_parser("search", help="Search messages")
    sp.add_argument("query"); sp.add_argument("--max", type=int, default=10); add_fmt(sp)

    snp = cmds.add_parser("send", help="Send a message")
    snp.add_argument("to"); snp.add_argument("subject"); snp.add_argument("body", nargs="?")
    snp.add_argument("--file"); snp.add_argument("--attach", nargs="+")
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

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a gmail subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.gmail.client import (  # lazy (spec §4.1)
        GmailClient, format_message_list, format_message_detail,
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
    if cmd in ("send", "draft"):
        body = args.body or (_read_file(args.file) if args.file else None)
        if not body:
            raise UsageError("send: provide body arg or --file")
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
    raise UsageError(f"unknown gmail subcommand: {cmd}")
