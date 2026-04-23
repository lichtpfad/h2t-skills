---
title: "H2T Skill Architecture Vision"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-03-30"
milestone: ""
---
# H2T Skill Architecture Vision

## Принцип

Каждый организационный скилл — три слоя:

| Слой | Где живёт | Что делает | Кто |
|------|-----------|------------|-----|
| **L1: Interface scripts** | Python модули в `lib/` | Получение и запись данных через API/CLI | Скрипт, без LLM |
| **L2: CLI утилита** | `h2t <command>` | Единая точка входа, роутинг, форматирование | Скрипт, без LLM |
| **L3: Skill** | SKILL.md + hook | Интерпретация, приоритизация, решения с пользователем | LLM |

**Ключевой принцип:** L1 и L2 работают без Claude. Человек может вызвать `h2t gmail inbox` из терминала. LLM нужен только для L3 — там, где нужен интеллект: отобрать из 50 писем 5 важных, из 15 issues предложить что делать, из handoff + context решить направление сессии.

**Hook** — мост между L2 и L3. PreToolUse → вызывает `h2t gather <skill>` → инжектит результат в systemMessage → SKILL.md получает готовые данные.

---

## Анализ всех 26 скиллов

### Подходит модели (Data → LLM interpretation)

Скиллы где L1/L2 собирают данные, а L3 (LLM) интерпретирует.

| Skill | L1: Scripts | L2: CLI | L3: LLM intelligence | Текущее состояние |
|-------|-------------|---------|----------------------|-------------------|
| **dev-session-start** | gather.py → git, github, stack, sessions | `h2t gather session-start` | Приоритизация issues, предложение направления, session naming | ✅ L1 есть, L2 частично (hook), L3 variant C |
| **daily-brief** | calendar_cli.py, gmail_cli.py, notion tasks | `h2t brief` | Из calendar+gmail+notion → план дня, приоритеты | ⚠️ L1 есть (скрипты), L2 нет, L3 в SKILL.md |
| **handoff** | gather.py → git, github, sessions | `h2t gather handoff` | Что записать как контекст, что важно для следующей сессии | ⚠️ L1 есть, L2 частично (hook), L3 в SKILL.md |
| **gmail** | gmail_cli.py → fetch/send | `h2t gmail inbox` | Из N писем → показать важные, предложить ответы | ⚠️ L1 есть, L2 нет, L3 в SKILL.md |
| **notion** | notion_cli.py → query/create | `h2t notion tasks` | Фильтрация, приоритизация задач | ⚠️ L1 есть, L2 нет, L3 в SKILL.md |
| **telegram** | telegram_cli.py → fetch | `h2t telegram saved` | Из сообщений → дайджест, задачи | ⚠️ L1 есть, L2 нет, L3 в SKILL.md |
| **dev-overview** | git, github across repos | `h2t overview` | Сводка по всем проектам, прогресс к целям | ❌ Нет L1, всё в SKILL.md |
| **calendar** | calendar_cli.py → events | `h2t calendar today` | Из событий → расписание, конфликты | ⚠️ L1 есть, L2 нет, L3 в SKILL.md |
| **init-project** | detect_project.py → type/domain/tracker | `h2t init` | Confirm с пользователем, выбор домена | ✅ L1 есть, L2 через hook, L3 confirm UI |
| **process-transcripts** | enrichment pipeline | `h2t enrich` | LLM enrichment (summary, outcomes) | ⚠️ L1 есть (pipeline), специфичен |
| **pre-merge-check** | git, tests, build | `h2t check` | Оценка готовности к merge, рекомендации | ❌ Нет L1, всё в SKILL.md |
| **drive** | drive_cli.py → search/download | `h2t drive sync` | Фильтрация, организация файлов | ⚠️ L1 есть, L2 нет |

### Частично подходит (LLM-heavy, но L1 полезен)

| Skill | Почему частично | Что может быть в L1 |
|-------|-----------------|---------------------|
| **github-issues** | LLM генерирует структуру issue, но `gh` вызовы детерминистичны | `h2t issue create --title X --body Y --labels Z` |
| **gh-memory** | Похож на github-issues | `h2t memory create --type task --domain X` |
| **milestone-closure** | LLM решает закрывать ли, но `gh` вызовы детерминистичны | `h2t milestone close --id N` |
| **youtube-transcript** | Скрипт скачивает, LLM не особо нужен | `h2t youtube transcript <URL>` — почти чистый L1 |
| **convert-meeting-transcript** | Скрипт конвертит, LLM для speaker names | `h2t convert <file.docx>` — почти чистый L1 |

### Не подходит модели (Pure generation / Pure LLM)

Скиллы где нет внешних данных — LLM генерирует контент из промпта.

| Skill | Почему | Что они делают |
|-------|--------|----------------|
| **deck** | LLM генерирует HTML презентацию | Нет внешних данных, чистая генерация |
| **design** | LLM применяет HUD design system | Стиль-гайд, чистая генерация |
| **ceo-council** | LLM играет роли советников | Чистый prompting, нет данных |
| **diagram-node** | LLM исследует и документирует | Смешанный: research (L1?) + writing (L3) |
| **node-researcher** | Exa API search + LLM analysis | Research fetch (L1) + analysis (L3) |
| **lesson-parser** | LLM парсит транскрипт в структуру | Input = текст, output = JSON graph |
| **drawio** | Generate + export | Generate = LLM, export = скрипт (уже L1) |
| **nlm** | Guide для NotebookLM CLI | Инструкции, нет скриптов |
| **setup** | Установка venv | Чистый bash, не skill |

---

## Приоритет миграции на трёхслойную архитектуру

### Wave 1: Workflow skills (максимальный ROI)

Скиллы вызываемые каждый день, где manual gather тратит больше всего токенов.

| Skill | Текущие потери | Действие |
|-------|---------------|----------|
| **dev-session-start** | ~15-25k tokens на ручной gather | ✅ В процессе (variant C) |
| **handoff** | ~10k tokens | Добавить briefing-like injection |
| **daily-brief** | ~20k tokens (3 API) | Объединить calendar+gmail+notion в один CLI вызов |

### Wave 2: Data skills (есть готовые скрипты)

| Skill | Действие |
|-------|----------|
| **gmail** | Обернуть gmail_cli.py в `h2t gmail`, hook injection |
| **notion** | Обернуть notion_cli.py в `h2t notion`, hook injection |
| **calendar** | Обернуть calendar_cli.py в `h2t calendar`, hook injection |
| **telegram** | Обернуть telegram_cli.py в `h2t telegram`, hook injection |

### Wave 3: Dev tools

| Skill | Действие |
|-------|----------|
| **pre-merge-check** | Создать L1: run tests, check git status, audit deps |
| **dev-overview** | Создать L1: parallel gather across repos |
| **github-issues** | Создать L1: `h2t issue create/update` |

### Не мигрируются

deck, design, ceo-council, lesson-parser, drawio (generation), nlm, setup — чистый LLM или чистый bash, трёхслойная модель не добавляет ценности.

---

## Целевая архитектура CLI

```
h2t
├── gather
│   ├── session-start   → JSON (project, git, github, stack, sessions)
│   ├── handoff          → JSON (same + session state)
│   ├── daily-brief      → JSON (calendar + gmail + notion)
│   └── overview         → JSON (multi-repo summary)
├── gmail
│   ├── inbox            → JSON (messages)
│   ├── send             → status
│   └── draft            → status
├── notion
│   ├── tasks            → JSON (tasks from DB)
│   ├── create-page      → status
│   └── query            → JSON
├── calendar
│   ├── today            → JSON (events)
│   └── create           → status
├── telegram
│   ├── saved            → JSON (messages)
│   └── digest           → Markdown
├── github
│   ├── issues           → JSON
│   ├── create-issue     → status
│   └── close-milestone  → status
├── init                 → JSON (detection + confirm)
├── check                → JSON (pre-merge results)
└── youtube transcript   → Markdown
```

Каждая команда:
- Принимает args через CLI (argparse)
- Возвращает JSON или Markdown в stdout
- Работает без LLM
- Кроссплатформенная (Windows/Mac)
- Может быть скомпилирована (PyInstaller)

---

## Hook как роутер

```bash
# gather-on-skill (обобщённый)
case "$SKILL_NAME" in
  dev-session-start)  CMD="h2t gather session-start --cwd $cwd" ;;
  handoff)            CMD="h2t gather handoff --cwd $cwd" ;;
  daily-brief)        CMD="h2t gather daily-brief" ;;
  gmail)              CMD="h2t gmail inbox --limit 20" ;;
  notion)             CMD="h2t notion tasks" ;;
  init-project)       CMD="h2t init --cwd $cwd" ;;
  *)                  exit 0 ;;
esac

RESULT=$($CMD 2>/dev/null) || true
# ... inject as systemMessage
```

---

## Гипотезы для проверки

### H1: Hook-injected instructions работают лучше чем SKILL.md
- **Тест:** variant C для dev-session-start
- **Метрика:** Claude показывает BRIEFING verbatim, не запускает manual gather
- **Статус:** ожидает live-тест

### H2: LLM следует позитивным инструкциям по обработке данных
- **Тест:** SKILL.md говорит "из этих 15 issues выбери top-3 по приоритету" (не "не делай X")
- **Метрика:** Claude делает именно это, не добавляет своё
- **Статус:** не проверено

### H3: Единая CLI утилита снижает complexity хуков
- **Тест:** заменить per-skill gather.py на `h2t gather <skill>`
- **Метрика:** hook становится < 20 строк, одинаковый для всех skills
- **Статус:** не реализовано

---

## Не в скоупе этого документа

- Компиляция в бинарник (PyInstaller) — отдельный этап после стабилизации
- Auth management (OAuth refresh, token storage) — #13
- Cross-machine sync — #13
- Notion DB creation — future
