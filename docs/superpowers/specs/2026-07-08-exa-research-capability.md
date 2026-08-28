---
title: "Exa research capability"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-08"
milestone: ""
issue: ""
---

# Exa research capability

## Context

Exa выпустили новые продукты поверх базового `/search`. Наш research-коннектор
(`h2t_ops/connectors/research/exa.py`) сейчас использует лишь малую часть их
поверхности. При этом наш «кастомный пайплайн» — по сути тонкая обёртка над
`/search`: мы не конкурируем с Exa по качеству поиска, мы его оркестрируем.

### Что нового у Exa

1. **Расширенный `/search`** — `type` теперь 6 уровней: `instant` → `fast` →
   `auto` → `deep-lite` → `deep` → `deep-reasoning`. Плюс `stream` (SSE),
   `maxAgeHours` (свежесть / принудительный live-краул), `outputSchema`
   (`{type:text}` или `{type:object}`), `systemPrompt`, `additionalQueries`.
   Мы используем только `fast/auto/deep` + schema.
2. **Research API** (`POST /research/v1`, async) — многошаговый агент: план →
   серия поисков → краул страниц → синтез с цитатами. Возвращает `researchId`,
   статус через `GET /research/v1/{id}` (`?events=true` — полный лог: `numSearches`,
   `numPages`, `reasoningTokens`). Модели `exa-research-fast` / `exa-research` /
   `exa-research-pro`. Выход — markdown-отчёт **или** structured JSON.
3. **Agent API** (`POST /agent/runs`, async) — оркестратор премиум data-source
   партнёров (`fiber_ai` B2B-контакты $0.02, `similar_web` трафик $0.03,
   `baselayer` верификация US-бизнеса $0.022, `financial_datasets` $0.01,
   `particle` подкаст-транскрипты $0.015, `affiliate.com`, `jinko`) + web search →
   один structured output. Стоимость аддитивная: `agentCompute` + `search` +
   `emails` + `phoneNumbers` + per-provider. Профиль — LeadGen / enrichment / invest.

### Живая проверка `type` (2026-07-08)

| type | HTTP | latency | вывод |
|---|---|---|---|
| `deep` | 200 | 3.9 s | наш текущий — лёгкий, **не** задепрекейчен |
| `deep-reasoning` | 200 | 13.4 s | новый — реально multi-step reasoning |
| `auto` | 200 | 1.3 s | обычный |

Наш `type: deep` живой, но `deep` ≠ `deep-reasoning` — мы недобираем глубину.

### Управляемость (что важно для клиентской работы)

Ты управляешь **входом, границами и формой выхода** (schema / systemPrompt / model /
type / domains / dates / maxAgeHours / additionalQueries), можешь аудировать через
`events=true`. Ты **не** управляешь внутренними шагами агента (выбор инструмента на
шаге, ранжирование, fusion). Это «управление по рамкам + схеме», не «сценарий».

## Strategic decision

**Не переизобретать Exa.** Обернуть новые endpoint-ы как **инструменты внутри**
нашего пайплайна, а не как замену пайплайну. Пайплайн остаётся оркестратором и
владельцем финального синтеза.

Ценность нашего пайплайна (то, что Exa не продаёт): оркестрация нескольких
провайдеров (Exa + Anysite + KB), интеграция с памятью/графом, воспроизводимость,
контроль стоимости и **`evidence-grounded-synthesis` (анти-галлюцинация)** — критично
для клиентских deliverable-ов.

**Дефолтный режим для клиентской работы = retrieval-first:** Exa/Agent тянут
структурированные данные с цитатами, финальный свод и выводы делаются под нашей
анти-галлюцинационной дисциплиной, а не отдаются чёрному ящику. Полный
«агент-сам-синтезировал» режим доступен, но помечен как быстрый/чернильный.

## Goal

Поэтапно интегрировать новые возможности Exa в `h2t-ops research` как отдельные
режимы/capability, переиспользуя существующие envelope / retry / secret-resolution /
cost-трекинг. Обновить скилл `h2t-ops:research` так, чтобы он знал обо всех режимах и
когда какой применять.

## Non-goals

- Замена `/search` — новые режимы дополняют, не вытесняют.
- Собственный поисковый движок или собственный многошаговый агент — используем Exa.
- Ломающие изменения существующих команд `search` / `answer` / `similar` / `fetch`.

## Phased design

### Phase 1 — `research` capability (Research API) — retrieval-first ядро
- `exa.py`: `research_task(instructions, *, model, output_schema, api_key, wait,
  poll_interval, timeout_s)`. `POST /research/v1` → poll `GET /research/v1/{id}` до
  `completed|failed`.
- Параметризовать `call_exa` по `endpoint` (сейчас `/search` хардкодится в attempt-записях).
- Расширить envelope-телеметрию: `numSearches`, `numPages`, `reasoningTokens`.
- Модели: `exa-research-fast` (default), `exa-research`, `exa-research-pro`.
- `commands.py`: `research` subparser — `--instructions`, `--model`, `--schema`,
  `--wait/--no-wait`, `--poll-interval`, `add_fmt`. `run()` ветка по образцу `answer`.
- `provider_routing.py`: `"research"` в `CAPABILITIES` + `ProviderCapability("exa",
  "research", required_secrets=("EXA_API_KEY",), priority=10)`.
- `client.py`: метод-обёртка.
- Тесты: `tests/connectors/research/test_research_task.py` (mock POST 201 + GET
  running→completed, poll-budget, failed, schema-validation, routing).
- **Skill:** документировать `research` режим + «когда research vs search».

### Phase 2 — расширенный `type`-ladder на `/search` (дешёвый апгрейд)
- Поднять `MODE_CONFIG`: добавить `deep-reasoning`, опционально `instant`/`deep-lite`.
- Проброс `maxAgeHours` (свежесть/live-краул) и `stream` (опционально).
- Решить судьбу текущего `mode=deep` → маппить на `deep-reasoning` или ввести новый
  режим `deep-reasoning`, оставив `deep` как есть (без ломки).
- Тесты + skill-доки на новый режим.

### Phase 3 — `agent` capability (Agent API) — LeadGen / enrichment (пилот)
- `exa.py`: `agent_run(query, *, data_sources, output_schema, api_key, wait, ...)`.
  `POST /agent/runs` → poll `GET /agent/runs/{id}`.
- Envelope: per-provider `AgentDataSourceUsage` / `AgentDataSourceCost` + `emails` /
  `phoneNumbers` cost.
- `commands.py`: `agent` subparser — `--query`, `--data-source` (repeatable),
  `--schema`, `--wait`, `add_fmt`.
- `provider_routing.py`: `"agent"` capability.
- **Cost-гейт:** default без платных провайдеров; платные включаются явным
  `--data-source`. Логировать стоимость до запуска, где возможно.
- Тесты + skill-доки. Профиль применения — клиентский LeadGen/Invest.

### Phase 4 — skill + decision-guide (cross-cutting)
- `SKILL.md`: единая «capability decision-guide» таблица (когда какой режим).
- Депрекейтнутый `plugins/h2t/agents/research-agent.md` — оставить указателем,
  при необходимости дополнить ссылкой на новые режимы.
- Обновить `references/` под retrieval-first синтез-контракт.

## Open questions

1. **`mode=deep` default** — маппить на `deep-reasoning` (глубже, дороже, 13 с) или
   ввести отдельный `deep-reasoning`, не трогая `deep`? (склоняюсь ко второму —
   без ломки).
2. **`research --wait` default** — ждать (проще человеку) или async-first (не
   блокировать CLI на 30–120 с)? (склоняюсь: `--wait` default для человека,
   async доступен флагом).
3. **`answer` → `exa-research-fast`** — держать оба (не ломать `answer`).
4. **Agent API scope** — Phase 3 сразу или отдельный пилот после Phase 1–2.

## Cost / risk

- `research-pro` и платные Agent-провайдеры тарифицируются по searches + pages +
  reasoning-tokens + per-provider → default дешёвые модели, платное — только явным флагом.
- Async polling — новый жизненный цикл запроса (POST→poll), а не «ещё один endpoint».
- Для клиентских deliverable-ов финальный синтез держим под `evidence-grounded-synthesis`.

## Rollout

Фазы = отдельные GitHub issues, мержатся независимо. Phase 1 — критический путь;
Phase 2 — дешёвый параллельный апгрейд; Phase 3 — пилот под клиентский кейс;
Phase 4 — обновляется инкрементально по мере готовности каждой фазы.
