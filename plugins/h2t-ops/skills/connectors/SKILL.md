---
name: h2t-ops:connectors
description: "h2t-ops connector hub — load when the user mentions Calendar (events, schedule, FreeBusy, Google Meet), Gmail (email, inbox, draft, send, labels), Drive/Google Docs/Sheets/Slides (files, folders, documents, download, export, upload, any drive.google.com/docs.google.com/sheets.google.com/slides.google.com link), Notion (pages, databases, sync, workspace), Telegram (dialogs, messages, auth, mentions), or MeetGeek (meetings, transcripts, summaries, recordings). Also load for any provider-owned URL or provider I/O command lookup. Research and daily-brief are separate skills."
compatibility: "CLI-first connector navigator. MCP/Playwright are optional and not required."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops Connectors

Provider I/O router for `h2t-ops`.

Use this skill for:

- Google Calendar events, availability, and event writes;
- Gmail search, read, draft, send, and labels;
- Google Drive list, search, download, export, upload, and upload-folder;
- Notion pages, blocks, databases, workspace search, graph, and sync;
- Telegram auth, dialogs, messages, saved messages, mentions, and bootstrap;
- MeetGeek teams, meetings, transcripts, summaries, highlights, insights, recording URLs, and submit-url.

Do not use this skill for:

- `h2t-ops:research`;
- `h2t-ops:daily-brief`;
- Telegram digest/tasks/research/students workflows;
- meeting interpretation or POS transcript intake;
- POS/DOR journal, vault, lake, or database writes.

## Safety Boundary

- Use the `h2t-ops` CLI for provider I/O.
- Do not use raw provider APIs when a connector command is missing.
- Missing provider functionality becomes a structured GitHub issue.
- Do not include secrets, tokens, OAuth codes, cookies, private message bodies, transcript bodies, calendar descriptions, or raw provider payloads in issues or final output.
- Write paths require explicit user intent.
- Paid provider checks belong to `h2t-ops:research`, not this skill.
- POS/DOR canonical state writes are out of scope.

## Router

### Provider URL trigger contract

Load this skill whenever the user provides a provider-owned URL, even if they do not name the provider explicitly.

| URL/domain pattern | Connector | First action |
| --- | --- | --- |
| `drive.google.com/...`, `docs.google.com/document/d/...`, `spreadsheets.google.com/...`, `docs.google.com/spreadsheets/d/...`, `slides.google.com/...`, `docs.google.com/presentation/d/...` | Drive | Extract the object ID and use `h2t-ops drive list/download/export` |
| `calendar.google.com/...`, `meet.google.com/...` | Calendar | Use `h2t-ops calendar` for events/availability; keep Meet links as event artifacts |
| `mail.google.com/...`, `gmail.com/...` | Gmail | Use `h2t-ops gmail` for message/search/draft/send flows |
| `notion.so/...`, `notion.site/...` | Notion | Extract page/database ID when present and use `h2t-ops notion` |
| `t.me/...`, `telegram.me/...` | Telegram | Use `h2t-ops telegram`; do not scrape Telegram URLs directly |
| MeetGeek recording/transcript/share URLs | MeetGeek | Use `h2t-ops meetgeek` |

Do not use Fetch/WebFetch/Playwright as the primary path for these URLs when an `h2t-ops` connector command exists.

| User intent | Connector | Load reference | CLI prefix |
| --- | --- | --- | --- |
| calendar, schedule, events, availability, FreeBusy, Google Meet links | Calendar | `references/calendar.md` | `h2t-ops calendar` |
| email, inbox, Gmail search, read, draft, send, labels | Gmail | `references/gmail.md` | `h2t-ops gmail` |
| Drive files, folders, Docs export, download, upload, upload folder | Drive | `references/drive.md` | `h2t-ops drive` |
| Notion pages, blocks, databases, workspace graph, embedded DBs | Notion | `references/notion.md` | `h2t-ops notion` |
| Telegram auth, dialogs, messages, saved messages, mentions | Telegram | `references/telegram.md` | `h2t-ops telegram` |
| MeetGeek meetings, transcripts, summaries, recordings | MeetGeek | `references/meetgeek.md` | `h2t-ops meetgeek` |
| local .webm / .mp4 recording files to upload to MeetGeek | MeetGeek + Drive | `references/meetgeek.md` → "Local File Upload Flow" | `h2t-ops drive upload` then `h2t-ops meetgeek submit-url` |

### Drive-specific intent routing (important)

- If a user asks to **download**, **browse**, or **open** a Drive artifact (including a shared folder/link), use this skill.
- If the request contains a Drive or Google Docs editor URL (`drive.google.com/.../folders/...`, `drive.google.com/file/d/...`, `docs.google.com/document/d/...`, `docs.google.com/spreadsheets/d/...`, or `docs.google.com/presentation/d/...`), extract the ID and use `h2t-ops drive list/download/export` as the first step.
- For a folder URL, use `h2t-ops drive list <FOLDER_ID> --json`.
- For a file URL, run `h2t-ops drive download <FILE_ID> --dest ./... --json`.
- For a Google Doc URL that the user asks to read, run `h2t-ops drive export <DOC_ID> --format text --dest ./... --json`; use `--format md` when Markdown structure is useful.

### Upload safety rules (mandatory)

- **Never pick a fallback folder on your own.** If the target folder is not found or not accessible, stop and ask: "Папка `<name>` не найдена. Куда загрузить?" Do NOT upload to a different folder without explicit user instruction.
- **Confirm the destination before uploading.** State the folder name and path. Wait for "да" / "yes" / explicit confirmation before running `drive upload`.
- **Sharing after upload.** Use `h2t-ops drive share <FILE_ID>`:
  - Invite by email: `h2t-ops drive share <FILE_ID> --email user@example.com --role writer --json`
  - Open link access: `h2t-ops drive share <FILE_ID> --anyone --confirm-public --json`
  - Inspect permissions: `h2t-ops drive share <FILE_ID> --get-link --json`
  - `--anyone` always requires `--confirm-public` (safety gate against accidental public exposure).

Example:

```text
User: "скачать папку с этого линка"
-> h2t-ops:connectors
-> extract id: 1vlj3QaDXWmlpDM1RUDfzo53WwTyuW9x0
-> h2t-ops drive list <id> --json

User: "почитай документ https://docs.google.com/document/d/159Iero..."
-> h2t-ops:connectors
-> extract id: 159Iero...
-> h2t-ops drive export <id> --format text --dest ./document.txt --json
```

## Workflow

1. Identify the provider and whether the user requested a read or write.
2. Load only the matching reference file.
3. Prefer JSON output for agent processing: add `--json` when supported.
4. For write commands, restate the intended write and require explicit user approval unless the user already gave clear write intent.
5. Run the `h2t-ops` command.
6. Summarize results without dumping private provider bodies.
7. If the command does not exist or provider behavior is wrong, use `references/issue-policy.md`.

## Preflight

Use these when the environment is unclear:

```bash
h2t-ops --version
h2t-ops doctor
h2t-ops connectors
```

For credential readiness, prefer the installed setup skill:

```text
/h2t-core:setup connectors-check
```

## Output Policy

- Provide concise human summaries.
- Keep provider IDs and artifact refs when useful.
- Do not paste raw emails, chat logs, transcripts, calendar descriptions, or private Notion content unless the user explicitly asks to inspect that content.
- For POS-relevant findings, emit a proposed capture rather than writing POS state directly.

## References

- `references/calendar.md`
- `references/gmail.md`
- `references/drive.md`
- `references/notion.md`
- `references/telegram.md`
- `references/meetgeek.md`
- `references/issue-policy.md`

## Codex / AGENTS Adapter

The portable core is the Safety Boundary, Router, Workflow, Preflight, and Output Policy sections.
In any agent context, treat this file as repo guidance and execute the same `h2t-ops` CLI commands.
MCP is not required for these flows.
