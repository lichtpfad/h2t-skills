---
name: daily-brief
description: "Morning briefing aggregating Google Calendar, Gmail, and Notion tasks into a daily plan. Triggers: 'daily brief', 'briefing', 'утренний брифинг', 'что сегодня', 'план на день', 'h2t:daily-brief'"
compatibility: "Requires the h2t-ops CLI on PATH (uv tool install), Google OAuth + NOTION_API_TOKEN."
metadata:
  author: lichtpfad
  version: 3.0.0
---

# Daily Brief

## POS Boundary

Daily Brief is a read and synthesis workflow, not the POS journal writer. Follow
`../../references/pos-operational-boundary.md`: route decisions, tasks, lessons,
and follow-ups through POS journal commands once available. Until then, emit
structured proposed captures instead of mutating stores.

## Правила достоверности

Эти правила важнее полноты брифинга. Нарушение = брифинг недостоверен.

1. **Счётчик только из футера или meta.** Каждая списочная команда заканчивается
   строкой `[N shown — complete]` или `[N of ~M shown — MORE EXIST]`. Число брать
   оттуда, никогда из длины показанного списка. При `MORE EXIST` формулировка
   «показаны N из ~M», а не «всего N».
2. **Ссылка на каждый пункт.** Событие, письмо, задача — без URL пункт не выводится.
3. **Разделять данные и вывод.** Всё, чего нет в выдаче, помечать `(вывод)`.
   Запрещено без проверки: «ждёт вашего ответа», «не отправлено», «следующий шаг будет».
4. **Пустое поле — не «нет».** `(unresolved)` у relation означает «неизвестно», а не
   повод подставить проект из CLAUDE.md или памяти.
5. **Не подгонять под формат.** Если свойство из Step 2 отсутствует в базе — сказать
   об этом в брифинге, а не заменять правило собственным суждением.

## Переменные

`h2t-ops` ставится через `uv tool install` и лежит в PATH. Никаких путей к
плагину и к клону репозитория: `${CLAUDE_PLUGIN_ROOT}` в bash-блок скилла
приходит не во всех харнессах, а версионированный кэш плагина протухает.

Питон в скилле не нужен: даты считает сам коннектор, `--from/--to` принимают
`today` и смещения вида `+2d` и резолвят их в таймзоне запроса. Это заодно
убирает POSIX-специфичный путь к интерпретатору, который ломался на Windows.

```bash
command -v h2t-ops >/dev/null || { echo "ERROR: h2t-ops not on PATH. Run /h2t-core:setup"; exit 1; }
TASKS_DB="beabac7bf4314952a9327759c638d89f"
TZ_NAME="Asia/Jerusalem"
```

## Шаги

### Step 1: Собери данные

Ошибка одного источника не блокирует остальные.

```bash
# События: явное окно календарных суток. --days считает от текущего момента и
# теряет то, что было раньше сегодня, поэтому здесь --from/--to с таймзоной.
h2t-ops calendar list --from today --to +2d --tz "$TZ_NAME" --max 50 --json

# Письма: --format human, а не --json. В json каждая строка тащит полное тело
# письма (~5 KB), 40 писем это ~300 KB в контекст. human даёт ~13 KB с ID.
h2t-ops gmail list --unread --query "is:important" --max 40 --format human

# Задачи: --format md отдаёт свойства, Link и резолвленный проект
h2t-ops notion search "$TASKS_DB" \
  --filter-json '{"property":"Status","status":{"does_not_equal":"Done"}}' \
  --limit 200 --format md --resolve-relations Project
```

Что даёт каждая команда:

| Команда | Ключевые поля |
|---|---|
| `calendar list` | `ongoing` (идёт **прямо сейчас**: по часам для событий со временем, весь день для all-day), `day_index`/`days_total` у многодневных, `html_link` |
| `gmail list` | отправитель, дата, `ID` (ссылка: `https://mail.google.com/mail/u/0/#all/<ID>`), snippet |
| `notion search` | `Status`, `Priority`, `Due`, `Link`, `Project` со ссылкой |

`--resolve-relations Project` обязателен: без него проект придёт как
`(unresolved)`, и подставлять его по памяти нельзя.

### Step 2: Приоритизация

Реальная схема базы задач: `Status` = `Not started` | `In progress` | `Done`,
плюс `Priority` = `High` | `Medium` | `Low` и `Due`. Часть задач не имеет ни
`Priority`, ни `Due`.

**Сначала отбрось нерелевантное:**

- **Шаблонные задачи Notion.** Проект называется `Sample Project: …` или
  `Getting started with …` — это демо-контент из шаблона, не работа. Считать
  отдельно, в приоритеты не включать: `🗑 N шаблонных задач Notion`.
- **Мёртвые дедлайны.** `Due` просрочен больше чем на 90 дней — задача не
  срочная, а забытая. В HIGH/MED/LOW не раскладывать, вывести одной строкой:
  `⚠️ N задач с дедлайнами старше 90 дней, нужна ревизия`.
  Исключение: `Priority: High` остаётся в приоритетах даже с мёртвым дедлайном,
  но с пометкой `дедлайн просрочен на N дн.` — важность и срочность это разные
  поля, и протухшая дата не отменяет проставленную важность.

**Затем приоритеты по оставшимся:**

- **HIGH**: идущие и сегодняшние события + `Priority: High` + `Due` просрочен
  не более чем на 30 дней или наступает в ближайшие 3 дня + письма с явным
  дедлайном или суммой к оплате
- **MED**: `Status: In progress` + `Priority: Medium` + `Due` просрочен на
  30-90 дней + важные письма без дедлайна
- **LOW**: остальное, включая задачи без `Priority` и без `Due`

**Проверка на вырождение.** Если после отбрасывания в HIGH попало больше
половины активных задач — правило не сработало на этих данных. Не выдавать
такой список за приоритеты: написать
`⚠️ правило приоритизации вырождается (N из M в HIGH), ранжирую по Priority и Status`
и приоритизировать только по `Priority` и `Status`.

Если ожидаемого свойства в выдаче нет — написать в брифинге
`⚠️ property <name> отсутствует, приоритет выставлен по <что использовалось>`.

### Step 3: Сгруппируй по доменам

- **🎨 Art & Culture** — art, museum, gallery, exhibition, QATAL, curator, ANU, Mamuta, Zilberman, Bezalel, AICF
- **💻 Development** — GitHub, PR, code, deploy, project, API, tech
- **📚 Education** — course, teaching, students, workshop, lecture
- **👤 Personal** — всё остальное

Домен из тега или проекта задачи важнее домена из ключевых слов в заголовке.

### Step 4: Покажи брифинг

Идущие события идут первыми, до списка сегодняшнего дня: это контекст всего
брифинга, а не строка в перечне. Отбор — по `ongoing`; фильтровать дополнительно
по `multi_day` не нужно (#359: раньше `ongoing` означал «попадает на сегодня», и
без этого костыля в секцию падала каждая сегодняшняя встреча).

```
# Daily Brief — YYYY-MM-DD

## 🔴 Идёт сейчас
- [Bavaria](html_link) — день 3 из 8, до 26.08

## 📅 Сегодня (N событий)
- [Название](html_link) — время

## 📧 Gmail (показаны M из ~N важных непрочитанных)
- [Тема](https://mail.google.com/mail/u/0/#all/<ID>) — отправитель, дата

## ✅ Tasks (N активных)
- [Задача](notion_url) — Status · Priority · Due · [Проект](project_url)
⚠️ N задач с дедлайнами старше 90 дней, нужна ревизия
🗑 N шаблонных задач Notion

## ⚡ Priority Actions
### HIGH
### MED
### LOW
```

## Обработка ошибок

- **`h2t-ops` не найден**: `/h2t-core:setup`, затем
  `python scripts/setup_h2t.py install-h2t-ops --source main --json`
- **Calendar/Gmail**: проверь токены — `~/.config/google-calendar-mcp/tokens.json`
- **Notion**: проверь `NOTION_API_TOKEN` в `~/.dor/secrets.env`
- Диагностика разом: `h2t-ops doctor`
- Если источник недоступен — пропусти его и укажи в брифинге `⚠️ <source> unavailable`
