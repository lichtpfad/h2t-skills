# Skill Surface and Portability Audit

Date: 2026-05-22

Scope: closing audit after h2t-ops connector migration and h2t-core agent-profile v0.2.

This report separates migration closure from later agent-profile debugging. Connector migration can be treated as shippable, but the skill surface still needs one cleanup pass before the repository is comfortable to share with another user.

Tracking issues:

- #160 `h2t-core: setup/update delivery + lifecycle context budget`
- #161 `h2t-ops: connector navigator + skill surface consolidation`
- #162 `h2t-ops drive: recursive folder upload/mirror`

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
- Prototype replacing Calendar/Drive/Gmail/MeetGeek/Notion/Telegram skills with one `h2t-ops:connectors` skill plus lazy references.

The product test is whether the agent still reliably chooses the correct connector and command from one navigator skill. The conceptual model is strong: `h2t-ops` exposes one CLI/API surface, and connectors are classes of provider I/O that require authorization. Do not collapse the active per-connector skills until this is tested in live sessions.

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
- Add a bounded handoff summary/index:
  - `summary_short`: max 1200 chars
  - `next_actions`: max 5
  - `blockers`: max 5
  - `artifacts`: max 10
  - `updated_at`, `session_id`, `project`, `domain`
- Write or update a per-project `latest.json` index beside the markdown files.
- Make `session-start` read only the bounded summary by default.
- Allow full handoff read only by explicit user request.
- Add truncation and tests so `session-start` context cost cannot grow with session history.

Open design point: `latest.json` is not valuable if it simply duplicates markdown in a more token-expensive format. It should be a compact routing/index artifact, not another narrative handoff. Handoff cleanup also needs retention semantics:

- keep latest bounded summary hot;
- keep full markdown archive available;
- periodically archive older handoffs by project/date;
- optionally distill long histories into a stable project memory;
- never require POS/DOR for basic `session-start` and `handoff` operation.

POS boundary: lifecycle skills may optionally publish to the personal OS, but their primary contract must work standalone. POS may consume handoff/session artifacts, but h2t-core must not require POS state to start or end a coding session.

## Setup and Update Skill

The install/share guide should not remain a passive document. It should be implemented as a `h2t-core:setup` / future `h2t-core:update` workflow.

Minimum setup story for another user:

1. Install `h2t-core`.
2. Run `h2t-core:setup`.
3. Install `h2t-ops`.
4. Run connector-specific auth/status checks:
   - Calendar/Gmail/Drive OAuth status.
   - Notion token status.
   - Telegram auth status.
   - MeetGeek API key check.
   - Research/Exa key check.
5. Optional: configure POS/DOR integration.
6. Optional: apply `h2t-core:agent-profile` to the repo.

This should work without requiring the user's private `C:/dev` tree.

Required delivery work:

- make `uv tool install` / `uvx` installation reliable for `h2t-ops`;
- make setup check whether `h2t-ops` is installed and runnable;
- add an update path for plugin/CLI refresh;
- expose connector auth/status checks from one setup/update workflow;
- separate required provider setup from optional POS/DOR integration.

## Connector Issue Capture

Connector skills should teach agents to file structured issues when they hit provider gaps.

Policy:

- If a bug is discovered, create or propose a bug issue in the relevant repository.
- If provider functionality is needed but missing, create or propose a feature request.
- The issue must include command, provider, observed behavior, expected behavior, sanitized error output, and whether it is read-only or write-path.
- Do not auto-file secrets, tokens, private message bodies, transcript bodies, or personal data.
- Prefer explicit user confirmation before creating GitHub issues unless the user has already asked to track the work.

This belongs in the connector navigator or shared h2t-ops reference, not duplicated across every connector skill.

Concrete example: uploading a folder of HTML, videos, and images to Google Drive
should be `h2t-ops drive upload-folder` / `mirror`, not an ad-hoc Google API
script written by the agent. Tracked by #162.

## Critical Path

1. Bound `session-start`/`handoff` context.
   This is the highest ROI fix because it prevents lifecycle tools from becoming progressively more expensive.

2. Archive or remove legacy `plugins/h2t/`.
   It is no longer active, but it keeps old assumptions and short names in the source tree.

3. Turn setup/install/share guidance into `h2t-core:setup` / `h2t-core:update`.
   This should cover split plugin install, `uv` delivery for `h2t-ops`, connector setup, credential checks, and optional POS integration.

4. Prototype h2t-ops connector navigator.
   Test one `h2t-ops:connectors` skill plus lazy connector references before removing per-connector skills.

5. Clean functional overlaps outside h2t-ops.
   Start with Arch node skills, Dev GitHub skills, Edu meeting/transcript skills, and Creative voice-eval.

6. Keep agent-profile follow-ups separate.
   Useful next items: configurator UX, multi-context project selection, sync across machines, and better profile presets.

## Definition of Done

The migration/cleanup stage is done when:

- Active marketplace has only split plugins, no legacy `h2t`.
- Source tree no longer presents legacy `plugins/h2t/` as an active plugin.
- `session-start` reads bounded summary context, not free-form handoff bodies.
- Setup/update workflow can install/check `h2t-ops` and connector auth without private H2T paths.
- h2t-ops connector navigator has been tested or explicitly rejected.
- Connector bug/feature issue capture policy exists.
- Agent-profile remaining issues are tracked as follow-ups, not blockers for connector migration closure.
