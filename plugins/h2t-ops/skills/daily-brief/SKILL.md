---
name: h2t-ops:daily-brief
description: "Morning briefing aggregating Google Calendar, Gmail, and Notion tasks into a daily plan. Triggers: 'daily brief', 'briefing', 'утренний брифинг', 'что сегодня', 'план на день', 'h2t:daily-brief'"
compatibility: "Requires Google OAuth + NOTION_API_TOKEN. Gmail, calendar, notion must be working."
metadata:
  author: lichtpfad
  version: 2.2.0
---

# Daily Brief

## POS Boundary

Daily Brief is a read and synthesis workflow, not the POS journal writer. Follow
`../../references/pos-operational-boundary.md`: route decisions, tasks, lessons,
and follow-ups through POS journal commands once available. Until then, emit
structured proposed captures instead of mutating stores.

## Правила достоверности

Эти правила важнее полноты брифинга. Нарушение = брифинг недостоверен.

1. **Счётчик только из конверта.** Число активных задач и писем берётся из
   `count` / `truncated` / `estimated_total`, никогда из длины показанного списка.
   При `truncated: true` формулировка «показаны N из ~M», а не «всего N».
2. **Ссылка на каждый пункт.** Событие, письмо, задача — без URL пункт не выводится.
3. **Разделять данные и вывод.** Всё, чего нет в выдаче, помечать `(вывод)`.
   Запрещено без проверки: «ждёт вашего ответа», «не отправлено», «следующий шаг будет».
4. **Пустое поле — не «нет».** `Project: unresolved` — это «неизвестно», а не повод
   подставить проект из CLAUDE.md или памяти.
5. **Не подгонять под формат.** Если свойство из Step 2 отсутствует в базе — сказать
   об этом в брифинге, а не заменять правило собственным суждением.

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

# lib/cli не поставляется ни одним плагином (см. issue #350) — ищем по кандидатам
H2T_CLI="${H2T_CLI:-}"
for c in \
  "${CLAUDE_PLUGIN_ROOT}/lib/cli/main.py" \
  "$HOME/.claude/plugins/cache/lichtpfad/h2t-core/latest/lib/cli/main.py" \
  "$HOME/.claude/plugins/marketplaces/lichtpfad/lib/cli/main.py" ; do
  [ -z "$H2T_CLI" ] && [ -f "$c" ] && H2T_CLI="$c"
done
[ -z "$H2T_CLI" ] && echo "ERROR: h2t CLI not found. See issue #350" && exit 1

CLI="$H2T_PYTHON $H2T_CLI"
COMPACT="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/daily-brief/compact.py"
TASKS_DB="beabac7bf4314952a9327759c638d89f"
```

## Шаги

### Step 1: Собери данные

Запусти последовательно — ошибка одного источника не блокирует остальные.
Сырой JSON в контекст не тащить: `gmail list` отдаёт полные тела писем
(десятки KB). Всё идёт через `compact.py`, который режет поля, строит ссылки и
помечает обрезку.

```bash
# События: окно --days считается от локальной полуночи, 3 суток с запасом.
# Многодневные события приходят с ongoing / day_index / days_total
$CLI ingest calendar list --days 3 --max 50 --json | $COMPACT calendar

# Важные непрочитанные письма
$CLI ingest gmail list --unread --query "is:important" --max 40 --json | $COMPACT gmail

# Активные задачи Notion (--format json, не --json: у notion другой флаг)
$CLI ingest notion search $TASKS_DB \
  --filter-json '{"property":"Status","status":{"does_not_equal":"Done"}}' \
  --limit 200 --format json --resolve-relations Project | $COMPACT notion
```

Каждый ответ это конверт: `items`, `count`, `truncated`, плюс `estimated_total`
у gmail и `window` у календаря. Счётчики брать оттуда, а не из длины списка.
`--resolve-relations Project` обязателен: без него проект задачи придёт как
`unresolved`, и подставлять его по памяти нельзя.

### Step 2: Приоритизация

Реальная схема базы задач: `Status` = `Not started` | `In progress` | `Done`,
плюс `Priority` = `High` | `Medium` | `Low` и `Due`. Часть задач не имеет ни
`Priority`, ни `Due`.

- **HIGH**: идущие и сегодняшние события + `Priority: High` + просроченный `Due`
  + письма с явным дедлайном или суммой к оплате
- **MED**: `Status: In progress` + `Priority: Medium` + важные письма без дедлайна
- **LOW**: остальное, включая задачи без `Priority` и без `Due`

Если ожидаемого свойства в выдаче нет — написать в брифинге
`⚠️ property <name> отсутствует, приоритет выставлен по <что использовалось>`.

### Step 3: Сгруппируй по доменам

- **🎨 Art & Culture** — art, museum, gallery, exhibition, QATAL, curator, ANU, Mamuta, Zilberman, Bezalel, AICF
- **💻 Development** — GitHub, PR, code, deploy, project, API, tech
- **📚 Education** — course, teaching, students, workshop, lecture
- **👤 Personal** — всё остальное

Домен из тега или проекта задачи важнее домена из ключевых слов в заголовке.

### Step 4: Покажи брифинг

Идущие многодневные события идут первыми, до списка сегодняшнего дня: это
контекст всего брифинга, а не строка в перечне.

```
# Daily Brief — YYYY-MM-DD

## 🔴 Идёт сейчас
- [Bavaria](html_link) — день 3 из 8, до 26.08

## 📅 Сегодня (N событий)
- [Название](html_link) — время

## 📧 Gmail (показаны M из ~N важных непрочитанных)
- [Тема](https://mail.google.com/mail/u/0/#all/<threadId>) — отправитель, дата

## ✅ Tasks (N активных)
- [Задача](notion_url) — Status · Priority · Due · [Проект](project_url)

## ⚡ Priority Actions
### HIGH
### MED
### LOW
```

Счётчики брать из `count` / `truncated` / `estimated_total` конверта, а не из
длины показанного списка. Если `truncated: true` — писать «показаны N из ~M».

## Обработка ошибок

- **CLI не найден**: см. issue #350, `lib/cli` не входит ни в один плагин
- **Calendar/Gmail**: проверь токены — `~/.config/google-calendar-mcp/tokens.json`
- **Notion**: проверь `NOTION_API_TOKEN` в `~/.dor/secrets.env`
- Если источник недоступен — пропусти его и укажи в брифинге `⚠️ <source> unavailable`
