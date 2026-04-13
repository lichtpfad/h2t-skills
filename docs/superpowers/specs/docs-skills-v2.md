---
title: "Docs & Repo Management Skills v2"
status: "draft"
owner: "lichtpfad"
date: "2026-04-14"
---

# Docs & Repo Management Skills v2

## Context

Текущие docs skills (Phase 7, M2) работают, но опираются на устаревшие соглашения. По итогам research выявлены три проблемы:

1. **Структура docs** — стандарт `documentation-structure.md` гранфазерил ошибки (handoff/, eval/ в docs/, registry/ в docs/ вместо data/)
2. **Lifecycle docs** — нет правил для completed specs/plans; docs-cleanup слишком узкий
3. **Repo root** — нет аудита структуры корня репо; зоопарк в нескольких репо

---

## Принципы (из research)

### Docs Lifecycle

| Тип | Правило |
|-----|---------|
| Completed milestone plans | `git mv` в `docs/archive/plans/` |
| Completed specs | `status: implemented` в frontmatter, остаются на месте |
| Reports | всегда в `docs/reports/`, неизменны |
| ADR | статус меняется (superseded), файл не трогается |
| `git rm` без перемещения | **запрещено** — потеря контекста |
| Git history как единственный архив | **недостаточно** — friction слишком высок |

### Naming Conventions

| Тип файла | Формат | Пример |
|-----------|--------|--------|
| Specs | `YYYY-MM-DD-mN-kebab.md` | `2026-04-14-m2-graph-query-api.md` |
| Plans | `YYYY-MM-DD-mN-kebab.md` | `2026-04-14-m11-consumer-plan.md` |
| ADR | `NNNN-kebab-case.md` | `0003-use-sqlite.md` |
| Reports | `mN-topic-report.md` | `m8-ground-truth-report.md` |

**Rationale:** Дата + milestone в имени файла — сразу виден контекст из `ls`. Workflow: GitHub issues → milestone → brainstorming → specs/plans с `YYYY-MM-DD-mN-` префиксом. ADR нумеруются порядково (не по дате). Reports идентифицируются по milestone, не по дате.

### Agent Context

- Старые completed specs = шум в контексте (context rot)
- Агент читает: CLAUDE.md + активные планы + reports (сжатый контекст)
- Progressive disclosure: минимум в контексте, детали по Read tool
- Архив нужен для людей, не для агентов (agents читают `status: implemented` и пропускают)

---

## Правильная структура docs/

```
docs/
  README.md                    # Navigation index (Quick Links на директории)
  superpowers/
    specs/                     # Живые спецификации (kebab-case.md, без даты)
    plans/                     # Планы с датой (YYYY-MM-DD-kebab.md)
  adr/                         # NNNN-kebab.md + index.md
  reports/                     # Milestone reports (immutable)
  archive/
    plans/                     # Выполненные планы (git mv из superpowers/plans/)
  # Conditional (только если применимо):
  product/                     # projects.yaml.docs.positioning = true
  client/                      # repo exposes public API
  architecture/                # complex internal arch
  guides/                      # external users / onboarding
  research/                    # exploratory work (YYYY-MM-DD-topic.md)
  marketing/                   # projects.yaml.docs.marketing_docs = true
  # Repo-specific extensions (документированы в docs/README.md):
  # h2t-evals: ops/, contracts/
  # h2t-transcription: methodology/, diagrams/
```

**Что НЕ должно быть в docs/:**

| Папка | Куда переносить |
|-------|----------------|
| `docs/handoff/` | `.dor/sessions/` (уже там) — удалить |
| `docs/eval/` | переехало в h2t-evals — удалить из h2t-ai |
| `docs/registry/` | `data/` (машиночитаемое) |
| `docs/context7-cache/` | `.cache/` или gitignore |
| `docs/plans/` | `docs/superpowers/plans/` или `docs/archive/plans/` |
| `docs/specs/` | `docs/superpowers/specs/` |
| `docs/integration/`, `docs/graph/` | аудит: docs или data? |

---

## Правильная структура repo root

```
README.md
LICENSE
pyproject.toml               # единая точка конфигурации
.gitignore
.env.example
CLAUDE.md                    # инструкции для агентов
.claude/                     # Claude Code settings, rules, hooks

src/                         # importable code (src-layout)
tests/
docs/
scripts/                     # user-facing CLI скрипты (не importable)
data/                        # machine-readable: реестры, датасеты, JSON schemas
config/                      # env-specific конфиги (не secrets)
```

**data/ vs docs/ граница:**
- `data/` — читает код программно (JSON, YAML, CSV)
- `docs/` — читает человек или агент (Markdown)

**Антипаттерны в корне:**
- `utils.py`, `helpers.py` в корне
- `temp/`, `old/`, `backup/` папки
- данные (`.json`, `.csv`) прямо в корне
- Корень репо > 10 элементов

---

## Skills: что нужно изменить

### docs-lint (расширить)

**Добавить проверки:**
- Нестандартные top-level папки в `docs/` (не в whitelist)
- Legacy dirs: `docs/plans/`, `docs/specs/`, `docs/handoff/`, `docs/eval/`
- Naming: specs без даты, plans с датой `YYYY-MM-DD`
- Корень репо: нет `temp/`, `old/`, `backup/`; корень ≤ 10 элементов

**Уже есть:**
- `--fix-frontmatter` (добавлен в текущей сессии)
- `--all` / auto-detect cwd
- ADR naming check

**Whitelist нестандартных dirs (по репо):**
```python
REPO_EXTRA_DIRS = {
    "h2t-evals": ["ops", "contracts"],
    "h2t-transcription": ["methodology", "diagrams"],
    "h2t-vision": ["presentation"],
}
```

### docs-cleanup (расширить)

**Добавить:**
- `--legacy-dirs` — архивирует `docs/plans/`, `docs/specs/`, `docs/handoff/` через `git mv`
- `--migrate-data` — перемещает `docs/registry/` → `data/registry/` через `git mv`
- Репорт legacy dirs в dry-run без флагов

**Уже есть:**
- Архивирование stale plans (>30 дней) из `docs/superpowers/plans/`
- Архивирование specs со `status: implemented`

### docs-index (переписать)

**Текущая проблема:** генерирует инвентарь файлов, а стандарт требует навигационный индекс.

**Новый формат `docs/README.md`:**
```markdown
# {Repo} Documentation

## Overview
{one paragraph — либо из projects.yaml, либо placeholder}

## Quick Links

| Section | Description |
|---------|-------------|
| [Specs & Plans](superpowers/) | Design specs and implementation plans |
| [ADRs](adr/) | Architectural decisions |
| [Reports](reports/) | Milestone reports |
# + conditional если папка существует:
| [Product](product/) | Positioning, scope |
| [Architecture](architecture/) | Technical design |
| [Research](research/) | Research documents |

## Architecture Decisions

| # | Title | Status | Date |
|---|-------|--------|------|
| 1 | [Title](adr/0001-...) | accepted | 2026-01-01 |
```

**Логика:**
- Quick Links — всегда, для директорий которые существуют
- ADR table — всегда (high signal для агентов)
- Specs/Plans/Reports detail — опционально, `--detailed`

### docs-init (обновить)

**Изменить:**
- Генерировать `docs/README.md` по новому шаблону (Quick Links)
- Учитывать `REPO_EXTRA_DIRS` при генерации
- Не создавать `docs/plans/`, `docs/specs/` (legacy)

### NEW: repo-audit skill

**Назначение:** аудит структуры корня репо и всего docs/

**Проверяет:**
- Корень ≤ 10 элементов
- Нет `temp/`, `old/`, `backup/` в корне
- `data/` vs `docs/` misplacement (JSON в docs/, Markdown в data/)
- `src/` layout если Python проект (не flat)
- Наличие `CLAUDE.md`, `pyproject.toml`

**Output:** список нарушений + suggested fixes

---

## Приоритеты

| Приоритет | Задача |
|-----------|--------|
| P0 | Обновить `documentation-structure.md` — убрать ошибочные исключения |
| P1 | `docs-lint`: добавить legacy dirs check + naming check |
| P1 | `docs-cleanup`: добавить `--legacy-dirs` и `--migrate-data` |
| P2 | `docs-index`: переписать под navigation template |
| P2 | `docs-init`: обновить шаблон README |
| P3 | `repo-audit`: новый скилл |

---

## Что НЕ входит в scope

- Автоматическое переименование существующих specs (добавление/удаление дат) — ручная операция
- Миграция `docs/eval/` из h2t-ai (специфика одного репо, не скилл)
- Проверка содержимого docs (это для vale/pymarkdownlnt)
