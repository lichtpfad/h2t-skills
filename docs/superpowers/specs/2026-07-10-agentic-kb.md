---
title: "Agentic KB — evidence-grounded методология агентной разработки"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-10"
milestone: ""
---

# Agentic KB — evidence-grounded методология агентной разработки

> **Rev-2 (2026-07-10):** редизайн после codex-ревью — исправлены 4 P1 (несовместимая
> claim-schema, обход council автопромоцией, recurrence-as-truth, config/schema архитектура)
> + P2. Ключевой сдвиг: recurrence = сигнал eligibility+confidence, **не** истина; council
> обязателен для каждого claim; промоушен требует **application-outcome** (не счётчик
> повторов); external — отдельное ортогональное поле, не ступень лестницы.

## Проблема

Практика агентной разработки (subagent-оркестрация, гейты, extraction-пайплайны,
session-continuity) наработана эмпирически и повторно решается в разных репо. Cross-repo
practice-harvest (PR #293) собрал 40 находок, но они лежат статичным registry-снимком — нет
живого store, где находка получает вердикт под council, дозревает по наблюдаемым исходам
применения и промоутится в стандарт. Стандарт `kb-grounded-operator-decisions` требует KB,
которой для этого домена нет (есть только quant-kb по крипте).

**Цель:** поднять `agentic-kb` — evidence-grounded KB методологии агентной разработки, по
паттерну и контракту quant-kb/llm-kb-template (falsifiability + typed evidence + обязательный
council **сохраняются**), но со strength-axis, где сигнал силы = recurrence+исход в
собственной практике, а внешняя литература — ортогональное обогащение.

## Что уже есть (не строим заново)

- **`lib/practice_harvest/`** (h2t-skills) — пайплайн сбора+синтеза, batch-вход.
- **`docs/reports/2026-07-10-practice-harvest-registry.{json,md}`** — 40 находок = seed
  (импортируются как `HYPOTHESIS`, см. ниже).
- **`C:/dev/llm-kb-template`** — drop-in фабрика evidence-grounded KB: install-протокол,
  schemas, council-скрипты, тесты genericity.
- **`C:/dev/quant-kb`** — reference-имплементация паттерна.
- **`C:/dev/docs/standards/`** — approved-поверхность (промоушен-цель).

## Эпистемология (ядро) — rev-2

### Что сохраняется от контракта темплейта (НЕ трогаем)

- **Falsifiability** — каждый claim = проверяемое утверждение.
- **Typed evidence** — `evidence[]` = массив claim-объектов со `sources[]` и `confidence`
  (схема темплейта; наша прошлая иллюстрация `{internal, external}` была структурно
  несовместима — исправлено).
- **Council обязателен** — каждый claim проходит 3 судей; без `judge_pass: true` claim не
  попадает в `tldr`/`decision_triggers`/промоушен. **Автопромоции по recurrence НЕТ.**

### Атом = practice-claim (в схеме темплейта)

```yaml
evidence:
  - claim: "давать каждому сабагенту непересекающийся write-set"
    sources:
      - type: internal-lineage
        ref: "run:h2t-skills/2026-07-10-practice-harvest"   # applied + outcome-observed
        replicated: true
      - type: internal-lineage
        ref: "run:crypto-regime-spike/2026-06-27-plan4"
        replicated: true
      - type: external-practitioner              # ОРТОГОНАЛЬНО, опционально
        ref: "https://..."
        replicated: false
    confidence: High
    verdict: WORKS-IN-PRACTICE          # generic string; членство валидит lint из config
    external_corroboration: true         # ОТДЕЛЬНОЕ поле, НЕ ступень лестницы
    single_source_warning: false
    judge_pass: true                     # выставляет council
    judge_round: 1
```

- **`sources` типа `internal-lineage`** = не «находка встретилась в сессии», а **run, где
  практика применена и исход наблюдён** (run-id + применение + ожидаемый/наблюдённый
  результат). Это закрывает P1 recurrence-as-truth: счётчик повторов ≠ подтверждённый успех.
- **`external_corroboration`** — отдельное булево поле (ортогонально recurrence), НЕ ступень
  вердикта. Убирает ложную монотонность прошлой лестницы `+CORROBORATED`.

### Лестница вердиктов (config-driven, но принцип фиксирован)

| verdict | rank | promote_when |
|---|---|---|
| `HYPOTHESIS` | 0 | стартовое; ≤1 independent-domain outcome, или ждёт council |
| `WORKS-IN-PRACTICE` | 1 | **council PASS** И application-outcome в **≥2 independent domains** |

- `external_corroboration` и `single_source_warning` — ортогональные флаги поверх лестницы,
  не её ступени.
- **Промоушен в `docs/standards` — только operator sign-off** (verdict advisory, см. ниже).

### Калибровка — честная позиция (P2)

Асимметрия с quant-kb ADR-0001 реальна лишь частично: оператор — авторитет, чтобы
**ратифицировать application-outcome** (в рамках компетенции), что снимает проблему авторства
доменной истины. Но она **НЕ снимает** требований ADR-0001 к независимости judge/corpus и
held-out дисциплине. Поэтому до полноценной калибровки (Проект B) **вердикты agentic-kb
advisory** (`load_bearing=false`-аналог quant-kb): промоушен в стандарт требует operator
sign-off, council-вердикт сам по себе стандарт не двигает.

### Риск скоррелированных линий (P2) — операционализирован

Recurrence по доменам одного оператора может отражать одну привычку, не N независимых
подтверждений. Судья **Generalization** получает operational-контроль (не вопрос):

- **independent domain** = отдельный репо/тип-задачи с иным механизмом (напр. crypto-quant ≠
  landing-recovery ≠ research-synthesis); линии одного типа-задачи = один домен.
- **PASS** = механизм практики domain-agnostic (работает из общего свойства) И
  application-outcomes из ≥2 таких различимых доменов.
- **FAIL** = все линии одного типа-задачи/привычки, или механизм доменно-специфичен.

## Scope

### В scope (Проект A)

**A1. Апгрейд `llm-kb-template` — конфигурируемый verdict/strength-axis.**

| Фиксировано (принцип) | Конфигурируемо per-domain |
|---|---|
| Вердикт = монотонная лестница из (strength-axis + **обязательный council**) | имена/число ступеней |
| Trust-hierarchy = verdict × replicated × judge_pass → вес | `strength_axis` |
| Council majority-vote + grade-not-kill + falsifiability + typed evidence | `promote_when` каждой ступени |
| Faithfulness механический, отдельно от council | judge-оси |

- `kb.config.json`: `verdicts: [{name, rank, promote_when}]` +
  `strength_axis: source_group_convergence | domain_recurrence`.
- **Config/schema архитектура (P1, решено):** путь (b) — `wiki-page.schema.json` типизирует
  `verdict` как **generic string**; членство валидит **runtime** `lint_wiki.py` против
  `config.verdicts` (тот же паттерн, что уже применяется к source `type`). Статическая схема
  НЕ хардкодит enum. `kb.config.schema.json` (мета-схема) валидирует **форму лестницы**:
  `rank` монотонен и уникален, каждая ступень называет `promote_when` + trust-вес.
- **`synthesize_council.py` (P2):** расширить — деривировать и записывать claim `verdict` из
  config-лестницы по (strength-axis сигнал + council PASS), не только majority-подсчёт.
- `_kbconfig.py`: загрузка+валидация `verdicts`/`strength_axis` (fail-loud).
- **Back-compat gate (P2, обязателен ДО правок):** запиннить golden-fixture текущего quant-kb
  (config + 1 топик + ожидаемый filter-log/pipeline-state); A1 обязан воспроизвести
  **байт-идентичный** вывод на quant-дефолте (`source_group_convergence` +
  `CONFIRMED/LIKELY/HYPOTHESIS`). Без прохождения этого гейта template не коммитим.
- Тесты genericity зелёные + новый тест configurable-verdict. CLAUDE.template/README обновить.

**A2. Поднять `agentic-kb` (новый standalone-репо) на апгрейженном темплейте.**
- `git clone llm-kb-template agentic-kb`, install-протокол для `agentic-development-methodology`.
- **source_types:** `internal-lineage`, `external-practitioner`, `external-academic`
  (группы INTERNAL / EXTERNAL).
- **strength_axis:** `domain_recurrence`.
- **verdicts:** лестница выше; **judges:** Realizability / Generalization (operational-крит.
  выше) / Falsification («есть контр-линия/run, где практика провалилась?»).
- **taxonomy (living):** `subagent-orchestration`, `verification-gates`,
  `extraction-pipelines`, `session-continuity`, `evidence-synthesis`, `autonomous-run`,
  `environment-portability`.
- **seed (P1, исправлено):** 40 находок registry → stub-атомы **все как `HYPOTHESIS`**.
  Recurrence из харвеста записывается как `internal-lineage` sources, но **не** как
  подтверждённый исход. Промоушен в `WORKS-IN-PRACTICE` — только после council PASS +
  отдельно записанных application-outcome в ≥2 independent domains.

**A3. Retrieval MVP.**
- Retrieval-протокол темплейта (`kb-lookup`-аналог) как скилл/reference в h2t-skills.
- Batch-вход: харвест → candidate queue (registry) → council → атом.
- **Consumer mapping (P2):** `kb-grounded-operator-decisions` консультирует agentic-kb так —
  authoritative = `verdict: WORKS-IN-PRACTICE` + `judge_pass: true`; `HYPOTHESIS`
  surfaced-with-warning, не как основание. Промоушен в стандарт = operator sign-off.

### Не в scope A → backlog (зафиксировано в GitHub issues)

- **#295 A-phase-2 (fast-follow):** live operator-question триггер + промоушен подтверждённого
  в `docs/standards`.
- **#296 Phase 2 — cross-machine JSON-L scan:** расширить coverage харвеста до всего JSON-L на
  двух машинах; gated **gbrain-spike** (≤4ч, PGLite-local, read-only) — НЕ коммит вслепую.
- **#297 Проект B — унификация машинерии:** влить свежий quant-kb (judge-calibration ADR-0001,
  faithfulness-механику, model-routing Plan 19), шеринг council-движка, news-research алгоритм.
- **#298 Downstream (отдельная спека):** overview незаконченных проектов — что убить /
  приоритизировать / как влить новый опыт в зависшие. Потребитель инсайтов, не KB.

Эпик Проекта A: **#294**.

## Владение / репо

| Слой | Репо | Роль |
|---|---|---|
| Общая машинерия | `llm-kb-template` | апгрейд A1 (+ back-compat golden gate) |
| Данные KB | `agentic-kb` (новый) | верифицированные practice-claim'ы |
| Тулинг | `h2t-skills` | harvest-пайплайн + retrieval-скилл |
| Approved | `C:/dev/docs/standards` | промоушен по operator sign-off |
| POS | — | вне петли |

## Петля (целевая; MVP покрывает жирное)

```
входы кандидатов:
  (1) LIVE (phase-2): агент упёрся → нет в KB → research → кандидат-claim (HYPOTHESIS)
  (2) BATCH (MVP):    прогон lib/practice_harvest → кандидаты (HYPOTHESIS)
        │
        ▼
  candidate queue (registry)
        │  COUNCIL ОБЯЗАТЕЛЕН (3 судьи) — recurrence лишь сигнал confidence/eligibility
        │  promote → WORKS-IN-PRACTICE ТОЛЬКО при council PASS + application-outcome ≥2 доменов
        ▼
  agentic-kb/wiki/<topic>.md  (атом; verdict advisory)   ←── retrieval: kb-lookup (MVP)
        │  промоушен = operator sign-off (не автоматом от council)
        ▼
  docs/standards/ (approved)
```

## Критерии готовности A

- [ ] `llm-kb-template`: verdict/strength-axis конфигурируемы (путь (b): generic string +
      runtime membership); мета-схема валидирует форму лестницы; `synthesize_council` пишет
      verdict; **back-compat golden-gate PASS** (байт-идентичный quant-вывод); тесты зелёные +
      configurable-verdict тест.
- [ ] `agentic-kb` поднят: config + taxonomy + 3 судьи (Generalization с operational-крит.) +
      seed 40 находок **как HYPOTHESIS**; `pytest` + `lint_wiki` зелёные.
- [ ] Retrieval-протокол доступен агенту; consumer-mapping для стандарта задокументирован.
- [ ] Один council-прогон по ≥1 P0-топику → атомы с council-вердиктами (advisory).
- [ ] Стандарт `kb-grounded-operator-decisions` разблокирован (KB существует).

## Открытые вопросы

- Имя репо: `agentic-kb` (параллельно `quant-kb`) — рабочее.
- Где физически живёт retrieval-скилл: новый скилл в h2t-skills vs reference в agentic-kb.
- Формат application-outcome записи (run-id + applied + expected/observed): минимальный
  артефакт vs расширение registry-схемы харвеста — решить в плане.

## Ссылки

- Codex-ревью rev-1 (4 P1 + 5 P2) — учтено в rev-2.
- Эпик: #294. Backlog issues: #295 (phase-2 loop), #296 (cross-machine scan + gbrain spike),
  #297 (Проект B unify), #298 (project overview).
- Seed: `docs/reports/2026-07-10-practice-harvest-registry.md`.
- Паттерн: `C:/dev/llm-kb-template/README.md`, `C:/dev/quant-kb/JUDGE-PIPELINE.md`.
- Калибровка (Проект B): `C:/dev/quant-kb/docs/adr/0001-...md`.
