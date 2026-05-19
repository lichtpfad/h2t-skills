---
name: research
description: "Semantic web research via Exa API. Modes: fast / generic / news / academic / competitor / people / deep. Transparent telemetry, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires $EXA_API_KEY env var. Get key at https://dashboard.exa.ai/api-keys. Requires ~/.h2t/venv (run /h2t-core:setup if missing). Optional: pip install trafilatura inside ~/.h2t/venv for richer article extraction (script falls back to stdlib inline parser if absent)."
metadata:
  author: lichtpfad
  version: 0.1.2
---

# h2t-ops:research

Semantic research via Exa HTTP API. Transparent (all tool calls visible in main conversation), fail-loud (no silent fallbacks), debug-friendly (telemetry block in every report).

## POS Boundary

For POS, KB, and daily-loop workflows, follow the shared boundary reference:
`../../references/pos-operational-boundary.md`. This skill may gather external
research evidence, but must not write POS journal rows, mutate `~/.dor/pos.db`,
or modify vault/lake directly except through approved `pos_ingest` or
coordinator workflow. Emit structured proposed captures until POS journal
commands exist.

## Architecture

```
User query
    ↓
Step 0: Preflight (env + connectivity)
    ↓
Step 1: Parse request → mode, depth, filters
Step 1b: Check cache → ~/.h2t/research/
    ↓
Step 2: Load systemprompts/{mode}.md
    ↓
Step 3: Call exa_search.py (search / crawl, parallel where possible)
    ↓
Step 4: Fail-loud checks (exit code ≠ 0 → STATUS:DEGRADED)
    ↓
Step 5: Synthesize findings (grounded — URL + quote + confidence)
    ↓
Step 6: Persist (script auto-writes .partial.md + .sources.json)
    ↓
Step 7: Present Output (agent finalises .md per REPORT-SPEC.md)
```

## Файлы скилла

| Файл | Назначение |
|---|---|
| `SKILL.md` | Этот файл — workflow, runtime contract, antipatterns |
| `REPORT-SPEC.md` | Точный формат report markdown |
| `reference.md` | Exa API reference, mode mapping, limitations (lazy-loaded) |
| `examples.md` | CLI invocation examples + output samples |
| `systemprompts/{mode}.md` | 7 готовых systemPrompt templates |
| `scripts/exa_search.py` | Python CLI wrapper (stdlib urllib, no pip) |
| `tests/test_exa_search.py` | pytest suite |

## Выходные файлы

| Файл | Когда | Writer |
|---|---|---|
| `~/.h2t/research/{project}-{slug}-{date}.partial.md` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.sources.json` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.md` | После synthesis | **agent** |
| `~/.h2t/research/.pending_telemetry.jsonl` | When evals unreachable | script |

## Runtime variables (set once at Step 0)

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

# CLAUDE_PLUGIN_ROOT is empty in bash agent context — discover via glob
_EXA_PY=$(ls ~/.claude/plugins/cache/lichtpfad/h2t-ops/*/skills/research/scripts/exa_search.py 2>/dev/null | sort -V | tail -1)
_FETCH_PY=$(ls ~/.claude/plugins/cache/lichtpfad/h2t-ops/*/skills/research/scripts/fetch_url.py 2>/dev/null | sort -V | tail -1)
[ -z "$_EXA_PY" ] && echo "ERROR:SETUP exa_search.py not found. Run: /plugin marketplace update && /reload-plugins" && exit 1
[ -z "$_FETCH_PY" ] && echo "ERROR:SETUP fetch_url.py not found. Run: /plugin marketplace update && /reload-plugins" && exit 1
EXA_CLI="$H2T_PYTHON $_EXA_PY"
FETCH_CLI="$H2T_PYTHON $_FETCH_PY"
```

## Tool Restriction (critical)

**ONLY use `$EXA_CLI`.** Do NOT use `WebSearch`, `WebFetch`, or direct `curl` as substitutes. If `$EXA_CLI` fails, return `STATUS: DEGRADED` with exact `EXA_ERROR:*` — never silently substitute.

## Provider Status Envelope

Каждый `$EXA_CLI search` пишет envelope в `.sources.json` (поле `meta.envelope`).
При флаге `--envelope` envelope печатается в stdout вместо markdown summary.

| `envelope.status` | Что значит | Действие агента |
|---|---|---|
| `OK` | Exa вернул ≥1 результат после всех retries | Continue to Step 5 (synthesis) |
| `DEGRADED` | Exa отработал, но 0 results после retries (`exit 0`) | Report `STATUS: DEGRADED + reason=exa_empty_results`. Агент МОЖЕТ: (a) попробовать другой mode/query вариацию явным новым CLI вызовом, (b) использовать `WebSearch` с обязательной пометкой `STATUS: DEGRADED + fallback=websearch` в репорте, (c) остановиться. Silent fallback запрещён. |
| `FAILED` | HTTP 4xx/5xx/network/malformed после retries | Report `STATUS: FAILED + EXA_ERROR:*` (точное сообщение из stderr). STOP. |

`exit 0` НЕ означает `status == OK`. Всегда читать envelope (либо из stdout при `--envelope`, либо из `.sources.json:meta.envelope`).

## Fetching Specific URLs (`fetch_url.py`)

`exa_search.py` находит URL'ы; `fetch_url.py` доставляет их содержимое через provider ladder (`direct → jina → stubs`).

Когда использовать:
- ✅ Известный URL, нужен полный текст статьи (а не только Exa highlight).
- ✅ Plain WebFetch вернул shell / 403 / пустоту.
- ✅ JS-rendered страницы (Jina Reader сам рендерит JS на их side).

Когда НЕ использовать:
- ❌ Поиск по теме → используй `$EXA_CLI search`.
- ❌ Bulk crawl сайта → используй адаптеры (`alltd.py`, `iihq.py`) после их реализации.
- ❌ Auth/paid контент → скрипт вернёт `FAILED + content_gate`; не пытайся обойти через `WebFetch`.

CLI:

$FETCH_CLI fetch --url "https://..." [--provider auto] [--json] [--keep-raw] [--project NAME]

Envelope status — тот же контракт, что у `exa_search.py`:

| `envelope.status` | exit | Действие агента |
|---|---|---|
| OK | 0 | Continue: synthesize from `body_markdown`. |
| DEGRADED | 0 | Report `STATUS: DEGRADED + reason=...`. Можно: (a) попробовать `--provider jina` явно, (b) пометить источник `failed-harvest` и идти дальше. Никакого silent fallback. |
| FAILED + `content_gate=login_required\|paid` | 5 | STOP. Не fetch'и через WebFetch. Источник legitimately gated. |
| FAILED + http | 2 | STOP. Report exact `FETCH_ERROR:HTTP`. |
| FAILED + network | 3 | STOP. Report exact `FETCH_ERROR:NETWORK`. |

Privacy note: Jina Reader — third-party URL relay; URL и часть содержимого видны Jina'у. Для public web research это допустимо; для anything sensitive — `--provider direct` или disable Jina через `~/.h2t/config/research/fetch_providers.json` (`providers.jina.enabled: false`).

## Workflow

### Step 0: Preflight

```bash
$EXA_CLI preflight
```

Failures:
- `ERROR:SETUP` in stderr (script not found) → tell user to run `/plugin marketplace update && /reload-plugins`, STOP. **Do NOT fall back to WebSearch.**
- Exit 4 + `EXA_ERROR:ENV EXA_API_KEY missing` → tell user to export key, STOP
- Exit 4 + `EXA_ERROR:NETWORK` → api.exa.ai unreachable, STOP

No silent fallback. No WebSearch substitution.

### Step 1: Parse Research Request

Accept natural language OR structured input. Extract:

| Field | Required | Default | Notes |
|---|---|---|---|
| `topic` | yes | — | passed as `--query` |
| `mode` | no | `generic` | one of fast / generic / news / academic / competitor / people / deep |
| `depth` | no | `standard` | shallow (1 call) / standard (search + crawl top-3) / deep (+ deep_reasoning synthesis) |
| `country` | no | — | ISO code, e.g. `CH`, `US` |
| `start_date` / `end_date` | no | — | ISO date (content date filter) |
| `include_domains` / `exclude_domains` | no | — | CSV list; see filter matrix in reference.md |
| `num_results` | no | mode default | override |
| `project` | no | `default` | for output filename prefix |

**Preserve query language.** Exa neural search is multilingual. If user's request is in Russian (or any non-English language), pass `--query` **verbatim** in that language — do NOT translate to English. Translating destroys relevance ranking and loses localized sources (verified 2026-04-19: English-translated query missed 4 of top-10 results including direct marketing/agency playbooks).

Ambiguous? Ask ONE clarifying question. Example: user says "research Rejuve.bio" → ask: "Company intel, press coverage, or team research? (competitor / news / people)"

### Step 1b: Check Cached Research

```bash
ls ~/.h2t/research/*{slug}* 2>/dev/null
```

If file < 7 days old exists — show path, ask: *"Use cached or re-search?"*

### Step 2: Load systemPrompt Template

Agent does NOT read `systemprompts/{mode}.md` directly — the script does. Agent just selects `--mode`.

### Step 3: Execute Search (parallel where independent)

```bash
# depth=shallow: one call
$EXA_CLI search --query "..." --mode generic --num-results 5 --project X

# depth=standard/deep: 2–3 query variations in parallel + dedupe
$EXA_CLI search \
  --query "Rejuve.bio Switzerland press 2026" \
  --additional-queries "Swiss longevity startups,DAO biotech 2026" \
  --mode news --start-date 2025-10-01 \
  --num-results 10 --project rejuve

# depth=deep phase 2: parallel crawl top-3 URLs in a single message
$EXA_CLI crawl --url "URL_1" --project X &
$EXA_CLI crawl --url "URL_2" --project X &
$EXA_CLI crawl --url "URL_3" --project X &
wait
```

**Batch independent calls in a single message.** Never sequentialize parallel searches.

### Step 4: Fail-Loud Checks

On any non-zero exit from `$EXA_CLI`:

- Read first stderr line (structured `EXA_ERROR:*`)
- Return `STATUS: DEGRADED` + exact cause + what was attempted
- **Forbidden phrasing:** `"permission blocked"`, `"tool failed"` without specifics
- **Required phrasing:** exact `EXA_ERROR:*` message from stderr

| Exit | Meaning | Action |
|---|---|---|
| envelope.status | OK / DEGRADED / FAILED | См. секцию Provider Status Envelope выше |
| 0 | Success | Continue |
| 1 | Args error | Stop, fix invocation |
| 2 | HTTP error (4xx/5xx) | STATUS:DEGRADED, report exact code |
| 3 | Network timeout | STATUS:DEGRADED, suggest retry |
| 4 | Preflight (env/connectivity) | STOP, fix env |

### Step 5: Synthesize Findings

Read script's markdown stdout (title + URL + highlight per result).

**Grounding rule (ALL depths, no exceptions):** every Key Finding MUST have:
- Verbatim quote from highlight (double-quoted string)
- URL to source
- Confidence label: high / medium / low + one-sentence reason

No grounding → not a finding. Move to Limitations or flag as `[research incomplete]`.

### Step 6: Persist (script auto-done)

Script wrote `.partial.md` + `.sources.json`. Agent now reads `.partial.md` and builds final `.md` per `REPORT-SPEC.md`.

### Step 7: Present Output

Write final report to `~/.h2t/research/{project}-{slug}-{date}.md` following REPORT-SPEC.md. Delete `.partial.md` after writing. In main conversation, show:

- Path to saved file
- Summary (top 3 findings as bullets)
- Status label (✅ completed / ⚠ partial / ❌ degraded)
- Telemetry status literal

## Error Handling

| Signal | Reaction |
|---|---|
| User query too vague (e.g. "research stuff") | Ask ONE clarifying question with mode examples |
| User asks "how many results?" Ambiguous | Ask: "10 (default), 5 (quick), or 50 (bulk)?" |
| Exa returns 0 results | Report honestly. Suggest query variations or broader category. Do NOT synthesize from general knowledge. |
| User asks for LinkedIn lead-gen | Route to `/search-leads` (BayramAnnakov plugin, Anysite engine). This skill does Exa only. |
| `.partial.md` missing when writing final | Script failed silently (bug). Re-run search; if still failing, check stderr. |

## Antipatterns

- **Synthesize findings without URL + quote** — violates grounding rule. #69 root cause.
- **Claim `depth=deep` when only `search` was called** — status lying. Integrity check row in telemetry catches this.
- **Hide tool failures** — any non-zero exit code must propagate to Meta.Status.
- **"permission blocked" as diagnosis** — forbidden without evidence of CC permission denial. Use exact `EXA_ERROR:*`.
- **Silent fallback to WebSearch** — script never does this; agent must not either.
- **Parse HTML inline in agent** — script's job. Agent reads cleaned markdown only.
- **Forget to delete `.partial.md`** — leaves stale files. Always `rm .partial.md` after writing final `.md`.
- **Translate non-English query to English** — destroys Exa multilingual ranking. Russian query → keep Russian. Mixed language → keep as-is. Only translate on explicit user request.
- **Treat `exit 0` as success without reading envelope** — `status == DEGRADED` пишется при exit 0 на empty results. Всегда читать `envelope.status`.
- **Silent retry того же запроса** — retry делает скрипт автоматически. Если агент видит `DEGRADED`, он либо явно меняет запрос (новый CLI вызов с другим `--mode` / query вариацией), либо переключается на fallback с пометкой. Никаких "молчаливых" повторов.
- **Bypass auth/paywall via WebFetch fallback** — `content_gate=login_required\|paid` означает legitimately gated. Substitute via WebFetch — нарушение интегритета.
- **Synthesize article from short_body / js_shell** — `status=DEGRADED` означает body не пригоден для wiki ingest. Помечай `failed-harvest`.

## When to use this skill

✅ "Find companies in longevity space"
✅ "Recent news about AI chip export controls"
✅ "Academic papers on LLM RAG evaluation"
✅ "Who is the CEO of Insilico Medicine?"

❌ "Generate leads for my outbound campaign" → use `/search-leads`
❌ "Monitor Twitter for brand mentions" → use `/search-leads` (Anysite has Twitter)
❌ "Scrape this internal URL" → use WebFetch / Playwright (auth-gated)

## Research Request

$ARGUMENTS
