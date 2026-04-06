"""CalendarClient — bidirectional Google Calendar adapter (ingest + publish).

Read:  list_events, search_events
Write: create_event, delete_event
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path.home() / ".dor" / "secrets.env", override=False)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError as e:
    raise ImportError(
        f"Google API libraries not found: {e}\n"
        "Install: pip install google-auth google-auth-oauthlib "
        "google-auth-httplib2 google-api-python-client"
    ) from e

CONFIG_DIR = Path.home() / ".config" / "google-calendar-mcp"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "tokens.json"


def _get_service():
    """Build Google Calendar API service from stored OAuth tokens."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"Token file not found: {TOKEN_FILE}\n"
            "Run the gmail skill to complete OAuth flow."
        )
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    if "normal" in token_data:
        token_data = token_data["normal"]

    if "client_id" not in token_data:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(f"credentials.json not found: {CREDENTIALS_FILE}")
        with open(CREDENTIALS_FILE) as f:
            creds_data = json.load(f)
        installed = creds_data.get("installed", creds_data)
        token_data["client_id"] = installed.get("client_id")
        token_data["client_secret"] = installed.get("client_secret")
        token_data.setdefault(
            "token_uri",
            installed.get("token_uri", "https://oauth2.googleapis.com/token"),
        )

    CALENDAR_SCOPE = ["https://www.googleapis.com/auth/calendar"]
    # Normalize singular "scope" field (legacy google-calendar-mcp format)
    if "scope" in token_data and "scopes" not in token_data:
        token_data["scopes"] = token_data.pop("scope").split()
    effective_scopes = token_data.get("scopes") or CALENDAR_SCOPE
    if isinstance(effective_scopes, str):
        effective_scopes = effective_scopes.split()

    creds = Credentials.from_authorized_user_info(token_data, effective_scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


class CalendarClient:
    """Google Calendar API client — read and write events."""

    def __init__(self) -> None:
        self.service = _get_service()

    # --- Read ---

    def list_events(self, days: int = 1, max_results: int = 20) -> List[Dict[str, Any]]:
        """Return events for the next N days as normalized dicts."""
        local_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        time_min = local_today.astimezone(timezone.utc).isoformat()
        time_max = (local_today + timedelta(days=days)).astimezone(timezone.utc).isoformat()

        result_raw = self.service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for event in result_raw.get("items", []):
            events.append(self._normalize_event(event))
        return events

    def search_events(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Full-text search across all calendar events."""
        result_raw = self.service.events().list(
            calendarId="primary",
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return [self._normalize_event(e) for e in result_raw.get("items", [])]

    # --- Write ---

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
        """Create a new calendar event. Returns the created event dict."""
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
        return self.service.events().insert(
            calendarId="primary", body=event, sendUpdates=send_updates
        ).execute()

    def delete_event(self, event_id: str) -> None:
        """Delete an event by ID."""
        self.service.events().delete(calendarId="primary", eventId=event_id).execute()

    def get_event(self, event_id: str) -> Dict[str, Any]:
        """Get a single event by ID."""
        return self.service.events().get(calendarId="primary", eventId=event_id).execute()

    # --- Helpers ---

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw Calendar API event to a flat dict."""
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
