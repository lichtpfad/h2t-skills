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
$CLI calendars --json
$CLI list [--days N] [--from YYYY-MM-DD --to YYYY-MM-DD] [--tz TZ] [--max N] [--busy-only] [--calendar-id primary] [--json]
```

- `calendars --json` — список доступных календарей, `access_role`, `can_write`, timezone
- `--days 1` — события на сегодня (по умолчанию)
- `--days 7` — события на неделю
- `--from ... --to ...` — явное окно дат; `--to` включительно для пользователя
- `--tz Asia/Jerusalem` — timezone для date-window; fallback: `H2T_CALENDAR_TZ`, затем `Asia/Jerusalem`
- `--busy-only` — скрыть transparent/free события
- `--max 250` — безопасный дефолт, чтобы не терять насыщенные дни
- `--calendar-id` — календарь для read/write операций; default `primary`

### Поиск событий
```bash
$CLI search "<query>" [--max N] [--calendar-id primary] [--json]
```

### Создание события
```bash
$CLI create "<summary>" <YYYY-MM-DD> <HH:MM> [--duration-min N] [--description "..."] [--location "..."] [--attendees "a@b.com,c@d.com"] [--meet] [--rrule "RRULE:FREQ=WEEKLY;COUNT=4"] [--reminder-minutes 10,60] [--calendar-id primary] [--tz "Asia/Jerusalem"]
$CLI create "<summary>" <YYYY-MM-DD> --all-day [--calendar-id primary] [--json]
```

Примеры:
```bash
$CLI create "Встреча" 2026-04-10 14:00 --duration-min 60 --meet
$CLI create "Встреча" 2026-04-10 14:00 --duration 90 --description "Важная встреча"
$CLI create "Holiday" 2026-04-10 --all-day --json
```

`--duration` остаётся deprecated alias для старых workflow; новые команды должны
использовать `--duration-min`.

### Обновление события
```bash
$CLI update <event-id> [--summary "..."] [--date YYYY-MM-DD --time HH:MM --duration-min N] [--all-day --date YYYY-MM-DD] [--description "..."] [--location "..."] [--replace-attendees a@b.com,c@d.com] [--meet] [--replace-rrule "RRULE:..."] [--replace-reminders 10,60] [--clear-reminders] [--calendar-id primary] [--json]
```

`--replace-attendees`, `--replace-rrule`, and `--replace-reminders` replace
Google Calendar array fields. Use them only when replacement is intended.

### FreeBusy
```bash
$CLI freebusy --from YYYY-MM-DD --to YYYY-MM-DD [--tz TZ] [--calendar-id primary] [--calendar-id team@example.com] [--json]
```

Returns raw busy windows and visible per-calendar errors.

### Удаление события
```bash
$CLI delete <event-id> [--calendar-id primary] [--confirm]
```

Без `--confirm` команда не удаляет и возвращает usage error. С `--confirm` удаляет.

### Получение события
```bash
$CLI get <event-id> [--calendar-id primary] [--json]
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
