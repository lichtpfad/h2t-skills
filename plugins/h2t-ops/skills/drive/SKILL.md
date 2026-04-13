---
name: drive
description: "Google Drive file browser and MeetGeek transcript sync. Use to search files, download transcripts, sync meeting recordings from MeetGeek to context/meetings/. Triggers: 'drive', 'google drive', 'sync meetings', 'meetgeek', 'транскрипты'., 'h2t-ops:drive'"
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json. DOR_ROOT env var for meeting sync."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

## Переменные

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-ops:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/drive_cli.py"
```

## Команды

### Список файлов

```bash
$CLI list [folder-name]
# Примеры:
$CLI list
$CLI list "MeetGeek Files"
```

### Поиск

```bash
$CLI search "query" [--type docx|folder]
```

### Скачать файл

```bash
$CLI download <file-id> [destination-path]
```

### Синхронизация транскриптов (главная команда)

```bash
$CLI sync-meetings [--dry-run] [--folder "MeetGeek Files"]
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
