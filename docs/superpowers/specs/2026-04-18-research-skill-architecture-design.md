---
title: "Research Skill Architecture — Exa + Anysite Integration"
status: "draft"
owner: "lichtpfad"
date: "2026-04-18"
milestone: "M2"
related_issue: "lichtpfad/h2t-skills#69"
---

# Research Skill Architecture — Exa + Anysite Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Заменить монолитный `h2t:research-agent` на два независимых skill'а с чёткими engine boundaries, transparent telemetry и fail-loud protocol. Устранить silent-fallback problem, убрать `"permission blocked"` гадания, добавить debug-friendly отчёты.

**Scope:** Новый skill `plugins/h2t-ops/skills/research/` (Exa), интеграция BayramAnnakov/lead-search-plugin (Anysite), deprecation старого research-agent, документированный telemetry-контракт с h2t-evals.

**Non-goals:** Websets, Monitors, streaming SSE, cross-engine orchestration layer (все три — v0.2+).

---

## 1. Context & Root Cause

Четыре research-файла от недавних сессий (`A1_rejuve_products.md`, `B1_competitors_ch.md`, `E1_channels_formats_2026.md`, `R3_R4_benchmarks_verified.md`) содержали WebSearch-only summaries, заявленные как authoritative. Sub-агенты (`h2t:research-agent`, `general-purpose`) рапортовали `"permission blocked"` — но реальная причина была иной: `mcp__exa__*` tools deferred и не инжектировались в sub-agent toolset. Агенты делали silent fallback на WebSearch и misdiagnosed tool unavailability как permission denial.

**Discovered facts:**

- Exa MCP настроен в `~/.claude.json` на user scope с 8 tools; `claude mcp list` в сессии их не показывает — tool injection issue.
- Exa HTTP API via curl работает: probe $0.007 за 5 результатов (auto + highlights).
- Anysite MCP: 65+ tools (LinkedIn 35, Instagram, Reddit, Twitter, YouTube, SEC, YC, DuckDuckGo), $30/mo unlimited plan.
- Firecrawl отключён (ограниченный free tier).

**Root causes:**

1. **Silent fallback** — sub-агенты не эскалировали tool failures caller'у.
2. **Diagnosis-by-guess** — `"permission blocked"` was a hypothesis reported as fact.
3. **No preflight** — env vars и connectivity не проверялись.
4. **No direct-source requirement** — WebSearch AI-summaries писались как фактические findings.
5. **Deferred tools not injected** — sub-agent toolset не содержал `mcp__exa__*`, ToolSearch был недоступен sub-agent'у.

---

## 2. Architecture Overview

Три независимые единицы, caller явно выбирает engine именем skill'а. **Engine-split на уровне skill names**, не через `mode` parameter внутри одного skill.

| Компонент | Роль | Engine | Status |
|---|---|---|---|
| `h2t-ops:research` | Exa-based semantic research (web, news, academic, company, people) | Exa HTTP API via `exa_search.py` | **NEW — build from scratch** |
| `BayramAnnakov/lead-search` | LinkedIn/Crunchbase/YC/SEC lead generation с ICP-ranking | Anysite MCP | **REUSE AS-IS** (автор разрешил) |
| `h2t:research-agent` | Старый agent — deprecated | — | **DEPRECATE** (stub → redirect) |

**No orchestration layer.** Cross-engine задачи (например "research компанию X: web + LinkedIn") — caller делает два явных вызова и синтезирует сам. Это сознательный trade-off: простота > автоматизация при недостатке статистики по cost/quality.

### 2.1 Transport Decisions

- **Exa:** HTTP API через Python CLI wrapper (`exa_search.py`), stdlib `urllib`, zero pip deps. **НЕ MCP** (tool injection unreliable для sub-agents) и **НЕ `exa-py` package** (избегаем pip зависимости для MVP; добавляем в v0.2 если понадобится streaming/retry).
- **Anysite:** MCP на user scope (`claude mcp add --transport http anysite https://mcp.anysite.io/mcp?api_key=...`). BayramAnnakov skill его использует напрямую через ToolSearch loading.

### 2.2 Скiль vs Агент — выбор skill

По Anthropic docs:

> *Subagents offer context isolation. Skills load inline with main conversation context.*

Research как skill выбран по трём причинам:
1. **Прозрачность** — caller видит каждый tool call, silent fallback physically невозможен.
2. **Deferred tools resolved inline** — главный агент имеет ToolSearch, грузит MCP по требованию.
3. **Быстрая итерация** — SKILL.md правится без rebuild/reload.

Контекст-гигиена решается через **persist-to-file** pattern: raw JSON и детали сохраняются на диск, в conversation возвращается только summary + path.

### 2.3 Deprecation

Старый `plugins/h2t/agents/research-agent.md` заменяется stub'ом:

```markdown
---
name: research-agent
description: DEPRECATED. Use /research (Exa) or /search-leads (Anysite).
---
This agent is deprecated. For new tasks invoke:
- `/research` — semantic web search via Exa
- `/search-leads` — LinkedIn/Crunchbase/YC lead-gen via Anysite
```

`~/.claude/CLAUDE.md` получает правило: *research → /research или /search-leads, never general-purpose agent*.

---

## 3. File Layout

```
plugins/h2t-ops/skills/research/
├── SKILL.md                     # overview, architecture diagram, 7-step workflow (< 500 lines)
├── REPORT-SPEC.md               # exact report template + integrity rules (аналог DASHBOARD-SPEC.md)
├── reference.md                 # Exa API full parameter reference (lazy-loaded by agent)
├── examples.md                  # sample invocations + sample outputs
├── systemprompts/
│   ├── generic.md
│   ├── news.md
│   ├── academic.md
│   ├── competitor.md
│   ├── people.md
│   └── deep.md
├── scripts/
│   └── exa_search.py            # Python CLI wrapper (stdlib urllib, ~150 lines)
└── tests/
    └── test_exa_search.py       # pytest unit tests
```

Структура следует официальному Anthropic паттерну (code.claude.com/docs/en/skills):

> *Keep SKILL.md under 500 lines. Move detailed reference material to separate files. Scripts don't load as skill content; Claude executes them and sees the output.*

---

## 4. Workflow (7 Steps in SKILL.md)

### Step 0: Preflight

- Проверить `$EXA_API_KEY` (env var). Missing → `STATUS: BLOCKED`, показать инструкцию как установить.
- Проверить `~/.h2t/venv/Scripts/python` (Windows) или `~/.h2t/venv/bin/python` (Unix) существует.
- Запустить `exa_search.py preflight` — probe connectivity к `api.exa.ai`.
- **Никаких silent fallback.** Failed preflight = stop с точной причиной.

### Step 1: Parse Research Request

Input format (natural language ИЛИ structured):

| Field | Type | Description |
|---|---|---|
| `topic` | string | research subject (required) |
| `mode` | enum | `generic` / `news` / `academic` / `competitor` / `people` / `deep` |
| `depth` | enum | `shallow` / `standard` / `deep` |
| `budget` | enum | `cheap` / `standard` / `premium` — soft hint for type selection |
| `urls` | list | optional specific URLs to crawl |
| `country` | string | ISO code, e.g. `CH`, `US` |
| `start_date` / `end_date` | ISO date | content date filter |
| `include_domains` / `exclude_domains` | list | domain filters |

### Step 1b: Check Cached Research

```bash
ls ~/.h2t/research/*{slug}* 2>/dev/null
```

Если существует файл < 7 дней — показать путь, спросить: *"Use cached or re-search?"*. Экономит Exa credits.

### Step 2: Load systemPrompt Template

Агент читает `systemprompts/{mode}.md`. Файл содержит YAML frontmatter (`exa_type`, `exa_category`, `output_schema`) + body (systemPrompt текст).

Если нужен ad-hoc systemPrompt (не покрытый готовыми modes) — caller копирует ближайший шаблон и правит. Отдельный `mode=custom` не вводим в MVP (YAGNI).

### Step 3: Execute Search (parallel где можно)

```bash
# depth=shallow: один вызов
python scripts/exa_search.py search --query "..." --mode competitor --num-results 5

# depth=deep: parallel discovery + crawl top-3 в одном message
python scripts/exa_search.py search --query "..." --mode competitor --num-results 10

# Parent агент читает JSON output, выбирает top-3 URLs, делает parallel crawl:
python scripts/exa_search.py crawl --url "URL_1" &
python scripts/exa_search.py crawl --url "URL_2" &
python scripts/exa_search.py crawl --url "URL_3" &
wait
```

**В SKILL.md явно:** *"Batch independent calls in single message. Never sequentialize parallel searches."* (Bayram pattern.)

### Step 4: Fail-Loud Checks

При любом ненулевом exit-code из `exa_search.py`:

- Читать stderr (структурированные `EXA_ERROR:*` сообщения).
- Возвращать caller'у `STATUS: DEGRADED` + точная причина + что attempted.
- **Запрещённые формулировки:** `"permission blocked"`, `"tool failed"` без точного error.
- **Требуемые формулировки:** `"EXA_API_KEY missing"` / `"HTTP 429 rate_limit"` / `"connection timeout to api.exa.ai"` / `"mcp__exa__* not in toolset"` (точный diagnosis, не гипотеза).

### Step 5: Synthesize Findings

Агент читает markdown output из `exa_search.py` (title + url + highlight).

**Правило grounding:** для `depth=deep` каждый Key Finding **ДОЛЖЕН** иметь:
- Прямая ссылка на источник
- Цитата из highlight (quoted string)

Findings без grounding не включаются. Если нечего groundить — пишем в Limitations.

### Step 6: Persist (auto by script)

`exa_search.py` сам сохраняет:
- `~/.h2t/research/{project}-{topic-slug}-{YYYY-MM-DD}.partial.md` — technical metadata + telemetry
- `~/.h2t/research/{project}-{topic-slug}-{YYYY-MM-DD}.sources.json` — raw API responses

Агент дополняет `.partial.md` → финальный `.md` и удаляет `.partial.md`.

### Step 7: Present Output

Согласно `REPORT-SPEC.md` (см. Section 5). Финальный файл: `~/.h2t/research/{project}-{topic-slug}-{YYYY-MM-DD}.md`. В main conversation агент возвращает **summary + path**, не raw content.

---

## 5. `exa_search.py` Specification

### 5.1 CLI Contract

```bash
python scripts/exa_search.py preflight
# Exit 0 если env+connectivity OK. Exit 4 + stderr иначе.

python scripts/exa_search.py search \
  --query "Rejuve.bio competitors Switzerland 2026" \
  --mode competitor \
  --depth standard \
  --num-results 10 \
  --country CH \
  --start-date 2025-01-01 --end-date 2026-04-18 \
  --include-domains "example.com,swiss-biotech.ch" \
  --full-text \
  --output-dir ~/.h2t/research \
  --project rejuve

python scripts/exa_search.py crawl \
  --url "https://example.com/article" \
  --output-dir ~/.h2t/research \
  --project rejuve

python scripts/exa_search.py --version
```

### 5.2 Mode → Exa Params Mapping (hard-coded в script)

| mode | type | category | highlights.maxChars | default numResults |
|---|---|---|---|---|
| `generic` | `auto` | — | 4000 | 10 |
| `news` | `auto` | `news` | 3000 | 10 |
| `academic` | `auto` | `research paper` | 4000 | 8 |
| `competitor` | `auto` | `company` | 4000 | 10 |
| `people` | `auto` | `people` | 3000 | 10 |
| `deep` | `deep-reasoning` | — | 5000 | 5 |

### 5.3 Exit Codes

| Code | Meaning | Agent action |
|---|---|---|
| 0 | success | Parse stdout, continue workflow |
| 1 | args/user error | Stop, fix invocation |
| 2 | API error (non-2xx from Exa) | STATUS:DEGRADED, report to user |
| 3 | network/timeout | STATUS:DEGRADED, suggest retry |
| 4 | preflight (env/connectivity) | STOP workflow, fix env |

### 5.4 stderr Format (structured)

```
EXA_ERROR:API http=429 body='{"error":"rate_limit_exceeded"}'
EXA_ERROR:NETWORK timeout after 30s connecting to api.exa.ai
EXA_ERROR:ENV EXA_API_KEY missing
EXA_ERROR:ARGS unknown mode 'foo' (valid: generic,news,academic,competitor,people,deep)
EXA_ERROR:FILE cannot write to ~/.h2t/research: permission denied
```

Agent reads first stderr line → matches `EXA_ERROR:*` → reports structured DEGRADED status.

### 5.5 stdout Format (compact, agent sees this)

```markdown
## Exa Search: "Rejuve.bio competitors Switzerland 2026"
**Mode:** competitor | **Type:** auto | **Results:** 8 | **Cost:** $0.012 | **Latency:** 2.1s

1. [Rejuve.bio — About Us](https://rejuve.bio/about) — 320 chars highlight...
2. [Swiss Longevity Startups 2026](https://...) — 280 chars highlight...
...

Saved: ~/.h2t/research/rejuve-competitors-switzerland-2026-04-18.partial.md
JSON: ~/.h2t/research/rejuve-competitors-switzerland-2026-04-18.sources.json
```

### 5.6 Dependencies

- **Stdlib only** для MVP: `urllib.request`, `json`, `argparse`, `pathlib`, `hashlib`, `datetime`, `sys`, `os`.
- **exa-py добавляется в v0.2** если окажется нужен streaming / advanced retry / OpenAPI-drift resilience.

---

## 6. Exa API Surface — Explicit Scope

| API / Feature | v0.1 MVP | v0.2 | Out of scope |
|---|:---:|:---:|:---:|
| `/search` endpoint | ✅ | | |
| `/contents` (Content API, auto JS/PDF) | ✅ (subcommand `crawl`) | | |
| Search types: `auto` / `fast` / `instant` | ✅ | | |
| Search types: `deep-lite` / `deep` / `deep-reasoning` | ✅ (mode=deep) | | |
| Categories (all 6) | ✅ | | |
| `highlights` + `text` (full content) | ✅ (`--full-text`) | | |
| `systemPrompt` + `outputSchema` | ✅ | | |
| `includeDomains` / `excludeDomains` / `includeText` | ✅ | | |
| `startPublishedDate` / `endPublishedDate` | ✅ | | |
| `maxAgeHours` (cache vs livecrawl) | ✅ | | |
| `userLocation` (country) | ✅ (`--country`) | | |
| Streaming SSE | | ✅ | |
| Websets ("find anything" agentic) | | ✅ | |
| Monitors (changes detection) | | | ❌ (отдельный skill `h2t-ops:monitor`) |

---

## 7. Supporting Files

### 7.1 `reference.md` (~200 строк)

Разделы:
1. **Exa Search API full reference** — все параметры, типы, defaults.
2. **Content API reference** — `/contents` endpoint, автоматическая обработка JS-rendered / PDF.
3. **Mode → params mapping table** — canonical копия из §5.2.
4. **Cost per call (observed data)** — пополняется по мере использования.
5. **Known limitations** — что Exa не умеет (images, real-time push, monitoring).
6. **Troubleshooting** — common errors + fixes.

### 7.2 `examples.md` (~150 строк)

1. **Invocation examples** — 6-8 CLI calls под разные mode/depth.
2. **Output format template** — ссылка на REPORT-SPEC.md.
3. **Sample real-world output** — один полный пример с реальными URLs и costs.
4. **Cross-engine recipe** — как комбинировать `/research` + `/search-leads` вручную.

### 7.3 `systemprompts/*.md` structure

Каждый файл: YAML frontmatter + body. Body = текст для Exa `systemPrompt` field. Frontmatter содержит `exa_type`, `exa_category`, `output_schema` JSON fragment.

**Пример `systemprompts/competitor.md`:**

```markdown
---
mode: competitor
exa_type: auto
exa_category: company
output_schema: |
  {"type": "object", "properties": {
    "company_name": {"type": "string"},
    "hq_location": {"type": "string"},
    "founded": {"type": "string"},
    "product_categories": {"type": "array", "items": {"type": "string"}},
    "pricing_page": {"type": "string"},
    "team_size_estimate": {"type": "string"}
  }}
---

You are a competitive intelligence researcher. Prefer official company pages
(about, pricing, product, team) and SEC filings over press coverage. Include
concrete data: funding rounds with dates, product names, pricing tiers,
employee counts. Deduplicate results — same company from different domains
should be merged. Flag any information older than 12 months as `[stale: date]`.
```

Script читает frontmatter → берёт `exa_type`, `exa_category`, `output_schema`; body → `systemPrompt`.

---

## 8. `REPORT-SPEC.md` — Research Report Template

Отдельный spec file внутри skill (аналог Gershuni `DASHBOARD-SPEC.md`). Определяет **точный формат** того что сохраняется в `~/.h2t/research/{project}-{topic-slug}-{date}.md`.

### 8.1 Template

```markdown
# Research: {topic}

## Meta

| Field | Value |
|---|---|
| **Date** | 2026-04-18T14:32:10Z |
| **Project** | rejuve |
| **Session** | personal-os-agent-skills-m2-docs-skills-2026-04-18 |
| **Query** | Rejuve.bio competitors Switzerland 2026 |
| **Mode** | competitor |
| **Depth** | standard |
| **Engine** | Exa (via scripts/exa_search.py) |
| **Status** | ✅ completed / ⚠ partial / ❌ degraded |
| **Cache hit** | false (or path to cached) |

## Telemetry

| # | Tool | Args | HTTP | Latency | Cost | Results |
|---|---|---|---|---|---|---|
| 1 | `exa_search.py search` | `type=auto, category=company, numResults=10` | 200 | 2.1s | $0.012 | 10 |
| 2 | `exa_search.py crawl` | `url=rejuve.bio/about` | 200 | 1.3s | $0.002 | 1 |
| 3 | `exa_search.py crawl` | `url=swiss-longevity.ch` | 200 | 0.9s | $0.002 | 1 |
| **Totals** | | | **0 errors** | **4.3s** | **$0.016** | **12 items** |

> **Integrity check:** 3/3 calls used Exa API. 0 fallbacks to WebSearch.

## Sources

1. [Rejuve.bio — About](https://rejuve.bio/about) — [company page, 2026-02-14] — used in findings #1, #2
2. [Swiss Longevity Startups 2026](https://swiss-longevity.ch/report) — [market report, 2026-01-20] — used in finding #3
3. ...

## Key Findings

### Finding #1: {concise statement}
- **Evidence:** "Exact quote from source" — [Source #1]
- **Confidence:** high / medium / low
- **Implications:** {optional, 1-2 sentences}

### Finding #2: ...

## Grounding Notes

- Total sources cited: N
- Sources from Exa `/search`: N
- Sources from Exa `/contents` (crawl): N
- Sources from WebSearch / other: **must be 0 if Status=completed**
- Unique domains: N
- Date range of content: YYYY-MM-DD → YYYY-MM-DD
- Freshness: {within 6 months ✅ / mixed / older}

## Limitations

- {What was NOT found}
- {What could not be verified}
- {Assumptions made}

## Follow-up Suggestions

- {For employees → /search-leads}
- {For financial filings → re-run mode=academic + category=financial report}
- {For press coverage → re-run mode=news + date filter}

---

*Generated by `h2t-ops:research` skill v0.1.0 | Telemetry sent to h2t-evals: ✅*
```

### 8.2 Integrity Check Rule

Строка `Integrity check: N/N calls used Exa API. 0 fallbacks to WebSearch.` — **обязательна в каждом отчёте**.

Если она читается как `0/N calls used Exa. N fallbacks to WebSearch` — это signal что что-то пошло не так и Exa не был реально использован. Это и есть debug tool который user упомянул: через telemetry block в теле отчёта пользователь обнаружил что Exa не использовался в предыдущих сессиях.

### 8.3 Script vs Agent Responsibility

| File | Writer | Contains |
|---|---|---|
| `*.sources.json` | script | Raw Exa API responses + full metadata |
| `*.partial.md` | script | Meta + Telemetry (technical, factual) |
| `*.md` (final) | agent | Meta + Telemetry (copied from partial) + Sources + Key Findings + Grounding + Limitations + Follow-up |

Агент удаляет `.partial.md` после формирования финального `.md`.

---

## 9. Telemetry Integration (h2t-evals)

### 9.1 Two Levels

**A. Technical metrics — пишет `exa_search.py`:**

```python
post_telemetry({
    "session_id": os.environ.get("H2T_SESSION_ID"),
    "engine": "exa",
    "endpoint": "/search",
    "mode": args.mode,
    "exa_type": body["type"],
    "exa_category": body.get("category"),
    "query_hash": sha256(args.query)[:16],    # privacy: no raw query
    "num_results_requested": args.num_results,
    "num_results_returned": len(data.get("results", [])),
    "cost_usd": data.get("costDollars", {}).get("total"),
    "latency_ms": elapsed_ms,
    "http_status": resp.status,
    "exit_code": 0,
    "timestamp": datetime.now(timezone.utc).isoformat(),
})
```

**B. Semantic metrics — пишет агент в Step 7:**

- `sources_used_count` — сколько источников в final synthesis
- `sources_from_exa` — все ли ссылки из Exa results
- `report_length_chars`
- `depth_effective` — реально ли shallow/standard/deep был выполнен

### 9.2 Endpoint + Auth

- `POST ${H2T_EVALS_URL}/api/telemetry/research` (URL в `$H2T_EVALS_URL` env)
- Auth: `Authorization: Bearer $H2T_EVALS_TOKEN`
- **Fail-graceful:** если evals unreachable → append to `~/.h2t/research/.pending_telemetry.jsonl`, retry позже
- **Never block search** — telemetry fail = warn к stderr, но exit 0

### 9.3 Schema Contract

До implementation — подтвердить точный endpoint/schema у h2t-evals (OpenAPI/swagger если есть). Это **pre-implementation task** в plan.

### 9.4 Target Insights (через 2-4 недели use)

- Средний cost per mode
- Distribution запросов per mode
- Success rate (exit_code=0 / total)
- Latency p50/p95 per type
- Какие systemPrompts дают лучший engagement (сколько sources попадают в final reports)

---

## 10. Testing Strategy

### 10.1 Unit Tests (`tests/test_exa_search.py`)

- Mode → params mapping (6 modes × validation)
- argparse: missing/invalid args → exit 1 + stderr match
- Response parsing: success / partial / malformed JSON
- HTTP error handling: 429, 401, 500, timeout → exit codes 2/3
- Preflight: env var mock + connectivity mock
- File persistence: correct filename, markdown + JSON written
- stderr format: `EXA_ERROR:*` prefix, structured fields

Runner: `~/.h2t/venv/Scripts/python -m pytest plugins/h2t-ops/skills/research/tests/`

### 10.2 Integration Tests (manual, 3 scenarios)

Перечислены в `examples.md`. Smoke-validation перед релизом. CI нет (MVP).

---

## 11. Migration Plan

**Phase 1 — Build (1-2 дня):**

1. Создать skill в `plugins/h2t-ops/skills/research/` со всеми файлами
2. Установить `anysite` MCP: `claude mcp add --transport http --scope user anysite "https://mcp.anysite.io/mcp?api_key=..."`
3. Установить Bayram plugin: `/plugin marketplace add BayramAnnakov/lead-search-plugin && /plugin install lead-search@lead-search-marketplace`
4. Проверить h2t-evals endpoint availability + schema

**Phase 2 — Deprecate (0.5 дня):**

5. Заменить `plugins/h2t/agents/research-agent.md` на stub
6. Обновить `~/.claude/CLAUDE.md`: research routing rule
7. Проверить `h2t-factory:research-agent` (из plugin cache) — align или стаб

**Phase 3 — Observe (ongoing):**

8. После каждых ~20 research запросов — посмотреть h2t-evals dashboard, валидировать routing decisions, корректировать `systemprompts/` templates.

**Rollback:** если `/research` сломан — old stub возвращает инструкцию использовать WebSearch напрямую; никто не заблокирован.

---

## 12. Gershuni Practices (Adopted)

Из `ai-native:aim-sprint`:

1. **Architecture diagram** сверху SKILL.md (text-ASCII).
2. **Таблица "Файлы скилла"** — что внутри skill + назначение.
3. **Таблица "Выходные файлы"** — где что сохраняется.
4. **Обработка ошибок через таблицы** (сигнал → реакция).
5. **Антипаттерны section** в конце SKILL.md.
6. **Отдельный SPEC-файл для output format** (`REPORT-SPEC.md` ← `DASHBOARD-SPEC.md`).

---

## 13. Antipatterns (в SKILL.md)

- **Синтезировать findings без grounding** — каждое finding должно иметь цитату + URL.
- **Заявлять `depth=deep` если вызвал только `web_search_exa`** — status lying.
- **Скрывать tool failures** — любой non-zero exit кодируется в report Meta.Status.
- **"permission blocked" как diagnosis** — запрещено без подтверждённого CC permission denial. Используй точный error.
- **Silent fallback на WebSearch** — physically невозможен в дизайне (script не вызывает WebSearch), но агент тоже не должен.
- **Парсить HTML в агенте** — script's job. Агент читает уже cleaned markdown output.

---

## 14. Open Questions (for implementation plan)

1. **h2t-evals schema** — требует pre-implementation probe. Если endpoint/schema не готов — добавляем в backlog, telemetry делаем buffered-only (JSONL локально).
2. **Bayram plugin install path** — через marketplace или fork & modify? Если user хочет менять Bayram скилл под свои paths (`~/.h2t/research/` вместо дефолта), нужен fork.
3. **Anysite MCP ключ** — где хранить? User-scope `claude.json` работает, но ключ в plain text. Альтернатива: env var.
4. **exa-py добавление** — решение отложено до v0.2. Критерий: если streaming или advanced retry нужны хотя бы в одном use case.
5. **Cross-engine orchestration** — сейчас ручное. Если окажется 50%+ запросов требуют обоих engines — сделать meta-skill `/research-deep` как v0.2.

---

## 15. References

- Issue #69: `lichtpfad/h2t-skills#69` (root-cause + plan)
- Anthropic docs:
  - `code.claude.com/docs/en/skills` — skill structure
  - `code.claude.com/docs/en/plugins-reference` — plugin layout
  - `anthropic.com/engineering/multi-agent-research-system` — multi-agent pattern (used for parallel decomposition inspiration)
- Exa:
  - API reference: `docs.exa.ai/reference/search-best-practices`
  - OpenAPI spec: `docs.exa.ai/reference/search`
- Bayram plugin: `github.com/BayramAnnakov/lead-search-plugin`
- Gershuni skill: `ai-native-marketplace/plugins/ai-native/skills/aim-sprint`
- Related h2t-skills specs:
  - `docs/superpowers/specs/2026-04-03-skills-v3-architecture-design.md`
  - `docs/superpowers/specs/2026-04-14-m2-repo-docs-standards-design.md`

---

*Spec status: draft. Ready for user review before implementation plan.*
