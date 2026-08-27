---
name: voice-eval
description: "Evaluate writing style of a draft against author voice profile. Triggers on: 'voice eval', 'check my voice', 'оцени стиль', 'проверь голос', 'voice check', '/voice-eval'. Requires the private h2t-voice repository; point H2T_VOICE_PYTHON at its interpreter."
compatibility: "Requires H2T_VOICE_PYTHON pointing at the h2t-voice interpreter. Profile must exist at ~/.h2t/voice/profiles/default/."
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Voice Eval

Оценивает черновик текста на соответствие авторскому голосу. Выдаёт score,
критические проблемы и prescriptions для LLM-рерайта.

## Setup

```bash
# h2t-voice is a separate, private repository — it is not part of this pack and is not
# published anywhere. Point H2T_VOICE_PYTHON at its interpreter yourself; there is no
# default worth guessing, and the old one named one directory on one Windows machine.
if [ -z "${H2T_VOICE_PYTHON:-}" ]; then
  echo "ERROR: this skill needs the private h2t-voice checkout." >&2
  echo "Set H2T_VOICE_PYTHON to the interpreter of its virtualenv, e.g." >&2
  echo "  export H2T_VOICE_PYTHON=/path/to/h2t-voice/.venv/bin/python" >&2
  exit 3
fi

VOICE_CLI="$H2T_VOICE_PYTHON -m h2t_voice.cli"
PROFILE="${VOICE_PROFILE:-default}"
```

## Команды

### Оценить черновик

```bash
$VOICE_CLI eval <path-to-draft.md> --profile $PROFILE
```

Выводит:

- `## CRITICAL ISSUES` — ai_slop, engagement bait, тяжёлые паттерны
- `## STYLE ADJUSTMENTS` — prescriptions отсортированные по feature importance
- `## VOICE MATCH SCORE: X.XX / 1.00 (classifier: Y.YY)` — общий score

### Только вероятность авторства

```bash
$VOICE_CLI classify <path-to-draft.md> --profile $PROFILE
```

### Посмотреть профили

```bash
$VOICE_CLI profile list
```

### JSON для автоматизации

```bash
$VOICE_CLI eval <draft.md> --profile $PROFILE --json-out
```

## Процедура

### Step 1: Определить черновик

Если пользователь указал файл — использовать его.
Если указал текст напрямую — записать во временный файл:

```bash
DRAFT_FILE=$(mktemp /tmp/voice-draft-XXXX.md)
# Записать текст в $DRAFT_FILE
```

Если не указано ничего — спросить.

### Step 2: Проверить профиль

```bash
$VOICE_CLI profile list
```

Если `default` профиль существует — использовать его.
Если нет профилей — сообщить:

```text
Профиль не найден. Создать: h2t-voice profile create default
Добавить тексты в: ~/.h2t/voice/profiles/default/reference/
Обучить: h2t-voice profile train default
```

### Step 3: Запустить eval

```bash
$VOICE_CLI eval "$DRAFT_FILE" --profile $PROFILE
```

### Step 4: Интерпретировать результат

| Score | Интерпретация | Действие |
| --- | --- | --- |
| ≥ 0.80 | GOOD — близко к voice | Можно публиковать |
| 0.60–0.79 | NEEDS WORK | Применить prescriptions, переписать |
| < 0.60 | FAR FROM REFERENCE | Значительный рерайт |

Если есть `## CRITICAL ISSUES` (ai_slop, engagement_bait) — они важнее score.

### Step 5: Добавить в reference

Если текст финализирован и опубликован — предложить добавить в reference для
улучшения профиля:

```bash
# Пользователь подтверждает
cp <final-text.md> ~/.h2t/voice/profiles/default/reference/
# Обновить профиль
$VOICE_CLI profile train default
```

**Не добавлять автоматически** — только после явного подтверждения.

## Интерпретация prescriptions

Prescriptions — готовый текст для инжекции в LLM-промпт:

```text
Возьми этот черновик и перепиши его, применив следующие корректировки:

[вставить вывод voice-eval]

Сохрани смысл, измени только стиль.
```

## Интеграция с factory-promote

При работе в h2t-factory pipeline (стадия promote → publish):

```bash
# Проверить сгенерированный контент перед публикацией
$VOICE_CLI eval <generated-content.md> --profile $PROFILE
```

Score < 0.65 → флаг для проверки (не блокирует публикацию, рекомендация).

## Диагностика

| Проблема | Решение |
| --- | --- |
| `Profile 'default' not found` | `h2t-voice profile create default` + добавить тексты + train |
| `No module named h2t_voice` | `H2T_VOICE_PYTHON` указывает не туда, либо пакет не установлен: `pip install -e <h2t-voice>` |
| `spaCy model not found` | `$H2T_VOICE_PYTHON -m spacy download ru_core_news_lg` |
| Classifier score отсутствует | Нет negatives в профиле или model.cbm не обучен |
