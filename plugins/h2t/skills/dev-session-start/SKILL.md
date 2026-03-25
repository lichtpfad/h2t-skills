---
name: dev-session-start
description: Use when starting a coding or product development session. Triggers on "/session-start", "начинаем работу", "start session", "new session", or at the beginning of any development conversation. NOT for non-coding sessions (personal, management, psychology)., 'h2t:dev-session-start'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.8.0
---

# Instructions

When this skill is invoked, the PreToolUse hook has already run gather.py. Use the gathered data to build and show a session briefing, name the session, post a GitHub comment.

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

### Step 1: Use Gathered Data

The PreToolUse hook already ran gather.py before this skill loaded. Look for `GATHER_DATA:` in the hook output or system messages from this conversation. It contains a JSON object with:
- `project.id`, `project.domain`, `git.branch`, `git.status`, `git.log`
- `github.issues`, `github.milestones`, `github.current_milestone`, `github.prs`, `github.bugs`
- `stack.name`, `sessions`, `machine`

If you see `GATHER_ERROR:` instead — show the error to the user and stop.

**Do NOT run git, gh, or any other gather commands manually.** All data is already collected. Empty fields (`[]`, `""`, `null`) mean no data exists for that category — this is normal for small or new repos. Do NOT attempt to fill empty fields with manual commands.

Also read:
- Session handoff files listed in `sessions[]` (max 2 most recent, key decisions only)
- User context from `user.core_path` if present
- `<memory_dir>/MEMORY.md` for stable lessons

### Step 2: Show Briefing

Format and display the briefing. Do NOT ask questions in this step.

```markdown
## Project: {project.id} ({git.branch})

**Stack:** {stack.name}
**Milestone:** {github.current_milestone.title} — {open}/{total} issues

### Open Tasks (from GitHub)
- P0: #{N} {title}...
- Bugs: #{N} {title}...

### Uncommitted Work
{git.status or "clean"}

### Open PRs
{github.prs or "none"}

### Context from last session
{key decisions from handoff files — omit if none}
```

**Rules:**
- GitHub issues are source of truth. Never copy "What Remains" from handoff as tasks.
- If handoff mentions a now-closed issue — omit it.
- Context section is optional — only include if non-obvious decisions exist.

**Actionable hints for missing data** — append to briefing when applicable:

| Condition | Hint |
|-----------|------|
| `project.id == "unknown"` | "Repo not registered. Add to `~/.h2t/config/repo-mapping.yaml` for project identity." |
| `github.issues == []` and repo has GitHub | "No open issues. Create with `/h2t:github-issues` or `gh issue create`." |
| `sessions == []` | "No previous sessions found. This is a fresh start." |
| `stack.name == "none"` | "Stack not detected. Add `pyproject.toml`, `package.json`, or `Cargo.toml` if applicable." |
| No CLAUDE.md in project root | "No CLAUDE.md found. Run `/init` to set up project instructions." |

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
| Running git/gh/gather manually | Hook already collected all data. Use GATHER_DATA from system messages |
| Ignoring GATHER_DATA in system messages | The hook output IS the data source. Parse and use it |
| Asking questions before naming | Step 2 is data-only. Questions go in Step 3 GATE |
| Start coding without naming session | Name first — handoff path depends on it |
| Guess session ID | Extract from actual jsonl file path in Step 4 |
| Trust handoff "What Remains" as task list | Use GitHub open issues — handoff is a stale snapshot |
