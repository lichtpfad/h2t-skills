---
name: meetgeek
description: "MeetGeek API: pull meetings, transcripts, summaries, highlights, insights. Bypasses broken Drive auto-sync (re-transcription bug, POS#80). Triggers: 'meetgeek', 'sync transcripts', 'pull meetings', 'митинги', 'h2t-ops:meetgeek'."
compatibility: "Requires MEETGEEK_API_KEY in ~/.dor/secrets.env or env var. Region-specific (EU/US) — key prefix indicates region."
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
