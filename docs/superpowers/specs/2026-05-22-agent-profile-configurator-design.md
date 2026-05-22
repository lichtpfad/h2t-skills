# h2t-core:agent-profile v0.2 — configurator design

Date: 2026-05-22
Status: needs-fix → patched 2026-05-22
Owner plugin: h2t-core
Follows: docs/superpowers/specs/2026-05-21-h2t-core-agent-profile-design.md

## Goal

Add a project configurator and a catalog editor (experimental) to `h2t-core:agent-profile`.
Extend merge semantics so that `overlays` entries can reference base profile names as
additional work contexts.

## Merge Semantics v0.2

### Name collision fix (Codex finding #1)

The original catalog contained overlays named `creative`, `marketing`, `product`, `dcc`
that collide with identically named base profiles. With "overlays wins on collision"
semantics, `overlays: ["creative"]` would apply the small overlay, not the full base
profile — breaking the "add 2-3 profiles" use case.

**Fix: remove the four colliding overlays from the catalog.** They were redundant once
base profiles can be used as work contexts. Remaining unique overlays:
`plugin-dev`, `research`, `github-heavy`, `minimal`.

### Resolver change

Change `resolve_effective_profile` to look up each work context name in two places:

1. `catalog["overlays"]` — first priority
2. `catalog["baseProfiles"]` — fallback if not found in overlays

With collisions removed, the fallback is unambiguous. If not found in either, return
`UNKNOWN_OVERLAY` error as before.

```json
{ "base": "dev", "overlays": ["ops", "creative", "github-heavy"] }
```

Here `ops` and `creative` resolve via baseProfiles; `github-heavy` resolves via overlays.
Existing bindings remain valid. No migration needed.

### add_overlay() validation fix (Codex finding #2)

Current `add_overlay()` validates only `catalog["overlays"]`. Fix: also accept names
found in `catalog["baseProfiles"]`. Same fallback logic as the resolver.

Add tests:
- `test_add_overlay_accepts_base_profile_as_work_context`
- `test_cli_add_accepts_base_profile_as_work_context`

## Terminology

The JSON key `overlays` stays unchanged. Documentation renames the concept to
**work contexts** to reflect the expanded semantics: a work context can be a small
task overlay (e.g. `github-heavy`) or a full secondary base profile (e.g. `ops`).

Update `profile-schema.md` and `SKILL.md` to use "work context" language.

## Project Configurator

A new `configure` workflow in `SKILL.md`.

### Flow

1. Run `catalog list` to get profiles and work contexts with descriptions.
2. Show base profiles as a text list (8 items fit in one message), ask user to name one.
3. Run `AskUserQuestion` multiselect for additional work contexts. If the list exceeds
   4 items, split into categorical groups (h2t-*, pm-*, creative/marketing/etc.).
   Present all base profiles (minus the chosen base) and all overlays as candidates.
4. Run `diff` — show changes without writing.
5. Confirm with user before `apply`.

### Safety

- Never apply without showing diff first.
- Stop and ask if `.claude/settings.json` has non-profile content not yet under
  `h2tAgentProfile` management.
- Do not change `permissions`, `hooks`, or `mcpServers`.

## Catalog Editor (Experimental)

Allows editing `agent-profiles.json` through the skill. Marked experimental because
changes affect all repos after `sync`/`apply`.

### Operations supported in v0.2

- `catalog list` — summary of profiles, work contexts, plugin aliases
- `catalog list-plugins` — all known aliases with marketplace IDs
- `catalog add-profile --name --description --enable --disable`
- `catalog edit-profile --name --add-enable --add-disable --remove-enable --remove-disable`
- `catalog add-overlay --name --description --enable --disable`
- `catalog edit-overlay --name --add-enable --add-disable --remove-enable --remove-disable`

### UX in SKILL.md

User describes intent in natural language or short-form:

```
add h2t-creative to creative enable
create profile research: enable h2t-ops, h2t-dev; disable h2t-creative
```

Skill extracts intent, validates aliases via `catalog list-plugins`, calls backend.
Skill always shows the resulting JSON diff and asks for explicit confirmation before writing.
Skill labels all catalog edit output with `[EXPERIMENTAL — affects all repos after sync]`.

### Catalog persistence (Codex finding #3)

Default catalog path is script-relative — in installed plugin mode this points to the
plugin cache, not the source repo. Edits to the cache are lost on reinstall.

**Scope for v0.2:** catalog editor operates only on the source catalog inside the
h2t-skills repo. The skill must detect `plugins/h2t-core/skills/agent-profile/references/`
relative to the repo root and refuse to edit if running from the plugin cache.
Document this limitation explicitly in SKILL.md under the `[EXPERIMENTAL]` label.

### Safety gates

- Backend validates all aliases against `pluginIds` before writing.
- Atomic write (`.tmp` → replace) as in existing `apply_profile`.
- Skill shows diff of catalog JSON before any write.
- Explicit user confirmation required before write.
- No automatic backup in v0.2; diff-before-write is the safety guard.
- Catalog editor refuses to write if catalog path is inside a plugin cache directory.

## New Script Modes

Add a `catalog` subcommand group to `apply_agent_profile.py`:

```bash
python apply_agent_profile.py catalog list [--cwd .]
python apply_agent_profile.py catalog list-plugins [--cwd .]
python apply_agent_profile.py catalog add-profile --name X --description Y --enable a,b --disable c
python apply_agent_profile.py catalog edit-profile --name X --add-enable a,b --remove-disable c
python apply_agent_profile.py catalog add-overlay --name X --description Y --enable a,b
python apply_agent_profile.py catalog edit-overlay --name X --add-enable a --remove-enable b
```

All modes output JSON. Catalog write modes return `{"ok": true, "diff": {...}}` or error.

## Status and Observability

`status` stays as-is (JSON for machines). Add `status --explain` as the primary
observability tool. Per Codex finding #4: backend always returns structured JSON;
SKILL.md instructs Claude to render it as prose. No mixed output contracts.

### `status --explain` output sections

- Current base profile and active work contexts (overlays)
- Effective enabled plugins (resolved from base + work contexts)
- Effective disabled plugins
- Drift: plugins expected by profile but missing from `settings.json enabledPlugins`
- Drift: plugin IDs in `settings.json` not present in catalog (unknown/stale)
- Preserved keys: confirms `permissions`, `hooks`, `mcpServers` are untouched
- Suggested next commands: `add --overlay X`, `remove --overlay X`, `sync`, `/reload-plugins`

### Enhanced `doctor`

Extend `doctor` to detect drift between binding, settings, and resolved profile:

- `binding_exists` — `.claude/agent-profile.json` present
- `settings_exist` — `.claude/settings.json` with `enabledPlugins` present
- `profile_resolvable` — base + work contexts resolve without error
- `settings_matches_profile` — `enabledPlugins` in settings matches resolved profile (drift detection)
- `no_unknown_plugin_ids` — all IDs in `settings.enabledPlugins` exist in current catalog
- `marker_matches_binding` — `h2tAgentProfile` marker in settings matches binding file

`doctor` remains report-only. No writes without explicit user approval.

## Tests to Add

Merge semantics:
- `test_overlay_fallback_to_base_profile` — `overlays: ["ops"]` resolves via baseProfiles
- `test_existing_binding_still_valid` — `{base:"dev", overlays:["creative"]}` resolves via baseProfiles (collision removed)
- `test_unknown_name_not_in_overlays_or_baseprofiles_returns_error`
- `test_add_overlay_accepts_base_profile_as_work_context`
- `test_cli_add_accepts_base_profile_as_work_context`

Catalog editor:
- `test_catalog_add_profile_writes_new_entry`
- `test_catalog_edit_profile_add_enable_removes_from_disable`
- `test_catalog_add_overlay_writes_new_entry`
- `test_catalog_edit_rejects_unknown_alias`
- `test_catalog_write_is_atomic`

Status/observability:
- `test_status_explain_shows_drift_when_settings_mismatch_profile`
- `test_status_explain_shows_unknown_plugin_ids`
- `test_doctor_detects_settings_mismatch_with_resolved_profile`
- `test_doctor_detects_unknown_plugin_ids_in_settings`
- `test_doctor_detects_marker_mismatch`

Sync safety:
- `test_sync_preserves_permissions_and_hooks`

## Files Changed

```
apply_agent_profile.py         — resolver fallback + catalog subcommands + status --explain + enhanced doctor
test_apply_agent_profile.py    — new tests (TDD: tests first)
SKILL.md                       — configure workflow + catalog editor section + status --explain instructions
profile-schema.md              — work contexts terminology
```

No new files. No changes to plugin.json or marketplace.json in this iteration
(version bump after smoke confirms feature works).

## Out of Scope for v0.2

- Skill-level (individual skill) enable/disable — Claude Code API not stable enough
- Global `~/.claude/settings.json` edits
- Permissions, hooks, MCP config
- Automatic backup of catalog before edit
- Conflict resolution UI for overlays that contradict each other's base profile
