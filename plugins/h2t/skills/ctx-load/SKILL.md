---
name: ctx-load
description: Process and display data from system messages.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 0.3.0
---

# Инструкции

Когда skill вызывается, собери данные через CLI и покажи результат.

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t:setup" && exit 1

GATHER="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/../dev-session-start/scripts/gather.py"
```

## Команды

### 1. Собрать данные
```bash
$GATHER --cwd "$(pwd)" --format-briefing
```

Возвращает JSON с полями:
- `_briefing` — готовый markdown для показа пользователю
- `_meta.slug_template` — шаблон имени сессии
- `project`, `git`, `github`, `stack`, `sessions`, `machine`

### 2. Показать результат

Из JSON возьми поле `_briefing` и покажи пользователю AS-IS.

### 3. Предложить направление

После показа briefing, предложи имя сессии и направление:

```
Предлагаю имя сессии: `{slug_template с заполненным {task}}`
Направление: #{номер} {title}
Корректируй если нужно.
```

Заполни `{task}` на основе top-priority issue (2-4 слова, kebab-case).
