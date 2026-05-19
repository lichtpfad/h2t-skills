---
name: gmail
description: "Reads and sends Gmail via the h2t-ops CLI. Use for checking inbox, reading messages, searching mail, sending or drafting messages, and managing labels. Triggers: 'check email', 'show inbox', 'read message', 'search gmail', 'send email', 'create draft', 'gmail labels', 'h2t-ops:gmail'"
compatibility: "Requires the `h2t-ops` CLI (run /h2t-core:setup) and Google OAuth credentials in ~/.config/google-calendar-mcp/ or ~/.config/gmail/"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# Gmail (h2t-ops connector)

## POS Boundary

For POS and daily-loop workflows, follow the shared boundary reference:
`../../references/pos-operational-boundary.md`. This skill may read Gmail data
through `h2t-ops`, but must not write POS journal rows, mutate `~/.dor/pos.db`,
or modify vault/lake directly. Emit structured proposed captures until POS
journal commands exist.

## Availability (cross-platform contract)

`h2t-ops --version` exits 0 when installed (identical on PowerShell and POSIX — no shell idioms).
If it fails: run `/h2t-core:setup`. `h2t-ops doctor` reports version, install path, connectors,
and secrets presence (no network).

## Secrets

Google OAuth — resolved from `~/.config/google-calendar-mcp/credentials.json` (shared with
calendar, token file `tokens.json` — plural) or `~/.config/gmail/credentials.json` +
`token.json` (singular). Missing credentials or unauthenticated state → exit 3 (`config`).

§4.1 non-interactive behavior: this connector will NOT open a browser. The two exit-3 cases
have concrete fixes:

- **Missing `credentials.json`** → download OAuth client credentials from the Google Cloud
  Console and place them at `~/.config/gmail/credentials.json` (or
  `~/.config/google-calendar-mcp/credentials.json`).
- **Have `credentials.json`, no valid token and no refresh token** → run the one-time
  interactive bootstrap OUTSIDE this connector (the legacy standalone script does the
  browser OAuth and writes the token):
  ```bash
  python plugins/h2t/skills/gmail/scripts/gmail_cli.py labels
  ```
  This performs `run_local_server` OAuth and writes `~/.config/gmail/token.json` (or
  `~/.config/google-calendar-mcp/tokens.json` if the shared dir is used). Afterwards,
  `h2t-ops gmail …` reuses the token and refreshes it silently.

## Commands

| Command | Purpose |
|---|---|
| `h2t-ops gmail list [--max N] [--unread] [--query Q]` | list messages (default 10); `--unread` filters to unread; `--query` accepts Gmail search syntax |
| `h2t-ops gmail read <message_id>` | message detail; use `--format md` for the full formatted message (headers + body) |
| `h2t-ops gmail search <query> [--max N]` | search by Gmail query string; supports `from:`, `subject:`, `after:YYYY/MM/DD`, `before:`, `has:attachment`, `is:unread` (e.g. `from:alice after:2024/01/01 has:attachment`) |
| `h2t-ops gmail send <to> <subject> [body] [--file f] [--attach file ...] [--draft]` | send message; body positional OR `--file f` required; `--draft` saves instead of sends |
| `h2t-ops gmail draft <to> <subject> [body] [--file f] [--attach file ...] [--thread-id ID] [--reply-to MID]` | create a draft; body positional OR `--file f` required |
| `h2t-ops gmail labels` | list all labels (system and user) |
| `h2t-ops gmail label <message_id> [--add label ...] [--remove label ...]` | add or remove labels on a message |

Output flags (every command): `--json` (raw envelope), `--format md` (markdown detail),
default = concise human text.

## Examples

```bash
h2t-ops gmail list --max 5 --unread
h2t-ops gmail search "from:alice after:2024/01/01 has:attachment" --max 20 --json
h2t-ops gmail read 18c3f4a12b9e7d --format md
h2t-ops gmail send alice@example.com "Meeting notes" --file notes.md --attach slides.pdf
h2t-ops gmail label 18c3f4a12b9e7d --add STARRED --remove UNREAD
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | provider / runtime error |
| 2 | usage / bad args |
| 3 | config / secrets missing |
| 4 | auth / permission denied |
| 5 | not found / empty resource |
| 6 | network / timeout |

`--json` errors go to stderr as `{"ok":false,"provider":"gmail","error":{...}}`; exit is non-zero.

## When to use / not use

- ✅ Read, search, or list Gmail messages.
- ✅ Send messages or create drafts, with or without attachments.
- ✅ Manage labels on messages.
- ❌ Bulk export of an entire mailbox or folder — out of scope.
- ❌ Download attachments from received messages — not supported by this connector.
- ❌ Do NOT fall back to raw HTTP/IMAP if a command fails — report the exit code/error.

## Deprecated

`h2t-ops ingest gmail …` still works (forwards here) but prints a deprecation notice to
stderr unless `--json`. Migrate call sites to `h2t-ops gmail …`.

> In the internal umbrella CLI, `h2t gmail …` may be available later via h2t-ai delegation. Skills should call `h2t-ops …` directly unless a project explicitly provides the umbrella bridge.
