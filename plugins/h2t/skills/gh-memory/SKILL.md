---
name: gh-memory
description: "GitHub Issues as persistent agent memory. Use to create task issues, track progress across sessions, filter by domain/type, and restore session context. Triggers: 'gh-memory', 'create issue', 'agent task', 'track task'."
compatibility: "Claude Code. Requires: gh CLI authenticated to lichtpfad account."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# gh-memory — GitHub Issues as Agent Memory

**Purpose:** Persistent cross-session memory via `lichtpfad/DOR` GitHub Issues.
Each Issue = one task/decision with full context, progress log, and outcome.

## Taxonomy

Labels come from `context/domains.yaml` — always sync with that file as SSOT.

### domain: labels
| Label | Описание |
|-------|----------|
| `domain:dev` | Dev & Tech (crypto-etl, dor, lms-dev, newsengine) |
| `domain:art` | AV Art & Music (qatalyiqtol, retouch, music, open-calls-art) |
| `domain:photo` | Photography (photo-production, photo-social) |
| `domain:hou2touch` | Hou2Touch бизнес (brand, teaching, lms-product) |
| `domain:learning` | Обучение (ai-mindset-lab, research, self-study) |
| `domain:life` | Life & Admin (taxes, citizenship, logistics) |

> `personal` домен (coaching, health, relationships) — **никогда не в GitHub Issues**.
> Личный контент идёт в `vault/800 Personal/` (gitignored).

### type: labels
| Label | Когда |
|-------|-------|
| `type:feature` | Новая функция / фича |
| `type:bug` | Ошибка, регрессия |
| `type:research` | Исследование, изучение |
| `type:automation` | Скрипт, skill, автоматизация |
| `type:decision` | Фиксация решения для памяти |
| `agent-task` | Задача поставленная/выполненная агентом |

### project: labels (создавать по необходимости)
Значения строго из `context/domains.yaml` поле `id`:
`qatalyiqtol`, `retouch`, `crypto-etl`, `dor`, `hou2touch-brand`, `hou2touch-teaching`,
`lms-dev`, `lms-product`, `music`, `photo-production`, `ai-mindset-lab` и др.

---

## Команды

### Создать задачу
```bash
gh issue create --repo lichtpfad/DOR \
  --title "[qatalyiqtol] Описание задачи" \
  --body "Контекст: что, почему, текущее состояние" \
  --label "domain:art,type:feature,agent-task"
```

### Список открытых задач (читать в начале сессии)
```bash
gh issue list --repo lichtpfad/DOR --label "agent-task" --state open
```

### Фильтр по домену
```bash
gh issue list --repo lichtpfad/DOR --label "domain:art" --state open
```

### Добавить прогресс-комментарий
```bash
gh issue comment <number> --repo lichtpfad/DOR \
  --body "Progress: что сделано, что осталось"
```

### Взять задачу в работу (state machine)
```bash
gh issue edit <number> --repo lichtpfad/DOR --add-label "in-progress"
```

### Закрыть задачу
```bash
gh issue close <number> --repo lichtpfad/DOR \
  --comment "Done: итог"
gh issue edit <number> --repo lichtpfad/DOR --remove-label "in-progress"
```

### Найти по ключевому слову
```bash
gh issue list --repo lichtpfad/DOR --search "<keyword>" --state all
```

### Восстановить контекст сессии
```bash
gh issue view <number> --repo lichtpfad/DOR --comments
```

---

## State Machine

```
[open] → add label "in-progress" → [active]
[active] → remove "in-progress" + close → [closed]
[active] → add label "blocked" → [blocked]
```

Hook `session-start-memory.sh` показывает Issues с `in-progress` первыми.

---

## Когда создавать Issue

**Создать:**
- Начало сложной задачи (>30 мин)
- Фиксация важного решения (type:decision)
- Исследование, которое продолжится в следующей сессии

**НЕ создавать:**
- Простые однострочные правки
- Личные/коучинговые темы (→ vault/800 Personal/)
- Дублирование задач уже трекнутых в Notion GTD

---

## Session Start Protocol

```bash
# Читать в начале каждой сложной сессии:
gh issue list --repo lichtpfad/DOR --label "in-progress" --state open
gh issue list --repo lichtpfad/DOR --label "agent-task" --state open --limit 5

# Восстановить контекст:
gh issue view <n> --repo lichtpfad/DOR --comments
```
