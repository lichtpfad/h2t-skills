"""Telegram CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

from pathlib import Path
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

    send = cmds.add_parser("send", help="Send a text message to an entity")
    send.add_argument("entity")
    group = send.add_mutually_exclusive_group(required=True)
    group.add_argument("--message")
    group.add_argument("--file")
    add_json(send)

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

    search = cmds.add_parser("search", help="Discover public channels/users by keyword")
    search.add_argument("query", nargs="+", help="search keyword (multi-word: telegram search real estate defi)")
    search.add_argument("--limit", type=int, default=20, help="max results (default 20)")
    add_json(search)

    send_file = cmds.add_parser("send-file", help="Send a file attachment to an entity")
    send_file.add_argument("entity")
    send_file.add_argument("path", help="local file path to send")
    send_file.add_argument("--caption", default=None, help="optional caption for the file")
    send_file.add_argument(
        "--confirm-send",
        action="store_true",
        help="required safety flag to confirm file send",
    )
    add_json(send_file)

    download_media = cmds.add_parser(
        "download-media", help="Download a message attachment to a local directory"
    )
    download_media.add_argument("entity")
    download_media.add_argument("message_id", type=int)
    download_media.add_argument(
        "--out",
        dest="out",
        default=None,
        help="output directory (default: ~/Downloads)",
    )
    add_json(download_media)

    forward_msg = cmds.add_parser("forward-message", help="Forward a message to another entity")
    forward_msg.add_argument("to_entity", help="destination entity (username, chat id, or 'me')")
    forward_msg.add_argument("--from", dest="from_entity", required=True, help="source entity")
    forward_msg.add_argument("--message-id", dest="message_id", type=int, required=True)
    forward_msg.add_argument(
        "--confirm-forward",
        action="store_true",
        help="required safety flag to confirm message forward",
    )
    add_json(forward_msg)

    delete_msg = cmds.add_parser("delete-message", help="Delete a message (requires --confirm)")
    delete_msg.add_argument("entity")
    delete_msg.add_argument("message_id", type=int)
    delete_msg.add_argument(
        "--confirm",
        action="store_true",
        help="required safety flag to confirm deletion",
    )
    add_json(delete_msg)

    p.set_defaults(_handler=run)


def _rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"rows": rows, "count": len(rows)}


def run(args: Any) -> Any:
    """Dispatch a Telegram subcommand. Returns a result or raises core.errors."""
    from h2t_ops.core.errors import UsageError
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter

    def _read_file(path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise UsageError(f"file not found: {path}") from exc

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
    if cmd == "send":
        text = args.message if getattr(args, "message", None) is not None else _read_file(args.file)
        if not text or not text.strip():
            raise UsageError("telegram send: message text is required")
        result = client.send_message(args.entity, text.strip())
        if getattr(args, "as_json", False):
            return result
        return f"✓ Message sent (ID: {result['message_id']})"
    if cmd == "saved-messages":
        return _rows(client.list_saved_messages(limit=args.limit, days=args.days))
    if cmd == "mentions":
        return _rows(client.list_mentions(args.chat_ids, days=args.days, limit=args.limit))
    if cmd == "bootstrap":
        return client.bootstrap_dialogs(force=args.force)
    if cmd == "send-file":
        if not getattr(args, "confirm_send", False):
            raise UsageError(
                "telegram send-file requires --confirm-send flag to prevent accidental sends"
            )
        return client.send_file(args.entity, args.path, caption=getattr(args, "caption", None))
    if cmd == "download-media":
        return client.download_media(
            args.entity,
            args.message_id,
            out_dir=getattr(args, "out", None),
        )
    if cmd == "forward-message":
        if not getattr(args, "confirm_forward", False):
            raise UsageError(
                "telegram forward-message requires --confirm-forward flag to prevent accidental forwards"
            )
        return client.forward_message(
            args.to_entity,
            from_entity=args.from_entity,
            message_id=args.message_id,
        )
    if cmd == "delete-message":
        if not getattr(args, "confirm", False):
            raise UsageError(
                "telegram delete-message requires --confirm flag to prevent accidental deletion"
            )
        return client.delete_message(args.entity, args.message_id)
    if cmd == "search":
        return _rows(client.search_channels(" ".join(args.query), limit=args.limit))
    raise UsageError(f"unknown telegram subcommand: {cmd}")
