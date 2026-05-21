---
name: h2t-ops:telegram
description: "Telegram provider access and compatibility workflows. Use for Telegram auth/session, dialogs, messages, saved messages, mentions, and legacy digest/tasks/research workflows. Triggers: telegram, saved messages, telegram digest, задачи из telegram"
compatibility: "Provider reads use h2t-ops telegram. Legacy workflow commands remain available through scripts/telegram_cli.py until portable workflow extraction."
metadata:
  author: lichtpfad
  version: 1.1.0
---

# Telegram

## Boundary

Telegram provider data is evidence, not truth.

- `h2t-ops telegram ...` is the provider connector: auth/session, dialogs, folders, messages, saved-messages, mentions, bootstrap.
- Legacy `telegram_cli.py` workflows remain available for compatibility: `saved`, `digest`, `tasks`, `research`, `students`, `sync`, `scan-chats`, `cleanup`.
- Gemini summaries/classification are analytics outputs and suggestions.
- POS/coordinator decides which proposals become accepted captures/tasks/decisions or provider writes.
- Notion writes are explicit coordinator actions executed through the Notion connector, not Telegram runtime.

## Provider Connector

```bash
h2t-ops telegram auth status --json
h2t-ops telegram auth request-code --phone +XXXXXXXXXXX
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --code XXXXX
h2t-ops telegram dialogs --limit 20 --json
h2t-ops telegram folders --json
h2t-ops telegram messages <entity> --days 7 --limit 200 --json
h2t-ops telegram saved-messages --days 7 --limit 200 --json
h2t-ops telegram mentions --chat-id 123456 --days 7 --json
h2t-ops telegram bootstrap --force --json
```

`saved-messages` returns raw Telegram rows. The legacy `saved` workflow below still produces the Gemini/markdown digest.

## Legacy Compatibility Workflows

These commands are useful and remain available, but their current placement is not the target architecture. They will move to portable workflow scripts with explicit input/output paths.

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/telegram_cli.py"
```

```bash
$CLI saved [--all]
$CLI digest [--all]
$CLI tasks [--all]
$CLI research [--all]
$CLI students [--all]
$CLI sync
$CLI scan-chats [--import-folders]
$CLI cleanup
```

Do not use `cleanup --archive` unless the user explicitly asks for a Telegram account mutation.

## Troubleshooting

### SESSION_INCOMPATIBLE

If `h2t-ops telegram ... --json` returns `SESSION_INCOMPATIBLE`, the Telethon SQLite session file is incompatible with the installed Telethon version.

The connector will not delete credentials automatically. Recovery is manual:

```bash
# move the old session aside yourself, then re-auth
h2t-ops telegram auth request-code --phone +XXXXXXXXXXX
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --code XXXXX
```

If Telegram asks for 2FA:

```bash
h2t-ops telegram auth complete --phone +XXXXXXXXXXX --password YOUR_PASSWORD
```

Passing `--password` can enter shell history. Prefer a future password-stdin/prompt flow when available.

## Config

```text
~/.config/telegram/
  config.json          {"api_id": N, "api_hash": "..."}
  session.session      Telethon session SQLite credential
  auth_state.json      temporary phone_code_hash between auth steps
  dialogs_bootstrapped entity-cache timestamp
  chats.yaml           workflow configuration owned by scripts/workflows, not connector
```

## Future Extraction

Planned follow-up: extract Telegram analytics/POS workflows into portable scripts.

Target shape:

```bash
h2t-ops telegram saved-messages --days 7 --json > saved.json
python scripts/workflows/telegram_digest.py --input saved.json --output digest.md
```

Portable scripts may call Gemini and write declared output paths. They must not be imported by connector registry/help and must not write POS journal/KB directly.
