---
name: youtube-transcript
description: "Extracts YouTube video transcripts with chapters and saves to vault. Triggers: 'youtube', 'video transcript', 'youtube transcript', 'сохрани видео'., 'h2t:youtube-transcript'"
compatibility: "Requires youtube-transcript-api installed in system python. DOR_ROOT env var optional."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

## Переменные

```bash
CLI="${CLAUDE_SKILL_DIR}/scripts/youtube_transcript_cli.py"
```

## Команды

### Сохранить транскрипт (в context/youtube/)

```bash
python3 $CLI <youtube-url-or-id>
```

### Сохранить в проект (в vault/100 Inbox/ с project-id)

```bash
python3 $CLI <url> --project <project-id>
```

### Только вывод в stdout (не сохранять)

```bash
python3 $CLI <url> --print
```

### Указать язык

```bash
python3 $CLI <url> --lang ru
```

## Routing

| Режим | Директория | Имя файла |
|-------|-----------|-----------|
| без `--project` | `$DOR_ROOT/context/youtube/` | `YYYY-MM-DD-{video-id}-{slug}.md` |
| с `--project` | `$VAULT_ROOT/100 Inbox/` | `{project-id} ref {title} – YYYY-MM-DD.md` |

## Переменные окружения

- `DOR_ROOT` — путь к DOR репо (по умолчанию: `~/Projects/DOR`)
- `VAULT_ROOT` — путь к vault (по умолчанию: `$DOR_ROOT/vault`)

## Формат файла

Frontmatter: `source`, `video_id`, `title`, `author`, `url`, `date`, опционально `project` и `type`.
Тело: `## Chapters` (TOC с временными метками) + `## Transcript` (разбит по чаптерам).

## Обработка ошибок

- Нет транскрипта для видео → ошибка "No transcript available for video {id}"
- Нет чаптеров → транскрипт разбивается по 2-минутным блокам с временными метками
- Нет метаданных → title/author = "Unknown", файл всё равно создаётся

## Зависимости

- `youtube-transcript-api` (pip install youtube-transcript-api) — системный python3, не .venv
- `python-dotenv` (pip install python-dotenv)
