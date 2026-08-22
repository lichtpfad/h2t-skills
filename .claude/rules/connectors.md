# Connectors Rules

## Provider I/O — h2t-ops only (mandatory)

Drive, Gmail, Calendar, Notion, Telegram, MeetGeek, Granola — **only** through
`h2t-ops <connector>`.
- Before running a command: invoke the `h2t-ops:connectors` skill **or** `h2t-ops <connector> --help`. **Do not guess flags** (a folder or file id is positional, not `--folder`).
- **Never** `gdown` / `rclone` / raw Google API / WebFetch / a browser for provider files — only `h2t-ops`.
- Discover: `h2t-ops connectors`.
- This applies to subagents too: they receive this file but not the loaded skills — load the reference before acting.

## MeetGeek + local files

Whenever MeetGeek comes up together with local files (webm, mp4, recording, upload), always
use `h2t-ops:connectors`. Do not build a custom pipeline through h2t-transcription or other
tools. The flow is: Drive upload → meetgeek submit-url (see `references/meetgeek.md` in the
connectors skill).
