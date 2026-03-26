---
name: dev-session-start
description: Use when starting a coding or product development session. Triggers on "/session-start", "начинаем работу", "start session", "new session", or at the beginning of any development conversation. NOT for non-coding sessions (personal, management, psychology)., 'h2t:dev-session-start'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.10.0
---

# Instructions

When this skill is invoked, the PreToolUse hook has already run gather.py and formatted a briefing. Show it, name the session, post a GitHub comment.

**Paired with:** `h2t:handoff` (SAVE at end) — this skill is LOAD at start.

**NOT for:** personal OS, management, psychology, non-dev conversations.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
```

## Procedure

### Step 1: Show Briefing

The PreToolUse hook already formatted the briefing. Look for `BRIEFING:` in hook output or system messages.

**Show it VERBATIM.** Do not modify, supplement, or re-gather any data. Do not run git, gh, or any other commands.

If `BRIEFING:` is missing, look for `GATHER_DATA:` (fallback) and format manually.
If `GATHER_ERROR:` — show the error and stop.

Also read (if paths are present in `GATHER_META`):
- Session handoff files from `sessions[]` (max 2 most recent, key decisions only)
- User context from `user.core_path`
- `<memory_dir>/MEMORY.md` for stable lessons

Append context from handoff/memory after the briefing under "### Контекст прошлых сессий".
Do NOT show this section if there is nothing relevant.

**Rules:**
- GitHub issues are source of truth. Never copy "What Remains" from handoff as tasks.
- If handoff mentions a now-closed issue — omit it.

### Step 2: Name Session + Choose Direction

⛔ **MANDATORY GATE** — You MUST complete this step. Do NOT ask "Что хочешь делать?" without proposing a session name. Do NOT proceed to coding without a confirmed name.

The hook provided `slug_template` in `GATHER_META` with deterministic parts pre-filled:
```
{slug_template}   ← project, milestone, date, time already set
```

You fill `{task}` based on the top-priority issue or user's stated direction. Use 2-4 words, kebab-case.

Examples:
- `agent-skills-{task}-2026-03-26-1430` → `agent-skills-briefing-in-hook-2026-03-26-1430`
- `crypto-p5-{task}-2026-03-26-1015` → `crypto-p5-annotation-layer-2026-03-26-1015`

**Your message MUST contain:**
1. Proposed session name (slug_template with `{task}` filled in)
2. Which issue(s) you suggest working on and why
3. "Корректируй если нужно."

Wait for user response. Store confirmed name as `SESSION_NAME`.

### Step 3: Post GitHub Comment + Register Session

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
| Modifying or supplementing the BRIEFING | Show it verbatim. All data is pre-formatted by the hook |
| Asking "Что хочешь делать?" without session name | Step 2 is a GATE — always propose name first |
| Ignoring slug_template from GATHER_META | Use it — only fill `{task}`, don't rebuild the slug |
| Start coding without naming session | Name first — handoff path depends on it |
| Trust handoff "What Remains" as task list | Use GitHub open issues — handoff is a stale snapshot |
