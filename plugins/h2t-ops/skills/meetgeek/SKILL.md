---
name: meetgeek
description: "MeetGeek API: pull meetings, transcripts, summaries, highlights, insights, recordings. Bypasses broken Drive auto-sync (re-transcription bug, POS#80). Watch mode + webhook server. Triggers: 'meetgeek', 'sync transcripts', 'pull meetings', 'митинги', 'h2t-ops:meetgeek'."
compatibility: "Requires MEETGEEK_API_KEY in ~/.dor/secrets.env or env var. Region-specific (EU/US) — key prefix indicates region."
metadata:
  author: lichtpfad
  version: 1.1.0
---

# Инструкции

## POS Boundary

For POS, meeting-memory, and daily-loop workflows, follow the shared boundary
reference: `../../references/pos-operational-boundary.md`. This skill may read
MeetGeek data through connector tooling, but must not write POS journal rows,
mutate `~/.dor/pos.db`, or modify vault/lake directly except through approved
`pos_ingest` or coordinator workflow. Emit structured proposed captures until
POS journal commands exist.

## Переменные

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-ops:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/meetgeek_cli.py"
```

## Команды

### Auth-check

```bash
$CLI auth-check
```

Validate `MEETGEEK_API_KEY` against `/v1/meetings?limit=1`. Exit 0 = ok.

### List meetings

```bash
$CLI list [--limit N] [--cursor C] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]
# Examples:
$CLI list --limit 10
$CLI list --from-date 2026-04-01 --to-date 2026-05-01
```

Output: JSON array. Pagination via `next_cursor` field.

### Single meeting

```bash
$CLI get <meeting-id>                                       # metadata
$CLI transcript <meeting-id> [--format md|json] [-o PATH]   # default: md
$CLI summary <meeting-id> [--format md|json] [-o PATH]
$CLI highlights <meeting-id> [--format md|json] [-o PATH]
$CLI insights <meeting-id> [--format md|json] [-o PATH]
$CLI download <meeting-id> [-o PATH]                        # recording
```

`md` format: frontmatter (POS data-architecture v3.3 compatible) + body.
`json` format: raw API response, full fidelity.

If `-o` omitted: stdout. Otherwise writes to PATH.

### Upload local recordings

Three composable commands for `webm → mp4 → Drive → MeetGeek` flow.

```bash
# Convert (default: webm → mp4 H.264/AAC; multi-track audio → amix)
$CLI convert <in.webm> [-o out.mp4] [--audio-only] [--mix-mode amix|first|keep] [--probe]

# Upload to Drive (default folder: MeetGeek Uploads/{YYYY-MM-DD}/, share=anyone)
$CLI drive-upload <file> [--folder "MeetGeek Uploads/2026-05-06"] [--no-make-public]

# Submit one URL directly (presumes you already have a public URL)
$CLI upload --download-url URL [--title T] [--language ru|en|auto]

# Batch — convert + drive-upload + submit for many files
$CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' \
            [--audio-only] [--mix-mode amix|first|keep] \
            [--language ru] [--no-skip-existing] [--dry-run]
```

State for resume lives in `~/.dor/lake/meetgeek/uploads-staging/`:
- `{YYYY-MM-DD}/*.mp4` — converted cache (skip re-encode on retry)
- `manifest.jsonl` — append-only state log; effective state per source = last line.

Recipes:
- One file end-to-end: `$CLI upload --from-file ~/Downloads/meetgeek-recording-2026-01-20T15-44-31-132Z.webm --language ru`
- Backfill 16 files (default skip-existing keeps it idempotent): `$CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' --language ru`
- Force re-process: append `--no-skip-existing` (Drive idempotent search and cached mp4 still avoid duplicate work).

Dependencies (auto-installed once):
```bash
~/.h2t/venv/Scripts/python.exe -m pip install imageio-ffmpeg   # Windows
~/.h2t/venv/bin/python -m pip install imageio-ffmpeg           # macOS
```

### Bulk sync (главная команда)

```bash
# Backfill: вся история транскриптов
$CLI sync --to ~/.dor/lake/meetgeek/historical/ \
          --include transcripts,summaries,highlights

# Incremental: только новые с последнего sync
$CLI sync --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/ \
          --since-cursor --include transcripts

# Date range
$CLI sync --to /tmp/test --since 2026-04-01 --limit 5

# Включить recordings (mp4) — POST /download → media.meetgeek.ai stream
$CLI sync --to ~/.dor/lake/meetgeek/historical/ \
          --include transcripts,recordings

# Watch mode: цикл sync каждые N секунд (мин 30), Ctrl-C для выхода
$CLI sync --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/ \
          --since-cursor --include transcripts --watch 300
```

#### Layout output

```
{LAKE_PATH}/
  manifest.jsonl            # one line per meeting (meta)
  transcripts/{id}.md       # human-readable
  transcripts/{id}.json     # raw API
  summaries/{id}.{md,json}
  highlights/{id}.{md,json}
  insights/{id}.{md,json}
```

#### Cursor

`~/.dor/lake/_cursors/meetgeek.json` (configurable via `--cursor-file`):

```json
{
  "source": "meetgeek",
  "last_seen_ts": "2026-05-02T14:00:40Z",
  "last_seen_id": "...",
  "last_run_at": "...",
  "items_ingested": 111,
  "version": 1
}
```

`--since-cursor` reads `last_seen_ts` and pulls only newer.

### Helpers

```bash
$CLI teams                  # list user's teams
```

### Webhook server

```bash
# Receive MeetGeek webhook events to disk (POST → JSON file per event)
$CLI webhook-server --port 8765 --bind 127.0.0.1 \
                    --out ~/.dor/lake/meetgeek/webhooks/ \
                    --secret <shared-secret>
```

- POST с любым path принимается; payload + headers + path сохраняется в `{out}/{uuid}.json`
- Если `--secret` задан, требуется header `X-Webhook-Secret`; иначе 401
- Без `--secret` любой POST пишется (для локальной разработки)
- GET / → health probe

## Use cases

1. **Daily pull** новых митингов — `$CLI sync --since-cursor --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/`
2. **Backfill всей истории** (POS#80) — `$CLI sync --to ~/.dor/lake/meetgeek/historical/ --include transcripts,summaries,highlights`
3. **Get one transcript** для distillation — `$CLI transcript <id> -o ~/.dor/context/meetings/<title>.md`
4. **Search by date range** — `$CLI list --from-date 2026-04-01 --to-date 2026-05-01`

## Переменные окружения

- `MEETGEEK_API_KEY` (required) — Bearer key. Registry: `~/.h2t/config/secrets/meetgeek.md`
- `MEETGEEK_BASE_URL` (default: `https://api.meetgeek.ai`) — для regional EU/US endpoints
- `MEETGEEK_TIMEOUT` (default: 30s)
- `MEETGEEK_MAX_PAGES` (default: 1000) — safety cap для list pagination

Loaded from `~/.dor/secrets.env` если присутствует (`python-dotenv`), иначе из shell env.

## Обработка ошибок

- **401** → key invalid. Check `~/.h2t/config/secrets/meetgeek.md`, regional prefix (`eu-`/`us-`).
- **404** → meeting id не найден. List sначала: `$CLI list --limit 5`.
- **429** → rate limit. CLI делает exponential backoff (max 3 retry).
- **Network timeout** → 30s default, 1 retry. Override `MEETGEEK_TIMEOUT`.
- **Sync partial fail** → cursor сохраняется как `partial(N)`, manifest содержит только успешные. Re-run пропустит уже синхронизированные через cursor.

## Why not Drive

MeetGeek auto-sync в Google Drive перетранскрибирует с auto-detect language → ломает RU↔EN code-switching. Originals в API correct. См. POS#80.
