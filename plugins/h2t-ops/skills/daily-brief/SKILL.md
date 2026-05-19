---
name: daily-brief
description: "Morning briefing aggregating Google Calendar, Gmail, and Notion tasks into a daily plan. Triggers: 'daily brief', 'briefing', 'утренний брифинг', 'что сегодня', 'план на день', 'h2t:daily-brief'"
compatibility: "Requires Google OAuth + NOTION_API_TOKEN. Gmail, calendar, notion must be working."
metadata:
  author: lichtpfad
  version: 2.0.0
---

# Daily Brief

## POS Boundary

Daily Brief is a read and synthesis workflow, not the POS journal writer. Follow
`../../references/pos-operational-boundary.md`: route decisions, tasks, lessons,
and follow-ups through POS journal commands once available. Until then, emit
structured proposed captures instead of mutating stores.

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/lib/cli/main.py"
TASKS_DB="beabac7bf4314952a9327759c638d89f"
```

## Шаги

### Step 1: Собери данные

Запусти последовательно — ошибка одного источника не блокирует остальные:

```bash
# События на сегодня и завтра
$CLI ingest calendar list --days 2 --json

# Важные непрочитанные письма
$CLI ingest gmail list --unread --query "is:important" --max 15 --json

# Активные задачи Notion
$CLI ingest notion search $TASKS_DB --filter-json '{"property":"Status","status":{"does_not_equal":"Done"}}' --limit 30 --json
```

### Step 2: Сформируй брифинг по доменам

Сгруппируй события/письма/задачи по ключевым словам:

- **🎨 Art & Culture** — art, museum, gallery, exhibition, QATAL, curator, ANU, Mamuta, Zilberman, Bezalel, AICF
- **💻 Development** — GitHub, PR, code, deploy, project, API, tech
- **📚 Education** — course, teaching, students, workshop, lecture
- **👤 Personal** — всё остальное

### Step 3: Добавь секцию ⚡ Priority Actions

Приоритеты (HIGH/MED/LOW):
- **HIGH**: события сегодня + задачи S/Action + письма с дедлайнами
- **MED**: задачи S/Next Action + важные письма без дедлайна
- **LOW**: фоновые задачи

### Step 4: Покажи брифинг

Формат:

```
# Daily Brief — YYYY-MM-DD

## 📅 Сегодня (N событий)
...

## 📧 Gmail (N важных непрочитанных)
...

## ✅ Tasks (N активных)
...

## ⚡ Priority Actions
### HIGH
...
### MED
...
```

## Обработка ошибок

- **Calendar/Gmail**: проверь токены — `~/.config/google-calendar-mcp/tokens.json`
- **Notion**: проверь `NOTION_API_TOKEN` в `~/.dor/secrets.env`
- Если источник недоступен — пропусти его и укажи в брифинге `⚠️ <source> unavailable`
