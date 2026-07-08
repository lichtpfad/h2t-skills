# Agent Instructions: docs-lint audit + refactor для rejuve

**Repo:** `C:/work/rejuve`
**Branch:** `docs-refactor-2026-06-02` (уже создана)
**Python (h2t-skills):** `C:/dev/h2t-skills/.venv/Scripts/python.exe`
**Python (system/h2t):** `~/.h2t/venv/Scripts/python.exe`
**lint script:** `C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py`

**Правила (из CLAUDE.md):**
- Одна команда на Bash call — без `&&` `||` `;`
- Git: `git -C C:/work/rejuve ...` — не `cd` + `git`
- Только `git mv` / `git rm`, не `mv` / `rm`
- Untracked файлы — не трогать без подтверждения

---

## Контекст

Уже существует детальный план рефакторинга:
`C:/work/rejuve/docs/superpowers/plans/2026-06-02-repo-refactor-plan.md`

**Прочитай его полностью** перед началом работы. Там 9 задач (~3 часа).

Твоя задача в этой сессии:
1. **Phase 0 (эта инструкция):** запустить docs-lint как аудит — зафиксировать начальное состояние, проскаффолдить недостающее
2. **Phase 1 (план):** выполнить Задачи 1–9 из плана

---

## Phase 0: docs-lint аудит

### 0.1 Переключиться на ветку

```
git -C C:/work/rejuve checkout docs-refactor-2026-06-02
```

### 0.2 Создать docs-lint.yaml

Проверь, существует ли `C:/work/rejuve/.claude/rules/docs-lint.yaml`.

Если **не существует** — создай:

```yaml
schema: h2t_docs_lint_config/v0.1
template: client_project
```

Если **существует** — прочитай и запиши содержимое в лог (шаг 0.3).

### 0.3 Создать лог улучшения скилла

Создай `C:/work/rejuve/docs/superpowers/plans/docs-lint-skill-log.md`:

```markdown
# docs-lint skill improvement log — rejuve

**Date:** 2026-06-04
**Template applied:** client_project
**Tool version:** h2t-dev 1.0.12
**Project type:** client / research / marketing / product / automation

## 0. Pre-run state

### docs-lint.yaml
<was it present? what did it contain? или "created fresh">

### Top-level dirs
<ls C:/work/rejuve>

### docs/ subdirs
<ls C:/work/rejuve/docs>
```

### 0.4 Doctor — before state

```
C:/dev/h2t-skills/.venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/work/rejuve --json --no-pymarkdown
```

Добавь в лог:

```markdown
## 1. Doctor — before

### Status
<status field>

### Typed findings (template: client_project)
<только findings с "template" ключом — list: path | message>

### Other findings (structure, frontmatter, etc.)
<остальные findings — краткий список по категориям>

### Observation: template fit
Посмотри какие dirs есть в репо но НЕ покрыты template.
Список:
- docs/analytics/ — ?
- docs/architecture/ — ?
- docs/pipeline/ — ?
- docs/product/ — ? (переименуется в client/ по плану)
- docs/registers/ — ?
- docs/rollout/ — ?
- docs/strategy/ — ?
- docs/archive/ — ?
- input/ (root) — ?
- nimbalyst-local/ (root) — ?
- node_modules/ (root) — ?
- tests/ (root) — ?

Для каждого: нужно ли добавить в template или это project-specific?

### Critical observation: docs/deliverables conflict
client_project template ожидает docs/deliverables/ (как документацию о deliverables).
НО: в этом проекте deliverables/ — root-level папка для HTML-артефактов.
docs/deliverables/ в плане НЕ предусмотрена.

Вопрос для улучшения скилла: должен ли client_project template включать docs/deliverables/?
Или нужен отдельный sub-variant?
```

### 0.5 Fix-safe — проскаффолдить недостающее

```
C:/dev/h2t-skills/.venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py fix-safe --root C:/work/rejuve
```

Добавь в лог:

```markdown
## 2. fix-safe output

<полный вывод команды>

### Что создано (новые пустые dirs)
<список>

### Что уже было
<список>

### Что fix-safe НЕ создал (но по плану нужно)
<dirs из плана которые fix-safe не трогает — например docs/client/, docs/implementation/>
```

### 0.6 Doctor — after fix-safe

Запусти doctor повторно. Добавь в лог:

```markdown
## 3. Doctor — after fix-safe

### Status
<status field>

### Typed findings — delta (что исчезло после fix-safe)
<сравни с before>

### Remaining typed findings
<что осталось и почему — например docs/deliverables/ конфликт>
```

### 0.7 Коммит Phase 0

```
git -C C:/work/rejuve add .claude/rules/docs-lint.yaml
git -C C:/work/rejuve add docs/superpowers/plans/docs-lint-skill-log.md
```

Если fix-safe создал новые dirs — добавь `.gitkeep` в каждую (если dir пуста) и добавь в индекс.

```
git -C C:/work/rejuve commit -m "docs: add docs-lint config + Phase 0 audit log"
```

---

## Phase 1: Выполнить план рефакторинга

После Phase 0 — выполни Задачи 1–9 из плана `2026-06-02-repo-refactor-plan.md`.

**Порядок важен** (там есть зависимости):
- Задача 6a (frontmatter product/ файлов) **до** Задачи 2 (git mv)
- Задача 8 (generate-index.py) — **после** всех git mv

По ходу выполнения добавляй в лог:

```markdown
## 4. Plan execution notes

### Task 2: product/ → client/
<что пошло не так, edge cases>

### Task 3: implementation/ merge
<что пошло не так>

... и т.д. для каждой задачи где была нетривиальная ситуация
```

---

## Phase 2: Финальный аудит docs-lint

После выполнения всех 9 задач — запусти doctor ещё раз:

```
C:/dev/h2t-skills/.venv/Scripts/python.exe C:/dev/h2t-skills/plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor --root C:/work/rejuve --json --no-pymarkdown
```

Добавь в лог:

```markdown
## 5. Doctor — final (after full refactor)

### Status
<status>

### Remaining findings
<что осталось — и является ли это реальными проблемами или false positives>

### False positives observed
<findings которые docs-lint показал но которые не являются реальными проблемами>

### Missing detections
<проблемы которые были в репо но docs-lint не поймал>
```

---

## Harvest — датасет для улучшения скилла

По ходу работы (Phase 0, 1, 2) — **каждый раз когда замечаешь проблему со скиллом** — добавляй запись в файл:

`C:/work/rejuve/docs/superpowers/plans/docs-lint-harvest.jsonl`

Формат — одна JSON-строка на наблюдение:

```jsonl
{"type": "false_positive", "template": "client_project", "finding_message": "missing template dir: docs/deliverables/ (template: client_project)", "context": "deliverables/ exists at root for HTML artifacts, docs/deliverables/ is not part of this project's architecture", "expected": "no finding — template should not require docs/deliverables/ when root deliverables/ is present", "severity": "high", "phase": "0.4"}
{"type": "template_mismatch", "template": "client_project", "context": "project has docs/analytics/, docs/strategy/, docs/registers/ — none covered by template", "observed": "no findings for these dirs", "expected": "either template covers them or config allows declaring project-specific dirs", "severity": "medium", "phase": "0.4"}
{"type": "missing_detection", "template": "client_project", "context": "docs/product/ should be docs/client/ per project conventions", "observed": "docs-lint did not flag wrong dir name", "expected": "some way to declare canonical dir names", "severity": "low", "phase": "1"}
{"type": "ux_issue", "template": "client_project", "finding_message": "...", "context": "message was confusing because...", "expected": "clearer wording", "severity": "low", "phase": "2"}
{"type": "error", "template": "client_project", "context": "what command was running", "observed": "exact error or traceback", "severity": "high", "phase": "0.5"}
{"type": "suggestion", "template": "client_project", "context": "after seeing the full project", "suggestion": "add research_client_project template with root_dirs: [docs, data, deliverables, scripts, input] and docs_dirs: [docs/ops, docs/research, docs/strategy, docs/analytics]", "severity": "medium", "phase": "2"}
```

**Типы записей:**
- `false_positive` — скилл нашёл проблему которой нет
- `false_negative` / `missing_detection` — скилл пропустил реальную проблему
- `template_mismatch` — template не подходит для этого типа проекта
- `ux_issue` — сообщение непонятно или вводит в заблуждение
- `error` — инструмент упал или вёл себя неожиданно
- `suggestion` — идея как улучшить template или скилл

**Severity:** `high` (блокирует использование), `medium` (мешает), `low` (косметика)

**Пиши по ходу — не в конце.** Каждое наблюдение сразу, пока контекст свежий.

### Pre-seeded entries (известные gaps до начала работы)

Добавь эти записи в harvest сразу при создании файла:

```jsonl
{"type": "suggestion", "template": "client_project", "suggestion": "add `docs-lint plan --apply` command: scans repo, compares actual file positions to expected (by template + naming rules), outputs proposed `git mv` list in reviewable diff format (old → new), executes via git mv with --apply flag. Enables one-shot file relocation after human review instead of manual git mv commands.", "severity": "high", "phase": "pre"}
{"type": "false_positive", "template": "client_project", "finding_message": "missing template dir: docs/deliverables/ (template: client_project)", "context": "project uses root-level deliverables/ for HTML artifacts — docs/deliverables/ is not part of this project's architecture and was not planned", "expected": "no finding — template should not require docs/deliverables/ when deliverables/ exists at root with different semantics", "severity": "high", "phase": "pre"}
```

---

## Финальный отчёт (в конце сессии)

В конце добавь в лог `docs-lint-skill-log.md`:

```markdown
## 6. Summary for skill improvement

### Harvest file
Path: docs/superpowers/plans/docs-lint-harvest.jsonl
Total entries: N
By type: false_positive: N, template_mismatch: N, suggestion: N, ...

### Top findings (high severity)
<3-5 самых важных наблюдения своими словами>

### Template fit score: client_project → X/5
<обоснование>

### Recommended next iteration
<что менять в первую очередь в скилле>
```

---

## Return

Когда всё выполнено, сообщи:
- Статус каждой из 9 задач плана
- Путь к лог-файлу
- Топ-3 наблюдения для улучшения скилла
- Финальный статус doctor (ok / warning / error)
