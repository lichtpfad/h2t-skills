"""Calendar CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROVIDER = "calendar"


def _resolve_query_tz(tz: str | None) -> str:
    return tz or os.environ.get("H2T_CALENDAR_TZ") or "Asia/Jerusalem"


def _date_window_bounds(from_date: str, to_date: str, tz_name: str) -> tuple[str, str]:
    from h2t_ops.core.errors import UsageError

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise UsageError(
            f"Unknown calendar timezone: {tz_name}",
            hint="Install project dependencies with `uv sync`; Windows requires the tzdata package.",
        ) from exc
    try:
        start_day = date.fromisoformat(from_date)
        end_day = date.fromisoformat(to_date)
    except ValueError as exc:
        raise UsageError("calendar list: --from/--to must use YYYY-MM-DD") from exc
    if end_day < start_day:
        raise UsageError("calendar list: --to must be on or after --from")
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    return start.isoformat(), end.isoformat()


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
    lp.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD")
    lp.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD")
    lp.add_argument("--tz", default=None)
    lp.add_argument("--max", type=int, default=250)
    lp.add_argument("--busy-only", action="store_true",
                    help="exclude transparent/free events")
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
        time_min = None
        time_max = None
        tz = getattr(args, "tz", None)
        if bool(getattr(args, "from_date", None)) != bool(getattr(args, "to_date", None)):
            raise UsageError("calendar list: --from and --to must be used together")
        if getattr(args, "from_date", None):
            tz = _resolve_query_tz(tz)
            time_min, time_max = _date_window_bounds(args.from_date, args.to_date, tz)
        return client.list_events(
            days=args.days,
            max_results=args.max,
            time_min=time_min,
            time_max=time_max,
            tz=tz,
            busy_only=getattr(args, "busy_only", False),
        )
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
