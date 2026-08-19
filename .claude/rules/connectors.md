# Connectors Rules

## Provider I/O — только h2t-ops (mandatory)

Drive, Gmail, Calendar, Notion, Telegram, MeetGeek, Granola — **только** через `h2t-ops <connector>`.
- Перед командой: вызвать скилл `h2t-ops:connectors` **или** `h2t-ops <connector> --help`. **Флаги не угадывать** (id папки/файла — позиционный, не `--folder`).
- **Никогда** `gdown` / `rclone` / raw Google API / WebFetch / браузер для provider-файлов — только `h2t-ops`.
- Discover: `h2t-ops connectors`.
- Касается и сабагентов: они получают этот файл, но не загруженные скиллы — грузи reference перед действием.

## MeetGeek + локальные файлы

При любом упоминании MeetGeek + локальные файлы (webm, mp4, запись, upload, залить) — всегда использовать `h2t-ops:connectors`. Не строить кастомный pipeline через h2t-transcription или другие инструменты. Флоу: Drive upload → meetgeek submit-url (см. `references/meetgeek.md` в connectors skill).
