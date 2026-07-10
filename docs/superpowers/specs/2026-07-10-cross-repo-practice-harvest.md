---
title: "Cross-repo practice harvest (monthly session meta-review)"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-10"
milestone: ""
---

# Cross-repo practice harvest (monthly session meta-review)

## Problem

За последний месяц (2026-06-10 … 2026-07-10) активно работали ~10 lineage проектов:
96 session-md, ~50 уникальных `.claude/rules/*.md`, ~29 per-repo `CLAUDE.md`, 30+
memory-записей. В этом корпусе накопились две категории повторяющихся наработок:

1. **Процессная дисциплина агента** — codex-review, destructive-ops / git-safety,
   autonomous-execution runbook, gates, research/evidence-дисциплина. Кристаллизуется
   в `.claude/rules` и `CLAUDE.md` **по репозиториям**, независимо переизобретается.
2. **Технические пайплайн-паттерны** — extraction / distillation, research-intake,
   two-gate verdict, validation-library, batch-telemetry. Живут в per-repo specs/plans
   и session `what-done`.

Обе категории застряли на **уровне репозитория**. Нет прохода, который поднимал бы
повторяющиеся, домен-независимые практики на **системный уровень** (сначала —
`docs/standards/` гайдбуки; код/скиллы — отложенная вторая стадия).

Этот документ — спека **методологии такого прохода** (не его исполнение). Пошаговый
implementation-план даёт следующий шаг (writing-plans).

## Goal & non-goals

**Goal.** Детерминированно собрать golden-source корпус за окно, извлечь кандидатов
в двух треках, оценить каждого по двум осям (recurrence × domain-independence),
сверить с существующими стандартами и выдать **реестр находок + предложения
гайдбуков** в `docs/standards/`.

**Non-goals (этой стадии).**
- Не писать/рефакторить shared lib или h2t-core скиллы — только тегировать как `deferred`.
- Не копать сырые JSONL-транскрипты (1622 шт) — только уже закристаллизованный слой.
- Не тащить тяжёлый аппарат evidence-grounded-synthesis (маркеры, render-source,
  гейты G1–G4, дуал-судьи) — здесь факты проверяемы, риск фабрикации ≈0.

## Approach

Гибрид: **детерминированный Python-агрегатор** (без LLM) собирает корпус с привязкой
к файлам-источникам → компактный индекс → **синтез в один прямой проход**. Корпус ≈
несколько сотен КБ — Workflow/fan-out не нужен, cost-gate не задеваем.

Отклонённые альтернативы:
- **A. Ручной синтез в треде** — читать 96 md вручную: тяжело по контексту, дрейф.
- **B. Fan-out субагентами** — упирается в cost-gate, избыточно для малого корпуса.

Опора на *принципы* `docs/standards/evidence-grounded-synthesis.md` (truth-слой владеет
фактами, LLM — только интерпретация паттернов), но в **облегчённом** виде (см. §5).

## Design

### 1. Корпус и нормализация (truth-слой, скрипт)

Источники в окне `[2026-06-10 … 2026-07-10]`:

| Источник | Путь | Роль |
|---|---|---|
| Session records | `~/.h2t/sessions/**/<project>/*.md` | что делали (оба трека) |
| Per-repo rules | `<repo>/.claude/rules/*.md` | процессный трек |
| Per-repo CLAUDE.md | `<repo>/CLAUDE.md` | процессный трек |
| Memory | `~/.claude/projects/*/memory/*.md` | оба трека (feedback/reference) |
| Specs/plans | `<repo>/docs/superpowers/{specs,plans}/*.md` | технический трек |

**Обязательная нормализация до любого подсчёта:**

- **Fork/worktree collapse → canonical lineage.** `crypto-regime-spike` ≡ `-dmde` ≡
  `-test`; все `h2t-skills*/.worktrees/**`, `.claude/worktrees/agent-*`,
  `h2t-skills-119-editorial-pilot`, `h2t-skills-editorial-wireframe` ≡ `h2t-skills`.
  Считать **распознанные lineage, не директории** — иначе клонированные rule-файлы
  выдумают «кросс-репо паттерн» из одного репо ×N. (Это entity-normalization из стандарта.)
- **Исключить `documentation.md`** — синхронный шаблон (docs-sync-labels), не находка;
  повторяется в ~20 репо как артефакт синхронизации, а не как практика.
- **Dedup** rule-файлов: **exact (sha256) + fork-collapse**. Near-dup (MinHash/shingling)
  сознательно отложен — это тяжёлая часть аппарата, которую §5 как раз облегчает; для
  rules/session-корпуса реальные дубли = клоны форков (ловятся exact+collapse). Ввести
  near-dup только если реальный корпус покажет near-дубли (YAGNI). *(уточнено на plan-gate,
  codex 2026-07-10)*

### 2. Два трека извлечения (раздельно)

- **Процессный трек:** `.claude/rules` + `CLAUDE.md` + codex-дисциплина + gates +
  git/destructive-safety.
- **Технический трек:** session `what-done` + `docs/superpowers/{specs,plans}` +
  pipeline-rules (extraction, distillation, research-intake, two-gate, telemetry).

Треки не смешивать в одном реестре-выводе: у них разные целевые дома при подъёме.

### 3. Критерий подъёма — двухосевой

Частота — **инструмент обнаружения, не критерий подъёма**. Каждый кандидат
оценивается по двум осям:

- **Recurrence** — в скольких *canonical lineage* встречается (после §1).
- **Domain-independence** — переносим ли за пределы своего домена (coupling-оценка).

`codex-review` живёт в одном quant-kb, но домен-независим → кандидат на подъём.
Частое, но домен-coupled → не поднимать. Обе оси печатаются в реестре явно.

### 4. Diff против существующих `docs/standards/`

Существующие стандарты (`evidence-grounded-synthesis`, `naming-conventions`, `git-*`,
`code-organization`, `adr-process`, `api-contracts`, `linting`) — база сравнения.
Вердикт по каждому кандидату:

`{ new-standard | append:<file> | skip (already-covered) | deferred:code | deferred:skill }`

(Целевые `docs/standards/` живут в infra-репо `C:/dev/docs`; этот прогон генерит **черновики**
в `docs/reports/proposed-standards/` внутри h2t-skills — перенос в infra вручную оператором.)

Иначе выход наплодит дубли уже существующих гайдбуков.

### 5. Анти-галлюцинация — облегчённая

Факты здесь = «правило X в lineage Y» (проверяемо, риск фабрикации ≈0). Оставить
дешёвые принципы, **убрать** тяжёлый аппарат.

| Оставить | Убрать |
|---|---|
| dedup + fork-collapse (§1) | marker-substitution `{{q:ID}}` |
| source-diversity флаг (практика на 1 lineage ≠ общая) | render-source черновики |
| одна опора-строка (путь-источник) на находку | гейты G1–G4 |
| — | дуал-судьи Opus+Codex |

### 6. Выход стадии

Единый **реестр находок** (машиночитаемый + человекочитаемый) со столбцами:

`practice · track · canonical-lineage-sources · recurrence · domain-independence ·
current-location · lift-verdict`

Плюс, для подтверждённых кандидатов процессного/технического трека — **черновые
предложения гайдбуков** в `docs/standards/` (или append-патчи к существующим).

Кандидаты, чей естественный дом — **код или скилл** (не гайдбук), тегируются
`lift-target: deferred(code|skill)` и остаются в реестре для второй стадии — не выбрасываются.

## Boundaries & risks

- **Видно только закристаллизованное.** Уроки, которые возникли, но не были выписаны
  в rule/handoff/memory, на этой глубине невидимы. JSONL сознательно отложен —
  осознанный компромисс стоимости, зафиксирован здесь.
- **Окно фиксировано** `[2026-06-10 … 2026-07-10]`; практики старше не попадают, если
  не встречаются заново в окне.
- **Fork-collapse — ручной справочник lineage.** Если появится новый форк без записи в
  справочнике — риск инфляции подсчёта; справочник lineage ревьюится оператором до синтеза.

## Deliverables

1. `lib/practice_harvest/` — детерминированный агрегатор корпуса (окно + lineage-collapse
   + exact-dedup) + sealed-валидатор реестра. (Пакет в `lib/`, а не `scripts/` — importable
   под pytest; уточнено на plan-gate.)
2. Реестр находок (`docs/reports/2026-07-10-practice-harvest-registry.{md,json}`).
3. Черновые гайдбуки / append-патчи в `docs/reports/proposed-standards/` (перенос в
   `C:/dev/docs/standards/` — вручную оператором) для подтверждённых кандидатов.
4. `deferred`-список code/skill-кандидатов для стадии 2.

