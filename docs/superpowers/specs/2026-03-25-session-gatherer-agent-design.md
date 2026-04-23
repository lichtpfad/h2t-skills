---
title: "Session Gatherer Agent — Design Spec"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-03-25"
milestone: ""
---
# Session Gatherer Agent — Design Spec

## Problem

Claude ignores `gather.py` in `dev-session-start` SKILL.md and falls back to manual tool calls (Read, Bash git/gh). Root cause: at session start, system-level "default patterns" (read CLAUDE.md, check git, read memory) outcompete skill instructions. This is confirmed by issue #12.

The same gather.py works reliably in subagent context — no competing patterns.

## Solution

Move gather + format logic into a dedicated **haiku subagent** (`session-gatherer`). SKILL.md becomes a thin orchestrator that dispatches the agent and handles interactive steps.

## Architecture

```
User: /session-start
  → SKILL.md loads (thin, ~40 lines)
  → Dispatches Agent(subagent_type="h2t:session-gatherer", model="haiku")
  → Haiku agent (isolated context):
      1. Runs gather.py --cwd <cwd>
      2. Reads handoff files from result.sessions[]
      3. Reads user context (core.md)
      4. Formats markdown briefing
      5. Returns formatted briefing string
  → Main context (opus):
      1. Shows briefing to user (Step 5)
      2. Step 6 GATE — session naming + direction choice
      3. Step 7 — GitHub comment + session registry
```

## Components

### 1. Agent definition: `agents/session-gatherer.md`

**Frontmatter:**

```yaml
name: session-gatherer
description: "Gathers project context via gather.py and returns formatted session briefing. Used by dev-session-start skill. Do not call directly."
model: haiku
tools:
  - Bash
  - Read
```

**Input contract (received via dispatch prompt):**

- `gather_cmd` — full command to run gather.py (includes python path)
- `cwd` — working directory for the project

Note: `memory_dir` and `session_id` are NOT passed to the agent. Session ID extraction happens in the main context (Step 4) because it requires access to Claude's project directory which the agent cannot determine.

**System prompt responsibilities:**

- Run `$gather_cmd --cwd "$cwd"` via Bash
- If gather.py fails (non-zero exit, invalid JSON, empty output): return `ERROR: gather failed — {stderr}. Run /h2t:setup to diagnose.` Do NOT attempt manual gather.
- Parse JSON output
- Read at most 2 most-recent handoff files from `result.sessions[]` — extract Key Decisions and Critical Context only. Skip missing files. Ignore files older than 30 days.
- Read `result.user.core_path` if it exists
- Check `result.github.issues` against handoff "What Remains" — omit closed issues
- Format briefing using the template (see Output Format below)

**Return protocol:**

The agent's final message IS the briefing — no wrapping, no preamble, no explanation. The main context uses the full agent response verbatim as the briefing text. If gather failed, the final message is the ERROR string above.

**Output format (returned to main context):**

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
{key decisions, critical gotchas from handoff files}
{machine: {machine}, date: {date}}
```

**Rules for the agent:**

- GitHub issues are the source of truth for tasks
- Never copy "What Remains" from handoff as tasks
- If handoff mentions an issue that is now closed — omit it
- Context section is optional — only include if non-obvious decisions or gotchas exist
- Do NOT ask questions — this is a data-gathering agent, always return results

### 2. SKILL.md rewrite: `skills/dev-session-start/SKILL.md`

Reduced from 216 lines to ~50 lines. Structure:

```
---
name: dev-session-start
description: <unchanged>
---

# Instructions

## Variables
<H2T_PYTHON detection — unchanged>
GATHER="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/gather.py"

## Procedure

### Step 1: Gather Context (via subagent)

Dispatch agent:
- subagent_type: "h2t:session-gatherer"
- model: haiku
- prompt: "Gather project context and return formatted briefing.
  gather_cmd: $GATHER
  cwd: $(pwd)"

### Step 2: Show Briefing

Display the agent's returned briefing verbatim to the user.
The agent's response IS the briefing — no reformatting needed.
If response starts with "ERROR:" — show the error and stop.
Do NOT ask questions in this step.

### Step 3: Name Session + Choose Direction (GATE)

<Step 6 logic from current SKILL.md — unchanged>

### Step 4: Post GitHub Comment + Register Session

<Step 7 + 7.5 logic from current SKILL.md — unchanged>

## Common Mistakes
<reduced list, focused on orchestration mistakes>
```

### 3. No changes to existing files

- `gather.py` — unchanged
- `lib/gather/` — unchanged
- `handoff/` skill — unchanged
- `plugin.json` — Claude Code auto-discovers agents from `agents/` directory (verify during testing)

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Haiku model | Gather+format is deterministic, no reasoning needed. Cheaper, faster. |
| Agent definition (not inline prompt) | Single source of truth, testable independently, reusable by future skills |
| Thin SKILL.md | Less text = fewer competing instructions = less chance of ignoring the dispatch |
| Only Bash + Read tools | Minimal toolset — agent only needs to run commands and read files |
| Handoff untouched | Working fine, don't fix what isn't broken |
| Agent returns formatted markdown | Main context gets clean result, no raw JSON parsing needed |
| No emoji in briefing template | Haiku may handle emoji inconsistently; clean markdown preferred |
| session_id extracted in main context | Agent cannot access Claude's project directory; main context resolves it in Step 4 |
| Max 2 handoff files, 30-day limit | Prevents agent from reading stale or excessive session history |
| Version bump: minor (2.7.0) | Replacing core execution mechanism is a behavioral change, not a patch |

## What This Fixes

- **#12** — gather.py runs in isolated subagent context where it cannot be ignored
- **Context window savings** — raw gather data stays in haiku context, main gets only formatted briefing
- **Reliability** — subagent has no competing "default patterns"

## Testing Plan

1. Run `/session-start` in `claude-agent-skills` repo — verify gather.py executes via subagent (not manual calls)
2. Run `/session-start` in `h2t-ai` repo — verify cross-repo project identity
3. Handoff file reading:
   - (a) No handoff files → context section omitted
   - (b) Handoff file exists → key decisions appear in briefing
   - (c) Handoff mentions a closed issue → issue absent from briefing
4. Gather failure: temporarily break gather.py → verify ERROR message returned, no manual fallback
5. Verify agent auto-discovery: `h2t:session-gatherer` appears in available agents without plugin.json changes
6. Verify Step 3 GATE still works (naming, direction)
7. Verify Step 4 GitHub comment + registry posts correctly

## Migration

1. Create `agents/session-gatherer.md`
2. Rewrite `skills/dev-session-start/SKILL.md`
3. Bump plugin version (minor: 2.7.0)
4. `marketplace update && plugin update h2t`
5. Test in real session
6. Close #12 if verified
