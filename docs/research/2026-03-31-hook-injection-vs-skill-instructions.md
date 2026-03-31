# Hook Injection vs SKILL.md Instructions: исследование управления поведением Claude Code

**Автор:** Станислав Глазов (lichtpfad)
**Дата:** 2026-03-31
**Контекст:** h2t plugin для Claude Code, dev-session-start skill
**Модель:** Claude Opus 4.6 (1M context)

---

## Проблема

При разработке dev workflow skill для Claude Code (`dev-session-start`) обнаружена устойчивая проблема: Claude игнорирует инструкции независимо от способа их доставки — через SKILL.md, PreToolUse hook systemMessage, или PostToolUse reminder.

Skill должен: показать briefing → предложить session name → дождаться подтверждения. На практике Claude показывает свою версию briefing и заканчивает "Что делаем?" минуя session naming.

## Эволюция подходов

### v0 / v2.6.3 — Claude ведёт pipeline (работало)

SKILL.md содержит 7 конкретных шагов с bash командами. Claude сам запускает `git log`, `gh issue list`, строит summary, доходит до Step 6 GATE (session naming).

```
Step 1: git remote, git branch, git log, git status
Step 2: Read session files
Step 3: gh issue list, gh milestone list
Step 4: Detect stack
Step 5: Present summary (NO QUESTIONS — data only)
Step 6: ⛔ GATE — propose session name + direction
Step 7: Post GitHub comment
```

**Почему работало:** Claude контролировал весь pipeline. Каждый шаг зависел от предыдущего — модель не могла перепрыгнуть. Линейный поток создавал инерцию, несущую через GATE.

**Ключевая строчка:** `"Do NOT ask the user any questions in Step 5. All user interaction happens in Step 6."`

### v2.8.0 — PreToolUse hook собирает данные (сломалось)

Перенесли gather в PreToolUse hook. Hook запускает `gather.py`, инжектирует JSON через `systemMessage`. SKILL.md говорит "покажи GATHER_DATA verbatim".

**Что сломалось:** Claude получает готовые данные через hook, но не следует инструкциям SKILL.md. Запускает собственный manual gather (git log, gh issue list) поверх hook data. GATE пропускается.

### v2.10.0 — Briefing formatting в hook

Hook форматирует markdown briefing + slug template. SKILL.md: "Show BRIEFING verbatim, then propose session name using slug_template."

**Результат:** Claude игнорирует инструкцию show verbatim, переформатирует по-своему (таблицы вместо markdown), GATE пропускается.

### v2.12.0 — Variant C: полные инструкции в hook systemMessage

Радикальный подход: hook инжектирует и данные, и пошаговые инструкции прямо в systemMessage. SKILL.md — минимальный stub.

```
=== DEV-SESSION-START: ОБЯЗАТЕЛЬНЫЕ ИНСТРУКЦИИ ===

ДАННЫЕ УЖЕ СОБРАНЫ. НЕ запускай git, gh, или другие команды.

ШАГ 1: Покажи этот брифинг AS-IS:
{briefing}

ШАГ 2 (ОБЯЗАТЕЛЬНЫЙ GATE): Предложи имя сессии.
ЗАПРЕЩЕНО: запускать git log, git status, gh issue list.
```

**Результат:** Claude видит инструкции (они отображаются в PreToolUse output), но полностью игнорирует — запускает manual gather, не предлагает session name.

### v2.12.1 — Объединение briefing + GATE в один блок

Объединили "покажи briefing" и "предложи session name" в единую инструкцию: "Твой ответ должен содержать ДВЕ части в ОДНОМ сообщении."

**Результат:** Без изменений. Claude игнорирует.

## Серия экспериментов

### Эксперимент 1: Нейтральное имя skill

**Гипотеза:** Claude запускает manual gather потому что название "dev-session-start" триггерит паттерн из training data.

**Действие:** Создали копию skill с именем `ctx-load` — нейтральное, без session/dev/start vocabulary.

**Результат в workspace (C:/dev/, не git repo):** Claude НЕ запустил gather — показал общий контекст из конфигов. ✅

**Результат в git repo:** Claude запустил git log, gh issue list — полный manual gather. ❌

**Вывод:** Имя skill — не единственный триггер. Git repo context тоже влияет.

### Эксперимент 2: Минимальный SKILL.md без trigger-слов

**Гипотеза:** Trigger-слова в SKILL.md (session, project, context, briefing) активируют gather паттерн.

**Действие:** SKILL.md сокращён до 6 строк: "System messages contain a data block. Find it and display. Propose work direction."

**Результат:** Claude запустил manual gather. ❌

**Вывод:** Даже без trigger-слов Claude запускает gather в git repo.

### Эксперимент 3: Нейтральное description команды

**Гипотеза:** Description в `commands/*.md` файле триггерит паттерн до загрузки SKILL.md.

**Действие:** Заменили "Load project context and display formatted briefing" → "Process and display data from system messages."

**Результат:** Claude запустил manual gather. ❌

**Вывод:** Description не является единственным триггером.

### Эксперимент 4: Контрольная группа — diagram-node

**Наблюдение:** Skill `diagram-node` в том же git repo НЕ вызывает gather. Claude просто спрашивает "Какой узел документируем?"

**Отличие:** SKILL.md содержит конкретный 5-шаговый pipeline с конкретной задачей (research → annotation). Claude знает что делать → не импровизирует.

**Вывод:** Конкретный pipeline подавляет импровизацию.

### Эксперимент 5: Gmail-style CLI pattern

**Гипотеза:** Если SKILL.md содержит конкретные bash команды (как gmail skill), Claude будет следовать им вместо manual gather.

**Действие:** ctx-load переписан в gmail-pattern:
```markdown
## Переменные
GATHER="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/../dev-session-start/scripts/gather.py"

## Команды
### 1. Собрать данные
$GATHER --cwd "$(pwd)" --format-briefing
### 2. Показать результат
Из JSON возьми _briefing и покажи AS-IS
### 3. Предложить направление
Предлагаю имя сессии: `{slug}`
```

**Результат:** Claude НЕ запустил ни `$GATHER`, ни manual gather. Он взял данные из hook systemMessage и показал их мгновенно. ✅ для данных, ❌ для GATE (session name пропущен).

**Вывод:** Gmail-pattern подавляет manual gather (Claude видит что есть конкретный способ получить данные и "успокаивается"). Но Step 3 (session naming) всё равно пропущен.

### Эксперимент 6: PostToolUse reminder

**Гипотеза:** PostToolUse hook, стреляющий после загрузки skill, может напомнить Claude про session naming.

**Действие:** Добавлен PostToolUse handler `gate-reminder` — инжектирует: "ДОЛЖЕН предложить имя сессии. НЕ заканчивай 'Что делаем?'"

**Результат:** Reminder виден в логе, Claude его получил. Но завершил "Готов к работе. Что делаем?" — GATE проигнорирован. ❌

## Сводная таблица

| Механизм | Доставка данных | Управление поведением |
|----------|:-:|:-:|
| PreToolUse systemMessage (данные) | ✅ | — |
| PreToolUse systemMessage (инструкции) | — | ❌ |
| PostToolUse systemMessage (reminder) | ✅ доставлен | ❌ |
| SKILL.md абстрактные инструкции | — | ❌ |
| SKILL.md конкретные bash команды | — | ⚠️ подавляет gather |
| SKILL.md линейный pipeline (v0) | ✅ | ✅ |

## Ключевые находки

### 1. Hooks отлично доставляют данные, но не управляют поведением

PreToolUse hook надёжно инжектирует JSON/markdown/инструкции через `systemMessage`. Claude **видит** эти данные и может их использовать. Но Claude **не следует** инструкциям из systemMessage — ни запретам ("НЕ запускай git"), ни позитивным указаниям ("предложи session name").

### 2. Training data паттерны сильнее любых runtime инструкций

В git repo Claude имеет устойчивый паттерн: "собрать контекст = git log + gh issue list + git status". Этот паттерн активируется не конкретным trigger-словом, а комбинацией:
- Мы в git repo (есть `.git/`)
- Skill invoked (нужно "быть полезным")
- Нет конкретной задачи (SKILL.md абстрактный)

### 3. Конкретный pipeline подавляет импровизацию

Когда SKILL.md содержит конкретный pipeline (diagram-node: "5 шагов, начни с research"), Claude следует ему. Когда SKILL.md абстрактный ("покажи данные, предложи направление") — Claude импровизирует по своим паттернам.

### 4. Gmail-style CLI pattern — промежуточное решение

Наличие конкретных bash команд в SKILL.md (`$CLI list`, `$GATHER --cwd`) подавляет manual gather даже если Claude не запускает сам скрипт. Claude "видит" что есть конкретный инструмент и не чувствует необходимости собирать данные самостоятельно. Однако это работает только для подавления gather, не для принуждения к конкретным действиям (GATE).

### 5. Единственный проверенный способ управления — линейный pipeline

v0/v2.6.3 работали потому что Claude сам выполнял каждый шаг: `git log` → parse → summary → GATE. Каждый шаг зависел от предыдущего, создавая инерцию. Claude не мог перепрыгнуть через шаг потому что следующий требовал данных от предыдущего.

### 6. Название skill влияет, но не определяет

"dev-session-start" усиливает gather паттерн, но нейтральное имя "ctx-load" не устраняет его полностью. Влияет комбинация: имя + description + контекст (git repo) + абстрактность инструкций.

## Архитектурные выводы для Claude Code plugin разработки

### Что работает

- **Hook для данных** — Pre/PostToolUse hooks надёжно доставляют данные через systemMessage. Используйте для pre-computed context, API responses, cached results.
- **Scripts для capabilities** — Python скрипты необходимы когда Claude не имеет нативного доступа (Gmail API, Notion API, OAuth). Claude охотно использует скрипты когда нет альтернативы.
- **Линейный pipeline** — SKILL.md с конкретными шагами, каждый зависит от предыдущего. Claude следует рельсам.
- **Gmail-style CLI pattern** — конкретные bash команды в SKILL.md подавляют импровизацию, даже если Claude не запускает их.

### Что не работает

- **Инструкции через hooks** — systemMessage из hooks не управляет поведением. Claude видит, но не следует.
- **Запреты** — "НЕ запускай git", "НЕ дополняй данные" — игнорируются.
- **Абстрактные SKILL.md** — "покажи данные и предложи направление" → Claude импровизирует.
- **Stub SKILL.md + hook instructions** — Claude игнорирует оба.

### Правило для plugin developers

> **Если Claude может сделать задачу сам — он будет делать по-своему, игнорируя ваши инструкции. Scripts работают только для capabilities, которых у Claude нет нативно. Для управления поведением — линейный pipeline с конкретными шагами.**

## Рекомендуемая архитектура

### Для skills с внешними API (gmail, notion, calendar)

```
Hook: не нужен
SKILL.md: CLI pattern ($CLI list, $CLI search)
Script: Python CLI с argparse → JSON stdout
```

Claude запустит скрипт потому что у него нет альтернативы.

### Для workflow skills (session-start, handoff)

```
Hook: доставить pre-cached данные (optional accelerator)
SKILL.md: линейный pipeline, Claude сам запускает каждый шаг
Script: gather.py вызывается Claude, не hook
```

Claude будет дублировать gather если hook уже собрал данные, но линейный pipeline обеспечит GATE.

### Для content generation (drawio, deck)

```
Hook: не нужен
SKILL.md: конкретный pipeline (5+ шагов)
Script: если нужен (export, validate)
```

Claude следует конкретным шагам без импровизации.

## Трёхслойная модель (обновлённая)

| Слой | Для чего работает | Для чего НЕ работает |
|------|-------------------|---------------------|
| **L1: Scripts** | Внешние API, auth, data sources | Замена нативных capabilities Claude |
| **L2: Hooks** | Доставка данных, pre-computation | Управление поведением, инструкции |
| **L3: SKILL.md** | Линейный pipeline с конкретными шагами | Абстрактные указания, запреты |

---

## Appendix: версии и эксперименты

| Версия | Подход | Gather | GATE | Notes |
|--------|--------|:------:|:----:|-------|
| v0 (6b6ae00f) | Claude runs bash commands | ✅ сам | ✅ | Линейный pipeline, 7 шагов |
| v2.6.3 (ebc17d4e) | Claude runs $GATHER script | ✅ скрипт | ✅ | Gmail-style CLI pattern |
| v2.8.0 (672249e7) | Hook runs gather.py | ❌ manual | ❌ | SKILL.md instructions ignored |
| v2.10.0 (f0c844c3) | Hook formats briefing | ❌ manual | ❌ | "show VERBATIM" ignored |
| v2.12.0 (4054334c) | Hook injects full instructions | ❌ manual | ❌ | Variant C — instructions ignored |
| v2.12.1 (ddca9ce) | Merged briefing + GATE | ❌ manual | ❌ | Combined instruction block ignored |
| v2.13.1 — ctx-load | Neutral skill name | ❌ manual | ❌ | Name is not the only trigger |
| v2.13.2 — minimal | 6-line SKILL.md | ❌ manual | ❌ | Abstract = improvisation |
| v2.13.3 — neutral desc | Neutral command description | ❌ manual | ❌ | Description not the trigger |
| v2.13.4 — gmail pattern | Concrete bash commands | ✅ hook data | ❌ | Suppresses gather, not GATE |
| v2.13.5 — PostToolUse | Reminder after skill load | ✅ hook data | ❌ | Reminder seen but ignored |
