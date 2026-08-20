---
name: lesson-parser
description: "Parses procedural tutorial transcripts into structured topology (nodes, connections, params). 3-level: chapters -> actions -> synthesis. Triggers: 'lesson-parser', 'parse tutorial', 'parse transcript', 'extract topology'."
compatibility: "Claude Code. Input: markdown transcript with chapters (from /h2t-edu:youtube-transcript)."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# Lesson Parser — Извлечение топологии из туториалов

**Назначение:** Парсит транскрипт процедурного туториала (TouchDesigner, Houdini) в структурированный документ топологии: ноды, коннекты, параметры, feedback loops.

Три уровня обработки:
1. **L1** — Сегментация по чаптерам (парсинг markdown)
2. **L2** — Извлечение действий по каждому чаптеру (LLM + node stack)
3. **L3** — Синтез в единый документ топологии

---

## Вход и выход

**Вход:** markdown-файл от `/h2t-edu:youtube-transcript` с форматом:
```
---
video_id: XXX
title: "..."
---
## Chapters
- [MM:SS] Title
## Transcript
### [MM:SS] Title
text...
```

**Выход:** `<transcript_dir>/<video_id>-topology.md`

---

## L1 — Сегментация по чаптерам

1. Прочитать файл через Read tool
   - Файл не найден или не markdown -> abort: `ERROR: файл не найден: <path>`
2. Извлечь `video_id` и `title` из YAML frontmatter
3. Найти секцию `## Transcript`
4. Спарсить заголовки `### [MM:SS] Title` или `### [HH:MM:SS] Title` внутри секции Transcript
5. Для каждого чаптера собрать: номер, заголовок, timestamp, полный текст до следующего `###`
6. Если заголовков не найдено -> один чаптер "Full Transcript" с полным текстом
7. Показать пользователю список чаптеров:
   ```
   Найдено N чаптеров:
     Ch.1 [00:00] Introduction
     Ch.2 [02:15] Setting up the network
     ...
   Начинаю извлечение топологии...
   ```

---

## L2 — Извлечение действий (ядро скилла)

Обработать каждый чаптер последовательно. Между чаптерами передавать **node stack** — накопленный контекст всех созданных нод.

### Грамматика действий

Каждое действие в чаптере записывается в одном из форматов:

```
CREATE <type> "<name>" [params: key=value, ...]
CONNECT <from> -> <to> [input: N]
SET <node>.<param> = <value>
EXPR <node>.<param> = "<expression>"
LOOP <feedback_node> wire=<input_node> par.top=<target_node>
NOTE <free text>
```

Примеры:
```
CREATE circleTOP "circle1"
CREATE feedbackTOP "fb1"
CONNECT circle1 -> fb1 [input: 0]
SET fb1.resetpulse = 1
EXPR circle1.centerx = "absTime.seconds * 0.1"
LOOP fb1 wire=displace1 par.top=level1
NOTE: speaker mentions "play with the values" — exact params unclear
```

### Node stack

Формат стека, который обновляется после каждого чаптера:

```
Stack:
  1. circle1 (circleTOP) — Ch.1, outputs: [fb1]
  2. fb1 (feedbackTOP) — Ch.1, inputs: [circle1], outputs: [level1]
  3. level1 (levelTOP) — Ch.2, inputs: [fb1], outputs: []
Last action: CONNECT fb1 -> level1 [input: 0]
```

Каждая запись содержит: имя, тип, чаптер создания, текущие inputs/outputs.

### Разрешение ссылок (CRITICAL)

Это главная функция скилла — замена местоимений и неявных ссылок на конкретные имена нод из стека.

**Правила:**

| Фраза в транскрипте | Разрешение |
|---------------------|-----------|
| "this", "it", "эту ноду" | Последняя созданная или упомянутая нода в стеке |
| "the feedback", "the math", "наш noise" | Ближайшая нода этого типа в стеке (поиск снизу вверх) |
| "connect X to Y" | Разрешить X и Y по стеку |
| "connect this to a feedback" | CONNECT last_node -> CREATE feedbackTOP "fb_N" |
| "drag X onto Y" | EXPR или SET в зависимости от контекста |
| "let's add a level after this" | CREATE levelTOP + CONNECT last_node -> new_level |
| "copy and paste this" | Дублировать паттерн последней цепочки |
| Неоднозначная ссылка | `NOTE: ambiguous ref "<phrase>" — candidates: node_a, node_b` |

### Вывод типов DCC

Автор туториала часто говорит неформально. Маппинг:

| Фраза | Тип |
|-------|-----|
| "circle top", "circle" | circleTOP |
| "noise chop", "a noise" (в контексте CHOP) | noiseCHOP |
| "a noise" (в контексте TOP) | noiseTOP |
| "a feedback", "feedback top" | feedbackTOP |
| "a level", "level top" | levelTOP |
| "displace", "displace top" | displaceTOP |
| "a math", "math chop" | mathCHOP |
| "constant chop" | constantCHOP |
| "ramp top" | rampTOP |
| "composite", "comp top" | compositeTOP |
| "transform top" | transformTOP |
| "null" (TOP context) | nullTOP |
| "null" (CHOP context) | nullCHOP |

Контекст (TOP/CHOP/SOP/MAT) определяется по окружающим словам и типу сети, в которой работает автор.

### Именование нод

- Имя = lowercase тип без суффикса семейства + порядковый номер: `circle1`, `fb1`, `noise_vel1`
- Если автор явно называет ноду ("let's call this velocity") -> использовать: `noise_vel1`
- Имя ВСЕГДА заканчивается цифрой (TD convention)

### Процесс L2 для каждого чаптера

1. Прочитать текст чаптера + текущий node stack
2. Извлечь все действия в грамматике выше
3. Разрешить ВСЕ местоимения и неявные ссылки -> конкретные имена нод
4. Обновить node stack (добавить новые ноды, обновить inputs/outputs)
5. Записать список действий для этого чаптера

---

## L3 — Синтез топологии

После обработки всех чаптеров — собрать единый документ.

### Формат выходного файла

```markdown
# Topology: <video title>

**Source:** <video_id>
**Chapters:** N
**Generated:** YYYY-MM-DD

## Summary
- Nodes: N (TOP: X, CHOP: Y, SOP: Z)
- Connections: M
- Feedback loops: K
- Warnings: W

## Nodes
| # | Name | Type | Key Params | Chapter |
|---|------|------|------------|---------|
| 1 | circle1 | circleTOP | centerx=expr | Ch.1 |
| 2 | fb1 | feedbackTOP | — | Ch.1 |

## Connections
| From | To | Input | Chapter |
|------|-----|-------|---------|
| circle1 | fb1 | 0 | Ch.1 |

## Feedback Loops
| Node | Wire Input | Loop Target |
|------|------------|-------------|
| fb1 | displace1 | level1 |

## Per-Chapter Details

### Ch.1: <title> [MM:SS]
- CREATE circleTOP "circle1"
- CREATE feedbackTOP "fb1"
- CONNECT circle1 -> fb1 [input: 0]

### Ch.2: <title> [MM:SS]
- CREATE levelTOP "level1"
- ...

## Warnings
- [Ch.3] Ambiguous ref: "the math" — candidates: math_vel1, math_force1
- [Ch.4] Node displace2 has no inputs (not a generator)
- [Ch.5] Unclosed feedback loop: fb2 missing par.top target
```

### Валидация

Проверить и добавить в Warnings:
1. **Ноды без входов** — если нода не генератор и не имеет входящих коннектов
   - Генераторы (exempt): `noise*`, `ramp*`, `constant*`, `circle*`, `panel*`, `keyboard*`, `movie*`, `text*`
2. **Dangling connections** — ссылка на несуществующую ноду
3. **Unclosed feedback loops** — LOOP без wire или без par.top
4. **Неразрешённые ссылки** — оставшиеся NOTE с ambiguous ref

### Запись файла

Сохранить в ту же директорию, что и исходный транскрипт:
```
<transcript_dir>/<video_id>-topology.md
```

---

## Полный процесс

1. Получить путь к файлу от пользователя
2. **L1:** Прочитать файл, спарсить чаптеры
3. Показать список чаптеров пользователю
4. **L2:** Обработать каждый чаптер последовательно, накапливая node stack
5. **L3:** Синтезировать топологию, провалидировать, записать файл
6. Показать summary:
   ```
   Topology extracted: <title>
   - Nodes: 12 (TOP: 8, CHOP: 4)
   - Connections: 15
   - Feedback loops: 2
   - Warnings: 1
   Saved: <output_path>
   ```

---

## Важные правила

- **Не пропускать действия.** Каждый CREATE/CONNECT/SET в транскрипте должен быть извлечён.
- **Не додумывать.** Если автор не упоминает параметр — не добавлять. Если ссылка неоднозначна — NOTE.
- **Node stack — единственный источник контекста** между чаптерами. Полный текст предыдущих чаптеров не перечитывать.
- **Именование:** всегда с цифрой на конце (`noise1`, не `noise`).
- **Порядок inputs:** `[input: 0]` — первый вход (сверху в TD), `[input: 1]` — второй. Если не указано — `[input: 0]`.
