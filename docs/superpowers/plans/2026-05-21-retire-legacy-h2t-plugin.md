# Retire legacy h2t plugin

**Issue:** #151 — skills: register only namespaced aliases to eliminate duplicate entries in system prompt
**Date:** 2026-05-21
**Status:** Draft / review-ready

## Goal

Stop publishing/loading the legacy `h2t` monolith plugin and leave operational
connector work under the split plugins, especially `h2t-ops`.

This is a context-hygiene and migration-closure task. It is not a new connector
migration and it is not a POS workflow migration.

## Current Facts

`plugins/h2t/skills` currently contains only six skills:

- `calendar`
- `daily-brief`
- `gmail`
- `notion`
- `telegram`
- `voice-eval`

The first five are either covered by `h2t-ops` or intentionally handled by
workflow/POS boundaries. The only unique useful skill is `voice-eval`.

Other legacy `h2t` contents:

- `lib/gather` and hooks: already covered by `h2t-core`.
- `commands/ctx-load.md` and `commands/session-name.md`: stale command stubs.
- `agents/research-agent.md`: explicitly deprecated.

## Architecture Decision

Retire `h2t` as an installed marketplace plugin. Keep `plugins/h2t/` in the repo
for one release as rollback/archive source, but remove it from
`.claude-plugin/marketplace.json` so new sessions no longer load it.

Move `voice-eval` to `h2t-creative` as `h2t-creative:voice-eval`.

## Non-Goals

- Do not migrate old Telegram/Notion/meeting dynamics from `h2t`.
- Do not reimplement old `daily-brief` internals.
- Do not delete `plugins/h2t/` from git in this first pass.
- Do not edit `.claude/settings.json`, `.claude/settings.local.json`, `.bak`
  files, `.superpowers/`, `build/`, or other unrelated dirty-tree files.
- Do not close POS/coordinator gaps here. Those belong to POS/workflow backlog.

## File Map

| File | Action |
| --- | --- |
| `plugins/h2t-creative/skills/voice-eval/SKILL.md` | Add, copied/adapted from legacy `h2t` |
| `plugins/h2t-creative/.claude-plugin/plugin.json` | Bump patch |
| `.claude-plugin/marketplace.json` | Remove `h2t` entry; bump `h2t-creative`; fix stale `h2t-ops` entry if needed |
| `docs/h2t-ops-roadmap.md` | Record legacy `h2t` retired from marketplace |
| `docs/superpowers/plans/2026-05-21-retire-legacy-h2t-plugin.md` | This plan |

Do not modify `plugins/h2t/` in implementation tasks except read-only checks.

## Task T0 — Baseline Audit (no commit)

1. Confirm dirty tree and do not stage unrelated files:

   ```powershell
   git status --short --branch
   ```

2. Confirm legacy skill inventory:

   ```powershell
   Get-ChildItem -Directory plugins\h2t\skills | Select-Object -ExpandProperty Name
   ```

   Expected: `calendar`, `daily-brief`, `gmail`, `notion`, `telegram`,
   `voice-eval`.

3. Confirm split-plugin coverage:

   ```powershell
   Get-ChildItem -Directory plugins\h2t-ops\skills | Select-Object -ExpandProperty Name
   Get-ChildItem -Directory plugins\h2t-core\skills | Select-Object -ExpandProperty Name
   Get-ChildItem -Directory plugins\h2t-creative\skills | Select-Object -ExpandProperty Name
   ```

4. Confirm current marketplace still publishes `h2t`:

   ```powershell
   Get-Content .claude-plugin\marketplace.json | ConvertFrom-Json
   ```

5. STOP if `voice-eval` already exists outside `plugins/h2t`.

## Task T1 — Move voice-eval to h2t-creative

1. Add `plugins/h2t-creative/skills/voice-eval/SKILL.md`.

   Source: `plugins/h2t/skills/voice-eval/SKILL.md`.

   Required edits:

   - `name: h2t-creative:voice-eval`
   - Keep the `h2t-voice` dependency notes.
   - Keep the explicit "do not add to reference automatically" rule.
   - Keep triggers for `voice eval`, `check my voice`, `оцени стиль`,
     `проверь голос`, `voice check`.

2. Bump `plugins/h2t-creative/.claude-plugin/plugin.json` patch version:

   - `1.4.3 -> 1.4.4`

3. Update `.claude-plugin/marketplace.json` `h2t-creative` entry:

   - `1.4.3 -> 1.4.4`

4. If `.claude-plugin/marketplace.json` still has stale `h2t-ops` version
   after #147, update it to match `plugins/h2t-ops/.claude-plugin/plugin.json`.

5. Verification:

   ```powershell
   Select-String -Path plugins\h2t-creative\skills\voice-eval\SKILL.md -Pattern '^name: h2t-creative:voice-eval$'
   Select-String -Path plugins\h2t-creative\skills\voice-eval\SKILL.md -Pattern 'h2t-voice|VOICE_CLI|profile train'
   git diff --check -- plugins/h2t-creative .claude-plugin\marketplace.json
   ```

6. Commit:

   ```powershell
   git add plugins/h2t-creative/skills/voice-eval/SKILL.md plugins/h2t-creative/.claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "feat(creative): move voice-eval out of legacy h2t (#151)"
   ```

## Task T2 — Retire h2t from marketplace

1. Remove the `h2t` plugin entry from `.claude-plugin/marketplace.json`.

   Do not delete `plugins/h2t/` yet. Removing the marketplace entry is the
   functional retirement path and keeps rollback simple.

2. Update `docs/h2t-ops-roadmap.md`:

   - Legacy `h2t` monolith retired from marketplace.
   - Active replacements:
     - ops/provider reads: `h2t-ops`
     - session/project runtime: `h2t-core`
     - dev/GitHub/docs: `h2t-dev`
     - creative/style: `h2t-creative`
     - education/transcripts: `h2t-edu`
   - Note that old Telegram/Notion/meeting dynamics are not migrated here;
     they remain POS/coordinator/workflow backlog by boundary decision.

3. Verification:

   ```powershell
   $mp = Get-Content .claude-plugin\marketplace.json | ConvertFrom-Json
   $mp.plugins.name
   ```

   Expected: no bare `h2t` plugin. Split plugins remain.

4. Check no plan accidentally stages legacy source deletion:

   ```powershell
   git diff --name-status --cached
   git status --short plugins\h2t
   ```

   Expected: no deleted files under `plugins/h2t/`.

5. Commit:

   ```powershell
   git add .claude-plugin/marketplace.json docs/h2t-ops-roadmap.md
   git commit -m "refactor(skills): retire legacy h2t marketplace plugin (#151)"
   ```

## Task T3 — Local Plugin Smoke (manual Claude-side gate)

After push, run in Claude Code:

```text
/plugin marketplace update
/plugin uninstall h2t@lichtpfad
/plugin install h2t-creative@lichtpfad
/reload-plugins
/context
```

Expected:

- No `Plugin (h2t)` section.
- No `h2t:calendar`, `h2t:gmail`, `h2t:notion`, `h2t:telegram`,
  `h2t:daily-brief`.
- `h2t-ops:*` connector skills remain.
- `h2t-core:*`, `h2t-dev:*`, `h2t-creative:*`, `h2t-edu:*` remain.
- `h2t-creative:voice-eval` is present.

If `h2t` still appears, inspect cache/installed plugins before closing #151.

## Task T4 — Push and Close #151

1. Push:

   ```powershell
   git push origin main
   ```

2. Close #151 only after the `/context` smoke confirms legacy `h2t` is gone.

   Evidence comment should include:

   - commit SHAs for T1/T2;
   - `Plugin (h2t)` absent from `/context`;
   - split replacements still present;
   - `voice-eval` now under `h2t-creative`.

## Rollback

If something critical is missing after plugin reload:

1. Re-add the `h2t` entry to `.claude-plugin/marketplace.json`.
2. Bump patch version if needed.
3. `/plugin marketplace update`, reinstall `h2t@lichtpfad`, `/reload-plugins`.

Because `plugins/h2t/` is not deleted in this plan, rollback is a marketplace
metadata change, not source recovery.

## Acceptance

- Legacy `h2t` is no longer published from this repo's marketplace.
- Current operational skills load from split plugins.
- `voice-eval` remains available as `h2t-creative:voice-eval`.
- No old Telegram/Notion/meeting workflow is migrated or normalized as current
  architecture.
- #151 can be closed after Claude `/context` confirms the duplicate legacy
  plugin section is gone.
