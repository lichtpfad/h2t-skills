"""CalendarClient — Google Calendar adapter (typed provider I/O)."""
from __future__ import annotations

import uuid
from datetime import date as date_cls
from datetime import datetime, time as time_cls, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from h2t_ops.core.errors import (
    AuthError, H2TError, NetworkError, NotFoundError, ProviderError, UsageError,
)
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_CALENDAR_LIST_HINT = "Run `h2t-ops calendar calendars --json` to inspect calendar ids and access roles."


def _local_day_window(days: int, tz: Optional[str]) -> tuple[str, str]:
    """Whole calendar days from today, in the query timezone (#351).

    A rolling `now .. now + days` window makes "today" start at the moment the
    command runs, so an event that ended an hour ago drops out of a brief that
    claims to describe today. Days are calendar days, and the day starts at
    midnight where the caller is.
    """
    zone = _zone(tz)
    today = datetime.now(zone).date()
    start = datetime.combine(today, time_cls.min, tzinfo=zone)
    return start.isoformat(), (start + timedelta(days=max(days, 1))).isoformat()


def _zone(tz: Optional[str]):
    if tz:
        try:
            return ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return datetime.now().astimezone().tzinfo


def _now_in(tz: Optional[str]) -> datetime:
    """Current instant in the requested timezone; local time when it is unusable."""
    return datetime.now(_zone(tz))


def _is_running(start: str, end: str, now: datetime, fallback: bool) -> bool:
    """True while ``now`` is inside [start, end) — the end instant is already over.

    Falls back to the date-level answer when the timestamps do not parse, so a
    malformed payload degrades to the old behaviour instead of raising.
    """
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    if now.tzinfo is None:
        now = now.replace(tzinfo=start_dt.tzinfo)
    return start_dt <= now < end_dt


def _map_http_error(e: Exception, *, op: str, hint: str | None = None):
    """Map googleapiclient.errors.HttpError to typed h2t_ops errors."""
    if isinstance(e, H2TError):
        return e
    status = getattr(getattr(e, "resp", None), "status", None)
    msg = f"Failed to {op}: {e}"
    if status in (401, 403):
        return AuthError(msg, hint=hint)
    if status == 404:
        return NotFoundError(msg, hint=hint)
    if status is not None and status >= 500:
        return ProviderError(msg, hint=hint)
    s = str(e).lower()
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(msg, hint=hint)
    return ProviderError(msg, hint=hint)


class CalendarClient:
    """Google Calendar API client."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("calendar", CALENDAR_SCOPES)
        self.service = build_google_service("calendar", "v3", creds)

    # ----- Read -----
    def list_calendars(self) -> Dict[str, Any]:
        try:
            res = self.service.calendarList().list().execute()
        except Exception as e:
            raise _map_http_error(e, op="list calendars") from e

        calendars = []
        for item in res.get("items", []):
            access_role = item.get("accessRole", "")
            calendars.append({
                "id": item.get("id", ""),
                "summary": item.get("summary", ""),
                "primary": bool(item.get("primary", False)),
                "access_role": access_role,
                "time_zone": item.get("timeZone", ""),
                "can_write": access_role in ("owner", "writer"),
                "conference_properties": item.get("conferenceProperties", {}),
            })
        return {"kind": "calendar_list/v1", "calendars": calendars}

    def list_events(
        self,
        days: int = 1,
        max_results: int = 250,
        *,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        tz: Optional[str] = None,
        busy_only: bool = False,
    ) -> List[Dict[str, Any]]:
        return self.list_events_page(
            days=days, max_results=max_results, calendar_id=calendar_id,
            time_min=time_min, time_max=time_max, tz=tz, busy_only=busy_only,
        )["items"]

    def list_events_page(
        self,
        days: int = 1,
        max_results: int = 250,
        *,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        tz: Optional[str] = None,
        busy_only: bool = False,
    ) -> Dict[str, Any]:
        """Same as list_events, plus whether Calendar had more to give."""
        if time_min is None or time_max is None:
            day_min, day_max = _local_day_window(days, tz)
            time_min = time_min or day_min
            time_max = time_max or day_max
        params: Dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if tz:
            params["timeZone"] = tz
        try:
            res = self.service.events().list(**params).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"list events on calendar {calendar_id!r}") from e
        items = res.get("items", [])
        if busy_only:
            items = [it for it in items if it.get("transparency") != "transparent"]
        return {
            "items": [self._normalize_event(it, calendar_id=calendar_id, tz=tz) for it in items],
            "truncated": bool(res.get("nextPageToken")),
            "window": {"from": time_min, "to": time_max},
        }

    def search_events(
        self,
        query: str,
        *,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Matching events. Prefer search_events_page — this drops truncation."""
        return self.search_events_page(
            query, calendar_id=calendar_id, max_results=max_results,
        )["items"]

    def search_events_page(
        self,
        query: str,
        *,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Same as search_events, plus whether Calendar had more to give (#351)."""
        try:
            res = self.service.events().list(
                calendarId=calendar_id,
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"search events on calendar {calendar_id!r}") from e
        return {
            "items": [self._normalize_event(it, calendar_id=calendar_id)
                      for it in res.get("items", [])],
            "truncated": bool(res.get("nextPageToken")),
        }

    def get_event(self, event_id: str, *, calendar_id: str = "primary") -> Dict[str, Any]:
        try:
            return self.service.events().get(
                calendarId=calendar_id, eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"get event {event_id} on calendar {calendar_id!r}") from e

    # ----- Write -----
    def create_event(
        self,
        summary: str,
        date: str,
        time: Optional[str] = None,
        duration_min: int = 60,
        description: Optional[str] = None,
        attendees: Optional[str] = None,
        tz: str = "Asia/Jerusalem",
        *,
        calendar_id: str = "primary",
        all_day: bool = False,
        location: Optional[str] = None,
        meet: bool = False,
        rrule: Optional[str] = None,
        reminder_minutes: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        event = self._event_time_body(
            summary=summary,
            date=date,
            time=time,
            duration_min=duration_min,
            all_day=all_day,
            tz=tz,
        )
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        parsed_attendees = self._parse_attendees(attendees)
        if parsed_attendees:
            event["attendees"] = parsed_attendees
        if meet:
            event["conferenceData"] = self._meet_request()
        if rrule:
            event["recurrence"] = [self._validate_rrule(rrule)]
        if reminder_minutes is not None:
            event["reminders"] = self._reminders_body(reminder_minutes)

        kwargs: Dict[str, Any] = {
            "calendarId": calendar_id,
            "body": event,
            "sendUpdates": "all" if parsed_attendees else "none",
        }
        if meet:
            kwargs["conferenceDataVersion"] = 1
        try:
            created = self.service.events().insert(**kwargs).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"create event {summary!r} on calendar {calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e
        return self._normalize_event(created, calendar_id=calendar_id)

    def patch_event(
        self,
        event_id: str,
        *,
        calendar_id: str = "primary",
        summary: Optional[str] = None,
        date: Optional[str] = None,
        time: Optional[str] = None,
        duration_min: Optional[int] = None,
        all_day: Optional[bool] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        replace_attendees: Optional[str] = None,
        meet: bool = False,
        replace_rrule: Optional[str] = None,
        replace_reminder_minutes: Optional[List[int]] = None,
        clear_reminders: bool = False,
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location

        wants_reschedule = date is not None or time is not None or all_day is not None
        if wants_reschedule:
            if all_day is True:
                if not date:
                    raise ValueError("all-day update requires --date")
                if time:
                    raise ValueError("all-day update rejects --time")
                body.update(self._date_range(date))
            else:
                if not date or not time:
                    raise ValueError("timed update requires --date and --time")
                body.update(self._datetime_range(
                    date,
                    time,
                    duration_min or 60,
                    tz or "Asia/Jerusalem",
                ))

        if replace_attendees is not None:
            body["attendees"] = self._parse_attendees(replace_attendees)
        if meet:
            body["conferenceData"] = self._meet_request()
        if replace_rrule is not None:
            body["recurrence"] = [self._validate_rrule(replace_rrule)]
        if clear_reminders:
            if replace_reminder_minutes is not None:
                raise ValueError("--clear-reminders cannot be combined with --replace-reminders")
            body["reminders"] = {"useDefault": False, "overrides": []}
        elif replace_reminder_minutes is not None:
            body["reminders"] = self._reminders_body(replace_reminder_minutes)

        if not body:
            raise ValueError("no update fields specified")

        kwargs: Dict[str, Any] = {
            "calendarId": calendar_id,
            "eventId": event_id,
            "body": body,
            "sendUpdates": "all" if "attendees" in body else "none",
        }
        if meet:
            kwargs["conferenceDataVersion"] = 1
        try:
            updated = self.service.events().patch(**kwargs).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"patch event {event_id} on calendar {calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e
        return self._normalize_event(updated, calendar_id=calendar_id)

    def rsvp_event(
        self,
        event_id: str,
        status: str,
        *,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        normalized = status.lower()
        if normalized not in {"accepted", "declined", "tentative"}:
            raise ValueError("status must be accepted, declined, or tentative")
        try:
            event = self.service.events().get(
                calendarId=calendar_id, eventId=event_id,
            ).execute()
            attendees = list(event.get("attendees", []) or [])
            updated = False
            for attendee in attendees:
                if attendee.get("self") is True:
                    attendee["responseStatus"] = normalized
                    updated = True
                    break
            if not updated:
                raise UsageError("event does not expose a self attendee to RSVP")
            result = self.service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body={"attendees": attendees},
                sendUpdates="all",
            ).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"rsvp event {event_id} on calendar {calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e
        return self._normalize_event(result, calendar_id=calendar_id)

    def move_event(
        self,
        event_id: str,
        *,
        calendar_id: str = "primary",
        destination_calendar_id: str,
    ) -> Dict[str, Any]:
        try:
            moved = self.service.events().move(
                calendarId=calendar_id,
                eventId=event_id,
                destination=destination_calendar_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"move event {event_id} from {calendar_id!r} to {destination_calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e
        return self._normalize_event(moved, calendar_id=destination_calendar_id)

    def delete_event(self, event_id: str, *, calendar_id: str = "primary") -> None:
        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"delete event {event_id} on calendar {calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e

    def create_calendar(self, summary: str, *, timezone: Optional[str] = None) -> dict:
        body: Dict[str, Any] = {"summary": summary}
        if timezone:
            body["timeZone"] = timezone
        try:
            return self.service.calendars().insert(body=body).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"create calendar {summary!r}") from e

    def list_instances(
        self,
        event_id: str,
        *,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "calendarId": calendar_id,
            "eventId": event_id,
            "maxResults": max_results,
        }
        if time_min is not None:
            params["timeMin"] = time_min
        if time_max is not None:
            params["timeMax"] = time_max
        try:
            res = self.service.events().instances(**params).execute()
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"list instances of event {event_id} on calendar {calendar_id!r}",
                hint=_CALENDAR_LIST_HINT,
            ) from e
        return res.get("items", [])

    def freebusy(
        self,
        time_min: str,
        time_max: str,
        *,
        calendar_ids: List[str],
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": cid} for cid in calendar_ids],
        }
        if tz:
            body["timeZone"] = tz
        try:
            res = self.service.freebusy().query(body=body).execute()
        except Exception as e:
            raise _map_http_error(e, op="freebusy query") from e
        calendars = [
            {"id": cid, "busy": data.get("busy", []), "errors": data.get("errors", [])}
            for cid, data in res.get("calendars", {}).items()
        ]
        has_errors = any(row["errors"] for row in calendars)
        if calendars and all(row["errors"] for row in calendars):
            raise ProviderError(f"FreeBusy failed for all calendars: {calendar_ids}")
        return {
            "kind": "calendar_freebusy/v1",
            "time_min": time_min,
            "time_max": time_max,
            "calendars": calendars,
            "has_errors": has_errors,
        }

    # ----- Helpers -----
    def _normalize_event(
        self,
        event: Dict[str, Any],
        *,
        calendar_id: str = "primary",
        now: Optional[datetime] = None,
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_obj = event.get("start", {})
        end_obj = event.get("end", {})
        start = start_obj.get("dateTime", start_obj.get("date", ""))
        end = end_obj.get("dateTime", end_obj.get("date", ""))
        all_day = "date" in start_obj and "dateTime" not in start_obj
        if start and "T" in start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            time_str = start_dt.strftime("%H:%M")
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            event_date = start_dt.strftime("%Y-%m-%d")
        else:
            time_str = "весь день"
            duration_min = None
            event_date = start

        conference = event.get("conferenceData", {}) or {}
        status = (
            conference.get("createRequest", {})
            .get("status", {})
            .get("statusCode")
        )
        meet_link = event.get("hangoutLink", "")
        if not meet_link:
            for entry in conference.get("entryPoints", []) or []:
                if entry.get("entryPointType") == "video":
                    meet_link = entry.get("uri", "")
                    break
        meet_status = status or ("success" if meet_link else "none")
        span = self._event_span(start, end, all_day, now, tz)

        return {
            "kind": "calendar_event/v1",
            "id": event.get("id", ""),
            "calendar_id": calendar_id,
            "summary": event.get("summary", "(без названия)"),
            "date": event_date,
            "time": time_str,
            "duration_min": duration_min,
            "start": start_obj,
            "end": end_obj,
            "all_day": all_day,
            "location": event.get("location", ""),
            "description": (event.get("description") or "")[:200],
            "html_link": event.get("htmlLink", ""),
            "meet_link": meet_link,
            "meet_status": meet_status,
            "recurrence": event.get("recurrence", []),
            "attendees": event.get("attendees", []),
            "reminders": event.get("reminders", {"useDefault": True, "overrides": []}),
            **span,
        }

    @staticmethod
    def _event_span(
        start: str,
        end: str,
        all_day: bool,
        now: Optional[datetime] = None,
        tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Derive multi-day / ongoing facts from a start-end pair.

        Without these a running multi-day event is indistinguishable from a
        past single-day one, because rows are keyed on the start date (#351).

        ``ongoing`` answers "is this running *now*", so a timed event is judged
        against the clock, not the date (#359): a 13:00 meeting is not ongoing at
        09:00. All-day rows have no clock — for them the day is the span, which is
        why a birthday stays ongoing until midnight. ``day_index`` is a different
        question ("which day of this event is today"), so it survives an event that
        has not started yet. ``now`` is injectable to keep the derivation testable.
        """
        blank = {"multi_day": False, "days_total": None,
                 "ongoing": None, "day_index": None}
        if not start or not end:
            return blank
        try:
            first = date_cls.fromisoformat(start[:10])
            last = date_cls.fromisoformat(end[:10])
        except ValueError:
            return blank
        if all_day:
            # All-day end dates are exclusive: 18 -> 26 means the 25th is last.
            last -= timedelta(days=1)
        days_total = max((last - first).days + 1, 1)
        now = now or _now_in(tz)
        today = now.date()
        spans_today = first <= today <= last
        ongoing = spans_today if all_day else _is_running(start, end, now, spans_today)
        return {
            "multi_day": days_total > 1,
            "days_total": days_total,
            "ongoing": ongoing,
            "day_index": (today - first).days + 1 if spans_today else None,
        }

    def _event_time_body(
        self,
        *,
        summary: str,
        date: str,
        time: Optional[str],
        duration_min: int,
        all_day: bool,
        tz: str,
    ) -> Dict[str, Any]:
        event = {"summary": summary}
        if all_day:
            if time:
                raise ValueError("all-day create rejects time")
            event.update(self._date_range(date))
            return event
        if not time:
            raise ValueError("timed create requires time")
        event.update(self._datetime_range(date, time, duration_min, tz))
        return event

    def _datetime_range(
        self,
        date: str,
        time: str,
        duration_min: int,
        tz: str,
    ) -> Dict[str, Any]:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_min)
        return {
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }

    def _date_range(self, event_date: str) -> Dict[str, Any]:
        start_day = date_cls.fromisoformat(event_date)
        end_day = start_day + timedelta(days=1)
        return {
            "start": {"date": start_day.isoformat()},
            "end": {"date": end_day.isoformat()},
        }

    def _meet_request(self) -> Dict[str, Any]:
        return {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    def _validate_rrule(self, rrule: str) -> str:
        if not rrule.startswith("RRULE:") or "\n" in rrule or "\r" in rrule:
            raise ValueError("RRULE must start with RRULE: and fit on one line")
        return rrule

    def _parse_attendees(self, attendees: Optional[str]) -> List[Dict[str, str]]:
        if not attendees:
            return []
        seen = set()
        rows = []
        for raw in attendees.split(","):
            email = raw.strip()
            if not email:
                raise ValueError("attendees must not contain empty emails")
            if email in seen:
                continue
            seen.add(email)
            rows.append({"email": email})
        return rows

    def _reminders_body(self, minutes: List[int]) -> Dict[str, Any]:
        if len(minutes) > 5:
            raise ValueError("at most 5 reminder overrides are allowed")
        for value in minutes:
            if value < 0 or value > 40320:
                raise ValueError("reminder minutes must be in range 0..40320")
        return {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": value} for value in minutes],
        }
