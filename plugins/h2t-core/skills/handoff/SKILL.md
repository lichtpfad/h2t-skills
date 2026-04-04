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

If SESSION_NAME is already known from this conversation — use it directly.

Otherwise propose auto-name and wait for confirmation:
```
Имя сессии: `{domain}-{project}-{topic}-YYYY-MM-DD`
(y/ok/. — принять, или введи своё)
```

Store as SESSION_NAME.

### Step 2: Auto-generate what was done

DO NOT ask the user. Reconstruct from:
1. Conversation history — what was implemented, fixed, discussed
2. `git log --oneline -20` for current repo — recent commits this session
3. Files created or modified visible in context

Write 3–7 bullet points in Russian. Be specific: what changed, not process.

Store as WHAT_DONE.

### Step 3: Auto-generate what remains

DO NOT ask the user. Infer from:
1. Open issues mentioned in this conversation
2. TODOs or next steps discussed but not completed
3. Known blockers or pending decisions from conversation

Write 2–5 bullet points. If nothing clear — write "Нет явных следующих шагов."

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
