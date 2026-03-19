---
name: calendar
description: "Reads and creates Google Calendar events via OAuth. Use to view schedule, list events, create meetings, or check free time. Triggers: 'calendar', 'schedule', 'events', 'meeting', 'расписание'., 'h2t:calendar'"
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

Когда skill вызывается, выполни соответствующую команду используя Python CLI:

## Переменные

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/calendar_cli.py"
```

## Команды

### 1. Просмотр событий
```bash
$CLI list [days]
```

Параметры:
- `days` - количество дней вперёд (по умолчанию: 1)

Примеры:
- `list` - события на сегодня
- `list 7` - события на неделю
- `list 30` - события на месяц

### 2. Поиск событий
```bash
$CLI search "<query>"
```

Поиск по названию события.

### 3. Создание события
```bash
$CLI create "<summary>" "<YYYY-MM-DD>" "<HH:MM>" [duration_minutes] ["description"]
```

Параметры:
- `summary` - название события (обязательно)
- `date` - дата в формате YYYY-MM-DD (обязательно)
- `time` - время начала HH:MM (обязательно)
- `duration` - длительность в минутах (по умолчанию: 60)
- `description` - описание события с локацией (опционально)

Примеры:
- `create "Встреча" "2026-02-20" "14:00" 60`
- `create "Встреча" "2026-02-20" "14:00" 90 "Location: Office A"`

## Формат даты и времени

- Дата: YYYY-MM-DD (например: 2026-02-20)
- Время: HH:MM в 24-часовом формате (например: 14:00, 09:30)
- Длительность: целое число минут (например: 60, 90, 120)

## Обработка ошибок

Если получена ошибка OAuth/credentials:
1. Проверь наличие `~/.config/google-calendar-mcp/credentials.json`
2. Проверь наличие `~/.config/google-calendar-mcp/tokens.json`
3. Если токен истёк, попроси пользователя переавторизоваться

## Workflow

1. Выполни команду через Bash tool
2. Покажи результат пользователю в читаемом формате
3. При создании события - подтверди успешное создание с ID и ссылкой
