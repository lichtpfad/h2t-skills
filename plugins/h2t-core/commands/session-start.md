---
description: "Use at the start of any working session (dev, creative, personal). Triggers on 'start session', 'начинаем', 'новая сессия'."
---

# Session Start v3

## Setup

```bash
GATHER="${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py"
ACTIVITY_LOG="${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Collect context

Run this command:

```bash
$H2T_PYTHON "$GATHER" --format-briefing
```

Parse the full JSON output as GATHER_RESULT.

### Step 2: Show briefing

Display `GATHER_RESULT._briefing` verbatim — no reformatting, no commentary.

If `_briefing` is missing: show `GATHER_ERROR — no briefing in output. Check plugin version.`

### Step 3: Read last handoff

If `GATHER_RESULT.sessions` is non-empty:
- Read the file at path `GATHER_RESULT.sessions[0]` using the Read tool
- Show section **"## What Remains"** verbatim under header `### Продолжение предыдущей сессии`
- If no "What Remains" section: show first 40 lines of the file

If `GATHER_RESULT.sessions` is empty: skip this step silently.

### Step 4: ⛔ GATE — Session naming

Propose session name in this exact format:
```
Имя сессии: `{domain}-{project}-{topic}-YYYY-MM-DD`

Пример: `dev-h2t-ai-skill-refactor-2026-04-03`
```

Replace `{topic}` with 1-2 word summary of most likely work direction from context.

Wait for user input. Accept:
- The proposed name verbatim → use it
- An alternative name → use that instead
- `y` / `да` / `ok` / `.` → use the proposed name as-is

**Do NOT proceed to Step 5 until user responds.**

### Step 5: Log session start

Substitute literal values from GATHER_RESULT and run:

```bash
$H2T_PYTHON "$ACTIVITY_LOG" start \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>"
```

Where:
- `<SESSION_NAME>` = confirmed session name from Step 4
- `<DOMAIN>` = `GATHER_RESULT.project.domain`
- `<PROJECT_ID>` = `GATHER_RESULT.project.id`

### Step 6: Check registration

If `GATHER_RESULT.project.registered` is `false` or `null`: invoke `h2t-core:init-project`.

Otherwise: skip this step.

### Step 7: Confirm ready

Show exactly:
```
✓ Сессия: {SESSION_NAME}
✓ Контекст загружен ({N} issues, {branch})

Что делаем?
```

Fill `N` and `branch` from GATHER_RESULT.
