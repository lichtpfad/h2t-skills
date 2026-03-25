# Claude Agent Skills

Two Claude Code plugins for personal AI-assisted workflow: **h2t** (dev workflow + integrations) and **creative-thinking** (creative problem-solving).

## Install

```bash
claude plugin install h2t@lichtpfad
claude plugin install creative-thinking@lichtpfad
```

After install: `/h2t:setup` to create `~/.h2t/venv` and install Python dependencies.

## h2t Plugin

Dev workflow, Google integrations, content processing, and project management.

### Dev Workflow

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `dev-session-start` | `/session-start`, start session | Load project context, show issues/milestones, name session |
| `handoff` | `/handoff`, session end | Save session state to `~/.dor/sessions/`, post GitHub comment |
| `dev-overview` | project overview, weekly review | Cross-project dashboard with progress bars |
| `pre-merge-check` | ready to merge | Security audit, tests, build, plan compliance gates |
| `milestone-closure` | close milestone | Close milestone, generate report |
| `github-issues` | create issue | Structured issues with Context/What/Why sections |
| `gh-memory` | create issue, agent task | GitHub Issues as persistent agent memory |

### Google Integrations

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `gmail` | check email, inbox | Read/send Gmail via OAuth |
| `calendar` | schedule, events | Read/create Google Calendar events |
| `drive` | google drive, meetgeek | Browse Drive, sync MeetGeek transcripts |
| `notion` | notion, tasks, GTD | Read/write Notion pages and databases |
| `telegram` | telegram, saved messages | Read channels, save digests, extract tasks |

### Content & Diagrams

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `drawio` | create diagram | Generate styled .drawio architecture diagrams |
| `diagram-node` | document node | Research + annotate diagram nodes |
| `node-researcher` | research node | Deep research via Exa API for diagram nodes |
| `deck` | create presentation | HTML presentations (terminal or editorial style) |
| `design` | HUD design | Tactical dashboard design system |
| `lesson-parser` | parse tutorial | Extract topology from procedural tutorial transcripts |

### Processing

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `daily-brief` | daily brief, план на день | Morning briefing: Calendar + Gmail + Notion |
| `convert-meeting-transcript` | convert transcript | DOCX meeting transcripts to Markdown |
| `process-transcripts` | process transcripts | LLM-enrichment of MeetGeek transcripts |
| `youtube-transcript` | youtube, video transcript | Extract YouTube transcripts with chapters |
| `ceo-council` | council, стратегический анализ | Strategic AI advisor council with personas |

### Agents

| Agent | What it does |
|-------|-------------|
| `research-agent` | Web search + URL extraction for skill context |

## creative-thinking Plugin

Creative problem-solving using 57 frameworks from Dmitriy Chernyshov's course.

| Component | What it does |
|-----------|-------------|
| `/creative-think` | Full pipeline: understand → lookup → research → generate → evaluate |
| `framework-agent` | Applies one framework to generate 3-5 ideas |
| `evaluator-agent` | Scores ideas against 8 Chernyshov criteria (1-10) |

Modes: `generate`, `evaluate`, `session` (full cycle), `funnel` (filter & refine).

## Gather Framework (`lib/gather/`)

Parallel context collection for skills. One Python call replaces 10+ sequential tool calls.

```
lib/gather/
  runner.py      ThreadPoolExecutor parallel runner
  project.py     Project identity from any directory
  user.py        User context (about-me, domain-dependent)
  git.py         Git state (remote, branch, log, status)
  github.py      GitHub issues, milestones, PRs
  stack.py       Stack detection (JS/Python/Rust/Go)
  sessions.py    Session file discovery across machines
  eval.py        Automatic metrics tracking
```

See `lib/gather/README.md` for API docs and `docs/adr/001-gather-framework.md` for architecture.

## Structure

```
plugins/
  h2t/                          Main plugin
    .claude-plugin/plugin.json  Manifest
    skills/                     25 skills
    agents/                     1 agent
    hooks/                      SessionStart hook
    lib/gather/                 Context Assembly Framework
  creative-thinking/            Creative thinking plugin
    skills/                     1 skill
    agents/                     2 agents
    hooks/                      PostToolUse + Stop hooks
hooks/                          Root-level hooks
docs/
  adr/                          Architecture Decision Records
  plans/                        Implementation plans
```

## Requirements

- Claude Code
- Python 3.10+ with `~/.h2t/venv/`
- `gh` CLI (authenticated)
- Google OAuth tokens (for gmail/calendar/drive)
