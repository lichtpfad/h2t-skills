---
title: "Pre-release audit — the tree against a machine that is not the author's"
date: "2026-08-27"
status: "in-progress"
issue: "#431"
runbook: "docs/superpowers/plans/2026-08-27-pre-release-clean-machine-audit-runbook.md"
---

# Pre-release audit

Measurement pass before publication (#419). Nothing here is fixed by this run; every finding
becomes an issue. Written incrementally so it survives a context compaction — a section with
no numbers in it has not been measured yet.

## Phase B — language

Agent-facing text was checked for Cyrillic across `plugins/`, `lib/`, `h2t_ops/`, `scripts/`,
`tools/`, `tests/` and `.claude/`. **45 files, 701 lines.** Not all of it costs the same, so
the classification is the finding rather than the total.

### B1. Skill descriptions — 24 SKILL.md, 17 of them in the frontmatter

The frontmatter `description` is what Claude Code reads to decide whether a skill applies. Of
24 SKILL.md files carrying Cyrillic, **17 carry it inside the frontmatter itself**:

| lines | frontmatter | file |
|---|---|---|
| 88 | yes | `plugins/h2t-ops/skills/daily-brief/SKILL.md` |
| 78 | no | `plugins/h2t-edu/skills/lesson-parser/SKILL.md` |
| 51 | yes | `plugins/h2t-edu/skills/process-transcripts/SKILL.md` |
| 51 | yes | `plugins/h2t-creative/skills/voice-eval/SKILL.md` |
| 35 | yes | `plugins/h2t-core/skills/scaffold-project/SKILL.md` |
| 33 | yes | `plugins/h2t-edu/skills/youtube-transcript/SKILL.md` |
| 20 | yes | `plugins/h2t-core/skills/handoff/SKILL.md` |
| 12 | no | `plugins/h2t-dev/skills/gh-memory/SKILL.md` |
| 10 | no | `plugins/h2t-dev/skills/docs-lint/SKILL.md` |
| 9 | yes | `plugins/h2t-core/skills/session-start/SKILL.md` |

…and 14 more with 1–6 lines each.

The shape is consistently a bilingual trigger list — `Triggers: 'daily brief', 'briefing',
'утренний брифинг', 'что сегодня'`. Whether that helps or hurts dispatch is a question for the
architecture review (phase I), not something this phase can settle by counting.

### B2. Runtime strings the user reads — 18 files

These are not documentation. They are what a person sees when something goes wrong:

```
44  plugins/h2t-ops/skills/drive/scripts/drive_cli.py
44  plugins/h2t-edu/skills/process-transcripts/scripts/process_transcripts.py
21  plugins/h2t-core/lib/gather/briefing.py
21  lib/gather/briefing.py
19  plugins/h2t-dev/skills/docs-lint/scripts/lint.py
16  plugins/h2t-core/skills/init-project/scripts/detect_project.py
14  plugins/h2t-core/hooks-handlers/structure_guard.py
 5  plugins/h2t-core/hooks-handlers/plan_closer.py
```

Sample — `drive_cli.py:88`:

```
Папка '{folder_name}' не найдена. Запустите: drive list
```

A `structure_guard` hook that blocks a commit does it with `BLOCKED: запрещённый паттерн
имени`. For an external user this is an error message in a language they may not read, from a
hook they did not install deliberately.

### B3. Harmless

22 test files (fixture strings and assertion text) and 8 content/config files (creative
profiles, CHANGELOGs, a handoff example). These carry no cost for an external reader.

## Phase K — codex cross-compatibility (partial)

**There is no `AGENTS.md` in this repository.** `codex` is installed on this machine
(`/opt/homebrew/bin/codex`) and reads `AGENTS.md` for project instructions; this tree has
`CLAUDE.md` only. A Codex session in this repo therefore starts with none of the project
rules — not the connector boundary, not the linting rule set, not the verification discipline.

Remaining sub-questions for this phase are unmeasured at time of writing.
