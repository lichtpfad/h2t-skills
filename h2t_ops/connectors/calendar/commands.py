"""Calendar CLI adapter. argparse only at module scope; client imported in handlers."""
from __future__ import annotations

import argparse
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
        raise UsageError("calendar: --from/--to must use YYYY-MM-DD") from exc
    if end_day < start_day:
        raise UsageError("calendar: --to must be on or after --from")
    start = datetime.combine(start_day, time.min, tzinfo=tz)
    end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)
    return start.isoformat(), end.isoformat()


def _parse_minutes(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    from h2t_ops.core.errors import UsageError

    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError as exc:
        raise UsageError("calendar: reminder minutes must be integers") from exc


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("calendar", help="Work with Google Calendar events")
    cmds = p.add_subparsers(dest="calendar_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human",
                        help="md = markdown/table, human = concise (default)")

    def add_calendar_id(sp):
        sp.add_argument("--calendar-id", default="primary")

    clp = cmds.add_parser("calendars", help="List available calendars")
    add_fmt(clp)

    lp = cmds.add_parser("list", help="List upcoming events")
    lp.add_argument("--days", type=int, default=1)
    lp.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD")
    lp.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD")
    lp.add_argument("--tz", default=None)
    lp.add_argument("--max", type=int, default=250)
    lp.add_argument("--busy-only", action="store_true",
                    help="exclude transparent/free events")
    add_calendar_id(lp)
    add_fmt(lp)

    sp = cmds.add_parser("search", help="Search events by free-text query")
    sp.add_argument("query")
    sp.add_argument("--max", type=int, default=10)
    add_calendar_id(sp)
    add_fmt(sp)

    gp = cmds.add_parser("get", help="Get one event by id")
    gp.add_argument("event_id")
    add_calendar_id(gp)
    add_fmt(gp)

    cp = cmds.add_parser("create", help="Create a calendar event")
    cp.add_argument("summary")
    cp.add_argument("date", help="YYYY-MM-DD")
    cp.add_argument("time", nargs="?", help="HH:MM (24h)")
    cp.add_argument("--duration-min", dest="duration_min", type=int, default=60)
    cp.add_argument("--duration", dest="duration_min", type=int, help=argparse.SUPPRESS)
    cp.add_argument("--all-day", action="store_true")
    cp.add_argument("--description")
    cp.add_argument("--location")
    cp.add_argument("--attendees", help="comma-separated emails")
    cp.add_argument("--meet", action="store_true")
    cp.add_argument("--rrule")
    cp.add_argument("--reminder-minutes")
    cp.add_argument("--tz", default="Asia/Jerusalem")
    add_calendar_id(cp)
    add_fmt(cp)

    up = cmds.add_parser("update", help="Patch or reschedule an event")
    up.add_argument("event_id")
    up.add_argument("--summary")
    up.add_argument("--date", dest="date")
    up.add_argument("--time")
    up.add_argument("--duration-min", dest="duration_min", type=int)
    up.add_argument("--all-day", action="store_true", default=None)
    up.add_argument("--description")
    up.add_argument("--location")
    up.add_argument("--replace-attendees")
    up.add_argument("--meet", action="store_true")
    up.add_argument("--replace-rrule")
    up.add_argument("--replace-reminders")
    up.add_argument("--clear-reminders", action="store_true")
    up.add_argument("--tz", default=None)
    add_calendar_id(up)
    add_fmt(up)

    dp = cmds.add_parser("delete", help="Delete an event by id")
    dp.add_argument("event_id")
    dp.add_argument("--confirm", action="store_true",
                    help="required for non-interactive delete (parity with legacy)")
    add_calendar_id(dp)
    add_fmt(dp)

    fb = cmds.add_parser("freebusy", help="Query raw calendar busy windows")
    fb.add_argument("--from", dest="from_date", required=True, metavar="YYYY-MM-DD")
    fb.add_argument("--to", dest="to_date", required=True, metavar="YYYY-MM-DD")
    fb.add_argument("--tz", default=None)
    fb.add_argument("--calendar-id", action="append", default=None)
    add_fmt(fb)

    p.set_defaults(_handler=run)


def _fmt(args) -> str:
    return "json" if getattr(args, "as_json", False) else getattr(args, "fmt", "human")


def run(args) -> Any:
    """Dispatch a calendar subcommand. Returns a result or raises core.errors."""
    from h2t_ops.connectors.calendar.client import CalendarClient  # lazy (spec §4.1)
    from h2t_ops.core.errors import UsageError

    cmd = args.calendar_cmd
    if cmd == "delete" and not getattr(args, "confirm", False):
        raise UsageError("calendar delete: --confirm is required for non-interactive delete")
    if cmd == "create":
        if getattr(args, "all_day", False) and getattr(args, "time", None):
            raise UsageError("calendar create: --all-day rejects time")
        if not getattr(args, "all_day", False) and not getattr(args, "time", None):
            raise UsageError("calendar create: timed create requires time")

    client = CalendarClient()

    if cmd == "calendars":
        return client.list_calendars()
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
            calendar_id=args.calendar_id,
            time_min=time_min,
            time_max=time_max,
            tz=tz,
            busy_only=getattr(args, "busy_only", False),
        )
    if cmd == "search":
        return client.search_events(
            args.query,
            calendar_id=args.calendar_id,
            max_results=args.max,
        )
    if cmd == "get":
        return client.get_event(args.event_id, calendar_id=args.calendar_id)
    if cmd == "create":
        try:
            return client.create_event(
                summary=args.summary,
                date=args.date,
                time=args.time,
                duration_min=args.duration_min,
                description=args.description,
                attendees=args.attendees,
                tz=args.tz,
                calendar_id=args.calendar_id,
                all_day=args.all_day,
                location=args.location,
                meet=args.meet,
                rrule=args.rrule,
                reminder_minutes=_parse_minutes(args.reminder_minutes),
            )
        except ValueError as exc:
            raise UsageError(f"calendar create: {exc}") from exc
    if cmd == "update":
        try:
            return client.patch_event(
                args.event_id,
                calendar_id=args.calendar_id,
                summary=args.summary,
                date=args.date,
                time=args.time,
                duration_min=args.duration_min,
                all_day=args.all_day,
                description=args.description,
                location=args.location,
                replace_attendees=args.replace_attendees,
                meet=args.meet,
                replace_rrule=args.replace_rrule,
                replace_reminder_minutes=_parse_minutes(args.replace_reminders),
                clear_reminders=args.clear_reminders,
                tz=args.tz,
            )
        except ValueError as exc:
            raise UsageError(f"calendar update: {exc}") from exc
    if cmd == "delete":
        client.delete_event(args.event_id, calendar_id=args.calendar_id)
        return {"deleted": args.event_id, "calendar_id": args.calendar_id}
    if cmd == "freebusy":
        tz = _resolve_query_tz(args.tz)
        time_min, time_max = _date_window_bounds(args.from_date, args.to_date, tz)
        return client.freebusy(
            time_min,
            time_max,
            calendar_ids=args.calendar_id or ["primary"],
            tz=tz,
        )
    raise UsageError(f"unknown calendar subcommand: {cmd}")
