---
name: telegram
description: "Reads Telegram saved messages, channels, and work chats. Saves digests to vault and tasks to Notion. Triggers: 'telegram', 'saved messages', 'telegram digest', 'задачи из telegram'."
compatibility: "Requires Telethon session (machine-local). GEMINI_API_KEY in ~/.dor/secrets.env. DOR_ROOT env var for context output."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

## Переменные

```
SKILL_DIR="/Users/stanislav_glazov/Projects/DOR/.claude/skills/telegram"
PYTHON="/Users/stanislav_glazov/Projects/DOR/.venv/bin/python3"
CLI="$PYTHON $SKILL_DIR/telegram_cli.py"
```

## Команды

### Auth (первичная настройка)

Двухфазная аутентификация:

```bash
# Шаг 1: отправить SMS-код
$CLI auth --phone +XXXXXXXXXXX

# Шаг 2: ввести код из SMS
$CLI auth --phone +XXXXXXXXXXX --code XXXXX

# Если включена 2FA:
$CLI auth --phone +XXXXXXXXXXX --password XXXXX
```

Сессия сохраняется в `~/.config/telegram/session` — повторная аутентификация не нужна.

### Saved Messages → Obsidian

```bash
# Только новые (с последнего запуска)
$CLI saved

# Все сообщения (полная история)
$CLI saved --all
```

**Output:** `content/learning/telegram/saved-YYYY-MM-DD.md`

### Digest (образовательные каналы)

```bash
$CLI digest [--all]
```

**Output:** `content/learning/telegram/digest-YYYY-MM-DD.md`

> Требует: заполнить `DIGEST_CHANNELS` в `telegram_cli.py`

### Tasks (рабочие чаты → Notion)

```bash
$CLI tasks [--all]
```

**Output:** `context/actions/telegram-tasks-YYYY-MM-DD.md` + задачи в Notion (confidence >= 0.8)

> Требует: заполнить `WORK_CHATS` в `telegram_cli.py`

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
```

`GEMINI_API_KEY` — из `.env` в корне репо.

## Обработка ошибок

- **SessionExpiredError**: повторите `auth`
- **GEMINI_API_KEY не найден**: добавьте в `.env`
- **Rate limit Telegram**: добавьте `asyncio.sleep(0.5)` между запросами к каналам
