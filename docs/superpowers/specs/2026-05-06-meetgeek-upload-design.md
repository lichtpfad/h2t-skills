# meetgeek upload + media conversion — design spec

**Date:** 2026-05-06
**Status:** Draft — pending plan
**Repo:** lichtpfad/h2t-skills (plugin: `h2t-ops`, skill: `meetgeek`)
**Issue:** lichtpfad/h2t-skills#93
**Target version:** h2t-ops 1.1.0 (minor — feature addition)

---

## 1. Context & Why

`h2t-ops:meetgeek` 1.0.7 покрывает только pull-side (list/transcript/sync/etc) — нет способа загрузить локальный файл в MeetGeek.

Реальная боль (User, 2026-05-06): за пару недель накопилось ~16 `.webm`-файлов созвонов на MacBook (`~/Downloads/meetgeek-recording-*.webm`), которые автоматически не подтянулись в MeetGeek (вероятно, из-за multi-track audio или кодек-issue), а ручной upload в UI отклоняется с misleading «file is too long». MP4 в тех же тестах принимается. Цель — автоматизировать конверсию + ingestion.

API contract `/v1/upload` верифицирован live 2026-05-06:

- POST `application/json` only
- Required: `download_url` (must be valid URL — MeetGeek сам качает файл)
- Optional: `language`, `title`
- Response: `202 Accepted`, обработка асинхронная
- Если `webhook_url` не настроен — message в response, но это **не ошибка**

То есть `/v1/upload` — это **URL ingestion**, а не direct file upload. Локальный файл должен где-то жить с публичным URL.

## 2. Decisions (locked-in)

| Decision | Choice | Rationale |
|---|---|---|
| Storage для public URL | Google Drive через `h2t-ops:drive` skill | Reuse существующего OAuth, persistent, привычный UX |
| Source format | `.webm` (Google Meet / MeetGeek live recording) | Подтверждённый source у текущего пользователя |
| Target format | `.mp4` H.264 + AAC | Самый надёжно принимаемый MeetGeek контейнер |
| ffmpeg dependency | `imageio-ffmpeg` (pip dep) | Cross-platform Win+Mac, авто-устанавливается в `~/.h2t/venv`, нулевая нагрузка на user |
| Drive folder layout | `Drive/MeetGeek Uploads/{YYYY-MM-DD}/` | Простота сейчас, дата = дата запуска batch |
| Drive permission | `anyone with link, role: reader` | Обязательно для MeetGeek download_url |
| Cleanup | Persistent (no auto-delete) | Можно проверить что отправилось; manual cleanup в follow-up |
| CLI shape | Composable subcommands (Approach 2) | Каждая стадия тестируется отдельно, `convert` re-usable |

## 3. Architecture

Все добавки внутри существующего `meetgeek_cli.py` (single-file pattern сохраняем). Никаких новых модулей.

```
meetgeek_cli.py (single-file, growth from 1.0.7)
├── cmd_convert        webm → mp4   (imageio-ffmpeg)
├── cmd_drive_upload   mp4  → URL   (Google Drive API)
└── cmd_upload         URL  → 202   (POST /v1/upload)
                       --from-file orchestrates all three

External state:
  ~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/*.mp4    (retry cache)
  ~/.dor/lake/meetgeek/uploads-staging/manifest.jsonl        (state-of-truth, append-only)
  Drive: MeetGeek Uploads/{YYYY-MM-DD}/*.mp4                  (anyone-with-link)
```

**State recovery:** манифест append-only jsonl. Каждая стадия (`converted` → `in-drive` → `submitted`) пишет новую строку. Повторный запуск читает manifest, видит на каком шаге остановилось, продолжает.

**Зависимости:**

- New pip: `imageio-ffmpeg`
- Reused: `requests`, `python-dotenv`, `google-api-python-client` (уже у drive_cli)
- ffmpeg binary: бандлится через `imageio_ffmpeg.get_ffmpeg_exe()`
- **ffprobe не предоставляется imageio-ffmpeg.** Поэтому stream-detection делаем через сам ffmpeg: `ffmpeg -hide_banner -i in.webm -f null -` → парсим stderr regex `Stream #\d+:\d+(\([\w]+\))?: Audio:` для подсчёта audio streams. Надёжно для нашего use-case (typed source: webm/mp4/m4a).

**Reuse Drive helpers:** функция `get_drive_service()` из `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` импортируется как пакет (через `sys.path.append` к sibling скрипту) или копируется minimal version. Решается на этапе implementation — обе опции допустимы при условии что OAuth token path остаётся `~/.config/google-calendar-mcp/tokens.json` без изменений.

## 4. Components

### 4.1 `cmd_convert`

```bash
meetgeek convert <in.webm> [-o out.mp4] [--audio-only] [--mix-mode amix|first|keep] [--probe]
```

**Inputs:** один webm (или другой декодируемый ffmpeg формат).
**Outputs:** mp4 (видео+аудио) или m4a (`--audio-only`).
**Side effects:** запись в staging-папку, stderr-progress.

Поведение:

1. Probe через `ffmpeg -hide_banner -i in -f null -`: парсим stderr на `Stream #...: Audio:` matches → audio stream count; `Duration: HH:MM:SS.MS` → длительность.
2. `--probe` без `-o` → печатает summary в stdout (audio_streams, duration, has_video, codecs), exit 0. Полезно для diagnostics.
3. `-o` не задан → `~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/{basename}.mp4`.
4. Если выходной файл уже существует с size > 0 → skip, warn в stderr.
5. ffmpeg recipe выбирается по числу audio streams. **Default mix-mode = `amix`**, реально *суммирует* дорожки — это семантика правильная для transcription, в отличие от `amerge` (склеивает в multichannel layout). Конкретные filtergraphs:
   - `count == 1`:
     ```
     ffmpeg -y -i in \
       -c:v libx264 -preset medium -crf 23 \
       -c:a aac -b:a 192k -ar 48000 -ac 2 \
       out
     ```
   - `count > 1` и `--mix-mode amix` (default — сумма дорожек, нормализованная):
     ```
     ffmpeg -y -i in \
       -filter_complex "[0:a:0][0:a:1]...[0:a:N-1]amix=inputs=N:duration=longest:dropout_transition=0,aresample=48000[a]" \
       -map 0:v? -map "[a]" \
       -c:v libx264 -preset medium -crf 23 \
       -c:a aac -b:a 192k -ac 2 \
       out
     ```
     `aresample=48000` гарантирует одинаковый sample rate перед mix; `0:v?` (с `?`) терпимо к audio-only source.
   - `--mix-mode first`: `-map 0:v? -map 0:a:0 ...`
   - `--mix-mode keep`: `-map 0 -c:v libx264 -c:a aac ...` (все исходные streams сохраняются; debug only)
6. `--audio-only` использует `-vn`, выход `.m4a`. Filtergraph для multi-track такой же (amix), просто без видео-маппинга.
8. Sanity check: после ffmpeg, проверяем mp4 size > 1KB; иначе удаляем и raise.
9. Stdout: путь к mp4.

### 4.2 `cmd_drive_upload`

```bash
meetgeek drive-upload <file> [--folder "MeetGeek Uploads/2026-05-06"] [--make-public]
```

**Inputs:** local file path.
**Outputs:** JSON `{drive_id, web_url, download_url, created: bool}`.

Поведение:

1. `get_drive_service()` — re-use из `drive_cli.py` (тот же tokens.json).
2. Default folder: `MeetGeek Uploads/{YYYY-MM-DD}/`. Создаётся если нет (recursive: `MeetGeek Uploads/` тоже создастся).
3. Idempotent search: `files.list(q="name='X' and '<folder_id>' in parents and trashed=false")`. Обрати внимание: правильный Drive Query syntax — `'<folder_id>' in parents` (а не `parents in '<folder_id>'`). Если совпадение — return `{drive_id, ..., created: false}`.
4. Иначе `MediaFileUpload(file, resumable=True, chunksize=...)` → upload.
5. Если `--make-public` (default true) → `permissions.create({type:"anyone", role:"reader"})`.
6. `download_url = f"https://drive.google.com/uc?export=download&id={drive_id}"`.
7. Stdout: вышеуказанный JSON.

### 4.3 `cmd_upload` (новая команда)

В текущем `meetgeek_cli.py` (1.0.7) команды `upload` нет — её нужно создать с нуля. Это новый argparse-branch, новый handler-функция, новые тесты — не «расширение». Direct mode (`--download-url`) и orchestrated mode (`--from-file`) реализуются вместе как два сценария одной команды:

```bash
# Direct: URL уже есть
meetgeek upload --download-url URL [--title T] [--language ru|en|auto]

# Orchestrated (new)
meetgeek upload --from-file <path-or-glob> [--audio-only] [--language ru]
                [--mix-mode amix|first|keep] [--skip-existing] [--dry-run]
```

Поведение `--from-file`:

1. `--from-file` принимает path к файлу ИЛИ glob ИЛИ путь к папке (в случае папки — `*.webm` rekursivно).
2. Загружаем staging manifest → set of `source_webm` paths уже processed.
3. `--skip-existing` (default true): если path в manifest со status=submitted — skip.
4. `--dry-run`: печатаем план, exit 0.
5. Per file pipeline:
   - probe / convert → `mp4_path` (resume-friendly: skip если cached)
   - drive_upload → `drive_id, download_url` (idempotent search)
   - POST `/v1/upload {download_url, title, language}` → 202
   - manifest append: финальная entry с `status: "submitted"`
6. **Default behavior:** `--skip-existing` ВКЛ по умолчанию. Можно отключить через `--no-skip-existing` (re-process даже если уже submitted в manifest). Argparse: `BooleanOptionalAction` или ручная пара флагов.
7. Title default: `"Meeting {date} {HH:MM} UTC"`, parsed из имени `meetgeek-recording-{ISO}Z.webm`. Override через `--title` применяется ко **всем** файлам batch (per-file override out of scope для этого milestone).
7. Stderr: progress per file `[N/total] basename  convert ✓  drive ✓  submit ✓`.
8. Stdout: финальная сводка JSON `{processed, skipped, errors, drive_folder, note}`.

## 5. Data flow (single file, end-to-end)

```
~/Downloads/meetgeek-recording-2026-01-20T15-44-31-132Z.webm
  ↓ [ffprobe — 3 audio tracks → mix-mode=amix]
  ↓ [cmd_convert]
~/.dor/lake/meetgeek/uploads-staging/2026-05-06/meetgeek-recording-2026-01-20T15-44-31-132Z.mp4
  ↓ [cmd_drive_upload]
Drive: MeetGeek Uploads/2026-05-06/meetgeek-recording-2026-01-20T15-44-31-132Z.mp4
        permissions: anyone-with-link, reader
  ↓ [download_url = https://drive.google.com/uc?export=download&id=<id>]
  ↓ [cmd_upload POST /v1/upload]
MeetGeek API: 202 Accepted (async processing 5-30 min)
  ↓ [manifest.jsonl append]
~/.dor/lake/meetgeek/uploads-staging/manifest.jsonl
  → status: submitted
  ↓ [later — separate command]
meetgeek sync --since-cursor → новый митинг подтянется в historical/
```

### Manifest reader semantics

Manifest — append-only jsonl. Per source webm может быть несколько строк (одна на каждое успешное завершение стадии). **Правила чтения:**

- **Effective state for a source = последняя строка с тем же `source_webm`** (linear scan, "last write wins").
- Поля reading order: `source_webm` определяется по absolute path после `Path(p).resolve()`. Любая иная нормализация — out of scope.
- `--skip-existing` (default ON): skip processing если effective.status == `"submitted"` И `effective.source_size_bytes == current_size_bytes` И `effective.source_mtime == current_mtime`. Если file changed (size/mtime отличаются), переобрабатывается как новый — это позволяет detect когда user заменил файл с тем же именем.
- `--no-skip-existing`: ignore manifest при decision, всё равно процессим. Drive idempotency (по name+folder) и cached mp4 (по path+size) остаются — мы не дублируем работу впустую, просто не пропускаем по статусу.
- Resume через intermediate states: если effective.status == `"converted"` и есть валидный `mp4_path` (file exists, size>0) → пропускаем convert, идём в drive. Если `"in-drive"` с валидным `drive_id` → идём прямо в submit.
- Failed states (`convert-failed`, `drive-failed`, `upload-rejected`) НЕ блокируют retry: при следующем запуске пробуем снова с того же шага. Если повторно falить — следующая failed-строка просто appendится.

### Manifest schema

One line per stage transition (append-only):

```json
{
  "source_webm": "/Users/.../meetgeek-recording-2026-01-20T15-44-31-132Z.webm",
  "source_mtime": "2026-01-20T15:44:31Z",
  "source_size_bytes": 78423104,
  "mp4_path": "/Users/.../uploads-staging/2026-05-06/meetgeek-recording-2026-01-20T15-44-31-132Z.mp4",
  "mp4_size_bytes": 41203712,
  "drive_id": "1aBcDeFgH...",
  "drive_download_url": "https://drive.google.com/uc?export=download&id=1aBcDeFgH...",
  "title": "Meeting 2026-01-20 15:44 UTC",
  "language": "ru",
  "submitted_at": "2026-05-06T08:12:33Z",
  "upload_response_message": "The recording has been validated and submitted for analysis...",
  "status": "submitted"
}
```

Status enum: `convert-failed | converted | drive-failed | in-drive | upload-rejected | submitted`.

## 6. Error handling

| Слой | Симптом | Behavior |
|---|---|---|
| convert | ffmpeg not found | `ApiError("imageio-ffmpeg not installed; pip install --upgrade imageio-ffmpeg")`, exit 2 |
| convert | corrupted source (ffprobe nonzero) | manifest `status: convert-failed`, error в stderr, **continue batch** |
| convert | disk full | partial mp4 удалён, manifest fail, error message с required free |
| convert | mp4 size < 1KB | удалить, manifest fail |
| drive | OAuth expired | auto-refresh из drive_cli (уже работает) |
| drive | token missing | `ApiError("Drive auth missing — run /h2t-ops:drive list")`, exit 1, **abort batch** |
| drive | quota exceeded | manifest `drive-quota-exceeded`, **abort batch** |
| drive | upload interrupted | resumable retry x3 |
| drive | permission set fails | retry x1, иначе manifest fail, **continue** |
| upload | 400 invalid URL | manifest `upload-rejected`, error, **continue** |
| upload | 401 invalid key | `ApiError`, **abort batch** |
| upload | 429 | exp backoff (existing `_request`) |
| upload | 202 + webhook warning | **success** (status: submitted) |
| upload | 5xx | retries x3, иначе manifest fail, **continue** |

**Exit codes:**

- 0: все processed (или skipped) без ошибок
- 1: per-file errors (продолжили batch)
- 2: abort (auth, quota, missing dep)

## 7. Testing

Расширяем `tests/test_meetgeek_cli.py` (текущих 15 → 29).

- 4 convert tests (single-track, multi-track amix, cached skip, corrupted source)
- 3 drive_upload tests (idempotent existing, dated folder creation, permission set)
- 4 upload-orchestrator tests (chain glob, skip-existing, resume-after-partial, dry-run)
- 3 error-handling tests (per-file convert fail continues, 401 aborts, 202+warning is success)

Все mock-based: `subprocess.run` для ffmpeg/ffprobe, `googleapiclient.discovery` для Drive, `requests.request` для MeetGeek (как уже сделано в существующих тестах).

**Live smoke (manual checklist, не CI):**

1. Один реальный webm → `meetgeek convert` → mp4 играется в QuickTime/VLC
2. `meetgeek drive-upload` → Drive web UI показывает файл с share=anyone-with-link
3. `meetgeek upload --download-url <real Drive link>` → 202
4. ~10 мин → `meetgeek list --limit 5` → новый митинг

## 7.5 Live verification gate (pre-batch)

Перед массовой реализацией batch+resume — **первый smoke на одном реальном файле** обязателен. Цель: подтвердить assumption что Drive `https://drive.google.com/uc?export=download&id={id}` действительно работает как `download_url` для MeetGeek. Эта URL-схема — допущение из общего паттерна Drive sharing, а не из MeetGeek docs.

Steps (manual, до того как мы пишем `--from-file` orchestrator):

1. `meetgeek convert <one.webm>` → mp4 ОК (играется в QuickTime/VLC)
2. `meetgeek drive-upload <mp4>` → JSON с `download_url`
3. Открыть `download_url` в incognito браузере (без auth) → файл должен начать качаться
4. `meetgeek upload --download-url <url> --title test` → 202 Accepted
5. ~10 мин → `meetgeek list --limit 5` → новый митинг появился, `transcript` содержит реальный текст

Если пункт 3 или 5 fails — Drive `uc?export=download&id=` insufficient. Альтернативы (для plan):

- Использовать API endpoint `https://www.googleapis.com/drive/v3/files/{id}?alt=media` (требует Bearer token, НЕ работает для MeetGeek)
- Создавать `permissions.create({type:"anyone", role:"reader"})` + `webContentLink` из metadata Drive API
- Promote file в Shared Drive с broader visibility

В spec фиксируем: live gate — **первая стадия implementation**, до того как пишем `cmd_upload --from-file` orchestrator.

## 8. Out of scope (this milestone)

- Webhook integration для статуса processing — ждём отдельный issue (можно использовать `webhook-server` из 1.0.7, но MeetGeek webhook config — отдельный flow)
- Per-file `--title` override в batch
- Auto-cleanup Drive folder по retention policy (`#X` follow-up)
- Source форматов кроме webm/mp4 (теоретически работает любой ffmpeg-decodable, но не проверено)
- Поддержка не-Drive storage (S3, R2) — гипотетически добавится в follow-up

## 9. Versioning

`h2t-ops` 1.0.7 → **1.1.0** (minor bump — добавляем feature, не fix).

Rationale: по convention из user CLAUDE.md, minor только после live confirmation. Bump делаем при коммите финальной фичи **после** ручной smoke-проверки на user-machine с реальным webm.

## 10. References

- Issue: https://github.com/lichtpfad/h2t-skills/issues/93
- Existing skill: `plugins/h2t-ops/skills/meetgeek/`
- Existing pattern: `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` (Drive auth)
- MeetGeek API: https://docs.meetgeek.ai/api/getting-started/introduction
- imageio-ffmpeg: https://github.com/imageio/imageio-ffmpeg
- Live API findings (2026-05-06): `/v1/upload` — POST application/json, requires `download_url`
