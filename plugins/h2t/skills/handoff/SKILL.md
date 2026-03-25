---
name: handoff
description: Use when ending a session, saving work status, or when context window is nearing limits. Triggers on "handoff", "save status", "session end", "сохрани статус", or when context is running low. Paired with h2t-dev-session-start for session load., 'h2t:handoff'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Session Handoff (SAVE)

Save development session state for later resumption. Write session file, post GitHub comment, preserve traceability.

**Paired with:** `h2t:dev-session-start` (LOAD at start) — this skill is SAVE at end.

**When to SAVE:** End of work session, context window nearing limits, switching to different task.

## Procedure

```dot
digraph handoff_save {
  "Trigger: /handoff" [shape=doublecircle];
  "1. Gather facts" [shape=box];
  "2. Determine session name" [shape=box];
  "3. Write session file" [shape=box];
  "4. Post GitHub comment" [shape=box];
  "Done" [shape=doublecircle];

  "Trigger: /handoff" -> "1. Gather facts";
  "1. Gather facts" -> "2. Determine session name";
  "2. Determine session name" -> "3. Write session file";
  "3. Write session file" -> "4. Post GitHub comment";
  "4. Post GitHub comment" -> "Done";
}
```

### Step 1: Gather Facts (DO NOT HALLUCINATE)

**CRITICAL: Only write what you can verify.**

**Gathered context (auto-collected):**

!`H2T_PYTHON="${H2T_PYTHON:-}"; [ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"; [ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"; [ -z "$H2T_PYTHON" ] && H2T_PYTHON="python3"; $H2T_PYTHON "${CLAUDE_SKILL_DIR}/gather.py" --cwd "$(pwd)" 2>/dev/null || echo '{"error": "gather.py failed"}'`

The JSON above contains all project context: `project` (identity, domain), `git` (branch, status, log), `session_id`, `machine`. Use this data — do NOT run git/gh commands to re-collect it.

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

**Location:** `~/.dor/sessions/{machine}/{repo}/{session-name}.md`

Determine path:

```bash
MACHINE="${DOR_MACHINE_NAME:-$(hostname | tr '[:upper:]' '[:lower:]' | cut -d. -f1)}"
REPO=$(basename "$(git remote get-url origin 2>/dev/null)" .git 2>/dev/null || basename "$(pwd)")
SESSION_DIR="$HOME/.dor/sessions/$MACHINE/$REPO"
mkdir -p "$SESSION_DIR"
```

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
- **Verify before writing.** Every path, hash, value must come from a tool call.
- **Uncommitted work is critical.** List every modified file from `git status`.
- **Remaining tasks are actionable.** Specific enough to start immediately.
- **Include issue numbers.** Every task links to a GitHub issue.

### Step 4: Post GitHub Comment

For each issue worked on in this session:

```bash
# Extract session ID
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

Extract session ID from current .jsonl file, then close registry entry:

```bash
REGISTRY_PY="$HOME/.h2t/config/registry/registry.py"
[ ! -f "$REGISTRY_PY" ] && REGISTRY_PY="/c/dev/config/registry/registry.py"

# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && H2T_PYTHON="python3"

MEMORY_DIR="<memory_dir>"
PROJECT_DIR=$(dirname "$MEMORY_DIR")
SESSION_ID=$(basename $(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null | head -1) .jsonl 2>/dev/null)

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

## Migration from Legacy

If `<memory_dir>/sessions/*.md` exists (old repo-local format):
1. Determine new path: `~/.dor/sessions/$MACHINE/$REPO/`
2. Move files there
3. Remove `<memory_dir>/sessions/` if empty

If `<memory_dir>/handoff.md` exists (very old format):
1. Read it
2. Move content to `~/.dor/sessions/$MACHINE/$REPO/{derived-name}.md`
3. Delete `handoff.md`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing values from memory | Run `git status`, `git log` first — verify everything |
| 100+ line handoff | Cut to 60 max. Reference docs, don't repeat |
| Vague remaining tasks | Be specific: "Implement blockType field (#38)" not "continue work" |
| Missing issue numbers | Every task and decision links to an issue |
| Forgetting GitHub comment | Traceability is lost — always post handoff comment |
| Overwriting existing session file | Check if file exists, append date suffix if needed |
| Including previous session work | "What Was Done" = THIS session only |
