---
name: agent-profile
description: >
  Project-scoped Claude plugin profile manager. Apply base profiles (dev, pos, ops, creative,
  dcc, product, marketing, mixed) and work contexts to control which plugins load per repo.
  Supports profile:name and overlay:name explicit refs plus bare-name legacy compat.
  Triggers: "agent-profile", "apply profile", "plugin profile", "set profile", "configure plugins",
  "профиль плагинов", "конфигуратор профиля".
compatibility: "Claude Code. Requires the h2t-ops CLI (h2t-agent-profile). The catalog
  editor operates on the h2t-skills checkout — it edits the source profile catalog and
  refuses to write when that catalog is absent."
metadata:
  author: lichtpfad
  version: 0.2.0
---

# h2t-core:agent-profile

Manage which plugins Claude loads for the current repository. Writes only `enabledPlugins`
and an `h2tAgentProfile` marker to `.claude/settings.json`. Never touches permissions,
MCP config, hooks, or global `~/.claude/settings.json`.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Command

Every mode below is a positional of one command:

```bash
h2t-agent-profile status --cwd "$(pwd)"
```

The general form is `h2t-agent-profile <mode> [options] --cwd <repo>`.

## Commands

| Mode | Effect |
|------|--------|
| `status` | Show binding and enabled plugins (machine JSON) |
| `status --explain` | Human-readable report: base, work contexts, enabled/disabled plugins, drift |
| `recommend` | Inspect repo signals, suggest base profile |
| `diff --base <name>` | Show changes without writing |
| `apply --base <name>` | Write binding + settings |
| `add --context <ref>` | Add a work context (`profile:ops`, `overlay:github-heavy`, or bare name) |
| `remove --context <ref>` | Remove a work context |
| `reset` | Strip work contexts, reapply base |
| `sync` | Re-apply committed binding on current machine |
| `doctor` | Drift report: binding / settings / profile resolution / unknown IDs (report-only) |
| `catalog list` | Summary of profiles, overlays, plugin count |
| `catalog list-plugins` | All known plugin aliases with marketplace IDs |
| `catalog add-profile` | [EXPERIMENTAL] Add a new base profile to the catalog |
| `catalog edit-profile` | [EXPERIMENTAL] Edit plugin lists in an existing base profile |
| `catalog add-overlay` | [EXPERIMENTAL] Add a new overlay to the catalog |
| `catalog edit-overlay` | [EXPERIMENTAL] Edit plugin lists in an existing overlay |

## Work context refs

- `profile:ops` — stack the full `ops` base profile as an additional work context
- `overlay:github-heavy` — add a small task overlay
- `creative` (bare) — overlay-first, then base-profile fallback (legacy compat)

## Base profiles

`dev` · `pos` · `ops` · `creative` · `dcc` · `product` · `marketing` · `mixed`

## Task overlays

`plugin-dev` · `creative` · `marketing` · `product` · `dcc` · `research` · `github-heavy` · `minimal`

## Project configurator workflow

Use this when user wants to set or change which plugins load in the current repo.

1. Run `catalog list --cwd <repo>` → get base profiles and overlays with descriptions
2. Show base profiles as a text list; ask user to type the name of the one that fits
3. Ask: "Any additional work contexts? (profile: or overlay: refs, comma-separated, or none)"
   — present examples: `profile:ops, overlay:github-heavy`
   — if user is unsure, show all options grouped: base profiles as `profile:X`, overlays as `overlay:X`
4. Run `diff --base <chosen> --cwd <repo>` (add `--context <ref>` per work context)
5. Show the diff output; ask for confirmation before writing
6. Run `apply --base <chosen> --cwd <repo>` (add `--context <ref>` per work context)
7. Tell user: run `/plugin marketplace update`, install any missing plugins, then `/reload-plugins`

**Stop before apply if** `.claude/settings.json` has existing permissions/hooks not yet seen.
**Always show diff first.** Never write without user confirmation.

## Catalog editor workflow (EXPERIMENTAL)

[EXPERIMENTAL — catalog changes affect all repos after sync/apply]

Only works on the source catalog in the h2t-skills repo. Refuses to write if the catalog
path resolves inside a plugin cache directory.

When user describes intent (e.g. "add h2t-creative to pos enable"):
1. Run `catalog list-plugins` to validate the alias exists
2. Confirm the intended operation with the user
3. Run the appropriate `catalog edit-profile` or `catalog edit-overlay` command
4. Show the returned diff; confirm with user before committing

For a new profile:
1. Ask: name, description, which plugins to enable, which to disable
2. Validate each alias via `catalog list-plugins`
3. Run `catalog add-profile --name X --description Y --enable a,b --disable c`
4. Show diff and commit if user approves

## Safety rules

1. Never write to global `~/.claude/settings.json`.
2. Never edit `permissions` allowlists.
3. Never install or uninstall plugins — print `/plugin install ...` commands instead.
4. Always show `diff` output before `apply`. Stop at diff if user did not request apply.
5. Stop and ask before applying to a repo with an existing non-profile `.claude/settings.json`.
6. `doctor` is report-only — no fixes without explicit user approval.
7. Catalog editor: never write to plugin cache; only source repo catalog.

## Output interpretation

All modes return JSON. Render for the user:

- `status --explain` → prose summary of base, work contexts, drift, suggestions
- `doctor.checks` → list each failing check; suggest `sync` for drift
- `error.message` → show verbatim; suggest corrective action
- Any write result → always show `diff` key before confirming success

After any write: tell user to run `/reload-plugins`.

## Catalog location

`h2t-agent-profile` reads the catalog shipped in the package; in the h2t-skills checkout
that file is the source the catalog editor edits:

```
h2t_ops/resources/agent_profile/agent-profiles.json
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
```

Until the plugin copy (`references/agent-profiles.json`) is retired, a catalog edit goes to
both files; `tests/tools/test_tool_copy_parity.py` fails when they differ.
