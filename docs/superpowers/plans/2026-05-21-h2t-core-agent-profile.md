# h2t-core:agent-profile implementation plan

Date: 2026-05-21
Status: ready for review
Design: docs/superpowers/specs/2026-05-21-h2t-core-agent-profile-design.md

## Goal

Implement `h2t-core:agent-profile`: a project-scoped Claude plugin profile manager with base profiles, temporary task overlays, and cross-machine sync.

The MVP must make repo-specific plugin loading practical without turning global Claude settings into a permanent everything-enabled state.

## Hard Constraints

1. Do not edit global `~/.claude/settings.json` in MVP.
2. Do not edit permissions allowlists.
3. Do not install/uninstall plugins automatically; print exact `/plugin install ...` commands instead.
4. Preserve unknown keys in project `.claude/settings.json`.
5. Only manage `enabledPlugins` and an `h2tAgentProfile` marker block.
6. Do not sync secrets, OAuth tokens, MCP credentials, or machine-local paths.
7. Do not touch legacy `plugins/h2t` in this task.
8. Keep profile catalog values reviewable; do not treat draft membership as final product strategy.
9. Normal commands must be deterministic and non-interactive except for explicit user confirmation in the skill instructions.
10. Keep `SKILL.md` small; put catalog/schema details in references and deterministic logic in Python.

## File Map

Create:

```text
plugins/h2t-core/skills/agent-profile/SKILL.md
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
```

Modify:

```text
plugins/h2t-core/.claude-plugin/plugin.json
.claude-plugin/marketplace.json
```

Optional, only if needed after smoke:

```text
plugins/h2t-core/skills/session-start/SKILL.md
```

No other files are in scope.

## User-Facing Workflows

The skill should guide the agent to run these script modes:

```text
status
recommend
diff
apply <base>
add <overlay>
remove <overlay>
reset
sync
doctor
```

MVP command shape:

```bash
python apply_agent_profile.py status --cwd <repo>
python apply_agent_profile.py recommend --cwd <repo>
python apply_agent_profile.py diff --cwd <repo> --base pos --overlay marketing
python apply_agent_profile.py apply --cwd <repo> --base pos
python apply_agent_profile.py add --cwd <repo> --overlay marketing
python apply_agent_profile.py remove --cwd <repo> --overlay marketing
python apply_agent_profile.py reset --cwd <repo>
python apply_agent_profile.py sync --cwd <repo>
python apply_agent_profile.py doctor --cwd <repo>
```

Script output must be JSON by default. The skill translates important fields into concise human guidance.

## Data Contracts

### `.claude/agent-profile.json`

Project-portable binding, committed when appropriate:

```json
{
  "base": "pos",
  "overlays": [],
  "updatedAt": "2026-05-21",
  "catalogVersion": 1
}
```

### `.claude/settings.json`

Project settings generated/updated by the script. Unknown keys preserved.

```json
{
  "h2tAgentProfile": {
    "base": "pos",
    "overlays": [],
    "managedBy": "h2t-core:agent-profile",
    "updatedAt": "2026-05-21"
  },
  "enabledPlugins": {
    "h2t-core@lichtpfad": true,
    "h2t-ops@lichtpfad": true,
    "h2t-creative@lichtpfad": false
  }
}
```

### Catalog

`agent-profiles.json` must separate base profiles from overlays:

```json
{
  "version": 1,
  "pluginIds": {
    "h2t-core": "h2t-core@lichtpfad"
  },
  "baseProfiles": {
    "pos": {
      "description": "Personal OS repository work",
      "enable": ["h2t-core", "h2t-ops", "h2t-dev", "superpowers"],
      "disable": ["h2t-creative", "h2t-dcc", "marketing-playbook"]
    }
  },
  "overlays": {
    "marketing": {
      "description": "Marketing, copy, lead-gen, GTM work",
      "enable": ["marketing-playbook", "lead-search"],
      "disable": []
    }
  }
}
```

Draft catalog membership is allowed in MVP, but it must be clearly marked as draft in `profile-schema.md`.

## Merge Semantics

1. Start with the base profile's `enable` and `disable`.
2. Apply overlays in listed order.
3. Later overlays win on direct conflicts.
4. Explicit `enable` removes the plugin from the effective disabled set.
5. Explicit `disable` removes the plugin from the effective enabled set.
6. Unknown plugin aliases produce a typed error in JSON output.
7. Unknown profile/overlay names produce a typed error in JSON output.

## T0 — Baseline and Existing Behavior

Commit: 0

Steps:

1. Confirm current plugin cleanup state:

   ```bash
   git log --oneline -n 5
   ```

2. Confirm split plugins have no command stubs except legacy `plugins/h2t`:

   ```powershell
   Get-ChildItem plugins -Directory | ForEach-Object {
     $cmd = Join-Path $_.FullName "commands"
     if (Test-Path $cmd) {
       Get-ChildItem $cmd -Filter *.md -File
     }
   }
   ```

3. Confirm per-project disabling still works from the observed experiment:

   - `marketing-playbook@marketing-playbook-plugins: false` removes the plugin from `/context`.
   - Do not rely on this one experimental setting as final profile config.

4. No commit in T0.

## T1 — Catalog, Schema, and Pure Merge Tests

Commit: 1

Files:

```text
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
```

TDD steps:

1. Create `test_apply_agent_profile.py` first with tests for pure functions:

   - `test_load_catalog_rejects_unknown_plugin_alias`
   - `test_resolve_base_profile_to_enabled_plugins`
   - `test_overlay_enable_wins_over_base_disable`
   - `test_later_overlay_disable_wins`
   - `test_unknown_base_profile_returns_error_payload`
   - `test_unknown_overlay_returns_error_payload`

2. Run the test file and confirm failures because implementation does not exist yet:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   ```

3. Implement minimal pure functions in `apply_agent_profile.py`:

   - `load_catalog(path: Path) -> dict`
   - `resolve_effective_profile(catalog, base, overlays) -> dict`
   - `error(code: str, message: str, **extra) -> dict`

4. Create `agent-profiles.json` with draft base profiles:

   - `dev`
   - `pos`
   - `ops`
   - `creative`
   - `dcc`
   - `product`
   - `marketing`
   - `mixed`

5. Create overlays:

   - `plugin-dev`
   - `creative`
   - `marketing`
   - `product`
   - `research`
   - `dcc`
   - `github-heavy`
   - `minimal`

6. Add `profile-schema.md` explaining:

   - catalog fields;
   - conflict resolution;
   - draft status of plugin membership;
   - safety rule that catalog is not a permissions model.

7. Verify:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   ```

8. Commit:

   ```bash
   git add plugins/h2t-core/skills/agent-profile/references/agent-profiles.json \
     plugins/h2t-core/skills/agent-profile/references/profile-schema.md \
     plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py \
     plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   git commit -m "feat(h2t-core): add agent profile catalog and merge logic"
   ```

## T2 — Settings Read/Write and Project Binding

Commit: 1

Files:

```text
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
```

TDD steps:

1. Add tests:

   - `test_apply_creates_agent_profile_json`
   - `test_apply_preserves_unknown_settings_keys`
   - `test_apply_updates_only_enabled_plugins_and_marker`
   - `test_apply_does_not_modify_permissions`
   - `test_reset_returns_to_base_without_overlays`
   - `test_add_overlay_updates_binding_and_settings`
   - `test_remove_overlay_updates_binding_and_settings`

2. Implement:

   - `load_json(path, default)`
   - `write_json_atomic(path, data)`
   - `load_project_binding(cwd)`
   - `write_project_binding(cwd, binding)`
   - `load_project_settings(cwd)`
   - `write_project_settings(cwd, settings)`
   - `apply_profile(cwd, base, overlays, *, dry_run=False)`
   - `add_overlay(cwd, overlay, *, dry_run=False)`
   - `remove_overlay(cwd, overlay, *, dry_run=False)`
   - `reset_profile(cwd, *, dry_run=False)`

3. Atomic writes:

   - write to sibling `.tmp`;
   - replace target;
   - create parent `.claude` directory if missing.

4. Do not create backups in MVP unless tests show it is needed; dry-run diff is the first safety guard.

5. Verify:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   ```

6. Commit:

   ```bash
   git add plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py \
     plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   git commit -m "feat(h2t-core): manage project agent profile settings"
   ```

## T3 — CLI Modes, Status, Recommend, Sync, Doctor

Commit: 1

Files:

```text
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
```

TDD steps:

1. Add CLI-level tests using `tempfile`/`tmp_path`-style helpers:

   - `test_cli_status_without_profile_returns_unconfigured`
   - `test_cli_recommend_h2t_skills_returns_dev_or_mixed`
   - `test_cli_diff_does_not_write_files`
   - `test_cli_sync_uses_existing_binding`
   - `test_cli_doctor_reports_missing_plugins_without_installing`
   - `test_cli_outputs_json`

2. Implement `argparse` subcommands:

   - `status`
   - `recommend`
   - `diff`
   - `apply`
   - `add`
   - `remove`
   - `reset`
   - `sync`
   - `doctor`

3. Recommendation heuristic:

   - `plugins/h2t-core` or `.claude-plugin/marketplace.json` present → `dev`
   - `h2t_ops` or `plugins/h2t-ops` present → `ops`
   - `CLAUDE.md` plus POS rule files → `pos`
   - `plugins/h2t-creative` or creative docs → `creative`
   - `.toe`, `.hip`, TouchDesigner/Houdini markers → `dcc`
   - otherwise → `mixed`

4. `doctor` checks:

   - profile binding exists;
   - project settings exist;
   - effective plugin ids are known;
   - missing installed plugin data if a machine-state file exists;
   - duplicate command stubs in current repo if it is an h2t plugin repo;
   - stale cache detection is report-only in MVP.

5. Verify all tests.

6. Commit:

   ```bash
   git add plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py \
     plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   git commit -m "feat(h2t-core): add agent profile CLI modes"
   ```

## T4 — Skill Entry and Plugin Metadata

Commit: 1

Files:

```text
plugins/h2t-core/skills/agent-profile/SKILL.md
plugins/h2t-core/.claude-plugin/plugin.json
.claude-plugin/marketplace.json
```

Steps:

1. Create `SKILL.md` with:

   - `name: h2t-core:agent-profile`
   - concise trigger description;
   - command table;
   - safety constraints;
   - instruction to show script JSON result;
   - instruction to tell user to run `/reload-plugins` after changes.

2. Keep `SKILL.md` under 180 lines.

3. Bump `h2t-core` patch version.

4. Update root marketplace entry for `h2t-core` patch version.

5. Verify:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py
   ```

6. Commit:

   ```bash
   git add plugins/h2t-core/skills/agent-profile/SKILL.md \
     plugins/h2t-core/.claude-plugin/plugin.json \
     .claude-plugin/marketplace.json
   git commit -m "feat(h2t-core): add agent profile skill"
   ```

## T5 — Local Smoke In h2t-skills

Commit: 0 unless drift is found.

Steps:

1. Run status:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py status --cwd .
   ```

2. Run recommend:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py recommend --cwd .
   ```

3. Run dry diff:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py diff --cwd . --base dev --overlay plugin-dev
   ```

4. Apply to `h2t-skills` only if user explicitly approves because this repo has existing `.claude/settings.json` local edits.

5. If approved, run:

   ```bash
   python plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py apply --cwd . --base dev
   ```

6. Ask user to run:

   ```text
   /plugin marketplace update
   /plugin uninstall h2t-core@lichtpfad
   /plugin install h2t-core@lichtpfad
   /reload-plugins
   /context
   ```

7. Confirm:

   - `h2t-core:agent-profile` appears once;
   - expected plugins are present;
   - disabled plugin from a profile is absent if applied;
   - no permissions settings changed.

## T6 — Cross-Machine Sync Dry Run

Commit: 0 unless documentation drift is found.

Steps:

1. In a temporary directory, create only:

   ```text
   .claude/agent-profile.json
   .claude/settings.json
   ```

2. Run `sync --cwd <tmp>`.

3. Confirm it updates only project settings, prints missing plugin commands, and does not require global settings.

4. Record evidence in final issue/comment text if this becomes a GitHub issue.

## Verification Checklist

Before final:

- `python plugins/h2t-core/skills/agent-profile/scripts/test_apply_agent_profile.py` passes.
- `git diff --check` passes for touched files.
- `SKILL.md` has no TODO/TBD placeholders.
- `agent-profiles.json` is valid JSON.
- Applying profile preserves unrelated settings keys.
- Applying profile does not change permissions allowlists.
- `sync` does not install/uninstall plugins.
- `doctor` is report-only.
- Existing `h2t-core` skills still list normally.

## Risk Notes

- Per-project `enabledPlugins` behavior was validated by experiment, but it is not deeply documented here. Keep MVP reversible and diff-first.
- Catalog membership is subjective. Treat it as draft data, not architecture law.
- User/global skills are outside this MVP; this solves plugin profiles, not the full `User` skill list.
- Claude Code plugin ids include marketplace suffixes. Wrong ids will silently fail from the user's point of view, so `doctor` must surface unknown/missing ids clearly.

## Stop Conditions

Stop and ask before:

- editing global `~/.claude/settings.json`;
- changing permissions blocks;
- uninstalling plugins;
- deleting plugin caches;
- applying a profile to a dirty project settings file without showing a diff;
- changing legacy `plugins/h2t`.

