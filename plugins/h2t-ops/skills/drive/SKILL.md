---
name: h2t-ops:drive
description: "Google Drive file browser through h2t-ops drive. Use to list, search, download, export, and upload Drive files. Triggers: 'drive', 'google drive', 'google docs', 'h2t-ops:drive'"
compatibility: "Requires Google OAuth token with Drive scope. Bootstrap via the same flow as Gmail/Calendar."
metadata:
  author: lichtpfad
  version: 1.1.1
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

### Retired: синхронизация транскриптов

`sync-meetings` retired in #147. It was a historical Drive-owned workaround
for meeting backfill before the MeetGeek API connector existed: discover docs
under `MeetGeek Files/`, export DOCX, write into DOR `context/meetings/`, then
run a local converter.

That useful workflow shape is preserved as future POS/coordinator semantics,
not as a Drive capability:

1. discover historical meeting artifacts;
2. assign or resolve a weak `meeting_key`;
3. skip already ingested artifacts;
4. store raw/readable transcript artifacts with provenance;
5. pass them to POS transcript intake;
6. leave journal/tasks/decisions behind review gates.

Use `h2t-ops drive list/search/export/download/upload` only for Drive provider
I/O. For MeetGeek artifacts, use `h2t-ops meetgeek ...`; for future batch
meeting backfill, use the POS/coordinator workflow when it exists.

## Обработка ошибок

- Папка не найдена → `h2t-ops drive folders`
- Ambiguous folder → уточни структуру Drive; `--folder-id` не входит в #133
- OAuth scope missing → re-bootstrap Google OAuth with Drive scope
- `export --format md` без `html2text` → установи optional dependency в h2t-ops environment
