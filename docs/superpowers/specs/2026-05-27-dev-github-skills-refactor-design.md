---
title: "Project Lifecycle OS — Skills Refactor: Docs, GitHub, Project Management"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-27"
milestone: "skills-release"
related: ["docs/superpowers/specs/docs-skills-v2.md"]
---

# Project Lifecycle OS — Skills Refactor

## Переосмысление (2026-05-27)

Задача шире чем "починить docs скиллы". По аналогии с подходом Andrej Karpathy к
personal OS — h2t должен вести проект по всему жизненному циклу:

```
Создать → Зарегистрировать → Спланировать → Выполнить → Поддерживать → Закрыть
```

**PM-бэкенд сейчас — GitHub.** Notion / Linear — будущее рассмотрение, не scope этого рефакторинга.
Даже нетехнические проекты идут через GitHub уже сейчас.

**Что это значит для текущих скиллов:**
- Они не "docs утилиты" — они фазы lifecycle
- Один вход на каждую фазу вместо 13 разрозненных скиллов

---

---

## Контекст

### Pre-release audit (2026-05-27)

Обнаружено 13 скиллов в h2t-dev + h2t-core, которые частично дублируют друг друга или
должны быть шагами пайплайна, а не самостоятельными скиллами.

**Legacy Plugin (h2t) — статус:**
Все скиллы из legacy плагина учтены:
- `calendar`, `gmail`, `notion`, `telegram`, `drive` → покрыты `h2t-ops:connectors` ✅
- `ceo-council` → перенесён в `creative-thinking` ✅
- `session-name`, `ctx-load` → намеренно удалены (superseded session-start) ✅
- `h2t` плагин снят с инсталляции ✅

Потерь нет.

---

## Текущий инвентарь

### h2t-dev (9 скиллов)

| Скилл | Назначение |
|-------|-----------|
| `docs-init` | Scaffold стандартной `docs/` структуры (one-time) |
| `docs-lint` | Compliance-чек frontmatter и структуры |
| `docs-index` | Rebuild `docs/README.md` индекса |
| `docs-cleanup` | Архивирование stale plans/specs после milestone |
| `docs-sync-labels` | Синхронизация GitHub labels из labels.json |
| `github-issues` | Создание/обновление issues по шаблону |
| `gh-memory` | GitHub Issues (DOR) как persistent agent memory |
| `milestone-closure` | Checklist закрытия milestone |
| `pre-merge-check` | Quality gate перед merge |

### h2t-core (5 скиллов)

| Скилл | Назначение |
|-------|-----------|
| `scaffold-project` | Wizard создания нового проекта |
| `init-project` | Регистрация существующего репо в h2t |
| `setup` | Install/repair/update h2t tooling |
| `project-audit` | 5-stage deep audit (SCAN→COUNCIL→JUDGE→DOCS→REPORT) |
| `session-start` | Session context gather (не в scope этого рефакторинга) |

---

## Research Findings (2026-05-27)

### Karpathy llm-wiki pattern
LLM не просто индексирует документы — он **компилирует и поддерживает живую wiki**:
интегрирует новые источники в существующую структуру, обновляет перекрёстные ссылки,
фиксирует противоречия. "Compile once, keep current" vs "re-derive on every query".
→ **Применимо к docs/**: не пересоздавать README каждый раз, а инкрементально обновлять.

### HELM (guntherb7/helm) — самый близкий паттерн
> "Tracking should be a byproduct of working, not a separate activity."

- **SessionEnd hook** автоматически обновляет статус проекта при закрытии сессии
- `/new-project` = scaffold + ops file + repo + hooks + GitHub + repo-map entry — **всё одной командой**
- Утреннее standup читает данные из реального состояния проектов, не вручную написанных заметок

### Claude Hangar
- `registry.json`: project → stack → template → config
- 4 project templates, каждый устанавливает правильные hooks и CLAUDE.md
- 13 lifecycle hooks, thin wrappers вызывают скрипты

### Right Hooks
- Auto-detect project type → устанавливает правильный набор hooks
- Per-profile gate intensity: **Strict / Standard / Light**
- `.right-hooks/skills.json` конфигурирует какой скилл вызывать на каком гейте

### Выводы для h2t
1. Scaffold = одна команда, поглощает всё (docs, labels, hooks, registration)
2. Hooks — thin wrappers на plugin scripts; обновляются автоматически с плагином
3. Project template = конфиг для всего (docs dirs, hooks set, gate intensity)
4. Maintenance — byproduct: SessionEnd hook проверяет milestone, docs freshness
5. LLM gate нужен только там где нужно суждение; всё детерминированное — CLI

---

## Архитектурный принцип

```
CLI  →  LLM gate  →  CLI  →  ...
```

- **CLI** — детерминированные операции: scaffold, git mv, label sync, lint, index
- **LLM gate** — суждения: что нарушено, что делать, подтверждение перед действием
- **Skill** — тонкий оркестратор: вызывает CLI, передаёт вывод в LLM, принимает решение

Максимум логики в CLI-скриптах (тестируемо, быстро, без LLM-токенов).
Минимум скиллов — каждый = одна lifecycle-фаза.

---

## Целевая архитектура

### Пайплайн 1: Новый проект (one-time setup)

```
scaffold-project
  ├── [step] docs-init     ← поглощается
  └── [step] docs-sync-labels  ← поглощается
      └── init-project
```

`docs-init` и `docs-sync-labels` становятся **шагами** `scaffold-project`, а не
самостоятельными скиллами. Вызов вручную остаётся через `h2t-dev:docs-init` / `h2t-dev:docs-sync-labels`
для существующих репо (repair/update).

### Пайплайн 2: Milestone closure

```
milestone-closure
  ├── [step] docs-cleanup  ← поглощается
  └── [step] docs-index    ← поглощается
```

`docs-cleanup` и `docs-index` вызываются автоматически как финальные шаги milestone-closure.
Остаются доступны ad-hoc.

### Пайплайн 3: PR / merge

```
pre-merge-check → (merge)
```

Самодостаточный, ничего не поглощает.

### Standalone скиллы (остаются)

| Скилл | Обоснование |
|-------|------------|
| `docs-lint` | Ядро compliance; расширяется in-place (не заменяется новым скиллом) |
| `github-issues` | Создание/обновление issues |
| `gh-memory` | **deprecated** — bridge до gbrain; не инвестировать |
| `project-audit` | Periodic deep audit — не milestone-driven |
| `setup` | Tooling install/repair; **также устанавливает `latest/` symlink** |
| `init-project` | Регистрация существующих репо (граница с scaffold: scaffold = новый проект, init = существующий) |

---

## Улучшения docs-lint (из docs-skills-v2.md)

Текущие проверки:
- Frontmatter наличие и корректность (`--fix-frontmatter`)
- ADR naming
- `--all` / auto-detect cwd

**Добавить:**

| Проверка | Описание |
|----------|----------|
| Legacy dirs | `docs/plans/`, `docs/specs/`, `docs/handoff/`, `docs/eval/` → warn |
| Naming | Specs без даты, plans с датой `YYYY-MM-DD` |
| Repo root | Нет `temp/`, `old/`, `backup/`; корень ≤ 10 элементов |
| data/ vs docs/ | JSON/YAML в docs/ → warn; Markdown в data/ → warn |

Whitelist нестандартных dirs:
```python
REPO_EXTRA_DIRS = {
    "h2t-evals":         ["ops", "contracts"],
    "h2t-transcription": ["methodology", "diagrams"],
    "h2t-vision":        ["presentation"],
}
```

## Улучшения docs-index (из docs-skills-v2.md)

**Один скрипт** — вызывается и из milestone-closure и ad-hoc. P3 rewrite меняет шаблон вывода для обоих.

Текущая проблема: генерирует инвентарь файлов вместо навигационного индекса.

Новый формат `docs/README.md`:
```markdown
# {Repo} Documentation

## Quick Links

| Section | Description |
|---------|-------------|
| [Specs & Plans](superpowers/) | Design specs and implementation plans |
| [ADRs](adr/) | Architectural decisions |
| [Reports](reports/) | Milestone reports |
# + conditional если папка существует

## Architecture Decisions

| # | Title | Status | Date |
```

---

## Scope этого рефакторинга

**В scope:**
- Добавить шаги docs-init + docs-sync-labels в scaffold-project
- Добавить шаги docs-cleanup + docs-index в milestone-closure
- Расширить docs-lint новыми проверками
- Переписать docs-index под navigation template

**Не в scope:**
- Автоматическое переименование существующих specs
- Миграция `docs/eval/` из h2t-ai (repo-specific)
- Содержательная проверка docs (vale/pymarkdownlnt)
- `node-researcher` / arch pipeline (отдельный трек)

---

## Что куда: CLI / Skill / Hook / Config

| Слой | Назначение | Примеры |
|------|-----------|---------|
| **CLI script** | Детерминированные операции, тестируемо, без LLM | scaffold_project.py, lint.py, cleanup.py, index.py, sync_labels.py |
| **Skill** | Оркестрация + LLM gate: вызов CLI → интерпретация → решение | scaffold-project, milestone-closure, docs, pre-merge-check |
| **Hook (thin wrapper)** | Автоматический триггер без диалога; вызывает plugin script | on-stop.py (check milestone), on-commit.py (lint changed .md) |
| **Config / template** | Декларативный выбор набора поведений для типа проекта | project templates, gate profiles |

### Правило разделения

```
Можно ли принять решение без LLM?
  Да → CLI script (+ hook если автоматический)
  Нет → LLM gate в skill

Нужен ли диалог с пользователем?
  Нет → hook (silent, byproduct)
  Да → skill
```

---

## Project Templates

`scaffold-project` выбирает шаблон → разные наборы dirs, hooks, labels, PM-настройки.

| Template | Описание | PM | Docs extras |
|----------|----------|----|-------------|
| `python-lib` | Библиотека / пакет | GitHub | api/, guides/ |
| `python-service` | Backend-сервис с deploy | GitHub | architecture/, ops/ |
| `skill-pack` | Claude Code плагин | GitHub | — |
| `research` | Исследовательский / нетехнический | GitHub / Notion | research/ |
| `creative` | AV / медиа проект | GitHub | — |

Шаблон — дополнительный слой поверх существующих типов scaffold (`code-github`, `code-local`, `docs`, `dcc`).
Существующие зарегистрированные проекты не затрагиваются — шаблон применяется только при новом scaffold.

Шаблон определяет:
- Какие `docs/` директории создать
- Какие labels синхронизировать
- Какие hooks установить в `.claude/settings.json`

---

## Hooks как часть lifecycle

Часть lifecycle-задач должна выполняться **автоматически через хуки**, а не только по явному вызову скилла.

| Хук | Событие | Действие |
|-----|---------|----------|
| `PostToolUse: Bash(git commit)` | После коммита с .md файлами | docs-lint quick check — **non-blocking, timeout 5s, только если changed files в docs/** |
| `Stop` (session end) | Конец сессии | Проверить: все milestone issues закрыты? → предложить milestone-closure |
| `PostToolUse: Bash(git push)` | После push в main | Обновить docs-index |
| `PreToolUse: Bash(git merge)` | Перед merge | pre-merge-check gate |

**Принцип разделения skill vs hook:**
- **Skill** — когда нужен диалог, подтверждение, LLM-суждение
- **Hook** — когда действие детерминировано и не требует диалога (CLI-only или предупреждение)

Hooks живут в `.claude/settings.json` проекта — устанавливаются шаблоном при scaffold.

### Hook update strategy: thin wrapper pattern

Hook в `settings.json` не содержит логики — только вызов скрипта из plugin cache:

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "",
      "command": "python ~/.h2t/venv/Scripts/python.exe ~/.claude/plugins/cache/lichtpfad/h2t-core/latest/scripts/hooks/on-stop.py --cwd $PWD"
    }]
  }
}
```

- Логика живёт в плагине (`h2t-core/scripts/hooks/`)
- Плагин обновился → все проекты автоматически получают новое поведение
- В `settings.json` ничего менять не нужно после scaffold
- `latest/` — symlink (Linux/Mac) или junction (Windows, не требует прав) на текущую версию плагина
- **`h2t-core:setup` обязан создавать/обновлять `latest/`** — это часть install pipeline, добавить в приоритеты
- Fallback если `latest/` нет: `setup` пишет `~/.h2t/config/plugin-versions.json` → hook резолвит путь через него

---

## Закрытые решения

| Вопрос | Решение |
|--------|---------|
| docs-init / docs-sync-labels standalone? | Да, остаются для repair существующих репо; автовызов из scaffold |
| docs-sync-labels из lint? | Да — `docs-lint --fix` запускает sync-labels если labels расходятся |
| docs-cleanup в milestone-closure | Обязательный шаг с dry-run preview перед выполнением |
| repo-audit отдельный скилл? | Нет — расширить docs-lint флагом `--repo-root` |
| gh-memory | Deprecated; bridge до gbrain; не инвестировать |

---

## Финальный инвентарь (целевой)

### Скиллы (целевой список)

| Скилл | Фаза | Поглощает |
|-------|------|-----------|
| `scaffold-project` (h2t-core) | INIT | docs-init + docs-sync-labels + hook install |
| `github-issues` (h2t-dev) | PLAN | — |
| `docs-lint` (h2t-dev, расширенный in-place) | MAINTAIN | repo-root check; `--fix` → sync-labels |
| `pre-merge-check` (h2t-dev) | REVIEW | — |
| `milestone-closure` (h2t-dev) | CLOSE | docs-cleanup + docs-index |
| `project-audit` (h2t-core) | AUDIT | — |
| `gh-memory` (h2t-dev) | — | **deprecated** |

### Standalone CLI (вызываемые вручную или из scaffold/lint)
`docs-init`, `docs-sync-labels` — остаются как repair-инструменты для существующих репо.

### Hooks (thin wrapper → plugin script)

| Hook | Триггер | Действие |
|------|---------|----------|
| `Stop` | Конец сессии | Проверить milestone completeness → предложить closure |
| `PostToolUse: Bash(git commit)` | После коммита | docs-lint на изменённые .md |
| `PreToolUse: Bash(git merge)` | Перед merge в main | pre-merge-check gate |

---

## Приоритеты реализации

| P | Задача |
|---|--------|
| P0 | Расширить `docs-lint`: legacy dirs, repo-root check, `--fix` → sync-labels |
| P1 | `h2t-core:setup`: создавать `latest/` junction/symlink + `plugin-versions.json` fallback |
| P1 | `scaffold-project`: поглотить docs-init + docs-sync-labels + hook install (thin wrappers) |
| P1 | `milestone-closure`: добавить шаги docs-cleanup + docs-index (с dry-run gate) |
| P2 | Hook `Stop`: non-blocking milestone completeness check → предложить closure |
| P2 | Hook `PostToolUse(git commit)`: non-blocking docs-lint на изменённые docs/*.md, timeout 5s |
| P3 | `docs-index`: переписать под navigation template (один скрипт, два вызывателя) |
| P3 | Пометить `gh-memory` deprecated в plugin.json |
