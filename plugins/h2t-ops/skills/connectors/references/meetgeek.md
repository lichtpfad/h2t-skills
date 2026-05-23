# MeetGeek Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth check | `h2t-ops meetgeek auth-check --json` |
| list teams | `h2t-ops meetgeek teams --json` |
| list meetings | `h2t-ops meetgeek list --limit 20 --json` |
| get meeting | `h2t-ops meetgeek get MEETING_ID_FROM_LIST --json` |
| transcript | `h2t-ops meetgeek transcript MEETING_ID_FROM_LIST --format md` |
| summary | `h2t-ops meetgeek summary MEETING_ID_FROM_LIST --format md` |
| highlights | `h2t-ops meetgeek highlights MEETING_ID_FROM_LIST --format md` |
| insights | `h2t-ops meetgeek insights MEETING_ID_FROM_LIST --format md` |
| recording URL | `h2t-ops meetgeek download-url MEETING_ID_FROM_LIST --json` |
| submit public URL | `h2t-ops meetgeek submit-url URL_TO_RECORDING --json` |

## Safety

- Auth-check, teams, list, get, transcript, summary, highlights, insights, and download-url are provider reads.
- Submit-url writes to MeetGeek and requires explicit user intent.
- Local recording recovery remains a legacy script/coordinator workflow, not connector runtime and not an active per-connector skill.
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

## Common Failures

- Listed meeting returns 404 from singular metadata endpoint: use current connector version with list fallback.
- Transcript missing for a fresh meeting: wait for MeetGeek processing.
- Local recording recovery request: use the existing MeetGeek recovery script/workflow from this repo or a POS/coordinator adapter, not connector runtime.
