# H2T Ops Recent Closure Validation Checklist

**Date:** 2026-05-25  
**Purpose:** safe live sweep for recent provider closures

Use this checklist together with
`docs/reports/2026-05-25-h2t-ops-recent-closure-validation-gate.md`.

## Rules

1. Use dedicated test objects only.
2. Prefer reversible actions.
3. Record exact command, object id, and outcome.
4. If a command is unsafe in the current environment, stop and log `deferred`,
   not `pass`.

## #169 Drive `create-folder`

### Preconditions

- Pick a dedicated test parent folder in Drive.
- Use a timestamped child name to avoid collisions.

### Command

```powershell
uv.exe run h2t-ops drive create-folder "h2t-ops-smoke-2026-05-25" --parent <TEST_PARENT_ID> --json
```

### Expected

- `ok: true`
- returned folder id
- folder appears under the chosen parent

### Notes

- Current `h2t-ops` surface does not yet provide a matching Drive delete/trash
  cleanup command.
- Cleanup is manual or deferred to future Drive write-ops backlog.

## #172 Gmail thread operations

### Preconditions

- Prefer a prepared low-risk thread in your own mailbox.
- Do not use a client thread.

### Read-only smoke

```powershell
uv.exe run h2t-ops gmail threads --max 5 --json
uv.exe run h2t-ops gmail thread <THREAD_ID> --json
```

### Reply-in-thread smoke

Only on a prepared test thread:

```powershell
uv.exe run h2t-ops gmail send <YOUR_EMAIL> "h2t-ops thread smoke" "reply smoke" --thread-id <THREAD_ID> --reply-to <MESSAGE_ID> --json
```

### Expected

- thread list returns thread ids
- thread detail returns messages for the requested thread
- reply smoke produces a sent/draft result anchored to the chosen thread

### Notes

- If no prepared safe thread exists, run only the read-only part and mark the
  reply-in-thread write path as `deferred`.

## #173 Gmail attachment download

### Preconditions

- Use a small known message attachment.
- Prefer a non-sensitive attachment.
- Output path should point to a temp directory.

### Discovery

```powershell
uv.exe run h2t-ops gmail read <MESSAGE_ID> --json
```

Find the `attachmentId` in the returned attachment metadata.

### Download smoke

```powershell
uv.exe run h2t-ops gmail attachment <MESSAGE_ID> <ATTACHMENT_ID> --output C:\tmp\h2t-ops-attachment-smoke.bin --json
```

### Expected

- `ok: true`
- output file exists
- output file size is non-zero

## #181 Telegram `send`

### Status

Already validated.

### Reference command

```powershell
uv.exe run h2t-ops telegram send me --message "h2t-ops self-test 2026-05-25" --json
```

### Evidence already captured

- safe self-target
- returned `message_id`
- no broader live sweep required unless behavior regresses

## #176 Calendar `rsvp` and `move`

### Preconditions

- Use a prepared test event where the authenticated account is an attendee.
- For `move`, use a safe source/destination calendar pair.
- Do not use production-critical events.

### Read / discovery

```powershell
uv.exe run h2t-ops calendar calendars --json
uv.exe run h2t-ops calendar get <EVENT_ID> --json
```

### RSVP smoke

```powershell
uv.exe run h2t-ops calendar rsvp <EVENT_ID> --status tentative --json
```

### Move smoke

```powershell
uv.exe run h2t-ops calendar move <EVENT_ID> --to <DESTINATION_CALENDAR_ID> --json
```

### Expected

- RSVP updates the self attendee response status
- move returns the event under the destination calendar id

### Notes

- `#176` should not be closed on unit coverage alone.
- If the environment does not expose a safe move target, run RSVP only and mark
  move as `deferred`.
