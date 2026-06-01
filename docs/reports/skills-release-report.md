---
title: "skills-release Milestone Report"
milestone: "skills-release"
date: "2026-06-02"
status: "completed"
version: "v2.15.0"
---

# skills-release Milestone Report

**Period:** 2026-05-25 → 2026-06-02  
**Version:** v2.15.0  
**Issues:** 29 closed, 0 open  
**PRs:** #234–#244

## What Was Implemented

### h2t-ops Connector P0 Coverage (PRs #234–#238)

| Connector | PR | Key additions |
|-----------|-----|---------------|
| Drive | #234 | Complete P0 API: list, get, export, upload, create folder, move, trash; format aliases (txt→text, markdown→md); stdlib HTML→MD fallback |
| Gmail | #235 | reply, forward, label lifecycle |
| Notion | #236 | database row + page lifecycle commands |
| Telegram | #237 | send-file, forward-message, delete-message |
| Calendar + MeetGeek | #238 | P0 API coverage |

### Session Continuity (PR #239)

- `h2t-core:handoff` Step 3 pulls open P0/blocker issues from GitHub

### docs-lint Unified Contract (PR #241)

- 5-mode CLI: audit, plan, fix-safe, fix-index, doctor
- Execution tracking JSON output
- BFS orphan detection
- writeControl guard

### Lifecycle OS (#196 + #197)

| PR | Issues | What |
|----|--------|------|
| #242 | — | Lifecycle harness contract spec |
| #243 | #196 | scaffold/init outside DEV_ROOT + milestone-closure backend; on-stop hook repair |
| #244 | #197 | PostToolUse git-commit docs-lint hook; scaffold installs both hooks; gh-memory deprecated |

## Key Architectural Decisions

- **Nested Claude Code hook shape** — `{"hooks": [{"type": "command", "command": "..."}]}` required by runtime; flat shape silently ignored
- **Hook report cache** — `.h2t/lifecycle/*.json` excluded via `.git/info/exclude` (not `.gitignore`) to avoid dirty working tree
- **stdlib HTML→MD fallback** — `html.parser`-based `_MarkdownHTMLParser` avoids hard dependency on `html2text`; graceful degradation
- **gh-memory deprecation** — compatibility shim retained for old DOR workflows; new work routes through `session-start`/`handoff`

## Changed Files (by area)

- `h2t_ops/connectors/` — drive, gmail, notion, telegram, calendar, meetgeek
- `plugins/h2t-core/hooks-handlers/` — on-stop, post-git-commit-docs-lint (new)
- `plugins/h2t-core/skills/scaffold-project/` — install_hooks nested shape + PostToolUse + cache ignore
- `plugins/h2t-dev/skills/gh-memory/` — deprecated shim
- `plugins/h2t-dev/skills/docs-lint/` — 5-mode CLI
- `tests/` — hooks/, lifecycle/, connectors/, scaffold/

## Test Coverage Added

- `tests/hooks/test_post_git_commit_docs_lint.py` — 16 tests (hook backend + timeout + main guard)
- `tests/lifecycle/test_gh_memory_deprecated.py` — 3 tests (deprecation guards)
- `tests/scaffold/test_scaffold_steps.py` — +7 tests (PostToolUse hook + cache ignore + idempotency)
- `tests/connectors/` — expanded P0 coverage across all connectors

## Next Candidates

- **#208** (P3): Drive md-to-docx upload via pandoc
- **#5**: h2t-arch diagram-node-documenter Step 0
- **creative-p2**: component library recovery (#83, #88, #89, #90, #91, #92, #119)
