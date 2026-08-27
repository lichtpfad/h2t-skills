# H2T Ops Recent Closure Validation Evidence

**Date:** 2026-05-25  
**Scope:** recent post-closure provider follow-ups

This report records the first live validation sweep defined in:

- `docs/reports/2026-05-25-h2t-ops-recent-closure-validation-gate.md`
- `docs/reports/2026-05-25-h2t-ops-recent-closure-validation-checklist.md`

## Results Summary

| Issue | Result | Notes |
| --- | --- | --- |
| #169 | PASS | Safe folder creation in Drive root |
| #172 | PARTIAL PASS | `threads` and `thread` read-only smoke passed; reply-in-thread deferred |
| #173 | PASS | Attachment downloaded to temp path with non-zero bytes |
| #181 | PASS | Prior self-target live smoke already existed |
| #176 | PARTIAL PASS | Safe `move` smoke passed with cleanup; `RSVP` still deferred |

## #169 Drive `create-folder`

Command:

```powershell
uv.exe run h2t-ops drive create-folder "h2t-ops-smoke-2026-05-25" --json
```

Result:

```json
{
  "ok": true,
  "provider": "drive",
  "result": {
    "file_id": "DRIVE_FILE_ID_1",
    "name": "h2t-ops-smoke-2026-05-25",
    "mimeType": "application/vnd.google-apps.folder",
    "parents": ["DRIVE_ID_1"],
    "web_view_link": "https://drive.google.com/drive/folders/DRIVE_FILE_ID_1",
    "parent_name": "root"
  }
}
```

Verdict: pass.

## #172 Gmail thread operations

Thread list command:

```powershell
uv.exe run h2t-ops gmail threads --max 5 --json
```

Thread detail command:

```powershell
uv.exe run h2t-ops gmail thread GMAIL_MESSAGE_ID_1 --json
```

Observed:

- `threads` returned real thread ids
- `thread` returned a multi-message thread with both message ids present

Reply-in-thread write path:

- deferred
- reason: no explicitly prepared safe test thread was introduced for this sweep

Verdict: partial pass on read-path; write-path still deferred.

## #173 Gmail attachment download

Discovery command:

```powershell
uv.exe run h2t-ops gmail search "has:attachment" --json
```

Attachment smoke:

```powershell
uv.exe run h2t-ops gmail attachment GMAIL_MESSAGE_ID_2 GMAIL_ATTACHMENT_ID_1 --output C:\tmp\h2t-ops-attachment-smoke-349096275.pdf --json
```

Result:

```json
{
  "ok": true,
  "provider": "gmail",
  "result": {
    "message_id": "GMAIL_MESSAGE_ID_2",
    "attachment_id": "GMAIL_ATTACHMENT_ID_1",
    "saved_path": "C:\\tmp\\h2t-ops-attachment-smoke-349096275.pdf",
    "size": 124718
  }
}
```

Filesystem check:

- `C:\tmp\h2t-ops-attachment-smoke-349096275.pdf`
- size `124718`

Verdict: pass.

## #181 Telegram send

Previously validated in the earlier P1 sweep:

```powershell
uv.exe run h2t-ops telegram send me --message "h2t-ops self-test 2026-05-25" --json
```

Verdict: pass; no additional live step needed in this sweep.

## #176 Calendar RSVP + move

Read-only discovery completed:

```powershell
uv.exe run h2t-ops calendar calendars --json
uv.exe run h2t-ops calendar list --from 2026-05-25 --to 2026-05-31 --max 20 --json
```

Observed:

- multiple writable owned calendars exist (`primary`, `Procedural`, `Hou2Touch`, etc.)
- real attendee events exist, including:
  - `CALENDAR_EVENT_ID_3`
  - `CALENDAR_EVENT_ID_1`

Move smoke:

```powershell
uv.exe run h2t-ops calendar create "h2t-ops move smoke 2026-05-25" 2026-05-31 10:00 --duration-min 15 --json
uv.exe run h2t-ops calendar move CALENDAR_EVENT_ID_2 --to PERSONAL_CALENDAR_ID_1 --json
uv.exe run h2t-ops calendar delete CALENDAR_EVENT_ID_2 --calendar-id PERSONAL_CALENDAR_ID_1 --confirm --json
```

Observed:

- temporary event created on `primary`
- event moved successfully to `Procedural`
- cleanup delete succeeded on destination calendar
- post-delete `get` shows `status: cancelled`

Current decision:

- `move` is now validated
- `RSVP` live write is still deferred until a clearly prepared safe invite is chosen

Verdict: partial pass; do not close `#176` until RSVP has its own safe smoke.
