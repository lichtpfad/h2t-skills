# MeetGeek Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth check | `h2t-ops meetgeek auth-check --json` |
| list teams | `h2t-ops meetgeek teams --json` |
| list meetings | `h2t-ops meetgeek list --limit 20 --json` |
| list meetings by date range | `h2t-ops meetgeek list --from 2026-05-01 --to 2026-05-27 --json` |
| get meeting | `h2t-ops meetgeek get MEETING_ID_FROM_LIST --json` |
| transcript | `h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md` |
| summary | `h2t-ops meetgeek summary MEETING_ID_FROM_LIST --format md` |
| highlights | `h2t-ops meetgeek highlights MEETING_ID_FROM_LIST --format md` |
| insights | `h2t-ops meetgeek insights MEETING_ID_FROM_LIST --format md` |
| action items | `h2t-ops meetgeek action-items MEETING_ID_FROM_LIST --json` |
| recording URL | `h2t-ops meetgeek download-url MEETING_ID_FROM_LIST --json` |
| submit public URL | `h2t-ops meetgeek submit-url URL_TO_RECORDING --json` |

## Safety

- Auth-check, teams, list, get, transcript, summary, highlights, insights, and download-url are provider reads.
- Submit-url writes to MeetGeek and requires explicit user intent.
- Local recording recovery remains a legacy script/coordinator workflow, not connector runtime and not an active per-connector skill.
- A public Drive link is a step in the flow, not a resting state — see step 5 of the upload flow.
- Do not include transcript bodies in GitHub issues.

## Commands

```bash
h2t-ops meetgeek auth-check --json
h2t-ops meetgeek list --limit 20 --json
h2t-ops meetgeek get MEETING_ID_FROM_LIST --json
h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md
```

## Auth

MeetGeek expects `MEETGEEK_API_KEY` from environment, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, or legacy `~/.dor/secrets.env`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Local File Upload Flow

MeetGeek API accepts only **public URLs** — not local files. For local `.webm` / `.mp4` recordings:

1. Upload to Drive with explicit parent folder and make public:
   ```bash
   h2t-ops drive upload PATH_TO_FILE.webm --parent-id DRIVE_FOLDER_ID --no-convert --json
   h2t-ops drive share FILE_ID --anyone --confirm-public --json
   ```
2. Submit the public Drive URL to MeetGeek — **use `drive.usercontent.google.com`**, not `drive.google.com`:
   ```bash
   h2t-ops meetgeek submit-url "https://drive.usercontent.google.com/download?id=FILE_ID&export=download&confirm=t" --json
   ```
3. Keep the Drive link public until MeetGeek finishes processing (check with `h2t-ops meetgeek list`).
4. Fetch transcript once processing is complete:
   ```bash
   h2t-ops meetgeek transcript MEETING_ID --format md
   ```
5. **Revoke the public link afterwards.** Step 1 makes the file readable by anyone who
   has the URL, and MeetGeek only needs that during the fetch. Left in place it does not
   expire: 26 recordings shared this way stayed world-readable for 108 days (#386).
   ```bash
   h2t-ops drive share FILE_ID --revoke-anyone --json
   ```

**Multiple files:** upload and submit one at a time.

**MeetGeek rejects webm as "corrupt":** known MeetGeek bug — the Drive URL workaround (step 2) bypasses it.

**Do NOT** use `https://drive.google.com/file/d/FILE_ID/view` — that is a viewer URL, not a download URL.

**Do NOT** route local recording files to `h2t-transcription` — that pipeline is for Vimeo/course content, not meeting recordings.

## Retention (recovery script, not the connector)

The recovery pipeline in `plugins/h2t-ops/skills/meetgeek/scripts/` sweeps after itself:
every `upload --from-file` batch revokes public ACLs and deletes staged media older than
24 hours, then reports what it did under `housekeeping` in its JSON. Both sweeps are also
available on their own:

```bash
meetgeek_cli.py drive-audit --revoke --min-age-hours 24
meetgeek_cli.py staging-purge --dry-run
```

The grace period is not a preference. `submit-url` returns when MeetGeek accepts the URL,
not when it has fetched the file, so anything retired on the strength of Stage 3 returning
success can be pulled out from under the download. `staging-purge` deletes a converted file
only when the recording is `submitted`, its source recording still exists locally, and the
Drive copy is still there — each gate is a way the deletion would otherwise be the loss of
the last copy.

## Common Failures

- Listed meeting returns 404 from singular metadata endpoint: use current connector version with list fallback.
- Transcript missing for a fresh meeting: wait for MeetGeek processing.
- Local recording recovery request: use the existing MeetGeek recovery script/workflow from this repo or a POS/coordinator adapter, not connector runtime.
- **MeetGeek silently drops submitted recording (no error, but never appears in list):** `drive.google.com/uc?export=download` returns HTML (confirmation page or quota error) instead of the file. Fix: use `drive.usercontent.google.com` — `https://drive.usercontent.google.com/download?id=FILE_ID&export=download&confirm=t`. This is Google's dedicated file-delivery endpoint and bypasses all intermediate pages. `drive.google.com` URLs are unreliable for MeetGeek submissions regardless of `&confirm=t`.

## Manual E2E Smoke Recipe

> action-items and list are read-only. Safe for automated E2E with env-provided meeting ID.

### action-items (read-only)

```python
import subprocess
result = subprocess.run(
    ["h2t-ops", "meetgeek", "action-items", meeting_id, "--json"],
    capture_output=True, text=True,
)
# Returns {"meeting_id": ..., "action_items": [...], "source": "summary"}
```

### list with date range (read-only)

```python
import subprocess
result = subprocess.run(
    ["h2t-ops", "meetgeek", "list",
     "--from", "2026-05-01", "--to", "2026-05-27", "--json"],
    capture_output=True, text=True,
)
```
