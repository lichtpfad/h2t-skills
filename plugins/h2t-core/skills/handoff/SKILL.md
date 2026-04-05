---
name: handoff
description: Use at the end of any working session. Records what was done, what remains, and artifacts produced. Triggers on "handoff", "завершить сессию", "конец сессии", "wrap up".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.1.0
---

# Handoff v3.1

## Setup

```bash
WRITER="${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Confirm session name

If SESSION_NAME is already known from this conversation — use it.
Otherwise use auto: `{domain}-{project}-YYYY-MM-DD`.

### Step 2: Auto-generate what was done

```bash
git log --oneline --since="$(date -d '1 day ago' +%Y-%m-%d)" 2>/dev/null || git log --oneline -10
```

From git log + conversation context, generate a bullet list of what was accomplished this session.
Store as WHAT_DONE.

### Step 3: Auto-generate what remains

From open GitHub issues (P1 first), unfinished topics from conversation context.
Store as WHAT_REMAINS.

### Step 4: Collect artifacts

Build ARTIFACT_LIST from session context:
- Commits: `commit:{sha7}`
- Issues closed: `issue:{number}`
- Files created: `file:{path}`
- PRs opened: `pr:{number}`

### Step 5: Show summary to user

Display before writing:

```
## Handoff: {SESSION_NAME}

### Что сделано
{WHAT_DONE}

### Что передаём в следующую сессию
{WHAT_REMAINS}

### Артефакты
{ARTIFACT_LIST}
```

⛔ GATE — Do NOT proceed to Step 6 until user confirms or corrects.

### Step 6: Write handoff

```bash
$H2T_PYTHON "$WRITER" write \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>" \
  --what-done "<WHAT_DONE>" \
  --what-remains "<WHAT_REMAINS>" \
  --artifacts <ARTIFACT_LIST>
```

Replace all `<...>` with literal values (not shell variables).

### Step 7: Confirm

```
✓ Сессия <SESSION_NAME> сохранена
✓ Activity stream: {spool_path}
✓ Markdown: {markdown_path}
✓ Артефактов: {N}
```
