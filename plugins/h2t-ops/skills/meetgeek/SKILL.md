---
name: meetgeek
description: "MeetGeek API: pull meetings, transcripts, summaries, highlights, insights, recordings. Bypasses broken Drive auto-sync (re-transcription bug, POS#80). Watch mode + webhook server. Triggers: 'meetgeek', 'sync transcripts', 'pull meetings', 'митинги', 'h2t-ops:meetgeek'."
compatibility: "Requires MEETGEEK_API_KEY in ~/.dor/secrets.env or env var. Region-specific (EU/US) — key prefix indicates region."
metadata:
  author: lichtpfad
  version: 1.2.0
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
# New connector CLI (migrated verbs)
H2T_OPS="h2t-ops"

# Legacy script (recovery workflow — tracked in #149)
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-ops:setup" && exit 1
LEGACY_CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/meetgeek_cli.py"
```

## Команды

### Migrated verbs (delegate to h2t-ops meetgeek)

#### Auth-check

```bash
$H2T_OPS meetgeek auth-check
```

Validate `MEETGEEK_API_KEY`. Exit 0 = ok.

#### Teams

```bash
$H2T_OPS meetgeek teams [--json]
```

#### List meetings

```bash
$H2T_OPS meetgeek list [--limit N] [--cursor C] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD] [--json]
```

#### Single meeting

```bash
$H2T_OPS meetgeek get <meeting-id> [--json]
$H2T_OPS meetgeek transcript <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek summary    <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek highlights <meeting-id> [--format md|json] [--json]
$H2T_OPS meetgeek insights   <meeting-id> [--format md|json] [--json]
```

#### Download recording URL

```bash
$H2T_OPS meetgeek download-url <meeting-id> [--json]
```

Returns `{meeting_id, download_url}` — signed URL only, no file download.

#### Submit URL for transcription

```bash
$H2T_OPS meetgeek submit-url <URL> [--title T] [--language-code CODE] [--template NAME] [--json]
```

`POST /v1/upload`. Submit a public recording URL directly to MeetGeek API.

**Compatibility alias:** `$LEGACY_CLI upload --download-url <URL>` — route to `$H2T_OPS meetgeek submit-url <URL>` instead. The legacy `_post_upload` path is superseded by this connector verb.

### Legacy: upload local recordings (tracked in #149)

**Do not delete these commands** — they are production functionality preserved until #149 extracts
and refactors the recovery workflow.

```bash
# Convert (webm → mp4)
$LEGACY_CLI convert <in.webm> [-o out.mp4] [--audio-only] [--mix-mode amix|first|keep] [--probe]

# Upload to Drive (creates MeetGeek Uploads/{YYYY-MM-DD}/, shares publicly)
$LEGACY_CLI drive-upload <file> [--folder "MeetGeek Uploads/2026-05-06"] [--no-make-public]

# Full pipeline: convert + drive-upload + submit (manifest/resume in ~/.dor/lake/meetgeek/)
$LEGACY_CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' \
            [--audio-only] [--mix-mode amix|first|keep] \
            [--language ru] [--no-skip-existing] [--dry-run]
```

State for resume: `~/.dor/lake/meetgeek/uploads-staging/manifest.jsonl`

These commands depend on `google-api-python-client` and `imageio-ffmpeg`.
#149 will extract this workflow and replace the embedded Drive logic with the Drive connector (#133).

### Legacy: sync and webhook-server

`sync` and `webhook-server` are **not migrated** to the h2t-ops connector.

- `sync` writes to `~/.dor/lake/meetgeek/`, cursor, manifest — coordinator/lake layer, not connector.
- `webhook-server` is dev-only; production webhook integration belongs to POS/VPS (stable public endpoint, signature verification, `pos_ingest` routing).

```bash
# Legacy sync (still works via legacy script)
$LEGACY_CLI sync --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/ --since-cursor --include transcripts

# Legacy webhook server (dev only)
$LEGACY_CLI webhook-server --port 8765 --bind 127.0.0.1 --out ~/.dor/lake/meetgeek/webhooks/
```

## Use cases

1. **Daily pull** новых митингов — `$H2T_OPS meetgeek list --since-cursor` (или `$LEGACY_CLI sync --since-cursor --to ~/.dor/lake/meetgeek/$(date +%Y-%m-%d)/`)
2. **Backfill всей истории** (POS#80) — `$LEGACY_CLI sync --to ~/.dor/lake/meetgeek/historical/ --include transcripts,summaries,highlights`
3. **Get one transcript** для distillation — `$H2T_OPS meetgeek transcript <id>`
4. **Search by date range** — `$H2T_OPS meetgeek list --from-date 2026-04-01 --to-date 2026-05-01`

## Переменные окружения

- `MEETGEEK_API_KEY` (required) — Bearer key. Registry: `~/.h2t/config/secrets/meetgeek.md`
- `MEETGEEK_BASE_URL` (default: `https://api.meetgeek.ai`) — для regional EU/US endpoints
- `MEETGEEK_TIMEOUT` (default: 30s)
- `MEETGEEK_MAX_PAGES` (default: 1000) — safety cap для list pagination

Loaded from `~/.dor/secrets.env` если присутствует (`python-dotenv`), иначе из shell env.

## Обработка ошибок

- **401** → key invalid. Check `~/.h2t/config/secrets/meetgeek.md`, regional prefix (`eu-`/`us-`).
- **404** → meeting id не найден. List сначала: `$H2T_OPS meetgeek list --limit 5`.
- **429** → rate limit. CLI делает exponential backoff (max 3 retry).
- **Network timeout** → 30s default, 1 retry. Override `MEETGEEK_TIMEOUT`.
- **Sync partial fail** → cursor сохраняется как `partial(N)`, manifest содержит только успешные. Re-run пропустит уже синхронизированные через cursor.

## Why not Drive

MeetGeek auto-sync в Google Drive перетранскрибирует с auto-detect language → ломает RU↔EN code-switching. Originals в API correct. См. POS#80.
