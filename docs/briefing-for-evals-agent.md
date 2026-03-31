# claude-agent-skills (h2t plugin) — Инвентарь инструментов

**Репо:** `C:/dev/claude-agent-skills` (GitHub: `lichtpfad/h2t`)
**Версия:** 2.12.1 | **Python venv:** `C:/Users/stani/.h2t/venv`
**Тесты:** `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest`

---

## 1. Skills (26 штук)

Каждый skill — директория `C:/dev/claude-agent-skills/plugins/h2t/skills/{name}/` с `SKILL.md` и опциональными `scripts/`.

### Workflow / Session Management

| Skill | Описание | Scripts |
|-------|----------|---------|
| **dev-session-start** | Старт dev-сессии: собирает контекст (git, github, stack), показывает briefing, предлагает session name | `C:/dev/claude-agent-skills/plugins/h2t/skills/dev-session-start/scripts/gather.py` |
| **handoff** | Конец сессии: сохраняет статус работы для следующей сессии | `C:/dev/claude-agent-skills/plugins/h2t/skills/handoff/scripts/gather.py` |
| **init-project** | Регистрация существующего repo/directory в h2t экосистеме (domains.yaml, repo-mapping.yaml) | `C:/dev/claude-agent-skills/plugins/h2t/skills/init-project/scripts/detect_project.py`, `C:/dev/claude-agent-skills/plugins/h2t/skills/init-project/scripts/apply_registration.py` |
| **daily-brief** | Утренний брифинг: агрегация Calendar + Gmail + Notion → план дня | `C:/dev/claude-agent-skills/plugins/h2t/skills/daily-brief/scripts/daily_brief_cli.py` |
| **pre-merge-check** | Проверка перед merge: security, tests, build gates | нет скриптов |
| **milestone-closure** | Закрытие milestone когда все issues закрыты | нет скриптов |
| **dev-overview** | Кросс-проектный дашборд: прогресс, активность, issues по всем проектам | нет скриптов |

### Integration (API-based)

| Skill | Описание | Script (абсолютный путь) |
|-------|----------|--------------------------|
| **gmail** | Чтение/отправка Gmail через OAuth | `C:/dev/claude-agent-skills/plugins/h2t/skills/gmail/scripts/gmail_cli.py` |
| **calendar** | Google Calendar events: чтение и создание | `C:/dev/claude-agent-skills/plugins/h2t/skills/calendar/scripts/calendar_cli.py` |
| **notion** | Notion pages и databases: чтение, создание, query | `C:/dev/claude-agent-skills/plugins/h2t/skills/notion/scripts/notion_cli.py` |
| **telegram** | Telegram saved messages, channels, дайджесты → vault + Notion tasks | `C:/dev/claude-agent-skills/plugins/h2t/skills/telegram/scripts/telegram_cli.py` |
| **drive** | Google Drive browser + MeetGeek transcript sync | `C:/dev/claude-agent-skills/plugins/h2t/skills/drive/scripts/drive_cli.py` |
| **youtube-transcript** | Извлечение YouTube транскриптов с чаптерами → vault | `C:/dev/claude-agent-skills/plugins/h2t/skills/youtube-transcript/scripts/youtube_transcript_cli.py` |

### GitHub Tools

| Skill | Описание | Scripts |
|-------|----------|---------|
| **github-issues** | Создание/обновление issues с единым форматом (Context/What/Why/Part-of), labels, milestones | нет скриптов |
| **gh-memory** | GitHub Issues как persistent agent memory: создание task issues, трекинг across sessions | нет скриптов |

### Content Generation

| Skill | Описание | Scripts |
|-------|----------|---------|
| **drawio** | Генерация и экспорт draw.io диаграмм из graph descriptions, shape libraries (TOML) | `C:/dev/claude-agent-skills/plugins/h2t/skills/drawio/scripts/generate.py`, `C:/dev/claude-agent-skills/plugins/h2t/skills/drawio/scripts/export.py` |
| **deck** | HTML презентации: terminal style (dark, monospace) или editorial (light, serif) | нет скриптов |
| **design** | HUD Design System: tactical dashboard aesthetic, monochrome + red accent | нет скриптов |
| **convert-meeting-transcript** | DOCX → Markdown конвертация meeting transcripts | `C:/dev/claude-agent-skills/plugins/h2t/skills/convert-meeting-transcript/scripts/convert_docx_to_md.py` |
| **process-transcripts** | LLM-enrichment MeetGeek транскриптов: participants, summary, action items | `C:/dev/claude-agent-skills/plugins/h2t/skills/process-transcripts/scripts/process_transcripts.py` |

### Research & Analysis

| Skill | Описание | Scripts |
|-------|----------|---------|
| **diagram-node** | Документирование architecture nodes: research → 6-line draw.io annotation + research doc | нет скриптов |
| **node-researcher** | Deep research crypto nodes через Exa API → research doc + draw.io annotation | нет скриптов |
| **ceo-council** | Strategic council of AI advisors: personas, confidence scores, modes (brainstorm, critic) | нет скриптов |
| **lesson-parser** | Парсинг tutorial транскриптов → structured topology (nodes, connections, params) | нет скриптов |

### Utility

| Skill | Описание | Scripts |
|-------|----------|---------|
| **nlm** | Expert guide для NotebookLM CLI — notebooks, sources, podcasts, reports | нет скриптов |
| **setup** | Установка h2t Python dependencies в `~/.h2t/venv` | нет скриптов |

---

## 2. Gather Framework (Python library)

Модули для параллельного сбора контекста. Используются skills через `gather.py`.

**Base path:** `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/`

| Модуль | Путь | Что делает |
|--------|------|------------|
| **runner.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/runner.py` | Параллельный запуск команд (ThreadPool, 8 workers, 15s timeout). `run_parallel(commands) → {name: stdout}`. `output_json(data)` — UTF-8 safe stdout. |
| **git.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/git.py` | Git state: remote, branch, log (5 lines), status, stash, owner_repo |
| **github.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/github.py` | GitHub через `gh` CLI: milestones, issues, bugs, PRs, milestone-filtered issues |
| **project.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/project.py` | Project identity: repo-mapping.yaml → domain, id, label, type, github. Поддерживает git, directory, workspace. |
| **stack.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/stack.py` | Tech stack detection: package.json → js, pyproject.toml → python, Cargo.toml → rust, go.mod → go |
| **sessions.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/sessions.py` | Session file discovery: `~/.dor/sessions/{machine}/{repo}/*.md`. Extract session ID from .jsonl. |
| **user.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/user.py` | User context paths: core.md, domain-specific deep context (psychology.md для personal). Progressive disclosure — пути, не содержимое. |
| **briefing.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/briefing.py` | `format_briefing(data) → (markdown, meta)`. Markdown briefing + slug template. Hints для missing data. |
| **eval.py** | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/eval.py` | `record_eval(skill, metrics)` → JSON в `~/.h2t/evals/{skill}/sessions/`. `estimate_tokens(data)` — len/4. |

---

## 3. Hooks

**Base path:** `C:/dev/claude-agent-skills/plugins/h2t/hooks-handlers/`

| Hook | Путь | Trigger | Что делает |
|------|------|---------|------------|
| **gather-on-skill** | `C:/dev/claude-agent-skills/plugins/h2t/hooks-handlers/gather-on-skill` | PreToolUse на любой Skill | Роутит на skill-specific скрипт: dev-session-start → gather.py, handoff → gather.py, init-project → detect_project.py. Инжектит результат через systemMessage. |
| **register-session** | `C:/dev/claude-agent-skills/plugins/h2t/hooks-handlers/register-session` | SessionStart (startup/resume/clear) | Регистрация сессии |

**Hook config:** `C:/dev/claude-agent-skills/plugins/h2t/hooks/hooks.json`
**Hook runner:** `C:/dev/claude-agent-skills/plugins/h2t/hooks/run-hook.cmd` (кроссплатформенный polyglot: cmd.exe + bash)

---

## 4. Utility Scripts

| Script | Путь | Что делает |
|--------|------|------------|
| **update-plugin.sh** | `C:/dev/claude-agent-skills/plugins/h2t/scripts/update-plugin.sh` | Синхронизация dev repo → Claude Code plugin cache. Push, pull marketplace, copy to cache, update installed_plugins.json. Возвращает JSON. `--push` flag для git push. |

---

## 5. Config Files (вне репо)

| Файл | Путь | Что хранит |
|------|------|------------|
| **repo-mapping.yaml** | `C:/Users/stani/.h2t/config/repo-mapping.yaml` | Маппинг git repo name → domain/project. cwd_patterns для non-git dirs. |
| **domains.yaml** | `C:/Users/stani/.h2t/config/domains.yaml` | 9 доменов, 50+ проектов. notion_db_id для hou2touch. |
| **about-me/** | `C:/Users/stani/.h2t/config/about-me/` | User context: core.md, psychology.md, health.md, vision.md |
| **evals/** | `C:/Users/stani/.h2t/evals/` | Eval metrics storage: JSON per skill invocation |

---

## 6. Тесты

**Запуск:** `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest <path> -v`

| Тесты | Путь | Кол-во |
|-------|------|--------|
| Gather framework | `C:/dev/claude-agent-skills/plugins/h2t/lib/gather/test_*.py` | 39 |
| Init-project detect | `C:/dev/claude-agent-skills/plugins/h2t/skills/init-project/scripts/test_detect.py` | 12 |
| Init-project apply | `C:/dev/claude-agent-skills/plugins/h2t/skills/init-project/scripts/test_apply.py` | 8 |
| Drawio generate | `C:/dev/claude-agent-skills/plugins/h2t/skills/drawio/scripts/test_generate.py` | 15 |
| Drawio export | `C:/dev/claude-agent-skills/plugins/h2t/skills/drawio/scripts/test_export.py` | — |
| **Итого** | | **~74** |
