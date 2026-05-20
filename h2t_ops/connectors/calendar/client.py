"""CalendarClient — Google Calendar adapter (re-wrapped, typed errors).

API logic mirrors lib/clients/calendar.py; only side effects and error types
changed per spec §10 (re-wrap not rewrite). Provider-feature expansion is
tracked in #145 — this module is parity-only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import (
    AuthError, H2TError, NetworkError, NotFoundError, ProviderError,
)
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _map_http_error(e: Exception, *, op: str):
    """Map googleapiclient.errors.HttpError to typed h2t_ops errors.

    Mirrors h2t_ops/connectors/gmail/client.py:_map_http_error. Defensive:
    google libs may be absent in test contexts, so we check duck-typed.
    """
    if isinstance(e, H2TError):
        return e
    status = getattr(getattr(e, "resp", None), "status", None)
    msg = f"Failed to {op}: {e}"
    if status in (401, 403):
        return AuthError(msg)
    if status == 404:
        return NotFoundError(msg)
    if status is not None and status >= 500:
        return ProviderError(msg)
    s = str(e).lower()
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(msg)
    return ProviderError(msg)


class CalendarClient:
    """Google Calendar API client — primary calendar only (parity scope #132)."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("calendar", CALENDAR_SCOPES)
        self.service = build_google_service("calendar", "v3", creds)

    # ----- Read -----
    def list_events(self, days: int = 1, max_results: int = 20) -> List[Dict[str, Any]]:
        time_min = datetime.now(timezone.utc).isoformat()
        time_max = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        try:
            res = self.service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op="list events") from e
        return [self._normalize_event(it) for it in res.get("items", [])]

    def search_events(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            res = self.service.events().list(
                calendarId="primary",
                q=query,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op="search events") from e
        return [self._normalize_event(it) for it in res.get("items", [])]

    def get_event(self, event_id: str) -> Dict[str, Any]:
        try:
            return self.service.events().get(
                calendarId="primary", eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"get event {event_id}") from e

    # ----- Write (explicit user-intent CLI verbs per runbook §7) -----
    def create_event(
        self,
        summary: str,
        date: str,
        time: str,
        duration_min: int = 60,
        description: Optional[str] = None,
        attendees: Optional[str] = None,
        tz: str = "Asia/Jerusalem",
    ) -> Dict[str, Any]:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_min)
        event: Dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        if description:
            event["description"] = description
        if attendees:
            event["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]
        send_updates = "all" if attendees else "none"
        try:
            return self.service.events().insert(
                calendarId="primary", body=event, sendUpdates=send_updates,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"create event {summary!r}") from e

    def delete_event(self, event_id: str) -> None:
        try:
            self.service.events().delete(
                calendarId="primary", eventId=event_id,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"delete event {event_id}") from e

    # ----- Helpers -----
    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Verbatim port from lib/clients/calendar.py._normalize_event."""
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        if "T" in start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            time_str = start_dt.strftime("%H:%M")
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            event_date = start_dt.strftime("%Y-%m-%d")
        else:
            time_str = "весь день"
            duration_min = None
            event_date = start
        return {
            "id": event.get("id", ""),
            "summary": event.get("summary", "(без названия)"),
            "date": event_date,
            "time": time_str,
            "duration_min": duration_min,
            "location": event.get("location", ""),
            "description": (event.get("description") or "")[:200],
            "html_link": event.get("htmlLink", ""),
        }
