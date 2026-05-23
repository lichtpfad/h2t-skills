# Gmail Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| list recent messages | `h2t-ops gmail list --max 10 --json` |
| search mail | `h2t-ops gmail search "from:example@example.com newer_than:7d" --max 10 --json` |
| read message | `h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json` |
| list labels | `h2t-ops gmail labels --json` |
| create draft | `h2t-ops gmail draft person@example.com "Subject" "Body" --json` |
| send email | `h2t-ops gmail send person@example.com "Subject" "Body" --json` |
| modify labels | `h2t-ops gmail label MESSAGE_ID_FROM_SEARCH --add LabelName --json` |

## Safety

- List, search, read, and labels are read-only.
- Draft, send, and label modification require explicit user intent.
- Prefer draft over send when user intent is ambiguous.
- Do not include raw email bodies, addresses, or private snippets in GitHub issues.

## Commands

```bash
h2t-ops gmail list --max 10 --json
h2t-ops gmail search "subject:invoice newer_than:30d" --max 10 --json
h2t-ops gmail read MESSAGE_ID_FROM_SEARCH --json
h2t-ops gmail draft person@example.com "Follow-up" "Draft body" --json
```

## Auth

Gmail reuses Google OAuth credentials under `~/.config/google-calendar-mcp/` or `~/.config/gmail/`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Common Failures

- Missing OAuth token: run Google OAuth setup.
- Expired token: refresh OAuth through the configured Google auth flow.
- Write command ambiguity: create a draft unless the user explicitly says send.
