---
name: h2t-ops:calendar
description: "Reads and creates Google Calendar events via OAuth. Use to view schedule, list events, create meetings, or check free time. Triggers: 'calendar', 'schedule', 'events', 'meeting', 'расписание', 'h2t:calendar'"
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Calendar

## POS Boundary

For POS and daily-loop workflows, follow the shared boundary reference:
`../../references/pos-operational-boundary.md`. This skill may read Calendar
data through connector tooling, but must not write POS journal rows, mutate
`~/.dor/pos.db`, or modify vault/lake directly. Emit structured proposed
captures until POS journal commands exist.

## Переменные

```bash
CLI="h2t-ops calendar"
```

## Команды

### Просмотр событий
```bash
$CLI list [--days N] [--from YYYY-MM-DD --to YYYY-MM-DD] [--tz TZ] [--max N] [--busy-only] [--json]
```

- `--days 1` — события на сегодня (по умолчанию)
- `--days 7` — события на неделю
- `--from ... --to ...` — явное окно дат; `--to` включительно для пользователя
- `--tz Asia/Jerusalem` — timezone для date-window; fallback: `H2T_CALENDAR_TZ`, затем `Asia/Jerusalem`
- `--busy-only` — скрыть transparent/free события
- `--max 250` — безопасный дефолт, чтобы не терять насыщенные дни

### Поиск событий
```bash
$CLI search "<query>" [--max N] [--json]
```

### Создание события
```bash
$CLI create "<summary>" <YYYY-MM-DD> <HH:MM> [--duration N] [--description "..."] [--attendees "a@b.com,c@d.com"] [--tz "Asia/Jerusalem"]
```

Примеры:
```bash
$CLI create "Встреча" 2026-04-10 14:00 --duration 60
$CLI create "Встреча" 2026-04-10 14:00 --duration 90 --description "Важная встреча"
```

### Удаление события
```bash
$CLI delete <event-id> [--confirm]
```

Без `--confirm` показывает детали события. С `--confirm` удаляет.

### Получение события
```bash
$CLI get <event-id>
```

## Workflow

1. Выполни команду через Bash tool
2. Покажи результат пользователю
3. При создании — подтверди создание с ID и ссылкой

## Обработка ошибок

OAuth ошибка:
1. Проверь `~/.config/google-calendar-mcp/credentials.json`
2. Проверь `~/.config/google-calendar-mcp/tokens.json`
3. Если токен истёк — переавторизуйся через Google OAuth setup

Timezone ошибка:
1. Запусти команды через project env (`uv run h2t-ops ...`) или установленный `h2t-ops`
2. На Windows для IANA timezone вроде `Asia/Jerusalem` нужен пакет `tzdata`
