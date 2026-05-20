"""Calendar CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

from typing import Any

PROVIDER = "calendar"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("calendar", help="Work with Google Calendar events")
    cmds = p.add_subparsers(dest="calendar_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/table, human = concise (default)")

    lp = cmds.add_parser("list", help="List upcoming events")
    lp.add_argument("--days", type=int, default=1)
    lp.add_argument("--max", type=int, default=20)
    add_fmt(lp)

    sp = cmds.add_parser("search", help="Search events by free-text query")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=10)
    add_fmt(sp)

    gp = cmds.add_parser("get", help="Get one event by id")
    gp.add_argument("event_id")
    add_fmt(gp)

    cp = cmds.add_parser("create", help="Create a primary-calendar event")
    cp.add_argument("summary")
    cp.add_argument("date", help="YYYY-MM-DD")
    cp.add_argument("time", help="HH:MM (24h)")
    cp.add_argument("--duration-min", dest="duration_min", type=int, default=60)
    cp.add_argument("--description")
    cp.add_argument("--attendees", help="comma-separated emails")
    cp.add_argument("--tz", default="Asia/Jerusalem")
    add_fmt(cp)

    dp = cmds.add_parser("delete", help="Delete an event by id")
    dp.add_argument("event_id")
    dp.add_argument("--confirm", action="store_true",
                    help="required for non-interactive delete (parity with legacy)")
    add_fmt(dp)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a calendar subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.calendar.client import CalendarClient  # lazy (spec §4.1)
    from h2t_ops.core.errors import UsageError

    client = CalendarClient()
    cmd = args.calendar_cmd

    if cmd == "list":
        return client.list_events(days=args.days, max_results=args.max)
    if cmd == "search":
        return client.search_events(args.query, max_results=args.max)
    if cmd == "get":
        return client.get_event(args.event_id)
    if cmd == "create":
        return client.create_event(
            summary=args.summary, date=args.date, time=args.time,
            duration_min=args.duration_min, description=args.description,
            attendees=args.attendees, tz=args.tz,
        )
    if cmd == "delete":
        if not getattr(args, "confirm", False):
            raise UsageError(
                "calendar delete: --confirm is required for non-interactive delete",
            )
        client.delete_event(args.event_id)
        return {"deleted": args.event_id}
    raise UsageError(f"unknown calendar subcommand: {cmd}")
