# Skill Surface and Portability Audit

Date: 2026-05-22

Scope: closing audit after h2t-ops connector migration and h2t-core agent-profile v0.2.

This report separates migration closure from later agent-profile debugging. Connector migration can be treated as shippable, but the skill surface still needs one cleanup pass before the repository is comfortable to share with another user.

## Current State

- `h2t-ops` connector layer is shippable: Calendar, Gmail, Drive, Notion, Telegram, MeetGeek, Research have provider-level CLI/skill coverage.
- `h2t-core:agent-profile` v0.2 is implemented and closed as an MVP. Further usability work belongs in follow-up tasks.
- Legacy `h2t@lichtpfad` is no longer in the active marketplace, but `plugins/h2t/` still exists in the source tree.
- Active split plugins use namespaced skill names.
- The remaining problem is not direct duplicate registration. It is functional overlap, portability, and context budget.

## Functional Overlap

### Legacy h2t Source Tree

`plugins/h2t/` still contains legacy skills:

- `calendar`
- `daily-brief`
- `gmail`
- `notion`
- `telegram`
- `voice-eval`

These overlap with split plugins and still contain older assumptions about secrets, local output paths, and short skill names. They are not active in the current marketplace, but their presence makes the repository harder to reason about.

Recommended action: move `plugins/h2t/` to an archive location or delete it after confirming no marketplace or test path still depends on it.

### h2t-ops Connector Skills

Current shape is one skill per connector:

- `h2t-ops:calendar`
- `h2t-ops:drive`
- `h2t-ops:gmail`
- `h2t-ops:meetgeek`
- `h2t-ops:notion`
- `h2t-ops:telegram`
- `h2t-ops:research`
- `h2t-ops:daily-brief`

This is useful for direct invocation, but it is not necessarily the best long-term shape. For non-research connectors, a single `h2t-ops:connectors` navigator skill with connector references could reduce listing noise and make install/share documentation clearer.

Recommended target:

- Keep `h2t-ops:research` separate because it has templates, telemetry, quality gates, and research artifact semantics.
- Keep `h2t-ops:daily-brief` separate or move it to workflow/surface semantics. It is not a connector.
- Consider replacing Calendar/Drive/Gmail/MeetGeek/Notion/Telegram skills with one `h2t-ops:connectors` skill plus lazy references.

### Other Merge Candidates

- `h2t-arch:diagram-node` and `h2t-arch:node-researcher` overlap around diagram/node research and annotation.
- `h2t-dev:gh-memory` and `h2t-dev:github-issues` overlap around issue state and issue creation.
- `h2t-edu:process-transcripts` overlaps with POS meeting distillation. Keep as historical reference or portable workflow, not canonical POS truth.
- `h2t-edu:convert-meeting-transcript` is a useful portable converter and should remain separate from POS intake.
- `h2t-creative:voice-eval` overlaps with legacy `h2t:voice-eval`; keep one active source.
- `h2t-core:project-audit` is landing/project specific and has hardcoded local paths. It may not belong in core for public sharing.

## Portability Risks

The main sharing risk is not Python packaging. It is personal filesystem and credential assumptions in skill instructions.

Observed risk classes:

- Absolute local paths such as `C:/dev/...`.
- Personal state paths such as `~/.dor/...`, `~/.h2t/...`, `~/.config/...`.
- Connector-specific credential paths and token file names.
- POS/DOR boundary assumptions inside skills that should be optional outside the user's own setup.
- Setup instructions that assume local editable installs from `C:/dev/h2t-skills`.
- Workflow skills that call Gemini, Notion, or POS state without a clear explicit output contract.

Required sharing standard:

- Every skill must degrade gracefully if the user's personal H2T config does not exist.
- Connector install must be documented as provider setup plus `h2t-ops` tool availability.
- Personal OS integration must be described as optional, not required for provider I/O.
- Any absolute `C:/dev/...` path must either be replaced by discovery/config or marked as local-only.
- Secrets must be read through documented resolution order and validated by doctor/auth commands.

## Session-Start and Handoff Context Budget

Current implementation:

- `handoff` writes one markdown file per session under `~/.dor/sessions/<machine>/<project>/`.
- `writer.py` stores unbounded `what_done` and `what_remains`.
- `session-start` discovers handoff files across machines and may read the latest markdown handoff.
- `briefing.py` shows the handoff count but does not provide a bounded machine-readable summary.

Problem:

Over time, handoff files become larger and more narrative. `session-start` should not depend on reading a free-form handoff body into the active context.

Recommended target:

- Keep full markdown handoff as archival evidence.
- Add a bounded machine-readable handoff summary:
  - `summary_short`: max 1200 chars
  - `next_actions`: max 5
  - `blockers`: max 5
  - `artifacts`: max 10
  - `updated_at`, `session_id`, `project`, `domain`
- Write or update a per-project `latest.json` index beside the markdown files.
- Make `session-start` read only the bounded summary by default.
- Allow full handoff read only by explicit user request.
- Add truncation and tests so `session-start` context cost cannot grow with session history.

## Install and Sharing Model

Minimum install story for another user:

1. Install `h2t-core`.
2. Run `h2t-core:setup` or an equivalent doctor command.
3. Install `h2t-ops`.
4. Run connector-specific auth/status checks:
   - Calendar/Gmail/Drive OAuth status.
   - Notion token status.
   - Telegram auth status.
   - MeetGeek API key check.
   - Research/Exa key check.
5. Optional: configure POS/DOR integration.
6. Optional: apply `h2t-core:agent-profile` to the repo.

This should be documented without requiring the user's private `C:/dev` tree.

## Critical Path

1. Bound `session-start`/`handoff` context.
   This is the highest ROI fix because it prevents lifecycle tools from becoming progressively more expensive.

2. Archive or remove legacy `plugins/h2t/`.
   It is no longer active, but it keeps old assumptions and short names in the source tree.

3. Write a public sharing/install guide.
   This should cover split plugin install, connector setup, credential checks, and optional POS integration.

4. Decide h2t-ops skill surface.
   Either keep one skill per connector with shorter descriptions, or introduce `h2t-ops:connectors` with lazy references.

5. Clean functional overlaps outside h2t-ops.
   Start with Arch node skills, Dev GitHub skills, Edu meeting/transcript skills, and Creative voice-eval.

6. Keep agent-profile follow-ups separate.
   Useful next items: configurator UX, multi-context project selection, sync across machines, and better profile presets.

## Definition of Done

The migration/cleanup stage is done when:

- Active marketplace has only split plugins, no legacy `h2t`.
- Source tree no longer presents legacy `plugins/h2t/` as an active plugin.
- `session-start` reads bounded summary context, not free-form handoff bodies.
- Connector install/auth documentation works for a new user without private H2T paths.
- h2t-ops connector skills have an explicit long-term surface decision.
- Agent-profile remaining issues are tracked as follow-ups, not blockers for connector migration closure.
