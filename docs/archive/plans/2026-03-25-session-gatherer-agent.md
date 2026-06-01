---
title: "Session Gatherer Agent — Implementation Plan"
status: "draft"
date: "2026-03-25"
milestone: ""
---
# Session Gatherer Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move gather+format logic from dev-session-start SKILL.md into a haiku subagent so gather.py cannot be ignored.

**Architecture:** New agent `session-gatherer.md` runs gather.py in isolated context and returns formatted briefing. SKILL.md becomes thin orchestrator (~80 lines, down from 216) that dispatches agent, shows result, handles interactive steps.

**Tech Stack:** Claude Code plugin agents (markdown frontmatter), Python gather.py (existing), Bash

**Spec:** `docs/superpowers/specs/2026-03-25-session-gatherer-agent-design.md`

---

### Task 1: Create session-gatherer agent definition

**Files:**
- Create: `plugins/h2t/agents/session-gatherer.md`
- Reference: `plugins/h2t/agents/research-agent.md` (existing agent pattern)

- [ ] **Step 1: Study the existing agent pattern**

Read `plugins/h2t/agents/research-agent.md` for frontmatter format: `name`, `description`, `tools`, and system prompt structure.

- [ ] **Step 2: Write the agent definition**

Create `plugins/h2t/agents/session-gatherer.md`:

```markdown
---
name: session-gatherer
description: "Gathers project context via gather.py and returns formatted session briefing. Used by dev-session-start skill. Do not call directly."
model: haiku
tools:
  - Bash
  - Read
---

You are a context-gathering agent. Your ONLY job: run a command, read files, and return a formatted briefing. No questions, no explanations.

## Input

You receive via dispatch prompt:
- `gather_cmd` — full shell command to run gather.py
- `cwd` — project working directory

## Procedure

### 1. Run gather

Execute the gather command provided in the dispatch prompt. The values of `gather_cmd` and `cwd` are literal strings from the prompt — substitute them directly into this Bash command:

```bash
<gather_cmd value> --cwd "<cwd value>"
```

Example: if gather_cmd is `/c/Users/stani/.h2t/venv/Scripts/python.exe /path/to/gather.py` and cwd is `/c/dev/claude-agent-skills`, run:
```bash
/c/Users/stani/.h2t/venv/Scripts/python.exe /path/to/gather.py --cwd "/c/dev/claude-agent-skills"
```

If the command fails (non-zero exit, no output, invalid JSON):
Return EXACTLY: `ERROR: gather failed — {stderr content}. Run /h2t:setup to diagnose.`
Do NOT attempt to gather context manually. Do NOT run git, gh, or any other commands.

### 2. Parse JSON result

The command outputs a JSON object. Extract these fields:
- `project.id`, `project.domain`
- `git.branch`, `git.status`, `git.log`
- `github.issues`, `github.milestones`, `github.current_milestone`, `github.prs`, `github.bugs`
- `stack.name`
- `sessions` — list of handoff file paths
- `user.core_path`, `user.deep_paths`
- `machine`

### 3. Read supplementary files

**Handoff files:** Read at most 2 most-recent files from `sessions[]`. Extract ONLY:
- "Key Decisions" section
- "Critical Context" section
Skip files older than 30 days. Skip missing files silently.

Do NOT extract "What Remains" — GitHub issues are the source of truth.

**User context:** Read `user.core_path` if the path exists.

### 4. Cross-check handoff vs GitHub

If handoff mentions issue numbers, check them against `github.issues`. If an issue is NOT in the open issues list, it is closed — omit it from the briefing.

### 5. Format and return briefing

Return ONLY the formatted briefing below. No preamble, no explanation, no wrapping.

```
## Project: {project.id} ({git.branch})

**Stack:** {stack.name}
**Milestone:** {github.current_milestone.title} — {open}/{total} issues

### Open Tasks (from GitHub)
{issues grouped by priority labels, format: "- P0: #{N} {title}"}
{bugs with label "bug": "- Bug: #{N} {title}"}
{remaining issues without priority: "- #{N} {title}"}

### Uncommitted Work
{git.status — or "clean" if empty}

### Open PRs
{github.prs — or "none"}

### Context from last session
{key decisions and critical context from handoff files}
{machine: {machine}, date: {handoff file date}}
```

If no handoff files exist or no key decisions found, omit the "Context from last session" section entirely.

## Rules

- NEVER ask questions. Always return a result.
- NEVER run manual git/gh commands. Only use gather.py output.
- NEVER add preamble like "Here is the briefing:" — your response IS the briefing.
- If any section has no data, omit the section header entirely.
```

- [ ] **Step 3: Verify agent is discoverable**

```bash
ls C:/dev/claude-agent-skills/plugins/h2t/agents/
```

Expected: `research-agent.md  session-gatherer.md`

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t/agents/session-gatherer.md
git commit -m "feat: add session-gatherer haiku agent for dev-session-start"
```

---

### Task 2: Rewrite dev-session-start SKILL.md

**Files:**
- Modify: `plugins/h2t/skills/dev-session-start/SKILL.md` (full rewrite, 216 → ~80 lines of orchestration logic)
- Reference: `docs/superpowers/specs/2026-03-25-session-gatherer-agent-design.md`

- [ ] **Step 1: Back up current SKILL.md for reference**

No file action needed — git history preserves the old version.

- [ ] **Step 2: Write the new SKILL.md**

Replace entire contents of `plugins/h2t/skills/dev-session-start/SKILL.md` with:

```markdown
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
```

- [ ] **Step 3: Verify SKILL.md syntax**

Read the file back and verify:
- Frontmatter is valid YAML
- Version is 2.7.0
- No broken markdown
- Steps 1-4 are complete

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/SKILL.md
git commit -m "feat: rewrite dev-session-start to dispatch session-gatherer subagent (v2.7.0)"
```

---

### Task 3: Bump plugin version

**Files:**
- Modify: `plugins/h2t/.claude-plugin/plugin.json`

- [ ] **Step 1: Update version in plugin.json**

Change `"version": "2.6.3"` to `"version": "2.7.0"` in `plugins/h2t/.claude-plugin/plugin.json`.

Note: version bump is required for `marketplace update` to propagate changes. No agent registration entries are needed in plugin.json — Claude Code discovers agents automatically from the `agents/` directory.

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t/.claude-plugin/plugin.json
git commit -m "chore: bump h2t plugin version to 2.7.0"
```

---

### Task 4: Manual verification

This task is performed by the user (not automated).

- [ ] **Step 1: Update plugin**

```bash
marketplace update && plugin update h2t
```

- [ ] **Step 2: Test in claude-agent-skills repo**

Start a new session: `/session-start`

**Pass criteria:**
- Agent `h2t:session-gatherer` is dispatched (visible in tool call log)
- gather.py runs inside the agent (not in main context)
- Formatted briefing appears
- Step 3 GATE works (naming prompt)
- Step 4 GitHub comment posts

- [ ] **Step 3: Test agent auto-discovery**

Verify `h2t:session-gatherer` appears in available agents list without any plugin.json changes.

- [ ] **Step 4: Test error path**

Temporarily rename gather.py, run `/session-start`. Verify ERROR message appears and no manual fallback.

- [ ] **Step 5: Close issue #12 if all tests pass**

```bash
gh issue close 12 --comment "Fixed: gather.py now runs in isolated haiku subagent. Verified in session {SESSION_NAME}."
```
