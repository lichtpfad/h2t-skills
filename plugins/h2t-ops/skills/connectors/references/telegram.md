# Telegram Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth status | `h2t-ops telegram auth status --json` |
| request login code | `h2t-ops telegram auth request-code --phone +10000000000 --json` |
| complete login | `h2t-ops telegram auth complete --phone +10000000000 --code 12345 --json` |
| list dialogs | `h2t-ops telegram dialogs --limit 20 --json` |
| list folders | `h2t-ops telegram folders --json` |
| read messages | `h2t-ops telegram messages ENTITY_FROM_DIALOGS --limit 20 --json` |
| read saved messages | `h2t-ops telegram saved-messages --limit 20 --json` |
| read mentions | `h2t-ops telegram mentions --chat-id CHAT_ID_FROM_DIALOGS --days 7 --limit 20 --json` |
| warm entity cache | `h2t-ops telegram bootstrap --json` |

## Safety

- Auth status, dialogs, folders, messages, saved messages, mentions, and bootstrap are provider reads.
- Request-code and complete modify local Telegram session state and require explicit user intent.
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

Telegram expects `~/.config/telegram/config.json` with `api_id` and `api_hash`, plus a Telethon session file after login.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- `SESSION_INCOMPATIBLE`: move the old Telethon session aside and re-authenticate.
- Two-factor password required: run auth complete with the password after explicit user consent.
- Workflow request such as digest or task extraction: keep provider reads here, then route analytics to portable workflow scripts or POS/coordinator.
