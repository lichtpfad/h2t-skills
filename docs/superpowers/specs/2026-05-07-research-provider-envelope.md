---
title: "Research Provider Envelope + Exa Retry/Degraded Semantics"
status: "draft"
owner: "lichtpfad"
date: "2026-05-07"
milestone: "Phase-2 research tooling"
related_issue: "lichtpfad/h2t-skills#100"
parent_issue: "lichtpfad/h2t-skills#97"
related_adr: "C:/work/TD/docs/adr/0005-phase-2-script-extraction-backlog.md (Candidate 1)"
supersedes: null
---

# Research Provider Envelope + Exa Retry/Degraded Semantics

**Goal:** Расширить `exa_search.py` machine-readable envelope `{status, primary_engine, fallback_engine_used, results, telemetry}` с явной семантикой `OK | DEGRADED | FAILED`, добавить retry для transient failures, и зафиксировать в `SKILL.md` правила fallback-policy для агента. Закрыть silent-class "tool exit 0, но 0 results = успех".

**Scope (PR #1):** только `h2t-ops:research` skill. Полная реализация для `search` подкоманды; `crawl` получает envelope в минимальном объёме (без retry) — расширение в follow-up.

**Non-goals:**
- Не реализуем альтернативные search engines внутри Python (issue #98 — отдельный fetch ladder).
- Не вызываем `WebSearch` из Python (это agent tool; см. ADR-0005 vs #100 разрешение).
- Не меняем `MODE_CONFIG`, `CATEGORY_BLOCKS`, systemPrompt loading.
- Не трогаем `post_telemetry` schema (см. #70 item 3 — синхронизация с h2t-evals идёт отдельно).
- Не вводим retention/multi-key routing (#71).

---

## 1. Context & Root Cause

TD POP research run (`C:/work/TD/pipeline-log/td-pop/0001*.md`) выявил два класса silent failure, перпендикулярных уже зафиксированному в ADR-0003:

1. **Empty-results silent OK.** `exa_search.py` отрабатывает HTTP 200 + `results: []` → exit 0. Агент видит "успешный поиск без находок" и пишет это как valid finding ("ничего не нашли"). На деле это часто означает: запрос не подошёл к Exa neural ranker, нужен retry с вариацией или fallback.
2. **Каллер не имеет machine-readable status.** Текущий контракт — exit code + stderr `EXA_ERROR:*` для агента-человека-читателя. Нет JSON-объекта, который другой Python-скрипт (например, будущий `author_resolve.py` из #99 или `fetch_url.py` из #98) мог бы потребить программно.

Обе проблемы решаются единым envelope. ADR-0005 Candidate 1 описывает похожий wrapper, но с pseudocode `call_websearch(...)` внутри Python — это **технически невозможно**: `WebSearch` — agent tool, доступный только в LLM-runtime. Issue #100 это перечеркнуло. Реализуем по #100.

---

## 2. Backward Compatibility Constraints (HARD)

Это центральное требование. Не нарушаем существующие workflows.

| Surface | Текущее поведение | После PR |
|---|---|---|
| `exa_search.py search ...` без новых флагов (default) | Markdown summary в stdout, `EXA_ERROR:*` в stderr, exit 0/2/3/4 | **Идентичное.** Markdown summary в stdout, exit codes те же. Envelope **не печатается** в stdout по умолчанию. |
| `.partial.md` writer | Пишет meta + telemetry таблицу | **Идентичное.** Дополнительно встраивается строка `Provider status: OK | DEGRADED` в Meta-таблицу. |
| `.sources.json` writer | `{meta, response}` | **Расширение, не breakage.** Добавляется поле `meta.envelope` с тем же объектом, что доступен через `--envelope`. Старые consumers продолжают читать `meta` и `response`. |
| `EXA_ERROR:*` stderr-формат | Структурированные строки | **Идентичное.** Envelope не вытесняет stderr-сообщения. |

**Новое:** опт-ин флаг `--envelope` печатает JSON envelope в stdout **вместо** markdown summary. Машинные consumers явно его запрашивают. Sidecar-копия envelope всегда сохраняется в `.sources.json` для post-hoc анализа независимо от флага.

**Не меняем имена существующих CLI-флагов.** Не меняем positional contract.

---

## 3. Envelope Schema

```json
{
  "status": "OK",
  "primary_engine": "exa",
  "fallback_engine_used": null,
  "results": [...],
  "telemetry": {
    "attempts": [
      {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 1234, "error": null}
    ],
    "reason_for_fallback": null,
    "total_latency_ms": 1234,
    "total_cost_usd": 0.012
  },
  "meta": {
    "query": "...",
    "mode": "generic",
    "num_results_requested": 10,
    "num_results_returned": 7,
    "timestamp": "2026-05-07T12:34:56+00:00",
    "envelope_version": "1"
  }
}
```

### 3.1 `status` Decision Matrix

| Условие | `status` | exit | `fallback_engine_used` |
|---|---|---|---|
| HTTP 200, `len(results) > 0` (после всех retries) | `OK` | 0 | `null` |
| HTTP 200, `len(results) == 0` (после всех retries) | `DEGRADED` | 0 | `null` |
| HTTP 5xx → exhausted retries | `FAILED` | 2 | `null` |
| HTTP 4xx (без retry) | `FAILED` | 2 | `null` |
| URLError / timeout → exhausted retries | `FAILED` | 3 | `null` |
| Args validation error | `FAILED` | 1 | `null` |
| Env / preflight error | `FAILED` | 4 | `null` |
| Malformed JSON в success-ответе Exa | `FAILED` | 2 | `null` |

`fallback_engine_used` остаётся `null` навсегда в этом PR — Python не делает fallback. Поле зарезервировано для будущих провайдеров (например, если #98 добавит `direct_fetch` ladder, тот же envelope сможет заполнять поле).

### 3.2 `results` Shape

В точности тот же list, что Exa возвращает в `response.results` (без преобразований). Если `status == FAILED`, `results == []`.

### 3.3 `telemetry.attempts` Per-Attempt Record

```json
{
  "engine": "exa",
  "endpoint": "/search",
  "http": 503,
  "latency_ms": 4200,
  "error": "exa_5xx_retryable"
}
```

`error` — короткая категоризация (`null` если успех). Допустимые значения:
- `null` — успешный HTTP 2xx
- `exa_5xx_retryable` — HTTP 5xx
- `exa_4xx_nonretryable` — HTTP 4xx
- `exa_network_timeout` — `URLError`
- `exa_empty_results` — HTTP 200, но `results: []`
- `exa_malformed_json` — Exa вернул не-JSON либо отсутствует поле `results`

---

## 4. Retry Policy

**Принцип:** retry только то, что может measurably измениться при повторе. 4xx/args/env — никогда.

| Class | Retryable? | Max attempts | Backoff |
|---|---|---|---|
| HTTP 2xx + non-empty | — | 1 | — |
| HTTP 2xx + empty | **Yes** (1 retry) | 2 | 1.0s + jitter (0–500ms) |
| HTTP 5xx | **Yes** | 2 | 2.0s + jitter |
| HTTP 429 (rate limit) | **Yes** | 2 | 5.0s + jitter |
| HTTP 4xx (other) | No | 1 | — |
| `URLError` (network) | **Yes** | 2 | 1.5s + jitter |
| `socket.timeout` | **Yes** | 2 | 1.5s + jitter |
| Malformed JSON | No | 1 | — |
| Args/env validation | No | 1 | — |

**Hard cap на cumulative retry time:** 10 секунд. Если cumulative `sleep` приближается к лимиту, не делаем последний sleep — фиксируем результат как есть.

**No retry storms:** жёстко 2 attempts (1 initial + 1 retry). Не configurable в этом PR.

**Empty-result retry — без модификации запроса.** В этом PR не меняем `query` / `mode` / `additional_queries`. Это эвристики для будущей итерации (issue #99 уже идёт по этому пути с `additional_queries`). Цель empty-retry здесь — поймать transient ranking flake, не исправить плохой запрос.

---

## 5. CLI Surface Changes

### 5.1 Новые флаги (search subcommand)

| Флаг | Default | Эффект |
|---|---|---|
| `--envelope` | off | Печатает JSON envelope в stdout вместо markdown summary. Markdown summary НЕ печатается. |
| `--no-retry` | off | Отключает retry policy полностью (дебаг-флаг для воспроизводимости тестов). |

### 5.2 Не меняем

- Все существующие флаги (`--query`, `--mode`, `--depth`, `--num-results`, `--additional-queries`, `--start-date`, `--end-date`, `--include-domains`, `--exclude-domains`, `--include-text`, `--exclude-text`, `--country`, `--full-text`, `--output-dir`, `--project`).
- `preflight` подкоманду.
- `crawl` подкоманду — см. §6.

### 5.3 Stdout Contract

```
default       → markdown summary (как сейчас)
--envelope    → JSON envelope (single line или indent=2 — выбираем indent=2 для читаемости)
```

Stderr остаётся каналом для `EXA_ERROR:*` независимо от флага.

---

## 6. Crawl Subcommand (Minimal в PR #1)

`crawl` получает envelope в `.sources.json` (поле `meta.envelope`), но:
- Без retry (один HTTP вызов).
- Без `--envelope` флага в этом PR (полная reach в follow-up если понадобится).
- `status == DEGRADED` если `len(results) == 0` после успешного HTTP 200, иначе `OK / FAILED` по тем же exit codes.

Обоснование: scope первого PR держим узким; `crawl` сейчас вызывают в основном внутри workflow, где агент явно один раз дёргает URL.

---

## 7. SKILL.md Changes

### 7.1 Новая секция: Provider Status Envelope

Сразу после `## Tool Restriction`:

```markdown
## Provider Status Envelope

Каждый `$EXA_CLI search` пишет envelope в `.sources.json` (поле `meta.envelope`).
При `--envelope` флаге envelope печатается в stdout вместо markdown.

| `envelope.status` | Что это значит | Действие агента |
|---|---|---|
| `OK` | Exa вернул ≥1 результат после всех retries | Continue to Step 5 (synthesis) |
| `DEGRADED` | Exa отработал, но 0 results после retries | Report `STATUS: DEGRADED + reason=exa_empty_results`. Агент МОЖЕТ: (a) попробовать другой mode/query вариацию явно (новый CLI вызов), (b) использовать `WebSearch` с обязательной пометкой `STATUS: DEGRADED + fallback=websearch` в репорте, (c) остановиться. Silent fallback запрещён. |
| `FAILED` | HTTP 4xx/5xx/network/malformed после retries | Report `STATUS: FAILED + EXA_ERROR:*` (точное сообщение из stderr). STOP. |
```

### 7.2 Update Step 4 (Fail-Loud Checks)

Расширить таблицу exit codes — добавить колонку `envelope.status` соответствие. Добавить явное упоминание: `exit 0` НЕ означает `status == OK`; нужно проверить envelope.

### 7.3 Update Antipatterns

Добавить:
- **Treat exit 0 as success without checking envelope.status** — если status `DEGRADED`, агент обязан это отразить в репорте.
- **Silent retry того же запроса** — retry делает скрипт, не агент. Если агент видит DEGRADED, он либо явно меняет запрос, либо переключается на fallback с пометкой.

---

## 8. Tests

Файл: `plugins/h2t-ops/skills/research/tests/test_exa_search.py` (расширение).

Покрытие (все через mock `urllib.request.urlopen`, без сетевых вызовов):

| Test | Сценарий | Ожидание |
|---|---|---|
| `test_envelope_ok_when_results_present` | 200 + 3 results | exit 0, envelope.status="OK", attempts.len=1 |
| `test_envelope_degraded_when_empty_after_retry` | 200 + [] дважды | exit 0, status="DEGRADED", attempts.len=2, reason=`exa_empty_results` |
| `test_envelope_degraded_when_empty_recovers_on_retry` | 200 + [] → 200 + 5 results | exit 0, status="OK", attempts.len=2, первая attempt error=`exa_empty_results` |
| `test_envelope_failed_on_4xx_no_retry` | 401 | exit 2, status="FAILED", attempts.len=1, error=`exa_4xx_nonretryable` |
| `test_envelope_failed_on_5xx_after_retries` | 503, 503 | exit 2, status="FAILED", attempts.len=2, error=`exa_5xx_retryable` |
| `test_envelope_recovers_on_5xx_retry` | 503 → 200 + results | exit 0, status="OK", attempts.len=2 |
| `test_envelope_failed_on_urlerror_after_retries` | URLError, URLError | exit 3, status="FAILED", attempts.len=2 |
| `test_envelope_recovers_on_urlerror_retry` | URLError → 200 + results | exit 0, status="OK", attempts.len=2 |
| `test_envelope_failed_on_malformed_json` | 200 + body без поля `results` (или невалидный JSON) | exit 2, status="FAILED", error=`exa_malformed_json`, **никакого generic traceback** в stderr — только `EXA_ERROR:MALFORMED ...`. Этот тест критичен: текущий код может leak'нуть raw `JSONDecodeError`. |
| `test_envelope_flag_prints_json_to_stdout` | 200 + results, флаг `--envelope` | stdout — валидный JSON, начинается с `{`, markdown summary НЕ печатается |
| `test_no_envelope_flag_prints_markdown_default` | 200 + results, без флага | stdout начинается с `## Exa Search:`, валидного JSON нет |
| `test_envelope_in_sources_json_always_written` | 200 + results, без флага | `.sources.json` содержит `meta.envelope` с правильной формой |
| `test_no_retry_flag_disables_retries` | 200 + [], `--no-retry` | attempts.len=1 (один вызов, без retry) |
| `test_429_triggers_retry` | 429 → 200 + results | exit 0, status="OK", attempts.len=2 |
| `test_cumulative_backoff_capped` | три быстрых fake-failures | sleep cumulative ≤ 10s (mocked sleep counter) |

Сохраняем все существующие 60+ тестов без изменений.

---

## 9. File Structure

| Файл | Изменение |
|---|---|
| `plugins/h2t-ops/skills/research/scripts/exa_search.py` | **Refactor `call_exa` first** (см. §9.1) — типизированные return/raise вместо `die()` внутри провайдера. Затем добавить `envelope` builder, retry loop, sleep helper, флаги `--envelope` / `--no-retry`. Обновить `_run_search` и (минимально) `_run_crawl`. Бамп `__version__` до `0.1.1` (patch). |
| `plugins/h2t-ops/skills/research/SKILL.md` | Новая секция Provider Status Envelope. Update Step 4, Antipatterns. Бамп `metadata.version` до `0.1.1` (patch). |
| `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | Добавить 15 новых тестов (см. §8). |
| `plugins/h2t-ops/skills/research/reference.md` | Добавить раздел "Envelope schema" с примером JSON. |
| `plugins/h2t-ops/plugin.json` (или version в manifest) | Patch bump (0.1.0 → 0.1.1) через `python scripts/bump_plugin.py h2t-ops 0.1.1`. |
| `docs/superpowers/plans/2026-05-07-research-provider-envelope.md` | Plan под этот spec — пишется отдельно после approval. |

### 9.1 `call_exa` Refactor (Plan Prerequisite)

Текущий `call_exa` (строки 167–204) делает `die(3, "EXA_ERROR:NETWORK ...")` напрямую при `URLError`, и неявно падает на `json.loads` если Exa вернул не-JSON. Это блокирует retry-классификацию: retry wrapper не сможет поймать категорию ошибки и решить retryable/non-retryable.

**Pre-condition для retry loop:** провайдер-call отделить от exit-decision. Конкретно:

1. Ввести typed exceptions внутри модуля: `class ExaTransientError(Exception)`, `class ExaPermanentError(Exception)`, `class ExaMalformedResponseError(Exception)`. Single-file определение, не отдельный модуль.
2. `call_exa` либо возвращает `(http_status, body, latency_ms)` с успехом, либо raise одно из перечисленных. **Никаких `die()` внутри провайдера.**
3. Retry wrapper ловит `ExaTransientError` → retry, `ExaPermanentError` → exit без retry, `ExaMalformedResponseError` → exit 2 без retry.
4. `die()` вызывается **только** в `_run_search` / `_run_crawl` после того, как retry loop вернул финальный envelope.

Это — первый task в plan'е. Без него остальные tasks ломают существующие network-error tests.

---

## 10. Migration / Rollout

1. Все существующие callers (агент через SKILL.md, текущий CLI usage) продолжают работать без изменений — backward compat по §2 гарантирует.
2. После merge — `SKILL.md` инструктирует агента читать envelope. До этого момента агенты видят старый stdout формат и работают как раньше.
3. Версия в этом PR — **patch bump 0.1.0 → 0.1.1**. Per user CLAUDE.md правилу `minor только после live-подтверждения`: 0.2.0 откладывается до момента, когда после merge будет выполнен реальный research run и проверено наличие корректного envelope в `.sources.json` с status=`OK`/`DEGRADED`/`FAILED` на разных сценариях. Minor bump — отдельный follow-up commit.

---

## 11. Resolved Decisions (ранее open questions)

1. **Backoff sleep mocking.** Внутри `exa_search.py` ввести helper `sleep_with_jitter(base_seconds: float) -> None`, который инкапсулирует `time.sleep` + jitter. В тестах подменяем через `monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)` — фиксируем 0 реального ожидания, проверяем call count и аргументы.
2. **`EXA_WARN:RETRY_BUDGET_EXHAUSTED`.** Добавляем, **только когда cumulative backoff cap реально остановил очередной sleep**. Печатается в stderr одной строкой, не блокирует exit code (это warning, не error). Тест: `test_warn_emitted_when_budget_exhausted`. Не блокер для PR — если plan-author увидит, что добавление раздувает scope, переносим в follow-up и удаляем тест.
3. **`--envelope` для `crawl`.** Откладываем. В первом PR `crawl` получает только sidecar envelope в `.sources.json` (см. §6). CLI-флаг — в follow-up, когда появится machine consumer.

---

## 12. Acceptance Criteria (из issue #100, перепроверка)

- [x] envelope содержит `status`, `primary_engine`, `fallback_engine_used`, `telemetry` — §3
- [x] empty results после retries не выглядят как success — §3.1, §4
- [x] SKILL.md говорит когда fallback разрешён и как его помечать — §7.1
- [x] Tests покрывают OK / empty / HTTP error / timeout / malformed — §8
- [x] Не вызывает WebSearch silently (Python никогда не вызывает WebSearch) — §1, §3
- [x] Backward compat — §2 (добавлено сверх требований issue)

---

## References

- Issue #100: https://github.com/lichtpfad/h2t-skills/issues/100
- Umbrella #97: https://github.com/lichtpfad/h2t-skills/issues/97
- ADR-0005 Candidate 1: `C:/work/TD/docs/adr/0005-phase-2-script-extraction-backlog.md`
- ADR-0003 (skill-as-context-loader): `C:/work/TD/docs/adr/0003-skill-invocation-protocol.md`
- Текущий exa_search: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Текущий SKILL.md: `plugins/h2t-ops/skills/research/SKILL.md`
- Pipeline evidence: `C:/work/TD/pipeline-log/td-pop/0001-iteration-1-authors.md`, `0001b-iteration-1-retry-exa.md`
- Original v0.1 spec: `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`
