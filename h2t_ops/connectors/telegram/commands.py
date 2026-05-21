"""Telegram CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

from typing import Any

PROVIDER = "telegram"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("telegram", help="Work with Telegram dialogs and messages")
    cmds = p.add_subparsers(dest="telegram_cmd", required=True)

    def add_json(sp: Any) -> None:
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
            help="human = concise default, md = markdown/detail output",
        )

    auth = cmds.add_parser("auth", help="Telegram auth/session operations")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)

    auth_status = auth_sub.add_parser("status", help="Check auth/session state")
    add_json(auth_status)
    auth_status.set_defaults(telegram_cmd="auth-status")

    auth_request = auth_sub.add_parser("request-code", help="Request Telegram login code")
    auth_request.add_argument("--phone", required=True)
    add_json(auth_request)
    auth_request.set_defaults(telegram_cmd="auth-request-code")

    auth_complete = auth_sub.add_parser("complete", help="Complete Telegram login")
    auth_complete.add_argument("--phone", required=True)
    auth_complete.add_argument("--code")
    auth_complete.add_argument("--password")
    add_json(auth_complete)
    auth_complete.set_defaults(telegram_cmd="auth-complete")

    dialogs = cmds.add_parser("dialogs", help="List Telegram dialogs")
    dialogs.add_argument("--limit", type=int, default=50)
    dialogs.add_argument("--kind", choices=["user", "group", "channel", "bot", "unknown"])
    add_json(dialogs)

    folders = cmds.add_parser("folders", help="List Telegram dialog folders")
    add_json(folders)

    messages = cmds.add_parser("messages", help="Read messages from an entity")
    messages.add_argument("entity")
    messages.add_argument("--days", type=int)
    messages.add_argument("--limit", type=int, default=200)
    add_json(messages)

    saved = cmds.add_parser("saved-messages", help="Read raw Telegram Saved Messages")
    saved.add_argument("--days", type=int)
    saved.add_argument("--limit", type=int, default=200)
    add_json(saved)

    mentions = cmds.add_parser("mentions", help="Read explicit chats for @mentions")
    mentions.add_argument("--chat-id", dest="chat_ids", action="append", required=True)
    mentions.add_argument("--days", type=int)
    mentions.add_argument("--limit", type=int, default=500)
    add_json(mentions)

    bootstrap = cmds.add_parser("bootstrap", help="Warm Telethon entity cache")
    bootstrap.add_argument("--force", action="store_true")
    add_json(bootstrap)

    p.set_defaults(_handler=run)


def _rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rows": rows, "count": len(rows)}


def run(args: Any) -> Any:
    """Dispatch a Telegram subcommand. Returns a result or raises core.errors."""
    from h2t_ops.core.errors import UsageError
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    client = TelegramClientAdapter()
    cmd = args.telegram_cmd
    if cmd == "auth-status":
        return client.auth_status()
    if cmd == "auth-request-code":
        return client.request_code(args.phone)
    if cmd == "auth-complete":
        return client.complete_auth(args.phone, code=args.code, password=args.password)
    if cmd == "dialogs":
        return _rows(client.list_dialogs(limit=args.limit, kind=args.kind))
    if cmd == "folders":
        return _rows(client.list_folders())
    if cmd == "messages":
        return _rows(client.list_messages(args.entity, limit=args.limit, days=args.days))
    if cmd == "saved-messages":
        return _rows(client.list_saved_messages(limit=args.limit, days=args.days))
    if cmd == "mentions":
        return _rows(client.list_mentions(args.chat_ids, days=args.days, limit=args.limit))
    if cmd == "bootstrap":
        return client.bootstrap_dialogs(force=args.force)
    raise UsageError(f"unknown telegram subcommand: {cmd}")
