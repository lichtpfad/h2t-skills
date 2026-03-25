---
name: dev-session-start
description: Use when starting a coding or product development session. Triggers on "/session-start", "начинаем работу", "start session", "new session", or at the beginning of any development conversation. NOT for non-coding sessions (personal, management, psychology)., 'h2t:dev-session-start'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.7.0
---

# Instructions

When this skill is invoked, dispatch a subagent to gather context, show the briefing, name the session, post a GitHub comment.

**Paired with:** `h2t:handoff` (SAVE at end) — this skill is LOAD at start.

**NOT for:** personal OS, management, psychology, non-dev conversations.

## Variables

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t:setup" && exit 1

GATHER="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/gather.py"
```

## Procedure

### Step 1: Gather Context (via subagent)

Dispatch agent:
- subagent_type: `h2t:session-gatherer`
- model: haiku
- prompt: include the resolved values of GATHER and cwd:

"Gather project context and return formatted session briefing.
gather_cmd: {resolved GATHER value}
cwd: {resolved pwd value}"

### Step 2: Show Briefing

Display the agent's response verbatim to the user.
The agent's response IS the briefing — no reformatting needed.
If response starts with "ERROR:" — show the error and stop.
Do NOT ask questions in this step.

### Step 3: Name Session + Choose Direction

⛔ **MANDATORY GATE** — Do NOT skip. Handoff file paths depend on session name.

Session slug template:
```
{project}-{milestone}-{layer-task}-{date}-{starttime}
```

| Segment | Format | Example |
|---------|--------|---------|
| `project` | short repo name | `crypto` |
| `milestone` | milestone prefix | `m4` |
| `layer-task` | layer + task type | `l10-annotations` |
| `date` | YYYY-MM-DD | `2026-03-13` |
| `starttime` | HHMM (24h local) | `1430` |

If no milestone applies, omit it: `crypto-annotation-fix-l7-l9-2026-03-13-1015`

**Output — propose BOTH name and direction in one message:**

```
Предлагаю имя сессии: `{slug}` (из issue #{N})
Корректируй если нужно.

Продолжить с задачей #{N} ({title}), или другое направление?
```

Wait for user response. Store confirmed name as `SESSION_NAME`.

### Step 4: Post GitHub Comment + Register Session

```bash
SESSION_ID=$(basename $(ls -t ~/.claude/projects/*/$(basename $(pwd))/*.jsonl 2>/dev/null | head -1) .jsonl 2>/dev/null)

gh issue comment {NUMBER} --body "Session: {SESSION_NAME}
Resume: claude --resume ${SESSION_ID}
Handoff: ~/.dor/sessions/{machine}/{repo}/{SESSION_NAME}.md"
```

```bash
REGISTRY_PY="$HOME/.h2t/config/registry/registry.py"
[ ! -f "$REGISTRY_PY" ] && REGISTRY_PY="/c/dev/config/registry/registry.py"

MACHINE="${DOR_MACHINE_NAME:-$(hostname | tr '[:upper:]' '[:lower:]' | cut -d. -f1)}"

# SESSION_ID already extracted above — reuse the same value
if [ -f "$REGISTRY_PY" ] && [ -n "$SESSION_ID" ]; then
  $H2T_PYTHON "$REGISTRY_PY" append --id "$SESSION_ID" --cwd "$(pwd)" --host "$MACHINE"
  $H2T_PYTHON "$REGISTRY_PY" update \
    --id "$SESSION_ID" \
    --status "active" \
    --session-name "{SESSION_NAME}" \
    --topic "{user-provided topic}" \
    --task-issue "#{NUMBER}" \
    --task-title "{issue title}"
fi
```

If registry.py not found or no .jsonl exists, skip silently.

Create TodoWrite tasks from chosen work items.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running git/gh manually instead of dispatching agent | Step 1 is agent dispatch ONLY |
| Reformatting agent response | Show verbatim — agent already formatted it |
| Asking questions before naming | Step 2 is data-only. Questions go in Step 3 GATE |
| Start coding without naming session | Name first — handoff path depends on it |
| Guess session ID | Extract from actual jsonl file path in Step 4 |
