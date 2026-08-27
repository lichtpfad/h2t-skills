---
name: session-start
description: "Use at the start of any working session (dev, creative, personal). Triggers on 'start session', 'начинаем', 'новая сессия'. Do not invoke again while already executing session-start."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.0.12
---

# Session Start v3

> ⚠️ **If you are already executing the session-start pipeline, STOP. Do NOT invoke this skill again. Return to the pipeline you were following.**

## Setup

```bash
command -v h2t-gather >/dev/null 2>&1 || {
  echo "ERROR: h2t-gather not found. From a checkout: uv tool install --editable ."
  exit 1
}
command -v h2t-activity-log >/dev/null 2>&1 || {
  echo "ERROR: h2t-activity-log not found. From a checkout: uv tool install --editable ."
  exit 1
}
```

## Pipeline

### Step 1: Collect context

**Check your system context first.** The PreToolUse hook may have already run gather and injected data as:
```
BRIEFING:
<briefing text>

GATHER_META: <json>
```

If `BRIEFING:` is present in your system context:
- Extract the text between `BRIEFING:\n` and `\n\nGATHER_META:` as `_briefing`
- Parse `GATHER_META` JSON as `GATHER_RESULT._meta`
- Parse `GATHER_META.project`, `GATHER_META.sessions`, `GATHER_META.machine` fields
- **Skip running gather.py** — data is already collected

If `BRIEFING:` is NOT in your context, run:

```bash
h2t-gather --cwd "$(pwd)" --briefing-only
```

This prints the **same `BRIEFING:` / `GATHER_META:` format** the hook injects — parse it
exactly as above (text between `BRIEFING:\n` and `\n\nGATHER_META:` → `_briefing`;
`GATHER_META` JSON → `GATHER_RESULT._meta`, with `.project` / `.sessions` / `.machine`).

⛔ The output is already in your context. Read `_briefing` and the `GATHER_META` fields
**directly** from it. Do NOT pipe, grep, `Select-String`, `jq`, or run `python`/`h2t-python`
on it — those are a Windows cp1252 / wrong-shell trap and produce nothing the plain output
doesn't already give you. One command, then read.

### Step 2: Show briefing

⛔ **STRICT: Copy the briefing text EXACTLY as-is. Zero additions.**

- Do NOT add VPS status
- Do NOT add blockers
- Do NOT add memory from previous sessions
- Do NOT reformat or restructure
- Do NOT add commentary before or after

Display `_briefing` verbatim.

If `_briefing` is missing: show `GATHER_ERROR — no briefing in output. Check plugin version.`

### Step 3: Previous-session context

Do not read handoff markdown by default.

The briefing already includes a bounded `### Previous Session` section when
`GATHER_RESULT.latest_session` is available. Full handoff markdown is archival
context and may be read only if the user explicitly asks for details.

If `GATHER_RESULT.sessions` is non-empty but `GATHER_RESULT.latest_session` is
missing, show one short line:

```
Есть архивные handoff-файлы, но нет bounded latest summary. Продолжаю без чтения markdown.
```

If both are empty: skip this step silently.

**Active autonomous-run check** (spec `autonomous-run` § Resume trigger, mechanism-1) — run
this separately from the verbatim briefing, so an unfinished run resumes across compaction:

```bash
_RB=$(ls -t docs/superpowers/plans/*-runbook.md 2>/dev/null | head -1)
[ -n "$_RB" ] && grep -q '^- \[ \] \*\*' "$_RB" && echo "ACTIVE_RUNBOOK: $_RB"
```

If it prints `ACTIVE_RUNBOOK: <path>`, surface exactly one line and offer to resume:
`Незавершённый автономный прогон: <path> → autonomous-run resume <path>`. Otherwise skip.

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
h2t-activity-log start \
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
