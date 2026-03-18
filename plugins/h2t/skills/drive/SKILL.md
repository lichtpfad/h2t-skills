---
name: drive
description: "Google Drive file browser and MeetGeek transcript sync. Use to search files, download transcripts, sync meeting recordings from MeetGeek to context/meetings/. Triggers: 'drive', 'google drive', 'sync meetings', 'meetgeek', 'транскрипты'., 'h2t:drive'"
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json. DOR_ROOT env var for meeting sync."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

## Переменные

```bash
CLI="${CLAUDE_SKILL_DIR}/scripts/drive_cli.py"
```

## Команды

### Список файлов

```bash
python3 $CLI list [folder-name]
# Примеры:
python3 $CLI list
python3 $CLI list "MeetGeek Files"
```

### Поиск

```bash
python3 $CLI search "query" [--type docx|folder]
```

### Скачать файл

```bash
python3 $CLI download <file-id> [destination-path]
```

### Синхронизация транскриптов (главная команда)

```bash
python3 $CLI sync-meetings [--dry-run] [--folder "MeetGeek Files"]
```

Pipeline: Drive/MeetGeek Files/*/Meeting Notes (Google Doc) → export DOCX → context/meetings/*.docx → context/meetings/*.md

Реальная структура Drive (важно!):
- "MeetGeek Files/" — главная папка
- Внутри: подпапки на каждую встречу
- Внутри каждой: Google Doc "Meeting Notes: [название]"

## Переменные окружения

- `DOR_ROOT` — путь к DOR репо (по умолчанию: `~/Projects/DOR`)
- `VAULT_ROOT` — путь к vault (по умолчанию: `$DOR_ROOT/vault`)

Транскрипты сохраняются в `$DOR_ROOT/context/meetings/`.

## Обработка ошибок

- Папка не найдена → запусти `drive list` чтобы увидеть структуру Drive
- OAuth ошибка → удали ~/.config/google-calendar-mcp/tokens.json, запусти gmail skill
- Конвертация не удалась → DOCX сохранён, MD не создан, ошибка в выводе
