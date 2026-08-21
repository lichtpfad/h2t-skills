# Calendar Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list calendars | `h2t-ops calendar calendars --json` |
| list events | `h2t-ops calendar list --days 1 --max 250 --json` — N календарных суток от сегодня в `--tz`, не скользящие N×24ч |
| explicit date window | `h2t-ops calendar list --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --max 250 --json` |
| busy windows | `h2t-ops calendar freebusy --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --json` |
| search events | `h2t-ops calendar search "meeting" --max 20 --json` |
| get event | `h2t-ops calendar get EVENT_ID_FROM_LIST --json` |
| create timed event | `h2t-ops calendar create "Planning" 2026-05-23 14:00 --duration-min 60 --json` |
| create all-day event | `h2t-ops calendar create "Travel" 2026-05-23 --all-day --json` |
| update event | `h2t-ops calendar update EVENT_ID_FROM_LIST --summary "Updated title" --json` |
| delete event | `h2t-ops calendar delete EVENT_ID_FROM_LIST --confirm --json` |
| create new calendar | `h2t-ops calendar create-calendar "My Calendar" --timezone UTC --json` |
| recurring event instances | `h2t-ops calendar instances EVENT_ID --from 2026-06-01 --to 2026-06-30 --json` |

## Safety

- Listing, searching, getting, and FreeBusy are read-only.
- Create, update, and delete require explicit user intent.
- Do not infer attendees, recurrence, reminders, or Google Meet links unless the user asks.
- Do not paste private calendar descriptions into GitHub issues.

## Commands

Use JSON for agent processing:

```bash
h2t-ops calendar calendars --json
h2t-ops calendar list --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --max 250 --busy-only --json
h2t-ops calendar freebusy --from 2026-05-23 --to 2026-05-23 --tz Asia/Jerusalem --json
h2t-ops calendar create "Planning" 2026-05-23 14:00 --duration-min 60 --meet --json
```

## Auth

Google OAuth credentials and tokens are expected under `~/.config/google-calendar-mcp/`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- Missing token: run Google OAuth setup before Calendar commands.
- Timezone error on Windows: ensure `tzdata` is installed in the `h2t-ops` environment.
- Delete without `--confirm`: command should fail instead of deleting.

## Manual E2E Smoke Recipe

> `create-calendar` live smoke requires explicit manual approval — no automated calendar creation.
> `instances` is read-only against an env-provided safe recurring event.

### instances (safe, read-only)

```python
import subprocess
result = subprocess.run(
    ["h2t-ops", "calendar", "instances", event_id,
     "--calendar-id", "primary", "--json"],
    capture_output=True, text=True,
)
# Returns list of event instances
```

### create-calendar (manual approval required)

Approve before running:

```
Command: h2t-ops calendar create-calendar "h2t-e2e-test-cal" --timezone "UTC"
Effect: creates a new calendar in your Google account
Rollback: delete the calendar from Google Calendar settings
```
