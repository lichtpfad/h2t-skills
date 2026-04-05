---
name: session-start
description: Use at the start of any working session (dev, creative, personal). Triggers on "start session", "session start", "начинаем", "новая сессия", or at the beginning of any work conversation.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.0.0
---

# Session Start v3

## ⛔ Execution Guard

You are now executing this skill. **DO NOT call `Skill(h2t-core:session-start)` again** at any point.
Follow the steps below directly without re-invoking the skill.
If this skill has already been executed in this conversation (BRIEFING is visible above), skip to the step where you left off.

## Setup

```bash
GATHER="${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py"
ACTIVITY_LOG="${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Collect context

⛔ DO NOT use Search, Glob, or Read tools in this step.

Check the messages already visible above you in this conversation. The hook injects a `PreToolUse:Skill says:` message containing `GATHER_META: {...}` before this skill loads.

**If you can see `GATHER_META:` in a previous message in this conversation:**
- Copy the JSON value after `GATHER_META:` as GATHER_RESULT (it is already in your context)
- Skip the Bash call below

**If you cannot see `GATHER_META:` in any previous message:**
- Run the fallback Bash command:

```bash
$H2T_PYTHON "$GATHER" --format-briefing
```

- Parse the JSON output as GATHER_RESULT

### Step 2: Show briefing verbatim

Extract `_briefing` from GATHER_RESULT. Display it exactly as-is — do not reformat, reorder, or add commentary.

If `_briefing` is missing: show `GATHER_ERROR — no briefing in output. Check plugin version.`

### Step 2.5: Read last handoff

If `GATHER_RESULT.sessions` is non-empty:
- Take `GATHER_RESULT.sessions[0]` (most recent)
- Read the file with the Read tool
- Show section **"## What Remains"** (or equivalent) verbatim under header `### Продолжение предыдущей сессии`
- If no "What Remains" section found: show first 40 lines of the file

If `GATHER_RESULT.sessions` is empty: skip this step silently.

### Step 3: Analyze top issues

From `GATHER_RESULT.github.issues` (if present): select up to 3 issues by priority (P1 > open > recent).

Show as numbered list:
```
1. #N — Title (P1/open/etc.)
2. #N — Title
3. #N — Title
```

If no issues: show "Нет открытых issues."

### Step 4: ⛔ GATE — Session naming

**Do NOT proceed to Step 5 until user confirms.**

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

**Note:** In Claude Code terminal, blank Enter is not possible — user must type something.

### Step 5: Log session start

After user confirms session name (store as SESSION_NAME):

Extract from GATHER_RESULT (you have these values in memory from Step 1):
- `DOMAIN` = `GATHER_RESULT["project"]["domain"]`
- `PROJECT_ID` = `GATHER_RESULT["project"]["id"]`

Substitute the actual values into this command and run it:

```bash
$H2T_PYTHON "$ACTIVITY_LOG" start \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>"
```

Replace `<SESSION_NAME>`, `<DOMAIN>`, `<PROJECT_ID>` with the literal string values (not shell variables — these are LLM-held values substituted at call time).

### Step 6: Check project registration

If `GATHER_RESULT.project.registered` is `false` or `null`: invoke `h2t:init-project` now.

Otherwise: skip this step.

### Step 7: Confirm ready

Show exactly:
```
✓ Сессия: {SESSION_NAME}
✓ Контекст загружен ({N} issues, {branch})

Что делаем?
```

Fill N and branch from GATHER_RESULT.
