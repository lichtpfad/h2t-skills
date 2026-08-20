---
name: gh-memory
description: "Deprecated compatibility shim for old GitHub-Issues-as-memory workflows. Prefer h2t-core:session-start and h2t-core:handoff for session continuity; prefer project GitHub issues for real task state."
compatibility: "Claude Code. Requires: gh CLI authenticated to the target GitHub account."
status: deprecated
metadata:
  author: lichtpfad
  version: 1.0.1
---

# gh-memory — Deprecated Compatibility Shim

`gh-memory` is deprecated as agent memory.

Use instead:

- `h2t-core:session-start` for bounded session context.
- `h2t-core:handoff` for confirmed session summary and live GitHub what-remains.
- Project-local GitHub issues for task truth.
- POS later for accepted long-term session/project memory.

This skill remains only as a compatibility shim for old workflows that stored
agent tasks in `lichtpfad/DOR` issues. Do not use it for new Lifecycle OS work.

## Legacy Commands

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
