# Telegram Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth status | `h2t-ops telegram auth status --json` |
| log in by QR (preferred) | `h2t-ops telegram auth qr` — run by the person in a terminal |
| request login code | `h2t-ops telegram auth request-code --phone +10000000000 --json` |
| resend code by next channel | `h2t-ops telegram auth resend --json` |
| complete login | `h2t-ops telegram auth complete --phone +10000000000 --code 12345 --password --json` |
| list dialogs | `h2t-ops telegram dialogs --limit 20 --json` |
| list folders | `h2t-ops telegram folders --json` |
| read messages | `h2t-ops telegram messages ENTITY_FROM_DIALOGS --limit 20 --json` |
| download attachment | `h2t-ops telegram download-media ENTITY MSG_ID --out /path/to/dir --json` |
| read saved messages | `h2t-ops telegram saved-messages --limit 20 --json` |
| read mentions | `h2t-ops telegram mentions --chat-id CHAT_ID_FROM_DIALOGS --days 7 --limit 20 --json` |
| warm entity cache | `h2t-ops telegram bootstrap --json` |
| send file attachment | `h2t-ops telegram send-file ENTITY /path/to/file --caption "optional" --confirm-send --json` |
| forward message | `h2t-ops telegram forward-message TO_ENTITY --from FROM_ENTITY --message-id MSG_ID --confirm-forward --json` |
| delete message | `h2t-ops telegram delete-message ENTITY MSG_ID --confirm --json` |

## Safety

- Auth status, dialogs, folders, messages, saved messages, mentions, bootstrap, and download-media are provider reads.
- `messages` output now carries a `media` field (kind/name/size/mime_type/ext) per message, or `null` when there is no attachment — use it to find `MSG_ID` before `download-media`.
- `download-media` writes to `--out` (default `~/Downloads`); it fails loud with a ProviderError when the message has no downloadable media.
- Auth qr, request-code, resend and complete modify local Telegram session state and require explicit user intent.
- `send-file`, `forward-message`, and `delete-message` are write/destructive operations. Require explicit user approval per command.
- `send-file` requires `--confirm-send` flag; the CLI raises UsageError without it.
- `forward-message` requires `--confirm-forward` flag; the CLI raises UsageError without it.
- `delete-message` requires `--confirm` flag; the CLI raises UsageError without it.
- `send-file` sends the file as a Telegram attachment (binary). The existing `send --file` command reads a local file as *text* and sends the text content — these are distinct operations.
- Telegram digest/tasks/research/students workflows are not connector operations.
- Do not include raw chat text, phone numbers, or private usernames in GitHub issues.

## Commands

```bash
h2t-ops telegram auth status --json
h2t-ops telegram dialogs --limit 20 --json
h2t-ops telegram saved-messages --limit 20 --json
h2t-ops telegram messages ENTITY_FROM_DIALOGS --limit 20 --json
```

## Auth

Telegram expects `~/.config/telegram/config.json` with `api_id` and `api_hash` (from
https://my.telegram.org/apps), plus a Telethon session file after login.

**Log in by QR first.** `auth qr` draws a QR in the terminal; the person scans it on a
phone already logged in (Settings → Devices → Link Desktop Device). No code is sent, so
nothing can get lost. It is interactive — the QR, the wait, a hidden 2FA prompt — so the
person runs it in their own terminal; an agent does not run it for them.

The code path is the fallback, for an account with no other logged-in device:

- `request-code` reports where the code went: `channel` (`app`, `sms`, `call`, `email`),
  `where` in words, `email_pattern` when it went to email, and `next_channel`. A code with
  `channel: app` is a message in the verified "Telegram" chat on a logged-in device — not SMS.
- `resend` asks for the next channel. `SEND_CODE_UNAVAILABLE` means there is none: stop
  requesting codes and use `auth qr`. Every new request voids the previous code.
- `--password` with no value asks for the 2FA password hidden; a value on the command line
  lands in shell history and in an agent transcript.
- Never advise logging out of Telegram on any device to "get a code": the logged-in
  devices are where app codes arrive, and the QR is scanned from them.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- `SESSION_INCOMPATIBLE`: move the old Telethon session aside and re-authenticate.
- `PEER_UNRESOLVED`: the peer, not the session. `ENTITY` and `--chat-id` resolve a
  chat title or `@username` directly; a numeric `id` from `dialogs` carries no
  access hash, so it works only once `bootstrap --force` has cached that peer.
- Two-factor password required: run auth complete with the password after explicit user consent.
- Workflow request such as digest or task extraction: keep provider reads here, then route analytics to portable workflow scripts or POS/coordinator.

## Manual E2E Smoke Recipe

> Telegram write/forward/delete live smoke requires explicit user approval per command and resource.
> Automated live E2E for send-file/forward-message/delete-message is intentionally skipped.
> Only read-only operations run in automated E2E.

### Manual approval template (required before any destructive smoke)

```
Approve this one manual smoke?
Command: h2t-ops telegram <cmd> <entity> ...
Resource: <entity or message id>
Effect: send/forward/delete
Rollback: delete message manually or N/A
```

### Unit/contract test coverage

The following commands are verified by unit tests (mocked Telethon client):

- `send-file` — requires `--confirm-send` flag (UsageError without it); dispatches entity, path, and optional caption to `client.send_file`
- `forward-message` — requires `--confirm-forward` flag (UsageError without it); dispatches to/from entities and message_id to `client.forward_message`
- `delete-message` — requires `--confirm` flag (UsageError without it); dispatches to `client.delete_message`
