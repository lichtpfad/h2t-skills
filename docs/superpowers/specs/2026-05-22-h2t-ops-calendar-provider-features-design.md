---
title: "h2t-ops Calendar Provider Features - Design"
status: "draft"
owner: "lichtpfad"
date: "2026-05-22"
milestone: ""
issue: ""
---
# h2t-ops Calendar Provider Features - Design

Date: 2026-05-22
Status: review-ready
Owner connector: h2t-ops/calendar
Issue: #145
Depends on: Calendar parity (#132), Calendar UX closure (#82)

## Goal

Extend the already-working Calendar connector from parity/UX closure to practical
provider completeness for day-to-day calendar operations.

Current Calendar supports:

- `list` with `--from/--to`, `--max`, `--busy-only`
- `search`
- `get`
- `create` timed event on primary calendar
- `delete`

This spec adds provider features tracked in #145:

- Google Meet links
- recurring events
- patch/reschedule
- all-day events
- multi-calendar support
- reminders
- FreeBusy

## Issue Closure Contract

#145 is not one large implementation unit. Each provider feature must be
independently shippable and reviewable. The full issue is closed only after all
slices pass tests and live smoke.

Required slices:

1. Multi-calendar read: `calendars` plus normalized `accessRole`.
2. `--calendar-id` read propagation for `list/search/get`.
3. `--calendar-id` write propagation for `create/update/delete`, with 403 error
   context.
4. All-day create.
5. Timed patch/reschedule.
6. All-day patch/conversion.
7. Meet link creation.
8. Recurrence.
9. Reminders.
10. FreeBusy.

Slices may be separate commits or PRs. Do not bundle Meet, recurrence, and
reminders into one review unit.

## Architecture

Keep the existing three-file connector shape:

- `h2t_ops/connectors/calendar/client.py`
- `h2t_ops/connectors/calendar/commands.py`
- `h2t_ops/connectors/calendar/__init__.py`

Do not introduce POS/coordinator behavior. Calendar remains provider I/O.

## Auth And Scope

Current scope is broad Calendar:

```python
https://www.googleapis.com/auth/calendar
```

That is sufficient for list/search/get/create/update/delete/freebusy/calendarList.
Do not add new scopes unless a live API smoke proves a missing permission.

Keep the missing-scope typed `ConfigError` behavior from the current connector.

## Client API

Add or extend methods:

```python
list_calendars() -> list[dict]

list_events(..., calendar_id="primary")
search_events(query, *, calendar_id="primary", max_results=10)
get_event(event_id, *, calendar_id="primary")

create_event(
    summary,
    *,
    calendar_id="primary",
    date,
    time=None,
    duration_min=60,
    all_day=False,
    description=None,
    location=None,
    attendees=None,
    tz="Asia/Jerusalem",
    meet=False,
    rrule=None,
    reminder_minutes=None,
    use_default_reminders=True,
)

patch_event(
    event_id,
    *,
    calendar_id="primary",
    summary=None,
    date=None,
    time=None,
    duration_min=None,
    all_day=None,
    description=None,
    location=None,
    replace_attendees=None,
    meet=False,
    replace_rrule=None,
    replace_reminder_minutes=None,
    clear_reminders=False,
    tz=None,
)

freebusy(time_min, time_max, *, calendar_ids, tz=None)
```

Patch safety:

- Scalar fields may be patched directly.
- Array fields must use explicit replace semantics.
- `replace_attendees`, `replace_rrule`, and `replace_reminder_minutes` replace
  provider arrays. They do not merge.
- Omitting array replace arguments must not send those fields in the patch body.

## CLI Surface

### Multi-calendar

```bash
h2t-ops calendar calendars --json
```

All event commands accept:

```bash
--calendar-id <id>   # default: primary
```

`calendars` must expose:

- `id`
- `summary`
- `primary`
- `accessRole`
- `timeZone`
- `conferenceProperties`
- derived `can_write`

Write commands do not need to preflight `accessRole`, but a Google 403 must map
to a typed auth/permission error that includes `calendar_id` and hints to run
`h2t-ops calendar calendars --json`.

### Create Timed Event

Backward-compatible timed create remains:

```bash
h2t-ops calendar create "Meeting" 2026-05-25 14:00 --duration-min 60
```

Accept legacy `--duration N` as a deprecated alias for `--duration-min N`
because the old skill docs and `ingest calendar` shim used it.

Add optional provider features:

```bash
h2t-ops calendar create "Meeting" 2026-05-25 14:00 \
  --calendar-id primary \
  --location "Berlin" \
  --attendees a@example.com,b@example.com \
  --meet \
  --rrule "RRULE:FREQ=WEEKLY;COUNT=4" \
  --reminder-minutes 10,60
```

### Create All-Day Event

Make the `time` positional optional in argparse and validate:

```bash
h2t-ops calendar create "Holiday" 2026-05-25 --all-day
```

Rules:

- if `--all-day` is absent, `time` is required;
- if `--all-day` is present, `time` must be absent;
- all-day body uses `start.date` / `end.date`;
- one-day all-day event uses exclusive end date = start date + 1 day;
- all-day event bodies do not send `timeZone`.

### Patch / Reschedule

```bash
h2t-ops calendar update <event_id> \
  [--calendar-id primary] \
  [--summary "..."] \
  [--date YYYY-MM-DD --time HH:MM --duration-min N] \
  [--all-day] \
  [--description "..."] \
  [--location "..."] \
  [--replace-attendees a@example.com,b@example.com] \
  [--meet] \
  [--replace-rrule "RRULE:..."] \
  [--replace-reminders 10,60] \
  [--clear-reminders]
```

Rules:

- no-op update raises `UsageError`;
- timed reschedule requires both `--date` and `--time`;
- all-day reschedule uses `--date --all-day` and rejects `--time`;
- `--replace-attendees`, `--replace-rrule`, and `--replace-reminders` are
  destructive provider-array replacements by name;
- `--clear-reminders` is an explicit destructive reminder replacement:
  `useDefault=false`, `overrides=[]`;
- `--meet` patches/creates `conferenceData.createRequest`;
- call `events.patch(..., conferenceDataVersion=1)` when Meet is requested.

### FreeBusy

```bash
h2t-ops calendar freebusy \
  --from 2026-05-25 \
  --to 2026-05-31 \
  [--tz Asia/Jerusalem] \
  [--calendar-id primary] [--calendar-id team@example.com] \
  --json
```

Date-only semantics mirror `list --from/--to`: `--from` is inclusive local
00:00; `--to` is inclusive user date converted to exclusive next-day bound.

FreeBusy can return HTTP 200 with per-calendar errors. Normalize those errors
inside the result instead of hiding them.

## Google API Details

### Meet Links

For insert/patch with Meet:

```json
{
  "conferenceData": {
    "createRequest": {
      "requestId": "<uuid4-per-request>",
      "conferenceSolutionKey": {"type": "hangoutsMeet"}
    }
  }
}
```

Call insert/patch with `conferenceDataVersion=1`.

`requestId` must be freshly generated for every new Meet creation request.
Reusing a previous id can make Google ignore the request.

Conference creation may be asynchronous. Normalize `meet_link` from
`hangoutLink` or `conferenceData.entryPoints`. If Meet creation is still
pending, return `meet_status="pending"` and let live smoke refetch/poll before
claiming success.

### Recurrence

Accept raw RRULE first:

```bash
--rrule "RRULE:FREQ=WEEKLY;COUNT=4"
```

Store as:

```json
"recurrence": ["RRULE:FREQ=WEEKLY;COUNT=4"]
```

Do not invent a high-level recurrence DSL in this slice.

Validation:

- value must start with `RRULE:`;
- reject newlines;
- update uses `--replace-rrule` to make replacement semantics explicit.

### Reminders

`--reminder-minutes 10,60` maps to:

```json
"reminders": {
  "useDefault": false,
  "overrides": [
    {"method": "popup", "minutes": 10},
    {"method": "popup", "minutes": 60}
  ]
}
```

Rules:

- at most 5 reminder overrides;
- minutes must be integers in Google Calendar's allowed range `0..40320`;
- create uses `--reminder-minutes`;
- update uses `--replace-reminders` or `--clear-reminders`.

### Attendees

Attendees are comma-separated emails.

Rules:

- strip whitespace;
- reject empty entries;
- dedupe preserving order;
- do not perform deep deliverability checks;
- create uses `--attendees`;
- update uses `--replace-attendees`.

## Universal Envelope

All examples below are `result` payloads. CLI JSON output remains wrapped in the
global connector envelope:

```json
{
  "ok": true,
  "provider": "calendar",
  "result": {}
}
```

## Output Contracts

### Normalized Event Payload

Used by `list`, `search`, `create`, and `update`.

```json
{
  "kind": "calendar_event/v1",
  "id": "...",
  "summary": "...",
  "date": "2026-05-25",
  "time": "14:00|all-day",
  "duration_min": 60,
  "calendar_id": "primary",
  "location": "...",
  "description": "...",
  "html_link": "...",
  "meet_link": "...",
  "meet_status": "success|pending|none|failed",
  "recurrence": [],
  "attendees": [],
  "reminders": {}
}
```

`get --json` remains a raw Google event payload for backward compatibility. It
must still include enough raw fields for agents to inspect provider state.

### Calendar List Payload

```json
{
  "kind": "calendar_list/v1",
  "calendars": [
    {
      "id": "primary",
      "summary": "Primary",
      "primary": true,
      "access_role": "owner",
      "time_zone": "Asia/Jerusalem",
      "can_write": true,
      "conference_properties": {}
    }
  ]
}
```

### FreeBusy Payload

```json
{
  "kind": "calendar_freebusy/v1",
  "time_min": "...",
  "time_max": "...",
  "calendars": [
    {
      "id": "primary",
      "busy": [],
      "errors": []
    }
  ],
  "has_errors": false
}
```

If all requested calendars fail, raise `ProviderError`. If some calendars
succeed, return partial success with `has_errors=true` and visible per-calendar
errors.

Do not break existing fields used by current tests and skills.

## Safety And Boundaries

- Calendar write commands are explicit user actions. Keep delete `--confirm`.
- Do not add POS/DOR writes.
- Preserve lazy import policy.
- Keep typed error mapping.
- Do not make provider features required for read-only usage.
- E2E write smoke requires explicit user approval and should create/delete test
  events only.

## Tests To Add

Client tests:

- `test_list_calendars_calls_calendar_list`
- `test_list_calendars_exposes_access_role_and_can_write`
- `test_list_events_accepts_calendar_id`
- `test_create_event_all_day_uses_date_fields`
- `test_create_event_all_day_omits_time_zone`
- `test_create_event_rejects_time_with_all_day`
- `test_create_event_accepts_duration_alias_in_commands`
- `test_create_event_with_meet_sets_conference_data_version`
- `test_create_event_with_meet_uses_fresh_uuid_request_id`
- `test_normalize_event_reports_pending_meet_status`
- `test_create_event_with_rrule_sets_recurrence`
- `test_create_event_rejects_invalid_rrule`
- `test_create_event_with_reminders_sets_overrides`
- `test_create_event_rejects_invalid_reminder_minutes`
- `test_patch_event_noop_rejected`
- `test_patch_event_reschedule_uses_events_patch`
- `test_patch_event_does_not_send_array_fields_without_replace_flags`
- `test_patch_event_replace_attendees_sends_attendees`
- `test_patch_event_replace_rrule_sends_recurrence`
- `test_patch_event_clear_reminders_sends_empty_overrides`
- `test_freebusy_calls_freebusy_query`
- `test_freebusy_returns_partial_errors`
- `test_normalize_event_includes_meet_link_when_present`

Command tests:

- `test_calendars_parser_registered`
- `test_all_event_commands_accept_calendar_id`
- `test_create_parser_accepts_duration_deprecated_alias`
- `test_create_parser_all_day_time_optional`
- `test_create_dispatch_all_day_validates_time_absent`
- `test_update_parser_registered`
- `test_update_dispatch_noop_raises_usageerror`
- `test_update_parser_uses_replace_flags_for_arrays`
- `test_freebusy_parser_date_window`
- `test_commands_import_does_not_import_client`

Regression tests:

- existing `list --from/--to --busy-only` continues to pass;
- existing timed `create SUMMARY DATE TIME` continues to parse;
- existing `delete --confirm` behavior unchanged;
- legacy `--duration` continues to parse as a deprecated alias.

## Live Smoke

Read-only:

```bash
h2t-ops calendar calendars --json
h2t-ops calendar list --from 2026-05-22 --to 2026-05-22 --calendar-id primary --json
h2t-ops calendar freebusy --from 2026-05-22 --to 2026-05-23 --calendar-id primary --json
```

Write smoke only after explicit approval:

```bash
h2t-ops calendar create "h2t test all-day" 2026-05-25 --all-day --json
h2t-ops calendar create "h2t test meet" 2026-05-25 14:00 --meet --json
h2t-ops calendar update <event_id> --summary "h2t test updated" --json
h2t-ops calendar delete <event_id> --confirm --json
```

Meet write smoke must refetch or poll until `meet_status` is `success`, or
record `pending` as non-failing evidence instead of claiming a Meet link exists.

## Implementation Slices

1. Multi-calendar read: `calendars`.
2. `--calendar-id` read propagation.
3. `--calendar-id` write propagation and permission error context.
4. All-day create.
5. Timed patch/reschedule.
6. All-day patch/conversion.
7. Meet links.
8. Recurrence.
9. Reminders.
10. FreeBusy.

Each slice should be TDD and independently shippable.

## Out Of Scope

- Natural-language scheduling.
- Availability recommendations / free-time search beyond raw FreeBusy.
- Calendar sync/coordinator workflows.
- POS task or journal creation from events.
