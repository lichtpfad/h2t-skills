# From 10+ Tool Calls to One: How We Built a Context Assembly Framework for Claude Code

> Material for AI Mindset Lab masterclass. March 2026.

## The Problem

Claude Code skills make a lot of external calls. A typical `dev-session-start` skill needs to:

1. `git remote get-url origin`
2. `git branch --show-current`
3. `git log --oneline -5`
4. `git status --short`
5. `gh api repos/.../milestones`
6. `gh issue list --state open`
7. `gh issue list --label bug`
8. `gh pr list --state open`
9. `gh issue list --milestone "..."`
10. `ls ~/.dor/sessions/...`
11. Check for `package.json` / `pyproject.toml`

Each call is a separate tool invocation. Each tool invocation costs 2-5 seconds of roundtrip — Claude sends the request, waits for permission, executes, reads the result, decides what to do next.

**Total: 20-60 seconds just to collect context before showing a summary.**

And here's the deeper issue: Claude treats each command as a sequential decision. It can't run `git status` and `gh issue list` at the same time. It runs one, reads the output, then decides to run the next. This is inherent to how LLM tool use works — each tool call is a turn in the conversation.

## The Insight

Python's `concurrent.futures.ThreadPoolExecutor` doesn't have this limitation. One subprocess can launch 8 parallel commands and wait for all of them.

What if we moved all context gathering into a single Python script?

```
Before:  Claude → tool call → result → Claude → tool call → result → ... (10+ times)
After:   Claude → one tool call → Python runs everything in parallel → one JSON result
```

**One tool call. ~950ms. All context.**

## The Architecture: Progressive Disclosure for LLM Context

Not every skill needs all the context. A `handoff` skill needs git state and registry, but not GitHub issues. A `ceo-council` skill needs user psychology context, but not stack detection.

We organized context into **4 layers of progressive disclosure**:

```
Layer 0 — Identity (instant)
  Who is the user? What project? What domain? What machine?

Layer 1 — State (local, ~100ms)
  Git branch, status, log. Project stack (Python? JS? Rust?).

Layer 2 — Work Context (API, ~500ms)
  GitHub issues, milestones, PRs. Session history files.

Layer 3 — Deep Context (on demand)
  File contents. User psychology profile. Notion tasks. Calendar.
```

Skills declare what they need:

```python
# dev-session-start needs layers 0-2
project = identify_project(cwd)    # Layer 0
git = gather_git()                  # Layer 1
github = gather_github(remote)      # Layer 2

# ceo-council needs only layer 0 + deep psychology
project = identify_project(cwd)     # Layer 0
user = gather_user_context(domain="personal")  # Layer 0 + deep
```

Each layer is a Python module. Each module returns a plain dict. The gatherer script composes the modules it needs and outputs one JSON to stdout.

## Project Identity from Any Directory

The framework needed to work beyond git repos. Our user works in Dropbox folders, Obsidian vaults, and config directories — not just code repositories.

Solution: a `project.py` module that resolves identity from any directory:

1. Check git remote → look up in `repo-mapping.yaml`
2. No git? → match the current path against `cwd_patterns`
3. Nothing matches? → fallback to default

```yaml
# repo-mapping.yaml
mappings:
  claude-agent-skills: personal-os/agent-skills
  h2t-ai: dev/h2t-ai

cwd_patterns:
  "/LichtPfad Dropbox/HOU2TOUCH": hou2touch/monorepo
  "/Steuer": admin/taxes

default: dev/unknown
```

This means a session started from `E:/DROPBOX/.../HOU2TOUCH/` automatically knows it's in the `hou2touch` domain. No git required.

## Domain-Aware Context Loading

Different domains need different context. A personal/psychology session should load the user's psychological profile. A development session doesn't need it.

```python
DOMAIN_CONTEXT_MAP = {
    "personal": ["psychology.md"],
    "personal-os": ["psychology.md"],
    "hou2touch": [],     # will add courses context later
    "crypto": [],        # will add strategy context later
}
```

The framework returns paths, not content. The skill decides whether to read them — progressive disclosure at the file level.

## Built-In Eval Tracking

Every gather call automatically records metrics:

```json
{
  "session_id": "de-2026-03-25-001",
  "skill": "dev-session-start",
  "timestamp": "2026-03-25T01:36:42Z",
  "metrics": {
    "duration_ms": 952,
    "layers": [0, 1, 2],
    "sources_used": ["project", "user", "git", "stack", "github", "sessions"],
    "sources_failed": [],
    "context_tokens_estimate": 1106
  }
}
```

This data accumulates in `~/.h2t/evals/{skill}/sessions/`. Over time, it shows:
- Which sources are slowest?
- Which sources fail most often?
- How much context are skills loading? (token budget awareness)

## Fixing the Step 6 Bug (Bonus)

We discovered a general pattern in Claude Code skills: **if a user-interaction point (question) appears before the end of a procedure, Claude will skip everything after it.**

In `dev-session-start`, Step 5 ended with "What should we work on?" — and Step 6 (Name Session) got consistently skipped. Claude treated the question as the procedure's natural endpoint.

Fix: remove the question from Step 5, make Step 6 the single interaction point with a `MANDATORY GATE` marker:

```markdown
### Step 6: Name Session + Choose Direction

⛔ **MANDATORY GATE** — Do NOT skip this step.

Предлагаю имя сессии: `{slug}` (из issue #{N})
Продолжить с задачей #{N} ({title}), или другое направление?
```

**Design principle for LLM skills: one interaction point per procedure, and it should be the last meaningful step.**

## The Module Structure

```
plugins/h2t/lib/gather/
  __init__.py       12 public exports
  runner.py         ThreadPoolExecutor parallel runner
  project.py        Project identity from any directory
  user.py           User context (domain-dependent)
  git.py            Git state
  github.py         GitHub issues, milestones, PRs
  stack.py          Stack detection
  sessions.py       Session file discovery
  eval.py           Automatic metrics

plugins/h2t/skills/dev-session-start/
  gather.py         Skill-specific gatherer (composes modules)
  SKILL.md          Updated: single gather call + Step 6 GATE
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Context collection time | 20-60 seconds | **~950ms** |
| Tool calls for context | 10-12 | **1** |
| Context token size | uncontrolled | **~1100 tokens** |
| Step 6 skip rate | frequent | **0** (GATE enforced) |
| Eval tracking | none | **automatic** |
| Non-git directory support | none | **full** |

## What's Next

The framework is designed to grow:

- **New sources:** `notion.py`, `calendar.py`, `obsidian.py` — each is a module, one import to use
- **Registry backend:** today JSONL on disk, tomorrow SQLite, then Postgres when VPS is ready
- **Cross-skill gather:** `handoff`, `pre-merge-check`, `dev-overview` — all will get their own `gather.py`
- **Unified analytics:** dashboard across all skills, token budget tracking

## Key Takeaways for AI Mindset Lab

1. **LLM tool calls are expensive.** Not in money — in time and context window. Batching them into one subprocess call is a 20-60x speedup.

2. **Progressive disclosure works for AI too.** Don't load everything into the prompt. Declare what you need, load only that.

3. **Skills are programs, not prompts.** They have bugs (Step 6 skip), they need architecture (layers), they need testing (8 test suites), and they need documentation (ADR, README).

4. **Python stdlib is enough.** `concurrent.futures`, `subprocess`, `json`, `pathlib` — no frameworks, no dependencies.

5. **Design for the directory, not the repo.** Your AI assistant might be called from anywhere. Project identity should resolve from any path.

---

*Built with Claude Code + h2t plugin suite. Architecture decision: `docs/adr/001-gather-framework.md`*
