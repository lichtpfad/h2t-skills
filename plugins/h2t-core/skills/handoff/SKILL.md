---
name: handoff
description: This skill should be used when the user says "handoff", "завершить сессию", "конец сессии", "wrap up", "закончим", "сохрани сессию", or asks to close/end the current working session. Reconstructs what was done and what remains from conversation context and git history, shows a summary for confirmation, then writes the session record.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.1.1
---

# Handoff v3.1

## Setup

```bash
WRITER="${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Establish session context

Resolve these values from conversation context:
- `SESSION_NAME` — from session-start confirmation if run this session, otherwise propose `{domain}-{project}-{topic}-YYYY-MM-DD` and wait for `y`/`ok`/`.`/alternative
- `DOMAIN` — from GATHER_RESULT.project.domain (session-start output), fallback: `personal-os`
- `PROJECT_ID` — from GATHER_RESULT.project.id (session-start output), fallback: current repo name

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

Write 2–5 items as **checkboxes** (`- [ ] ...`). If nothing clear — write `- [ ] Нет явных следующих шагов.`
Store as WHAT_REMAINS.

### Step 4: Collect artifacts

Build ARTIFACT_LIST from session context:
- Commits: `commit:{sha7}`
- Issues closed: `issue:{number}`
- Files created: `file:{path}`
- PRs opened: `pr:{number}`

### Step 5: Show summary to user

Display before writing. **Follow the format from `references/handoff-example.md` exactly** — use `##` for session name, `###` for sections, bullet list for "Что сделано", checkboxes (`- [ ]`) for "Что передаём", dash list for "Артефакты".

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

## Graph Integration

### Query (optional — if handoff structure or step behavior is unclear)

```bash
SKILL_GRAPH_DIR="${SKILL_GRAPH_DIR:-C:/dev/claude-agent-skills/lib}"
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli query \
  --context "handoff: session summary, what-done reconstruction, what-remains inference" \
  --skill "handoff") 2>/dev/null || true
```

If results contain relevant patterns or lessons, apply them before proceeding.

### Add Lesson (after resolving unexpected behavior in this skill)

```bash
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli add-lesson \
  --skill "handoff" \
  --trigger "<what broke or caused confusion>" \
  --resolution "<what fixed it>" \
  --session-id "$SESSION_NAME") 2>/dev/null || true
```
