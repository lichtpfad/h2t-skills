# Claude/Codex Skill Portability Research

Date: 2026-05-23

Scope: reusable guidance for adapting h2t skills so the same core instructions
work in Claude Code plugin skills and in Codex/AGENTS-style repo guidance.

Primary use case: #161 `h2t-ops: connector navigator + skill surface
consolidation`, but the principles apply to other h2t skills.

## Sources

Official Claude Code docs checked during research:

- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/slash-commands
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/discover-plugins

Local source patterns inspected:

- `CLAUDE.md`
- `plugins/h2t-ops/references/h2t-connector-runbook.md`
- `plugins/h2t-ops/references/pos-operational-boundary.md`
- `h2t_ops/core/registry.py`
- `h2t_ops/core/envelope.py`
- `h2t_ops/core/output.py`
- `h2t_ops/core/secrets.py`
- existing `plugins/h2t-ops/skills/*/SKILL.md`

## Core Findings

### 1. Keep active skill text small

Claude Code skills load only when relevant, but once loaded their body remains
in context across turns. Therefore the active `SKILL.md` should be a router or
procedure, not a full manual.

Rule of thumb:

- keep `SKILL.md` under 500 lines;
- prefer under 200 lines for navigator skills;
- move long command maps, examples, provider quirks, templates, and historical
  rationale into referenced files.

### 2. Use references for detail

Claude Code skills support directories with extra files: references, scripts,
examples, templates. This is the right place for connector-specific docs.

Good split:

| Layer | Belongs there |
| --- | --- |
| CLI/runtime | API calls, auth, retries, pagination, typed errors, JSON envelope |
| Scripts | deterministic multi-step automation, validation, artifact transforms |
| `SKILL.md` | routing, safety gates, workflow order, when to load references |
| References | command tables, examples, auth notes, provider quirks, templates |

Avoid embedding API logic or full `--help` output in `SKILL.md`.

### 3. Plugins remain the shareable boundary

Standalone `.claude/` config is useful for local experiments. Plugins are better
for versioned, namespaced, marketplace/shareable skills.

For h2t this means:

- keep `h2t-core` as boot/runtime;
- keep `h2t-ops` as provider I/O;
- reduce skill count with navigator/reference patterns;
- do not merge all plugins just to reduce listing noise.

### 4. Write a portable core plus adapter notes

To make skills reusable by Codex/AGENTS-style agents, keep the main logic free
of Claude-only assumptions.

Recommended shape:

```md
---
name: plugin:skill
description: Claude Code trigger text
compatibility: Claude Code, Codex/AGENTS-compatible core
---

# Purpose
# When To Use
# Safety Boundary
# Decision Tree
# Command Map
# Output Policy
# Issue Capture Policy
# References
# Claude Code Adapter
# Codex / AGENTS Adapter
```

The portable core should not depend on:

- `CLAUDE_PLUGIN_ROOT`;
- `CLAUDE_SKILL_DIR`;
- slash-command-only invocation;
- Claude-only tool names;
- private local paths.

Claude-specific details can stay in frontmatter or an adapter section.

### 5. Navigator skills need a mini-index

A consolidated navigator must preserve discoverability.

Use a stable mini-index:

```text
Need email/inbox/send/draft/labels -> Gmail -> references/gmail.md
Need calendar/events/availability -> Calendar -> references/calendar.md
Need files/search/export/upload -> Drive -> references/drive.md
Need pages/databases/tasks -> Notion -> references/notion.md
Need chats/messages/saved -> Telegram -> references/telegram.md
Need meeting transcripts -> MeetGeek -> references/meetgeek.md
```

This prevents the navigator from becoming vague. It also helps non-Claude agents
route without relying on automatic skill trigger behavior.

### 6. Keep safety rules inline

Long command details can be lazy-loaded. Safety boundaries should be visible in
the main skill.

Minimum inline safety rules:

- no raw provider API fallback when `h2t-ops` lacks a command;
- no secrets/tokens/cookies in output or issues;
- no raw email/chat/transcript/calendar bodies in GitHub issues;
- write paths require explicit user intent;
- paid provider checks require explicit confirmation;
- POS/DOR state writes are out of scope unless an explicit coordinator owns
  them.

### 7. Issue capture needs structure

Agents should create or propose structured issues for connector bugs/missing
features instead of writing ad-hoc provider scripts.

Reusable issue template:

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

Allowed evidence:

- provider name;
- command name;
- exit code;
- typed error class;
- sanitized top-level message;
- synthetic examples.

Forbidden evidence:

- secrets, tokens, OAuth codes, cookies;
- full provider JSON with private data;
- email/chat/transcript/calendar bodies;
- personal identifiers unless already public and necessary;
- private filesystem paths when they reveal project/person names.

## Anti-Patterns

- One giant navigator `SKILL.md` with every command table.
- Duplicating the same boundary and issue policy in every connector reference.
- Ambiguous trigger descriptions that steal `research` or `daily-brief` tasks.
- Raw provider SDK/API scripts as fallback for missing connector features.
- Deleting old per-connector skills before live routing smoke passes.
- Hiding connector names so autocomplete/direct invocation gets worse.
- Burying POS/DOR boundaries only in references.

## Acceptance Criteria For Future Skill Refactors

For any h2t skill consolidation:

- active `SKILL.md` stays within an explicit line/context budget;
- references are loaded only when relevant;
- CLI/runtime owns external side effects and API semantics;
- safety boundary is inline;
- issue/reporting policy is centralized;
- Claude-specific metadata does not prevent Codex/AGENTS use;
- representative live or dry-run smoke proves the new surface routes correctly;
- old skill surface is deprecated/removed only after evidence.

## Implications For #161

#161 should implement `h2t-ops:connectors` as:

- one short navigator skill;
- six connector reference files;
- one shared issue policy reference;
- Research kept separate;
- Daily Brief kept separate;
- old per-connector skills retained or deprecated until smoke proves the
  navigator is not worse.

