# h2t-ops Calendar Provider Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Calendar provider backlog #145 by adding multi-calendar support, all-day events, patch/reschedule, Meet links, recurrence, reminders, and FreeBusy as independently shippable slices.

**Architecture:** Keep the existing Calendar connector shape. Extend `client.py` with provider feature methods and normalized payloads, extend `commands.py` with explicit flags, and preserve read-only/lazy behavior. Calendar remains provider I/O only; no POS/coordinator behavior.

**Tech Stack:** Python 3.11, google-api-python-client, argparse, pytest, h2t_ops typed errors/envelopes.

---

## Inputs

| Source | Path / Issue | Use |
|---|---|---|
| Design | `docs/superpowers/specs/2026-05-22-h2t-ops-calendar-provider-features-design.md` | Source of truth |
| Issue | `#145` | Calendar provider features |
| Current client | `h2t_ops/connectors/calendar/client.py` | Implementation target |
| Current commands | `h2t_ops/connectors/calendar/commands.py` | CLI target |
| Current tests | `tests/connectors/calendar/` | Extend in place |
| Skill docs | `plugins/h2t-ops/skills/calendar/SKILL.md` | User-facing update |

---

## File Map

| File | Action | Owner task | Responsibility |
|---|---|---|---|
| `h2t_ops/connectors/calendar/client.py` | Modify | T1/T2/T3/T4/T5/T6 | Client methods and payload normalization |
| `h2t_ops/connectors/calendar/commands.py` | Modify | T1/T2/T3/T4/T5/T6 | Parser flags, validation, dispatch |
| `tests/connectors/calendar/test_client.py` | Modify | T1/T2/T3/T4/T5/T6 | Client tests |
| `tests/connectors/calendar/test_commands.py` | Modify | T1/T2/T3/T4/T5/T6 | Parser/dispatch tests |
| `plugins/h2t-ops/skills/calendar/SKILL.md` | Modify | T7 | Document new commands and safety |

Do not modify `plugins/h2t/skills/calendar/**`.

---

## Hard Constraints

1. Keep delete `--confirm`.
2. Keep `get --json` raw for backward compatibility.
3. Accept legacy `--duration` as deprecated alias for `--duration-min`.
4. Array updates must use explicit replace flags: `--replace-attendees`, `--replace-rrule`, `--replace-reminders`.
5. Meet request ids are fresh `uuid4` values per request.
6. FreeBusy per-calendar errors are visible.
7. No POS/DOR/vault/lake/context writes.
8. Preserve lazy import policy: `commands.py` must not import `CalendarClient` at module scope.
9. Each commit-bearing task stages only its listed files.
10. Command tests that stub `CalendarClient` must use the existing
    `_patch_calendar_client(monkeypatch, factory)` helper in
    `tests/connectors/calendar/test_commands.py`. Do not use direct
    `monkeypatch.setattr(client_mod, "CalendarClient", ...)` snippets from
    older notes; they can miss the module object used by `commands.run()` in
    clean CI after import-laziness tests.

## Output Contract

Every user-facing event payload returned by `list`, `search`, `create`, and
`update` must use the same normalized event shape while preserving legacy keys
already emitted today:

```python
{
    "kind": "calendar_event/v1",
    "id": "...",
    "calendar_id": "...",
    "summary": "...",
    "start": {...},
    "end": {...},
    "all_day": False,
    "meet_link": "",
    "meet_status": "none|pending|success|failure",
    "recurrence": [],
    "attendees": [],
    "reminders": {"useDefault": True, "overrides": []},
}
```

`get --json` remains raw for backward compatibility.

---

## Shared Commands

Run after every commit-bearing task:

```powershell
where.exe uv
uv.exe run pytest tests/connectors/calendar -q
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Boundary grep:

```powershell
Select-String -Path h2t_ops/connectors/calendar/*.py -Pattern "DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/|~/.dor"
```

Expected: no matches.

---

## T0 - Baseline

**Files:**
- Read only

- [ ] **Step 1: Confirm branch and dirty tree**

Run:

```powershell
git status --short --branch
```

Expected: unrelated dirty files may exist. Do not stage or modify them.

- [ ] **Step 2: Run current Calendar tests**

Run:

```powershell
where.exe uv
uv.exe run pytest tests/connectors/calendar -q
```

Expected: PASS.

- [ ] **Step 3: Do not commit T0**

Expected: no files changed by T0.

---

## T1 - Multi-Calendar Read And Read Propagation

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Add failing client tests**

Append to `tests/connectors/calendar/test_client.py`:

```python
def test_list_calendars_normalizes_access_role(client_obj):
    client_obj.service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "primary",
                "summary": "Primary",
                "primary": True,
                "accessRole": "owner",
                "timeZone": "Asia/Jerusalem",
                "conferenceProperties": {"allowedConferenceSolutionTypes": ["hangoutsMeet"]},
            }
        ]
    }
    result = client_obj.list_calendars()
    assert result["kind"] == "calendar_list/v1"
    assert result["calendars"][0]["access_role"] == "owner"
    assert result["calendars"][0]["can_write"] is True


def test_list_events_accepts_calendar_id(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {"items": []}
    client_obj.list_events(calendar_id="team@example.com")
    client_obj.service.events.return_value.list.assert_called_once()
    assert client_obj.service.events.return_value.list.call_args.kwargs["calendarId"] == "team@example.com"


def test_search_and_get_accept_calendar_id(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {"items": []}
    client_obj.search_events("q", calendar_id="team@example.com")
    assert client_obj.service.events.return_value.list.call_args.kwargs["calendarId"] == "team@example.com"
    client_obj.service.events.return_value.get.return_value.execute.return_value = {"id": "e"}
    assert client_obj.get_event("e", calendar_id="team@example.com") == {"id": "e"}
    assert client_obj.service.events.return_value.get.call_args.kwargs["calendarId"] == "team@example.com"
```

- [ ] **Step 2: Add failing command tests**

Append to `tests/connectors/calendar/test_commands.py`:

```python
def test_calendars_parser_registered_and_calendar_id_on_reads():
    parser = _build_parser()
    assert parser.parse_args(["calendar", "calendars", "--json"]).calendar_cmd == "calendars"
    assert parser.parse_args(["calendar", "list", "--calendar-id", "team@example.com"]).calendar_id == "team@example.com"
    assert parser.parse_args(["calendar", "search", "q", "--calendar-id", "team@example.com"]).calendar_id == "team@example.com"
    assert parser.parse_args(["calendar", "get", "evt", "--calendar-id", "team@example.com"]).calendar_id == "team@example.com"


def test_calendar_commands_keep_client_import_lazy():
    import sys
    sys.modules.pop("h2t_ops.connectors.calendar.client", None)
    import importlib
    import h2t_ops.connectors.calendar.commands as commands_mod
    importlib.reload(commands_mod)
    assert "h2t_ops.connectors.calendar.client" not in sys.modules


def test_calendars_dispatch(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod

    class _Stub:
        def list_calendars(self):
            return {"kind": "calendar_list/v1", "calendars": []}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(calendar_cmd="calendars", as_json=True, fmt="human"))
    assert out["kind"] == "calendar_list/v1"


def test_list_dispatch_passes_calendar_id(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def list_events(self, **kwargs):
            calls.append(kwargs)
            return []

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    cmds_mod.run(SimpleNamespace(
        calendar_cmd="list", calendar_id="team@example.com", days=1,
        from_date=None, to_date=None, tz=None, max=10, busy_only=False,
        as_json=True, fmt="human",
    ))
    assert calls[0]["calendar_id"] == "team@example.com"
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/calendar -q
```

Expected: FAIL because `calendars` and `calendar_id` support do not exist.

- [ ] **Step 4: Implement client read support**

Modify `CalendarClient`:

```python
    def list_calendars(self) -> Dict[str, Any]:
        try:
            res = self.service.calendarList().list().execute()
        except Exception as e:
            raise _map_http_error(e, op="list calendars") from e
        rows = []
        for item in res.get("items", []):
            access_role = item.get("accessRole", "")
            rows.append({
                "id": item.get("id", ""),
                "summary": item.get("summary", ""),
                "primary": bool(item.get("primary", False)),
                "access_role": access_role,
                "time_zone": item.get("timeZone", ""),
                "can_write": access_role in ("owner", "writer"),
                "conference_properties": item.get("conferenceProperties", {}),
            })
        return {"kind": "calendar_list/v1", "calendars": rows}
```

Update method signatures:

```python
list_events(..., calendar_id: str = "primary")
search_events(query: str, *, calendar_id: str = "primary", max_results: int = 10)
get_event(event_id: str, *, calendar_id: str = "primary")
```

Replace hard-coded `calendarId="primary"` in read calls with `calendarId=calendar_id`.

- [ ] **Step 5: Implement command read support**

In `commands.py`, add a helper:

```python
    def add_calendar_id(sp):
        sp.add_argument("--calendar-id", default="primary")
```

Add parser:

```python
    clp = cmds.add_parser("calendars", help="List available calendars")
    add_fmt(clp)
```

Call `add_calendar_id()` on `list`, `search`, and `get`.

Add dispatch:

```python
    if cmd == "calendars":
        return client.list_calendars()
```

Pass `calendar_id=args.calendar_id` to `list_events`, `search_events`, and `get_event`.

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
uv.exe run pytest tests/connectors/calendar -q
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops dev check lazy-registry
```

Expected: PASS.

Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): add multi-calendar reads (#145)"
```

---

## T2 - Write Calendar ID Propagation And Legacy Duration Alias

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
# tests/connectors/calendar/test_client.py
def test_create_and_delete_accept_calendar_id(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "new"}
    client_obj.create_event("S", "2026-05-25", "14:00", calendar_id="team@example.com")
    assert client_obj.service.events.return_value.insert.call_args.kwargs["calendarId"] == "team@example.com"
    client_obj.delete_event("new", calendar_id="team@example.com")
    assert client_obj.service.events.return_value.delete.call_args.kwargs["calendarId"] == "team@example.com"


def test_create_permission_error_mentions_calendar_id_and_calendar_list_hint(client_obj):
    err = _fake_google_error(status=403, reason="forbidden")
    client_obj.service.events.return_value.insert.return_value.execute.side_effect = err
    with pytest.raises(ProviderError) as exc:
        client_obj.create_event("S", "2026-05-25", "14:00", calendar_id="team@example.com")
    msg = str(exc.value)
    assert "team@example.com" in msg
    assert "h2t-ops calendar calendars --json" in msg


def test_delete_permission_error_mentions_calendar_id_and_calendar_list_hint(client_obj):
    err = _fake_google_error(status=403, reason="forbidden")
    client_obj.service.events.return_value.delete.return_value.execute.side_effect = err
    with pytest.raises(ProviderError) as exc:
        client_obj.delete_event("evt", calendar_id="team@example.com")
    msg = str(exc.value)
    assert "team@example.com" in msg
    assert "h2t-ops calendar calendars --json" in msg


def test_normalize_event_has_provider_feature_fields(client_obj):
    row = client_obj._normalize_event({
        "id": "evt",
        "summary": "S",
        "start": {"date": "2026-05-25"},
        "end": {"date": "2026-05-26"},
        "recurrence": ["RRULE:FREQ=DAILY;COUNT=2"],
        "attendees": [{"email": "a@example.com"}],
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
    }, calendar_id="team@example.com")
    assert row["kind"] == "calendar_event/v1"
    assert row["calendar_id"] == "team@example.com"
    assert row["all_day"] is True
    assert row["meet_status"] == "none"
    assert row["recurrence"] == ["RRULE:FREQ=DAILY;COUNT=2"]
    assert row["attendees"] == [{"email": "a@example.com"}]
    assert row["reminders"]["overrides"][0]["minutes"] == 10


def test_create_event_with_location_sets_location(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "evt"}
    client_obj.create_event("S", "2026-05-25", "14:00", location="Room A")
    body = client_obj.service.events.return_value.insert.call_args.kwargs["body"]
    assert body["location"] == "Room A"
```

```python
# tests/connectors/calendar/test_commands.py
def test_create_accepts_calendar_id_and_duration_alias():
    parser = _build_parser()
    ns = parser.parse_args([
        "calendar", "create", "S", "2026-05-25", "14:00",
        "--calendar-id", "team@example.com", "--duration", "45",
    ])
    assert ns.calendar_id == "team@example.com"
    assert ns.duration_min == 45


def test_create_accepts_location():
    parser = _build_parser()
    ns = parser.parse_args([
        "calendar", "create", "S", "2026-05-25", "14:00",
        "--location", "Room A",
    ])
    assert ns.location == "Room A"


def test_create_dispatch_passes_location(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def create_event(self, *args, **kwargs):
            calls.append(kwargs)
            return {"kind": "calendar_event/v1", "id": "evt"}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    cmds_mod.run(SimpleNamespace(
        calendar_cmd="create", summary="S", date="2026-05-25", time="14:00",
        all_day=False, duration_min=60, description=None, attendees=None,
        location="Room A", calendar_id="primary", tz="Asia/Jerusalem",
        as_json=True, fmt="human",
    ))
    assert calls[0]["location"] == "Room A"


def test_delete_accepts_calendar_id(monkeypatch):
    parser = _build_parser()
    ns = parser.parse_args(["calendar", "delete", "evt", "--calendar-id", "team@example.com", "--confirm"])
    assert ns.calendar_id == "team@example.com"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv.exe run pytest tests/connectors/calendar -q
```

Expected: FAIL.

- [ ] **Step 3: Implement**

In `client.py`:

- add `calendar_id: str = "primary"` to `create_event` and `delete_event`;
- replace `calendarId="primary"` with `calendarId=calendar_id`;
- when mapping write-side Google errors, include the target `calendar_id` and
  hint `h2t-ops calendar calendars --json` for 403/notFound cases;
- update `_normalize_event(event, calendar_id="primary")` so list/search/create/update
  share the Output Contract fields above while preserving existing legacy keys.
- add optional `location` support in `create_event` and set `event["location"]`
  when provided.

In `commands.py`:

- call `add_calendar_id(cp)` and `add_calendar_id(dp)`;
- add create flag `--location`;
- add deprecated alias:

```python
cp.add_argument("--duration", dest="duration_min", type=int, help=argparse.SUPPRESS)
```

If `argparse` is not imported, add `import argparse` at top.

Pass `calendar_id=args.calendar_id` and `location=args.location` to create
dispatch. Do not add `--meet`, `--rrule`, or `--reminder-minutes` dispatch in T2;
those flags are added in their vertical feature slices T5A/T5B/T5C.

- [ ] **Step 4: Run and commit**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): propagate calendar ids for writes (#145)"
```

---

## T3 - All-Day Create

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_create_event_all_day_uses_date_fields(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "ad"}
    client_obj.create_event("Holiday", "2026-05-25", None, all_day=True)
    body = client_obj.service.events.return_value.insert.call_args.kwargs["body"]
    assert body["start"] == {"date": "2026-05-25"}
    assert body["end"] == {"date": "2026-05-26"}


def test_create_event_rejects_time_with_all_day(client_obj):
    with pytest.raises(ValueError):
        client_obj.create_event("Holiday", "2026-05-25", "14:00", all_day=True)
```

```python
def test_create_parser_all_day_time_optional():
    parser = _build_parser()
    ns = parser.parse_args(["calendar", "create", "Holiday", "2026-05-25", "--all-day"])
    assert ns.time is None
    assert ns.all_day is True


def test_create_dispatch_rejects_missing_time_without_all_day(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            calendar_cmd="create", summary="S", date="2026-05-25", time=None,
            all_day=False, duration_min=60, description=None, attendees=None,
            tz="Asia/Jerusalem", calendar_id="primary", as_json=True, fmt="human",
        ))
```

- [ ] **Step 2: Implement**

In `client.py`, update `create_event`:

```python
        if all_day:
            if time:
                raise ValueError("all-day create rejects time")
            start_dt = datetime.strptime(date, "%Y-%m-%d").date()
            end_dt = start_dt + timedelta(days=1)
            event = {
                "summary": summary,
                "start": {"date": start_dt.isoformat()},
                "end": {"date": end_dt.isoformat()},
            }
        else:
            if not time:
                raise ValueError("timed create requires time")
            start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration_min)
            event = {
                "summary": summary,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
            }
```

In `commands.py`:

- make `time` positional optional: `cp.add_argument("time", nargs="?")`;
- add `cp.add_argument("--all-day", action="store_true")`;
- before client call:

```python
        if args.all_day and args.time:
            raise UsageError("calendar create: --all-day rejects time")
        if not args.all_day and not args.time:
            raise UsageError("calendar create: time is required unless --all-day is used")
```

- pass `all_day=args.all_day`.

- [ ] **Step 3: Run and commit**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): create all-day events (#145)"
```

---

## T4 - Patch / Reschedule With Explicit Array Replacement

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_patch_event_noop_rejected(client_obj):
    with pytest.raises(ValueError):
        client_obj.patch_event("evt")


def test_patch_event_timed_reschedule_uses_patch(client_obj):
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {"id": "evt"}
    client_obj.patch_event("evt", date="2026-05-25", time="14:00", duration_min=30)
    body = client_obj.service.events.return_value.patch.call_args.kwargs["body"]
    assert body["start"]["dateTime"].startswith("2026-05-25T14:00")
    assert body["end"]["dateTime"].startswith("2026-05-25T14:30")


def test_patch_event_does_not_send_arrays_without_replace_flags(client_obj):
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {"id": "evt"}
    client_obj.patch_event("evt", summary="New")
    body = client_obj.service.events.return_value.patch.call_args.kwargs["body"]
    assert "attendees" not in body
    assert "recurrence" not in body
    assert "reminders" not in body


def test_patch_event_with_meet_adds_conference_create_request(client_obj, monkeypatch):
    import h2t_ops.connectors.calendar.client as cal_client
    monkeypatch.setattr(cal_client.uuid, "uuid4", lambda: "uuid-update")
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {"id": "evt"}
    client_obj.patch_event("evt", summary="M", meet=True)
    kwargs = client_obj.service.events.return_value.patch.call_args.kwargs
    assert kwargs["conferenceDataVersion"] == 1
    assert kwargs["body"]["conferenceData"]["createRequest"]["requestId"] == "uuid-update"


def test_patch_event_returns_normalized_event(client_obj):
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {
        "id": "evt",
        "summary": "Updated",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
    }
    result = client_obj.patch_event("evt", summary="Updated", calendar_id="team@example.com")
    assert result["kind"] == "calendar_event/v1"
    assert result["calendar_id"] == "team@example.com"


def test_patch_permission_error_mentions_calendar_id_and_calendar_list_hint(client_obj):
    err = _fake_google_error(status=403, reason="forbidden")
    client_obj.service.events.return_value.patch.return_value.execute.side_effect = err
    with pytest.raises(ProviderError) as exc:
        client_obj.patch_event("evt", summary="S", calendar_id="team@example.com")
    msg = str(exc.value)
    assert "team@example.com" in msg
    assert "h2t-ops calendar calendars --json" in msg
```

```python
def test_update_parser_uses_replace_flags():
    parser = _build_parser()
    ns = parser.parse_args([
        "calendar", "update", "evt",
        "--replace-attendees", "a@example.com",
        "--replace-rrule", "RRULE:FREQ=WEEKLY;COUNT=2",
        "--replace-reminders", "10,60",
    ])
    assert ns.replace_attendees == "a@example.com"
    assert ns.replace_rrule.startswith("RRULE:")
    assert ns.replace_reminders == "10,60"


def test_update_dispatch_rejects_noop(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            calendar_cmd="update", event_id="evt", calendar_id="primary",
            summary=None, date=None, time=None, duration_min=None, all_day=False,
            description=None, location=None, replace_attendees=None, meet=False,
            replace_rrule=None, replace_reminders=None, clear_reminders=False,
            tz="Asia/Jerusalem", as_json=True, fmt="human",
        ))


def test_update_dispatch_passes_meet(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def patch_event(self, event_id, **kwargs):
            calls.append((event_id, kwargs))
            return {"kind": "calendar_event/v1", "id": event_id}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        calendar_cmd="update", event_id="evt", calendar_id="primary",
        summary="M", date=None, time=None, duration_min=None, all_day=False,
        description=None, location=None, replace_attendees=None, meet=True,
        replace_rrule=None, replace_reminders=None, clear_reminders=False,
        tz="Asia/Jerusalem", as_json=True, fmt="human",
    ))
    assert out["kind"] == "calendar_event/v1"
    assert calls == [("evt", {
        "calendar_id": "primary",
        "summary": "M",
        "date": None,
        "time": None,
        "duration_min": None,
        "all_day": False,
        "description": None,
        "location": None,
        "replace_attendees": None,
        "meet": True,
        "replace_rrule": None,
        "replace_reminder_minutes": None,
        "clear_reminders": False,
        "tz": "Asia/Jerusalem",
    })]
```

- [ ] **Step 2: Implement client patch**

Add `import uuid`, then add method:

```python
    def patch_event(self, event_id: str, *, calendar_id: str = "primary",
                    summary: Optional[str] = None, date: Optional[str] = None,
                    time: Optional[str] = None, duration_min: Optional[int] = None,
                    all_day: Optional[bool] = None, description: Optional[str] = None,
                    location: Optional[str] = None, replace_attendees: Optional[str] = None,
                    replace_rrule: Optional[str] = None,
                    replace_reminder_minutes: Optional[List[int]] = None,
                    clear_reminders: bool = False, tz: Optional[str] = None,
                    meet: bool = False) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        if location is not None:
            body["location"] = location
        if all_day:
            if not date or time:
                raise ValueError("all-day patch requires --date and rejects --time")
            start_day = datetime.strptime(date, "%Y-%m-%d").date()
            body["start"] = {"date": start_day.isoformat()}
            body["end"] = {"date": (start_day + timedelta(days=1)).isoformat()}
        elif date or time:
            if not (date and time):
                raise ValueError("timed patch requires both date and time")
            minutes = duration_min if duration_min is not None else 60
            start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=minutes)
            zone = tz or "Asia/Jerusalem"
            body["start"] = {"dateTime": start_dt.isoformat(), "timeZone": zone}
            body["end"] = {"dateTime": end_dt.isoformat(), "timeZone": zone}
        if replace_attendees is not None:
            body["attendees"] = self._parse_attendees(replace_attendees)
        if replace_rrule is not None:
            body["recurrence"] = [replace_rrule]
        if replace_reminder_minutes is not None:
            body["reminders"] = self._reminders_body(replace_reminder_minutes)
        if clear_reminders:
            body["reminders"] = {"useDefault": False, "overrides": []}
        if meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        if not body:
            raise ValueError("no-op patch")
        try:
            event = self.service.events().patch(
                calendarId=calendar_id, eventId=event_id, body=body,
                conferenceDataVersion=1 if meet else 0,
            ).execute()
            return self._normalize_event(event, calendar_id=calendar_id)
        except Exception as e:
            raise _map_http_error(
                e,
                op=f"patch event {event_id} on calendar {calendar_id}. "
                   "Run h2t-ops calendar calendars --json to inspect write access.",
            ) from e
```

Also add helper:

```python
    def _parse_attendees(self, attendees: str) -> List[Dict[str, str]]:
        seen = set()
        rows = []
        for raw in attendees.split(","):
            email = raw.strip()
            if not email:
                raise ValueError("empty attendee email")
            if email not in seen:
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
```

- [ ] **Step 3: Implement command update**

Add parser:

```python
up = cmds.add_parser("update", help="Patch or reschedule an event")
up.add_argument("event_id")
add_calendar_id(up)
up.add_argument("--summary")
up.add_argument("--date")
up.add_argument("--time")
up.add_argument("--duration-min", dest="duration_min", type=int)
up.add_argument("--all-day", action="store_true")
up.add_argument("--description")
up.add_argument("--location")
up.add_argument("--replace-attendees")
up.add_argument("--meet", action="store_true")
up.add_argument("--replace-rrule")
up.add_argument("--replace-reminders")
up.add_argument("--clear-reminders", action="store_true")
up.add_argument("--tz", default="Asia/Jerusalem")
add_fmt(up)
```

Dispatch:

```python
    if cmd == "update":
        reminder_minutes = _parse_minutes(args.replace_reminders) if args.replace_reminders else None
        try:
            return client.patch_event(
                args.event_id, calendar_id=args.calendar_id,
                summary=args.summary, date=args.date, time=args.time,
                duration_min=args.duration_min, all_day=args.all_day,
                description=args.description, location=args.location,
                replace_attendees=args.replace_attendees, meet=args.meet,
                replace_rrule=args.replace_rrule,
                replace_reminder_minutes=reminder_minutes,
                clear_reminders=args.clear_reminders, tz=args.tz,
            )
        except ValueError as exc:
            raise UsageError(f"calendar update: {exc}") from exc
```

Add `_parse_minutes` helper in commands:

```python
def _parse_minutes(raw: str) -> list[int]:
    from h2t_ops.core.errors import UsageError
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError as exc:
        raise UsageError("calendar: reminder minutes must be integers") from exc
```

- [ ] **Step 4: Run and commit**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): patch and reschedule events safely (#145)"
```

---

## T5 - Meet, Recurrence, And Reminders As Independent Commits

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

### T5A - Meet Links

- [ ] **Step 1: Add failing Meet tests**

Append:

```python
def test_create_event_with_meet_uses_fresh_uuid_and_conference_version(client_obj, monkeypatch):
    import h2t_ops.connectors.calendar.client as cal_client
    monkeypatch.setattr(cal_client.uuid, "uuid4", lambda: "uuid-1")
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "evt"}
    client_obj.create_event("M", "2026-05-25", "14:00", meet=True)
    kwargs = client_obj.service.events.return_value.insert.call_args.kwargs
    assert kwargs["conferenceDataVersion"] == 1
    assert kwargs["body"]["conferenceData"]["createRequest"]["requestId"] == "uuid-1"


def test_normalize_event_includes_meet_status_and_link(client_obj):
    row = client_obj._normalize_event({
        "id": "evt",
        "summary": "M",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "hangoutLink": "https://meet.google.com/abc",
        "conferenceData": {"createRequest": {"status": {"statusCode": "success"}}},
    })
    assert row["meet_link"] == "https://meet.google.com/abc"
    assert row["meet_status"] == "success"


def test_normalize_event_preserves_pending_meet_status(client_obj):
    row = client_obj._normalize_event({
        "id": "evt",
        "summary": "M",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "conferenceData": {"createRequest": {"status": {"statusCode": "pending"}}},
    })
    assert row["meet_status"] == "pending"
    assert row["meet_link"] == ""


def test_create_dispatch_passes_meet(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def create_event(self, *args, **kwargs):
            calls.append(kwargs)
            return {"kind": "calendar_event/v1", "id": "evt"}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    cmds_mod.run(SimpleNamespace(
        calendar_cmd="create", summary="M", date="2026-05-25", time="14:00",
        all_day=False, duration_min=60, description=None, attendees=None,
        location=None, calendar_id="primary", meet=True, rrule=None,
        reminder_minutes=None, tz="Asia/Jerusalem", as_json=True, fmt="human",
    ))
    assert calls[0]["meet"] is True
```

- [ ] **Step 2: Implement Meet**

In `client.py`, `import uuid` already exists from T4.

In `create_event`, if `meet`:

```python
event["conferenceData"] = {
    "createRequest": {
        "requestId": str(uuid.uuid4()),
        "conferenceSolutionKey": {"type": "hangoutsMeet"},
    }
}
```

Pass `conferenceDataVersion=1 if meet else 0` to insert.

In `commands.py`, ensure `create` parser has `--meet` and dispatch passes
`meet=args.meet`.

Update `_normalize_event`:

```python
        conference = event.get("conferenceData", {})
        status = conference.get("createRequest", {}).get("status", {}).get("statusCode")
        meet_link = event.get("hangoutLink", "")
        if not meet_link:
            for ep in conference.get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri", "")
                    break
        meet_status = status or ("success" if meet_link else "none")
```

Add `meet_link` and `meet_status` to returned dict.

- [ ] **Step 3: Run and commit T5A**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): create Google Meet links (#145)"
```

### T5B - Recurrence

- [ ] **Step 4: Add failing recurrence tests**

Append:

```python
def test_create_event_with_rrule_sets_recurrence(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "evt"}
    client_obj.create_event("R", "2026-05-25", "14:00", rrule="RRULE:FREQ=WEEKLY;COUNT=2")
    body = client_obj.service.events.return_value.insert.call_args.kwargs["body"]
    assert body["recurrence"] == ["RRULE:FREQ=WEEKLY;COUNT=2"]


def test_create_event_rejects_invalid_rrule(client_obj):
    with pytest.raises(ValueError):
        client_obj.create_event("R", "2026-05-25", "14:00", rrule="FREQ=WEEKLY")


def test_create_dispatch_passes_rrule(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def create_event(self, *args, **kwargs):
            calls.append(kwargs)
            return {"kind": "calendar_event/v1", "id": "evt"}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    cmds_mod.run(SimpleNamespace(
        calendar_cmd="create", summary="R", date="2026-05-25", time="14:00",
        all_day=False, duration_min=60, description=None, attendees=None,
        location=None, calendar_id="primary", meet=False,
        rrule="RRULE:FREQ=WEEKLY;COUNT=2", reminder_minutes=None,
        tz="Asia/Jerusalem", as_json=True, fmt="human",
    ))
    assert calls[0]["rrule"] == "RRULE:FREQ=WEEKLY;COUNT=2"
```

- [ ] **Step 5: Implement recurrence**

Add helper:

```python
    def _validate_rrule(self, rrule: str) -> str:
        if not rrule.startswith("RRULE:") or "\n" in rrule or "\r" in rrule:
            raise ValueError("RRULE must start with RRULE: and fit on one line")
        return rrule
```

In `create_event`, if `rrule`, set `event["recurrence"] = [self._validate_rrule(rrule)]`.

In `patch_event`, if `replace_rrule`, set `body["recurrence"] = [self._validate_rrule(replace_rrule)]`.

In `commands.py`, ensure `create` parser has `--rrule` and dispatch passes
`rrule=args.rrule`.

- [ ] **Step 6: Run and commit T5B**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): support recurrence rrules (#145)"
```

### T5C - Reminders

- [ ] **Step 7: Add failing reminder tests**

Append:

```python
def test_create_event_with_reminders_sets_overrides(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {"id": "evt"}
    client_obj.create_event("R", "2026-05-25", "14:00", reminder_minutes=[10, 60])
    body = client_obj.service.events.return_value.insert.call_args.kwargs["body"]
    assert body["reminders"]["useDefault"] is False
    assert body["reminders"]["overrides"] == [
        {"method": "popup", "minutes": 10},
        {"method": "popup", "minutes": 60},
    ]


def test_create_event_rejects_invalid_reminder_minutes(client_obj):
    with pytest.raises(ValueError):
        client_obj.create_event("R", "2026-05-25", "14:00", reminder_minutes=[-1])


def test_create_dispatch_passes_reminder_minutes(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def create_event(self, *args, **kwargs):
            calls.append(kwargs)
            return {"kind": "calendar_event/v1", "id": "evt"}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    cmds_mod.run(SimpleNamespace(
        calendar_cmd="create", summary="R", date="2026-05-25", time="14:00",
        all_day=False, duration_min=60, description=None, attendees=None,
        location=None, calendar_id="primary", meet=False, rrule=None,
        reminder_minutes="10,60", tz="Asia/Jerusalem", as_json=True, fmt="human",
    ))
    assert calls[0]["reminder_minutes"] == [10, 60]
```

- [ ] **Step 8: Implement reminders**

The `_reminders_body` helper already exists from T4 because update
`--replace-reminders` uses the same validation. If it was not added in T4,
add it now:

```python
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
```

In `create_event`, if `reminder_minutes is not None`, set `event["reminders"] = self._reminders_body(reminder_minutes)`.

In `commands.py`, add create parser:

```python
cp.add_argument("--reminder-minutes")
```

Pass `reminder_minutes=_parse_minutes(args.reminder_minutes) if args.reminder_minutes else None`.

- [ ] **Step 9: Run and commit T5C**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): support reminder overrides (#145)"
```

---

## T6 - FreeBusy

**Files:**
- Modify: `h2t_ops/connectors/calendar/client.py`
- Modify: `h2t_ops/connectors/calendar/commands.py`
- Modify: `tests/connectors/calendar/test_client.py`
- Modify: `tests/connectors/calendar/test_commands.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_freebusy_normalizes_partial_errors(client_obj):
    client_obj.service.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {
            "primary": {"busy": [{"start": "s", "end": "e"}]},
            "bad": {"errors": [{"reason": "notFound"}], "busy": []},
        }
    }
    out = client_obj.freebusy("s", "e", calendar_ids=["primary", "bad"])
    assert out["kind"] == "calendar_freebusy/v1"
    assert out["has_errors"] is True
    assert out["calendars"][1]["errors"][0]["reason"] == "notFound"
```

```python
def test_freebusy_parser_and_dispatch(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def freebusy(self, time_min, time_max, *, calendar_ids, tz=None):
            calls.append((time_min, time_max, calendar_ids, tz))
            return {"kind": "calendar_freebusy/v1", "calendars": [], "has_errors": False}

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    out = cmds_mod.run(SimpleNamespace(
        calendar_cmd="freebusy", from_date="2026-05-22", to_date="2026-05-23",
        tz="Asia/Jerusalem", calendar_id=["primary", "team@example.com"],
        as_json=True, fmt="human",
    ))
    assert out["kind"] == "calendar_freebusy/v1"
    assert calls[0][2] == ["primary", "team@example.com"]


def test_freebusy_parser_default_calendar_id_not_duplicated():
    parser = _build_parser()
    ns = parser.parse_args([
        "calendar", "freebusy", "--from", "2026-05-22", "--to", "2026-05-23", "--json",
    ])
    assert ns.calendar_id is None
    ns2 = parser.parse_args([
        "calendar", "freebusy", "--from", "2026-05-22", "--to", "2026-05-23",
        "--calendar-id", "team@example.com", "--json",
    ])
    assert ns2.calendar_id == ["team@example.com"]
```

- [ ] **Step 2: Implement client**

Add:

```python
    def freebusy(self, time_min: str, time_max: str, *, calendar_ids: List[str],
                 tz: Optional[str] = None) -> Dict[str, Any]:
        body = {
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
        rows = []
        for cid, data in res.get("calendars", {}).items():
            rows.append({"id": cid, "busy": data.get("busy", []), "errors": data.get("errors", [])})
        has_errors = any(row["errors"] for row in rows)
        if rows and all(row["errors"] for row in rows):
            raise ProviderError(f"FreeBusy failed for all calendars: {calendar_ids}")
        return {
            "kind": "calendar_freebusy/v1",
            "time_min": time_min,
            "time_max": time_max,
            "calendars": rows,
            "has_errors": has_errors,
        }
```

- [ ] **Step 3: Implement parser and dispatch**

Add parser:

```python
fb = cmds.add_parser("freebusy", help="Query raw calendar busy windows")
fb.add_argument("--from", dest="from_date", required=True, metavar="YYYY-MM-DD")
fb.add_argument("--to", dest="to_date", required=True, metavar="YYYY-MM-DD")
fb.add_argument("--tz", default=None)
fb.add_argument("--calendar-id", action="append", default=None)
add_fmt(fb)
```

Dispatch:

```python
    if cmd == "freebusy":
        tz = _resolve_query_tz(args.tz)
        time_min, time_max = _date_window_bounds(args.from_date, args.to_date, tz)
        return client.freebusy(time_min, time_max, calendar_ids=args.calendar_id or ["primary"], tz=tz)
```

- [ ] **Step 4: Run and commit**

Run shared commands. Commit:

```powershell
git add h2t_ops/connectors/calendar/client.py h2t_ops/connectors/calendar/commands.py tests/connectors/calendar/test_client.py tests/connectors/calendar/test_commands.py
git commit -m "feat(calendar): add freebusy query (#145)"
```

---

## T7 - Skill Docs And Closure Verification

**Files:**
- Modify: `plugins/h2t-ops/skills/calendar/SKILL.md`

- [ ] **Step 1: Update skill docs**

Update command examples in `plugins/h2t-ops/skills/calendar/SKILL.md` to include:

```markdown
h2t-ops calendar calendars --json
h2t-ops calendar list --from YYYY-MM-DD --to YYYY-MM-DD --calendar-id primary --json
h2t-ops calendar create "Meeting" YYYY-MM-DD HH:MM --duration-min 60 --meet --json
h2t-ops calendar create "Holiday" YYYY-MM-DD --all-day --json
h2t-ops calendar update <event-id> --summary "New title" --json
h2t-ops calendar update <event-id> --replace-attendees a@example.com,b@example.com --json
h2t-ops calendar freebusy --from YYYY-MM-DD --to YYYY-MM-DD --calendar-id primary --json
```

Add safety note:

```markdown
`--replace-attendees`, `--replace-rrule`, and `--replace-reminders` replace
Google Calendar array fields. Use them only when replacement is intended.
```

- [ ] **Step 2: Run docs grep**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/calendar/SKILL.md -Pattern "calendars --json|--all-day|--replace-attendees|freebusy|array fields"
```

Expected: matches for all terms.

- [ ] **Step 3: Run full verification**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops calendar --help
uv.exe run h2t-ops dev check lazy-registry
```

Expected: PASS and `OK lazy-registry`.

- [ ] **Step 4: Read-only live smoke**

Run if Google Calendar credentials are configured:

```powershell
uv.exe run h2t-ops calendar calendars --json
uv.exe run h2t-ops calendar list --from 2026-05-22 --to 2026-05-22 --calendar-id primary --json
uv.exe run h2t-ops calendar freebusy --from 2026-05-22 --to 2026-05-23 --calendar-id primary --json
```

Expected: exit 0 and valid JSON.

- [ ] **Step 5: Write smoke only with explicit approval**

Ask user before running any write smoke and ask for a disposable target
calendar id. Capture both created event ids and delete both before claiming
PASS. If delete fails, report the leaked event id immediately.

```powershell
uv.exe run h2t-ops calendar create "h2t test all-day" 2026-05-25 --all-day --calendar-id <target_calendar_id> --json
uv.exe run h2t-ops calendar create "h2t test meet" 2026-05-25 14:00 --meet --calendar-id <target_calendar_id> --json
uv.exe run h2t-ops calendar update <meet_event_id> --summary "h2t test updated" --calendar-id <target_calendar_id> --json
uv.exe run h2t-ops calendar delete <all_day_event_id> --calendar-id <target_calendar_id> --confirm --json
uv.exe run h2t-ops calendar delete <meet_event_id> --calendar-id <target_calendar_id> --confirm --json
```

Expected: create/update/delete test events only. Meet may report `meet_status=pending`; refetch before claiming success.

- [ ] **Step 6: Commit T7**

Run:

```powershell
git add plugins/h2t-ops/skills/calendar/SKILL.md
git commit -m "docs(calendar): document provider feature commands (#145)"
```

---

## T8 - Final Evidence

**Files:**
- No commits

- [ ] **Step 1: Full verification**

Run:

```powershell
uv.exe run pytest tests/core tests/connectors -q
uv.exe run h2t-ops --help
uv.exe run h2t-ops calendar --help
uv.exe run h2t-ops dev check lazy-registry
```

Expected: tests pass, help exits 0, lazy-registry OK.

- [ ] **Step 2: Boundary audit**

Run:

```powershell
Select-String -Path h2t_ops/connectors/calendar/*.py -Pattern "DOR_ROOT|VAULT_ROOT|vault|lake|pos\.db|dor\.db|context/|~/.dor"
```

Expected: no matches.

- [ ] **Step 3: Prepare closure evidence**

Prepare but do not post:

```markdown
## Calendar provider features evidence

- multi-calendar read: PASS
- calendar-id read/write propagation: PASS
- all-day create: PASS
- patch/reschedule: PASS
- Meet links: PASS/PENDING with refetch note
- recurrence: PASS
- reminders: PASS
- FreeBusy: PASS
- tests/core tests/connectors: PASS
- lazy-registry: PASS
- boundary grep: CLEAN
- live smoke: PASS/SKIPPED with reason
```

- [ ] **Step 4: Stop for approval**

Do not push, post comments, or close #145 without explicit user approval.

---

## Self-Review Checklist

- Multi-calendar: T1/T2.
- All-day: T3.
- Patch/reschedule: T4.
- Meet: T5A.
- Recurrence: T5B.
- Reminders: T5C.
- FreeBusy: T6.
- Legacy `--duration`: T2.
- Explicit array replacement: T4/T5.
- Universal envelope: commands return result payloads only.
- No POS/DOR writes: hard constraints and T8 audit.
- No placeholders: all tasks include concrete tests/commands/implementation snippets.
