---
name: daily-brief
description: "Morning briefing aggregating Google Calendar, Gmail, and Notion tasks into a daily plan. Triggers: 'daily brief', 'briefing', 'утренний брифинг', 'что сегодня', 'план на день'., 'h2t:daily-brief'"
compatibility: "Requires Google OAuth + NOTION_API_TOKEN. DOR_ROOT for output. Gmail, calendar, notion sibling skills must be installed."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

## Запуск

### Интерактивный режим (по умолчанию)

1. Запусти скрипт с флагами `--json --save` для получения данных и автосохранения:
   ```bash
   ~/.h2t/venv/bin/python ${CLAUDE_SKILL_DIR}/scripts/daily_brief_cli.py --json --save
   ```

2. Получив JSON, сформируй брифинг по доменам:
   - **🎨 Art & Culture** — события/письма/задачи с ключевыми словами: art, museum, gallery, open call, grant, exhibition, QATAL, curator, ANU, Mamuta, Zilberman, Bezalel, AICF, Mifal
   - **💻 Development** — GitHub, PR, code, deploy, client, project, API, tech
   - **📚 Education** — course, teaching, students, workshop, lecture, university
   - **📸 Photography** — photo, shoot, client, print, exhibition (photography context)
   - **👤 Personal** — всё остальное

3. Добавь секцию **⚡ Priority Actions** (HIGH/MED/LOW):
   - HIGH: события сегодня + S/Action задачи + письма с дедлайнами
   - MED: S/Next Action задачи + остальные важные письма
   - LOW: фоновые задачи

4. Брифинг уже сохранён автоматически в `content/Daily/YYYY-MM-DD.md` (флаг `--save` передан на шаге 1)

### Автономный режим (только сбор + сохранение, без Claude)

```bash
$PYTHON $SKILL_DIR/daily_brief_cli.py --save
```

Сохраняет в `content/Daily/YYYY-MM-DD.md`

### Опции

```
--json       Вывод JSON (для интерактивного режима с Claude)
--save       Сохранить Markdown файл
--days N     Событий на N дней вперёд (default: 1)
```

## Обработка ошибок

- **Ошибка Calendar/Gmail**: проверь токены — `~/.config/google-calendar-mcp/tokens.json`
  - Если expired: запусти gmail skill для re-auth
- **Ошибка Notion**: проверь токен — `~/.config/notion/token`
- **ImportError**: проверь что `.venv` активен, зависимости установлены

## Cron (автоматический запуск в 7:00)

```bash
# Добавить в crontab -e (путь к скрипту из claude plugin install):
0 7 * * * ~/.h2t/venv/bin/python ~/.claude/plugins/installed/h2t@lichtpfad/skills/daily-brief/scripts/daily_brief_cli.py \
  --save >> /tmp/daily-brief.log 2>&1
```
