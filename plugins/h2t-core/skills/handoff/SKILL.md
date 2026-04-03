---
name: handoff
description: Use at the end of any working session. Records what was done, what remains, and artifacts produced. Triggers on "handoff", "завершить сессию", "конец сессии", "wrap up".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.0.0
---

# Handoff v3

## Setup

```bash
WRITER="${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Confirm session name

Ask if not already known:
```
Имя сессии этой работы? (или нажми Enter для auto: `{domain}-{project}-YYYY-MM-DD`)
```

Store as SESSION_NAME.

### Step 2: Collect what was done

Ask the user:
```
Что было сделано? (bullet points или свободный текст)
```

Store as WHAT_DONE.

### Step 3: Collect what remains

Ask the user:
```
Что остаётся? (следующие шаги или "ничего")
```

Store as WHAT_REMAINS.

### Step 4: Collect artifacts

List artifacts produced this session. Format each as `type:ref`:
- Commits: `commit:{sha7}`
- Issues closed: `issue:{number}`
- Files created: `file:{path}`
- PRs opened: `pr:{number}`

Build ARTIFACT_LIST from session context (git log, closed issues, etc.).

### Step 5: Write handoff

Substitute SESSION_NAME, DOMAIN, PROJECT_ID, WHAT_DONE, WHAT_REMAINS, and artifact list:

```bash
$H2T_PYTHON "$WRITER" write \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>" \
  --what-done "<WHAT_DONE>" \
  --what-remains "<WHAT_REMAINS>" \
  --artifacts <ARTIFACT_LIST>
```

Replace all `<...>` placeholders with literal values from memory (not shell variables).

### Step 6: Confirm

Show result:
```
✓ Сессия <SESSION_NAME> сохранена
✓ Activity stream: {spool_path}
✓ Markdown: {markdown_path}
✓ Артефактов: {N}
```
