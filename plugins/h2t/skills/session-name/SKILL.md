---
name: session-name
description: Generate session name slug and register session. Use after choosing work direction.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 0.1.0
---

# Инструкции

Зафиксировать имя сессии, запостить GitHub comment, зарегистрировать в registry.

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
```

## Команды

### 1. Определить компоненты slug

```bash
REPO=$(basename $(git remote get-url origin 2>/dev/null | sed 's/\.git$//') 2>/dev/null || basename $(pwd))
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H%M)
```

### 2. Собрать slug

Формат: `{repo}-{task}-{date}-{time}`

- `repo` — короткое имя из git remote
- `task` — 2-4 слова kebab-case из выбранного issue или темы разговора
- `date` — YYYY-MM-DD
- `time` — HHMM

Примеры:
- `h2t-graphs-provenance-enrichment-2026-03-31-0415`
- `agent-skills-briefing-hook-2026-03-31-1430`
- `creative-thinking-llm-judge-evals-2026-03-31-2200`

### 3. Подтвердить с пользователем

```
Имя сессии: `{slug}`
Корректируй если нужно.
```

Дождаться ответа. Сохранить подтверждённое имя как SESSION_NAME.

### 4. Запостить GitHub comment

```bash
SESSION_ID=$(basename $(ls -t ~/.claude/projects/*/$(basename $(pwd))/*.jsonl 2>/dev/null | head -1) .jsonl 2>/dev/null)

gh issue comment {NUMBER} --body "Session: {SESSION_NAME}
Resume: claude --resume ${SESSION_ID}
Handoff: ~/.dor/sessions/{machine}/{repo}/{SESSION_NAME}.md"
```

Если нет конкретного issue — пропустить.

### 5. Зарегистрировать в registry

```bash
REGISTRY_PY="$HOME/.h2t/config/registry/registry.py"
MACHINE="${DOR_MACHINE_NAME:-$(hostname | tr '[:upper:]' '[:lower:]' | cut -d. -f1)}"

if [ -f "$REGISTRY_PY" ] && [ -n "$SESSION_ID" ]; then
  $H2T_PYTHON "$REGISTRY_PY" append --id "$SESSION_ID" --cwd "$(pwd)" --host "$MACHINE"
  $H2T_PYTHON "$REGISTRY_PY" update \
    --id "$SESSION_ID" \
    --status "active" \
    --session-name "{SESSION_NAME}" \
    --topic "{тема}" \
    --task-issue "#{NUMBER}" \
    --task-title "{title}"
fi
```

Если registry.py не найден — пропустить молча.
