---
name: handoff
description: Use when ending a session, saving work status, or when context window is nearing limits. Triggers on "handoff", "save status", "session end", "сохрани статус", or when context is running low. Paired with h2t-dev-session-start for session load., 'h2t:handoff'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.1.0
---

# Инструкции

Когда skill вызывается, PreToolUse hook уже собрал факты через gather.py. Используй данные из hook, напиши session file в правильную директорию, пост GitHub comment.

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
```

## Процедура

### Step 1: Use Gathered Data (DO NOT HALLUCINATE)

**CRITICAL: Only write what you can verify.**

The PreToolUse hook already ran gather.py. Look for `GATHER_DATA:` in the hook output or system messages. It contains JSON with:
- `project.domain`, `project.id` — project identity
- `git.branch`, `git.status`, `git.log` — repo state
- `machine` — hostname
- `_handoff.session_dir` — **the correct directory for the session file**

If you see `GATHER_ERROR:` — show the error and stop.

**Do NOT run git, gh, or gather commands manually.** All data is already collected. Empty fields mean no data exists.

**Scope:** "What Was Done" describes THIS SESSION only. Use conversation context, not `git diff HEAD~N`.

Read the TodoWrite task list if it exists. Check for open tasks.

### Step 2: Determine Session Name

If `SESSION_NAME` was set during `h2t:dev-session-start`, use it.

If not (session started without `/session-start`), derive from:
- Current branch name, OR
- Primary issue worked on, OR
- Ask user: "Как назвать эту сессию? Предлагаю: `{slug}`"

Format: `{task-slug}-{YYYY-MM-DD}` (e.g., `phase5-blocktype-2026-03-11`)

### Step 3: Write Session File

**Location:** Use `_handoff.session_dir` from GATHER_DATA — this is the pre-computed correct path.

```bash
# _handoff.session_dir from hook, e.g. ~/.dor/sessions/automata/h2t-ai
SESSION_DIR="{_handoff.session_dir from GATHER_DATA}"
mkdir -p "$SESSION_DIR"
```

**NEVER write to the project directory.** The path MUST start with `~/.dor/sessions/`.

```markdown
# Session: {session-name}

## Meta
- **Date:** YYYY-MM-DD
- **Branch:** {branch}
- **Last commit:** {hash} {message}
- **Uncommitted:** {yes/no, list if yes}
- **Issues:** #{N}, #{M}
- **Session ID:** {extracted from jsonl path}
- **Resume:** `claude --resume {session-id}`

## What Was Done
- {completed item 1}
- {completed item 2}

## What Remains
- [ ] {next task 1}
- [ ] {next task 2}

## Key Decisions
- {decision}: {rationale}

## Critical Context
{anything the next session MUST know to avoid mistakes}
```

### Rules

- **Max 60 lines.** Handoff is a summary, not a journal.
- **No duplication.** Don't repeat CLAUDE.md or MEMORY.md. Reference them.
- **Verify before writing.** Every path, hash, value must come from gather output or a tool call.
- **Uncommitted work is critical.** List every modified file from `git.status`.
- **Remaining tasks are actionable.** Specific enough to start immediately.
- **Include issue numbers.** Every task links to a GitHub issue.

### Step 4: Post GitHub Comment

For each issue worked on in this session:

```bash
MEMORY_DIR="<memory_dir>"
PROJECT_DIR=$(dirname "$MEMORY_DIR")
SESSION_ID=$(basename $(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null | head -1) .jsonl 2>/dev/null)

gh issue comment {NUMBER} --body "🤖 Handoff: {session-name}
Resume: claude --resume ${SESSION_ID}
File: ~/.dor/sessions/$MACHINE/$REPO/{session-name}.md
Status: {brief — what's done, what remains}"
```

If context ran out (not end of work), note in comment:
```
Status: Context limit reached. Work continues in next session.
```

### Step 4.5: Close Session in Registry

```bash
REGISTRY_PY="$HOME/.h2t/config/registry/registry.py"
[ ! -f "$REGISTRY_PY" ] && REGISTRY_PY="/c/dev/config/registry/registry.py"

if [ -f "$REGISTRY_PY" ] && [ -n "$SESSION_ID" ]; then
  $H2T_PYTHON "$REGISTRY_PY" update \
    --id "$SESSION_ID" \
    --status "done" \
    --summary "{one-line summary of what was accomplished}"
fi
```

For interrupted sessions (context limit, not end of work):
```bash
  $H2T_PYTHON "$REGISTRY_PY" update \
    --id "$SESSION_ID" \
    --status "interrupted" \
    --summary "{what remains}"
```

If registry.py not found or no .jsonl exists, skip silently.

## Session ID Extraction

```bash
MEMORY_DIR="<memory_dir>"
PROJECT_DIR=$(dirname "$MEMORY_DIR")
SESSION_ID=$(basename $(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null | head -1) .jsonl 2>/dev/null)
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing values from memory | Use GATHER_DATA from hook — verify everything |
| Running git/gh/gather manually | Hook already collected all data |
| 100+ line handoff | Cut to 60 max. Reference docs, don't repeat |
| Vague remaining tasks | Be specific: "Implement blockType field (#38)" not "continue work" |
| Missing issue numbers | Every task and decision links to an issue |
| Forgetting GitHub comment | Traceability is lost — always post handoff comment |
| Overwriting existing session file | Check if file exists, append date suffix if needed |
| Including previous session work | "What Was Done" = THIS session only |
| Writing to project root | Session files go to `~/.dor/sessions/` — NEVER to project directory |
