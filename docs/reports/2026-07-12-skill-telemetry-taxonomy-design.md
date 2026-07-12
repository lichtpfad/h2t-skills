# Skill Telemetry — Metric Taxonomy & Sync Design (2026-07-12)

Фаза 2 после аудита `2026-07-12-skill-telemetry-audit.md`. Определяет **какие метрики мы эмитим,
на каком слое, для какого потребителя**, и **как это синхронизируется с h2t-evals**.
Принцип: метрика без потребителя = шум → каждая привязана к consumer'у (metric→consumer).
Родитель: #289. Решения оператора из аудита §4 приняты как вход.

## 1) Consumers first — зачем вообще заполнять телеметрию

Метрика оправдана, только если питает решение. Пять потребителей:

| Consumer | Решение, которое питает | Блокирующий? |
|---|---|---|
| **C1 CI-gate** (`validate-repo`, unit/integration thresholds) | пускать ли merge/release | да (hard-gate) |
| **C2 Judge-score** (LLM над `*_cases.jsonl`) | качество работы скилла/модели, регрессии | нет (сигнал качества) |
| **C3 Cost-guard / dashboard** | сколько тратим (Exa/API), где дорого | нет (операционный) |
| **C4 Business-KPI** | приоритизация (что чинить/улучшать) | нет (§10 non-blocking) |
| **C5 Skill-graph feedback** | авто-уроки при регрессии eval-score (`SkillEval.close`) | нет (обучение) |

Любая предложенная ниже метрика ссылается на C1–C5. Нет ссылки → не эмитим.

## 2) Три слоя измерения (авторитетное размещение)

| Слой | Механизм | Что ТОЛЬКО здесь измеримо |
|---|---|---|
| **L1 script** | `SkillEval` внутри Python-входа | детерминизм скрипта: успех/фейл, длительность, schema-валидность вывода, **стоимость своих API-вызовов**, source success-rate, доменные счётчики |
| **L2 harness-hook** | PreToolUse/PostToolUse/Stop на `Skill` | session-факты: `tool_call_success_rate`, `time_to_first_valid_ms`, последовательность tool-call, checklist-step completion, abort-safety |
| **L3 judge** | LLM над `*_cases.jsonl` (оффлайн-eval) | **качество**: следование pipeline, корректность, полнота — пассивная телеметрия это НЕ меряет |

Правило размещения: метрику ставим на **самый низкий слой, где она достоверно измерима**.
Захардкоженные `core.*` (аудит G2) распределяются по этому правилу — см. §3.

## 3) core.* (обязательный контракт) → L1 self-complete + L2 enrichment

**Жёсткое ограничение (verified):** `validate-repo` энфорсит `core.*`-полноту **по-сессионно**
(`h2t-evals/cli.py:258-267` — для каждой сессии `required_core − present`, миссинг = fail). L1 (скрипт)
и L2 (hook) — разные процессы = **разные `session_id`** (хотя SDK допускает явный shared id, корреляция
hook↔subprocess дорога). Значит `core.*` **нельзя дробить** между слоями — иначе ни L1, ни L2-сессия
не проходят гейт.

**Решение:** L1-сессия эмитит **все 5 `core.*`** (self-complete; `_send_central` уже так делает —
одна сессия start→5→finish). L2-hook — **отдельный обогащающий поток** (своя сессия, глубже session-level
сигнал), НЕ владелец mandatory-метрик.

**Стаб vs прокси (суть дефекта G2):** проблема не в наличии 5, а в *значениях* — 4/5 захардкожены
константами независимо от реальности. Различаем:
- **Стаб** (чинить): `op_type_correct_rate=1.0` игнорит фактический вывод → ложь. Реально: JSON
  parseable + ожидаемые ключи. `deflection_rate` тоже реально измеримо.
- **Честный прокси** (оставить, задокументировать): `time_to_first_valid_ms` = полный runtime скрипта;
  `tool_call_success_rate` = успех самого скрипта (1.0/0.0). Это не ложь — это L1-приближение session-факта.

| Метрика | Уровень | L1 (обязательно, self-complete) | L2-обогащение (опц.) |
|---|---|---|---|
| `core.task_success` | integration | реально: нет исключения | — |
| `core.op_type_correct_rate` | unit | **реально** (schema-валидность) — чинить стаб G2 | — |
| `core.deflection_rate` | business | **реально** (без ручного fallback) — чинить стаб G2 | — |
| `core.time_to_first_valid_ms` | integration | **честный прокси**: runtime скрипта | точный session-факт |
| `core.tool_call_success_rate` | unit | **честный прокси**: успех скрипта | successful/attempted по ходу |

Вывод: L1 самодостаточен для гейта. L2 — не «доносит 2 недостающие», а уточняет 2 прокси + добавляет
свои session-метрики отдельным потоком. Это снимает требование кросс-процессной корреляции для C1.

## 4) Custom-метрики `h2t-skills.*` по классам (предложение)

Именование `h2t-skills.<name>` (после ре-бренда, #305). Каждую регистрировать до использования
(§7 контракта, метод — `metric-def upsert`, h2t-evals#97 DONE). Уровень/тип/агрегация/слой/consumer:

### 4.1 Кросс-классовые (все script-backed)
| key | level | type | agg | слой | consumer | как |
|---|---|---|---|---|---|---|
| `h2t-skills.duration_ms` | integration | num | avg | L1 | C3,C4 | wall-clock скрипта |
| `h2t-skills.fallback_used` | business | bool | ratio | L1 | C4 | сработал ли degraded-путь |
| `h2t-skills.error_class` | unit | text | count | L1 | C3 | тип исключения (provider/usage/config/auth/net) — коды выхода коннекторов 1-6 |

### 4.2 gather-класс (session-start, handoff, init-project)
| key | level | type | agg | слой | consumer | как |
|---|---|---|---|---|---|---|
| `h2t-skills.gather_source_success_rate` | unit | num | avg | L1 | C1,C4 | доля источников без ошибки (уже эмитится) |
| `h2t-skills.context_tokens_estimate` | unit | num | avg | L1 | C3 | len(payload)//4 (уже как `token_consumption`) |
| `h2t-skills.sources_failed_count` | unit | num | avg | L1 | C3 | число упавших источников |

### 4.3 integration-класс (connectors, research, drawio, docs-*, transcripts)
| key | level | type | agg | слой | consumer | как |
|---|---|---|---|---|---|---|
| `h2t-skills.research_cost_usd` | business | num | sum | L1 | **C3** | из envelope `telemetry.total_cost_usd` — реконсиляция §5 |
| `h2t-skills.api_latency_ms` | integration | num | avg | L1 | C3 | latency внешнего вызова (Exa/Google/…) |
| `h2t-skills.records_returned` | unit | num | avg | L1 | C4 | размер результата (items) |

### 4.4 prompt-класс — отложено (поток 2)
Телеметрия L1/L2 неинформативна (нет кода / ценность в модели). Механизм — **L3 judge** над
`*_cases.jsonl`, точечно, если появится нужда + эталонные кейсы. Метрики здесь НЕ определяем сейчас.

### 4.5 `skills.checklist_compliance` (G5)
Объявлена, не эмитится. Размещение — **L2** (доля выполненных шагов SKILL.md, вкл. session-naming
GATE = session-факт). Либо реализовать на L2-hook, либо снять объявление (issue #308).

## 5) Cost-телеметрия — реконсиляция (НЕ greenfield)

Сейчас **два несовместимых канала** (аудит-находка):
- `SkillEval` → SDK `/v1/sessions/*`, `X-H2T-Token`, `H2T_EVALS_SERVICE_URL`, SDK-spool, `H2T_EVALS_MODE`.
- research `post_telemetry` → сырой POST `/api/telemetry/research`, `Bearer`, `H2T_EVALS_URL`, локальный
  JSONL. **Endpoint на сервисе НЕ существует** → research-cost уходит в `awaiting_endpoint`, централизованно
  не персистится (живёт только в возвращаемом envelope).

**Решение:** унифицировать на `SkillEval`. Research оборачивается в `SkillEval` и эмитит
`h2t-skills.research_cost_usd` (+ latency/records) как custom-метрики. Бespoke `post_telemetry` +
env `H2T_EVALS_URL`/`H2T_EVALS_DISABLE` — deprecate. Альтернатива (реализовать `/api/telemetry/research`
на сервисе) — отвергнута: плодит второй канал, auth/spool/gate расходятся. → отдельный follow-up issue.

## 6) Sync-модель с h2t-evals

- **Dual-write + mode-gating** — уже построено (`resolve_mode`, PR #304): `off`/`local`/`push`, off-by-default.
  Не переизобретать.
- **eval_set по-классу** (#309): `skills-{gather|integration|prompt}-baseline-v1`; SkillEval получает eval_set
  из skill→class карты (источник — аудит §2.2). ✅ verified: `eval_set_id` — свободная строка на сессии
  (нет FK/регистрации, validate-repo проверяет только non-null) → **W2 без VPS-предусловия** (в отличие
  от токена/metric-defs).
- **repo identity** = `h2t-skills` (#305), декуплена от `project.id`; токен+metric-defs переоформить на VPS.
- **Регистрация метрик до использования**: все `h2t-skills.*` из §4 через `metric-def upsert` (owner=`h2t-skills`).
- **Offline-first**: SDK-spool сохраняет при недоступности сервиса, авто-ретрай. (⚠ но 4xx молча теряются в
  спуле — h2t-evals#96; регистрировать метрики ДО пуша, иначе `400 E_METRIC_NOT_REGISTERED` → тихая потеря.)
- **L2-hook канал**: session-факты требуют harness-hook (отдельная задача); до неё `core.tool_call_success_rate`
  / `time_to_first_valid_ms` не слать (не заглушкой).
- **Graph-bridge** (C5): `SkillEval.close(score)` уже пишет eval-finding уроки при delta>0.1 — сохранить.

## 7) Rollout (волнами, привязка к issues)

| Волна | Содержание | Issues | Предусл. |
|---|---|---|---|
| W0 | ре-бренд identity → h2t-skills + VPS переоформление токена/metric-defs | #305 | — |
| W1 | core.* реальные на L1 (op_type, deflection) + удалить заглушки | #306 | W0 |
| W2 | eval_set по-классу + skill→class карта | #309 | W0 |
| W3 | инструментировать integration-класс (SkillEval в connectors/research/drawio/docs-*) + research-cost реконсиляция §5 | (нов.) | W1,W2 |
| W4 | repo-ассеты `*_cases.jsonl` + `business_kpi.toml` → validate-repo зелёный (C1) | #307 | W2 (**НЕ** W5 — L1 self-complete закрывает core.* для гейта) |
| W5 | L2 harness-hook (обогащение): точные `tool_call_success_rate`/`time_to_first_valid_ms` + `checklist_compliance` — отдельный поток, НЕ блокер C1 | (нов.), #308 | W1 |
| W6 | L3 judge-кейсы для критичных скиллов (C2) | (нов.) | W4 |
| — | cleanup вестижиал `record_eval` | #310 | — |

**CI-статус (verified):** `eval-gate` job (`evals.yml`) сейчас **условно пропускается** — `validate-repo`
бежит только при `H2T_EVALS_ENABLED=1`+secrets, иначе echo "BLOCKED", шаг зелёный. Реальный гейт = unit-tests.
C1 спит до W0-активации; текущие стабы CI не ломают, но при активации per-session core.*-полнота обязательна.

## 8) Открытые решения для оператора

1. **research-cost реконсиляция** (§5): унифицировать на SkillEval (реком.) vs просить h2t-evals реализовать
   `/api/telemetry/research`? — завести issue.
2. **L2-hook сейчас или позже:** без него 2/5 `core.*` неполны. Строить L2 в этом эпике или отдельным?
3. **Custom-метрики §4** — принять список как есть или урезать? (каждая уже привязана к consumer'у).
4. **Judge (L3)** — какие скиллы первыми получают эталонные кейсы (research? connectors?), критерий выбора.
5. **W-порядок** — W0 (ре-бренд+VPS) блокирует push; делать ли L1-наполнение параллельно в local-режиме до W0.
