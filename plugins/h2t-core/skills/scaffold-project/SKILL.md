---
name: h2t-core:scaffold-project
description: >
  Create and register a new project in h2t ecosystem via interactive wizard.
  Triggers on "/scaffold-project", "scaffold", "новый проект", "new project".
  After creation: calls docs-init with explicit --repo-root, writes docs-lint
  template config, writes a machine-readable setup report, installs on-stop
  hook into .claude/settings.json. After GitHub creation: syncs labels via
  docs-sync-labels. NOT for registering existing repos (use
  /h2t-core:init-project for that).
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

You are the wizard. Ask the user questions in natural conversation, then run the scaffolding.
No UI framework — just Claude asking questions and acting on answers.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"

SCAFFOLD="$CLAUDE_PLUGIN_ROOT/skills/scaffold-project/scripts/scaffold_project.py"
APPLY_REG="$CLAUDE_PLUGIN_ROOT/skills/init-project/scripts/apply_registration.py"
CONFIG_ROOT="$HOME/.h2t/config"
```

---

## Step 1: Collect Identity

Ask in a single prompt (user can answer inline or line-by-line):

```
Создаём новый проект. Ответь на несколько вопросов:

1. **ID проекта** — kebab-case, станет именем директории (напр. h2t-voice, my-tool)
2. **Домен** — в каком домене живёт проект?
   Доступные: personal-os | dev | hou2touch | crypto | life
3. **Тип:**
   - `code-github` — Git-репо + GitHub
   - `code-local` — Git-репо, без GitHub
   - `docs` — документация/исследование (без кода)
   - `dcc` — TouchDesigner / Houdini проект
   - `directory` — просто директория без git
4. **Stack** (только для code): python | js | ts | rust | none
5. **Краткое описание** (1 строка, для README и CLAUDE.md)
```

Parse the user's answer. Ask follow-up only for any missing required fields.
- For non-code types, skip the stack question.
- For `dcc` type, stack = "none".

---

## Step 2: Confirm Base Directory

Ask: "Где создать директорию? (по умолчанию: C:/dev/{id})"

Accept:
- Enter / `.` / `да` → use `C:/dev/{id}`
- A path → use that path exactly (e.g. `C:/work/new-thing`)

Resolve the final path: if user gave a relative path, prepend `C:/dev/`.

---

## Step 3: Dry-Run Preview (GATE)

Run:

```bash
$H2T_PYTHON "$SCAFFOLD" create \
  --id "{id}" --type "{type}" --stack "{stack}" \
  --dir "{base_dir}" --description "{description}" \
  --dry-run
```

Show the `would_create` list from JSON output as a bullet list.

Then ask: "Создаём? (y / да / .)"

**Do NOT proceed until user confirms.**

---

## Step 4: Create Structure

Run (without --dry-run):

```bash
$H2T_PYTHON "$SCAFFOLD" create \
  --id "{id}" --type "{type}" --stack "{stack}" \
  --dir "{base_dir}" --description "{description}"
```

Parse JSON. If `"status": "error"` — show error and stop.

Show actions list as checkmarks. Note `"path"` from JSON — this is the project root.

---

## Step 5: Register in h2t Ecosystem

Determine task tracker:
- `code-github` → ask: "Task tracker: github или none?"
- `code-local`, `docs`, `directory` → tracker = "none"
- `dcc` → tracker = "none"

Determine `--github` arg:
- `code-github` → set `github_slug = "{github_owner}/{id}"`. Ask: "GitHub owner? (по умолчанию: lichtpfad)"
- All others → omit `--github`

Run:

```bash
$H2T_PYTHON "$APPLY_REG" \
  --id "{id}" --domain "{domain}" --type "{reg_type}" \
  --label "{label}" --task-tracker "{tracker}" \
  --cwd "{project_path}" --config-root "$CONFIG_ROOT" \
  [--github "{github_slug}"] \
  [--stack "{stack}"]
```

Where:
- `{label}` = human-readable name (capitalised id by default, user can override)
- `{reg_type}` = `git` for code-github, `git-local` for code-local, `directory` for others

Show `actions` and `next_steps` from JSON output.

---

## Step 6: GitHub Remote (code-github only)

Ask: "Создать GitHub repo `{github_slug}`? (public/private/skip)"

If public or private:

```bash
$H2T_PYTHON "$SCAFFOLD" github \
  --github "{github_slug}" \
  --description "{description}" \
  --source "{project_path}" \
  [--private]
```

If error → show it but continue.

If skip → remind: "Создай вручную и добавь remote: `git remote add origin git@github.com:{github_slug}.git`"

---

## Step 7: GitHub Milestones & Labels (code-github only, optional)

Ask: "Создать начальные milestones? Введи названия через запятую (или skip):"

If user provides names:

```bash
for milestone in {milestones}; do
  gh milestone create --title "$milestone" --repo "{github_slug}"
done
```

Labels are set from `~/.h2t/config/labels.json` if the file exists:

```bash
# Apply canonical labels
gh label list --repo "{github_slug}" --json name | \
  $H2T_PYTHON -c "
import json,sys,subprocess
existing = {x['name'] for x in json.load(sys.stdin)}
labels = json.load(open('$CONFIG_ROOT/../../../docs/standards/labels.json' if False else '$HOME/.h2t/config/docs/standards/labels.json', encoding='utf-8'))
# fallback: skip if labels.json not found
" 2>/dev/null || true
```

Actually — skip automatic label apply for now. Just tell user:
"Запусти `/h2t-dev:docs-sync-labels` в новом репо для применения канонических labels."

---

## Step 8: Confirm Ready

Show:

```
✓ Проект создан: {project_path}
✓ Зарегистрирован: {domain}/{id}
[✓ GitHub: https://github.com/{github_slug}]

Открыть сессию в новом проекте?
```

If yes → instruct: "Открой Claude Code в `{project_path}` и запусти `/h2t-core:session-start`"
(Cannot auto-switch cwd in current session.)

---

## Error Handling

| Situation | Action |
|-----------|--------|
| `scaffold_project.py` not found | Show: "SCAFFOLD_ERROR: script not found at $SCAFFOLD. Run `/h2t-core:setup`" |
| `apply_registration.py` error | Show error, ask: "Зарегистрировать вручную через `/h2t-core:init-project` позже?" |
| `gh` not found | Skip GitHub steps, remind to install `gh` CLI |
| Directory already exists | Show warning, ask: "Директория уже существует. Продолжить (дополнить) или выбрать другой путь?" |
