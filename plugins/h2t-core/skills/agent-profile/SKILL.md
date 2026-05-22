---
name: h2t-core:agent-profile
description: >
  Project-scoped Claude plugin profile manager. Apply base profiles (dev, pos, ops, creative,
  dcc, product, marketing, mixed) and task overlays (plugin-dev, creative, marketing, product,
  research, dcc, github-heavy, minimal) to control which plugins load per repo.
  Triggers: "agent-profile", "apply profile", "plugin profile", "set profile", "профиль плагинов".
---

# h2t-core:agent-profile

Manage which plugins Claude loads for the current repository. Writes only `enabledPlugins`
and an `h2tAgentProfile` marker to `.claude/settings.json`. Never touches permissions,
MCP config, hooks, or global `~/.claude/settings.json`.

## Script location

```
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
```

Call it with the project Python (no venv needed — stdlib only):

```bash
python <script> <mode> --cwd <repo>
```

## Commands

| Mode | Effect |
|------|--------|
| `status` | Show current binding, overlays, enabled plugins |
| `recommend` | Inspect repo signals, suggest base profile |
| `diff --base <name>` | Show changes without writing |
| `apply --base <name>` | Write binding + settings |
| `add --overlay <name>` | Add overlay to current binding |
| `remove --overlay <name>` | Remove overlay |
| `reset` | Strip overlays, reapply base |
| `sync` | Re-apply committed binding on current machine |
| `doctor` | Report missing plugins, stale binding (report-only) |

## Base profiles

`dev` · `pos` · `ops` · `creative` · `dcc` · `product` · `marketing` · `mixed`

## Task overlays

`plugin-dev` · `creative` · `marketing` · `product` · `research` · `dcc` · `github-heavy` · `minimal`

## Workflow

**First time in a repo:**

```
recommend → diff --base <name> → apply --base <name>
```

Ask user to confirm before running `apply` if `.claude/settings.json` already has content.
Always show diff output before writing.

**Adding temporary work context:**

```
add --overlay <name>
```

**Syncing to another machine after `git pull`:**

```
sync
```

Then tell user: run `/plugin marketplace update`, `/plugin install` for any missing plugins
listed in output, then `/reload-plugins`.

## Safety rules

1. Never write to global `~/.claude/settings.json`.
2. Never edit `permissions` allowlists.
3. Never install or uninstall plugins — print the exact `/plugin install ...` commands instead.
4. Always show `diff` output before `apply`. If user did not request apply, stop at diff.
5. Stop and ask before applying to a repo with an existing non-profile `.claude/settings.json`.
6. `doctor` is report-only — no fixes without explicit user approval.

## Output

All script modes return JSON. Translate key fields into concise human guidance:

- `status.unconfigured` → "No profile set. Run `recommend` to get a suggestion."
- `sync.message` → show verbatim.
- `doctor.checks` → list failing checks, suggest fixes.
- `error.message` → show verbatim, suggest corrective action.

After any write: tell user to run `/reload-plugins` to apply changes.

## Catalog

Profile definitions live in:
```
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json
```

Schema documented in:
```
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
```
