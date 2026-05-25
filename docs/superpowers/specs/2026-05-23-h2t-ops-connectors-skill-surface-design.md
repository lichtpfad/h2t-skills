---
title: "h2t-ops connectors skill surface design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-23"
milestone: ""
---
# h2t-ops connectors skill surface design

Date: 2026-05-23
Status: draft, research-integrated
Issue: #161
Owner plugin: h2t-ops
Related: #160, #162, docs/reports/2026-05-22-skill-surface-portability-audit.md
Research note: docs/reports/2026-05-23-claude-codex-skill-portability-research.md

## Goal

Reduce connector skill surface area without weakening agent reliability.

The connector layer is shippable. The remaining problem is not provider
functionality, but the skill interface around it: six connector skills repeat
the same pattern, add prompt weight, and make sharing harder.

This spec designs a controlled experiment: one `h2t-ops:connectors` navigator
skill for provider I/O connectors, with lazy references for connector-specific
details.

## Decisions Already Made

### Keep plugin boundaries

Do not move `h2t-ops` into `h2t-core`.

`h2t-core` remains the minimal boot/runtime layer:

- setup/update/doctor;
- session-start/handoff;
- project scaffolding;
- agent profiles.

`h2t-core` must work before provider credentials, Telegram sessions, Google
OAuth, Notion tokens, MeetGeek keys, or Exa billing are configured.

The only h2t-core change in this migration is runtime index hygiene:
session-start/handoff context may advertise `h2t-ops:connectors` instead of the
retired per-connector skill names. This is not a plugin merge and must not pull
provider connector logic into h2t-core.

`h2t-ops` remains the provider I/O plugin:

- Calendar;
- Gmail;
- Drive;
- Notion;
- Telegram;
- MeetGeek;
- Research, with a separate skill surface.

This reduces skill prompt weight without collapsing runtime/package boundaries.

## Research Findings

### Claude Code skills/plugins

Official Claude Code guidance supports the planned shape:

- `SKILL.md` is the required entrypoint.
- Supporting files can hold references, scripts, templates, and examples.
- Skill bodies load only when used, unlike always-on repo instructions.
- Once loaded, skill body text stays in context across turns, so the active
  `SKILL.md` should stay concise.
- Skills are preferred over old command files when supporting files are needed.
- Plugin skills are namespaced and are the right distribution boundary for
  marketplace/shareable functionality.

Sources:

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/slash-commands
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/discover-plugins

Implication for #161:

`h2t-ops:connectors` should be a short router with lazy references. It must not
be a mega-manual that embeds six connector command cards.

Target budget:

- `SKILL.md`: under 500 lines, preferably under 200.
- Each connector reference: focused command map and examples, not full CLI help.

### Codex / AGENTS portability

The navigator should be useful outside Claude Code.

Use a two-layer document shape:

1. Portable core:
   - purpose;
   - when to use;
   - safety boundary;
   - connector decision tree;
   - command map;
   - output/issue policy.
2. Adapter notes:
   - Claude Code invocation/frontmatter/references;
   - Codex/AGENTS usage when copied or summarized into repo docs.

The portable core must not depend on:

- `CLAUDE_PLUGIN_ROOT`;
- `CLAUDE_SKILL_DIR`;
- slash-command-only assumptions;
- Claude-only tool names.

Those details may exist in adapter sections or scripts, but not in the shared
routing logic.

### Research stays separate

Do not fold `h2t-ops:research` into `h2t-ops:connectors`.

Research is not a normal provider connector. It has:

- paid Exa usage;
- templates;
- telemetry;
- traceability requirements;
- quality gates;
- research artifacts.

It should remain its own skill and may later use references/templates more
aggressively.

### Daily Brief is not a connector

`h2t-ops:daily-brief` is a workflow/surface, not provider I/O.

It is out of scope for this consolidation. It should not be moved into the
connector navigator.

### Navigator skill responsibility

`h2t-ops:connectors` should not duplicate the full CLI help.

Its job is routing:

```text
user asks for external provider data/action
  -> identify provider and intent
  -> read the minimal command map
  -> load lazy connector reference if needed
  -> call h2t-ops CLI
  -> if command is missing, file/suggest structured issue
```

The skill is an ontology and safety layer, not a second CLI manual.

### References, not prompt bloat

The main `SKILL.md` should stay short.

Connector-specific details move to lazy references:

```text
plugins/h2t-ops/skills/connectors/
  SKILL.md
  references/
    calendar.md
    gmail.md
    drive.md
    notion.md
    telegram.md
    meetgeek.md
    issue-policy.md
```

Each connector reference should include:

- intent ontology;
- command map;
- read/write safety matrix;
- auth/config locations;
- output shape examples;
- common failures;
- when to file a connector bug vs feature issue.

Do not paste full `--help` output. Prefer stable command summaries and examples.

### Local precedent

The existing `h2t-ops:research` skill is closer to the target pattern than the
per-connector skills:

- short command surface;
- explicit boundary;
- lazy references/templates;
- workflow-specific quality requirements.

For #161, copy the reference-loading pattern, not the research scope. Research
itself stays separate.

## Target Skill Inventory

Target h2t-ops skills after the experiment:

| Skill | Status | Reason |
| --- | --- | --- |
| `h2t-ops:connectors` | new primary connector navigator | Calendar/Gmail/Drive/Notion/Telegram/MeetGeek routing |
| `h2t-ops:research` | keep separate | paid provider, templates, telemetry, quality gates |
| `h2t-ops:daily-brief` | keep separate or classify later | workflow/surface, not connector |

Existing per-connector skills should not be deleted in the first commit. First
they are deprecated or retained while live task smoke proves the navigator is
not worse.

## Connector Scope

Included in `h2t-ops:connectors`:

- Calendar: events, calendars, FreeBusy, create/update/delete when requested.
- Gmail: list/search/read/send/draft/labels.
- Drive: list/search/folders/download/export/upload/upload-folder.
- Notion: get/blocks/search/search-workspace/graph/find-databases/create/update/sync.
- Telegram: auth status, dialogs, folders, messages, saved messages, mentions, bootstrap.
- MeetGeek: auth-check, teams, list/get/transcript/summary/highlights/insights/download-url/submit-url.

Excluded:

- Research.
- Daily Brief.
- Telegram digest/tasks/research/students workflows.
- Meeting interpretation or POS transcript intake.
- Notion task acceptance or journal/KB promotion.
- Any POS/DOR canonical state write.

## Issue Capture Policy

When an agent finds a provider bug or missing provider function while using a
connector, it should create or propose a structured GitHub issue instead of
writing ad-hoc scripts.

Minimum issue fields:

```md
## Context

- Connector:
- Command:
- Environment: Windows/macOS/Linux
- CLI source: installed/local/dev
- Read or write path:

## Expected

Behavior without private payloads.

## Actual

- Exit code:
- Error class:
- Sanitized message:

## Repro

Minimal command with placeholders:

`h2t-ops <connector> <verb> --json ...`

## Evidence

- CLI version:
- Connector:
- Redacted envelope:
- Artifact refs only, no raw content:

## Privacy Review

- [ ] No tokens/API keys/cookies/session files
- [ ] No raw email bodies, transcripts, calendar descriptions, chat text
- [ ] No personal emails/phone numbers/client names unless already public
- [ ] IDs are truncated or generalized where possible
- [ ] Local paths contain no private project/person names, or are generalized

## Classification

type:bug|feature
priority:p?
domain:skills
phase:triage
```

Never include:

- secrets, tokens, OAuth codes, cookies;
- private message bodies;
- transcript bodies;
- personal data from provider payloads;
- full provider JSON if it contains user data.

Bug vs feature:

- Bug: documented command exists but fails or returns wrong shape.
- Feature: provider operation is useful but no command exists.

Recent example: recursive Drive upload was missing and an agent wrote an ad-hoc
Google API script. That belongs as a feature request and is now fixed by #162.

Agents may include provider names, command names, exit codes, typed error names,
sanitized stack tops, and synthetic examples. They must not include raw provider
payloads or private content.

## Experiment Strategy

Do not delete old per-connector skills until this experiment passes.

Phases:

1. Add `h2t-ops:connectors` and references.
2. Run representative task smoke with the navigator.
3. Compare behavior against existing per-connector skills.
4. If equal or better, deprecate old per-connector skills.
5. Only then remove, disable, or archive old per-connector skills.

Old connector skills may temporarily become wrappers/stubs only if that improves
transition safety. They must not duplicate the full command docs after the
navigator exists.

## Representative Task Smoke

Navigator must handle:

- Calendar: list events for a date window; query busy windows.
- Gmail: search and read messages; create draft/send only when explicitly asked.
- Drive: search/list files; upload a folder preserving relative paths.
- Notion: find shared page/database and inspect embedded child databases.
- Telegram: auth status and read Saved Messages or a named dialog.
- MeetGeek: list/get meeting and fetch transcript.

Acceptance is not just command success. The agent must:

- pick the right provider;
- avoid paid/live/write paths unless asked;
- load only the relevant reference;
- not ask for unrelated credentials;
- file/propose a structured issue if the command does not exist.

Cross-agent smoke should also prove that the same routing text leads Claude Code
and Codex-style agents to the same command choice for each provider.

## Research Plan Before Final Spec

Run two focused research packets before finalizing the design.

### Packet A: Claude Code skill/plugin best practices

Questions:

- Best practices for `SKILL.md` length, references, lazy loading, and plugin
  marketplace sharing.
- Skill vs slash command boundaries.
- How to avoid prompt bloat while preserving discoverability.
- Patterns for navigator skills that route to CLI subcommands.
- Anti-patterns when consolidating skills.

Output:

- findings;
- implications for #161;
- acceptance criteria.

### Packet B: Codex / AGENTS compatibility

Questions:

- How to structure skill-like instructions so they also work as repo docs or
  `AGENTS.md`-style guidance.
- What belongs in CLI/scripts vs skill text vs references.
- Cross-agent issue capture policy.
- Smoke criteria that prove the navigator works for Claude and Codex agents.

Output:

- findings;
- implications for #161;
- acceptance criteria.

## Non-Goals

- Do not merge h2t-ops into h2t-core.
- Do not merge research into h2t-core.
- Do not redesign `h2t-core:agent-profile`.
- Do not change provider connector code unless a real CLI gap is discovered.
- Do not delete per-connector skills before live navigator smoke.
- Do not move Daily Brief into connector navigator.
- Do not implement POS/DOR workflow contracts here.

## Open Questions

- Should old connector skills become thin stubs pointing to
  `h2t-ops:connectors`, or should they be removed entirely after smoke?
- Should `h2t-ops:connectors` include an explicit issue-filing helper script, or
  is a documented issue template enough for v1?
- Should references be hand-written summaries or generated from CLI help during
  release checks?
- Should connector navigator be optimized for Claude Code only first, or be
  written as cross-agent repo documentation from day one?
- Should automatic invocation be enabled immediately, or should the first
  version require direct invocation until smoke proves it does not steal
  `h2t-ops:research` / `daily-brief` traffic?

## Acceptance Gates

- `h2t-ops:connectors` exists and is short enough to avoid replacing six skills
  with one huge prompt block.
- Connector-specific details live in lazy references.
- Research and Daily Brief remain outside the connector navigator.
- Representative task smoke passes for Calendar, Gmail, Drive, Notion,
  Telegram, and MeetGeek.
- Old per-connector skills are either retained with reason, deprecated, or
  removed after evidence.
- Issue capture policy is documented once and avoids secret/private-data leaks.
- `plugins/h2t/` remains retired and does not re-enter the active source path.
- Main navigator remains below the agreed context budget.
- Portable routing core does not require Claude-only environment variables.
- No fallback to raw provider APIs is recommended when a connector command is
  missing; the correct behavior is structured issue capture.
