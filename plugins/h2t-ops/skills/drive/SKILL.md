---
name: drive
description: "Google Drive file browser through h2t-ops drive. Use to list, search, download, export, and upload Drive files. Triggers: 'drive', 'google drive', 'google docs', 'h2t-ops:drive'"
compatibility: "Requires Google OAuth token with Drive scope. Bootstrap via the same flow as Gmail/Calendar."
metadata:
  author: lichtpfad
  version: 1.1.0
---

# Инструкции

## POS Boundary

For POS, vault/lake, and daily-loop workflows, follow the shared boundary
reference: `../../references/pos-operational-boundary.md`. This skill may read
Drive data through connector tooling, but must not write POS journal rows,
mutate `~/.dor/pos.db`, or modify vault/lake directly except through approved
`pos_ingest` or coordinator workflow. Emit structured proposed captures until
POS journal commands exist.

## Команды

### Список файлов

```bash
h2t-ops drive list [folder] [--max N] [--json]
# Примеры:
h2t-ops drive list
h2t-ops drive list "MeetGeek Files" --max 20
h2t-ops drive list --json
```

### Поиск

```bash
h2t-ops drive search "query" [--type docx|folder] [--max N] [--json]
```

### Список папок

```bash
h2t-ops drive folders [parent] [--json]
```

### Скачать файл

```bash
h2t-ops drive download <file_id> [--dest PATH] [--json]
```

`download` сохраняет файл в `--dest` или в текущую директорию под оригинальным
именем. JSON envelope: `{saved_path, file_id, name, mimeType, size?}`; `size`
присутствует только когда Google Drive вернул размер.

### Экспорт Google Docs / Sheets / Slides

```bash
h2t-ops drive export <file_id> [--dest PATH] [--format text|csv|md|docx|xlsx|pdf|pptx] [--print] [--json]
```

`--print` разрешён только для текстовых форматов: `text`, `csv`, `md`.
Бинарные форматы (`docx`, `xlsx`, `pdf`, `pptx`) пишутся только в файл.

### Загрузить файл

```bash
h2t-ops drive upload <file> --folder "NAME" [--no-convert] [--json]
```

`--folder` обязателен. Drive folder names are not unique: если найдено больше
одной папки с таким именем, команда вернёт ошибку ambiguous folder.

### Legacy: синхронизация транскриптов (не для нового кода)

Subcommand `sync-meetings` исторически жил в `drive_cli.py`, пока у MeetGeek
не было нормального публичного API. Он скачивает Google Doc транскрипты из
папки `MeetGeek Files/`, экспортирует в DOCX в `$DOR_ROOT/context/meetings/`
и вызывает DOR-internal конвертер. Это **coordinator/POS workflow, а не Drive
runtime**, и в `h2t-ops drive ...` он не мигрирован.

Disposition этой команды отслеживается в **#147** (`Retire Drive
sync-meetings legacy workflow`). Для нового кода используй:

- `h2t-ops drive list "MeetGeek Files"` + `h2t-ops drive export <doc_id> --print` для отдельных транскриптов, или
- `h2t-ops meetgeek ...` когда #134 закроет MeetGeek connector.

Не вызывай `h2t-ops drive sync-meetings` — такого верба больше нет.

Legacy-only env vars for the old script:

- `DOR_ROOT` — путь к DOR repo (по умолчанию: `~/Projects/DOR`)
- `VAULT_ROOT` — путь к vault (по умолчанию: `$DOR_ROOT/vault`)

Они не влияют на `h2t-ops drive ...` verbs.

## Обработка ошибок

- Папка не найдена → `h2t-ops drive folders`
- Ambiguous folder → уточни структуру Drive; `--folder-id` не входит в #133
- OAuth scope missing → re-bootstrap Google OAuth with Drive scope
- `export --format md` без `html2text` → установи optional dependency в h2t-ops environment
