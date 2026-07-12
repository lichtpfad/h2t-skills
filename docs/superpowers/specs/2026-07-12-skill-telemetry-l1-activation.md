---
title: "Skill telemetry l1 activation"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-12"
milestone: ""
---

# Skill telemetry L1 activation

> Design inputs: `docs/reports/2026-07-12-skill-telemetry-audit.md` (карта+гэпы),
> `docs/reports/2026-07-12-skill-telemetry-taxonomy-design.md` (таксономия+синк).
> Epic: #289. Issues в скоупе: #306 (core.*), #307 (repo-assets), #309 (eval_set), #310 (record_eval).
> Out of scope (отдельные эпики): **#305 identity-rebrand + push-активация (VPS)** — отдельный трек
> (решение eng-review 2026-07-12: развязать L1-наполнение от платформенных операций);
> L2 harness-hook (#308 checklist), L3 judge, prompt-only скиллы.

## Problem

Телеметрия скиллов существует как инфраструктура (`SkillEval`, dual-write, mode-gating из PR #304),
но **не наполнена и не когерентна**:

1. Живое покрытие = только gather-стек (`main.py` → session-start/handoff); ~28 script-backed скиллов
   не инструментированы.
2. `core.*` кроме `task_success` — захардкоженные стабы (`session.py:210-213`): `op_type_correct_rate=1.0`,
   `deflection_rate` не считается, `time_to_first_valid_ms=0.0`, `tool_call_success_rate` — константа.
   Стабы = мусорный сигнал для любого потребителя.
3. repo-identity расходится по 3 строкам: `repo.toml`/CI=`claude-agent-skills`, runtime push=`agent-skills`
   (=project.id), GitHub=`h2t-skills`. Живая регистрация в central DB = `agent-skills`.
4. research-cost пишется в **несуществующий** endpoint `/api/telemetry/research` → нигде не персистится.
5. Custom-метрики частью объявлены-не-эмитятся; нет skill→class карты для per-class eval_set.
6. Легаси `record_eval` (×3 копии) — вестижиал с устаревшим `claude-agent-skills` namespace.

## Goals

- Каждая инструментированная сессия (L1) **self-complete**: все 5 `core.*` с реальными значениями
  или честными L1-прокси (не стабами).
- research-cost унифицирован на `SkillEval` (bespoke-канал deprecated).
- Custom-метрики по классам, зарегистрированы до использования (префикс — существующий `skills.*`,
  namespace-rename едет с идентити в #305).
- eval_set по-классу через skill→class карту.
- **Local-only в этом спеке**: всё разрабатывается/гоняется в режиме `local` (без VPS/токена),
  под текущей живой идентити `agent-skills`. Push-активация НЕ в скоупе (требует #305 + VPS).

## Non-Goals

- **Identity-rebrand `agent-skills`→`h2t-skills` + push-активация (#305)** — отдельный трек. Он тащит
  VPS-переоформление токена/metric-defs и namespace-rename `skills.*`→`h2t-skills.*`. L1-наполнение от
  него не зависит (local-режим работает под любой идентити).
- L2 harness-hook (точные session-факты `tool_call_success_rate`/`time_to_first_valid_ms`,
  `checklist_compliance`) — **отдельный эпик**. До него эти 2 метрики = честные L1-прокси.
- L3 LLM-judge и эталонные `*_cases.jsonl` для качества — **отложено** (вернуться с prompt-потоком).
- Инструментирование prompt-only скиллов.
- Построение потребителя-дашборда (это отдельная активационная веха #289).

## Constraints (verified against h2t-evals source)

- `validate-repo` энфорсит `core.*`-полноту **по-сессионно** (`cli.py:258-267`) → `core.*` нельзя дробить
  между процессами/слоями; L1-сессия обязана нести все 5.
- Session-metadata required (ingest reject): `repo, framework, source, host, run_env, eval_set_id,
  schema_version, sdk_version, metric_set_version, client_event_at` (`constants.py`). `branch`/`commit`
  НЕ обязательны (doc-vs-code дрейф на стороне h2t-evals).
- Custom-метрики: регистрировать до использования (`metric-def upsert`, owner=repo), иначе
  `400 E_METRIC_NOT_REGISTERED` → **тихая потеря в SDK-спуле** (h2t-evals#96).
- `eval_set_id` — свободная строка (нет FK/регистрации) → per-class не требует VPS-предусловия.
- Push-режим требует токен под `h2t-skills` + metric-defs owner=`h2t-skills` (VPS, repo-boundary → issue туда).
- SkillEval никогда не роняет вызывающий скилл (сохранить инвариант PR #304).
- **Vendored parity (Q1, eng-review):** `lib/eval/session.py` имеет byte-identical копию
  `plugins/h2t-core/lib/eval/session.py` + guard `tests/core/test_eval_vendored_parity.py`. Любая правка
  session.py (D1, D9) **обязана** менять ОБЕ копии, иначе CI красный.

## Design

### D1 — core.* self-complete на L1 (issue #306)
⚠ **Coredx-P1:** сейчас 5 `core.*` эмитятся ТОЛЬКО в `_send_central` (push-путь, :209-213); `_write_local`
(:152) пишет лишь caller-метрики → в `local`-режиме core.* **не пишутся вообще**. Значит core.* надо
считать в ОДНОМ месте (в `__exit__`/helper) и писать в ОБА пути (local JSON + central). Заменить *значения*:
- `op_type_correct_rate` — считается **на call-site** там, где есть определённая схема вывода (JSON-parseable
  + ожидаемые ключи → 1.0/0.0); call-site передаёт через `ev.metric(...)`. Где схемы нет — честный прокси
  (1.0 при отсутствии исключения). Не универсально-автоматом (Codex-P2).
- `deflection_rate` — реально: `1.0` без ручного fallback, иначе `0.0` (связать с `fallback_used`).
- `time_to_first_valid_ms` — честный прокси: wall-clock скрипта (задокументировать как proxy).
- `tool_call_success_rate` — честный прокси: успех самого скрипта (1.0/0.0).
- `task_success` — без изменений (`status=="success"`).
Убрать хардкод-константы; прокси помечены как proxy в описании метрики. core.* пишутся и в local, и в push.

### D2 — (перенесено в #305, вне скоупа)
Identity-rebrand + push-активация — отдельный трек. В этом спеке runtime `repo` остаётся `agent-skills`
(текущая живая идентити, совпадает с выданным токеном/metric-defs). См. Non-Goals.

### D3 — custom-метрики (taxonomy §4, accepted; префикс `skills.*`)
⚠ **Codex-P1:** `metric()` (:133) не принимает `level`/`unit`; `_send_central` дефолтит всем custom
`level="unit"` (:217) → business-метрики уедут как unit. **Расширить сигнатуру** `metric(key, *, level,
value_*, unit=None)` и протянуть level/unit в ОБА пути (local + central). Эмитить **впрок** (решение
eng-review: cost/latency — дешёвые L1-факты, копим до дашборда). Префикс `skills.*` (rename в #305).
Зарегистрированы (#289): `skills.gather_source_success_rate`, `skills.token_consumption`. Добавить:
- Кросс: `skills.duration_ms` (int/num/avg), `skills.fallback_used` (bus/bool/ratio), `skills.error_class` (unit/text/count).
- gather: `skills.sources_failed_count` (unit/num/avg).
- integration: `skills.research_cost_usd` (bus/num/sum), `skills.api_latency_ms` (int/num/avg), `skills.records_returned` (unit/num/avg).

Регистрация metric-defs (`metric-def upsert`, owner=`agent-skills`) пишет на central-сервис → **этот шаг
в треке #305/push**, не в local-only. В этом спеке метрики эмитятся в local JSON (регистрация не нужна для local).

### D4 — research-cost унификация (issue новый, W3)
⚠ **Codex-P2:** «одна сессия на инвокейшен» (A2) требует оркестрационного шва, которого нет — research идёт
per под-вызов. **Решение eng-review: interim per-под-вызов** — обернуть существующий `exa_search.py`-вызов в
`SkillEval` (шов есть), `skills.research_cost_usd` из envelope `telemetry.total_cost_usd`, cost агрегируется
server-side по eval_set. Per-invocation-шов (одна сессия = весь research) — **отдельный follow-up**.
Deprecate `post_telemetry` + env `H2T_EVALS_URL`/`H2T_EVALS_DISABLE` (bespoke-канал в мёртвый endpoint).

### D5 — eval_set по-классу (issue #309)
skill→class карта (gather/integration/prompt) из аудита §2.2 — **один источник истины** (модуль-константа,
A3 eng-review), НЕ дублировать по call-sites; `SkillEval` получает eval_set по классу:
`skills-{gather|integration|prompt}-baseline-v1`. Обновить `repo.toml` default.

### D6 — repo-ассеты (issue #307)
Написать файлы `evals/unit_cases.jsonl`, `integration_cases.jsonl`, `business_kpi.toml` — минимальные, но
реальные, parse-валидные. ⚠ **Codex/eng-review:** `validate-repo` читает **central-БД** (`cli.py:218`) → его
«зелёность» недостижима в local-only (нужны push-сессии). Поэтому в этом спеке — только **авторинг + parse-тест**
файлов; сам гейт `validate-repo зелёный` уезжает в трек #305/push.

### D7 — cleanup record_eval (issue #310)
Удалить вестижиал `lib/gather/eval.py` (+2 копии) + README-ссылки; проверить экспорт `__init__.py`.

### D9 — fix `_write_local` seq-glob (P1, eng-review; issue новый)
`session.py:161` делает `glob` для seq-номера на каждую запись → O(n) от числа файлов. При инструментировании
~15 горячих входов становится массовым. Заменить seq на timestamp/uuid в имени файла (убирает glob).
Затрагивает обе vendored-копии (Q1) + тесты формата имени (`test_session.py`). Существующие файлы не мигрируем
(имя — только для локальной инспекции, никто кроме самого seq-glob его не парсит).

## Tests (TDD, per D-item)

- D1: per-метрика — valid-выход→`op_type=1.0`, invalid→`0.0`; `deflection` от `fallback_used`; прокси
  задокументированы. Ноль хардкод-констант (T2).
- D3: тест — `metric(level=...)` протягивает level/unit в local И central; business ≠ unit.
- D4: тест — cost из envelope доходит до SkillEval-сессии (interim: per под-вызов).
- core.*-в-local: тест — `_write_local` содержит все 5 core.* (не только caller-метрики).
- D5: тест — каждый класс скиллов получает свой eval_set из единой карты.
- D7: тест — импорты не ломаются после удаления (`__init__.py` экспорт снят).
- D9: тест — параллельные/последовательные записи не коллизируют по имени без glob.
- Parity-guard (`tests/core/test_eval_vendored_parity.py`) сам сработает на рассинхрон копий (Q1).
- Весь pytest зелёный + ruff на изменённых; изменения session.py в ОБЕИХ копиях.

### D8 — инструментировать integration-класс (W3)
`SkillEval` в script-входы: connectors, drive, meetgeek, research, telegram, drawio, docs-*, edu-transcripts.
Тонкая общая обёртка (один helper), эмит core.* (D1) + доменные custom (D3).

## Rollout (waves) — всё в `local`, под `agent-skills`

| W | Содержание | Issues | Режим |
|---|---|---|---|
| W1 | D1 core.* реальные/прокси **в оба пути** (local+central); убрать стабы + D3 level-param в `metric()` | #306 | local |
| W2 | D5 eval_set по-классу + skill→class карта (единый модуль) | #309 | local |
| W3 | D8 инструментирование integration + D4 research (interim per-под-вызов) + D3 новые метрики (эмит) | #312 | local |
| W4 | D6 авторинг repo-ассетов (parse-тест) | #307 | local |
| W5 | D9 fix `_write_local` seq-glob (обе копии) | #313 | local |
| — | D7 cleanup record_eval ×3 | #310 | — |

Весь спек — L1-код в `local`, без VPS-зависимостей. **Central-гейты вне скоупа → трек #305/push:**
регистрация metric-defs, `validate-repo зелёный`, push-активация, identity-rebrand, namespace-rename `skills.*`→`h2t-skills.*`.

## Acceptance (всё проверяемо локально)

- **Local JSON-сессии несут все 5 `core.*`** (не только caller-метрики) — реальные/прокси, ноль хардкод-констант;
  прокси помечены как proxy. Тест на `_write_local` содержимое.
- `metric()` принимает `level`/`unit`, протягивает в оба пути; business-метрики не вырождаются в unit.
- research эмитит `skills.research_cost_usd` через SkillEval (interim per-под-вызов); bespoke `post_telemetry` удалён.
- Custom-метрики §4 **эмитятся** в local JSON (регистрация metric-defs — трек #305).
- eval_set по-классу из единого модуля-карты.
- repo-ассеты (`*_cases.jsonl`, `business_kpi.toml`) написаны и parse-валидны (гейт `validate-repo` — #305).
- `_write_local` без per-write glob (D9); обе vendored-копии синхронны (parity-guard зелёный).
- `record_eval` удалён (×3), весь pytest + ruff на изменённых зелёные.
- SkillEval-инвариант сохранён: ни один эмит не роняет вызывающий скилл.

**Вне acceptance (трек #305/push):** регистрация metric-defs, `validate-repo зелёный`, push, identity/namespace-rename.

## Open questions

- Точный список integration-скиллов первой волны W3 (все сразу vs research+connectors первыми).
- `business_kpi.toml` содержание (какие KPI, каденс).

## Eng-review outcome (2026-07-12, plan-eng-review + Codex outside-voice)

**Step 0 scope:** REDUCED — ре-бренд identity `agent-skills`→`h2t-skills` + push вынесены в отдельный
трек #305; спек = L1-наполнение в local-режиме.

**Findings свёрнуты в спек:**
- Q1 (9/10) vendored-parity: правки session.py в обеих копиях → Constraints.
- A2/D4: research-гранулярность — interim per-под-вызов (per-invocation-шов = follow-up).
- A3/D5: skill→class карта — единый модуль-константа.
- P1/D9 (5/10): `_write_local` seq-glob O(n) → timestamp/uuid, обе копии.
- D3-metrics: эмитить впрок (cost/business до дашборда).

**Codex outside-voice (независимая линза, подтверждено primary-source):**
- **Codex-P1:** core.* эмитятся только в `_send_central` (push), НЕ в `_write_local` → «self-complete в
  local» было ложно → D1 пишет core.* в оба пути.
- **Codex-P1:** `metric()` без `level`/`unit`, custom дефолтит unit → D3 расширяет сигнатуру.
- **Codex-P2:** `op_type_correct_rate` невычислим автоматом — считается на call-site, где есть схема, иначе прокси.
- **Codex-структурная:** `validate-repo` + `metric-def upsert` требуют central-сервис → недостижимы в
  local-only → central-гейты пере-скоуплены в #305. D6 = авторинг файлов + parse-тест.
- **Codex-P2:** D9 отсутствовал в rollout/acceptance → добавлен (W5).

**VERDICT:** спек пере-скоуплен под local-only L1; central-зависимые гейты изолированы в #305. Готов к
разложению в TDD-план. Cross-model: расхождений Claude↔Codex не осталось (все находки Codex приняты).
Новые issues заведены: #312 (D4 research-унификация), #313 (D9 glob-fix).

