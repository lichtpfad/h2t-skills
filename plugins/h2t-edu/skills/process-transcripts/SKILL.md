---
name: process-transcripts
description: "LLM-enrichment of MeetGeek meeting transcripts. Extracts participants, summary, action items, decisions, routes personal/coaching sessions to SELFWORK. Triggers: 'process transcripts', 'обработай транскрипты', 'enrichment meetings'., 'h2t-edu:process-transcripts'"
compatibility: "Requires GEMINI_API_KEY in ~/.dor/secrets/secrets.env, legacy ~/.dor/secrets.env, or env var. DOR_ROOT env var for context/meetings input and output."
context: fork
agent: general-purpose
allowed-tools:
  - Bash
  - Read
  - Write
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Process Transcripts Skill

## Переменные

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

SKILL_DIR="${CLAUDE_SKILL_DIR}"
PYTHON="$H2T_PYTHON"
```

## Команды

### Один файл
```bash
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md"
```

### Все необработанные
```bash
$PYTHON $SKILL_DIR/process_transcripts.py --all
```

### Dry run (без изменений)
```bash
$PYTHON $SKILL_DIR/process_transcripts.py --all --dry-run
```

### Перезаписать уже обработанные
```bash
$PYTHON $SKILL_DIR/process_transcripts.py --all --force
```

### Без обновления INDEX.md
```bash
$PYTHON $SKILL_DIR/process_transcripts.py --all --no-index
```

## Тестирование с --dump-json + jq

`--dump-json` вызывает LLM, выводит сырой JSON в stdout **без** записи файла.
Диагностика (тип, дата, прогресс) идёт в stderr — не мешает пайпу.

```bash
# Используй те же переменные из секции выше (H2T_PYTHON, SKILL_DIR)

# Полный JSON от LLM — посмотреть всё сразу
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json | jq .

# Только участники
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json | jq '.participants'

# Только action items (owner + task)
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json \
  | jq '[.action_items[] | {owner, task}]'

# Проверить категорию и проекты
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json \
  | jq '{category, meeting_type, projects, participants_confidence}'

# Ключевые решения
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json \
  | jq '.key_decisions[]'

# Сохранить JSON для diff сравнения
$PYTHON $SKILL_DIR/process_transcripts.py "Meeting Notes- Название.md" --dump-json \
  > /tmp/meeting_test.json 2>/dev/null
jq '.summary' /tmp/meeting_test.json
```

### Проверка уже обработанных файлов

Для записанных файлов используй `yq` (YAML-версия jq):

```bash
# Установить yq если нет
brew install yq

# Frontmatter одного файла
yq eval 'frontmatter' context/meetings/"Meeting Notes- Название.md"

# Все участники из всех обработанных файлов
for f in context/meetings/*.md; do
  yq eval '.participants[]' "$f" 2>/dev/null
done | sort | uniq -c | sort -rn

# Проверить INDEX.md
head -20 context/meetings/INDEX.md
```

## Что делает скилл

1. **Парсер**: берёт только текст после `Meeting Transcript`, выбрасывает MeetGeek metadata
2. **Детектор типа**:
   - Тип A: `Real Name - 00:12` → имена точные
   - Тип B: `Speaker_01 - 00:12` → нет имён, LLM пытается определить из контекста
3. **LLM вызов**: Claude Haiku через `claude --print --json-schema`
4. **Обогащение**: participants, meeting_type, topic, summary, projects, action_items, decisions
5. **Запись**: YAML frontmatter + чистый транскрипт
6. **Роутинг**: category=personal/coaching → `SELFWORK/transcripts/`, остальное остаётся в `context/meetings/`
7. **Сайд-эффекты**: `context/actions/`, `context/decisions/`, `context/meetings/INDEX.md`

## Зависимости

- `pyyaml` в `.venv` (установлен)
- `google-genai` (Gemini SDK, в h2t venv)
- Проекты: `.claude/projects.yaml`

## Выходной формат файла

```yaml
---
title: "Краткое описание встречи"
date_raw: "2026-02-11T08:15:00Z"
date_reliable: true
meeting_type: partner_sync
participants: [Stanislav, Sergey Spiridonov]
projects: [crypto-etl]
category: work
tags: [architecture, etl]
transcript_type: A
participants_confidence: high
processed: true
processed_at: "2026-02-21"
---

## Summary
...

## Action Items
- [ ] **Stanislav**: начать имплементацию шага 1

## Key Decisions
- Утверждена новая архитектура

## Transcript
[чистый транскрипт]
```
