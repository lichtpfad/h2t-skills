---
name: telegram
description: "Reads Telegram saved messages, channels, and work chats. Saves digests to vault and tasks to Notion. Triggers: 'telegram', 'saved messages', 'telegram digest', 'задачи из telegram', 'h2t:telegram'"
compatibility: "Requires Telethon session (machine-local). GEMINI_API_KEY in ~/.dor/secrets.env. DOR_ROOT env var for context output."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Telegram

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/telegram_cli.py"
```

## Команды

### Auth (первичная настройка)

```bash
$CLI auth --phone +XXXXXXXXXXX
$CLI auth --phone +XXXXXXXXXXX --code XXXXX
$CLI auth --phone +XXXXXXXXXXX --password XXXXX  # если 2FA
```

Сессия сохраняется в `~/.config/telegram/session` — повторная аутентификация не нужна.

### Saved Messages → MD
```bash
$CLI saved [--all]
```
Output: `context/telegram/saved-YYYY-MM-DD.md`

### Digest (образовательные каналы)
```bash
$CLI digest [--all]
```
Output: `context/telegram/digest-YYYY-MM-DD.md`

### Tasks (рабочие чаты → Notion)
```bash
$CLI tasks [--all]
```

### Sync (все три pipeline)
```bash
$CLI sync
```

## Config

```
~/.config/telegram/
├── config.json      {"api_id": N, "api_hash": "..."}
├── session          Telethon session (SQLite)
└── last_sync.json   timestamps per pipeline

~/.config/telegram/chats.yaml — конфиг каналов и чатов
```

## Обработка ошибок

- **SessionExpiredError**: повторите `auth`
- **GEMINI_API_KEY не найден**: добавьте в `~/.dor/secrets.env`
