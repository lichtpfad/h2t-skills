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
    "file_id": "1JeS1Wz4sQkzVBcgaH2FL6oJd6eTwS2wV",
    "name": "h2t-ops-smoke-2026-05-25",
    "mimeType": "application/vnd.google-apps.folder",
    "parents": ["0ACriOCEyHP1zUk9PVA"],
    "web_view_link": "https://drive.google.com/drive/folders/1JeS1Wz4sQkzVBcgaH2FL6oJd6eTwS2wV",
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
uv.exe run h2t-ops gmail thread 19e4a72c0188a0ee --json
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
uv.exe run h2t-ops gmail attachment 19e595d395a65f58 ANGjdJ_l7nkI9VuJSLdYAeFCS9mRLdK_ldEBf1-Xb46PCqukvANHwd4Ruyr6Tv75rAd2jkwQqTcjjxmSykOVKJSp874Zb0ABNb1puL7ssNebu1uammYdmeUPZdx7qel-2j7f25DOTR6HvbG4j267HNpO68Zo41ghk7iTg6QMOq6HZ9Av0wLWocDIRrzhQLeVa2eKKzHfIO2cZaUJ0ywGpBpeaH43H6ynRNJRfaMHii6obUfDhmY2mT023klCkGT4SPkB72n0_-VO3fJ29khUCgWagukYt9S0pTCV8JHjDeocEga4RN6sV727-vKYl5RcQSzqIj37oBB_5hN2yxbtSZNZLbFmmSnx58VYc_rsiaNm9ddd7hPoZMJAzZgj8KqD9TJ-znL_a6kXqTbmB6O2J0kdTnScFTEbLT55F9BL0Q --output C:\tmp\h2t-ops-attachment-smoke-349096275.pdf --json
```

Result:

```json
{
  "ok": true,
  "provider": "gmail",
  "result": {
    "message_id": "19e595d395a65f58",
    "attachment_id": "ANGjdJ_l7nkI9VuJSLdYAeFCS9mRLdK_ldEBf1-Xb46PCqukvANHwd4Ruyr6Tv75rAd2jkwQqTcjjxmSykOVKJSp874Zb0ABNb1puL7ssNebu1uammYdmeUPZdx7qel-2j7f25DOTR6HvbG4j267HNpO68Zo41ghk7iTg6QMOq6HZ9Av0wLWocDIRrzhQLeVa2eKKzHfIO2cZaUJ0ywGpBpeaH43H6ynRNJRfaMHii6obUfDhmY2mT023klCkGT4SPkB72n0_-VO3fJ29khUCgWagukYt9S0pTCV8JHjDeocEga4RN6sV727-vKYl5RcQSzqIj37oBB_5hN2yxbtSZNZLbFmmSnx58VYc_rsiaNm9ddd7hPoZMJAzZgj8KqD9TJ-znL_a6kXqTbmB6O2J0kdTnScFTEbLT55F9BL0Q",
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
  - `_7185aqqea5jn2hjg8d732k3bb0oncjabb0q40gr1dgn66rrd`
  - `6o2b3g9r6j1ht4v5b2h84bujpq`

Move smoke:

```powershell
uv.exe run h2t-ops calendar create "h2t-ops move smoke 2026-05-25" 2026-05-31 10:00 --duration-min 15 --json
uv.exe run h2t-ops calendar move qoaooo8se7os9nmg0cisper1hc --to omue9dcijvb1qup9v4gvttnslg@group.calendar.google.com --json
uv.exe run h2t-ops calendar delete qoaooo8se7os9nmg0cisper1hc --calendar-id omue9dcijvb1qup9v4gvttnslg@group.calendar.google.com --confirm --json
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
